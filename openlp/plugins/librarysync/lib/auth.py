"""Google Desktop OAuth with PKCE and OS-backed token storage."""
import base64
import hashlib
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import keyring
import requests

from openlp.plugins.librarysync.lib.provider import SyncError


TOKEN_URL = 'https://oauth2.googleapis.com/token'
SCOPE = 'https://www.googleapis.com/auth/drive'
SERVICE = 'OpenLP+ Library Sync Google Drive'


class TokenStore:
    """Fail closed when the OS has no encrypted credential store."""

    def __init__(self, client_id):
        self.account = hashlib.sha256(client_id.encode()).hexdigest()
        backend = keyring.get_keyring()
        candidates = getattr(backend, 'backends', [backend])
        secure_modules = ('keyring.backends.macOS', 'keyring.backends.Windows', 'keyring.backends.SecretService',
                          'keyring.backends.libsecret', 'keyring.backends.kwallet')
        self.backend = next((item for item in candidates
                             if type(item).__module__.startswith(secure_modules) and item.priority > 0), None)
        if self.backend is None:
            raise SyncError('Unlock or install your operating system’s credential store to connect to Google Drive.')

    def load(self):
        try:
            raw = self.backend.get_password(SERVICE, self.account)
            return json.loads(raw) if raw else {}
        except Exception as error:
            raise SyncError('Could not read the Google Drive sign-in from the OS credential store.') from error

    def save(self, token):
        try:
            self.backend.set_password(SERVICE, self.account, json.dumps(token))
        except Exception as error:
            raise SyncError('Could not save the sign-in. Unlock your OS credential store and retry.') from error

    def delete(self):
        try:
            if self.backend.get_password(SERVICE, self.account):
                self.backend.delete_password(SERVICE, self.account)
        except Exception as error:
            raise SyncError('Could not remove the Google Drive sign-in from the credential store.') from error


class GoogleAuth:
    def __init__(self, client, store=None):
        self.client = client
        self.store = store or TokenStore(client['client_id'])
        self.token = self.store.load()

    def exchange(self, fields):
        try:
            response = requests.post(TOKEN_URL, data={**self.client, **fields}, timeout=(10, 30))
            if response.status_code != 200:
                raise SyncError('Google sign-in expired or was refused. '
                                'Reconnect and check the organisation’s OAuth setup.')
            token = response.json()
            if not isinstance(token.get('access_token'), str):
                raise SyncError('Google returned an invalid sign-in response.')
            token['expires_at'] = time.time() + int(token.get('expires_in', 3600))
            token['refresh_token'] = token.get('refresh_token') or self.token.get('refresh_token', '')
            self.store.save(token)
            self.token = token
        except requests.RequestException as error:
            raise SyncError('Could not contact Google sign-in. Check your internet connection and retry.') from error

    def access_token(self):
        if self.token.get('access_token') and self.token.get('expires_at', 0) > time.time() + 60:
            return self.token['access_token']
        if not self.token.get('refresh_token'):
            raise SyncError('Connect to Google Drive to sign in with your own account.')
        self.exchange({'grant_type': 'refresh_token', 'refresh_token': self.token['refresh_token']})
        return self.token['access_token']

    def sign_in(self, cancel, open_browser):
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        result = {}

        class Callback(BaseHTTPRequestHandler):
            def do_GET(self):
                query = parse_qs(urlparse(self.path).query)
                valid = (urlparse(self.path).path == '/oauth2callback'
                         and secrets.compare_digest(query.get('state', [''])[0], state))
                if valid and ('code' in query or 'error' in query):
                    result.update(query)
                self.send_response(200 if valid else 400)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(b'You can return to OpenLP+.' if valid else b'Invalid sign-in response.')

            def log_message(self, *args):
                pass  # OAuth codes must never enter request logs.

        class LoopbackServer(HTTPServer):
            def get_request(self):
                connection, address = super().get_request()
                connection.settimeout(1)
                return connection, address

        with LoopbackServer(('127.0.0.1', 0), Callback) as server:
            server.timeout = 0.5
            redirect = f'http://127.0.0.1:{server.server_port}/oauth2callback'
            open_browser('https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
                'client_id': self.client['client_id'], 'redirect_uri': redirect, 'response_type': 'code',
                'scope': SCOPE, 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
                'access_type': 'offline', 'prompt': 'consent select_account'}))
            deadline = time.monotonic() + 180
            while not result and not cancel.is_set() and time.monotonic() < deadline:
                server.handle_request()
            if cancel.is_set():
                raise SyncError('Sign-in cancelled.')
            if 'code' not in result:
                raise SyncError('Google sign-in was cancelled or timed out. Choose Connect to try again.')
            self.exchange({'grant_type': 'authorization_code', 'code': result['code'][0],
                           'code_verifier': verifier, 'redirect_uri': redirect})

    def disconnect(self):
        self.store.delete()
        self.token = {}
