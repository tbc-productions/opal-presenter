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
    A page for importing settings from a backup file (.conf or .zip)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ImportSettingsPage')

    def setup_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)

        self.info_label = QtWidgets.QLabel(self)
        self.info_label.setWordWrap(True)
        self.info_label.setFluentTypography(QtWidgets.fluentqt.FontRole.Body)
        self.info_label.setObjectName('info_label')
        self.layout.addWidget(self.info_label)

        self.group_layout = QtWidgets.QFormLayout()

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

        self.file_label = QtWidgets.QLabel(self)
        self.file_label.setObjectName('file_label')
        self.file_label.setBuddy(self.file_edit)
        self.group_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.group_layout.addRow(self.file_label, self.file_layout)
        self.layout.addLayout(self.group_layout)
        self.layout.addStretch()

        # Connect signals
        self.browse_button.clicked.connect(self.on_browse_clicked)
        self.file_edit.textChanged.connect(lambda _text: self.completeChanged.emit())

        # Set initial states
        self.file_edit.setEnabled(True)
        self.browse_button.setEnabled(True)

    def retranslate_ui(self):
        self.setTitle(translate('OpenLP.FirstTimeWizard', 'Import Settings'))
        self.setSubTitle(translate('OpenLP.FirstTimeWizard', 'Import settings from a previous backup.'))
        self.info_label.setText(
            translate('OpenLP.FirstTimeWizard',
                      'If you have a previously exported settings file (.conf or .zip), you can select it now. '
                      'This will restore your configuration, including plugins, theme selections, '
                      'and other preferences.\n\n'
                      'Alternatively, you can leave this blank to configure OpenLP+ manually.'))
        self.browse_button.setText(translate('OpenLP.FirstTimeWizard', 'Open…'))
        self.file_label.setText(translate('OpenLP.FirstTimeWizard', 'Settings File:'))

    def on_browse_clicked(self):
        from openlp.core.widgets.dialogs import FileDialog
        file_path, filter_used = FileDialog.getOpenFileName(
            self,
            translate('OpenLP.FirstTimeWizard', 'Import settings'),
            None,
            translate('OpenLP.FirstTimeWizard', 'OpenLP+ Settings (*.conf *.zip)'))
        if file_path:
            self.file_edit.setText(str(file_path))

    def isComplete(self):
        # Optional, so always complete
        return True


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
        self.setWindowTitle(translate('OpenLP.FirstTimeWizard', 'Set up OpenLP+'))
        self.setButtonText(QtWidgets.QWizard.WizardButton.FinishButton,
                           translate('OpenLP.FirstTimeWizard', 'Finish setup'))
        self.welcome_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Welcome to OpenLP+'))
        self.welcome_page.setSubTitle(translate('OpenLP.FirstTimeWizard', 'Set up your presentation workspace.'))
        self.information_label.setText(translate(
            'OpenLP.FirstTimeWizard', 'Choose the features and display you want to use, or restore a settings backup. '
            'Songs, Bibles and themes can be imported from your own files after setup.\n\n'
            'OpenLP+ is an independent project and is not endorsed by OpenLP.'))
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
        self.bible_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Bibles – Import and show Bibles'))
        self.image_check_box.setText(translate('OpenLP.FirstTimeWizard',
                                               'Images – Show images or replace background with them'))
        self.presentation_check_box.setText(translate('OpenLP.FirstTimeWizard',
                                                      'Presentations – Show .ppt, .odp and .pdf files'))
        self.media_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Media – Playback of Audio and Video files'))
        self.song_usage_check_box.setText(translate('OpenLP.FirstTimeWizard', 'Song Usage Monitor'))
        self.alert_check_box.setText(translate('OpenLP.FirstTimeWizard',
                                               'Alerts – Display informative messages while showing other slides'))
        self.obs_studio_check_box.setText(
            translate('OpenLP.FirstTimeWizard', 'OBS Studio - Control scenes directly from OpenLP+')
        )
        self.projector_check_box.setText(
            translate('OpenLP.FirstTimeWizard', 'Projector – Control network projectors using PJLink'))
        self.remote_interface_check_box.setText(
            translate('OpenLP.FirstTimeWizard', 'Remote Interface – Remote control, stage, live and chords views'))
        for check_box in (self.projector_check_box, self.remote_interface_check_box):
            check_box.setToolTip(translate(
                'OpenLP.FirstTimeWizard', 'Changes made when re-running setup take effect after restarting OpenLP+.'))
        for checkbox in self.plugin_page.findChildren(QtWidgets.QCheckBox):
            text = checkbox.text()
            checkbox.setToolTip(checkbox.toolTip() or text)
            checkbox.setText(text.split(' – ')[0].split(' - ')[0])
