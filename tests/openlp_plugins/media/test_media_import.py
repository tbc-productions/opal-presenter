"""Regression tests for media library paths used by service items."""

from unittest.mock import MagicMock, patch

import pytest

from openlp.core.common import sha256_file_hash
from openlp.core.common.registry import Registry
from openlp.core.lib import ServiceItemContext
from openlp.core.lib.serviceitem import ServiceItem
from openlp.plugins.media.lib.db import Item
from openlp.plugins.media.lib.mediaitem import MediaMediaItem


@pytest.fixture
def media_item(settings):
    Registry().register('service_list', MagicMock())
    Registry().register('main_window', MagicMock())
    Registry().register('live_controller', MagicMock())
    with patch('openlp.plugins.media.lib.mediaitem.FolderLibraryItem._setup'), \
            patch('openlp.plugins.media.lib.mediaitem.MediaMediaItem.setup_item'):
        item = MediaMediaItem(None, MagicMock())
        item.manager = MagicMock()
    controller = MagicMock()
    controller.is_media_supported.return_value = (True, '')
    Registry().register('media_controller', controller)
    return item


def _generate_service_item(media_item, db_item, library_root):
    tree_item = MagicMock()
    tree_item.data.return_value = db_item
    plugin = MagicMock()
    plugin.name = 'media'
    service_item = ServiceItem(plugin)
    with patch('openlp.plugins.media.lib.mediaitem.AppLocation.get_section_data_path',
               return_value=library_root):
        result = media_item.generate_slide_data(service_item, item=tree_item,
                                                context=ServiceItemContext.Preview)
    return result, service_item


@pytest.mark.parametrize('legacy_hash_name', [False, True])
def test_managed_media_service_uses_real_filename(media_item, state_media, tmp_path, legacy_hash_name):
    """Named and older hash-named imports both resolve the existing media file."""
    library_root = tmp_path / 'media'
    library_dir = library_root / 'library'
    library_dir.mkdir(parents=True)
    media_name = 'My clip.mp4'
    file_hash = 'b870bbf63029ff91e040adde90f40dd47ac19998dd5f1952a73878686faaff0c'
    stored_name = f'{file_hash}.mp4' if legacy_hash_name else media_name
    media_path = library_dir / stored_name
    media_path.write_bytes(b'media')
    db_item = Item(name=media_name, file_path=str(media_path))
    db_item.file_hash = file_hash

    result, service_item = _generate_service_item(media_item, db_item, library_root)

    assert result is True
    assert service_item.title == 'My clip'
    assert service_item.get_frame_path() == media_path
    assert service_item.is_valid is True
    assert service_item.slides[0]['title'] == media_name


def test_missing_managed_hash_path_recovers_named_file(media_item, state_media, tmp_path):
    """A renamed managed file repairs a stale database path using its hash."""
    library_root = tmp_path / 'media'
    library_dir = library_root / 'library'
    library_dir.mkdir(parents=True)
    media_path = library_dir / 'My clip.mp4'
    media_path.write_bytes(b'media')
    file_hash = sha256_file_hash(media_path)
    db_item = Item(name=media_path.name, file_path=str(library_dir / f'{file_hash}.mp4'))
    db_item.file_hash = file_hash

    result, service_item = _generate_service_item(media_item, db_item, library_root)

    assert result is True
    assert db_item.file_path == str(media_path)
    media_item.manager.save_object.assert_called_once_with(db_item)
    media_item.media_controller.is_media_supported.assert_called_once_with(str(media_path))
    assert service_item.get_frame_path() == media_path
    assert service_item.is_valid is True
