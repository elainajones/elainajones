"""HTTP simple server class.

Simplifies creation of simple, non-blocking HTTP servers.
"""

import http.server
import os
import socketserver
from threading import Thread


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler base class wrapper.
    """
    def log_message(self, format, *args):
        """Do nothing instead of logging an arbitrary message.
        """
        pass


class SimpleServer:
    """Simple HTTP file server for file transfer operations.

    Attributes:
        path (str): Directory path to host.
        port (int): HTTP server port.
        url (str): URL to directory root where files are hosted.
    """
    def __init__(self, path=None, port=8080) -> None:
        """Initializes the HTTP server.

        Args:
            path (str): Directory path to host.
            port (int): HTTP server port.

        Returns:
            None
        """
        self.path = path or os.getcwd()
        self.port = port
        self.url = None

        self.__thread = None
        self.__server = None
        self.__handler = QuietHTTPRequestHandler

        if os.path.isfile(self.path):
            self.path = os.path.dirname(self.path)

    def __activate(self) -> None:
        """Start the HTTP server.

        This will be run on a separate thread to avoid blocking the
        parent process.
        """
        os.chdir(self.path)

        self.url = f'http://127.0.0.1:{self.port}'

        with socketserver.TCPServer(("", self.port), self.__handler) as httpd:
            self.__server = httpd
            self.__server.serve_forever()

    def start(self) -> None:
        """Start the HTTP server.

        This will be run on a separate thread to avoid blocking the
        parent process.
        """
        self.__thread = Thread(target=self.__activate)
        self.__thread.start()

    def stop(self) -> None:
        """Stop the running HTTP server.
        """
        self.__server.shutdown()
        self.__thread.join()
