"""Portable connection configuration; user tokens never belong in a profile."""
import base64
import json
import zlib
from pathlib import Path
from tempfile import NamedTemporaryFile

from opal.plugins.librarysync.lib.provider import SyncError
from opal.core.lib.nativefile import document, read_document


MAX_PROFILE = 64 * 1024


def validate_local_profile(value):
    """Local profiles carry a folder location, never credentials or arbitrary item paths."""
    name, path = value.get('name'), value.get('path')
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise SyncError('Invalid library name.')
    if not isinstance(path, str) or not path or len(path) > 4096 or '\x00' in path or not Path(path).is_absolute():
        raise SyncError('Choose an absolute path to a local storage folder.')
    return {'version': 1, 'provider': 'local-cloud', 'name': name.strip(), 'path': str(Path(path)),
            'folders': [{'id': '.', 'name': name.strip(), 'resource_key': ''}]}


PROFILE_VALIDATORS = {'local-cloud': validate_local_profile}


def validate_profile(value):
    """Dispatch to a provider's allowlist before storing or sharing configuration."""
    if not isinstance(value, dict) or value.get('version') != 1:
        raise SyncError('Choose a Library Sync connection file (version 1).')
    provider = value.get('provider')
    if not isinstance(provider, str) or provider not in PROFILE_VALIDATORS:
        raise SyncError('This cloud provider is not supported.')
    return PROFILE_VALIDATORS[provider](value)


def serialize_profile(profile):
    """Encode the validated connection in the portable format."""
    profile = validate_profile(profile)
    data = json.dumps(profile, separators=(',', ':')).encode('utf-8')
    return json.dumps(document('connection', {
        'format': 'openlp-library-sync', 'version': 1, 'encoding': 'zlib+base64',
        'name': profile['name'], 'data': base64.b64encode(zlib.compress(data)).decode('ascii')
    }), indent=2, ensure_ascii=False) + '\n'


def deserialize_profile(text):
    if isinstance(text, dict):
        text = json.dumps(text)
    if not isinstance(text, str):
        raise SyncError('The connection file is invalid or damaged.')
    if len(text.encode('utf-8')) > MAX_PROFILE:
        raise SyncError('The connection file is too large.')
    try:
        value = json.loads(text)
        if isinstance(value, dict) and value.get('format') == 'opal-presenter':
            value = read_document(value, 'connection')
        if isinstance(value, dict) and value.get('format') == 'openlp-library-sync':
            if value.get('version') != 1 or value.get('encoding') != 'zlib+base64':
                raise SyncError('Unsupported Library Sync connection format.')
            if not isinstance(value.get('data'), str):
                raise SyncError('The connection file has no valid payload.')
            packed = base64.b64decode(value['data'], validate=True)
            inflater = zlib.decompressobj()
            data = inflater.decompress(packed, MAX_PROFILE + 1)
            if len(data) > MAX_PROFILE or inflater.unconsumed_tail or inflater.unused_data or not inflater.eof:
                raise SyncError('The connection file is damaged or expands beyond the supported size.')
            value = json.loads(data.decode('utf-8'))
        return validate_profile(value)
    except (ValueError, UnicodeError, zlib.error) as error:
        raise SyncError('The connection file is invalid or damaged.') from error


def write_profile(path, profile):
    path = path.with_suffix('.opal-connection')
    text = serialize_profile(profile)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(text)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_profile(path):
    if path.stat().st_size > MAX_PROFILE:
        raise SyncError('The connection file is too large.')
    try:
        text = path.read_text(encoding='utf-8')
        if path.suffix.lower() == '.opal-connection':
            read_document(json.loads(text), 'connection')
        return deserialize_profile(text)
    except (ValueError, TypeError) as error:
        raise SyncError('The connection file is invalid or damaged.') from error
