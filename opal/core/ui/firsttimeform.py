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
import logging
import shutil
from pathlib import Path
from tempfile import mkdtemp

from PySide6 import QtCore
from opal.core.widgets import fluent as QtWidgets
from opal.core.common.applocation import AppLocation
from opal.core.common.i18n import translate
from opal.core.common.mixins import RegistryProperties
from opal.core.common.registry import Registry
from opal.core.lib.opal_libraryimport import copy_opal_library, copy_opal_library_file
from opal.core.lib.plugin import PluginStatus
from opal.core.ui.firsttimewizard import UiFirstTimeWizard
from opal.core.ui.presentationexportdialog import ExportProgressDialog, write_with_progress


opal_log = logging.getLogger(__name__)


class FirstTimeForm(QtWidgets.QWizard, UiFirstTimeWizard, RegistryProperties):
    """Configure Opal Presenter locally, without downloading upstream resources."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui(self)
        self.has_run_wizard = False
        self.opal_imported_library = None
        self.opal_settings_imported = False
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
        self.import_settings_page.opal_source_combo.setCurrentIndex(0)
        self.import_settings_page.opal_library_radio.setChecked(True)
        self.opal_imported_library = None
        self.opal_settings_imported = False
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
            self.slide_designer_check_box.setChecked(
                self.plugin_manager.get_plugin_by_name('slide_designer').is_active())
            self.library_sync_check_box.setChecked(self.plugin_manager.get_plugin_by_name('librarysync').is_active())
            self.song_usage_check_box.setChecked(self.plugin_manager.get_plugin_by_name('songusage').is_active())
            self.alert_check_box.setChecked(self.plugin_manager.get_plugin_by_name('alerts').is_active())
            self.obs_studio_check_box.setChecked(self.plugin_manager.get_plugin_by_name('obs_studio').is_active())

    def accept(self):
        """
        Called when the user clicks 'Finish'. Reimplement it to to save the plugin status

        :rtype: None
        """
        opal_page = self.import_settings_page
        if not opal_page.isComplete():
            opal_page.completeChanged.emit()
            return
        imported_settings = False
        opal_source = (self.import_settings_page.opal_library_edit.text().strip()
                       if opal_page.opal_source_combo.currentIndex() != 0 and
                       opal_page.opal_library_radio.isChecked() else '')
        if opal_source:
            opal_progress = ExportProgressDialog(self)
            opal_progress.setWindowTitle(translate('Opal.FirstTimeWizard', 'Import library'))
            opal_progress.setLabelText(translate('Opal.FirstTimeWizard', 'Copying and checking the library…'))
            opal_progress.show()

            def opal_copy(_progress):
                self.opal_imported_library = copy_opal_library(
                    Path(opal_source), AppLocation.get_directory(AppLocation.DataDir).parent)

            try:
                write_with_progress(opal_copy, opal_progress.update_progress)
            except Exception as opal_error:
                opal_log.exception('Could not import the library')
                opal_progress.finish()
                QtWidgets.QMessageBox.critical(
                    self, translate('Opal.FirstTimeWizard', 'Import library'),
                    translate('Opal.FirstTimeWizard', 'Could not import the library.\n\n{error}').format(
                        error=str(opal_error)))
                return
            opal_progress.finish()
        if opal_page.opal_source_combo.currentIndex() == 1 and opal_page.opal_settings_radio.isChecked() and \
                self.import_settings_page.file_edit.text().strip():
            file_path = self.import_settings_page.file_edit.text().strip()
            opal_settings_error = ''

            def opal_copy_settings_files(opal_values):
                nonlocal opal_settings_error
                opal_current_root = AppLocation.get_data_path()
                opal_current_root.mkdir(parents=True, exist_ok=True)
                opal_destination = Path(mkdtemp(prefix='opal-imported-files-', dir=opal_current_root))
                opal_source_root = Path(opal_values.get('advanced/data path') or
                                        Path(file_path).parent).resolve()
                opal_progress = ExportProgressDialog(self)
                opal_progress.setWindowTitle(translate('Opal.FirstTimeWizard', 'Import files'))
                opal_progress.setLabelText(translate('Opal.FirstTimeWizard', 'Copying linked files…'))
                opal_progress.show()

                def opal_copy(_progress):
                    for opal_key in ('media/media files', 'presentations/presentations files'):
                        if opal_key in opal_values:
                            opal_values[opal_key] = [copy_opal_library_file(
                                opal_path, opal_source_root, opal_destination) for opal_path in opal_values[opal_key]]
                    opal_logo = opal_values.get('core/logo file')
                    if isinstance(opal_logo, Path) and not str(opal_logo).startswith(':/'):
                        opal_values['core/logo file'] = copy_opal_library_file(
                            opal_logo, opal_source_root, opal_destination)
                try:
                    write_with_progress(opal_copy, opal_progress.update_progress)
                except Exception as opal_error:
                    opal_settings_error = str(opal_error)
                    shutil.rmtree(opal_destination)
                    raise
                finally:
                    opal_progress.finish()
                # Settings-only imports retain the current library.
                opal_values['advanced/data path'] = opal_current_root

            imported_settings = self.settings.import_settings(
                Path(file_path), opal_copy_library_files=opal_copy_settings_files) \
                if Path(file_path).is_file() else False
            if not imported_settings:
                QtWidgets.QMessageBox.critical(
                    self, translate('OpenLP.FirstTimeWizard', 'Import settings'),
                    opal_settings_error or translate('Opal.FirstTimeWizard', 'Could not import this settings backup. '
                                                     'Choose another file or clear the field.'))
                return

        # Choices made in this wizard take priority over the settings backup.
        self._set_plugin_status(self.songs_check_box, 'songs/status')
        self._set_plugin_status(self.bible_check_box, 'bibles/status')
        self._set_plugin_status(self.presentation_check_box, 'presentations/status')
        self._set_plugin_status(self.image_check_box, 'images/status')
        self._set_plugin_status(self.media_check_box, 'media/status')
        self._set_plugin_status(self.custom_check_box, 'custom/status')
        self._set_plugin_status(self.slide_designer_check_box, 'slide_designer/status')
        self._set_plugin_status(self.library_sync_check_box, 'librarysync/status')
        self._set_plugin_status(self.song_usage_check_box, 'songusage/status')
        self._set_plugin_status(self.alert_check_box, 'alerts/status')
        self._set_plugin_status(self.obs_studio_check_box, 'obs_studio/status')
        self._set_plugin_status(self.projector_check_box, 'projector/status')
        self._set_plugin_status(self.remote_interface_check_box, 'remote_interface/status')
        self.screen_selection_widget.save()
        if self.opal_imported_library and not self.has_run_wizard:
            self.settings.setValue('advanced/data path', self.opal_imported_library)
        self.opal_settings_imported = imported_settings
        if self.opal_imported_library or imported_settings:
            if self.opal_imported_library:
                opal_message = translate('Opal.FirstTimeWizard', 'Library copied successfully.')
            else:
                opal_message = translate('Opal.FirstTimeWizard', 'Settings copied successfully.')
            QtWidgets.QMessageBox.information(
                self, translate('Opal.FirstTimeWizard', 'Import complete'), opal_message)
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
