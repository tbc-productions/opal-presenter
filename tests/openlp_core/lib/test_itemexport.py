"""Tests for individual library item exports."""
import json
import zipfile
from unittest.mock import MagicMock

from opal.core.lib.itemexport import suggested_item_export_path, write_item_service
from opal.core.lib.serviceitem import ServiceItem


def test_suggested_item_export_path_uses_item_title(tmp_path):
    manager = MagicMock()
    manager.suggested_presentation_file_path.return_value = tmp_path / 'Service.odp'

    path = suggested_item_export_path(manager, 'A Song: Title', '.odp')

    assert path == tmp_path / 'A Song_ Title.odp'


def test_write_item_service_preserves_custom_text(tmp_path, settings):
    item = ServiceItem(None)
    item.name = 'custom'
    item.title = 'Welcome'
    item.add_from_text('First slide')
    path = tmp_path / 'Welcome.opal-slides'

    write_item_service(path, item)

    with zipfile.ZipFile(path) as archive:
        service = json.loads(archive.read('service.json'))
    assert service[0]['openlp_core']['openlp-servicefile-version'] == 3
    assert service[1]['serviceitem']['header']['title'] == 'Welcome'
    assert service[1]['serviceitem']['data'][0]['raw_slide'] == 'First slide'
