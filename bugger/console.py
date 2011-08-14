"""A Collection of InteractiveConsoles made available through various interfaces


"""
import code
import select
import socket
import sys

_stdout = sys.stdout
_stderr = sys.stderr

DEBUG_TELNET_OPTIONS = False

#===============================================================================
# Telnet Protocol Definition
# 
# In order to at least "work" with most telnet clients, we need to implement
# some basic parts of the telnet protocol.  In particular, we need to handle
# IAC (Interpret As Command) Option specifiers.
#
# Requests and responses for specifying options both have the following form:
# +-----+-------------------+--------+
# | IAC | Operation/Command | Option |
# +-----+-------------------+--------+
#===============================================================================
class TELNET_COMMANDS(object):
    SE = 240
    NOP = 241
    DM = 242
    BRK = 243
    IP = 244
    AO = 245
    AYT = 246
    EC = 247
    EL = 248
    GA = 249
    SB = 250
    WILL = 251
    WONT = 252
    DO = 253
    DONT = 254
    IAC = 255

class TELNET_OPTIONS(object):
    ECHO = 1 # RFC 857
    SUPRESS_GO_AHEAD = 3 # RFC 858
    STATUS = 5 # RFC 859
    TIMING_MARK = 6 # RFC 860
    TERMINAL_TYPE = 24 # RFC 1091
    WINDOW_SIZE = 31 # RFC 1073
    TERMINAL_SPEED = 32 # RFC 1079
    REMOTE_FLOW_CONTROL = 33 # RFC 1372
    LINEMODE = 34 # RFC 1184
    ENVIRONMENT_VARIABLES = 36 # RFC 1408

class StreamInteractiveConsole(code.InteractiveConsole):
    """Interactive console that works off an input and output stream"""

    def __init__(self, input_stream, output_stream, locals=None):
        """Initialize an interactive interpreter talking to the provided streams

        Both ``input_stream`` and ``output_stream`` are assumed to be file-like
        objects.
        """
        code.InteractiveConsole.__init__(self, locals)
        self.input_stream = input_stream
        self.output_stream = output_stream
        self._asyn_more = 0
        self._byte_buffer = ''
    
    def async_init(self, banner=None, ps1=None, ps2=None):
        """Initialize the interpreter when operating in async mode

        This will push out the banner and other intro items.  After this
        call returns, further input that comes in through whatever channel
        should be piped through ``async_input()``, the result will be written
        back out the output channel when there is something to write.
        """
        if ps1 is not None:
            sys.ps1 = ps1
        if ps2 is not None:
            sys.ps2 = ps2

        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = ">>> "
        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = "... "

        cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
        if banner is None:
            self.write("Python %s on %s\r\n%s\r\n(%s)\r\n" % 
                       (sys.version, sys.platform, cprt,
                        self.__class__.__name__))
        else:
            self.write("%s\r\n" % str(banner))

        self.write(sys.ps1)

    def async_recv(self, bytes=''):
        """Notify this console that there is data to receive"""
        if not bytes:
            bytes = self.input_stream.read()
        encoding = getattr(sys.stdin, 'encoding', None)
        unpushed_bytes = ''.join([self._byte_buffer, bytes])
        
        # split on both \r\n and \n (effectively convert to just \n)
        if not '\n' in unpushed_bytes:
            self._byte_buffer += bytes
        else:
            for line in ('\n'.join(unpushed_bytes.rstrip().split('\r\n'))).split('\n'):
                if line == '\x04': # EOF
                    raise SystemExit
                if encoding and not isinstance(line, unicode):
                    line = line.decode(encoding)
                self._asyn_more = self.push(line)
            
            # only write prompt if we are done with all lines and we did in
            # fact receive a line.  This makes things work out nicer if they
            # can push multiple lines at once (some clients)
            if self._asyn_more:
                prompt = sys.ps2
            else:
                prompt = sys.ps1
            self._byte_buffer = ''
            self.write(prompt)
    
            return bytes

    def close(self):
        """Close the input and output streams"""
        self.input_stream.close()
        self.output_stream.close()

    def raw_input(self, prompt=''):
        """Override the default behaviour of raw_input to write to the stream"""
        # TODO: we would like to do non-blocking input
        self.output_stream.write(prompt)
        return self.input_stream.readline().rstrip()

    def write(self, data):
        """Write the specified data to the output stream"""
        self.output_stream.write(data)

