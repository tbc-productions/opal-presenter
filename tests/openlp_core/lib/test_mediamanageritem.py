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
Package to test the opal.core.lib.mediamanageritem package.
"""
import pytest
from unittest.mock import MagicMock, patch

from opal.core.common.registry import Registry
from opal.core.lib.mediamanageritem import MediaManagerItem


@pytest.mark.parametrize('name', ['images', 'media', 'presentations'])
def test_empty_controls_panel_leaves_header_against_toolbar(qapp, settings, qtbot, name):
    from PySide6 import QtCore
    from opal.core.ui.icons import UiIcons

    plugin = MagicMock(name=name)
    plugin.name = name
    plugin.icon = UiIcons().picture
    plugin.get_string.return_value = {'title': name, 'tooltip': name}
    with patch('opal.core.lib.ui.ActionList.get_instance'):
        item = MediaManagerItem(None, plugin)
    qtbot.addWidget(item)
    item.resize(640, 500)
    item.show()
    qtbot.wait(20)
    assert item.panel_widget.isHidden()
    assert item.list_view.mapTo(item, QtCore.QPoint()).y() == item.toolbar.geometry().bottom() + 1


@pytest.fixture
def media_env(qapp):
    setup_patcher = patch('opal.core.lib.mediamanageritem.MediaManagerItem._setup')
    setup_patcher.start()
    yield
    setup_patcher.stop()


def test_search_controls_align_and_submit_with_mouse_and_enter(media_env, settings, qtbot):
    from PySide6 import QtCore
    from opal.core.widgets import fluent

    item = MediaManagerItem(None)
    qtbot.addWidget(item)
    item.settings_section = 'songs'
    item.panel_layout = fluent.QVBoxLayout(item)
    item.on_search_text_button_clicked = MagicMock()
    item.on_search_text_edit_changed = MagicMock()
    item.add_search_to_toolbar()
    assert not hasattr(item, 'search_text_label')
    item.search_text_edit.setPlaceholderText('Search Titles…')
    item.show()
    for width in (600, 300):
        item.resize(width, 100)
        fluent.QApplication.processEvents()
        assert item.search_text_edit.height() == item.search_text_button.height()
    qtbot.mouseClick(item.search_text_button, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(item.search_text_edit, QtCore.Qt.Key.Key_Return)
    assert item.on_search_text_button_clicked.call_count == 2


def test_custom_new_precedes_import_in_command_bar(qapp, settings, qtbot):
    from opal.core.widgets.toolbar import OpenLPToolbar
    from opal.plugins.custom.lib.mediaitem import CustomMediaItem

    plugin = MagicMock()
    plugin.name = 'custom'
    plugin.get_string.return_value = {'title': 'Custom Slides', 'tooltip': 'Custom Slides'}
    with patch.object(MediaManagerItem, '_setup'), patch.object(CustomMediaItem, 'setup_item'):
        item = CustomMediaItem(None, plugin)
    qtbot.addWidget(item)
    item.toolbar = OpenLPToolbar(item)
    item.required_icons()
    item.add_start_header_bar()
    item.add_common_header_bar()
    assert [action.objectName() for action in item.toolbar.actions()] == [
        'customNewAction', 'customImportAction', 'customEditAction', 'customDeleteAction']


@patch('opal.core.lib.mediamanageritem.MediaManagerItem.on_preview_click')
def test_on_double_clicked(mocked_on_preview_click, media_env, registry):
    """
    Test that when an item is double-clicked then the item is previewed
    """
    # GIVEN: A setting to enable "Double-click to go live" and a media manager item
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = False
    Registry().register('settings', mocked_settings)
    mmi = MediaManagerItem(None)
    mmi.can_preview = True
    mmi.can_make_live = True
    mmi.can_add_to_service = True

    # WHEN: on_double_clicked() is called
    mmi.on_double_clicked()

    # THEN: on_preview_click() should have been called
    mocked_on_preview_click.assert_called_with()


def test_required_icons(media_env):
    """
    Test the default icons for plugins
    """
    # GIVEN: A MediaManagerItem
    mmi = MediaManagerItem(None)
    # WHEN: Object is created
    mmi.required_icons()
    # THEN: Default icons should be populated
    assert mmi.has_import_icon is False, 'There should be no import icon by default'
    assert mmi.has_new_icon is True, 'By default a new icon should be present'
    assert mmi.has_file_icon is False, 'There should be no file icon by default'
    assert mmi.has_delete_icon is True, 'By default a delete icon should be present'
    assert mmi.add_to_service_item is False, 'There should be no add_to_service icon by default'
    assert mmi.can_preview is True, 'There should be a preview icon by default'
    assert mmi.can_make_live is True, 'There should be a make live by default'
    assert mmi.can_add_to_service is True, 'There should be a add to service icon by default'


@patch('opal.core.lib.mediamanageritem.MediaManagerItem.on_live_click')
def test_on_double_clicked_go_live(mocked_on_live_click, media_env, registry):
    """
    Test that when "Double-click to go live" is enabled that the item goes live
    """
    # GIVEN: A setting to enable "Double-click to go live" and a media manager item
    mocked_settings = MagicMock()
    mocked_settings.value.side_effect = lambda x: x == 'advanced/double click live'
    Registry().register('settings', mocked_settings)
    mmi = MediaManagerItem(None)
    mmi.can_preview = True
    mmi.can_make_live = True
    mmi.can_add_to_service = True

    # WHEN: on_double_clicked() is called
    mmi.on_double_clicked()

    # THEN: on_live_click() should have been called
    mocked_on_live_click.assert_called_with()


@patch('opal.core.lib.mediamanageritem.MediaManagerItem.on_live_click')
@patch('opal.core.lib.mediamanageritem.MediaManagerItem.on_preview_click')
def test_on_double_clicked_single_click_preview(mocked_on_preview_click, mocked_on_live_click, media_env, registry):
    """
    Test that when "Single-click preview" is enabled then nothing happens on double-click
    """
    # GIVEN: A setting to enable "Double-click to go live" and a media manager item
    mocked_settings = MagicMock()
    mocked_settings.value.side_effect = lambda x: x == 'advanced/single click preview'
    Registry().register('settings', mocked_settings)
    mmi = MediaManagerItem(None)
    mmi.can_preview = True
    mmi.can_make_live = True
    mmi.can_add_to_service = True

    # WHEN: on_double_clicked() is called
    mmi.on_double_clicked()

    # THEN: on_live_click() should have been called
    assert 0 == mocked_on_live_click.call_count, 'on_live_click() should not have been called'
    assert 0 == mocked_on_preview_click.call_count, 'on_preview_click() should not have been called'


def test_search_options(media_env):
    """
    Test that the default search options return a empty list
    """
    # GIVEN: A media manager item
    mmi = MediaManagerItem(None)

    # WHEN: The search options are requested
    result = mmi.search_options()

    # THEN: should return a empty list
    assert result == []


def test_set_search_option(media_env):
    """
    Test that the default set search option return false because it's setting a non existant setting
    """
    # GIVEN: A media manager item
    mmi = MediaManagerItem(None)

    # WHEN: The a search option is set
    result = mmi.set_search_option('my option', 'my value')

    # THEN: should return false
    assert result is False


def test_on_selection_change_updates_preview_live_service_action_state(media_env, registry):
    """
    Test that Preview/Live/Add actions are disabled with no selection and enabled with selection.
    """
    # GIVEN: A media manager item with mocked actions and list view
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = False
    Registry().register('settings', mocked_settings)
    mmi = MediaManagerItem(None)
    mmi.list_view = MagicMock()
    mmi.preview_action = MagicMock()
    mmi.live_action = MagicMock()
    mmi.add_to_service_action = MagicMock()
    mmi.quick_preview_allowed = False
    mmi.auto_select_id = -1

    # WHEN: Nothing is selected
    mmi.list_view.selectedIndexes.return_value = []
    mmi.on_selection_change()

    # THEN: Actions should be disabled
    mmi.preview_action.setEnabled.assert_called_with(False)
    mmi.live_action.setEnabled.assert_called_with(False)
    mmi.add_to_service_action.setEnabled.assert_called_with(False)

    # WHEN: Something is selected
    mmi.list_view.selectedIndexes.return_value = [MagicMock()]
    mmi.on_selection_change()

    # THEN: Actions should be enabled
    mmi.preview_action.setEnabled.assert_called_with(True)
    mmi.live_action.setEnabled.assert_called_with(True)
    mmi.add_to_service_action.setEnabled.assert_called_with(True)


def test_on_selection_change_updates_add_to_selected_service_action_state(media_env, registry):
    """
    Test that the "Add to selected Service Item" context action is disabled when no service item is selected.
    """
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = False
    Registry().register('settings', mocked_settings)
    mmi = MediaManagerItem(None)
    mmi.list_view = MagicMock()
    mmi._service_manager = MagicMock()
    mmi._service_manager.find_service_item.return_value = (-1, -1)
    mmi.add_to_service_context_action = MagicMock()

    # WHEN: A library item is selected but no service item is selected
    mmi.list_view.selectedIndexes.return_value = [MagicMock()]
    mmi.on_selection_change()

    # THEN: The add-to-selected-service action should be disabled
    mmi.add_to_service_context_action.setEnabled.assert_called_with(False)

    # WHEN: A valid service item is selected
    mmi.service_manager.find_service_item.return_value = (0, -1)
    mmi.on_selection_change()

    # THEN: The add-to-selected-service action should be enabled
    mmi.add_to_service_context_action.setEnabled.assert_called_with(True)


def test_on_selection_change_updates_edit_delete_action_state(media_env, registry):
    """
    Test that Edit/Delete actions are disabled with no selection and enabled with selection.
    """
    # GIVEN: A media manager item with mocked actions and list view
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = False
    Registry().register('settings', mocked_settings)
    mmi = MediaManagerItem(None)
    mmi.list_view = MagicMock()
    mmi.edit_action = MagicMock()
    mmi.delete_action = MagicMock()
    mmi.edit_context_action = MagicMock()
    mmi.delete_context_action = MagicMock()

    # WHEN: Nothing is selected
    mmi.list_view.selectedIndexes.return_value = []
    mmi.on_selection_change()

    # THEN: Edit/Delete actions should be disabled
    mmi.edit_action.setEnabled.assert_called_with(False)
    mmi.delete_action.setEnabled.assert_called_with(False)
    mmi.edit_context_action.setEnabled.assert_called_with(False)
    mmi.delete_context_action.setEnabled.assert_called_with(False)

    # WHEN: Something is selected
    mmi.list_view.selectedIndexes.return_value = [MagicMock()]
    mmi.on_selection_change()

    # THEN: Edit/Delete actions should be enabled
    mmi.edit_action.setEnabled.assert_called_with(True)
    mmi.delete_action.setEnabled.assert_called_with(True)
    mmi.edit_context_action.setEnabled.assert_called_with(True)
    mmi.delete_context_action.setEnabled.assert_called_with(True)


def test_on_selection_change_does_not_override_edit_delete_when_selection_rule_disabled(media_env, registry):
    """
    Test that edit/delete selection gating can be explicitly disabled by plugins.
    """
    # GIVEN: A media manager item where selection-based edit/delete disabling is turned off
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = False
    Registry().register('settings', mocked_settings)
    mmi = MediaManagerItem(None)
    mmi.disable_edit_delete_by_selection = False
    mmi.list_view = MagicMock()
    mmi.list_view.selectedIndexes.return_value = []
    mmi.edit_action = MagicMock()
    mmi.delete_action = MagicMock()
    mmi.edit_context_action = MagicMock()
    mmi.delete_context_action = MagicMock()

    # WHEN: Selection changes
    mmi.on_selection_change()

    # THEN: edit/delete actions should not be modified by the base selection updater
    mmi.edit_action.setEnabled.assert_not_called()
    mmi.delete_action.setEnabled.assert_not_called()
    mmi.edit_context_action.setEnabled.assert_not_called()
    mmi.delete_context_action.setEnabled.assert_not_called()
