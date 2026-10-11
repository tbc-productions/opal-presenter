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
The UI widgets for the first time wizard.
"""
from pathlib import Path

from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.i18n import translate
from openlp.core.display.screens import ScreenList
from openlp.core.widgets.widgets import ScreenSelectionWidget
from openlp.core.ui.icons import UiIcons


class FirstTimePage:
    Welcome = 0
    Plugins = 1
    ScreenConfig = 2
    ImportSettings = 3


class ImportSettingsPage(QtWidgets.QWizardPage):
    """
    Optional library and settings imports from an existing installation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ImportSettingsPage')

    def setup_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)

        self.opal_source_layout = QtWidgets.QHBoxLayout()
        self.opal_source_combo = QtWidgets.QComboBox(self)
        self.opal_source_label = QtWidgets.QLabel(self)
        self.opal_source_label.setBuddy(self.opal_source_combo)
        self.opal_source_layout.addWidget(self.opal_source_label)
        self.opal_source_layout.addWidget(self.opal_source_combo, 1)
        self.layout.addLayout(self.opal_source_layout)

        self.opal_library_card = QtWidgets.Card(self)
        self.opal_library_card_layout = QtWidgets.QVBoxLayout(self.opal_library_card)
        self.opal_library_card_layout.setContentsMargins(16, 16, 16, 16)
        self.opal_library_card_layout.setSpacing(12)
        self.opal_library_radio = QtWidgets.QRadioButton(self.opal_library_card)
        self.opal_library_card_layout.addWidget(self.opal_library_radio)
        self.opal_library_layout = QtWidgets.QHBoxLayout()
        self.opal_library_edit = QtWidgets.QLineEdit(self)
        self.opal_library_edit.setClearButtonEnabled(True)
        self.opal_library_layout.addWidget(self.opal_library_edit, 1)
        self.opal_library_button = QtWidgets.QPushButton(self)
        self.opal_library_button.setIcon(UiIcons().open)
        self.opal_library_edit.setMinimumHeight(self.opal_library_button.sizeHint().height())
        self.opal_library_layout.addWidget(self.opal_library_button)
        self.opal_library_card_layout.addLayout(self.opal_library_layout)
        self.layout.addWidget(self.opal_library_card)

        self.opal_settings_card = QtWidgets.Card(self)
        self.opal_settings_card_layout = QtWidgets.QVBoxLayout(self.opal_settings_card)
        self.opal_settings_card_layout.setContentsMargins(16, 16, 16, 16)
        self.opal_settings_card_layout.setSpacing(12)
        self.opal_settings_radio = QtWidgets.QRadioButton(self.opal_settings_card)
        self.opal_settings_card_layout.addWidget(self.opal_settings_radio)
        self.file_layout = QtWidgets.QHBoxLayout()
        self.file_edit = QtWidgets.QLineEdit(self)
        self.file_edit.setClearButtonEnabled(True)
        self.file_edit.setObjectName('file_edit')
        self.file_layout.addWidget(self.file_edit, 1)

        self.browse_button = QtWidgets.QPushButton(self)
        self.browse_button.setObjectName('browse_button')
        self.browse_button.setIcon(UiIcons().open)
        self.file_edit.setMinimumHeight(self.browse_button.sizeHint().height())
        self.file_layout.addWidget(self.browse_button)

        self.opal_settings_card_layout.addLayout(self.file_layout)
        self.layout.addWidget(self.opal_settings_card)
        self.layout.addStretch()
        self.opal_import_group = QtWidgets.QButtonGroup(self)
        self.opal_import_group.addButton(self.opal_library_radio)
        self.opal_import_group.addButton(self.opal_settings_radio)
        self.opal_library_radio.setChecked(True)

        # Connect signals
        self.browse_button.clicked.connect(self.on_browse_clicked)
        self.file_edit.textChanged.connect(lambda _text: self.completeChanged.emit())
        self.opal_library_edit.textChanged.connect(lambda _text: self.completeChanged.emit())
        self.opal_library_button.clicked.connect(self.opal_browse_library)
        self.opal_source_combo.currentIndexChanged.connect(self.opal_update_source)
        self.opal_library_radio.toggled.connect(self.opal_update_source)
        self.opal_settings_radio.toggled.connect(self.opal_update_source)

    def retranslate_ui(self):
        self.setTitle(translate('Opal.FirstTimeWizard', 'Import existing data'))
        if not self.opal_source_combo.count():
            self.opal_source_combo.addItems([translate('Opal.FirstTimeWizard', 'None'), 'Opal Presenter', 'OpenLP'])
        self.opal_source_label.setText(translate('Opal.FirstTimeWizard', 'Import from'))
        self.opal_library_radio.setText(translate('Opal.FirstTimeWizard', 'Library'))
        self.opal_library_edit.setPlaceholderText(translate('Opal.FirstTimeWizard', 'Select a library folder'))
        self.opal_library_edit.setAccessibleName(translate('Opal.FirstTimeWizard', 'Library folder'))
        self.opal_library_button.setText(translate('Opal.FirstTimeWizard', 'Open…'))
        self.browse_button.setText(translate('OpenLP.FirstTimeWizard', 'Open…'))
        self.opal_settings_radio.setText(translate('Opal.FirstTimeWizard', 'Settings only'))
        self.file_edit.setPlaceholderText(translate('Opal.FirstTimeWizard', 'Select a settings backup'))
        self.file_edit.setAccessibleName(translate('Opal.FirstTimeWizard', 'Settings backup'))
        self.opal_update_source()

    def opal_update_source(self):
        opal_source = self.opal_source_combo.currentIndex()
        if opal_source == 2:
            self.opal_library_radio.setChecked(True)
        self.opal_library_card.setVisible(opal_source != 0)
        self.opal_settings_card.setVisible(opal_source == 1)
        self.opal_library_edit.setEnabled(opal_source != 0 and self.opal_library_radio.isChecked())
        self.opal_library_button.setEnabled(self.opal_library_edit.isEnabled())
        self.file_edit.setEnabled(opal_source == 1 and self.opal_settings_radio.isChecked())
        self.browse_button.setEnabled(self.file_edit.isEnabled())
        self.completeChanged.emit()

    def on_browse_clicked(self):
        from openlp.core.widgets.dialogs import FileDialog
        file_path, filter_used = FileDialog.getOpenFileName(
            self,
            translate('OpenLP.FirstTimeWizard', 'Import settings'),
            None,
            translate('OpenLP.FirstTimeWizard', 'Opal Presenter Settings (*.opal-settings *.conf *.zip)'))
        if file_path:
            self.file_edit.setText(str(file_path))

    def isComplete(self):
        if self.opal_source_combo.currentIndex() == 0:
            return True
        if self.opal_source_combo.currentIndex() == 1 and self.opal_settings_radio.isChecked():
            opal_path = self.file_edit.text().strip()
            return bool(opal_path) and Path(opal_path).is_file()
        opal_path = self.opal_library_edit.text().strip()
        return bool(opal_path) and Path(opal_path).is_dir()

    def opal_browse_library(self):
        from openlp.core.widgets.dialogs import FileDialog
        opal_path = FileDialog.getExistingDirectory(
            self, translate('Opal.FirstTimeWizard', 'Select the library data folder'))
        if opal_path:
            self.opal_library_edit.setText(str(opal_path))


