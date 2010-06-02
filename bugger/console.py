"""A Collection of InteractiveConsoles made available through various interfaces


"""
import code
import select
import socket
import sys
import SimpleHTTPServer

_stdout = sys.stdout
_stderr = sys.stderr

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
            self.write("Python %s on %s\n%s\n(%s)\n" %
                       (sys.version, sys.platform, cprt,
                        self.__class__.__name__))
        else:
            self.write("%s\n" % str(banner))
        
        self.write(sys.ps1)
    
    def async_recv(self, bytes=''):
        """Notify this console that there is data to receive"""
        bytes = self.input_stream.read()
        encoding = getattr(sys.stdin, 'encoding', None)

        # split on both \r\n and \n
        for line in '\n'.join(bytes.rstrip().split('\r\n')).split('\n'):
            if line == '\x04': # EOF
                raise SystemExit
            if encoding and not isinstance(line, unicode):
                line = line.decode(encoding)
            self._asyn_more = self.push(line)
            
            if self._asyn_more:
                prompt = sys.ps2
            else:
                prompt = sys.ps1
            self.write(prompt)
        
        return bytes
    
    def raw_input(self, prompt=''):
        """Override the default behaviour of raw_input to write to the stream"""
        # TODO: we would like to do non-blocking input
        self.output_stream.write(prompt)
        return self.input_stream.readline().rstrip()
    
    def write(self, data):
        """Write the specified data to the output stream"""
        self.output_stream.write(data)

class TelnetInteractiveConsoleServer(object):
    """Make an interactive console available via telnet which can interact with your app
    
    
    """
    
    def __init__(self, port=7070, locals=None):
        self.port = port
        self.has_exit = False
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.client_sockets = {}
    
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
        self.server_sock.bind(('0.0.0.0', self.port))
        self.server_sock.listen(5) # backlog a few connections
        
        while not self.has_exit:
            rl = select.select(self.client_sockets.keys() + [self.server_sock], [], [], 5.0)[0]
            if self.server_sock in rl:
                rl.remove(self.server_sock) # we process others as normal
                client, _addr = self.server_sock.accept() # accept the connection
                client_console = StreamInteractiveConsole(client.makefile('r', 0), 
                                                          client.makefile('w', 0))
                client_console.async_init()
                self.client_sockets[client] = client_console
            
            for client in rl:
                bytes = client.recv(1024)
                if bytes == '': # client disconnect
                    client.close()
                    del self.client_sockets[client]
                else:
                    client_console = self.client_sockets[client]
                    sys.stdout = client_console.output_stream
                    sys.stderr = client_console.output_stream
                    try:
                        bytes = client_console.async_recv()
                    except (SystemExit,):
                        sys.stdout = _stdout
                        sys.stderr = _stderr
                        client_console.input_stream.close()
                        client_console.output_stream.close()
                        client.close()
                        del self.client_sockets[client]

if __name__ == '__main__':
    console_server = TelnetInteractiveConsoleServer(port=7070, locals=locals())
    console_server.accept_interactions()
