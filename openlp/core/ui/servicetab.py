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
The services tab of the configuration dialog.
"""
import logging
import re
from datetime import datetime, timedelta

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import SlideLimits
from openlp.core.common.i18n import UiStrings, format_time, translate
from openlp.core.ui.icons import UiIcons
from openlp.core.lib.settingstab import SettingsTab

log = logging.getLogger(__name__)


class ServiceTab(SettingsTab):
    """
    ServiceTab is the service settings tab in the settings dialog.
    """
    ICON_THEME_COLOR_SETTINGS = {
        'song': 'servicemanager/theme color song',
        'bible': 'servicemanager/theme color bible',
        'presentation': 'servicemanager/theme color presentation',
        'image': 'servicemanager/theme color image',
        'media': 'servicemanager/theme color media',
        'custom_slide': 'servicemanager/theme color custom slide'
    }

    ICON_THEME_COLOR_DEFAULTS = {
        'song': '#FBBF24',
        'bible': '#4ADE80',
        'presentation': '#C084FC',
        'image': '#60A5FA',
        'media': '#F87171',
        'custom_slide': '#14B8A6'
    }
    HEX_COLOR_REGEX = re.compile(r'^[0-9A-F]{6}$')

    def __init__(self, parent):
        """
        Initialise the service settings tab
        """
        # self.logo_background_color = '#ffffff'
        self.icon_path = UiIcons().live
        self.should_update_service_name_example = True
        service_translated = translate('OpenLP.ServiceTab', 'Service')
        super(ServiceTab, self).__init__(parent, 'Service', service_translated)

    def setup_ui(self):
        """
        Create the user interface for the service settings tab
        """
        self.setObjectName('ServiceTab')
        super(ServiceTab, self).setup_ui()
        # Default service name
        self.service_name_group_box = QtWidgets.QGroupBox(self.left_column)
        self.service_name_group_box.setObjectName('service_name_group_box')
        self.service_name_layout = QtWidgets.QFormLayout(self.service_name_group_box)
        self.service_name_check_box = QtWidgets.QCheckBox(self.service_name_group_box)
        self.service_name_check_box.setObjectName('service_name_check_box')
        self.service_name_layout.setObjectName('service_name_layout')
        self.service_name_layout.addRow(self.service_name_check_box)
        self.service_name_time_label = QtWidgets.QLabel(self.service_name_group_box)
        self.service_name_time_label.setObjectName('service_name_time_label')
        self.service_name_day = QtWidgets.QComboBox(self.service_name_group_box)
        self.service_name_day.addItems(['', '', '', '', '', '', '', ''])
        self.service_name_day.setObjectName('service_name_day')
        self.service_name_time = QtWidgets.QTimeEdit(self.service_name_group_box)
        self.service_name_time.setObjectName('service_name_time')
        self.service_name_time_layout = QtWidgets.QHBoxLayout()
        self.service_name_time_layout.setObjectName('service_name_time_layout')
        self.service_name_time_layout.addWidget(self.service_name_day)
        self.service_name_time_layout.addWidget(self.service_name_time)
        self.service_name_layout.addRow(self.service_name_time_label, self.service_name_time_layout)
        self.service_name_label = QtWidgets.QLabel(self.service_name_group_box)
        self.service_name_label.setObjectName('service_name_label')
        self.service_name_edit = QtWidgets.QLineEdit(self.service_name_group_box)
        self.service_name_edit.setObjectName('service_name_edit')
        self.service_name_edit.setValidator(
            QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(r'[^/\\?*|<>\[\]":+]+'), self))
        self.service_name_revert_button = QtWidgets.QToolButton(self.service_name_group_box)
        self.service_name_revert_button.setObjectName('service_name_revert_button')
        self.service_name_revert_button.setIcon(UiIcons().undo)
        self.service_name_button_layout = QtWidgets.QHBoxLayout()
        self.service_name_button_layout.setObjectName('service_name_button_layout')
        self.service_name_button_layout.addWidget(self.service_name_edit)
        self.service_name_button_layout.addWidget(self.service_name_revert_button)
        self.service_name_layout.addRow(self.service_name_label, self.service_name_button_layout)
        self.service_name_example_label = QtWidgets.QLabel(self.service_name_group_box)
        self.service_name_example_label.setObjectName('service_name_example_label')
        self.service_name_example = QtWidgets.QLabel(self.service_name_group_box)
        self.service_name_example.setObjectName('service_name_example')
        self.service_name_layout.addRow(self.service_name_example_label, self.service_name_example)
        self.left_layout.addWidget(self.service_name_group_box)
        # Slide Controller
        self.slide_controller_groupbox = QtWidgets.QGroupBox(self.left_column)
        self.slide_controller_groupbox.setObjectName('slide_controller_groupbox')
        self.slide_controller_layout = QtWidgets.QFormLayout(self.slide_controller_groupbox)
        self.slide_controller_layout.setObjectName('slide_controller_layout')
        self.auto_unblank_check_box = QtWidgets.QCheckBox(self.slide_controller_groupbox)
        self.auto_unblank_check_box.setObjectName('auto_unblank_check_box')
        self.slide_controller_layout.addRow(self.auto_unblank_check_box)
        self.click_live_slide_to_unblank_check_box = QtWidgets.QCheckBox(self.slide_controller_groupbox)
        self.click_live_slide_to_unblank_check_box.setObjectName('click_live_slide_to_unblank')
        self.slide_controller_layout.addRow(self.click_live_slide_to_unblank_check_box)
        self.auto_preview_check_box = QtWidgets.QCheckBox(self.slide_controller_groupbox)
        self.auto_preview_check_box.setObjectName('auto_preview_check_box')
        self.slide_controller_layout.addRow(self.auto_preview_check_box)
        self.live_preview_shows_presentation_screen_check_box = QtWidgets.QCheckBox(self.slide_controller_groupbox)
        self.live_preview_shows_presentation_screen_check_box.setObjectName(
            'live_preview_shows_presentation_screen_check_box'
        )
        self.slide_controller_layout.addRow(self.live_preview_shows_presentation_screen_check_box)
        self.timeout_label = QtWidgets.QLabel(self.slide_controller_groupbox)
        self.timeout_label.setObjectName('timeout_label')
        self.timeout_spin_box = QtWidgets.QSpinBox(self.slide_controller_groupbox)
        self.timeout_spin_box.setObjectName('timeout_spin_box')
        self.timeout_spin_box.setRange(1, 180)
        self.slide_controller_layout.addRow(self.timeout_label, self.timeout_spin_box)
        self.left_layout.addWidget(self.slide_controller_groupbox)
        # Service Item Wrapping
        self.slide_group_box = QtWidgets.QGroupBox(self.right_column)
        self.slide_group_box.setObjectName('slide_group_box')
        self.slide_layout = QtWidgets.QVBoxLayout(self.slide_group_box)
        self.slide_layout.setObjectName('slide_layout')
        self.slide_label = QtWidgets.QLabel(self.slide_group_box)
        self.slide_label.setWordWrap(True)
        self.slide_layout.addWidget(self.slide_label)
        self.end_slide_radio_button = QtWidgets.QRadioButton(self.slide_group_box)
        self.end_slide_radio_button.setObjectName('end_slide_radio_button')
        self.slide_layout.addWidget(self.end_slide_radio_button)
        self.wrap_slide_radio_button = QtWidgets.QRadioButton(self.slide_group_box)
        self.wrap_slide_radio_button.setObjectName('wrap_slide_radio_button')
        self.slide_layout.addWidget(self.wrap_slide_radio_button)
        self.next_item_radio_button = QtWidgets.QRadioButton(self.slide_group_box)
        self.next_item_radio_button.setObjectName('next_item_radio_button')
        self.slide_layout.addWidget(self.next_item_radio_button)
        self.right_layout.addWidget(self.slide_group_box)
        # Service Editing
        self.service_editing_groupbox = QtWidgets.QGroupBox(self.left_column)
        self.service_editing_groupbox.setObjectName('service_editing_groupbox')
        self.service_editing_layout = QtWidgets.QFormLayout(self.service_editing_groupbox)
        self.service_editing_layout.setObjectName('service_editing_layout')
        self.service_editing_check_box = QtWidgets.QCheckBox(self.service_editing_groupbox)
        self.service_editing_check_box.setObjectName('service_editing_check_box')
        self.service_editing_layout.addRow(self.service_editing_check_box)
        self.right_layout.addWidget(self.service_editing_groupbox)
        # Theme
        self.theme_group_box = QtWidgets.QGroupBox(self.right_column)
        self.theme_group_box.setObjectName('theme_group_box')
        self.theme_layout = QtWidgets.QFormLayout(self.theme_group_box)
        self.theme_layout.setObjectName('theme_layout')
        self.icon_theme_colors = self.ICON_THEME_COLOR_DEFAULTS.copy()
        self.icon_theme_color_edits = {}
        self.icon_theme_color_buttons = {}
        self.theme_song_label = QtWidgets.QLabel(self.theme_group_box)
        self.theme_song_label.setObjectName('theme_song_label')
        self.theme_bible_label = QtWidgets.QLabel(self.theme_group_box)
        self.theme_bible_label.setObjectName('theme_bible_label')
        self.theme_presentation_label = QtWidgets.QLabel(self.theme_group_box)
        self.theme_presentation_label.setObjectName('theme_presentation_label')
        self.theme_image_label = QtWidgets.QLabel(self.theme_group_box)
        self.theme_image_label.setObjectName('theme_image_label')
        self.theme_media_label = QtWidgets.QLabel(self.theme_group_box)
        self.theme_media_label.setObjectName('theme_media_label')
        self.theme_custom_slide_label = QtWidgets.QLabel(self.theme_group_box)
        self.theme_custom_slide_label.setObjectName('theme_custom_slide_label')
        self._add_theme_color_row('song', self.theme_song_label)
        self._add_theme_color_row('bible', self.theme_bible_label)
        self._add_theme_color_row('presentation', self.theme_presentation_label)
        self._add_theme_color_row('image', self.theme_image_label)
        self._add_theme_color_row('media', self.theme_media_label)
        self._add_theme_color_row('custom_slide', self.theme_custom_slide_label)
        self.theme_defaults_row_widget = QtWidgets.QWidget(self.theme_group_box)
        self.theme_defaults_row_layout = QtWidgets.QHBoxLayout(self.theme_defaults_row_widget)
        self.theme_defaults_row_layout.setContentsMargins(0, 0, 0, 0)
        self.theme_defaults_button = QtWidgets.QPushButton(self.theme_group_box)
        self.theme_defaults_button.setObjectName('theme_defaults_button')
        self.theme_defaults_row_layout.addWidget(self.theme_defaults_button)
        self.theme_defaults_row_layout.addStretch()
        self.theme_layout.addRow(self.theme_defaults_row_widget)
        self.theme_defaults_button.clicked.connect(self.on_restore_theme_defaults_clicked)
        self.right_layout.addWidget(self.theme_group_box)
        # Push everything in both columns to the top
        self.left_layout.addStretch()
        self.right_layout.addStretch()
        # Connect signals and slots
        self.should_update_service_name_example = False
        # Default Service Name
        self.service_name_check_box.toggled.connect(self.service_name_check_box_toggled)
        self.service_name_day.currentIndexChanged.connect(self.on_service_name_day_changed)
        self.service_name_time.timeChanged.connect(self.update_service_name_example)
        self.service_name_edit.textChanged.connect(self.update_service_name_example)
        self.service_name_revert_button.clicked.connect(self.on_service_name_revert_button_clicked)
        # Service Item Wrapping
        self.end_slide_radio_button.clicked.connect(self.on_end_slide_button_clicked)
        self.wrap_slide_radio_button.clicked.connect(self.on_wrap_slide_button_clicked)
        self.next_item_radio_button.clicked.connect(self.on_next_item_button_clicked)

    def retranslate_ui(self):
        """
        Translate the service settings tab to the currently selected language
        """
        self.tab_title_visible = translate('OpenLP.ServiceTab', 'Service')
        # Default Service Name
        self.service_name_group_box.setTitle(translate('OpenLP.ServiceTab', 'Default Service Name'))
        self.service_name_check_box.setText(translate('OpenLP.ServiceTab', 'Enable default service name'))
        self.service_name_time_label.setText(translate('OpenLP.ServiceTab', 'Date and Time:'))
        self.service_name_day.setItemText(0, translate('OpenLP.ServiceTab', 'Monday'))
        self.service_name_day.setItemText(1, translate('OpenLP.ServiceTab', 'Tuesday'))
        self.service_name_day.setItemText(2, translate('OpenLP.ServiceTab', 'Wednesday'))
        self.service_name_day.setItemText(3, translate('OpenLP.ServiceTab', 'Thursday'))
        self.service_name_day.setItemText(4, translate('OpenLP.ServiceTab', 'Friday'))
        self.service_name_day.setItemText(5, translate('OpenLP.ServiceTab', 'Saturday'))
        self.service_name_day.setItemText(6, translate('OpenLP.ServiceTab', 'Sunday'))
        self.service_name_day.setItemText(7, translate('OpenLP.ServiceTab', 'Now'))
        self.service_name_time.setToolTip(translate('OpenLP.ServiceTab', 'Time service usually starts.'))
        self.service_name_label.setText(translate('OpenLP.ServiceTab', 'Name:'))
        self.service_name_edit.setToolTip(translate('OpenLP.ServiceTab',
                                                  'Use date and time codes to build a suggested service filename.'))
        self.service_name_revert_button.setToolTip(
            translate('OpenLP.ServiceTab',
                      'Revert to the default service name "{name}".').format(name=UiStrings().DefaultServiceName))
        self.service_name_example_label.setText(translate('OpenLP.ServiceTab', 'Example:'))
        # Slide Controller
        self.slide_controller_groupbox.setTitle(translate('OpenLP.ServiceTab', 'Slide Controller'))
        self.click_live_slide_to_unblank_check_box.setText(translate('OpenLP.ServiceTab',
                                                           'Unblank display when changing slide in Live'))
        self.auto_unblank_check_box.setText(translate('OpenLP.ServiceTab', 'Unblank display when sending '
                                                                           'items to Live'))
        self.auto_preview_check_box.setText(translate('OpenLP.ServiceTab',
                                                      'Automatically preview the next item in service'))
        self.live_preview_shows_presentation_screen_check_box.setText(
            UiStrings().LivePreviewShowsPresentationScreen
        )
        self.timeout_label.setText(translate('OpenLP.ServiceTab', 'Timed slide interval:'))
        self.timeout_spin_box.setSuffix(translate('OpenLP.ServiceTab', ' sec'))
        # Service Item Wrapping
        self.slide_group_box.setTitle(translate('OpenLP.ServiceTab', 'Service Item Wrapping'))
        self.slide_label.setText(translate('OpenLP.ServiceTab', 'Behavior of next/previous on the last/first slide:'))
        self.end_slide_radio_button.setText(translate('OpenLP.ServiceTab', '&Remain on Slide'))
        self.wrap_slide_radio_button.setText(translate('OpenLP.ServiceTab', '&Wrap around'))
        self.next_item_radio_button.setText(translate('OpenLP.ServiceTab', '&Move to next/previous service item'))
        # Service Editing
        self.service_editing_groupbox.setTitle(translate('OpenLP.ServiceTab', 'Service Editing'))
        self.service_editing_check_box.setText(translate('OpenLP.ServiceTab', 'Show confirmation box when deleting '
                                                                              'item from service'))
        # Theme
        self.theme_group_box.setTitle(translate('OpenLP.ServiceTab', 'Theme'))
        self.theme_song_label.setText(translate('OpenLP.ServiceTab', 'Song:'))
        self.theme_bible_label.setText(translate('OpenLP.ServiceTab', 'Bible:'))
        self.theme_presentation_label.setText(translate('OpenLP.ServiceTab', 'Presentation:'))
        self.theme_image_label.setText(translate('OpenLP.ServiceTab', 'Image:'))
        self.theme_media_label.setText(translate('OpenLP.ServiceTab', 'Media:'))
        self.theme_custom_slide_label.setText(translate('OpenLP.ServiceTab', 'Custom Slide:'))
        self.theme_defaults_button.setText(translate('OpenLP.ServiceTab', 'Restore Defaults'))

    def load(self):
        """
        Load the settings to populate the form
        """
        # Default Service Name
        self.service_name_day.setCurrentIndex(self.settings.value('advanced/default service day'))
        self.service_name_time.setTime(QtCore.QTime(self.settings.value('advanced/default service hour'),
                                                    self.settings.value('advanced/default service minute')))
        self.should_update_service_name_example = True
        self.service_name_edit.setText(self.settings.value('advanced/default service name'))
        default_service_enabled = self.settings.value('advanced/default service enabled')
        self.service_name_check_box.setChecked(default_service_enabled)
        self.service_name_check_box_toggled(default_service_enabled)
        # Slide Controller
        self.auto_unblank_check_box.setChecked(self.settings.value('core/auto unblank'))
        self.click_live_slide_to_unblank_check_box.setChecked(self.settings.value('core/click live slide to unblank'))
        self.auto_preview_check_box.setChecked(self.settings.value('core/auto preview'))
        self.live_preview_shows_presentation_screen_check_box.setChecked(
            self.settings.value('core/live preview shows presentation screen')
        )
        self.timeout_spin_box.setValue(self.settings.value('core/loop delay'))
        # Service Item Wrapping
        self.slide_limits = self.settings.value('advanced/slide limits')
        if self.slide_limits == SlideLimits.End:
            self.end_slide_radio_button.setChecked(True)
        elif self.slide_limits == SlideLimits.Wrap:
            self.wrap_slide_radio_button.setChecked(True)
        else:
            self.next_item_radio_button.setChecked(True)
        # Service Editing
        self.service_editing_check_box.setChecked(self.settings.value('advanced/delete service item confirmation'))
        # Theme colors
        for key, setting_key in self.ICON_THEME_COLOR_SETTINGS.items():
            default = self.ICON_THEME_COLOR_DEFAULTS[key]
            color_value = self._normalise_color(self.settings.value(setting_key), default)
            self.icon_theme_colors[key] = color_value
            self.icon_theme_color_edits[key].setText(color_value)
            self._update_theme_color_picker_preview(key)

    def save(self):
        """
        Save the settings from the form
        """
        # Default Service Name
        self.settings.setValue('advanced/default service enabled', self.service_name_check_box.isChecked())
        service_name = self.service_name_edit.text()
        preset_is_valid = self.generate_service_name_example()[0]
        if service_name == UiStrings().DefaultServiceName or not preset_is_valid:
            self.settings.remove('advanced/default service name')
            self.service_name_edit.setText(service_name)
        else:
            self.settings.setValue('advanced/default service name', service_name)
        self.settings.setValue('advanced/default service day', self.service_name_day.currentIndex())
        self.settings.setValue('advanced/default service hour', self.service_name_time.time().hour())
        self.settings.setValue('advanced/default service minute', self.service_name_time.time().minute())
        # Slide Controller
        self.settings.setValue('core/auto unblank', self.auto_unblank_check_box.isChecked())
        self.settings.setValue('core/click live slide to unblank',
                               self.click_live_slide_to_unblank_check_box.isChecked())
        self.settings.setValue('core/auto preview', self.auto_preview_check_box.isChecked())
        self.settings.setValue('core/live preview shows presentation screen',
                               self.live_preview_shows_presentation_screen_check_box.isChecked())
        self.settings.setValue('core/loop delay', self.timeout_spin_box.value())
        # Service Item Wrapping
        self.settings.setValue('advanced/slide limits', self.slide_limits)
        self.settings_form.register_post_process('slidecontroller_update_slide_limits')
        # Service Editing
        self.settings.setValue('advanced/delete service item confirmation', self.service_editing_check_box.isChecked())
        # Theme colors
        self._normalise_theme_color_edits()
        for key, setting_key in self.ICON_THEME_COLOR_SETTINGS.items():
            self.settings.setValue(setting_key, self.icon_theme_colors[key])
        self.settings_form.register_post_process('service_manager_repaint_list_icons')
        self.settings_form.register_post_process('media_dock_refresh_icons')
        self.post_set_up()

    def _add_theme_color_row(self, color_key, label):
        """
        Add a theme color row consisting of a hex text box and color picker button.
        """
        edit = QtWidgets.QLineEdit(self.theme_group_box)
        edit.setObjectName('theme_{key}_color_edit'.format(key=color_key))
        edit.setPlaceholderText('#RRGGBB')
        edit.setMaxLength(7)
        picker_button = QtWidgets.QToolButton(self.theme_group_box)
        picker_button.setObjectName('theme_{key}_color_button'.format(key=color_key))
        picker_button.setText('...')
        row_widget = QtWidgets.QWidget(self.theme_group_box)
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(edit)
        row_layout.addWidget(picker_button)
        self.theme_layout.addRow(label, row_widget)
        self.icon_theme_color_edits[color_key] = edit
        self.icon_theme_color_buttons[color_key] = picker_button
        picker_button.clicked.connect(lambda checked=False, key=color_key: self.on_theme_color_pick_clicked(key))
        edit.editingFinished.connect(lambda key=color_key: self.on_theme_color_edit_finished(key))

    def _normalise_theme_color_edits(self):
        """
        Normalize all hex text edits and update button previews.
        """
        for key in self.icon_theme_color_edits:
            color_text = self._normalise_color(self.icon_theme_color_edits[key].text(), self.icon_theme_colors[key])
            self.icon_theme_colors[key] = color_text
            self.icon_theme_color_edits[key].setText(color_text)
            self._update_theme_color_picker_preview(key)

    def _update_theme_color_picker_preview(self, color_key):
        """
        Update picker button color preview for a theme row.
        """
        color_text = self.icon_theme_colors[color_key]
        self.icon_theme_color_buttons[color_key].setStyleSheet(
            'background-color: {color};'.format(color=color_text)
        )

    def on_theme_color_edit_finished(self, color_key):
        """
        Validate and normalize a theme color when typing finishes.
        """
        color_text = self._normalise_color(self.icon_theme_color_edits[color_key].text(), self.icon_theme_colors[color_key])
        self.icon_theme_colors[color_key] = color_text
        self.icon_theme_color_edits[color_key].setText(color_text)
        self._update_theme_color_picker_preview(color_key)

    def on_theme_color_pick_clicked(self, color_key):
        """
        Open the color picker and apply the selected theme color.
        """
        current_color = self._normalise_color(self.icon_theme_color_edits[color_key].text(), self.icon_theme_colors[color_key])
        picked_color = QtWidgets.QColorDialog.getColor(QtGui.QColor(current_color), self)
        if not picked_color.isValid():
            return
        color_text = self._normalise_color(picked_color.name().upper(), self.icon_theme_colors[color_key])
        self.icon_theme_colors[color_key] = color_text
        self.icon_theme_color_edits[color_key].setText(color_text)
        self._update_theme_color_picker_preview(color_key)

    def on_restore_theme_defaults_clicked(self):
        """
        Restore all service icon theme colors to defaults.
        """
        for key, default in self.ICON_THEME_COLOR_DEFAULTS.items():
            self.icon_theme_colors[key] = default
            self.icon_theme_color_edits[key].setText(default)
            self._update_theme_color_picker_preview(key)

    @staticmethod
    def _normalise_color(color_text, default):
        """
        Normalize text to #RRGGBB and fall back to the provided default when invalid.
        """
        color_text = str(color_text).strip().upper()
        if color_text.startswith('#'):
            color_text = color_text[1:]
        if not ServiceTab.HEX_COLOR_REGEX.match(color_text):
            return default
        return '#{text}'.format(text=color_text)

    def post_set_up(self):
        """
        Apply settings after the tab has loaded
        """
        self.settings_form.register_post_process('slidecontroller_live_spin_delay')

    def service_name_check_box_toggled(self, default_service_enabled):
        """
        Service Name options changed
        """
        self.service_name_day.setEnabled(default_service_enabled)
        time_enabled = default_service_enabled and self.service_name_day.currentIndex() != 7
        self.service_name_time.setEnabled(time_enabled)
        self.service_name_edit.setEnabled(default_service_enabled)
        self.service_name_revert_button.setEnabled(default_service_enabled)

    def generate_service_name_example(self):
        """
        Display an example of the template used
        """
        preset_is_valid = True
        if self.service_name_day.currentIndex() == 7:
            local_time = datetime.now()
        else:
            now = datetime.now()
            day_delta = self.service_name_day.currentIndex() - now.weekday()
            if day_delta < 0:
                day_delta += 7
            time = now + timedelta(days=day_delta)
            local_time = time.replace(
                hour=self.service_name_time.time().hour(),
                minute=self.service_name_time.time().minute()
            )
        try:
            service_name_example = format_time(self.service_name_edit.text(), local_time)
        except ValueError:
            preset_is_valid = False
            service_name_example = translate('OpenLP.ServiceTab', 'Syntax error.')
        return preset_is_valid, service_name_example

    def update_service_name_example(self, returned_value):
        """
        Update the example service name.
        """
        if not self.should_update_service_name_example:
            return
        name_example = self.generate_service_name_example()[1]
        self.service_name_example.setText(name_example)

    def on_service_name_day_changed(self, service_day):
        """
        React to the day of the service name changing.
        """
        self.service_name_time.setEnabled(service_day != 7)
        self.update_service_name_example(None)

    def on_service_name_revert_button_clicked(self):
        """
        Revert to the default service name.
        """
        self.service_name_edit.setText(UiStrings().DefaultServiceName)
        self.service_name_edit.setFocus()

    def on_end_slide_button_clicked(self):
        """
        Stop at the end either top ot bottom
        """
        self.slide_limits = SlideLimits.End

    def on_wrap_slide_button_clicked(self):
        """
        Wrap round the service item
        """
        self.slide_limits = SlideLimits.Wrap

    def on_next_item_button_clicked(self):
        """
        Advance to the next service item
        """
        self.slide_limits = SlideLimits.Next
