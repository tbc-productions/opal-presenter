"""Portable profiles and sign-in must never expose personal tokens."""
import base64
import hashlib
import json
import zlib
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from openlp.plugins.librarysync.lib.auth import GoogleAuth, TokenStore
from openlp.plugins.librarysync.lib.profile import (
    deserialize_profile, folder_reference, read_profile, serialize_profile, validate_profile, write_profile)
from openlp.plugins.librarysync.lib.provider import SyncError


@pytest.fixture
def profile():
    return {'version': 1, 'provider': 'google-drive',
            'installed': {'client_id': 'church.apps.googleusercontent.com', 'client_secret': 'desktop-client'},
            'folders': [{'id': 'church-folder', 'name': 'Church Library'}]}


def test_profile_allowlist_excludes_tokens_and_custom_endpoints(profile):
    profile['refresh_token'] = 'private-user-token'
    profile['installed']['token_uri'] = 'https://attacker.example/tokens'
    profile['installed']['access_token'] = 'private-access-token'
    result = validate_profile(profile)
    assert 'refresh_token' not in result
    assert set(result['installed']) == {'client_id', 'client_secret'}
    assert 'private' not in str(result)


def test_shared_connection_conceals_client_details_and_excludes_tokens(profile, tmp_path):
    profile['refresh_token'] = 'private-user-token'
    profile['installed']['access_token'] = 'private-access-token'
    path = tmp_path / 'church.librarysync.json'
    write_profile(path, profile)
    exported = path.read_text()
    assert 'church.apps.googleusercontent.com' not in exported
    assert 'desktop-client' not in exported
    assert read_profile(path) == validate_profile(profile)
    value = json.loads(exported)
    unpacked = zlib.decompress(base64.b64decode(value['data'])).decode()
    assert 'private' not in unpacked


def test_legacy_plain_connection_is_still_importable(profile):
    assert deserialize_profile(json.dumps(profile)) == validate_profile(profile)


def test_qsettings_decoded_profiles_remain_importable(profile):
    assert deserialize_profile(profile) == validate_profile(profile)
    assert deserialize_profile(json.loads(serialize_profile(profile))) == validate_profile(profile)


@pytest.mark.parametrize('data', [
    'not base64', base64.b64encode(b'broken').decode(),
    base64.b64encode(zlib.compress(b'x' * (64 * 1024 + 1))).decode()])
def test_shared_connection_rejects_corruption_and_unbounded_expansion(data):
    envelope = json.dumps({'format': 'openlp-library-sync', 'version': 1, 'encoding': 'zlib+base64', 'data': data})
    with pytest.raises(SyncError):
        deserialize_profile(envelope)


def test_serialized_settings_use_the_same_portable_format(profile):
    assert deserialize_profile(serialize_profile(profile)) == validate_profile(profile)


@pytest.mark.parametrize('name', ['', '  ', None, 'x' * 201])
def test_connection_name_must_be_a_short_nonempty_label(profile, name):
    profile['name'] = name
    with pytest.raises(SyncError, match='connection name'):
        validate_profile(profile)


def test_failed_export_keeps_previous_connection_file(profile, tmp_path, monkeypatch):
    path = tmp_path / 'organisation.librarysync.json'
    path.write_text('previous connection')
    monkeypatch.setattr('openlp.plugins.librarysync.lib.profile.Path.replace',
                        MagicMock(side_effect=OSError('disk error')))
    with pytest.raises(OSError):
        write_profile(path, profile)
    assert path.read_text() == 'previous connection'
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('value', [
    'https://attacker.example/drive/folders/f', "x' or trashed = false", '../folder',
    'https://drive.google.com/file/d/f/view'])
def test_folder_reference_rejects_untrusted_paths(value):
    with pytest.raises(SyncError):
        folder_reference(value)


def test_folder_reference_preserves_resource_key():
    assert folder_reference('https://drive.google.com/drive/u/0/folders/church?resourcekey=key') == ('church', 'key')


def test_token_store_rejects_plaintext_backend(monkeypatch):
    backend = type('PlaintextKeyring', (), {'priority': 10, '__module__': 'keyrings.alt.file'})()
    monkeypatch.setattr('openlp.plugins.librarysync.lib.auth.keyring.get_keyring', lambda: backend)
    with pytest.raises(SyncError, match='credential store'):
        TokenStore('church')


def test_refresh_preserves_refresh_token_and_saves_only_to_store(profile, monkeypatch):
    store = MagicMock()
    store.load.return_value = {'refresh_token': 'user-refresh-token', 'expires_at': 0}
    auth = GoogleAuth(profile['installed'], store)
    reply = MagicMock(status_code=200)
    reply.json.return_value = {'access_token': 'new-token', 'expires_in': 3600}
    post = MagicMock(return_value=reply)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.auth.requests.post', post)
    assert auth.access_token() == 'new-token'
    assert store.save.call_args.args[0]['refresh_token'] == 'user-refresh-token'
    assert post.call_args.kwargs['data']['grant_type'] == 'refresh_token'


def test_browser_sign_in_checks_state_and_uses_pkce(profile, monkeypatch):
    opened = {}
    received = []
    store = MagicMock()
    store.load.return_value = {}
    auth = GoogleAuth(profile['installed'], store)
    auth.exchange = MagicMock()

    class Server:
        server_port = 49123

        def __init__(self, address, callback):
            assert address == ('127.0.0.1', 0)
            self.callback = callback

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def handle_request(self):
            callback = self.callback.__new__(self.callback)
            state = 'wrong-state' if not received else opened['state'][0]
            callback.path = '/oauth2callback?' + urlencode({'state': state, 'code': 'auth-code'})
            callback.send_response = received.append
            callback.send_header = MagicMock()
            callback.end_headers = MagicMock()
            callback.wfile = MagicMock()
            callback.do_GET()

    monkeypatch.setattr('openlp.plugins.librarysync.lib.auth.HTTPServer', Server)
    auth.sign_in(Event(), lambda url: opened.update(parse_qs(urlparse(url).query)))
    fields = auth.exchange.call_args.args[0]
    expected = base64.urlsafe_b64encode(hashlib.sha256(fields['code_verifier'].encode()).digest()).rstrip(b'=').decode()
    assert opened['code_challenge'] == [expected]
    assert opened['code_challenge_method'] == ['S256']
    assert fields['redirect_uri'] == 'http://127.0.0.1:49123/oauth2callback'
    assert fields['code'] == 'auth-code'
    assert received == [400, 200]


def test_expired_sign_in_error_does_not_include_tokens(profile, monkeypatch):
    store = MagicMock()
    store.load.return_value = {}
    auth = GoogleAuth(profile['installed'], store)
    reply = SimpleNamespace(status_code=400, text='private-token')
    monkeypatch.setattr('openlp.plugins.librarysync.lib.auth.requests.post', lambda *args, **kwargs: reply)
    with pytest.raises(SyncError) as error:
        auth.exchange({'grant_type': 'refresh_token', 'refresh_token': 'private-token'})
    assert 'private-token' not in str(error.value)


@pytest.mark.parametrize('provider', ['unsupported', None, [], {}])
def test_unsupported_profile_provider_is_rejected(profile, provider):
    profile['provider'] = provider
    with pytest.raises(SyncError, match='not supported'):
        validate_profile(profile)
