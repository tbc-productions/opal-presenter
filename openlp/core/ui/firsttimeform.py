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
This module contains the first time wizard.
"""
from pathlib import Path

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.common.registry import Registry
from openlp.core.lib.plugin import PluginStatus
from openlp.core.ui.firsttimewizard import UiFirstTimeWizard


class FirstTimeForm(QtWidgets.QWizard, UiFirstTimeWizard, RegistryProperties):
    """Configure OpenLP+ locally, without downloading upstream resources."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui(self)
        self.has_run_wizard = False
        Registry().register_function('config_screen_changed', self.screen_selection_widget.load)

    def initialize(self, screens):
        self.screens = screens
        self.screen_selection_widget.screens = screens
        self.screen_selection_widget.load()

    def exec(self):
        self.set_defaults()
        return super().exec()

    def set_defaults(self):
        """Restore the current plugin choices when setup is run again."""
        self.restart()
        self.has_run_wizard = self.settings.value('core/has run wizard')
        self.projector_check_box.setChecked(
            self.has_run_wizard and self.settings.value('projector/status') == PluginStatus.Active)
        self.remote_interface_check_box.setChecked(
            self.has_run_wizard and self.settings.value('remote_interface/status') == PluginStatus.Active)
        if self.has_run_wizard and self.plugin_manager is not None:
            self.songs_check_box.setChecked(self.plugin_manager.get_plugin_by_name('songs').is_active())
            self.bible_check_box.setChecked(self.plugin_manager.get_plugin_by_name('bibles').is_active())
            self.presentation_check_box.setChecked(
                self.plugin_manager.get_plugin_by_name('presentations').is_active())
            self.image_check_box.setChecked(self.plugin_manager.get_plugin_by_name('images').is_active())
            # temp fix for #677 when we have an error
            try:
                self.media_check_box.setChecked(self.plugin_manager.get_plugin_by_name('media').is_active())
            except Exception:
                self.media_check_box.setEnabled(False)
            self.custom_check_box.setChecked(self.plugin_manager.get_plugin_by_name('custom').is_active())
            self.song_usage_check_box.setChecked(self.plugin_manager.get_plugin_by_name('songusage').is_active())
            self.alert_check_box.setChecked(self.plugin_manager.get_plugin_by_name('alerts').is_active())
            self.obs_studio_check_box.setChecked(self.plugin_manager.get_plugin_by_name('obs_studio').is_active())

    def accept(self):
        """
        Called when the user clicks 'Finish'. Reimplement it to to save the plugin status

        :rtype: None
        """
        imported_settings = False
        if self.import_settings_page.file_edit.text():
            file_path = self.import_settings_page.file_edit.text()
            imported_settings = self.settings.import_settings(Path(file_path)) if Path(file_path).is_file() else False
            if not imported_settings:
                QtWidgets.QMessageBox.critical(
                    self, translate('OpenLP.FirstTimeWizard', 'Import settings'),
                    translate('OpenLP.FirstTimeWizard', 'Could not import the selected settings file. '
                              'Choose another file or clear the selection to continue.'))
                return

        if not imported_settings:
            self._set_plugin_status(self.songs_check_box, 'songs/status')
            self._set_plugin_status(self.bible_check_box, 'bibles/status')
            self._set_plugin_status(self.presentation_check_box, 'presentations/status')
            self._set_plugin_status(self.image_check_box, 'images/status')
            self._set_plugin_status(self.media_check_box, 'media/status')
            self._set_plugin_status(self.custom_check_box, 'custom/status')
            self._set_plugin_status(self.song_usage_check_box, 'songusage/status')
            self._set_plugin_status(self.alert_check_box, 'alerts/status')
            self._set_plugin_status(self.obs_studio_check_box, 'obs_studio/status')
            self._set_plugin_status(self.projector_check_box, 'projector/status')
            self._set_plugin_status(self.remote_interface_check_box, 'remote_interface/status')
            self.screen_selection_widget.save()
        Registry().remove_function('config_screen_changed', self.screen_selection_widget.load)
        super().accept()

    def reject(self):
        Registry().remove_function('config_screen_changed', self.screen_selection_widget.load)
        super().reject()

    def _set_plugin_status(self, field, tag):
        """
        Set the status of a plugin.
        """
        status = PluginStatus.Active if field.checkState() == QtCore.Qt.CheckState.Checked else PluginStatus.Inactive
        self.settings.setValue(tag, status)
