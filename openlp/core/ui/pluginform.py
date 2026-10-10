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
The actual plugin view form
"""
import logging
import sys
from html import escape
from pathlib import Path

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.state import State
from openlp.core.common.i18n import get_natural_key, translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.common.restart import show_restart_message
from openlp.core.lib.plugin import PluginStatus
from openlp.core.ui.plugindialog import Ui_PluginViewDialog


log = logging.getLogger(__name__)


class PluginForm(QtWidgets.QDialog, Ui_PluginViewDialog, RegistryProperties):
    """
    The plugin form provides user control over the plugins OpenLP uses.
    """
    def __init__(self, parent=None):
        """
        Constructor
        """
        super(PluginForm, self).__init__(parent,
                                         QtCore.Qt.WindowType.WindowSystemMenuHint |
                                         QtCore.Qt.WindowType.WindowTitleHint |
                                         QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.active_plugin = None
        self.programmatic_change = False
        self.setup_ui(self)
        # Right, now let's put some signals and slots together!
        self.plugin_list_widget.itemSelectionChanged.connect(self.on_plugin_list_widget_selection_changed)
        self.status_checkbox.stateChanged.connect(self.on_status_checkbox_changed)
        self.open_folder_button.clicked.connect(self.on_open_folder_clicked)
        self.load()

    def load(self, selected_plugin=None):
        """
        Load the plugin details into the screen
        """
        self.programmatic_change = True
        with QtCore.QSignalBlocker(self.plugin_list_widget):
            self.plugin_list_widget.clear()
            self._clear_details()
            plugins = [plugin for plugin in State().list_plugins() if plugin]
            for plugin in plugins:
                plugin.status = int(plugin.status)
            plugins.sort(key=lambda plugin: (plugin.status != PluginStatus.Active,
                                             get_natural_key(plugin.name_strings['singular'])))
            selected_row = 0
            for row, plugin in enumerate(plugins):
                item = QtWidgets.QListWidgetItem(self.plugin_list_widget)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, plugin)
                if plugin is selected_plugin:
                    selected_row = row
                # Set the little status text in brackets next to the plugin name.
                if plugin.status == PluginStatus.Disabled:
                    status_text = translate('OpenLP.PluginForm', '{name} (Disabled)')
                elif plugin.status == PluginStatus.Active:
                    status_text = translate('OpenLP.PluginForm', '{name}')
                else:
                    # PluginStatus.Inactive
                    status_text = translate('OpenLP.PluginForm', '{name} (Inactive)')
                item.setText(status_text.format(name=plugin.name_strings['singular']))
                item.setToolTip(item.text())
                # Dim inactive/disabled plugins
                if plugin.status != PluginStatus.Active:
                    colour = self.palette().color(QtGui.QPalette.ColorRole.Text)
                    colour.setAlphaF(0.65)
                    item.setForeground(colour)
                # If the plugin has an icon, set it!
                if plugin.icon:
                    item.setIcon(plugin.icon)
            if plugins:
                self.plugin_list_widget.setCurrentRow(selected_row)
        self.on_plugin_list_widget_selection_changed()
        self.programmatic_change = False

    def _clear_details(self):
        """
        Clear the plugin details widgets
        """
        self.active_plugin = None
        self.plugin_folder = None
        self.status_checkbox.setChecked(False)
        self.about_text_browser.setHtml('')
        self.status_checkbox.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.setToolTip('')

    def _set_details(self):
        """
        Set the details of the currently selected plugin
        """
        log.debug('PluginStatus: {status}'.format(status=str(self.active_plugin.status)))
        plugin = self.active_plugin
        module_path = getattr(sys.modules.get(type(plugin).__module__), '__file__', None)
        self.plugin_folder = Path(module_path).resolve().parent if module_path else None
        folder_available = self.plugin_folder is not None and self.plugin_folder.is_dir()
        self.open_folder_button.setEnabled(folder_available)
        self.open_folder_button.setToolTip(
            str(self.plugin_folder) if folder_available else
            translate('OpenLP.PluginForm', 'This plugin’s folder is not available on disk.'))
        version = plugin.version if getattr(plugin, 'version_is_explicit', True) else ''
        html = ''
        for field, label, value in [
            ('version', translate('OpenLP.PluginForm', 'Version'), version),
            ('developer', translate('OpenLP.PluginForm', 'Developer'), plugin.developer),
            ('licence', translate('OpenLP.PluginForm', 'Licence'), plugin.licence),
            ('website', translate('OpenLP.PluginForm', 'Website'), plugin.website),
            ('updates', translate('OpenLP.PluginForm', 'Updates'), getattr(plugin, 'updates', '')),
        ]:
            if not value or not str(value).strip():
                continue
            value_text = escape(str(value))
            if field == 'website':
                url = QtCore.QUrl(value)
                if url.isValid() and url.scheme() in ('http', 'https') and url.host():
                    value_text = '<a href="{url}">{url}</a>'.format(url=escape(value, quote=True))
            html += '<p><b>{label}:</b> {value}</p>'.format(label=escape(label), value=value_text)
        if html:
            html += '<hr>'
        html += '<h3>{about}</h3>{description}'.format(
            about=escape(translate('OpenLP.PluginForm', 'About')), description=plugin.about())
        self.about_text_browser.setHtml(html)
        self.programmatic_change = True
        if not self.active_plugin.can_be_disabled:
            self.status_checkbox.setChecked(True)
            self.status_checkbox.setEnabled(False)
        elif self.active_plugin.status != PluginStatus.Disabled:
            self.status_checkbox.setChecked(self.active_plugin.status == PluginStatus.Active)
            self.status_checkbox.setEnabled(True)
        else:
            self.status_checkbox.setChecked(False)
            self.status_checkbox.setEnabled(False)
        self.programmatic_change = False

    def on_plugin_list_widget_selection_changed(self):
        """
        If the selected plugin changes, update the form
        """
        if self.plugin_list_widget.currentItem() is None:
            self._clear_details()
            return
        self.active_plugin = self.plugin_list_widget.currentItem().data(QtCore.Qt.ItemDataRole.UserRole)
        if self.active_plugin:
            self._set_details()
        else:
            self._clear_details()

    def on_status_checkbox_changed(self, status):
        """
        If the status of a plugin is altered, apply the change
        """
        if self.programmatic_change or self.active_plugin is None:
            return
        if status:
            self.application.set_busy_cursor()
            self.active_plugin.toggle_status(PluginStatus.Active)
            self.application.set_normal_cursor()
            self.active_plugin.app_startup()
        else:
            self.active_plugin.toggle_status(PluginStatus.Inactive)
        self.load(selected_plugin=self.active_plugin)
        if getattr(self.active_plugin, 'requires_restart', False) is True:
            show_restart_message(
                self, translate('OpenLP.PluginForm', 'Restart Required'),
                translate('OpenLP.PluginForm', 'Restart OpenLP+ to apply this plugin change.'))

    def on_open_folder_clicked(self):
        """Open the selected plugin's installed directory in the system file manager."""
        if self.plugin_folder is None:
            return
        if (not self.plugin_folder.is_dir() or
                not QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.plugin_folder)))):
            QtWidgets.QMessageBox.warning(
                self, translate('OpenLP.PluginForm', 'Cannot Open Plugin Folder'),
                translate('OpenLP.PluginForm', 'The plugin folder could not be opened.'))
