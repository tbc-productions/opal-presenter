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
This module contains tests for the Alerts settings tab.
"""
from PySide6 import QtGui

from opal.core.common.settings import Settings
from opal.plugins.alerts.lib.alertstab import AlertsTab


def test_update_display_uses_preview_palette_colors(registry, settings: Settings):
    """
    Test that the alerts preview textbox applies configured colors through the widget palette.
    """
    # GIVEN: An alerts settings tab with explicit preview colors
    settings.setValue('alerts/font face', QtGui.QFont().family())
    alerts_tab = AlertsTab(None, 'alerts', 'Alerts', ':/icon/opal-presenter.png')
    alerts_tab.background_color = '#112233'
    alerts_tab.font_color = '#ddeeff'
    alerts_tab.font_size = 24

    # WHEN: The preview is updated
    alerts_tab.update_display()

    # THEN: The preview uses the expected background and text colors
    active_base = alerts_tab.font_preview.palette().color(QtGui.QPalette.ColorGroup.Active,
                                                          QtGui.QPalette.ColorRole.Window)
    active_text = alerts_tab.font_preview.palette().color(QtGui.QPalette.ColorGroup.Active,
                                                          QtGui.QPalette.ColorRole.WindowText)
    inactive_base = alerts_tab.font_preview.palette().color(QtGui.QPalette.ColorGroup.Inactive,
                                                            QtGui.QPalette.ColorRole.Window)
    inactive_text = alerts_tab.font_preview.palette().color(QtGui.QPalette.ColorGroup.Inactive,
                                                            QtGui.QPalette.ColorRole.WindowText)

    assert active_base == QtGui.QColor('#112233')
    assert inactive_base == QtGui.QColor('#112233')
    assert active_text == QtGui.QColor('#ddeeff')
    assert inactive_text == QtGui.QColor('#ddeeff')


def test_update_display_prefers_antialiased_font_rendering(registry, settings: Settings):
    """
    Test that the alerts preview label requests antialiased font rendering.
    """
    # GIVEN: An alerts settings tab with default preview settings
    settings.setValue('alerts/font face', QtGui.QFont().family())
    alerts_tab = AlertsTab(None, 'alerts', 'Alerts', ':/icon/opal-presenter.png')

    # WHEN: The preview is updated
    alerts_tab.update_display()

    # THEN: The preview font should prefer antialiasing
    assert alerts_tab.font_preview.font().styleStrategy() & QtGui.QFont.StyleStrategy.PreferAntialias
