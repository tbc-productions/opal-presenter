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
The :mod:`advancedtab` provides an advanced settings facility.
"""
import logging
from pathlib import Path
from shutil import copy2

from PySide6 import QtCore, QtWidgets

from openlp.core.common import sha256_file_hash
from openlp.core.common.applocation import AppLocation
from openlp.core.common.i18n import UiStrings, translate
from openlp.core.common.path import create_paths
from openlp.core.lib.settingstab import SettingsTab
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets.edits import PathEdit
from openlp.core.widgets.enums import PathEditType
from openlp.core.widgets.widgets import ProxyWidget


log = logging.getLogger(__name__)


class AdvancedTab(SettingsTab):
    """
    The :class:`AdvancedTab` manages the advanced settings tab including the UI
    and the loading and saving of the displayed settings.
    """
    def __init__(self, parent):
        """
        Initialise the settings tab
        """
        self.data_exists = False
        self.icon_path = UiIcons().settings
        advanced_translated = translate('OpenLP.AdvancedTab', 'Advanced')
        super(AdvancedTab, self).__init__(parent, 'Advanced', advanced_translated)

    def setup_ui(self):
        """
        Configure the UI elements for the tab.
        """
        self.setObjectName('AdvancedTab')
        super(AdvancedTab, self).setup_ui()
        # Data Directory
        self.data_directory_group_box = QtWidgets.QGroupBox(self.left_column)
        self.data_directory_group_box.setObjectName('data_directory_group_box')
        self.data_directory_layout = QtWidgets.QFormLayout(self.data_directory_group_box)
        self.data_directory_layout.setObjectName('data_directory_layout')
        self.data_directory_new_label = QtWidgets.QLabel(self.data_directory_group_box)
        self.data_directory_new_label.setObjectName('data_directory_current_label')
        self.data_directory_path_edit = PathEdit(self.data_directory_group_box, path_type=PathEditType.Directories,
                                                 default_path=AppLocation.get_directory(AppLocation.DataDir))
        self.data_directory_layout.addRow(self.data_directory_new_label, self.data_directory_path_edit)
        self.new_data_directory_has_files_label = QtWidgets.QLabel(self.data_directory_group_box)
        self.new_data_directory_has_files_label.setObjectName('new_data_directory_has_files_label')
        self.new_data_directory_has_files_label.setWordWrap(True)
        self.data_directory_cancel_button = QtWidgets.QToolButton(self.data_directory_group_box)
        self.data_directory_cancel_button.setObjectName('data_directory_cancel_button')
        self.data_directory_cancel_button.setIcon(UiIcons().delete)
        self.data_directory_copy_check_layout = QtWidgets.QHBoxLayout()
        self.data_directory_copy_check_layout.setObjectName('data_directory_copy_check_layout')
        self.data_directory_copy_check_box = QtWidgets.QCheckBox(self.data_directory_group_box)
        self.data_directory_copy_check_box.setObjectName('data_directory_copy_check_box')
        self.data_directory_copy_check_layout.addWidget(self.data_directory_copy_check_box)
        self.data_directory_copy_check_layout.addStretch()
        self.data_directory_copy_check_layout.addWidget(self.data_directory_cancel_button)
        self.data_directory_protect_check_layout = QtWidgets.QHBoxLayout()
        self.data_directory_protect_check_layout.setObjectName('data_directory_copy_check_layout')
        self.data_directory_protect_check_box = QtWidgets.QCheckBox(self.data_directory_group_box)
        self.data_directory_protect_check_box.setObjectName('data_directory_protect_check_box')
        self.data_directory_protect_check_layout.addWidget(self.data_directory_protect_check_box)
        self.data_directory_layout.addRow(self.data_directory_copy_check_layout)
        self.data_directory_layout.addRow(self.data_directory_protect_check_layout)
        self.copy_library_files_check_layout = QtWidgets.QHBoxLayout()
        self.copy_library_files_check_layout.setObjectName('copy_library_files_check_layout')
        self.copy_library_files_check_box = QtWidgets.QCheckBox(self.data_directory_group_box)
        self.copy_library_files_check_box.setObjectName('copy_library_files_check_box')
        self.copy_library_files_check_layout.addWidget(self.copy_library_files_check_box)
        self.data_directory_layout.addRow(self.copy_library_files_check_layout)
        self.migrate_library_files_button_layout = QtWidgets.QHBoxLayout()
        self.migrate_library_files_button_layout.setObjectName('migrate_library_files_button_layout')
        self.migrate_library_files_button = QtWidgets.QPushButton(self.data_directory_group_box)
        self.migrate_library_files_button.setObjectName('migrate_library_files_button')
        self.migrate_library_files_button_layout.addWidget(self.migrate_library_files_button)
        self.migrate_library_files_button_layout.addStretch()
        self.data_directory_layout.addRow(self.migrate_library_files_button_layout)
        self.data_directory_layout.addRow(self.new_data_directory_has_files_label)
        self.left_layout.addWidget(self.data_directory_group_box)
        # Display Workarounds
        self.display_workaround_group_box = QtWidgets.QGroupBox(self.left_column)
        self.display_workaround_group_box.setObjectName('display_workaround_group_box')
        self.display_workaround_layout = QtWidgets.QVBoxLayout(self.display_workaround_group_box)
        self.display_workaround_layout.setObjectName('display_workaround_layout')
        self.ignore_aspect_ratio_check_box = QtWidgets.QCheckBox(self.display_workaround_group_box)
        self.ignore_aspect_ratio_check_box.setObjectName('ignore_aspect_ratio_check_box')
        self.display_workaround_layout.addWidget(self.ignore_aspect_ratio_check_box)
        self.x11_bypass_check_box = QtWidgets.QCheckBox(self.display_workaround_group_box)
        self.x11_bypass_check_box.setObjectName('x11_bypass_check_box')
        self.display_workaround_layout.addWidget(self.x11_bypass_check_box)
        self.alternate_rows_check_box = QtWidgets.QCheckBox(self.display_workaround_group_box)
        self.alternate_rows_check_box.setObjectName('alternate_rows_check_box')
        self.display_workaround_layout.addWidget(self.alternate_rows_check_box)
        self.allow_transparent_display_check_box = QtWidgets.QCheckBox(self.display_workaround_group_box)
        self.allow_transparent_display_check_box.setObjectName('allow_transparent_display_check_box')
        self.display_workaround_layout.addWidget(self.allow_transparent_display_check_box)
        self.prefer_windowed_capture_check_box = QtWidgets.QCheckBox(self.display_workaround_group_box)
        self.prefer_windowed_capture_check_box.setObjectName('prefer_windowed_capture_check_box')
        self.display_workaround_layout.addWidget(self.prefer_windowed_capture_check_box)
        self.left_layout.addWidget(self.display_workaround_group_box)
        # Proxies
        self.proxy_widget = ProxyWidget(self.right_column)
        self.right_layout.addWidget(self.proxy_widget)
        # After the last item on each side, add some spacing
        self.left_layout.addStretch()
        self.right_layout.addStretch()
        # Set up all the connections and things
        self.data_directory_path_edit.pathChanged.connect(self.on_data_directory_path_edit_path_changed)
        self.data_directory_cancel_button.clicked.connect(self.on_data_directory_cancel_button_clicked)
        self.data_directory_copy_check_box.toggled.connect(self.on_data_directory_copy_check_box_toggled)
        self.migrate_library_files_button.clicked.connect(self.on_migrate_library_files_button_clicked)

    def retranslate_ui(self):
        """
        Setup the interface translation strings.
        """
        self.tab_title_visible = UiStrings().Advanced
        self.data_directory_group_box.setTitle(translate('OpenLP.AdvancedTab', 'Data Location'))
        self.data_directory_new_label.setText(translate('OpenLP.AdvancedTab', 'Path:'))
        self.data_directory_cancel_button.setText(translate('OpenLP.AdvancedTab', 'Cancel'))
        self.data_directory_cancel_button.setToolTip(
            translate('OpenLP.AdvancedTab', 'Cancel OpenLP+ data directory location change.'))
        self.data_directory_copy_check_box.setText(translate('OpenLP.AdvancedTab', 'Copy data to new location.'))
        self.data_directory_copy_check_box.setToolTip(translate(
            'OpenLP.AdvancedTab', 'Copy the OpenLP+ data files to the new location.'))
        self.data_directory_protect_check_box.setText(translate(
            'OpenLP.AdvancedTab', 'Protect the data directory with a locking mechanism.'))
        self.data_directory_protect_check_box.setToolTip(translate(
            'OpenLP.AdvancedTab', 'Protect the data directory with a locking mechanism to avoid data corruption if '
                                  'multiple users access the data at the same time. Useful for instances shared via '
                                  'network. <strong>NOTE:</strong> This will only work if the network sharing is '
                                  'available when OpenLP+ is running.'))
        self.copy_library_files_check_box.setText(translate(
            'OpenLP.AdvancedTab', 'Copy library files to data folder.'))
        self.copy_library_files_check_box.setToolTip(translate(
            'OpenLP.AdvancedTab', 'Store Images, Media, and Presentations in the OpenLP+ data folder for reliability.'))
        self.migrate_library_files_button.setText(translate(
            'OpenLP.AdvancedTab', 'Migrate existing library files to data folder'))
        self.migrate_library_files_button.setToolTip(translate(
            'OpenLP.AdvancedTab', 'Copy existing Images, Media, and Presentations into OpenLP+-managed storage.'))
        self.new_data_directory_has_files_label.setText(
            translate('OpenLP.AdvancedTab', '<strong>WARNING:</strong> New data directory location contains '
                      'OpenLP+ data files.  These files WILL be replaced during a copy.'))
        self.display_workaround_group_box.setTitle(translate('OpenLP.AdvancedTab', 'Display Workarounds'))
        self.ignore_aspect_ratio_check_box.setText(translate('OpenLP.AdvancedTab', 'Ignore Aspect Ratio'))
        self.x11_bypass_check_box.setText(translate('OpenLP.AdvancedTab', 'Bypass X11 Window Manager'))
        self.alternate_rows_check_box.setText(translate('OpenLP.AdvancedTab', 'Use alternating row colours in lists'))
        self.allow_transparent_display_check_box.setText(
            translate('OpenLP.AdvancedTab', 'Disable display transparency'))
        self.prefer_windowed_capture_check_box.setText(
            translate('OpenLP.AdvancedTab', 'Prefer window capture instead of screen capture'))
        self.proxy_widget.retranslate_ui()

    def load(self):
        """
        Load settings from disk.
        """
        self.ignore_aspect_ratio_check_box.setChecked(self.settings.value('advanced/ignore aspect ratio'))
        self.x11_bypass_check_box.setChecked(self.settings.value('advanced/x11 bypass wm'))
        # Prevent the dialog displayed by the alternate_rows_check_box to display.
        self.alternate_rows_check_box.blockSignals(True)
        self.alternate_rows_check_box.setChecked(self.settings.value('advanced/alternate rows'))
        self.alternate_rows_check_box.blockSignals(False)
        self.allow_transparent_display_check_box.setChecked(self.settings.value('advanced/disable transparent display'))
        self.prefer_windowed_capture_check_box.setChecked(
            self.settings.value('advanced/prefer windowed screen capture'))
        self.data_directory_copy_check_box.hide()
        self.new_data_directory_has_files_label.hide()
        self.data_directory_cancel_button.hide()
        # Since data location can be changed, make sure the path is present.
        self.data_directory_path_edit.path = AppLocation.get_data_path()
        # Don't allow data directory move if running portable.
        if self.settings.value('advanced/is portable'):
            self.data_directory_new_label.hide()
            self.data_directory_path_edit.hide()
        self.data_directory_protect_check_box.setChecked(self.settings.value('advanced/protect data directory'))
        self.copy_library_files_check_box.setChecked(self.settings.value('advanced/copy library files to data folder'))

    def save(self):
        """
        Save settings to disk.
        """
        alternate_rows = self.settings.value('advanced/alternate rows')
        self.settings.setValue('advanced/disable transparent display',
                               self.allow_transparent_display_check_box.isChecked())
        self.settings.setValue('advanced/prefer windowed screen capture',
                               self.prefer_windowed_capture_check_box.isChecked())
        self.settings.setValue('advanced/ignore aspect ratio', self.ignore_aspect_ratio_check_box.isChecked())
        if self.x11_bypass_check_box.isChecked() != self.settings.value('advanced/x11 bypass wm'):
            self.settings.setValue('advanced/x11 bypass wm', self.x11_bypass_check_box.isChecked())
            self.settings_form.register_post_process('config_screen_changed')
        self.settings.setValue('advanced/alternate rows', self.alternate_rows_check_box.isChecked())
        if alternate_rows != self.alternate_rows_check_box.isChecked():
            self.settings_form.register_post_process('alternate_rows_changed')
        self.settings.setValue('advanced/protect data directory', self.data_directory_protect_check_box.isChecked())
        self.settings.setValue('advanced/copy library files to data folder',
                               self.copy_library_files_check_box.isChecked())
        self.proxy_widget.save()

    def cancel(self):
        """
        Dialogue was cancelled, remove any pending data path change.
        """
        self.on_data_directory_cancel_button_clicked()
        SettingsTab.cancel(self)

    def on_data_directory_path_edit_path_changed(self, new_path):
        """
        Handle the `editPathChanged` signal of the data_directory_path_edit

        :param pathlib.Path new_path: The new path
        :rtype: None
        """
        # Check if data already exists here.
        self.check_data_overwrite(new_path)
        # Make sure they want to change the data.
        if self.data_directory_copy_check_box.isChecked():
            warning_string = translate('OpenLP.AdvancedTab', 'Are you sure you want to change the '
                                                             'location of the OpenLP+ data directory to:\n\n{path}'
                                                             '\n\nExisting files in this directory could be '
                                                             'overwritten. The data directory will be changed when '
                                                             'OpenLP+ is closed.').format(path=new_path)
        else:
            warning_string = translate('OpenLP.AdvancedTab', 'Are you sure you want to change the '
                                                             'location of the OpenLP+ data directory to:\n\n{path}'
                                                             '\n\nThe data directory will be changed when OpenLP+ is '
                                                             'closed.').format(path=new_path)
        answer = QtWidgets.QMessageBox.question(self, translate('OpenLP.AdvancedTab', 'Confirm Data Directory Change'),
                                                warning_string, defaultButton=QtWidgets.QMessageBox.StandardButton.No)
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            self.data_directory_path_edit.path = AppLocation.get_data_path()
            self.new_data_directory_has_files_label.hide()
            return
        # Save the new location.
        self.main_window.new_data_path = new_path
        self.data_directory_cancel_button.show()

    def on_data_directory_copy_check_box_toggled(self):
        """
        Copy existing data when you change your data directory.
        """
        self.main_window.set_copy_data(self.data_directory_copy_check_box.isChecked())
        if self.data_exists:
            if self.data_directory_copy_check_box.isChecked():
                self.new_data_directory_has_files_label.show()
            else:
                self.new_data_directory_has_files_label.hide()

    def check_data_overwrite(self, data_path):
        """
        Check if there's already data in the target directory.

        :param pathlib.Path data_path: The target directory to check
        """
        if (data_path / 'songs').exists():
            self.data_exists = True
            # Check is they want to replace existing data.
            answer = QtWidgets.QMessageBox.warning(self,
                                                   translate('OpenLP.AdvancedTab', 'Overwrite Existing Data'),
                                                   translate('OpenLP.AdvancedTab',
                                                             'WARNING: \n\nThe location you have selected \n\n{path}'
                                                             '\n\nappears to contain OpenLP+ data files. '
                                                             'Do you wish to replace these files with the current data '
                                                             'files?').format(path=data_path),
                                                   QtWidgets.QMessageBox.StandardButton(
                                                       QtWidgets.QMessageBox.StandardButton.Yes |
                                                       QtWidgets.QMessageBox.StandardButton.No),
                                                   QtWidgets.QMessageBox.StandardButton.No)
            self.data_directory_copy_check_box.show()
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                self.data_directory_copy_check_box.setChecked(True)
                self.new_data_directory_has_files_label.show()
            else:
                self.data_directory_copy_check_box.setChecked(False)
                self.new_data_directory_has_files_label.hide()
        else:
            self.data_exists = False
            self.data_directory_copy_check_box.setChecked(True)
            self.new_data_directory_has_files_label.hide()

    def on_data_directory_cancel_button_clicked(self):
        """
        Cancel the data directory location change
        """
        self.data_directory_path_edit.path = AppLocation.get_data_path()
        self.data_directory_copy_check_box.setChecked(False)
        self.main_window.new_data_path = None
        self.main_window.set_copy_data(False)
        self.data_directory_copy_check_box.hide()
        self.data_directory_cancel_button.hide()
        self.new_data_directory_has_files_label.hide()

    @staticmethod
    def _is_path_in_directory(path: Path, directory: Path) -> bool:
        """
        Return True when ``path`` is inside ``directory``.
        """
        try:
            path.relative_to(directory)
            return True
        except ValueError:
            return False

    @staticmethod
    def _library_plugin_specs():
        """
        Return plugin/item mappings for folder-backed media libraries.
        """
        from openlp.plugins.images.lib.db import Item as ImageItem
        from openlp.plugins.media.lib.db import Item as MediaItem
        from openlp.plugins.presentations.lib.db import Item as PresentationItem
        return (
            ('images', ImageItem),
            ('media', MediaItem),
            ('presentations', PresentationItem)
        )

    def _collect_library_migration_candidates(self):
        """
        Collect candidate library entries from images/media/presentations.
        """
        candidates = []
        for plugin_name, item_class in self._library_plugin_specs():
            plugin = self.plugin_manager.get_plugin_by_name(plugin_name)
            manager = getattr(plugin, 'manager', None) if plugin else None
            if not manager:
                continue
            items = manager.get_all_objects(item_class)
            for item in items:
                if not item.file_path:
                    continue
                candidates.append((plugin_name, manager, item, Path(item.file_path)))
        return candidates

    def on_migrate_library_files_button_clicked(self):
        """
        Migrate existing external library files into OpenLP+-managed storage.
        """
        answer = QtWidgets.QMessageBox.question(
            self,
            translate('OpenLP.AdvancedTab', 'Migrate library files'),
            translate('OpenLP.AdvancedTab',
                      'Copy existing Image, Media, and Presentation files into the OpenLP+ data folder now?')
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        candidates = self._collect_library_migration_candidates()
        if not candidates:
            QtWidgets.QMessageBox.information(
                self,
                translate('OpenLP.AdvancedTab', 'Migrate library files'),
                translate('OpenLP.AdvancedTab', 'No library files were found to migrate.')
            )
            return
        progress_dialog = QtWidgets.QProgressDialog(
            translate('OpenLP.AdvancedTab', 'Migrating library files...'),
            translate('OpenLP.AdvancedTab', 'Cancel'),
            0,
            len(candidates),
            self
        )
        progress_dialog.setWindowTitle(translate('OpenLP.AdvancedTab', 'Migrate library files'))
        progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)
        progress_dialog.setMinimumWidth(520)
        progress_dialog.setFixedSize(progress_dialog.sizeHint())
        copied_count = 0
        skipped_count = 0
        failed_count = 0
        for index, (plugin_name, manager, item, source_path) in enumerate(candidates, start=1):
            if progress_dialog.wasCanceled():
                break
            display_name = source_path.name
            if len(display_name) > 64:
                display_name = '{prefix}...{suffix}'.format(prefix=display_name[:40], suffix=display_name[-21:])
            progress_dialog.setLabelText(
                translate('OpenLP.AdvancedTab', 'Migrating {plugin}: {name}').format(
                    plugin=plugin_name,
                    name=display_name
                )
            )
            QtWidgets.QApplication.processEvents()
            if not source_path.exists():
                skipped_count += 1
                progress_dialog.setValue(index)
                continue
            try:
                library_dir = AppLocation.get_section_data_path(plugin_name) / 'library'
                create_paths(library_dir)
                source_hash = sha256_file_hash(source_path)
                destination = library_dir / '{hash}{ext}'.format(hash=source_hash, ext=source_path.suffix)
                if self._is_path_in_directory(source_path.resolve(), library_dir.resolve()):
                    skipped_count += 1
                else:
                    if not destination.exists():
                        copy2(source_path, destination)
                    item.name = source_path.name
                    item.file_path = str(destination)
                    item.file_hash = source_hash
                    manager.save_object(item)
                    copied_count += 1
            except Exception:
                failed_count += 1
                log.exception('Failed to migrate library file %s for plugin %s', source_path, plugin_name)
            progress_dialog.setValue(index)
        progress_dialog.close()
        if progress_dialog.wasCanceled():
            status_text = translate('OpenLP.AdvancedTab', 'Migration cancelled.')
        else:
            status_text = translate('OpenLP.AdvancedTab', 'Migration complete.')
        QtWidgets.QMessageBox.information(
            self,
            translate('OpenLP.AdvancedTab', 'Migrate library files'),
            translate(
                'OpenLP.AdvancedTab',
                '{status}\n\nCopied: {copied}\nSkipped: {skipped}\nFailed: {failed}'
            ).format(
                status=status_text,
                copied=copied_count,
                skipped=skipped_count,
                failed=failed_count
            )
        )
