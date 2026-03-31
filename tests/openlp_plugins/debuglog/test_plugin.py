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
Tests for the Debug Log plugin.
"""
import logging
from unittest.mock import patch

import pytest
from PySide6 import QtWidgets

from openlp.core.common.registry import Registry
from openlp.plugins.debuglog.debuglogplugin import DebugLogPlugin


@pytest.fixture
def debuglog_plugin(settings, registry, state):
    main_window = QtWidgets.QMainWindow()
    menu_bar = QtWidgets.QMenuBar(main_window)
    tools_menu = QtWidgets.QMenu(menu_bar)
    main_window.setMenuBar(menu_bar)
    registry.register('main_window', main_window)
    plugin = DebugLogPlugin()
    plugin.add_tools_menu_item(tools_menu)
    yield plugin


def test_about_text():
    """The plugin should expose a non-empty about text."""
    assert isinstance(DebugLogPlugin.about(), str)
    assert len(DebugLogPlugin.about()) > 0


def test_initialise_adds_log_entries(debuglog_plugin, qapp):
    """A log message should appear in the plugin panel after initialise."""
    debuglog_plugin.initialise()

    logging.getLogger('openlp.test').warning('warning from debug log plugin test')
    qapp.process_events()

    assert debuglog_plugin.debug_log_panel.model.rowCount() == 1
    assert debuglog_plugin.debug_log_panel.model.item(0, 0).text() == 'warning from debug log plugin test'
    assert debuglog_plugin.debug_log_panel.model.item(0, 2).text() == 'WARNING'
    debuglog_plugin.finalise()


def test_panel_filters_by_severity_and_message(debuglog_plugin):
    """The panel should filter by severity and message query."""
    panel = debuglog_plugin.debug_log_panel
    panel.add_entry('alpha warning', '2026-03-31 12:00:00', 'WARNING')
    panel.add_entry('beta info', '2026-03-31 12:00:01', 'INFO')
    panel.add_entry('gamma error', '2026-03-31 12:00:02', 'ERROR')

    panel.severity_combo.setCurrentText('ERROR')
    assert panel.proxy_model.rowCount() == 1

    panel.severity_combo.setCurrentText('All')
    panel.search_edit.setText('beta')
    assert panel.proxy_model.rowCount() == 1

    panel.search_edit.setText('missing')
    assert panel.proxy_model.rowCount() == 0


def test_hovering_message_shows_full_message_tooltip(debuglog_plugin):
    """Hovering a row should show a tooltip containing the full message text."""
    panel = debuglog_plugin.debug_log_panel
    message = 'This is a long debug message with extra details.'
    panel.add_entry(message, '2026-03-31 12:00:03', 'DEBUG')

    with patch('openlp.plugins.debuglog.debuglogplugin.QtWidgets.QToolTip.showText') as mock_show_text:
        index = panel.proxy_model.index(0, 0)
        panel.on_table_view_entered(index)

    mock_show_text.assert_called_once()
    assert mock_show_text.call_args[0][1] == message


def test_copy_selected_rows_exports_csv_to_clipboard(debuglog_plugin):
    """Copy should export only selected rows in CSV format to clipboard."""
    panel = debuglog_plugin.debug_log_panel
    panel.add_entry('first msg', '2026-03-31 12:01:00', 'INFO')
    panel.add_entry('second msg', '2026-03-31 12:01:01', 'ERROR')
    first_msg_row = None
    for row in range(panel.proxy_model.rowCount()):
        if panel.proxy_model.data(panel.proxy_model.index(row, 0)) == 'first msg':
            first_msg_row = row
            break
    assert first_msg_row is not None
    panel.table_view.selectRow(first_msg_row)

    with patch('openlp.plugins.debuglog.debuglogplugin.QtWidgets.QApplication.clipboard') as mock_clipboard:
        clipboard_obj = mock_clipboard.return_value
        panel.copy_selected_rows_to_clipboard()

    clipboard_obj.setText.assert_called_once()
    copied = clipboard_obj.setText.call_args[0][0]
    assert 'Message,Time,Severity' in copied
    assert 'first msg,2026-03-31 12:01:00,INFO' in copied
    assert 'second msg,2026-03-31 12:01:01,ERROR' not in copied
