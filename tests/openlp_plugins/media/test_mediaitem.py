# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
Test the media plugin
"""
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from PySide6 import QtCore, QtWidgets

from openlp.core.common.registry import Registry
from openlp.core.lib import ServiceItemContext
from openlp.core.ui.media import MediaType, get_supported_media_suffix
from openlp.core.ui.icons import UiIcons
from openlp.plugins.media.lib.db import Item
from openlp.plugins.media.lib.mediaitem import MediaMediaItem


@pytest.fixture
def media_item(settings):
    """Local test setup"""
    mocked_main_window = MagicMock()
    Registry().register('service_list', MagicMock())
    Registry().register('main_window', mocked_main_window)
    Registry().register('live_controller', MagicMock())
    mocked_plugin = MagicMock()
    with patch('openlp.plugins.media.lib.mediaitem.FolderLibraryItem._setup'), \
            patch('openlp.plugins.media.lib.mediaitem.MediaMediaItem.setup_item'):
        m_item = MediaMediaItem(None, mocked_plugin)
        m_item.manager = MagicMock()
    return m_item


def test_search_found(media_item):
    """
    Media Remote Search Successful find
    """
    # GIVEN: The Mediaitem set up a list of media
    media_item.manager.get_all_objects.return_value = [MagicMock(file_path='test.mp4')]

    # WHEN: Retrieving the test file
    result = media_item.search('test.mp4', False)

    # THEN: a file should be found
    assert result == [['test.mp4', 'test.mp4']], 'The result file contain the file name'


def test_search_not_found(media_item):
    """
    Media Remote Search not find
    """
    # GIVEN: The Mediaitem set up a list of media
    media_item.manager.get_all_objects.return_value = []

    # WHEN: Retrieving the test file
    result = media_item.search('test.mpx', False)

    # THEN: a file should be found
    assert result == [], 'The result file should be empty'


@patch('openlp.plugins.media.lib.mediaitem.or_')
@patch('openlp.plugins.media.lib.mediaitem.Item')
def test_get_list_audio(MockItem, mocked_or, media_item):
    """
    Test the ``MediaMediaItem.get_list()`` method to return all audio items
    """
    # GIVEN: A mocked Item class and some mocked items to return
    media_item.manager.get_all_objects.return_value = [MagicMock(file_path='test1.mp3'),
                                                       MagicMock(file_path='test2.ogg')]
    MockItem.file_path.endswith.side_effect = lambda ext: ext
    mocked_or.side_effect = lambda *ext: list(ext)

    # WHEN: get_list() is called
    media_list = media_item.get_list(MediaType.Audio)

    # THEN: All the clauses should have been created, and the right extensions used
    a_suffixes, _ = get_supported_media_suffix()
    expected_extensions = [ext[1:] for ext in a_suffixes]
    expected_calls = [call(ext) for ext in expected_extensions]
    MockItem.file_path.endswith.assert_has_calls(expected_calls)
    mocked_or.assert_called_once_with(*expected_extensions)
    media_item.manager.get_all_objects.assert_called_once_with(MockItem, expected_extensions)
    assert media_list == [Path('test1.mp3'), Path('test2.ogg')]


@patch('openlp.plugins.media.lib.mediaitem.or_')
@patch('openlp.plugins.media.lib.mediaitem.Item')
def test_get_list_video(MockItem, mocked_or, media_item):
    """
    Test the ``MediaMediaItem.get_list()`` method to return all audio items
    """
    # GIVEN: A mocked Item class and some mocked items to return
    media_item.manager.get_all_objects.return_value = [MagicMock(file_path='test1.mp4'),
                                                       MagicMock(file_path='test2.ogv')]
    MockItem.file_path.endswith.side_effect = lambda ext: ext
    mocked_or.side_effect = lambda *ext: list(ext)

    # WHEN: get_list() is called
    media_list = media_item.get_list(MediaType.Video)

    # THEN: All the clauses should have been created, and the right extensions used
    _, v_suffixes = get_supported_media_suffix()
    expected_extensions = [ext[1:] for ext in v_suffixes]
    expected_calls = [call(ext) for ext in expected_extensions]
    MockItem.file_path.endswith.assert_has_calls(expected_calls)
    mocked_or.assert_called_once_with(*expected_extensions)
    media_item.manager.get_all_objects.assert_called_once_with(MockItem, expected_extensions)
    assert media_list == [Path('test1.mp4'), Path('test2.ogv')]


def test_add_device_stream(media_item):
    """Test that the ``MediaMediaItem.add_device_stream()`` method calls validate_and_load()"""
    # GIVEN: A MediaMediaItem object, with a mocked out `validate_and_load` method
    with patch.object(media_item, 'validate_and_load') as mocked_validate_and_load:
        # WHEN: add_device_stream is called
        media_item.add_device_stream('devicestream:/dev/v4l')

        # THEN: The mocked method should have been called
        mocked_validate_and_load.assert_called_once_with(['devicestream:/dev/v4l'])


def test_add_network_stream(media_item):
    """Test that the ``MediaMediaItem.add_network_stream()`` method calls validate_and_load()"""
    # GIVEN: A MediaMediaItem object, with a mocked out `validate_and_load` method
    with patch.object(media_item, 'validate_and_load') as mocked_validate_and_load:
        # WHEN: add_network_stream is called
        media_item.add_network_stream('networkstream:rmtp://localhost')

        # THEN: The mocked method should have been called
        mocked_validate_and_load.assert_called_once_with(['networkstream:rmtp://localhost'])


def test_load_item_metadata_columns(media_item):
    """Test that load_item populates the Date column and tooltip with type and size for a normal media file"""
    # GIVEN: A media file item and a controlled stat result
    file_path = Path('/media/video.mp4')
    item = MagicMock(file_path=file_path)
    mocked_stat = MagicMock()
    mocked_stat.st_size = 150 * 1024 * 1024  # 150.0 MB
    mocked_stat.st_mtime = 1700000000.0

    with patch.object(Path, 'exists', return_value=True), \
            patch.object(Path, 'stat', return_value=mocked_stat), \
            patch('openlp.plugins.media.lib.mediaitem.QtCore.QFileInfo') as mocked_qfileinfo, \
            patch('openlp.plugins.media.lib.mediaitem.get_supported_media_suffix', return_value=([], [])):
        mocked_qfileinfo.return_value.isFile.return_value = True

        # WHEN: load_item() is called
        result = media_item.load_item(item)

    # THEN: Date column should be populated, tooltip enriched with type and size
    assert result.text(1) == datetime.fromtimestamp(1700000000.0).strftime('%Y-%m-%d %H:%M')
    assert result.toolTip(0) == '/media/video.mp4\nMP4 · 150.0 MB'


@patch('openlp.plugins.media.lib.mediaitem.critical_error_message_box')
def test_generate_slide_data_blocks_unsupported_media(mocked_error_dialog: MagicMock, media_item, tmp_path):
    """
    Test that generate_slide_data returns False when the platform cannot decode the file.
    """
    # GIVEN: a real file path and media controller reporting unsupported
    media_path = tmp_path / 'unsupported.mp4'
    media_path.write_bytes(b'test')
    mocked_db_item = Item(name='unsupported.mp4', file_path=str(media_path))
    mocked_tree_item = MagicMock()
    mocked_tree_item.data.return_value = mocked_db_item
    mocked_service_item = MagicMock()
    mocked_media_controller = MagicMock()
    mocked_media_controller.is_media_supported.return_value = (False, 'decode unsupported')
    Registry().register('media_controller', mocked_media_controller)

    # WHEN: generate_slide_data is called
    result = media_item.generate_slide_data(mocked_service_item, item=mocked_tree_item)

    # THEN: it should reject the media and show a user-facing error
    assert result is False
    mocked_error_dialog.assert_called_once()


def test_generate_slide_data_queues_media_length_probe_for_service(media_item, tmp_path):
    """
    Test that media duration probing is queued (not run inline) for service items.
    """
    # GIVEN: a supported media file and a media item with a probe queue method
    media_path = tmp_path / 'supported.mp4'
    media_path.write_bytes(b'test')
    mocked_db_item = Item(name='supported.mp4', file_path=str(media_path))
    mocked_tree_item = MagicMock()
    mocked_tree_item.data.return_value = mocked_db_item
    mocked_service_item = MagicMock()
    mocked_media_controller = MagicMock()
    mocked_media_controller.is_media_supported.return_value = (True, '')
    Registry().register('media_controller', mocked_media_controller)

    with patch.object(media_item, '_queue_media_length_probe') as mocked_queue:
        # WHEN: generate_slide_data() is called for Service context
        result = media_item.generate_slide_data(
            mocked_service_item,
            item=mocked_tree_item,
            context=ServiceItemContext.Service
        )

    # THEN: media length probing should be queued asynchronously
    assert result is True
    mocked_queue.assert_called_once_with(mocked_service_item, str(media_path))


def test_apply_media_length_probe_result_retries_when_worker_returns_zero(media_item):
    """When worker probe returns 0, media length should be retried once on the main thread."""
    # GIVEN: A matching service item and a media controller that can provide a fallback length
    mocked_service_item = MagicMock(unique_identifier='item-1')
    mocked_service_manager = MagicMock(service_items=[{'service_item': mocked_service_item}])
    mocked_media_controller = MagicMock()
    mocked_media_controller.media_length.return_value = 3210
    Registry().remove('service_manager')
    Registry().remove('media_controller')
    Registry().register('service_manager', mocked_service_manager)
    Registry().register('media_controller', mocked_media_controller)

    # WHEN: Applying a zero worker result
    media_item._apply_media_length_probe_result('item-1', 0, 'C:/video.mp4')

    # THEN: Fallback media_length should be used and applied to the service item
    mocked_media_controller.media_length.assert_called_once_with('C:/video.mp4')
    mocked_service_item.set_media_length.assert_called_once_with(3210)
    mocked_service_manager.repaint_service_list.assert_called_once_with(0, -1)


@patch('openlp.plugins.media.lib.mediaitem.FolderLibraryItem.validate_and_load')
@patch('openlp.plugins.media.lib.mediaitem.critical_error_message_box')
def test_validate_and_load_filters_unsupported_files(mocked_error_dialog: MagicMock,
                                                     mocked_super_validate: MagicMock,
                                                     media_item,
                                                     tmp_path):
    """
    Test that validate_and_load only forwards supported files to the base implementation.
    """
    # GIVEN: one supported file and one unsupported file
    supported = tmp_path / 'supported.mp4'
    unsupported = tmp_path / 'unsupported.mp4'
    supported.write_bytes(b'supported')
    unsupported.write_bytes(b'unsupported')
    mocked_media_controller = MagicMock()

    def _is_supported(path):
        return (False, 'decode unsupported') if str(path).endswith('unsupported.mp4') else (True, '')

    mocked_media_controller.is_media_supported.side_effect = _is_supported
    Registry().register('media_controller', mocked_media_controller)

    # WHEN: validate_and_load is called with mixed files
    media_item.validate_and_load([supported, unsupported])

    # THEN: only supported files should be forwarded and an error should be shown
    mocked_super_validate.assert_called_once_with([supported], None)
    mocked_error_dialog.assert_called_once()


def test_generate_thumbnail_path_prefers_file_hash(media_item, tmp_path):
    """Media thumbnails should use file_hash when available for stable cache names."""
    media_item.service_path = tmp_path
    item = Item(name='clip.mp4', file_path=str(tmp_path / 'clip.mp4'))
    item.file_hash = 'abc123'
    assert media_item.generate_thumbnail_path(item) == tmp_path / 'abc123.png'


@patch('openlp.plugins.media.lib.mediaitem.delete_file')
def test_delete_item_removes_generated_thumbnail(mocked_delete_file: MagicMock, media_item, tmp_path):
    """Delete should remove the generated PNG thumbnail path."""
    media_item.service_path = tmp_path
    item = Item(name='clip.mp4', file_path=str(tmp_path / 'clip.mp4'))
    item.file_hash = 'abc123'

    media_item.delete_item(item)

    mocked_delete_file.assert_called_once_with(tmp_path / 'abc123.png')


@patch('openlp.plugins.media.lib.mediaitem.media_info')
@patch('openlp.plugins.media.lib.mediaitem.build_icon')
@patch('openlp.plugins.media.lib.mediaitem.validate_thumb')
@patch('openlp.plugins.media.lib.mediaitem.get_supported_media_suffix')
def test_load_item_video_uses_cached_thumbnail(mocked_suffixes: MagicMock,
                                               mocked_validate_thumb: MagicMock,
                                               mocked_build_icon: MagicMock,
                                               mocked_media_info: MagicMock,
                                               media_item,
                                               tmp_path):
    """When video thumbnail is valid in cache, no regeneration should be attempted."""
    media_item.service_path = tmp_path
    video_file = tmp_path / 'clip.mp4'
    video_file.write_bytes(b'test')
    item = Item(name='clip.mp4', file_path=str(video_file))
    item.file_hash = 'abc123'
    mocked_suffixes.return_value = (['*.mp3'], ['*.mp4'])
    mocked_validate_thumb.return_value = True
    mocked_build_icon.return_value = UiIcons().video

    tree_item = media_item.load_item(item)

    assert tree_item is not None
    mocked_build_icon.assert_called_once_with(tmp_path / 'abc123.png')
    mocked_media_info.assert_not_called()


@patch('openlp.plugins.media.lib.mediaitem.media_info')
@patch('openlp.plugins.media.lib.mediaitem.build_icon')
@patch('openlp.plugins.media.lib.mediaitem.validate_thumb')
@patch('openlp.plugins.media.lib.mediaitem.get_supported_media_suffix')
def test_load_item_video_generates_thumbnail_when_missing(mocked_suffixes: MagicMock,
                                                          mocked_validate_thumb: MagicMock,
                                                          mocked_build_icon: MagicMock,
                                                          mocked_media_info: MagicMock,
                                                          media_item,
                                                          tmp_path):
    """When video thumbnail cache is invalid, generation should be attempted and icon built from new thumb."""
    media_item.service_path = tmp_path
    video_file = tmp_path / 'clip.mp4'
    video_file.write_bytes(b'test')
    item = Item(name='clip.mp4', file_path=str(video_file))
    item.file_hash = 'abc123'
    mocked_suffixes.return_value = (['*.mp3'], ['*.mp4'])
    mocked_validate_thumb.return_value = False
    mocked_build_icon.return_value = UiIcons().video
    mocked_info_instance = MagicMock()
    mocked_info_instance.create_media_thumbnail.return_value = True
    mocked_media_info.return_value = mocked_info_instance

    tree_item = media_item.load_item(item)

    assert tree_item is not None
    mocked_info_instance.create_media_thumbnail.assert_called_once_with(str(video_file), str(tmp_path / 'abc123.png'))
    mocked_build_icon.assert_called_once_with(tmp_path / 'abc123.png')


@patch('openlp.plugins.media.lib.mediaitem.media_info')
@patch('openlp.plugins.media.lib.mediaitem.validate_thumb')
@patch('openlp.plugins.media.lib.mediaitem.get_supported_media_suffix')
def test_load_item_video_defers_thumbnail_generation_on_initial_load(mocked_suffixes: MagicMock,
                                                                     mocked_validate_thumb: MagicMock,
                                                                     mocked_media_info: MagicMock,
                                                                     media_item,
                                                                     tmp_path):
    """Initial media list load should not probe/decode video when thumbnail cache is missing."""
    media_item.service_path = tmp_path
    video_file = tmp_path / 'clip.mp4'
    video_file.write_bytes(b'test')
    item = Item(name='clip.mp4', file_path=str(video_file))
    item.file_hash = 'abc123'
    mocked_suffixes.return_value = (['*.mp3'], ['*.mp4'])
    mocked_validate_thumb.return_value = False

    tree_item = media_item.load_item(item, is_initial_load=True)

    assert tree_item is not None
    assert tree_item.data(0, media_item.pending_thumbnail_role) is True
    mocked_media_info.assert_not_called()


@patch('openlp.plugins.media.lib.mediaitem.media_info')
@patch('openlp.plugins.media.lib.mediaitem.build_icon')
@patch('openlp.plugins.media.lib.mediaitem.validate_thumb')
def test_on_focus_generates_deferred_thumbnails(mocked_validate_thumb: MagicMock,
                                                mocked_build_icon: MagicMock,
                                                mocked_media_info: MagicMock,
                                                media_item,
                                                tmp_path):
    """Deferred thumbnails should be generated once the media tab gains focus."""
    media_item.service_path = tmp_path
    video_file = tmp_path / 'clip.mp4'
    video_file.write_bytes(b'test')
    item = Item(name='clip.mp4', file_path=str(video_file))
    item.file_hash = 'abc123'
    media_item.list_view = QtWidgets.QTreeWidget()

    tree_item = QtWidgets.QTreeWidgetItem(['clip.mp4'])
    tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
    tree_item.setData(0, media_item.pending_thumbnail_role, True)
    media_item.list_view.addTopLevelItem(tree_item)

    mocked_validate_thumb.return_value = False
    mocked_build_icon.return_value = UiIcons().video
    mocked_info_instance = MagicMock()
    mocked_info_instance.create_media_thumbnail.return_value = True
    mocked_media_info.return_value = mocked_info_instance

    media_item.on_focus()

    mocked_info_instance.create_media_thumbnail.assert_called_once_with(str(video_file), str(tmp_path / 'abc123.png'))
    mocked_build_icon.assert_called_once_with(tmp_path / 'abc123.png')
    assert tree_item.data(0, media_item.pending_thumbnail_role) is False


def test_fixed_canvas_icon_dimensions(media_item):
    """Fallback icon should render on fixed 88x50 canvas."""
    icon = media_item._fixed_canvas_icon(UiIcons().video)
    pixmap = icon.pixmap(88, 50)
    assert pixmap.width() == 88
    assert pixmap.height() == 50
