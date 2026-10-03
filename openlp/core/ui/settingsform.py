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
The :mod:`settingsform` provides a user interface for the OpenLP+ settings
"""
import logging

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.state import State
from openlp.core.api.tab import ApiTab
from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.common.registry import Registry
from openlp.core.lib import build_icon
from openlp.core.projectors.tab import ProjectorTab
from openlp.core.ui.advancedtab import AdvancedTab
from openlp.core.ui.generaltab import GeneralTab
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.servicetab import ServiceTab
from openlp.core.ui.screenstab import ScreensTab
from openlp.core.ui.themestab import ThemesTab
from openlp.core.ui.media.mediatab import MediaTab
from openlp.core.ui.settingsdialog import Ui_SettingsDialog
from openlp.core.ui.settingstooltips import apply_settings_tooltips


log = logging.getLogger(__name__)


class SettingsForm(QtWidgets.QDialog, Ui_SettingsDialog, RegistryProperties):
    """
    Provide the form to manipulate the settings for OpenLP+
    """
    SERVICE_COLOR_ICON_MAP = {
        'songs': ('music', ServiceTab.ICON_THEME_COLOR_SETTINGS['song']),
        'bibles': ('bible', ServiceTab.ICON_THEME_COLOR_SETTINGS['bible']),
        'presentations': ('presentation', ServiceTab.ICON_THEME_COLOR_SETTINGS['presentation']),
        'images': ('picture', ServiceTab.ICON_THEME_COLOR_SETTINGS['image']),
        'media': ('video', ServiceTab.ICON_THEME_COLOR_SETTINGS['media']),
        'custom': ('custom', ServiceTab.ICON_THEME_COLOR_SETTINGS['custom_slide'])
    }
    RESET_PRESERVED_KEYS = (
        'settings/version', 'core/application version', 'core/has run wizard',
        'advanced/data path', 'advanced/is portable'
    )

    def __init__(self, parent=None):
        """
        Initialise the settings form
        """
        Registry().register('settings_form', self)
        Registry().register_function('bootstrap_post_set_up', self.bootstrap_post_set_up)
        super(SettingsForm, self).__init__(parent,
                                           QtCore.Qt.WindowType.WindowSystemMenuHint |
                                           QtCore.Qt.WindowType.WindowTitleHint |
                                           QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.processes = []
        self.setup_ui(self)
        self.reset_defaults_button.clicked.connect(self.reset_to_defaults)
        self._settings_tabs_ordered = []
        self.setting_list_widget.currentRowChanged.connect(self.list_item_changed)
        self.general_tab = None
        self.service_tab = None
        self.themes_tab = None
        self.player_tab = None
        self.projector_tab = None
        self.advanced_tab = None
        self.api_tab = None

    def exec(self, starting_tab_name=None):
        """
        Execute the form
        """
        # load all the widgets
        self.setting_list_widget.blockSignals(True)
        self.setting_list_widget.clear()
        while self.content_tabs_layout.count():
            item = self.content_tabs_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        self._settings_tabs_ordered.clear()

        for tab_widget, is_visible in self._get_ordered_tabs():
            self.insert_tab(tab_widget, is_visible)

        self.setting_list_widget.blockSignals(False)
        starting_tab_row = 0
        for index in range(self.setting_list_widget.count()):
            item = self.setting_list_widget.item(index)
            if item.text() == starting_tab_name:
                starting_tab_row = index
                break
        self._set_minimum_dialog_size()
        self.setting_list_widget.setCurrentRow(starting_tab_row)
        return QtWidgets.QDialog.exec(self)

    def _get_ordered_tabs(self):
        """
        Return all settings tabs in display order:
        General first, all other tabs alphabetically, Advanced last.
        """
        tabs = [
            (self.general_tab, True),
            (self.service_tab, True),
            (self.advanced_tab, True),
            (self.screens_tab, True),
            (self.themes_tab, True),
            (self.player_tab, True),
            (self.projector_tab, True),
            (self.api_tab, True)
        ]
        for plugin in State().list_plugins():
            if plugin.settings_tab:
                tabs.append((plugin.settings_tab, plugin.is_active()))

        def sort_key(tab_entry):
            tab_widget, _ = tab_entry
            if tab_widget is self.general_tab:
                return 0, ''
            if tab_widget is self.advanced_tab:
                return 2, ''
            return 1, tab_widget.tab_title_visible.casefold()

        return sorted(tabs, key=sort_key)

    def _set_minimum_dialog_size(self):
        """
        Set a minimum dialog size using the dialog baseline, capped to the available viewport.
        """
        original_size = QtCore.QSize(1200, 700)
        required_width = original_size.width()
        required_height = original_size.height()
        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        if screen:
            available_size = screen.availableGeometry().size()
            required_width = min(required_width, available_size.width())
            required_height = min(required_height, available_size.height())
        minimum_size = QtCore.QSize(max(required_width, 0), max(required_height, 0))
        self.setMinimumSize(minimum_size)
        self.resize(max(self.width(), minimum_size.width()), max(self.height(), minimum_size.height()))

    def insert_tab(self, tab_widget, is_visible=True):
        """
        Add a tab to the form at a specific location

        :param tab_widget: The widget to add
        :param is_visible: If this tab should be visible
        """
        log.debug('Inserting {text} tab'.format(text=tab_widget.tab_title))
        self._settings_tabs_ordered.append(tab_widget)
        tab_widget.setParent(self.content_widget)
        tab_widget.hide()
        self._normalise_settings_tab_layout(tab_widget)
        if is_visible:
            list_item = QtWidgets.QListWidgetItem(self._build_settings_tab_icon(tab_widget),
                                                  tab_widget.tab_title_visible)
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, tab_widget.tab_title)
            self.setting_list_widget.addItem(list_item)
            tab_widget.load()
            try:
                apply_settings_tooltips(tab_widget)
            except Exception:
                log.exception('Could not add settings help icons for %s', tab_widget.tab_title)

    def _build_settings_tab_icon(self, tab_widget):
        """
        Build a settings tab list icon.

        Service item tabs use the user-configured Service theme colors. All other tabs keep their
        existing icons unchanged.
        """
        tab_key = str(tab_widget.tab_title).strip().lower()
        service_color_icon = self.SERVICE_COLOR_ICON_MAP.get(tab_key)
        if service_color_icon:
            icon_name, color_setting = service_color_icon
            color_value = self.settings.value(color_setting)
            if color_value:
                return UiIcons().get_icon_variant(icon_name, color=color_value)
        return build_icon(tab_widget.icon_path)

    @staticmethod
    def _normalise_settings_tab_layout(tab_widget):
        """
        Apply a minimum spacing baseline to nested settings layouts for better readability.
        """
        for group_box in tab_widget.findChildren(QtWidgets.QGroupBox):
            layout_attr = getattr(group_box, 'layout', None)
            group_layout = layout_attr() if callable(layout_attr) else layout_attr
            if group_layout is not None:
                margins = group_layout.contentsMargins()
                left, top, right, bottom = margins.left(), margins.top(), margins.right(), margins.bottom()
                if left == 0 and top == 0 and right == 0 and bottom == 0:
                    group_layout.setContentsMargins(12, 14, 12, 12)
                if group_layout.spacing() < 12:
                    group_layout.setSpacing(12)

        for form_layout in tab_widget.findChildren(QtWidgets.QFormLayout):
            if form_layout.horizontalSpacing() < 14:
                form_layout.setHorizontalSpacing(14)
            if form_layout.verticalSpacing() < 14:
                form_layout.setVerticalSpacing(14)
            form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        for box_layout in tab_widget.findChildren(QtWidgets.QBoxLayout):
            if box_layout.spacing() < 14:
                box_layout.setSpacing(14)
            group_box_count = 0
            for index in range(box_layout.count()):
                item = box_layout.itemAt(index)
                widget = item.widget() if item is not None else None
                if isinstance(widget, QtWidgets.QGroupBox):
                    group_box_count += 1
            if group_box_count >= 2 and box_layout.spacing() < 24:
                box_layout.setSpacing(24)

        for grid_layout in tab_widget.findChildren(QtWidgets.QGridLayout):
            if grid_layout.horizontalSpacing() < 14:
                grid_layout.setHorizontalSpacing(14)
            if grid_layout.verticalSpacing() < 14:
                grid_layout.setVerticalSpacing(14)

        minimum_input_height = 32

        for line_edit in tab_widget.findChildren(QtWidgets.QLineEdit):
            if line_edit.minimumHeight() < minimum_input_height:
                line_edit.setMinimumHeight(minimum_input_height)

        for combo_box in tab_widget.findChildren(QtWidgets.QComboBox):
            if combo_box.minimumHeight() < minimum_input_height:
                combo_box.setMinimumHeight(minimum_input_height)

        spin_boxes = (tab_widget.findChildren(QtWidgets.QAbstractSpinBox) +
                      tab_widget.findChildren(QtWidgets.QSpinBox) +
                      tab_widget.findChildren(QtWidgets.QTimeEdit))
        for abstract_spin_box in spin_boxes:
            if abstract_spin_box.minimumHeight() < minimum_input_height:
                abstract_spin_box.setMinimumHeight(minimum_input_height)

        for check_box in tab_widget.findChildren(QtWidgets.QCheckBox):
            if check_box.minimumHeight() < 24:
                check_box.setMinimumHeight(24)

        for radio_button in tab_widget.findChildren(QtWidgets.QRadioButton):
            if radio_button.minimumHeight() < 24:
                radio_button.setMinimumHeight(24)

    def reset_to_defaults(self):
        """Reset saved preferences while keeping the user's library location and setup state."""
        title = translate('OpenLP.SettingsForm', 'Reset preferences')
        warning = translate(
            'OpenLP.SettingsForm',
            'Reset preferences to their defaults? Your library data, its location, and enabled plugins will be kept. '
            'Restart OpenLP+ to apply the changes.')
        answer = QtWidgets.QMessageBox.warning(
            self, title, warning,
            QtWidgets.QMessageBox.StandardButton.Reset | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel)
        if answer != QtWidgets.QMessageBox.StandardButton.Reset:
            return

        if self.advanced_tab is not None:
            self.advanced_tab.cancel()
        # Plugin activation is part of the installation state. Clearing it hides plugin settings tabs
        # (including Songs) and disables their Library sections after the next restart.
        preserved_keys = set(self.RESET_PRESERVED_KEYS)
        preserved_keys.update(key for key in self.settings.allKeys() if key.endswith('/status'))
        preserved = {key: self.settings.value(key) for key in preserved_keys if self.settings.contains(key)}
        self.settings.clear()
        for key, value in preserved.items():
            self.settings.setValue(key, value)
        self.settings.sync()
        if self.settings.status() != QtCore.QSettings.Status.NoError:
            QtWidgets.QMessageBox.critical(
                self, title, translate('OpenLP.SettingsForm', 'The preferences could not be reset.'))
            return

        main_window = Registry().get('main_window')
        if main_window is not None:
            main_window.settings_replaced = True
        self.processes = []
        QtWidgets.QMessageBox.information(
            self, title, translate('OpenLP.SettingsForm', 'Preferences reset. Restart OpenLP+ to apply all changes.'))
        QtWidgets.QDialog.reject(self)

    def accept(self):
        """
        Process the form saving the settings
        """
        log.debug('Processing settings exit')
        theme_keys = ('advanced/interface style', 'advanced/ui_theme_name')
        previous_theme = tuple(self.settings.value(key) for key in theme_keys)
        # All tab widgets are registered even if the plugin is inactive,
        # but we don't add the item to the list on the side if the plugin is inactive,
        # so loop through the list items, and then find the tab for that item.
        for item_index in range(self.setting_list_widget.count()):
            # Get the list item
            list_item = self.setting_list_widget.item(item_index)
            if not list_item:
                continue
            # Now figure out if there's a tab for it, and save the tab.
            plugin_name = list_item.data(QtCore.Qt.ItemDataRole.UserRole)
            for tab_widget in self._settings_tabs_ordered:
                if tab_widget.tab_title == plugin_name:
                    tab_widget.save()
        # Now lets process all the post save handlers
        while self.processes:
            process = self.processes.pop(0)
            if process == 'theme_update_list':
                theme_manager = Registry().get('theme_manager')
                theme_names = theme_manager.get_theme_names() if theme_manager else []
                Registry().execute(process, theme_names)
            elif process == 'config_screen_changed':
                # Defer costly thumbnail regeneration until after the dialog has closed.
                QtCore.QTimer.singleShot(0, self._execute_deferred_config_screen_changed)
            else:
                Registry().execute(process)
        result = QtWidgets.QDialog.accept(self)
        if tuple(self.settings.value(key) for key in theme_keys) != previous_theme:
            QtWidgets.QMessageBox.information(
                self, translate('OpenLP.SettingsForm', 'Restart required'),
                translate('OpenLP.SettingsForm',
                          'Your interface theme has been saved. Restart OpenLP+ to apply it.'))
        return result

    def _execute_deferred_config_screen_changed(self):
        main_window = Registry().get('main_window')
        original_should_show_message = None
        try:
            if main_window is not None and hasattr(main_window, 'should_show_screen_change_message'):
                original_should_show_message = main_window.should_show_screen_change_message
                main_window.should_show_screen_change_message = False
            Registry().execute('config_screen_changed')
        finally:
            if main_window is not None and original_should_show_message is not None and \
                    hasattr(main_window, 'should_show_screen_change_message'):
                main_window.should_show_screen_change_message = original_should_show_message

    def reject(self):
        """
        Process the form saving the settings
        """
        self.processes = []
        # Same as accept(), we need to loop over the visible tabs, and skip the inactive ones
        for item_index in range(self.setting_list_widget.count()):
            # Get the list item
            list_item = self.setting_list_widget.item(item_index)
            if not list_item:
                continue
            # Now figure out if there's a tab for it, and save the tab.
            plugin_name = list_item.data(QtCore.Qt.ItemDataRole.UserRole)
            for tab_widget in self._settings_tabs_ordered:
                if tab_widget.tab_title == plugin_name:
                    tab_widget.cancel()
        return QtWidgets.QDialog.reject(self)

    def bootstrap_post_set_up(self):
        """
        Run any post-setup code for the tabs on the form
        """
        try:
            self.general_tab = GeneralTab(self)
            self.service_tab = ServiceTab(self)
            self.themes_tab = ThemesTab(self)
            self.projector_tab = ProjectorTab(self)
            self.advanced_tab = AdvancedTab(self)
            self.player_tab = MediaTab(self)
            self.api_tab = ApiTab(self)
            self.screens_tab = ScreensTab(self)
        except Exception as e:
            print(e)
        self.general_tab.post_set_up()
        self.themes_tab.post_set_up()
        self.advanced_tab.post_set_up()
        self.player_tab.post_set_up()
        self.api_tab.post_set_up()
        for plugin in State().list_plugins():
            if plugin.settings_tab:
                plugin.settings_tab.post_set_up()

    def list_item_changed(self, item_index):
        """
        A different settings tab is selected

        :param item_index: The index of the item that was selected
        """
        # Get the item we clicked on
        list_item = self.setting_list_widget.item(item_index)
        # Quick exit to the left if the item doesn't exist (maybe -1?)
        if not list_item:
            return
        for tab_widget in self._settings_tabs_ordered:
            # Check that the title of the tab (i.e. plugin name) is the same as the data in the list item
            if tab_widget.tab_title == list_item.data(QtCore.Qt.ItemDataRole.UserRole):
                # Make the matching tab visible (only one tab in the layout so size hint matches content)
                while self.content_tabs_layout.count():
                    item = self.content_tabs_layout.takeAt(0)
                    if item.widget():
                        item.widget().hide()
                tab_widget.tab_visited = True
                self.content_tabs_layout.addWidget(tab_widget, 0, QtCore.Qt.AlignmentFlag.AlignTop)
                tab_widget.show()
                tab_widget.tab_visible()

    def register_post_process(self, function):
        """
        Register for updates to be done on save removing duplicate functions

        :param function:  The function to be called
        """
        if function not in self.processes:
            self.processes.append(function)
