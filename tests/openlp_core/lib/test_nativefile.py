"""Native document identity and untrusted archive boundaries."""
import io
import json
import zipfile

import pytest

from openlp.core.lib.nativefile import document, read_document, read_manifest, service_payload, write_manifest


def test_native_package_round_trip():
    with zipfile.ZipFile(io.BytesIO(), 'w') as archive:
        archive.writestr('service.json', '[]')
        write_manifest(archive, 'service', 'service.json')
        assert read_manifest(archive, 'service', required=True)['version'] == 1
        assert service_payload(archive, required=True) == 'service.json'
    assert read_document(document('styles', []), 'styles') == []


@pytest.mark.parametrize('change', [{'version': 2}, {'version': True}, {'type': 'theme'},
                                   {'payload': 'missing.json'}, {'format': 'another-app'}])
def test_reject_invalid_manifest(change):
    with zipfile.ZipFile(io.BytesIO(), 'w') as archive:
        archive.writestr('service.json', '[]')
        manifest = {'format': 'opal-presenter', 'version': 1, 'type': 'service', 'payload': 'service.json'}
        archive.writestr('manifest.json', json.dumps({**manifest, **change}))
        with pytest.raises(ValueError):
            read_manifest(archive, 'service', required=True)


@pytest.mark.parametrize('name', ['../outside', '/outside', 'C:/outside', '..\\outside'])
def test_reject_unsafe_legacy_archive(name):
    with zipfile.ZipFile(io.BytesIO(), 'w') as archive:
        archive.writestr(name, 'content')
        with pytest.raises(ValueError):
            read_manifest(archive, 'service')


def test_legacy_import_requires_explicit_fallback():
    with zipfile.ZipFile(io.BytesIO(), 'w') as archive:
        archive.writestr('service_data.osj', '[]')
        assert service_payload(archive) == 'service_data.osj'
        with pytest.raises(ValueError):
            service_payload(archive, required=True)


def test_atomic_package_failure_preserves_destination(tmp_path):
    from openlp.core.lib.itemexport import export_archive
    destination = tmp_path / 'existing.opal-song'
    destination.write_bytes(b'existing document')
    with pytest.raises(OSError):
        with export_archive(destination, 'song', 'song.xml') as archive:
            archive.writestr('song.xml', '<song/>')
            raise OSError('media write failed')
    assert destination.read_bytes() == b'existing document'
    assert list(tmp_path.iterdir()) == [destination]


def test_plain_openlyrics_omits_extensions_and_assets(tmp_path):
    from lxml import etree
    from openlp.core.lib.itemexport import write_xml_package
    xml = ('<song xmlns="http://openlyrics.info/namespace/2009/song" version="0.9">'
           '<properties><titles><title>Grace</title></titles></properties>'
           '<lyrics><verse name="v1"><lines><chord name="G"/>Amazing grace</lines></verse></lyrics>'
           '<opal:design xmlns:opal="urn:net.tbcproductions.OpalPresenter:slide-design:1">{}</opal:design>'
           '<old:theme xmlns:old="https://openlp.org/ns/library-sync/1">Theme</old:theme></song>')
    destination = tmp_path / 'Grace.xml'
    write_xml_package(destination, xml)
    contents = destination.read_bytes()
    assert b'urn:net.tbcproductions.OpalPresenter' not in contents
    assert b'https://openlp.org/ns/' not in contents
    assert b'assets/' not in contents
    root = etree.fromstring(contents)
    assert root.find('.//{*}chord').get('name') == 'G'
    assert root.find('.//{*}title').text == 'Grace'


@pytest.mark.parametrize('file_type,suffix,xml', [
    ('song', '.opal-song', '<song xmlns="http://openlyrics.info/namespace/2009/song"><properties/>'
                          '<lyrics><verse name="v1"><lines>Welcome</lines></verse></lyrics></song>'),
    ('slides', '.opal-slides', '<song><title>Welcome</title><lyrics><verse>Welcome</verse></lyrics></song>')])
def test_native_xml_round_trip_and_type_validation(tmp_path, file_type, suffix, xml):
    from openlp.core.lib.itemexport import read_xml_package, write_xml_package
    path = tmp_path / ('Welcome' + suffix)
    write_xml_package(path, xml)
    original = path.read_bytes()
    root, text = read_xml_package(path, file_type)
    assert 'Welcome' in text
    assert root.find('.//{*}verse') is not None
    assert path.read_bytes() == original
    with pytest.raises(ValueError):
        read_xml_package(path, 'slides' if file_type == 'song' else 'song')


@pytest.mark.parametrize('lite', [False, True])
def test_native_service_load_preserves_metadata(tmp_path, lite):
    from unittest.mock import MagicMock, patch
    from openlp.core.lib.itemexport import export_archive
    from openlp.core.lib.serviceitem import ServiceItem
    from openlp.core.ui.servicemanager import ServiceLoadWorker
    with patch('openlp.core.lib.serviceitem.UiIcons'):
        item = ServiceItem()
        item.title, item.name = 'Welcome', 'custom'
        item.add_from_text('Welcome', 'v1')
        item.slide_transition_settings = {'enabled': True, 'type': 2, 'speed': 1}
        item.slide_design = {'version': 1, 'elements': []}
        with patch.object(item, 'get_theme_data', return_value=None):
            data = item.get_service_repr(lite)
    items = [{'openlp_core': {'lite-service': lite, 'openlp-servicefile-version': 3}}, {'serviceitem': data}]
    kind = 'service-lite' if lite else 'service'
    path = tmp_path / ('Welcome.opal-' + kind)
    with export_archive(path, kind, 'service.json') as archive:
        archive.writestr('service.json', json.dumps(items))
    worker = ServiceLoadWorker(path, tmp_path / 'extracted')
    result, failed = MagicMock(), MagicMock()
    worker.loaded.connect(result); worker.failed.connect(failed)
    worker.start()
    failed.assert_not_called()
    assert result.call_args.args[0]['items'] == items
    assert path.exists()


def test_malformed_service_rejected_before_media_extraction(tmp_path):
    from unittest.mock import MagicMock
    from openlp.core.ui.servicemanager import ServiceLoadWorker
    path = tmp_path / 'Bad.opal-service'
    with zipfile.ZipFile(path, 'w') as archive:
        write_manifest(archive, 'service', 'service.json')
        archive.writestr('service.json', '[{"serviceitem": {"header": {}}}]')
        archive.writestr('media.mp4', b'not applied')
    extracted = tmp_path / 'extracted'
    worker = ServiceLoadWorker(path, extracted)
    failed = MagicMock();worker.failed.connect(failed)
    worker.start()
    failed.assert_called_once()
    assert not extracted.exists()


@pytest.mark.parametrize('change', [{'data': [{}]}, {'header': {'type': 'unknown'}},
                                   {'header': {'capabilities': None}}])
def test_incomplete_service_slide_is_rejected(change):
    from openlp.core.lib.nativefile import validate_service
    value = {'header': {'title': 'Welcome', 'name': 'custom', 'type': 1, 'theme': None, 'footer': [],
                        'audit': '', 'notes': '', 'from_plugin': False, 'capabilities': []},
             'data': [{'raw_slide': 'Welcome', 'verseTag': 'v1'}]}
    if 'header' in change:
        value['header'].update(change['header'])
    else:
        value.update(change)
    with pytest.raises(ValueError):
        validate_service([{'openlp_core': {'openlp-servicefile-version': 3}}, {'serviceitem': value}])
