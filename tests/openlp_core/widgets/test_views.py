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
Package to test the openlp.core.widgets.views package.
"""
import os
import pytest
from types import GeneratorType
from unittest.mock import MagicMock, call, patch

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import UiStrings
from openlp.core.common.registry import Registry
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.widgets.views import FileTreeWidgetItem, ListPreviewWidget, ListWidgetWithDnD, TreeWidgetWithDnD, \
    handle_mime_data_urls
from openlp.core.ui.icons import UiIcons
from tests.utils.osdinteraction import read_service_from_file


@pytest.fixture
def clapperboard(mock_settings):
    return UiIcons().clapperboard


@pytest.fixture
def preview_widget_env():
    """Local test setup"""
    parent_patcher = patch('openlp.core.widgets.views.ListPreviewWidget.parent')
    mocked_parent = parent_patcher.start()
    mocked_parent.width.return_value = 100

    # Mock self.viewport().width()
    viewport_patcher = patch('openlp.core.widgets.views.ListPreviewWidget.viewport')
    mocked_viewport = viewport_patcher.start()
    mocked_viewport_obj = MagicMock()
    mocked_viewport_obj.return_value.width.return_value = 200
    mocked_viewport.return_value = mocked_viewport_obj
    yield mocked_parent, mocked_viewport_obj
    parent_patcher.stop()
    viewport_patcher.stop()


@pytest.fixture()
def mocked_parent(qapp):
    """A prepared parent object"""
    parent_obj = QtWidgets.QWidget(None)
    with patch.object(parent_obj, 'width') as mocked_width:
        mocked_width.return_value = 100
        yield parent_obj
    parent_obj.deleteLater()


@pytest.fixture()
def preview_widget(settings):
    main_window = QtWidgets.QMainWindow()
    Registry().register('main_window', main_window)
    p_widget = ListPreviewWidget(main_window, 2)
    return p_widget


def test_files():
    """
    Test handle_mime_data_urls when the data points to some files.
    """
    # GIVEN: Some mocked objects that return True when is_file is called, and some mocked mime data
    mocked_path_instance_1 = MagicMock(**{'is_file.return_value': True})
    mocked_path_instance_2 = MagicMock(**{'is_file.return_value': True})
    with patch('openlp.core.widgets.views.Path',
               side_effect=[mocked_path_instance_1, mocked_path_instance_2]) as mocked_path:
        mocked_q_url_1 = MagicMock(**{'toLocalFile.return_value': os.path.join('file', 'test', 'path', '1.ext')})
        mocked_q_url_2 = MagicMock(**{'toLocalFile.return_value': os.path.join('file', 'test', 'path', '2.ext')})
        mocked_q_mime_data = MagicMock(**{'urls.return_value': [mocked_q_url_1, mocked_q_url_2]})

        # WHEN: Calling handle_mime_data_urls with the mocked mime data
        result = handle_mime_data_urls(mocked_q_mime_data)

        # THEN: Both mocked Path objects should be returned in the list
        mocked_path.assert_has_calls([call(os.path.join('file', 'test', 'path', '1.ext')),
                                      call(os.path.join('file', 'test', 'path', '2.ext'))])
        assert result == [mocked_path_instance_1, mocked_path_instance_2]


def test_directory():
    """
    Test handle_mime_data_urls when the data points to some directories.
    """
    # GIVEN: Some mocked objects that return True when is_dir is called, and some mocked mime data
    mocked_path_instance_1 = MagicMock()
    mocked_path_instance_2 = MagicMock()
    mocked_path_instance_3 = MagicMock()
    mocked_path_instance_4 = MagicMock(**{'is_file.return_value': False, 'is_directory.return_value': True,
                                          'iterdir.return_value': [mocked_path_instance_1, mocked_path_instance_2]})
    mocked_path_instance_5 = MagicMock(**{'is_file.return_value': False, 'is_directory.return_value': True,
                                          'iterdir.return_value': [mocked_path_instance_3]})
    with patch('openlp.core.widgets.views.Path',
               side_effect=[mocked_path_instance_4, mocked_path_instance_5]) as mocked_path:
        mocked_q_url_1 = MagicMock(**{'toLocalFile.return_value': os.path.join('file', 'test', 'path')})
        mocked_q_url_2 = MagicMock(**{'toLocalFile.return_value': os.path.join('file', 'test', 'path')})
        mocked_q_mime_data = MagicMock(**{'urls.return_value': [mocked_q_url_1, mocked_q_url_2]})

        # WHEN: Calling handle_mime_data_urls with the mocked mime data
        result = handle_mime_data_urls(mocked_q_mime_data)

        # THEN: The three mocked Path file objects should be returned in the list
        mocked_path.assert_has_calls([call(os.path.join('file', 'test', 'path')),
                                      call(os.path.join('file', 'test', 'path'))])
        assert result == [mocked_path_instance_1, mocked_path_instance_2, mocked_path_instance_3]


def test_new_list_preview_widget(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock):
    """
    Test that creating an instance of ListPreviewWidget works
    """
    # GIVEN: A ListPreviewWidget class with a mocked parent
    # WHEN: An object is created
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)

    # THEN: The object is not None, and the _setup() method was called.
    assert list_preview_widget is not None, 'The ListPreviewWidget object should not be None'
    assert list_preview_widget.screen_ratio == 1, 'Should not be called'


def test_preview_widget_arrow_keys_signal_slide_change(preview_widget):
    """Keyboard row changes must notify the slide controller."""
    preview_widget.setRowCount(3)
    for row in range(3):
        preview_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(str(row)))
    preview_widget.selectRow(1)
    changed = MagicMock()
    preview_widget.keyboard_slide_changed.connect(changed)

    preview_widget.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Down,
                                                QtCore.Qt.KeyboardModifier.NoModifier))
    assert preview_widget.currentRow() == 2
    assert changed.call_count == 1

    preview_widget.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Up,
                                                QtCore.Qt.KeyboardModifier.NoModifier))
    assert preview_widget.currentRow() == 1
    assert changed.call_count == 2


def test_replace_service_item_thumbs(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock):
    """
    Test that thubmails for different slides are loaded properly in replace_service_item.
    """
    # GIVEN: A setting to adjust "Max height for non-text slides in slide controller",
    #        different ServiceItem(s), an ImageManager, and a ListPreviewWidget.

    # Mock Settings().value('advanced/slide max height')
    mock_settings.value.return_value = 0
    # Mock self.viewport().width()
    mocked_viewport_obj = MagicMock()
    mocked_viewport_obj.return_value.width.return_value = 200
    # Mock Image service item
    mocked_img_service_item = MagicMock()
    mocked_img_service_item.is_text.return_value = False
    mocked_img_service_item.is_media.return_value = False
    mocked_img_service_item.is_command.return_value = False
    mocked_img_service_item.is_capable.return_value = False
    mocked_img_service_item.get_frames.return_value = [{'title': None, 'path': 'TEST1', 'image': 'FAIL'},
                                                       {'title': None, 'path': 'TEST2', 'image': 'FAIL'}]
    # Mock Command service item
    mocked_cmd_service_item = MagicMock()
    mocked_cmd_service_item.is_text.return_value = False
    mocked_cmd_service_item.is_media.return_value = False
    mocked_cmd_service_item.is_command.return_value = True
    mocked_cmd_service_item.is_capable.return_value = True
    mocked_cmd_service_item.get_frames.return_value = [{'title': None, 'path': 'FAIL', 'image': 'TEST3'},
                                                       {'title': None, 'path': 'FAIL', 'image': 'TEST4'}]

    # init ListPreviewWidget and load service item
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)

    # WHEN: replace_service_item is called
    with patch.object(list_preview_widget, 'viewport', mocked_viewport_obj), \
            patch.object(list_preview_widget, 'resizeRowsToContents'), \
            patch.object(list_preview_widget, 'setRowHeight'):
        list_preview_widget.replace_service_item(mocked_img_service_item, 200, 0)
        list_preview_widget.replace_service_item(mocked_cmd_service_item, 200, 0)


def test_replace_service_item_text_uses_single_line_verse_header(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock):
    """
    Test that text slide row headers use single-line verse tags (e.g. V1) for readability.
    """
    # GIVEN: A text service item with one verse
    service_item = MagicMock()
    service_item.is_text.return_value = True
    service_item.display_slides = [{'verse': 'V1', 'text': 'Verse text'}]
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)

    # WHEN: The service item is loaded into the preview widget
    list_preview_widget.replace_service_item(service_item, 200, 0)

    # THEN: The row header should be the one-line verse tag
    assert list_preview_widget.verticalHeaderItem(0).text() == 'V1'
    assert list_preview_widget.verticalHeaderItem(0).textAlignment() == int(QtCore.Qt.AlignmentFlag.AlignCenter)


def test_replace_service_item_numbers_custom_display_pages(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock):
    """Split custom slides get page letters; single-page slides retain their source number."""
    service_item = MagicMock()
    service_item.name = 'custom'
    service_item.is_text.return_value = True
    service_item.display_slides = [
        {'verse': '1', 'text': 'First page'},
        {'verse': '1', 'text': 'Overflow page'},
        {'verse': '1', 'text': 'Another overflow page'},
        {'verse': '2', 'text': 'Single-page slide'},
        {'verse': '3', 'text': 'First page'},
        {'verse': '3', 'text': 'Overflow page'},
    ]
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)

    list_preview_widget.replace_service_item(service_item, 200, 0)

    assert [list_preview_widget.verticalHeaderItem(index).text() for index in range(6)] == [
        '1a', '1b', '1c', '2', '3a', '3b']


def test_replace_recalculate_layout_text(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock):
    """
    Test if "Max height for non-text slides..." enabled, txt slides unchanged in replace_service_item & __recalc...
    """
    # GIVEN: A setting to adjust "Max height for non-text slides in slide controller",
    #        a text ServiceItem and a ListPreviewWidget.

    # Mock Settings().value('advanced/slide max height')
    mock_settings.value.return_value = 100
    # Mock self.viewport().width()
    mocked_viewport_obj = MagicMock()
    mocked_viewport_obj.return_value.width.return_value = 200
    # Mock text service item
    service_item = MagicMock()
    service_item.is_text.return_value = True
    service_item.get_frames.return_value = [{'title': None, 'text': None, 'verseTag': None},
                                            {'title': None, 'text': None, 'verseTag': None}]
    # init ListPreviewWidget and load service item
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)
    list_preview_widget.replace_service_item(service_item, 200, 0)
    # Change viewport width before forcing a resize
    mocked_viewport_obj.return_value.width.return_value = 400

    # WHEN: __recalculate_layout() is called (via resizeEvent)
    with patch.object(list_preview_widget, 'resizeRowsToContents') as mocked_resize_rows_to_contents, \
            patch.object(list_preview_widget, 'setRowHeight') as mocked_set_row_height, \
            patch.object(list_preview_widget, 'viewport', mocked_viewport_obj):
        list_preview_widget.resizeEvent(None)

    # THEN: setRowHeight() should not be called, while resizeRowsToContents() should be called twice
    #       (once each in __recalculate_layout and replace_service_item)
    assert mocked_resize_rows_to_contents.call_count == 1, 'Should be called'
    assert mocked_set_row_height.call_count == 0, 'Should not be called'


    # calls = [call(0, 200), call(1, 200), call(0, 400), call(1, 400), call(0, 400), call(1, 400)]
    # mocked_setRowHeight.assert_has_calls(calls)


    # calls = [call(0, 100), call(1, 100), call(0, 100), call(1, 100)]
    # mocked_setRowHeight.assert_has_calls(calls)


def test_replace_recalculate_layout_img_auto(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock, clapperboard):
    """
    Test if "Max height for non-text slides..." auto, img slides resized in replace_service_item & __recalc...
    """
    # GIVEN: A setting to adjust "Max height for non-text slides in slide controller",
    #        an image ServiceItem and a ListPreviewWidget.

    # Mock Settings().value('advanced/slide max height')
    mock_settings.value.return_value = -4
    # Mock self.viewport().width()
    mocked_viewport_obj = MagicMock()
    mocked_viewport_obj.return_value.width.return_value = 200
    mocked_viewport_obj.return_value.height.return_value = 600
    # Mock image service item
    service_item = MagicMock()
    service_item.is_text.return_value = False
    service_item.is_capable.return_value = False
    service_item.get_frames.return_value = [{'title': None, 'path': None, 'image': clapperboard},
                                            {'title': None, 'path': None, 'image': clapperboard}]
    # init ListPreviewWidget and load service item
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)
    list_preview_widget.replace_service_item(service_item, 200, 0)
    # Change viewport width before forcing a resize
    mocked_viewport_obj.return_value.width.return_value = 400

    # WHEN: __recalculate_layout() is called (via screen_size_changed)
    with patch.object(list_preview_widget, 'resizeRowsToContents') as mocked_resize_rows_to_contents, \
            patch.object(list_preview_widget, 'setRowHeight') as mocked_set_row_height, \
            patch.object(list_preview_widget, 'viewport', mocked_viewport_obj):
        list_preview_widget.screen_size_changed(1)
        mocked_viewport_obj.height.return_value = 200
        list_preview_widget.screen_size_changed(1)

    # THEN: resizeRowsToContents() should not be called, while setRowHeight() should be called
    #       twice for each slide.
    assert mocked_resize_rows_to_contents.call_count == 0, 'Should not be called'
    assert mocked_set_row_height.call_count == 0, 'Should not be called'
    # calls = [call(0, 100), call(1, 100), call(0, 150), call(1, 150), call(0, 100), call(1, 100)]
    # mocked_setRowHeight.assert_has_calls(calls)


def test_row_resized_text(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock):
    """
    Test if "Max height for non-text slides..." enabled, text-based slides not affected in row_resized.
    """
    # GIVEN: A setting to adjust "Max height for non-text slides in slide controller",
    #        a text ServiceItem and a ListPreviewWidget.

    # Mock Settings().value('advanced/slide max height')
    mock_settings.value.return_value = 100
    # Mock self.viewport().width()
    mocked_viewport_obj = MagicMock()
    mocked_viewport_obj.return_value.width.return_value = 200
    # Mock text service item
    service_item = MagicMock()
    service_item.is_text.return_value = True
    service_item.get_frames.return_value = [{'title': None, 'text': None, 'verseTag': None},
                                            {'title': None, 'text': None, 'verseTag': None}]
    # Mock self.cellWidget().children().setMaximumWidth()
    mocked_cell_widget_child = MagicMock()
    mocked_cell_widget = MagicMock()
    mocked_cell_widget.return_value.children.return_value = [None, mocked_cell_widget_child]
    # init ListPreviewWidget and load service item
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)
    list_preview_widget.replace_service_item(service_item, 200, 0)

    # WHEN: row_resized() is called
    with patch.object(list_preview_widget, 'resizeRowsToContents'), \
            patch.object(list_preview_widget, 'setRowHeight'), \
            patch.object(list_preview_widget, 'cellWidget', mocked_cell_widget), \
            patch.object(list_preview_widget, 'viewport', mocked_viewport_obj):
        list_preview_widget.row_resized(0, 100, 150)

    # THEN: self.cellWidget(row, 0).children()[1].setMaximumWidth() should not be called
    assert mocked_cell_widget_child.setMaximumWidth.call_count == 0, 'Should not be called'


def test_row_resized_img_max(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock, clapperboard):
    """
    Test if "Max height for non-text slides..." enabled, image-based slides are scaled in row_resized.
    """
    # GIVEN: A setting to adjust "Max height for non-text slides in slide controller",
    #        an image ServiceItem and a ListPreviewWidget.

    # Mock Settings().value('advanced/slide max height')
    mock_settings.value.return_value = 100
    # Mock self.viewport().width()
    mock_settings.width.return_value = 200
    # Mock image service item
    service_item = MagicMock()
    service_item.is_text.return_value = False
    service_item.is_capable.return_value = False
    service_item.get_frames.return_value = [{'title': None, 'path': None, 'image': clapperboard},
                                            {'title': None, 'path': None, 'image': clapperboard}]
    # Mock self.cellWidget().children().setMaximumWidth()
    mocked_cell_widget_child = MagicMock()
    mocked_cell_widget = MagicMock()
    mocked_cell_widget.return_value.children.return_value = [None, mocked_cell_widget_child]
    # init ListPreviewWidget and load service item
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)
    list_preview_widget.replace_service_item(service_item, 200, 0)

    # WHEN: row_resized() is called
    with patch.object(list_preview_widget, 'resizeRowsToContents'), \
            patch.object(list_preview_widget, 'setRowHeight'), \
            patch.object(list_preview_widget, 'cellWidget', mocked_cell_widget), \
            patch.object(list_preview_widget, 'viewport'):
        list_preview_widget.row_resized(0, 100, 150)

    # THEN: self.cellWidget(row, 0).children()[1].setMaximumWidth() should be called
    mocked_cell_widget_child.setMaximumWidth.assert_called_once_with(150)


def test_row_resized_setting_changed(mocked_parent: QtWidgets.QWidget, mock_settings: MagicMock, clapperboard):
    """
    Test if "Max height for non-text slides..." enabled while item live, program doesn't crash on row_resized.
    """
    # GIVEN: A setting to adjust "Max height for non-text slides in slide controller",
    #        an image ServiceItem and a ListPreviewWidget.

    # Mock Settings().value('advanced/slide max height')
    mock_settings.value.return_value = 0
    # Mock self.viewport().width()
    mocked_viewport_obj = MagicMock()
    mocked_viewport_obj.return_value.width.return_value = 200
    # Mock image service item
    service_item = MagicMock()
    service_item.is_text.return_value = False
    service_item.is_capable.return_value = False
    service_item.get_frames.return_value = [{'title': None, 'path': None, 'image': clapperboard},
                                            {'title': None, 'path': None, 'image': clapperboard}]
    # Mock self.cellWidget().children()
    mocked_cell_widget = MagicMock()
    mocked_cell_widget.return_value.children.return_value = None
    # init ListPreviewWidget and load service item
    list_preview_widget = ListPreviewWidget(mocked_parent, 1)
    list_preview_widget.replace_service_item(service_item, 200, 0)
    mock_settings.value.return_value = 100

    # WHEN: row_resized() is called
    with patch.object(list_preview_widget, 'resizeRowsToContents'), \
            patch.object(list_preview_widget, 'setRowHeight'), \
            patch.object(list_preview_widget, 'cellWidget', mocked_cell_widget), \
            patch.object(list_preview_widget, 'viewport', mocked_viewport_obj):
        list_preview_widget.row_resized(0, 100, 150)

    # THEN: self.cellWidget(row, 0).children()[1].setMaximumWidth() should fail
    # assert Exception


def test_treewidgetwithdnd_clear():
    """
    Test the clear method when called without any arguments.
    """
    # GIVEN: An instance of ListWidgetWithDnD
    widget = ListWidgetWithDnD()

    # WHEN: Calling clear with out any arguments
    widget.clear()

    # THEN: The results text should be the standard 'no results' text.
    assert widget.no_results_text == UiStrings().NoResults


def test_slide_change_keeps_selected_slide_visible(mocked_parent, mock_settings):
    """Navigation keeps the actual selected row visible rather than an adjacent slide."""
    widget = ListPreviewWidget(mocked_parent, 1)
    widget.setRowCount(3)
    item = QtWidgets.QTableWidgetItem('Current slide')
    widget.setItem(1, 0, item)
    with patch.object(widget, 'scrollToItem') as scroll:
        widget.change_slide(1)
    assert widget.currentRow() == 1
    scroll.assert_called_once_with(item, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)


def test_slide_change_empty_list(mocked_parent, mock_settings):
    """Navigation before slides are loaded must not scroll to a missing item."""
    widget = ListPreviewWidget(mocked_parent, 1)
    with patch.object(widget, 'scrollToItem') as scroll:
        widget.change_slide(0)
    scroll.assert_not_called()


def test_thumbnail_height_adapts_to_viewport(mocked_parent, mock_settings, clapperboard):
    """Thumbnails fit four rows where possible, with a readable minimum height."""
    item = MagicMock()
    item.is_text.return_value = False
    item.is_capable.return_value = False
    item.get_frames.return_value = [{'title': None, 'path': None, 'image': clapperboard}]
    item.slides = [MagicMock()]
    viewport = MagicMock()
    viewport.width.return_value = 400
    viewport.height.return_value = 800
    widget = ListPreviewWidget(mocked_parent, 1)
    with patch.object(widget, 'viewport', return_value=viewport):
        widget.replace_service_item(item, 400, 0)
        assert widget.rowHeight(0) == 200
        viewport.height.return_value = 200
        widget.resizeEvent(None)
        assert widget.rowHeight(0) == 100


def test_clear_search_while_typing():
    """
    Test the clear method when called with the search_while_typing argument set to True
    """
    # GIVEN: An instance of ListWidgetWithDnD
    widget = ListWidgetWithDnD()

    # WHEN: Calling clear with search_while_typing set to True
    widget.clear(search_while_typing=True)

    # THEN: The results text should be the 'short results' text.
    assert widget.no_results_text == UiStrings().ShortResults


def test_all_items_no_list_items():
    """
    Test allItems when there are no items in the list widget
    """
    # GIVEN: An instance of ListWidgetWithDnD
    widget = ListWidgetWithDnD()
    with patch.object(widget, 'count', return_value=0), \
            patch.object(widget, 'item', side_effect=lambda x: [][x]):

        # WHEN: Calling allItems
        result = widget.allItems()

        # THEN: An instance of a Generator object should be returned. The generator should not yeild any results
        assert isinstance(result, GeneratorType)
        assert list(result) == []


def test_all_items_list_items():
    """
    Test allItems when the list widget contains some items.
    """
    # GIVEN: An instance of ListWidgetWithDnD
    widget = ListWidgetWithDnD()
    with patch.object(widget, 'count', return_value=2), \
            patch.object(widget, 'item', side_effect=lambda x: [5, 3][x]):

        # WHEN: Calling allItems
        result = widget.allItems()

        # THEN: An instance of a Generator object should be returned. The generator should not yeild any results
        assert isinstance(result, GeneratorType)
        assert list(result) == [5, 3]


def test_paint_event():
    """
    Test the paintEvent method when the list is not empty
    """
    # GIVEN: An instance of ListWidgetWithDnD with a mocked out count methode which returns 1
    #       (i.e the list has an item)
    widget = ListWidgetWithDnD()
    with patch('openlp.core.widgets.views.QtWidgets.QListWidget.paintEvent') as mocked_paint_event, \
            patch.object(widget, 'count', return_value=1), \
            patch.object(widget, 'viewport') as mocked_viewport:
        mocked_event = MagicMock()

        # WHEN: Calling paintEvent
        widget.paintEvent(mocked_event)

        # THEN: The overridden paintEvnet should have been called
        mocked_paint_event.assert_called_once_with(mocked_event)
        assert mocked_viewport.called is False


def test_paint_event_no_items():
    """
    Test the paintEvent method when the list is empty
    """
    # GIVEN: An instance of ListWidgetWithDnD with a mocked out count methode which returns 0
    #       (i.e the list is empty)
    widget = ListWidgetWithDnD()
    mocked_painter_instance = MagicMock()
    mocked_qrect = MagicMock()
    with patch('openlp.core.widgets.views.QtWidgets.QListWidget.paintEvent') as mocked_paint_event, \
            patch.object(widget, 'count', return_value=0), \
            patch.object(widget, 'viewport'), \
            patch('openlp.core.widgets.views.QtGui.QPainter',
                  return_value=mocked_painter_instance) as mocked_qpainter, \
            patch('openlp.core.widgets.views.QtCore.QRect', return_value=mocked_qrect):
        mocked_event = MagicMock()

        # WHEN: Calling paintEvent
        widget.paintEvent(mocked_event)

        # THEN: The overridden paintEvnet should have been called, and some text should be drawn.
        mocked_paint_event.assert_called_once_with(mocked_event)
        mocked_qpainter.assert_called_once_with(widget.viewport())
        mocked_painter_instance.drawText.assert_called_once_with(mocked_qrect.adjusted.return_value, 4100, 'No Search Results')


def test_treewidgetwithdnd_constructor():
    """
    Test the constructor
    """
    # GIVEN: A TreeWidgetWithDnD
    # WHEN: An instance is created
    widget = TreeWidgetWithDnD(name='Test')

    # THEN: It should be initialised correctly
    assert widget.mime_data_text == 'Test'
    assert widget.allow_internal_dnd is False
    assert widget.indentation() == 16
    assert widget.isAnimated() is False


def test_treewidgetwithdnd_setup_columns(qapp):
    """setup_columns shows the header, sets correct labels, and enables sorting"""
    # GIVEN: A TreeWidgetWithDnD
    widget = TreeWidgetWithDnD(name='Test')

    # WHEN: setup_columns is called with four labels
    widget.setup_columns(['Name', 'Type', 'Size', 'Date'])

    # THEN: The header should be visible with the right labels, and sorting enabled
    assert widget.columnCount() == 4
    assert widget.headerItem().text(0) == 'Name'
    assert widget.headerItem().text(1) == 'Type'
    assert widget.headerItem().text(2) == 'Size'
    assert widget.headerItem().text(3) == 'Date'
    assert widget.isSortingEnabled() is True
    assert widget.header().isHidden() is False


def test_treewidgetwithdnd_keeps_first_column_wide_enough(qapp):
    """The first column keeps at least 70 percent of the visible width."""
    widget = TreeWidgetWithDnD(name='Test')

    widget.resize(500, 300)
    widget.show()
    widget.setup_columns(['Name', 'Date'])
    qapp.process_events()

    try:
        assert widget.columnWidth(0) >= int(widget.viewport().width() * widget.first_column_min_ratio)
    finally:
        widget.hide()
        widget.deleteLater()


def test_file_tree_widget_item_fallback_string_sort(qapp):
    """FileTreeWidgetItem falls back to alphabetical sort when no numeric key is set"""
    # GIVEN: A tree with two items and no sort data set
    tree = QtWidgets.QTreeWidget()
    tree.setColumnCount(1)
    item_a = FileTreeWidgetItem(['Apple'])
    item_b = FileTreeWidgetItem(['Banana'])
    tree.addTopLevelItem(item_b)
    tree.addTopLevelItem(item_a)

    # WHEN: The tree is sorted ascending
    tree.setSortingEnabled(True)
    tree.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)

    # THEN: Items sort alphabetically
    assert tree.topLevelItem(0) is item_a
    assert tree.topLevelItem(1) is item_b


def test_initial_slide_count(preview_widget):
    """
    Test the initial slide count .
    """
    # GIVEN: A new ListPreviewWidget instance.
    # WHEN: No SlideItem has been added yet.
    # THEN: The count of items should be zero.
    assert preview_widget.slide_count() == 0, 'The slide list should be empty.'


def test_initial_slide_number(preview_widget):
    """
    Test the initial current slide number.
    """
    # GIVEN: A new ListPreviewWidget instance.
    # WHEN: No SlideItem has been added yet.
    # THEN: The number of the current item should be -1.
    assert preview_widget.current_slide_number() == -1, 'The slide number should be -1.'


def test_replace_service_item(preview_widget, state_media):
    """
    Test item counts and current number with a service item.
    """
    # GIVEN: A ServiceItem with two frames.
    service_item = ServiceItem(None)
    service = read_service_from_file('serviceitem_image_3.osj')
    with patch('os.path.exists') and patch('openlp.core.lib.serviceitem.sha256_file_hash', new=lambda x: "MockedHash"):
        service_item.set_from_service(service[0])
    # WHEN: Added to the preview widget.
    preview_widget.replace_service_item(service_item, 1, 1)
    # THEN: The slide count and number should fit.
    assert preview_widget.slide_count() == 2, 'The slide count should be 2.'
    assert preview_widget.current_slide_number() == 1, 'The current slide number should  be 1.'


def test_change_slide(preview_widget, state_media):
    """
    Test the change_slide method.
    """
    # GIVEN: A ServiceItem with two frames content.
    service_item = ServiceItem(None)
    service = read_service_from_file('serviceitem_image_3.osj')
    with patch('os.path.exists') and patch('openlp.core.lib.serviceitem.sha256_file_hash', new=lambda x: "MockedHash"):
        service_item.set_from_service(service[0])
    # WHEN: Added to the preview widget and switched to the second frame.
    preview_widget.replace_service_item(service_item, 1, 0)
    preview_widget.change_slide(1)
    # THEN: The current_slide_number should reflect the change.
    assert preview_widget.current_slide_number() == 1, 'The current slide number should  be 1.'


def test_text_slide_rows_have_small_vertical_padding(settings, qapp):
    """Padding surrounds wrapped slide text and remains stable after resizing."""
    from fluentqt import Spacing

    parent = QtWidgets.QWidget()
    view = ListPreviewWidget(parent, 1)
    view.service_item = MagicMock()
    view.service_item.is_text.return_value = True
    view.setRowCount(1)
    view.setItem(0, 0, QtWidgets.QTableWidgetItem('First line\nSecond line\nThird line'))
    view.resize(400, 240)
    view.show()
    qapp.process_events()
    view.resizeRowsToContents()
    padded_height = view.rowHeight(0)
    native = view.itemDelegate()._native_delegate
    delegate = view.itemDelegate()
    view.setItemDelegate(native)
    view.resizeRowsToContents()
    assert abs(padded_height - view.rowHeight(0) - 2 * Spacing.Small) <= 1
    view.setItemDelegate(delegate)
    view.resizeRowsToContents()
    assert view.rowHeight(0) == padded_height
    view.close()


def test_bible_slide_rows_wrap_and_reflow(settings, qapp):
    from openlp.core.widgets.views import SLIDE_TEXT_HTML_ROLE

    parent = QtWidgets.QWidget()
    view = ListPreviewWidget(parent, 1)
    service_item = MagicMock()
    service_item.name = 'bibles'
    service_item.is_text.return_value = True
    words = 'In the beginning God created the heavens and the earth. ' * 2
    service_item.display_slides = [{'verse': '1:1', 'text': '1 ' + words,
                                   'text_html': '<sup>1 </sup>' + words}]
    parent.resize(650, 400)
    parent.show()
    view.resize(600, 300)
    view.replace_service_item(service_item, 600, 0)
    view.show()
    qapp.process_events()
    from PySide6 import QtTest
    QtTest.QTest.qWait(50)
    wide_height = view.rowHeight(0)
    view.resize(350, 300)
    qapp.process_events()

    QtTest.QTest.qWait(50)
    assert view.rowHeight(0) > wide_height
    assert view.item(0, 0).data(SLIDE_TEXT_HTML_ROLE) == '<sup>1 </sup>' + words
    option = QtWidgets.QStyleOptionViewItem()
    option.font = view.font()
    document = view.itemDelegate()._document(option, view.model().index(0, 0))
    cursor = QtGui.QTextCursor(document)
    cursor.setPosition(1)
    assert cursor.charFormat().verticalAlignment() == QtGui.QTextCharFormat.VerticalAlignment.AlignSuperScript
    view.close()


@pytest.mark.parametrize('rich_text', [False, True])
def test_slide_row_shows_only_first_four_lines(settings, qapp, rich_text):
    from openlp.core.widgets.views import SLIDE_TEXT_HTML_ROLE

    parent = QtWidgets.QWidget()
    view = ListPreviewWidget(parent, 1)
    view.service_item = MagicMock()
    view.service_item.is_text.return_value = True
    view.setRowCount(1)
    item = QtWidgets.QTableWidgetItem('One\nTwo\nThree\nFour\nFive\nSix')
    if rich_text:
        item.setData(SLIDE_TEXT_HTML_ROLE, '<sup>1</sup> One<br>Two<br>Three<br>Four<br>Five<br>Six')
    view.setItem(0, 0, item)
    view.setColumnWidth(0, 400)
    option = QtWidgets.QStyleOptionViewItem()
    option.font = view.font()
    delegate = view.itemDelegate()
    document = delegate._document(option, view.model().index(0, 0))

    assert document.toPlainText().splitlines() == (['1 One', 'Two', 'Three', 'Four…'] if rich_text else
                                                ['One', 'Two', 'Three', 'Four…'])
    # Wrapped lines count towards the same limit, even within a single paragraph.
    item.setText('A long slide with enough words to wrap onto many lines. ' * 20)
    item.setData(SLIDE_TEXT_HTML_ROLE, None)
    document = delegate._document(option, view.model().index(0, 0))
    document.size()
    assert document.begin().layout().lineCount() == 4
    assert len(document.toPlainText()) < len(item.text())
    assert document.toPlainText().endswith('…')
    # A slide that fits exactly four lines does not need an ellipsis.
    item.setText('One\nTwo\nThree\nFour')
    document = delegate._document(option, view.model().index(0, 0))
    assert document.toPlainText() == item.text()
    view.close()


def test_slide_list_vertical_scrollbar_stays_visible(settings, qapp):
    from PySide6 import QtTest

    parent = QtWidgets.QWidget()
    parent.resize(450, 300)
    view = ListPreviewWidget(parent, 1)
    view.service_item = MagicMock()
    view.service_item.is_text.return_value = True
    view.setRowCount(30)
    for row in range(30):
        view.setItem(row, 0, QtWidgets.QTableWidgetItem('Slide text'))
    view.resize(400, 240)
    parent.show()
    view.show()
    QtTest.QTest.qWait(50)
    scrollbar = view.verticalFluentScrollBar()

    assert view.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    assert scrollbar.isVisible()
    assert scrollbar.maximum() > 0
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    assert scrollbar.value() == scrollbar.maximum()
    # The Fluent fade animation must not make the thumb disappear after interaction.
    for animation in scrollbar.findChildren(QtCore.QPropertyAnimation):
        if animation.targetObject() == scrollbar and bytes(animation.propertyName()) == b'opacity':
            animation.stop()
            animation.setStartValue(1.0)
            animation.setEndValue(0.0)
            animation.setDuration(20)
            animation.start()
    QtTest.QTest.qWait(50)
    assert scrollbar.opacity() == 1.0
    assert scrollbar.isVisible()
    parent.close()
