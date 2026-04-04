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
Package to test the openlp.core.ui.generaltab package.
"""
from unittest.mock import patch

from openlp.core.ui.generaltab import GeneralTab
from openlp.core.ui.settingsform import SettingsForm
from openlp.core.ui.style import UiThemes

from PySide6 import QtCore, QtTest, QtWidgets


def test_creation(settings):
    """
    Test that General Tab is created.
    """
    # GIVEN: A new General Tab
    settings_form = SettingsForm(None)

    # WHEN: I create an general tab
    general_tab = GeneralTab(settings_form)

    # THEN:
    assert "Core" == general_tab.tab_title, 'The tab title should be Core'


def test_slide_max_height_combo_is_left_aligned(settings):
    """
    Test that max height combo does not expand and remains left-aligned in form layout.
    """
    # GIVEN: A new General Tab
    settings_form = SettingsForm(None)
    general_tab = GeneralTab(settings_form)

    # WHEN/THEN: The combo should use a fixed horizontal size policy
    assert general_tab.slide_max_height_combo_box.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Policy.Fixed
    assert general_tab.slide_max_height_combo_box.parent() == general_tab.slide_max_height_row_widget
    assert general_tab.slide_max_height_row_layout.count() == 2
    assert general_tab.slide_max_height_row_layout.itemAt(1).spacerItem() is not None
    assert general_tab.slide_max_height_label.wordWrap() is True
    assert '\n' not in general_tab.slide_max_height_label.text()


def test_change_search_as_type(settings):
    """
    Test that when search as type is changed custom and song configs are updated
    """
    # GIVEN: A new General Tab
    settings_form = SettingsForm(None)
    general_tab = GeneralTab(settings_form)

    # WHEN: I change search as type check box
    general_tab.on_search_as_type_check_box_changed(True)

    # THEN: we should have two post save processed to run
    assert 2 == len(settings_form.processes), 'Two post save processes should be created'
    assert "songs_config_updated" in settings_form.processes, 'The songs plugin should be called'
    assert "custom_config_updated" in settings_form.processes, 'The custom plugin should be called'


def test_slide_numbers_in_footer(settings):
    """
    Test that when the slide number in footers option is changed then the settings are updated
    """
    # GIVEN: Settings, a settings form and a general tab
    settings.setValue('advanced/slide numbers in footer', False)
    settings_form = SettingsForm(None)
    general_tab = GeneralTab(settings_form)
    settings_form.insert_tab(general_tab, is_visible=True)

    # WHEN: I click the checkbox and then save
    QtTest.QTest.mouseClick(general_tab.slide_no_in_footer_checkbox, QtCore.Qt.MouseButton.LeftButton)
    settings_form.accept()

    # THEN: the settings should be updated
    assert settings.value('advanced/slide numbers in footer') is True


def test_new_service_message(settings):
    """
    Test that when the new service message option is changed then the settings are updated
    """
    # GIVEN: Settings, a settings form and a general tab
    settings.setValue('advanced/new service message', True)
    settings_form = SettingsForm(None)
    general_tab = GeneralTab(settings_form)
    settings_form.insert_tab(general_tab, is_visible=True)

    # WHEN: I click the checkbox and then save
    QtTest.QTest.mouseClick(general_tab.new_service_message_check_box, QtCore.Qt.MouseButton.LeftButton)
    settings_form.accept()

    # THEN: the settings should be updated
    assert settings.value('advanced/new service message') is False


def test_logo_fit_setting_is_saved(settings):
    """
    Test that changing the logo fit option updates the setting value.
    """
    # GIVEN: Settings, a settings form and a general tab
    settings.setValue('core/logo fit', 'contain')
    settings_form = SettingsForm(None)
    general_tab = GeneralTab(settings_form)
    settings_form.insert_tab(general_tab, is_visible=True)

    # WHEN: I select a new fit mode and save
    general_tab.logo_fit_combo_box.setCurrentIndex(0)
    settings_form.accept()

    # THEN: the settings should be updated
    assert settings.value('core/logo fit') == 'cover'


@patch('openlp.core.ui.generaltab.has_ui_theme', return_value=False)
def test_get_ui_theme_index_maps_native_to_system_theme(_mock_has_ui_theme):
    """Test that legacy Native theme maps to the Use system theme combo index."""
    assert GeneralTab.get_ui_theme_index(UiThemes.Native) == 0


@patch('openlp.core.ui.generaltab.has_ui_theme', return_value=False)
def test_get_ui_theme_name_index_3_falls_back_to_automatic_without_qdarkstyle(_mock_has_ui_theme):
    """Test that index 3 maps to Automatic when QDarkStyle is unavailable."""
    assert GeneralTab.get_ui_theme_name(3) == UiThemes.Automatic


