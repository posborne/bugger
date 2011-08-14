import os
import telnetlib
import threading
import sys
import time
import unittest

# TODO: hack!
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from bugger import console

class TestTelnetInteractiveConsole(unittest.TestCase):
    # Test the TelnetInteractiveConsoleServer implementation.
    # 
    # This isn't strictl a "unit test" as it involves us spawning threads and
    # blocking for some period of time between tests (not ideal).  It is, however,
    # an effect realistic test of the code.
    
    HOST = '127.0.0.1'
    PORT = 5665 # unlikely to be in use
    TIMEOUT = 0.05 # we want to exit quickly
    
    def setUp(self):
        # for each test, we would like to have a fresh telnet
        # session to a known-state telnet session
        self.remote_session_locals = {}
        self.server_console = console.TelnetInteractiveConsoleServer(
            host=self.HOST,
            port=self.PORT,
            select_timeout=self.TIMEOUT,
            locals=self.remote_session_locals)
        self.server_thread = threading.Thread(target=self.server_console.accept_interactions)
    
    def tearDown(self):
        self.server_console.stop()
        self.server_thread.join()
    
    def _make_telnet_connection(self):
        telnet_connection = telnetlib.Telnet() # w/o host/port __init__ does not connect
        telnet_connection.open(self.HOST, self.PORT, 5.0)
        return telnet_connection

    def test_basic_interaction(self):
        # Test that the basic with a single client work as expected
        self.server_thread.start()
        telnet_connection = self._make_telnet_connection()
        try:
            telnet_connection.read_until(">>> ") # no assertion here, too much platform junk
            
            # >>> import sys
            telnet_connection.write("import sys\r\n")
            self.assertEqual(telnet_connection.read_until(">>> ", 1.0), ">>> ")
            
            # >>> print sys.version
            # ...
            telnet_connection.write("print sys.version\r\n")
            self.assertEqual(telnet_connection.read_until(">>> ", 1.0), "%s\r\n>>> " % sys.version)
            
            # a = 3.14
            telnet_connection.write("a = 3.14\r\n")
            self.assertEqual(telnet_connection.read_until(">>> ", 1.0), ">>> ")
            
            # >>> int(a * 1000)
            # 314000
            telnet_connection.write("int(a * 1000)\r\n")
            self.assertEqual(telnet_connection.read_until(">>> ", 1.0), "3140\r\n>>> ")
        finally:
            telnet_connection.close()

    def test_console_state_sharing(self):
        # Show that the state from one client to another is in fact operating on
        # the same locals, at least.  This is as much a demo as anything else
        self.server_thread.start()
        tc1 = self._make_telnet_connection()
        tc2 = self._make_telnet_connection()
        try:
            tc1.read_until(">>> ")
            tc2.read_until(">>> ")
        
            # Connection 1:
            # >>> a = 10
            tc1.write("a = 10\r\n")
            tc1.read_until(">>> ")
            
            # Connection 2:
            # >>> a
            # 10
            tc2.write("a\r\n")
            self.assertEqual(tc2.read_until(">>> "), "10\r\n>>> ")
        finally:
            tc1.close()
            tc2.close()

if __name__ == '__main__':
    unittest.main()