class UiFirstTimeWizard:
    """Local first-time setup pages."""

    def setup_ui(self, first_time_wizard):
        first_time_wizard.setObjectName('first_time_wizard')
        first_time_wizard.setWindowIcon(UiIcons().main_icon)
        first_time_wizard.setModal(True)
        first_time_wizard.resize(760, 640)
        first_time_wizard.setOption(QtWidgets.QWizard.WizardOption.IndependentPages)
        self.welcome_page = QtWidgets.QWizardPage()
        self.welcome_layout = QtWidgets.QVBoxLayout(self.welcome_page)
        self.information_label = QtWidgets.QLabel(self.welcome_page)
        self.information_label.setFluentTypography(QtWidgets.fluentqt.FontRole.Body)
        self.information_label.setWordWrap(True)
        self.welcome_layout.addWidget(self.information_label)
        self.welcome_layout.addStretch()
        first_time_wizard.setPage(FirstTimePage.Welcome, self.welcome_page)
        # The plugins page
        self.plugin_page = QtWidgets.QWizardPage()
        self.plugin_page.setObjectName('plugin_page')
        self.plugin_layout = QtWidgets.QVBoxLayout(self.plugin_page)
        self.plugin_layout.setContentsMargins(0, 0, 0, 0)
        self.plugin_layout.setObjectName('plugin_layout')
        self.songs_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.songs_check_box.setChecked(True)
        self.songs_check_box.setObjectName('songs_check_box')
        self.plugin_layout.addWidget(self.songs_check_box)
        self.custom_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.custom_check_box.setChecked(True)
        self.custom_check_box.setObjectName('custom_check_box')
        self.plugin_layout.addWidget(self.custom_check_box)
        self.slide_designer_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.slide_designer_check_box.setChecked(True)
        self.slide_designer_check_box.setObjectName('slide_designer_check_box')
        self.plugin_layout.addWidget(self.slide_designer_check_box)
        self.bible_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.bible_check_box.setChecked(True)
        self.bible_check_box.setObjectName('bible_check_box')
        self.plugin_layout.addWidget(self.bible_check_box)
        self.image_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.image_check_box.setChecked(True)
        self.image_check_box.setObjectName('image_check_box')
        self.plugin_layout.addWidget(self.image_check_box)
        self.presentation_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.presentation_check_box.setChecked(True)
        self.presentation_check_box.setObjectName('presentation_check_box')
        self.plugin_layout.addWidget(self.presentation_check_box)
        self.media_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.media_check_box.setChecked(True)
        self.media_check_box.setObjectName('media_check_box')
        self.plugin_layout.addWidget(self.media_check_box)
        self.library_sync_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.library_sync_check_box.setChecked(True)
        self.library_sync_check_box.setObjectName('library_sync_check_box')
        self.plugin_layout.addWidget(self.library_sync_check_box)
        self.song_usage_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.song_usage_check_box.setChecked(False)
        self.song_usage_check_box.setObjectName('song_usage_check_box')
        self.plugin_layout.addWidget(self.song_usage_check_box)
        self.alert_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.alert_check_box.setChecked(False)
        self.alert_check_box.setObjectName('alert_check_box')
        self.plugin_layout.addWidget(self.alert_check_box)
        self.obs_studio_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.obs_studio_check_box.setChecked(False)
        self.obs_studio_check_box.setObjectName('obs_studio_check_box')
        self.plugin_layout.addWidget(self.obs_studio_check_box)
        self.projector_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.projector_check_box.setChecked(False)
        self.projector_check_box.setObjectName('projector_check_box')
        self.plugin_layout.addWidget(self.projector_check_box)
        self.remote_interface_check_box = QtWidgets.QCheckBox(self.plugin_page)
        self.remote_interface_check_box.setChecked(False)
        self.remote_interface_check_box.setObjectName('remote_interface_check_box')
        self.plugin_layout.addWidget(self.remote_interface_check_box)
        first_time_wizard.setPage(FirstTimePage.Plugins, self.plugin_page)
        self.screen_page = QtWidgets.QWizardPage()
        self.screen_page_layout = QtWidgets.QVBoxLayout(self.screen_page)
        self.screen_selection_widget = ScreenSelectionWidget(self.screen_page, ScreenList())
        self.screen_selection_widget.use_simple_view()
        self.screen_selection_widget.load()
        self.screen_page_layout.addWidget(self.screen_selection_widget)
        first_time_wizard.setPage(FirstTimePage.ScreenConfig, self.screen_page)
        self.import_settings_page = ImportSettingsPage(first_time_wizard)
        self.import_settings_page.setup_ui()
        first_time_wizard.setPage(FirstTimePage.ImportSettings, self.import_settings_page)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(translate('OpenLP.FirstTimeWizard', 'Set up Opal Presenter'))
        self.setButtonText(QtWidgets.QWizard.WizardButton.FinishButton,
                           translate('OpenLP.FirstTimeWizard', 'Finish setup'))
        self.welcome_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Welcome to Opal Presenter'))
        self.welcome_page.setSubTitle(translate('OpenLP.FirstTimeWizard', 'Set up your presentation workspace.'))
        self.information_label.setText(translate(
            'Opal.FirstTimeWizard', 'Thank you for installing Opal Presenter. Let\'s get you set up.\n\n'
            'You can import an existing Opal Presenter (or OpenLP) library during setup.'))
        self.plugin_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Choose your features'))
        self.plugin_page.setSubTitle(
            translate('OpenLP.FirstTimeWizard', 'You can change these choices in Settings later.'))
        self.screen_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Choose your display'))
        self.screen_page.setSubTitle(translate('OpenLP.FirstTimeWizard', 'Select the screen used for presentations.'))
        self.import_settings_page.retranslate_ui()
        self.songs_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Songs'))
        self.custom_check_box.setText(
            translate('OpenLP.FirstTimeWizard',
                      'Custom Slides – Easier to manage than songs and they have their own list of slides'))
        self.slide_designer_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Slide Designer'))
        self.bible_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Bibles – Import and show Bibles'))
        self.image_check_box.setText(translate('OpenLP.FirstTimeWizard',
                                               'Images – Show images or replace background with them'))
        self.presentation_check_box.setText(translate('OpenLP.FirstTimeWizard',
                                                      'Presentations – Show .ppt, .odp and .pdf files'))
        self.media_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Media – Playback of Audio and Video files'))
        self.library_sync_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Library Sync'))
        self.song_usage_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Song Usage Monitor'))
        self.alert_check_box.setText(translate('OpenLP.FirstTimeWizard',
                                               'Alerts – Display informative messages while showing other slides'))
        self.obs_studio_check_box.setText(
            translate('OpenLP.FirstTimeWizard', 'OBS Studio - Control scenes directly from Opal Presenter')
        )
        self.projector_check_box.setText(
            translate('OpenLP.FirstTimeWizard', 'Projector – Control network projectors using PJLink'))
        self.remote_interface_check_box.setText(
            translate('OpenLP.FirstTimeWizard', 'Remote Interface – Remote control, stage, live and chords views'))
        for check_box in (self.projector_check_box, self.remote_interface_check_box):
            check_box.setToolTip(translate(
                'OpenLP.FirstTimeWizard',
                'Changes made when re-running setup take effect after restarting Opal Presenter.'))
        for checkbox in self.plugin_page.findChildren(QtWidgets.QCheckBox):
            text = checkbox.text()
            checkbox.setToolTip(checkbox.toolTip() or text)
            checkbox.setText(text.split(' – ')[0].split(' - ')[0])
