"""Versioned Opal documents and archive validation shared by importers."""
import json
import stat
from pathlib import PurePosixPath


FORMAT = 'opal-presenter'
VERSION = 1
SERVICE_SUFFIXES = ('.opal-service', '.opal-service-lite', '.osz', '.oszl')
DESIGN_NAMESPACE = 'urn:net.tbcproductions.OpalPresenter:slide-design:1'
LEGACY_DESIGN_NAMESPACE = 'https://openlp.org/ns/slide-design/1'
SYNC_NAMESPACE = 'urn:net.tbcproductions.OpalPresenter:library-sync:1'
LEGACY_SYNC_NAMESPACE = 'https://openlp.org/ns/library-sync/1'


def document(file_type, data):
    return {'format': FORMAT, 'version': VERSION, 'type': file_type, 'data': data}


def read_document(value, file_type):
    if (not isinstance(value, dict) or value.get('format') != FORMAT
            or type(value.get('version')) is not int or value['version'] != VERSION
            or value.get('type') != file_type or 'data' not in value):
        raise ValueError('This is not a supported Opal Presenter {type} document.'.format(type=file_type))
    return value['data']


def validate_archive(archive):
    """Reject ambiguous members, traversal and links before importing."""
    members = archive.infolist()
    names = set()
    for member in members:
        name = member.filename
        path = PurePosixPath(name)
        if (not name or '\\' in name or path.is_absolute() or '..' in path.parts
                or any(':' in part for part in path.parts) or name in names
                or path.as_posix() != name.rstrip('/')
                or stat.S_ISLNK(member.external_attr >> 16)):
            raise ValueError('The archive contains an unsafe or duplicate file path.')
        names.add(name)


def write_manifest(archive, file_type, payload):
    archive.writestr('manifest.json', json.dumps(
        {'format': FORMAT, 'version': VERSION, 'type': file_type, 'payload': payload}))


def read_manifest(archive, file_type, required=False):
    """Validate native packages; allow explicitly selected legacy inputs without a manifest."""
    validate_archive(archive)
    if 'manifest.json' not in archive.namelist():
        if required:
            raise ValueError('The Opal Presenter package has no manifest.')
        return None
    if archive.getinfo('manifest.json').file_size > 65536:
        raise ValueError('The package manifest is too large.')
    value = json.loads(archive.read('manifest.json'))
    expected = (file_type,) if isinstance(file_type, str) else file_type
    if (not isinstance(value, dict) or value.get('format') != FORMAT
            or type(value.get('version')) is not int or value['version'] != VERSION
            or value.get('type') not in expected or not isinstance(value.get('payload'), str)):
        raise ValueError('This is not a supported Opal Presenter package for this importer.')
    payload = value['payload']
    if payload not in archive.namelist() or archive.getinfo(payload).is_dir():
        raise ValueError('The package payload is missing.')
    return value


def service_payload(archive, required=False, file_type=None):
    manifest = read_manifest(archive, file_type or ('service', 'service-lite'), required)
    if manifest:
        return manifest['payload']
    return next((name for name in archive.namelist()
                 if name == 'service_data.osj' or name.endswith('osj')), None)


def design_element(root):
    for namespace in (DESIGN_NAMESPACE, LEGACY_DESIGN_NAMESPACE):
        element = root.find('{' + namespace + '}design')
        if element is not None:
            return element
    return None


def validate_service(items):
    from opal.core.common.enum import ServiceItemType
    if not isinstance(items, list):
        raise ValueError('The service payload must contain a list of items.')
    version = next((item['openlp_core'].get('openlp-servicefile-version', 2) for item in items
                    if isinstance(item, dict) and isinstance(item.get('openlp_core'), dict)), 2)
    if type(version) is not int or version not in (2, 3):
        raise ValueError('Unsupported service payload version.')
    lite = any(item.get('openlp_core', {}).get('lite-service', False) for item in items if isinstance(item, dict)
               and isinstance(item.get('openlp_core', {}), dict))
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Invalid service item.')
        if 'openlp_core' in item:
            if not isinstance(item['openlp_core'], dict):
                raise ValueError('Invalid service metadata.')
            continue
        value = item.get('serviceitem')
        if not isinstance(value, dict) or not isinstance(value.get('header'), dict):
            raise ValueError('Invalid service item header.')
        header = value['header']
        required = {'title', 'name', 'type', 'theme', 'footer', 'audit', 'notes', 'from_plugin', 'capabilities'}
        if not required.issubset(header) or not isinstance(value.get('data'), list):
            raise ValueError('Incomplete service item.')
        kind = ServiceItemType.parse(header['type'])
        if kind is None or not isinstance(header['capabilities'], list):
            raise ValueError('Invalid service item type or capabilities.')
        keys = {'raw_slide', 'verseTag'} if kind == ServiceItemType.Text else {'title', 'image', 'path'}
        if kind == ServiceItemType.Text and header.get('is_slide_set'):
            keys.add('title')
        if kind == ServiceItemType.Image and version >= 3:
            keys = {'title', 'image', 'file_hash'} | ({'path'} if lite else set())
        for slide in value['data']:
            if kind == ServiceItemType.Image and version == 2 and not lite:
                if not isinstance(slide, str):
                    raise ValueError('Invalid legacy image slide.')
            elif not isinstance(slide, dict) or not keys.issubset(slide):
                raise ValueError('Incomplete service slide.')
