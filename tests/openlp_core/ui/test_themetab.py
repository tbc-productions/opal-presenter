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
Package to test the opal.core.ui.ThemeTab package.
"""
from unittest.mock import MagicMock

from opal.core.common.registry import Registry
from opal.core.ui.settingsform import SettingsForm
from opal.core.ui.themestab import ThemesTab


def test_save_triggers_processes_true(mock_settings):
    """
    Test that the global theme event is triggered when the tab is visited.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)
    themes_tab = ThemesTab(settings_form)
    Registry().register('renderer', MagicMock())
    themes_tab.tab_visited = True
    # WHEN: I change search as type check box
    themes_tab.save()

    # THEN: update transitions and theme refresh should both be queued
    assert 'slidecontroller_update_item_transitions' in settings_form.processes
    assert 'theme_update_list' in settings_form.processes


def test_save_triggers_processes_false(mock_settings):
    """
    Test that the global theme event is not triggered when the tab is not visited.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)
    themes_tab = ThemesTab(settings_form)
    Registry().register('renderer', MagicMock())
    themes_tab.tab_visited = False
    # WHEN: I change search as type check box
    themes_tab.save()

    # THEN: transition refresh should still be queued even when the tab is not visited
    assert settings_form.processes == ['slidecontroller_update_item_transitions']


def test_item_transition_controls_disabled_when_unchecked(mock_settings):
    """
    Test that transition speed controls are disabled when item transitions are off.
    """
    # GIVEN: A themes tab with item transitions disabled
    settings_form = SettingsForm(None)
    themes_tab = ThemesTab(settings_form)
    themes_tab.item_transitions_check_box.setChecked(False)

    # WHEN: The UI refreshes enabled state
    themes_tab._update_item_transition_controls()

    # THEN: Transition controls should be disabled
    assert themes_tab.item_transition_speed_label.isEnabled() is False
    assert themes_tab.item_transition_speed_combo_box.isEnabled() is False


def test_item_transition_controls_enabled_when_checked(mock_settings):
    """
    Test that transition speed controls are enabled when item transitions are on.
    """
    # GIVEN: A themes tab with item transitions enabled
    settings_form = SettingsForm(None)
    themes_tab = ThemesTab(settings_form)
    themes_tab.item_transitions_check_box.setChecked(True)

    # WHEN: The UI refreshes enabled state
    themes_tab._update_item_transition_controls()

    # THEN: Transition controls should be enabled
    assert themes_tab.item_transition_speed_label.isEnabled() is True
    assert themes_tab.item_transition_speed_combo_box.isEnabled() is True
