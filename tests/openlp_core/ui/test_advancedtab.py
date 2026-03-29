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
Package to test the openlp.core.ui.advancedtab package.
"""
import platform

from openlp.core.ui.advancedtab import AdvancedTab, HAS_SCREEN_CAPTURE_KIT, HAS_WINDOWS_CAPTURE
from openlp.core.ui.settingsform import SettingsForm


def test_creation(settings):
    """
    Test that Advanced Tab is created.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)

    # WHEN: I create an advanced tab
    advanced_tab = AdvancedTab(settings_form)

    # THEN:
    assert "Advanced" == advanced_tab.tab_title, 'The tab title should be Advanced'


def test_desktop_capture_method_load_default(settings):
    """
    Test that desktop capture method defaults to Qt.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)
    advanced_tab = AdvancedTab(settings_form)

    # WHEN: the tab loads settings
    advanced_tab.load()

    # THEN: desktop capture method should default to Qt
    assert advanced_tab.desktop_capture_method_combobox.currentIndex() == 0


def test_desktop_capture_method_save(settings):
    """
    Test that desktop capture method is persisted.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)
    advanced_tab = AdvancedTab(settings_form)

    # WHEN: selecting mss and saving
    advanced_tab.desktop_capture_method_combobox.setCurrentIndex(1)
    advanced_tab.save()

    # THEN: value should be stored
    assert settings.value('advanced/desktop capture method') == 1


def test_desktop_capture_fps_load_default(settings):
    """
    Test that desktop capture fps defaults to index 1 (15 fps).
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)
    advanced_tab = AdvancedTab(settings_form)

    # WHEN: the tab loads settings
    advanced_tab.load()

    # THEN: desktop capture fps should default to 15 fps (index 1)
    assert advanced_tab.desktop_capture_fps_combobox.currentIndex() == 1


def test_desktop_capture_fps_save(settings):
    """
    Test that desktop capture fps setting is persisted.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)
    advanced_tab = AdvancedTab(settings_form)

    # WHEN: selecting 30 fps (index 2) and saving
    advanced_tab.desktop_capture_fps_combobox.setCurrentIndex(2)
    advanced_tab.save()

    # THEN: value should be stored
    assert settings.value('advanced/desktop capture fps') == 2


def test_desktop_capture_method_platform_options_visible_and_disabled_when_unsupported(settings):
    """
    Test that platform-specific capture methods are always visible but disabled when unsupported.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)
    advanced_tab = AdvancedTab(settings_form)

    # WHEN: the tab loads settings
    advanced_tab.load()

    # THEN: Both platform-specific methods should always be visible
    assert advanced_tab.desktop_capture_method_combobox.count() == 4
    sckit_item = advanced_tab.desktop_capture_method_combobox.model().item(2)
    windows_item = advanced_tab.desktop_capture_method_combobox.model().item(3)
    assert sckit_item is not None
    assert windows_item is not None

    # And each should only be enabled on its supported platform.
    if platform.system() == 'Darwin':
        assert sckit_item.isEnabled() == HAS_SCREEN_CAPTURE_KIT
        assert not windows_item.isEnabled()
    elif platform.system() == 'Windows':
        assert windows_item.isEnabled() == HAS_WINDOWS_CAPTURE
        assert not sckit_item.isEnabled()
    else:
        assert not sckit_item.isEnabled()
        assert not windows_item.isEnabled()
