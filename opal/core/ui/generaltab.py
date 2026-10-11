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
The general tab of the configuration dialog.
"""
import logging
from pathlib import Path

from PySide6 import QtCore, QtGui
from opal.core.widgets import fluent as QtWidgets

from opal.core.common import get_images_filter
from opal.core.common.i18n import UiStrings, translate
from opal.core.common.registry import Registry
from opal.core.lib.settingstab import SettingsTab
from opal.core.ui import HideMode
from opal.core.ui.style import UiThemes
from opal.core.widgets.buttons import ColorButton
from opal.core.widgets.edits import PathEdit

log = logging.getLogger(__name__)


class GeneralTab(SettingsTab):
    """
    GeneralTab is the general settings tab in the settings dialog.
    """

    def __init__(self, parent):
        """
        Initialise the general settings tab
        """
        self.logo_background_color = '#ffffff'
        self.icon_path = ':/icon/opal-presenter-icon.svg'
        general_translated = translate('OpenLP.GeneralTab', 'General')
        super(GeneralTab, self).__init__(parent, 'Core', general_translated)

    def setup_ui(self):
        """
        Create the user interface for the general settings tab
        """
        self.setObjectName('GeneralTab')
        super(GeneralTab, self).setup_ui()
        # Application Startup
        self.startup_group_box = QtWidgets.QGroupBox(self.left_column)
        self.startup_group_box.setObjectName('startup_group_box')
        self.startup_layout = QtWidgets.QVBoxLayout(self.startup_group_box)
        self.startup_layout.setObjectName('startup_layout')
        self.auto_open_check_box = QtWidgets.QCheckBox(self.startup_group_box)
        self.auto_open_check_box.setObjectName('auto_open_check_box')
        self.startup_layout.addWidget(self.auto_open_check_box)
        self.check_for_updates_check_box = QtWidgets.QCheckBox(self.startup_group_box)
        self.check_for_updates_check_box.setObjectName('check_for_updates_check_box')
        self.startup_layout.addWidget(self.check_for_updates_check_box)
        self.check_for_remote_updates_check_box = QtWidgets.QCheckBox(self.startup_group_box)
        self.check_for_remote_updates_check_box.setObjectName('check_for_remote_updates_check_box')
        self.startup_layout.addWidget(self.check_for_remote_updates_check_box)
        self.left_layout.addWidget(self.startup_group_box)
        # Logo
        self.logo_group_box = QtWidgets.QGroupBox(self.left_column)
        self.logo_group_box.setObjectName('logo_group_box')
        self.logo_layout = QtWidgets.QFormLayout(self.logo_group_box)
        self.logo_layout.setObjectName('logo_layout')
        self.logo_file_label = QtWidgets.QLabel(self.logo_group_box)
        self.logo_file_label.setObjectName('logo_file_label')
        self.logo_file_path_edit = PathEdit(self.logo_group_box,
                                            default_path=Path(':/graphics/opal-presenter-background.png'))
        self.logo_layout.addRow(self.logo_file_label, self.logo_file_path_edit)
        self.logo_color_label = QtWidgets.QLabel(self.logo_group_box)
        self.logo_color_label.setObjectName('logo_color_label')
        self.logo_color_button = ColorButton(self.logo_group_box)
        self.logo_color_button.setObjectName('logo_color_button')
        self.logo_layout.addRow(self.logo_color_label, self.logo_color_button)
        self.logo_fit_label = QtWidgets.QLabel(self.logo_group_box)
        self.logo_fit_label.setObjectName('logo_fit_label')
        self.logo_fit_combo_box = QtWidgets.QComboBox(self.logo_group_box)
        self.logo_fit_combo_box.setObjectName('logo_fit_combo_box')
        self.logo_fit_combo_box.addItem('', userData='cover')
        self.logo_fit_combo_box.addItem('', userData='contain')
        self.logo_fit_combo_box.addItem('', userData='stretch')
        self.logo_fit_combo_box.addItem('', userData='repeat')
        self.logo_layout.addRow(self.logo_fit_label, self.logo_fit_combo_box)
        self.logo_hide_on_startup_check_box = QtWidgets.QCheckBox(self.logo_group_box)
        self.logo_hide_on_startup_check_box.setObjectName('logo_hide_on_startup_check_box')
        self.logo_layout.addRow(self.logo_hide_on_startup_check_box)
        self.left_layout.addWidget(self.logo_group_box)
        self.logo_color_button.colorChanged.connect(self.on_logo_background_color_changed)
        self.logo_file_path_edit.pathChanged.connect(self._on_logo_file_changed)
        # CCLI Details
        self.ccli_group_box = QtWidgets.QGroupBox(self.left_column)
        self.ccli_group_box.setObjectName('ccli_group_box')
        self.ccli_layout = QtWidgets.QFormLayout(self.ccli_group_box)
        self.ccli_layout.setObjectName('ccli_layout')
        self.number_label = QtWidgets.QLabel(self.ccli_group_box)
        self.number_label.setObjectName('number_label')
        self.number_edit = QtWidgets.QLineEdit(self.ccli_group_box)
        self.number_edit.setValidator(QtGui.QIntValidator())
        self.number_edit.setObjectName('number_edit')
        self.ccli_layout.addRow(self.number_label, self.number_edit)
        self.left_layout.addWidget(self.ccli_group_box)
        # Ui Settings
        self.ui_group_box = QtWidgets.QGroupBox(self.right_column)
        self.ui_group_box.setObjectName('ui_group_box')
        self.ui_layout = QtWidgets.QFormLayout(self.ui_group_box)
        self.ui_layout.setObjectName('ui_layout')
        self.recent_label = QtWidgets.QLabel(self.ui_group_box)
        self.recent_label.setObjectName('recent_label')
        self.recent_spin_box = QtWidgets.QSpinBox(self.ui_group_box)
        self.recent_spin_box.setObjectName('recent_spin_box')
        self.recent_spin_box.setMinimum(0)
        self.ui_layout.addRow(self.recent_label, self.recent_spin_box)
        self.hide_mouse_check_box = QtWidgets.QCheckBox(self.ui_group_box)
        self.hide_mouse_check_box.setObjectName('hide_mouse_check_box')
        self.ui_layout.addRow(self.hide_mouse_check_box)
        self.double_click_live_check_box = QtWidgets.QCheckBox(self.ui_group_box)
        self.double_click_live_check_box.setObjectName('double_click_live_check_box')
        self.ui_layout.addRow(self.double_click_live_check_box)
        self.single_click_preview_check_box = QtWidgets.QCheckBox(self.ui_group_box)
        self.single_click_preview_check_box.setObjectName('single_click_preview_check_box')
        self.ui_layout.addRow(self.single_click_preview_check_box)
        self.single_click_service_preview_check_box = QtWidgets.QCheckBox(self.ui_group_box)
        self.single_click_service_preview_check_box.setObjectName('single_click_service_preview_check_box')
        self.ui_layout.addRow(self.single_click_service_preview_check_box)
        self.expand_service_item_check_box = QtWidgets.QCheckBox(self.ui_group_box)
        self.expand_service_item_check_box.setObjectName('expand_service_item_check_box')
        self.ui_layout.addRow(self.expand_service_item_check_box)
        # Generate numeric values for combo box dynamically
        self.slide_no_in_footer_checkbox = QtWidgets.QCheckBox(self.ui_group_box)
        self.slide_no_in_footer_checkbox.setObjectName('SlideNumbersInFooter_check_box')
        self.ui_layout.addRow(self.slide_no_in_footer_checkbox)
        self.search_as_type_check_box = QtWidgets.QCheckBox(self.ui_group_box)
        self.search_as_type_check_box.setObjectName('SearchAsType_check_box')
        self.ui_layout.addRow(self.search_as_type_check_box)
        self.enable_auto_close_check_box = QtWidgets.QCheckBox(self.ui_group_box)
        self.enable_auto_close_check_box.setObjectName('enable_auto_close_check_box')
        self.ui_layout.addRow(self.enable_auto_close_check_box)
        self.ui_theme_style_label = QtWidgets.QLabel(self.ui_group_box)
        self.ui_theme_style_label.setObjectName('theme_style_label')
        self.ui_theme_style_combo_box = QtWidgets.QComboBox(self.ui_group_box)
        self.ui_theme_style_combo_box.addItems([''] * 3)
        self.ui_theme_style_combo_box.setObjectName('theme_style_combo_box')
        self.ui_layout.addRow(self.ui_theme_style_label)
        self.ui_layout.addRow(self.ui_theme_style_combo_box)
        self.right_layout.addWidget(self.ui_group_box)
        # Push everything in both columns to the top
        self.left_layout.addStretch()
        self.right_layout.addStretch()
        # Connect a few things
        self.search_as_type_check_box.stateChanged.connect(self.on_search_as_type_check_box_changed)

    def retranslate_ui(self):
        """
        Translate the general settings tab to the currently selected language
        """
        self.tab_title_visible = translate('OpenLP.GeneralTab', 'General')
        # Application Startup
        self.startup_group_box.setTitle(translate('OpenLP.GeneralTab', 'Application Startup'))
        self.auto_open_check_box.setText(translate('OpenLP.GeneralTab', 'Automatically open the previous service file'))
        # Logo
        self.logo_group_box.setTitle(translate('OpenLP.GeneralTab', 'Logo'))
        self.logo_color_label.setText(UiStrings().BackgroundColorColon)
        self.logo_file_label.setText(translate('OpenLP.GeneralTab', 'Logo file'))
        self.logo_fit_label.setText(translate('OpenLP.GeneralTab', 'Logo fit'))
        self.logo_fit_combo_box.setItemText(0, translate('OpenLP.GeneralTab', 'Zoom to fill (Cover)'))
        self.logo_fit_combo_box.setItemText(1, translate('OpenLP.GeneralTab', 'Zoom to fit (Contain)'))
        self.logo_fit_combo_box.setItemText(2, translate('OpenLP.GeneralTab', 'Stretch'))
        self.logo_fit_combo_box.setItemText(3, translate('OpenLP.GeneralTab', 'Tile'))
        self.logo_hide_on_startup_check_box.setText(translate('OpenLP.GeneralTab', 'Don\'t show logo on startup'))
        self.check_for_updates_check_box.setText(translate('OpenLP.GeneralTab', 'Check for updates to Opal Presenter'))
        self.check_for_remote_updates_check_box.setText(translate('OpenLP.GeneralTab',
                                                                  'Check for updates to Opal Presenter Remote UI'))
        # CCLI Details
        self.ccli_group_box.setTitle(translate('OpenLP.GeneralTab', 'CCLI Details'))
        self.number_label.setText(UiStrings().CCLINumberLabel)
        self.logo_file_path_edit.dialog_caption = translate('OpenLP.AdvancedTab', 'Select Logo File')
        self.logo_file_path_edit.dialog_caption = translate('OpenLP.AdvancedTab', 'Select Logo File')
        self.logo_file_path_edit.filters = '{text};;{names} (*)'.format(
            text=get_images_filter(), names=UiStrings().AllFiles)
        # UI Settings
        self.ui_group_box.setTitle(translate('OpenLP.AdvancedTab', 'UI Settings'))
        self.recent_label.setText(translate('OpenLP.AdvancedTab', 'Number of recent service files to display'))
        self.double_click_live_check_box.setText(translate('OpenLP.AdvancedTab',
                                                           'Double-click to send items straight to Live'))
        self.single_click_preview_check_box.setText(translate('OpenLP.AdvancedTab',
                                                              'Preview items when clicked in Library'))
        self.single_click_service_preview_check_box.setText(translate('OpenLP.AdvancedTab',
                                                                      'Preview items when clicked in Service'))
        self.expand_service_item_check_box.setText(translate('OpenLP.AdvancedTab',
                                                             'Expand new service items on creation'))
        self.enable_auto_close_check_box.setText(translate('OpenLP.AdvancedTab',
                                                           'Enable application exit confirmation'))
        self.slide_no_in_footer_checkbox.setText(translate('SongsPlugin.GeneralTab', 'Include slide number in footer'))
        self.search_as_type_check_box.setText(translate('SongsPlugin.GeneralTab', 'Enable search as you type'))
        self.ui_theme_style_label.setText(translate('OpenLP.AdvancedTab', 'Interface Theme (needs restart)'))
        theme_labels = (
            translate('OpenLP.GeneralTab', 'Auto'),
            translate('OpenLP.GeneralTab', 'Dark'),
            translate('OpenLP.GeneralTab', 'Light'))
        for index, label in enumerate(theme_labels):
            self.ui_theme_style_combo_box.setItemText(index, label)
        self.hide_mouse_check_box.setText(translate('OpenLP.AdvancedTab', 'Hide mouse cursor when over display window'))

    def load(self):
        """
        Load the settings to populate the form
        """
        self.number_edit.setText(self.settings.value('core/ccli number'))
        self.auto_open_check_box.setChecked(self.settings.value('core/auto open'))
        self.logo_background_color = self.settings.value('core/logo background color')
        self.logo_file_path_edit.path = self.settings.value('core/logo file')
        self.logo_hide_on_startup_check_box.setChecked(self.settings.value('core/logo hide on startup'))
        logo_fit = self.settings.value('core/logo fit')
        for i in range(self.logo_fit_combo_box.count()):
            if self.logo_fit_combo_box.itemData(i) == logo_fit:
                self.logo_fit_combo_box.setCurrentIndex(i)
                break
        self.logo_color_button.color = self.logo_background_color
        self._on_logo_file_changed(self.logo_file_path_edit.path)
        self.check_for_updates_check_box.setChecked(self.settings.value('core/update check'))
        self.check_for_remote_updates_check_box.setChecked(self.settings.value('api/update check'))
        # UI Settings
        # The max recent files value does not have an interface and so never
        # gets actually stored in the settings therefore the default value of
        # 20 will always be used.
        self.recent_spin_box.setMaximum(self.settings.value('advanced/max recent files'))
        self.recent_spin_box.setValue(self.settings.value('advanced/recent file count'))
        self.double_click_live_check_box.setChecked(self.settings.value('advanced/double click live'))
        self.single_click_preview_check_box.setChecked(self.settings.value('advanced/single click preview'))
        self.single_click_service_preview_check_box.setChecked(
            self.settings.value('advanced/single click service preview'))
        self.expand_service_item_check_box.setChecked(self.settings.value('advanced/expand service item'))
        self.enable_auto_close_check_box.setChecked(self.settings.value('advanced/enable exit confirmation'))
        ui_theme_index = GeneralTab.get_ui_theme_index(self.settings.value('advanced/ui_theme_name'))
        self.ui_theme_style_combo_box.setCurrentIndex(ui_theme_index)
        self.slide_no_in_footer_checkbox.setChecked(self.settings.value('advanced/slide numbers in footer'))
        self.hide_mouse_check_box.setChecked(self.settings.value('advanced/hide mouse'))
        self.is_search_as_you_type_enabled = self.settings.value('advanced/search as type')
        self.search_as_type_check_box.setChecked(self.is_search_as_you_type_enabled)

    @staticmethod
    def get_ui_theme_index(ui_theme):
        """Map stored colour settings to Auto, Dark or Light."""
        if ui_theme in (UiThemes.DefaultDark, UiThemes.QDarkStyle):
            return 1
        if ui_theme == UiThemes.DefaultLight:
            return 2
        return 0

    @staticmethod
    def get_ui_theme_name(index):
        """Return the colour scheme of a combined theme selection."""
        if index not in range(3):
            return UiThemes.Automatic
        return (UiThemes.Automatic, UiThemes.DefaultDark, UiThemes.DefaultLight)[index % 3]

    def save(self):
        """
        Save the settings from the form
        """
        self.settings.setValue('core/auto open', self.auto_open_check_box.isChecked())
        self.settings.setValue('core/logo background color', self.logo_background_color)
        self.settings.setValue('core/logo file', self.logo_file_path_edit.path)
        self.settings.setValue('core/logo hide on startup', self.logo_hide_on_startup_check_box.isChecked())
        self.settings.setValue('core/logo fit', self.logo_fit_combo_box.currentData())
        self.settings.setValue('core/update check', self.check_for_updates_check_box.isChecked())
        self.settings.setValue('api/update check', self.check_for_remote_updates_check_box.isChecked())
        self.settings.setValue('core/ccli number', self.number_edit.displayText())
        # UI Settings
        self.settings.setValue('advanced/recent file count', self.recent_spin_box.value())
        self.settings.setValue('advanced/double click live', self.double_click_live_check_box.isChecked())
        self.settings.setValue('advanced/single click preview', self.single_click_preview_check_box.isChecked())
        self.settings.setValue('advanced/single click service preview',
                               self.single_click_service_preview_check_box.isChecked())
        self.settings.setValue('advanced/expand service item', self.expand_service_item_check_box.isChecked())
        self.settings.setValue('advanced/slide numbers in footer', self.slide_no_in_footer_checkbox.isChecked())
        self.settings.setValue('advanced/enable exit confirmation', self.enable_auto_close_check_box.isChecked())
        self.settings.setValue('advanced/hide mouse', self.hide_mouse_check_box.isChecked())
        self.settings.setValue('advanced/search as type', self.is_search_as_you_type_enabled)
        theme_name = GeneralTab.get_ui_theme_name(self.ui_theme_style_combo_box.currentIndex())
        self.settings.setValue('advanced/ui_theme_name', theme_name)
        self.settings.setValue('advanced/interface style', 'modern')
        self.settings.sync()
        self.post_set_up()

    def post_set_up(self):
        """
        Apply settings after the tab has loaded
        """
        self.settings_form.register_post_process('slidecontroller_live_spin_delay')
        # If the live display is currently showing the logo, refresh it so the
        # new logo file / fit / colour takes effect immediately without a restart.
        QtCore.QTimer.singleShot(0, self._refresh_live_logo_if_active)

    def _refresh_live_logo_if_active(self):
        """
        Re-apply logo display settings to the live display if it is currently showing the logo screen.
        Called via a deferred timer so it runs after the settings dialog has closed.
        """
        live_controller = Registry().get('live_controller')
        if not live_controller:
            return
        hide_mode = getattr(live_controller, '_current_hide_mode', None)
        if hide_mode == HideMode.Logo:
            # Currently in logo hide mode - re-apply via display
            Registry().execute('live_display_hide', HideMode.Logo)
        elif hide_mode is None and getattr(live_controller, 'service_item', None) is None:
            # No service item loaded - still showing the startup logo screen
            display = getattr(live_controller, 'display', None)
            if display and hasattr(display, 'set_startup_screen'):
                display.set_startup_screen()

    def _on_logo_file_changed(self, path):
        """
        Enable or disable logo fit options that don't apply to SVG images.
        """
        is_svg = path is not None and str(path).lower().endswith('.svg')
        model = self.logo_fit_combo_box.model()
        for i in range(self.logo_fit_combo_box.count()):
            fit_value = self.logo_fit_combo_box.itemData(i)
            if fit_value in ('stretch', 'repeat'):
                flags = QtCore.Qt.ItemFlag.NoItemFlags if is_svg else (
                    QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
                model.item(i).setFlags(flags)
        # If the current selection is now disabled, fall back to 'cover'
        if is_svg and self.logo_fit_combo_box.currentData() in ('stretch', 'repeat'):
            for i in range(self.logo_fit_combo_box.count()):
                if self.logo_fit_combo_box.itemData(i) == 'cover':
                    self.logo_fit_combo_box.setCurrentIndex(i)
                    break

    def on_logo_background_color_changed(self, color):
        """
        Select the background color for logo.
        """
        self.logo_background_color = color

    def on_search_as_type_check_box_changed(self, check_state):
        self.is_search_as_you_type_enabled = (check_state == QtCore.Qt.CheckState.Checked)
        self.settings_form.register_post_process('songs_config_updated')
        self.settings_form.register_post_process('custom_config_updated')
