"""An ephemeral loopback relay serves provider media to the native player."""
import mimetypes
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import requests

from opal.plugins.librarysync.lib.provider import SyncError


class MediaStream:
    def __init__(self, provider, item, cancel):
        route = '/' + secrets.token_urlsafe(32) + '/media' + Path(item.name).suffix
        mime = mimetypes.guess_type(item.name)[0] or 'application/octet-stream'

        class Handler(BaseHTTPRequestHandler):
            def valid(self):
                if self.path != route or cancel.is_set():
                    self.send_error(404)
                    return False
                return True

            def do_HEAD(self):
                if self.valid():
                    self.send_response(200)
                    self.send_header('Content-Length', str(item.size))
                    self.send_header('Content-Type', mime)
                    self.send_header('Accept-Ranges', 'bytes')
                    self.end_headers()

            def do_GET(self):
                if not self.valid():
                    return
                byte_range = self.headers.get('Range', '')
                if byte_range and not re.fullmatch(r'bytes=(?:\d+-\d*|-\d+)', byte_range):
                    self.send_error(416)
                    return
                try:
                    with provider.stream(item, byte_range, cancel) as response:
                        self.send_response(response.status_code)
                        self.send_header('Content-Type', response.headers.get('Content-Type', mime))
                        self.send_header('Accept-Ranges', 'bytes')
                        self.send_header('Cache-Control', 'no-store')
                        for key in ('Content-Length', 'Content-Range'):
                            if key in response.headers:
                                self.send_header(key, response.headers[key])
                        self.end_headers()
                        for chunk in response.iter_content(256 * 1024):
                            if cancel.is_set():
                                break
                            self.wfile.write(chunk)
                except (OSError, SyncError, requests.RequestException):
                    self.close_connection = True

            def log_message(self, *args):
                pass

        class Server(ThreadingHTTPServer):
            # server_close joins bounded request handlers before the tracked worker exits.
            daemon_threads = False

            def get_request(self):
                connection, address = super().get_request()
                connection.settimeout(5)
                return connection, address

        self.server = Server(('127.0.0.1', 0), Handler)
        self.server.timeout = 0.25
        self.url = f'http://127.0.0.1:{self.server.server_port}{route}'
        self.cancel = cancel

    def serve(self):
        try:
            while not self.cancel.is_set():
                self.server.handle_request()
        finally:
            self.server.server_close()