class _TelnetStream(object):
    """Wrap raw stream and make console and telnet play nice with each other"""
    
    def __init__(self, stream):
        self.stream = stream
    
    def _handle_telnet_option(self, option_bytes):
        assert len(option_bytes) == 3
        assert option_bytes[0] == chr(TELNET_COMMANDS.IAC)
        command, option = [ord(x) for x in option_bytes[1:]]
        if DEBUG_TELNET_OPTIONS:
            inverse_command_map = dict([(v, k) for (k, v) in TELNET_COMMANDS.__dict__.items() if not k.startswith('_')])
            inverse_options_map = dict([(v, k) for (k, v) in TELNET_OPTIONS.__dict__.items() if not k.startswith('_')])
            command_description = inverse_command_map.get(command, "Unknown")
            option_description = inverse_options_map.get(option, "Unknown")
            _stdout.write(self.write("TELNET: Command/Option = %s/%s, %s/%s\r\n" % (command, option, command_description, option_description)))
    
    def __getattr__(self, attr):
        return getattr(self.stream, attr)
    
    def sanitize_input(self, data):
        # first, check for any special telnet sequences (IAC = Interpret As Command)
        IAC = chr(TELNET_COMMANDS.IAC)
        while IAC in data:
            # check to ensure that there are 3 bytes following IAC, as we are
            # dealing with a stream of data
            iac_index = data.index(IAC)
            if iac_index + 3 <= len(data):
                telnet_option_bytes = data[iac_index:iac_index + 3]
                data = data[:iac_index] + data[iac_index+3:]
                self._handle_telnet_option(telnet_option_bytes)
            else:
                break
        
        return data.replace('\r\n', '\n')

    def read(self, *args, **kwargs):
        underlying_read = self.stream.read(*args, **kwargs)
        return self.sanitize_input(underlying_read)
    
    def write(self, s):
        # for telnet, convert newlines to always be \r\n
        self.stream.write(s.replace('\r\n', '\n').replace('\n', '\r\n'))

class TelnetInteractiveConsoleServer(object):
    """Make an interactive console available via telnet which can interact with your app"""

    def __init__(self, host='0.0.0.0', port=7070, locals=None, select_timeout=5.0):
        self.host = host
        self.port = port
        self.select_timeout = select_timeout
        self.locals = locals
        self.has_exit = False
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client_sockets = {}

    def client_connect(self, client):
        """Called when a client successfully connected to the server

        Might be overridden in subclasses.
        client is the socket object of the client connection.
        """
        pass

    def client_disconnect(self, client):
        """Called when a client is about to disconnected from the server

        Might be overridden in subclasses.
        client is the socket object of the client connection.
        """
        pass

    def stop(self):
        """Cleanly shutdown and kill this console session"""
        self.has_exit = True

    def accept_interactions(self):
        """Accept and interact with clients via telnet

        This is the main beef of the application and a blocking call.  If you
        desire to run your telnet session inside of a separate thread, you can
        do something like the following...

            >>> # doctest: +SKIP
            >>> import threading
            >>> from bugger.console import TelnetInteractiveConsole
            >>> console = TelnetInteractiveConsole(port=7070)
            >>> t = threading.Thread(name="Telnet Interactive Session",
                                     target=console.accept_interactions)
            >>> # ...
            >>> console.stop() # this will end the target method and thread

        """
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5) # backlog a few connections

        while not self.has_exit:
            rl = select.select(self.client_sockets.keys() + [self.server_sock], [], [], self.select_timeout)[0]
            if self.server_sock in rl:
                rl.remove(self.server_sock) # we process others as normal
                client, _addr = self.server_sock.accept() # accept the connection
                client_console = StreamInteractiveConsole(_TelnetStream(client.makefile('r', 0)),
                                                          _TelnetStream(client.makefile('w', 0)),
                                                          self.locals)
                client_console.async_init()
                self.client_sockets[client] = client_console
                self.client_connect(client)

            for client in rl:
                bytes = client.recv(1024)
                if bytes == '': # client disconnect
                    self.client_disconnect(client)
                    client.close()
                    del self.client_sockets[client]
                else:
                    client_console = self.client_sockets[client]
                    bytes = client_console.input_stream.sanitize_input(bytes)
                    if len(bytes) == 0:
                        continue
                    sys.stdout = client_console.output_stream
                    sys.stderr = client_console.output_stream
                    try:
                        bytes = client_console.async_recv(bytes)
                    except (SystemExit,):
                        sys.stdout = _stdout
                        sys.stderr = _stderr
                        client_console.close()
                        client.close()
                        del self.client_sockets[client]
        
        # after main loop, ensure that we perform cleanup
        try:
            self.server_sock.close()
        except socket.error:
            pass

if __name__ == '__main__':
    print "Starting python telnet server on port 7070"
    console_server = TelnetInteractiveConsoleServer(host='0.0.0.0', port=7070, locals=locals())
    console_server.accept_interactions()
