"""Presentation service items must retain file paths independently of display names."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest
from PySide6 import QtCore, QtWidgets

from openlp.core.common import sha256_file_hash
from openlp.core.common.applocation import AppLocation
from openlp.core.common.json import OpenLPJSONDecoder, OpenLPJSONEncoder
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.ui.servicemanager import ServiceManager
from openlp.plugins.presentations.lib.db import Item
from openlp.plugins.presentations.lib.mediaitem import PresentationMediaItem
from tests.utils.constants import RESOURCE_PATH


@pytest.fixture(scope='module', autouse=True)
def presentation_app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.mark.parametrize('managed', [True, False])
@pytest.mark.parametrize('lite_save', [True, False])
def test_presentation_paths_survive_service_save_and_reload(tmp_path, monkeypatch, registry, state, managed, lite_save):
    registry.register('settings', MagicMock())
    data_path = tmp_path / 'data'
    library_path = data_path / 'presentations' / 'library'
    library_path.mkdir(parents=True)
    source = RESOURCE_PATH / 'presentations' / 'test.pptx'
    file_hash = sha256_file_hash(source)
    stored_filename = file_hash + '.pptx'
    file_path = library_path / (stored_filename if managed else 'Original filename.pptx')
    file_path.write_bytes(source.read_bytes())
    thumbnails = data_path / 'presentations' / 'thumbnails' / file_hash
    thumbnails.mkdir(parents=True)
    thumbnail_paths = [thumbnails / f'slide{index}.png' for index in (1, 2)]
    for thumbnail in thumbnail_paths:
        thumbnail.touch()
    monkeypatch.setattr(AppLocation, 'get_section_data_path', lambda section: data_path / section)
    monkeypatch.setattr(AppLocation, 'get_data_path', staticmethod(lambda: data_path))

    document = MagicMock()
    document.get_sha256_file_hash.return_value = file_hash
    document.get_thumbnail_path.side_effect = [*thumbnail_paths, None]
    document.get_titles_and_notes.return_value = (['First', 'Second'], ['Notes', ''])
    controller = MagicMock()
    controller.add_document.return_value = document
    media_item = SimpleNamespace(
        display_type_combo_box=MagicMock(currentText=lambda: 'Powerpoint', itemData=lambda index: 'Powerpoint'),
        controllers={'Powerpoint': controller},
        _ensure_first_thumbnail=PresentationMediaItem._ensure_first_thumbnail,
        _selected_controller_name=lambda: 'Powerpoint',
        should_render_as_images=lambda file_path, processor: False)
    library_item = QtWidgets.QTreeWidgetItem()
    library_item.setData(0, QtCore.Qt.ItemDataRole.UserRole,
                         Item(name='Sunday sermon.pptx', file_path=str(file_path), file_hash=file_hash))
    service_item = ServiceItem()
    service_item.name = 'presentations'

    assert PresentationMediaItem.generate_slide_data(media_item, service_item, item=library_item)
    assert service_item.is_valid
    assert service_item.title == 'Sunday sermon'
    assert [service_item.get_frame_path(row) for row in range(2)] == [file_path, file_path]
    controller.add_document.assert_called_once_with(file_path)

    manager = SimpleNamespace(service_items=[{'service_item': service_item}])
    write_list, missing = ServiceManager.get_write_file_list(manager)
    assert missing == []
    assert write_list.count((file_path, Path(stored_filename))) == 1
    representation = service_item.get_service_repr(lite_save)
    assert representation['header']['stored_filename'] == stored_filename
    serialised = json.dumps({'serviceitem': representation}, cls=OpenLPJSONEncoder)
    extract_path = None
    if not lite_save:
        archive_path = tmp_path / 'service.osz'
        with ZipFile(archive_path, 'w') as archive:
            for source_path, target_path in write_list:
                archive.write(source_path, str(target_path))
        extract_path = tmp_path / 'extracted'
        with ZipFile(archive_path) as archive:
            archive.extractall(extract_path)
    restored = ServiceItem()
    restored.set_from_service(json.loads(serialised, cls=OpenLPJSONDecoder), path=extract_path, version=3)
    assert restored.is_valid
    assert restored.title == 'Sunday sermon'
    expected_path = file_path if lite_save else extract_path / stored_filename
    assert [restored.get_frame_path(row) for row in range(2)] == [expected_path, expected_path]
    assert expected_path.is_file()
