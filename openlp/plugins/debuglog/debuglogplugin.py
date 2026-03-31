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

import logging
import csv
import io
from datetime import datetime

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.state import State
from openlp.core.common.enum import PluginStatus
from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.core.lib.plugin import Plugin, StringContent
from openlp.core.lib.ui import create_action
from openlp.core.ui.icons import UiIcons


log = logging.getLogger(__name__)

SEVERITY_LEVELS = [
    'All',
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL'
]


class DebugLogFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Filter rows by severity and free-text message query."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._severity = 'All'
        self._search_text = ''

    def set_severity(self, severity):
        self._severity = severity
        self.invalidateFilter()

    def set_search_text(self, text):
        self._search_text = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if not model:
            return False
        message_index = model.index(source_row, 0, source_parent)
        severity_index = model.index(source_row, 2, source_parent)
        message_text = str(model.data(message_index) or '')
        severity_text = str(model.data(severity_index) or '')
        if self._severity != 'All' and severity_text != self._severity:
            return False
        if self._search_text and self._search_text not in message_text.lower():
            return False
        return True


class DebugLogPanel(QtWidgets.QWidget):
    """Dock panel UI that shows, filters and sorts debug messages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        controls_layout = QtWidgets.QHBoxLayout()
        self.severity_label = QtWidgets.QLabel(self)
        self.severity_combo = QtWidgets.QComboBox(self)
        self.severity_combo.addItems(SEVERITY_LEVELS)
        self.search_label = QtWidgets.QLabel(self)
        self.search_edit = QtWidgets.QLineEdit(self)
        controls_layout.addWidget(self.severity_label)
        controls_layout.addWidget(self.severity_combo)
        controls_layout.addWidget(self.search_label)
        controls_layout.addWidget(self.search_edit, 1)
        self.copy_button = QtWidgets.QPushButton(self)
        controls_layout.addWidget(self.copy_button)
        layout.addLayout(controls_layout)

        self.model = QtGui.QStandardItemModel(0, 3, self)
        self.model.setHorizontalHeaderLabels([
            translate('DebugLogPlugin', 'Message'),
            translate('DebugLogPlugin', 'Time'),
            translate('DebugLogPlugin', 'Severity')
        ])
        self.proxy_model = DebugLogFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table_view = QtWidgets.QTableView(self)
        self.table_view.setObjectName('debug_log_table_view')
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_view.verticalHeader().setVisible(True)
        self.table_view.setMouseTracking(True)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table_view.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table_view, 1)

        self.retranslate_ui()
        self.severity_combo.currentTextChanged.connect(self.proxy_model.set_severity)
        self.search_edit.textChanged.connect(self.proxy_model.set_search_text)
        self.copy_button.clicked.connect(self.copy_selected_rows_to_clipboard)
        self.table_view.entered.connect(self.on_table_view_entered)

    def retranslate_ui(self):
        self.severity_label.setText(translate('DebugLogPlugin', 'Severity:'))
        self.search_label.setText(translate('DebugLogPlugin', 'Search:'))
        self.search_edit.setPlaceholderText(translate('DebugLogPlugin', 'Filter by message text'))
        self.copy_button.setText(translate('DebugLogPlugin', 'Copy'))

    def add_entry(self, message, timestamp, severity):
        message_item = QtGui.QStandardItem(message)
        message_item.setToolTip(message)
        self.model.appendRow([
            message_item,
            QtGui.QStandardItem(timestamp),
            QtGui.QStandardItem(severity)
        ])
        self.table_view.scrollToBottom()

    def on_table_view_entered(self, index):
        if not index.isValid():
            return
        source_index = self.proxy_model.mapToSource(index)
        message_index = source_index.siblingAtColumn(0)
        message = str(self.model.data(message_index) or '')
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), message, self.table_view)

    def copy_selected_rows_to_clipboard(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Message', 'Time', 'Severity'])

        selected_rows = sorted({index.row() for index in self.table_view.selectionModel().selectedRows()})
        for proxy_row in selected_rows:
            source_row = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0)).row()
            writer.writerow([
                self.model.item(source_row, 0).text() if self.model.item(source_row, 0) else '',
                self.model.item(source_row, 1).text() if self.model.item(source_row, 1) else '',
                self.model.item(source_row, 2).text() if self.model.item(source_row, 2) else ''
            ])
        QtWidgets.QApplication.clipboard().setText(output.getvalue())


class _DebugLogEmitter(QtCore.QObject):
    message = QtCore.Signal(str, str, str)


class DebugLogHandler(logging.Handler):
    """Forward log records to the debug panel over a Qt signal."""

    def __init__(self, emitter):
        super().__init__(level=logging.DEBUG)
        self._emitter = emitter

    def emit(self, record):
        if record.name.startswith('openlp.plugins.debuglog'):
            return
        try:
            text = record.getMessage()
            timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
            self._emitter.message.emit(text, timestamp, record.levelname)
        except Exception:
            self.handleError(record)


class DebugLogPlugin(Plugin):
    """Plugin providing a dock panel for debug log inspection."""

    def __init__(self):
        Settings.extend_default_settings({
            'debuglog/status': PluginStatus.Inactive,
            'shortcuts/showDebugLogPanel': []
        })
        super(DebugLogPlugin, self).__init__('debuglog')
        if not Registry().has(f'{self.name}_plugin'):
            Registry().register(f'{self.name}_plugin', self)
        self.weight = -2
        self.icon = UiIcons().info
        self.debug_log_dock = None
        self.debug_log_panel = None
        self.show_debug_log_panel_action = None
        self._emitter = _DebugLogEmitter()
        self._emitter.message.connect(self._on_log_message)
        self._handler = None
        State().add_service(self.name, self.weight, is_plugin=True)
        State().update_pre_conditions(self.name, self.check_pre_conditions())

    def check_pre_conditions(self):
        return True

    def set_plugin_text_strings(self):
        self.text_strings[StringContent.Name] = {
            'singular': translate('DebugLogPlugin', 'Debug Log', 'name singular'),
            'plural': translate('DebugLogPlugin', 'Debug Logs', 'name plural')
        }
        self.text_strings[StringContent.VisibleName] = {
            'title': translate('DebugLogPlugin', 'Debug Log', 'container title')
        }

    def add_tools_menu_item(self, tools_menu):
        self.debug_log_dock = QtWidgets.QDockWidget(self.main_window)
        self.debug_log_dock.setObjectName('debug_log_dock')
        self.debug_log_dock.setWindowIcon(UiIcons().info)
        self.debug_log_dock.setWindowTitle(translate('DebugLogPlugin', 'Debugging'))
        self.debug_log_panel = DebugLogPanel(self.debug_log_dock)
        self.debug_log_dock.setWidget(self.debug_log_panel)
        self.debug_log_dock.setVisible(False)
        self.main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.debug_log_dock)

        self.show_debug_log_panel_action = create_action(
            tools_menu,
            'showDebugLogPanel',
            text=translate('DebugLogPlugin', '&Debugging'),
            icon=UiIcons().info,
            statustip=translate('DebugLogPlugin', 'Show or hide the Debugging panel.'),
            checked=False,
            visible=False,
            can_shortcuts=True,
            triggers=self.on_toggle_panel
        )
        self.show_debug_log_panel_action.setCheckable(True)
        tools_menu.addAction(self.show_debug_log_panel_action)
        self.debug_log_dock.visibilityChanged.connect(self._on_panel_visibility_changed)

    def initialise(self):
        super(DebugLogPlugin, self).initialise()
        if self.show_debug_log_panel_action:
            self.show_debug_log_panel_action.setVisible(True)
            self.show_debug_log_panel_action.setChecked(True)
        if self._handler is None:
            self._handler = DebugLogHandler(self._emitter)
            logging.getLogger().addHandler(self._handler)

    def app_startup(self):
        # restoreState() runs after initialise(), so we must show the dock here
        # to ensure it is visible regardless of the previously saved window state.
        if self.debug_log_dock:
            self.debug_log_dock.setVisible(True)

    def finalise(self):
        if self._handler is not None:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None
        if self.show_debug_log_panel_action:
            self.show_debug_log_panel_action.setVisible(False)
            self.show_debug_log_panel_action.setChecked(False)
        if self.debug_log_dock:
            self.debug_log_dock.setVisible(False)
        super(DebugLogPlugin, self).finalise()

    def on_toggle_panel(self, checked=False):
        if self.debug_log_dock:
            self.debug_log_dock.setVisible(bool(checked))

    def _on_panel_visibility_changed(self, is_visible):
        if self.show_debug_log_panel_action:
            self.show_debug_log_panel_action.blockSignals(True)
            self.show_debug_log_panel_action.setChecked(is_visible)
            self.show_debug_log_panel_action.blockSignals(False)

    def _on_log_message(self, message, timestamp, severity):
        if self.debug_log_panel:
            self.debug_log_panel.add_entry(message, timestamp, severity)

    @staticmethod
    def about():
        return translate('DebugLogPlugin', '<strong>Debug Log Plugin</strong>'
                         '<br />The debug log plugin captures log output and displays it in a filterable panel.')
