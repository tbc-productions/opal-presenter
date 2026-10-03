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
Package to test the openlp.core.ui.settingsform package.
"""
from unittest.mock import MagicMock, patch

from PySide6 import QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.core.ui.servicetab import ServiceTab
from openlp.core.ui.settingsform import SettingsForm


class MockTab(QtWidgets.QWidget):
    """A mocked tab object, to make MyPy happy"""
    def __init__(self, parent, tab_title: str, tab_title_visible: str, icon_path: str):
        super().__init__(parent)
        self.tab_title = tab_title
        self.tab_title_visible = tab_title_visible
        self.icon_path = icon_path
        self.save = MagicMock()
        self.load = MagicMock()
        self.cancel = MagicMock()


def test_insert_tab_visible(registry: Registry, mock_settings: MagicMock):
    """
    Test that the insert_tab() method works correctly when a visible tab is inserted
    """
    # GIVEN: A mocked tab and a Settings Form
    settings_form = SettingsForm(None)
    general_tab = MagicMock()
    general_tab.tab_title = 'mock'
    general_tab.tab_title_visible = 'Mock'
    general_tab.icon_path = ':/icon/openlp-logo.svg'
    expected_icon = QtGui.QIcon(QtGui.QPixmap(16, 16))

    # WHEN: We insert the general tab
    with patch.object(settings_form.setting_list_widget, 'addItem') as mocked_add_item, \
            patch.object(settings_form, '_build_settings_tab_icon', return_value=expected_icon) as mocked_build_icon:
        settings_form.insert_tab(general_tab, is_visible=True)

        # THEN: The tab is registered for the content area and an item is added to the sidebar list
        assert general_tab in settings_form._settings_tabs_ordered
        mocked_build_icon.assert_called_once_with(general_tab)
        assert 1 == mocked_add_item.call_count, 'addItem should have been called'


def test_build_settings_tab_icon_uses_service_theme_color_for_song_tabs(registry: Registry, settings: Settings):
    """
    Test that the songs settings icon uses the configured service theme color.
    """
    settings_form = SettingsForm(None)
    settings.setValue('servicemanager/theme color song', '#123456')
    song_tab = MagicMock()
    song_tab.tab_title = 'songs'
    song_tab.icon_path = ':/icon/openlp-logo.svg'
    expected_icon = QtGui.QIcon(QtGui.QPixmap(16, 16))

    with patch('openlp.core.ui.settingsform.UiIcons') as mocked_ui_icons:
        mocked_ui_icons.return_value.get_icon_variant.return_value = expected_icon

        icon = settings_form._build_settings_tab_icon(song_tab)

    mocked_ui_icons.return_value.get_icon_variant.assert_called_once_with('music', color='#123456')
    assert icon.cacheKey() == expected_icon.cacheKey()


def test_insert_tab_not_visible(registry: Registry, mock_settings: MagicMock):
    """
    Test that the insert_tab() method works correctly when a tab that should not be visible is inserted
    """
    # GIVEN: A general tab and a Settings Form
    settings_form = SettingsForm(None)
    general_tab = MagicMock()
    general_tab.tab_title = 'mock'

    # WHEN: We insert the general tab
    with patch.object(settings_form.setting_list_widget, 'addItem') as mocked_add_item:
        settings_form.insert_tab(general_tab, is_visible=False)

        # THEN: The tab is registered but no sidebar list item is added
        assert general_tab in settings_form._settings_tabs_ordered
        assert 0 == mocked_add_item.call_count, 'addItem should not have been called'


def test_accept_with_inactive_plugins(registry: Registry, mock_settings: MagicMock):
    """
    Test that the accept() method works correctly when some of the plugins are inactive
    """
    # GIVEN: A visible general tab and an invisible theme tab in a Settings Form

    settings_form = SettingsForm(None)
    general_tab = MockTab(None, 'mock-general', 'Mock General', ':/icon/openlp-logo.svg')
    settings_form.insert_tab(general_tab, is_visible=True)
    themes_tab = MockTab(None, 'mock-themes', 'Mock Themes', ':/icon/openlp-logo.svg')
    settings_form.insert_tab(themes_tab, is_visible=False)

    # WHEN: The accept() method is called
    settings_form.accept()

    # THEN: The general tab's save() method should have been called, but not the themes tab
    general_tab.save.assert_called_with()
    assert 0 == themes_tab.save.call_count, 'The Themes tab\'s save() should not have been called'


def test_list_item_changed_invalid_item(registry: Registry, mock_settings: MagicMock):
    """
    Test that the list_item_changed() slot handles a non-existent item
    """
    # GIVEN: A mocked tab inserted into a Settings Form
    settings_form = SettingsForm(None)
    general_tab = MockTab(None, 'mock', 'Mock', ':/icon/openlp-logo.svg')
    settings_form.insert_tab(general_tab, is_visible=True)

    # WHEN: The list_item_changed() slot is called with an invalid item index
    settings_form.list_item_changed(100)

    # THEN: No tab is placed in the content layout (early return before iterating tabs)
    assert settings_form.content_tabs_layout.count() == 0


def test_reject_with_inactive_items(registry: Registry, mock_settings: MagicMock):
    """
    Test that the reject() method works correctly when some of the plugins are inactive
    """
    # GIVEN: A visible general tab and an invisible theme tab in a Settings Form
    settings_form = SettingsForm(None)
    general_tab = MockTab(None, 'mock-general', 'Mock General', ':/icon/openlp-logo.svg')
    settings_form.insert_tab(general_tab, is_visible=True)
    themes_tab = MockTab(None, 'mock-themes', 'Mock Themes', ':/icon/openlp-logo.svg')
    settings_form.insert_tab(themes_tab, is_visible=False)

    # WHEN: The reject() method is called
    settings_form.reject()

    # THEN: The general tab's cancel() method should have been called, but not the themes tab
    general_tab.cancel.assert_called_with()
    assert 0 == themes_tab.cancel.call_count, 'The Themes tab\'s cancel() should not have been called'


def test_register_post_process(registry: Registry, mock_settings: MagicMock):
    """
    Test that the register_post_process() method works correctly
    """
    # GIVEN: A settings form instance
    settings_form = SettingsForm(None)
    fake_function = MagicMock()

    # WHEN: register_post_process() is called
    settings_form.register_post_process(fake_function)

    # THEN: The fake function should be in the settings form's list
    assert fake_function in settings_form.processes


def test_help_button_removed(mock_settings: MagicMock):
    """The settings dialog uses control tooltips instead of a Help button."""
    settings_form = SettingsForm(None)

    assert settings_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Help) is None


def test_insert_tab_normalises_input_control_heights(registry: Registry, settings: Settings):
    """
    Test that settings input widgets get a consistent minimum height when a tab is inserted.
    """
    # GIVEN: A service tab with line edit, combo box, and time edit controls
    settings_form = SettingsForm(None)
    service_tab = ServiceTab(settings_form)

    # WHEN: The service tab is inserted into the settings form
    settings_form.insert_tab(service_tab, is_visible=False)

    # THEN: The input controls should share the normalized minimum height
    assert service_tab.service_name_edit.minimumHeight() == 32
    assert service_tab.service_name_day.minimumHeight() == 32
    assert service_tab.service_name_time.minimumHeight() == 32


def test_get_ordered_tabs_places_general_first_advanced_last(registry: Registry, mock_settings: MagicMock):
    """
    Test that tab ordering is General first, alphabetical middle, Advanced last.
    """
    # GIVEN: A settings form with unordered core tabs and plugin tabs
    settings_form = SettingsForm(None)
    settings_form.general_tab = MockTab(None, 'general', 'General', ':/icon/openlp-logo.svg')
    settings_form.advanced_tab = MockTab(None, 'advanced', 'Advanced', ':/icon/openlp-logo.svg')
    settings_form.service_tab = MockTab(None, 'service', 'Service', ':/icon/openlp-logo.svg')
    settings_form.screens_tab = MockTab(None, 'screens', 'Screens', ':/icon/openlp-logo.svg')
    settings_form.themes_tab = MockTab(None, 'themes', 'Themes', ':/icon/openlp-logo.svg')
    settings_form.player_tab = MockTab(None, 'media', 'Media', ':/icon/openlp-logo.svg')
    settings_form.projector_tab = MockTab(None, 'projector', 'Projectors', ':/icon/openlp-logo.svg')
    settings_form.api_tab = MockTab(None, 'api', 'API', ':/icon/openlp-logo.svg')

    active_plugin = MagicMock()
    active_plugin.settings_tab = MockTab(None, 'alerts', 'Alerts', ':/icon/openlp-logo.svg')
    active_plugin.is_active.return_value = True
    inactive_plugin = MagicMock()
    inactive_plugin.settings_tab = MockTab(None, 'songs', 'Songs', ':/icon/openlp-logo.svg')
    inactive_plugin.is_active.return_value = False

    with patch('openlp.core.ui.settingsform.State') as mocked_state:
        mocked_state.return_value.list_plugins.return_value = [inactive_plugin, active_plugin]

        # WHEN: Getting ordered tabs
        ordered_tabs = settings_form._get_ordered_tabs()

    # THEN: General should be first, Advanced last, and middle sorted A-Z by visible title
    ordered_titles = [tab.tab_title_visible for tab, _ in ordered_tabs]
    assert ordered_titles == [
        'General', 'Alerts', 'API', 'Media', 'Projectors', 'Screens', 'Service', 'Songs', 'Themes', 'Advanced'
    ]
    assert ordered_tabs[0][1] is True
    assert ordered_tabs[-1][1] is True
