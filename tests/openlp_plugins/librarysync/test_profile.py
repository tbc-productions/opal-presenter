"""Portable profiles validate folder settings and never carry credentials."""
import base64
import json
import zlib
from unittest.mock import MagicMock

import pytest

from opal.plugins.librarysync.lib.profile import (
    deserialize_profile, read_profile, serialize_profile, validate_profile, write_profile)
from opal.plugins.librarysync.lib.provider import SyncError


@pytest.fixture
def profile(tmp_path):
    return {'version': 1, 'provider': 'local-cloud', 'name': 'Church Library', 'path': str(tmp_path)}


def test_profile_allowlist_excludes_credentials(profile):
    profile['refresh_token'] = 'private-user-token'
    profile['installed'] = {'client_id': 'private-client', 'client_secret': 'private-secret'}
    result = validate_profile(profile)
    assert set(result) == {'version', 'provider', 'name', 'path', 'folders'}
    assert 'private-user-token' not in str(result) and 'private-secret' not in str(result)


def test_shared_connection_excludes_credentials(profile, tmp_path):
    profile['refresh_token'] = 'private-user-token'
    profile['installed'] = {'access_token': 'private-access-token'}
    path = tmp_path / 'church.opal-connection'
    write_profile(path, profile)
    exported = path.read_text()
    assert 'private-user-token' not in exported and 'private-access-token' not in exported
    assert read_profile(path) == validate_profile(profile)
    value = json.loads(exported)
    unpacked = zlib.decompress(base64.b64decode(value['data']['data'])).decode()
    assert 'private-user-token' not in unpacked and 'private-access-token' not in unpacked


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
def test_library_name_must_be_a_short_nonempty_label(profile, name):
    profile['name'] = name
    with pytest.raises(SyncError, match='library name'):
        validate_profile(profile)


def test_failed_export_keeps_previous_connection_file(profile, tmp_path, monkeypatch):
    path = tmp_path / 'organisation.opal-connection'
    path.write_text('previous connection')
    monkeypatch.setattr('opal.plugins.librarysync.lib.profile.Path.replace',
                        MagicMock(side_effect=OSError('disk error')))
    with pytest.raises(OSError):
        write_profile(path, profile)
    assert path.read_text() == 'previous connection'
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('provider', ['google-drive', 'unsupported', None, [], {}])
def test_unsupported_profile_provider_is_rejected(profile, provider):
    profile['provider'] = provider
    with pytest.raises(SyncError, match='not supported'):
        validate_profile(profile)
