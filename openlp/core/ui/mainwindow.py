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
This is the main window, where all the action happens.
"""
import json
import shutil
import webbrowser
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from tempfile import gettempdir
from threading import Lock

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.api.http.server import HttpServer
from openlp.core.api.websockets import WebSocketServer
from openlp.core.common import add_actions
from openlp.core.common.actions import ActionList, CategoryOrder
from openlp.core.common.applocation import AppLocation
from openlp.core.common.i18n import LanguageManager, UiStrings, translate
from openlp.core.common.json import OpenLPJSONDecoder
from openlp.core.common.mixins import LogMixin, RegistryProperties
from openlp.core.common.path import create_paths, resolve
from openlp.core.common.platform import is_macosx, is_win
from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.core.display.screens import ScreenList
from openlp.core.lib.plugin import PluginStatus
from openlp.core.lib.ui import create_action
from openlp.core.projectors.manager import ProjectorManager
from openlp.core.state import State
from openlp.core.ui.aboutform import AboutForm
from openlp.core.ui.advanceddocking import AdvancedDockingMixin, AdvancedDockWidget
from openlp.core.ui.firsttimeform import FirstTimeForm
from openlp.core.ui.formattingtagform import FormattingTagForm
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.pluginform import PluginForm
from openlp.core.ui.printserviceform import PrintServiceForm
from openlp.core.ui.servicemanager import ServiceManager
from openlp.core.ui.settingsform import SettingsForm
from openlp.core.widgets.statusbar import FooterStatusBar
from openlp.core.ui.shortcutlistform import ShortcutListForm
from openlp.core.ui import HideMode
from openlp.core.ui.style import get_library_stylesheet
from openlp.core.ui.modernstyle import is_modern_style
from openlp.core.widgets.fluent_navigation import LayoutPresetNavigation
from openlp.core.ui.thememanager import ThemeManager
from openlp.core.version import get_version
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.docks import MediaDockManager, MediaToolBox, OpenLPDockWidget

# Layout preset ids (match ``core/view mode`` values) for per-preset saved window layout.
_PRESET_LAYOUT_MODES = ('default', 'setup', 'live')
_PRESET_VISIBILITY_SNAPSHOT_KEY = 'visibility snapshot'


def _preset_layout_storage_key(mode: str, fragment: str, modern=None) -> str:
    layout = 'modern preset layout' if (is_modern_style() if modern is None else modern) else 'preset layout'
    return 'user interface/{}/{}/{}'.format(layout, mode, fragment)


def _window_state_storage_key(modern=None) -> str:
    modern = is_modern_style() if modern is None else modern
    return 'user interface/modern window state' if modern else 'user interface/main window state'


def _set_dock_visible(dock, visible):
    if isinstance(dock, AdvancedDockWidget):
        dock.setDockVisible(visible)
    else:
        dock.setVisible(visible)


def _dock_is_visible(dock):
    return dock.isDockOpen() if isinstance(dock, AdvancedDockWidget) else dock.isVisible()


def _preset_layout_has_saved_state(settings: Settings, mode: str, modern=None) -> bool:
    st = settings.value(_preset_layout_storage_key(mode, 'main window state', modern))
    return bool(st and len(st) > 0)


class Ui_MainWindow(object):
    """
    This is the UI part of the main window.
    """
    def setup_ui(self, main_window):
        """
        Set up the user interface
        """
        main_window.setObjectName('MainWindow')
        self._modern_appearance = is_modern_style()
        if self._modern_appearance:
            main_window.setProperty('fluentUi', True)
        main_window.setWindowIcon(UiIcons().main_icon)
        main_window.setDockNestingEnabled(True)
        if is_macosx():
            main_window.setDocumentMode(True)
        # Set up the main container, which contains all the other form widgets.
        self.main_content = QtWidgets.QWidget(main_window)
        self.main_content.setObjectName('main_content')
        self.main_content_layout = QtWidgets.QHBoxLayout(self.main_content)
        self.main_content_layout.setSpacing(0)
        self.main_content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_content_layout.setObjectName('main_content_layout')
        main_window.setCentralWidget(self.main_content)
        show_layout_preset_tabs = self.settings.value('user interface/show layout preset tabs')
        if show_layout_preset_tabs is None:
            show_layout_preset_tabs = True
        self.control_splitter = QtWidgets.QSplitter(self.main_content)
        self.control_splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.control_splitter.setObjectName('control_splitter')
        if is_modern_style():
            self.main_content_layout.setContentsMargins(6, 6, 6, 6)
            self.control_splitter.setHandleWidth(8)
        self.main_content_layout.addWidget(self.control_splitter)
        advanced_docking = is_modern_style()
        if advanced_docking:
            main_window.initialize_advanced_docking()
        self.layout_preset_navigation = LayoutPresetNavigation(main_window)
        self.layout_preset_navigation.setObjectName('layout_preset_navigation')
        for button, icon in zip(self.layout_preset_navigation.buttons,
                                (UiIcons().dashboard, UiIcons().mode_setup, UiIcons().live)):
            button.setIcon(icon)
        self.layout_preset_navigation.contentHost().addOwnedPage(main_window.takeCentralWidget())
        self.layout_preset_navigation.contentHost().setCurrentIndex(0, animated=False)
        main_window.setCentralWidget(self.layout_preset_navigation)
        self.layout_preset_navigation.setNavigationVisible(show_layout_preset_tabs)
        dock_widget_class = AdvancedDockWidget if advanced_docking else OpenLPDockWidget
        preview_visible = self.settings.value('user interface/preview panel')
        live_visible = self.settings.value('user interface/live panel')
        panel_locked = self.settings.value('user interface/lock panel')
        # Create menu
        self.menu_bar = QtWidgets.create_application_menu_bar(main_window)
        self.menu_bar.setObjectName('menu_bar')
        self.file_menu = QtWidgets.create_application_menu(self.menu_bar)
        self.file_menu.setObjectName('fileMenu')
        self.recent_files_menu = QtWidgets.create_application_menu(self.file_menu)
        self.recent_files_menu.setIcon(UiIcons().time)
        self.recent_files_menu.setObjectName('recentFilesMenu')
        self.file_import_menu = QtWidgets.create_application_menu(self.file_menu)
        self.file_import_menu.setIcon(UiIcons().download)
        self.file_import_menu.setObjectName('file_import_menu')
        self.file_export_menu = QtWidgets.create_application_menu(self.file_menu)
        self.file_export_menu.setIcon(UiIcons().upload)
        self.file_export_menu.setObjectName('file_export_menu')
        # View Menu
        self.view_menu = QtWidgets.create_application_menu(self.menu_bar)
        self.view_menu.setObjectName('viewMenu')
        self.view_mode_menu = QtWidgets.create_application_menu(self.view_menu)
        self.view_mode_menu.setIcon(UiIcons().dashboard)
        self.view_mode_menu.setObjectName('viewModeMenu')
        # Tools Menu
        self.tools_menu = QtWidgets.create_application_menu(self.menu_bar)
        self.tools_menu.setObjectName('tools_menu')
        # Settings Menu
        self.settings_menu = QtWidgets.create_application_menu(self.menu_bar)
        self.settings_menu.setObjectName('settingsMenu')
        self.settings_language_menu = QtWidgets.create_application_menu(self.settings_menu)
        self.settings_language_menu.setIcon(UiIcons().translation)
        self.settings_language_menu.setObjectName('settingsLanguageMenu')
        # Help Menu
        self.help_menu = QtWidgets.create_application_menu(self.menu_bar)
        self.help_menu.setObjectName('helpMenu')
        main_window.setMenuBar(self.menu_bar)
        self.status_bar = FooterStatusBar(main_window)
        self.status_bar.setObjectName('status_bar')
        main_window.setStatusBar(self.status_bar)
        self.load_progress_bar = QtWidgets.QProgressBar(self.status_bar)
        self.load_progress_bar.setObjectName('load_progress_bar')
        self.status_bar.add_left_widget(self.load_progress_bar, 1)
        self.load_progress_bar.hide()
        self.load_progress_bar.setValue(0)
        self.default_theme_container = QtWidgets.QWidget(self.status_bar)
        default_theme_layout = QtWidgets.QHBoxLayout(self.default_theme_container)
        default_theme_layout.setContentsMargins(0, 0, 0, 0)
        default_theme_layout.setSpacing(4)
        self.default_theme_label = QtWidgets.QLabel(self.default_theme_container)
        self.default_theme_label.setObjectName('default_theme_label')
        self.default_theme_label.setText(translate('OpenLP.MainWindow', 'Default Theme:'))
        default_theme_layout.addWidget(self.default_theme_label)
        self.default_theme_button = QtWidgets.fluentqt.HyperlinkButton('', self.default_theme_container)
        self.default_theme_button.setObjectName('default_theme_button')
        self.default_theme_button.setFluentSize(QtWidgets.fluentqt.Button.ButtonSize.Small)
        self.default_theme_button.setToolTip(translate('OpenLP.MainWindow', 'Open Themes settings'))
        self.default_theme_button.clicked.connect(self.on_default_theme_clicked)
        default_theme_layout.addWidget(self.default_theme_button)
        self.status_bar.add_right_widget(self.default_theme_container)
        # Library and Themes are separate dock widgets; Qt tabifies them in the same dock area.
        self.media_manager_dock = dock_widget_class(main_window, 'media_manager_dock',
                                                   UiIcons().library)
        self.media_tool_box = MediaToolBox()
        self.media_tool_box.setObjectName('media_tool_box')
        self.media_tool_box.setStyleSheet(get_library_stylesheet())
        self.media_manager_dock.setWidget(self.media_tool_box)
        self.theme_manager_dock = dock_widget_class(main_window, 'theme_manager_dock',
                                                   UiIcons().theme)
        self.theme_manager_contents = ThemeManager(self.theme_manager_dock)
        self.theme_manager_contents.setObjectName('theme_manager_contents')
        self.theme_manager_dock.setWidget(self.theme_manager_contents)
        # Create the service manager
        self.service_manager_dock = dock_widget_class(main_window, 'service_manager_dock',
                                                     UiIcons().live)
        self.service_manager_contents = ServiceManager(self.service_manager_dock)
        self.service_manager_dock.setWidget(self.service_manager_contents)
        main_window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.service_manager_dock)
        main_window.splitDockWidget(self.service_manager_dock, self.media_manager_dock,
                                    QtCore.Qt.Orientation.Vertical)
        # Do not addDockWidget(theme) on the left: Qt would tabify it with another left dock (often Service).
        # tabifyDockWidget attaches Themes only to Library, below Service.
        main_window.tabifyDockWidget(self.media_manager_dock, self.theme_manager_dock)
        self.media_manager_dock.raise_()
        # Create the projector manager
        self.projector_manager_dock = dock_widget_class(parent=main_window,
                                                       name='projector_manager_dock',
                                                       icon=UiIcons().projector)
        self.projector_manager_contents = ProjectorManager(self.projector_manager_dock)
        self.projector_manager_contents.setObjectName('projector_manager_contents')
        self.projector_manager_dock.setWidget(self.projector_manager_contents)
        _set_dock_visible(self.projector_manager_dock, False)
        main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.projector_manager_dock)
        # Create the menu items
        action_list = ActionList.get_instance()
        action_list.add_category(UiStrings().File, CategoryOrder.standard_menu)
        self.file_new_item = create_action(main_window, 'fileNewItem', icon=UiIcons().new,
                                           can_shortcuts=True, category=UiStrings().File,
                                           triggers=self.service_manager_contents.on_new_service_clicked)
        self.file_open_item = create_action(main_window, 'fileOpenItem', icon=UiIcons().open,
                                            can_shortcuts=True, category=UiStrings().File,
                                            triggers=self.service_manager_contents.on_load_service_clicked)
        self.file_save_item = create_action(main_window, 'fileSaveItem', icon=UiIcons().save,
                                            can_shortcuts=True, category=UiStrings().File,
                                            triggers=self.service_manager_contents.decide_save_method)
        self.file_save_as_item = create_action(main_window, 'fileSaveAsItem', icon=UiIcons().save_plus,
                                               can_shortcuts=True, category=UiStrings().File,
                                               triggers=self.service_manager_contents.save_file_as)
        self.print_service_order_item = create_action(main_window, 'printServiceItem', icon=UiIcons().print,
                                                      can_shortcuts=True, category=UiStrings().File,
                                                      triggers=lambda x: PrintServiceForm().exec())
        self.file_exit_item = create_action(main_window, 'fileExitItem', icon=UiIcons().exit,
                                            can_shortcuts=True,
                                            category=UiStrings().File, triggers=main_window.close)
        # Give QT Extra Hint that this is the Exit Menu Item
        self.file_exit_item.setMenuRole(QtGui.QAction.MenuRole.QuitRole)
        action_list.add_category(UiStrings().Import, CategoryOrder.standard_menu)
        self.import_theme_item = create_action(main_window, 'importThemeItem',
                                               category=UiStrings().Import, can_shortcuts=True)
        self.import_language_item = create_action(main_window, 'importLanguageItem')
        action_list.add_category(UiStrings().Export, CategoryOrder.standard_menu)
        self.export_theme_item = create_action(main_window, 'exportThemeItem',
                                               category=UiStrings().Export, can_shortcuts=True)
        self.export_language_item = create_action(main_window, 'exportLanguageItem')
        action_list.add_category(UiStrings().View, CategoryOrder.standard_menu)
        # Projector items
        self.import_projector_item = create_action(main_window, 'importProjectorItem',
                                                   category=UiStrings().Import, can_shortcuts=False)
        action_list.add_category(UiStrings().Import, CategoryOrder.standard_menu)
        self.view_projector_manager_item = create_action(main_window, 'viewProjectorManagerItem',
                                                         icon=UiIcons().projector,
                                                         checked=_dock_is_visible(self.projector_manager_dock),
                                                         can_shortcuts=True,
                                                         category=UiStrings().View,
                                                         triggers=self.toggle_projector_manager)
        self.view_media_manager_item = create_action(main_window, 'viewMediaManagerItem',
                                                     icon=UiIcons().library,
                                                     checked=_dock_is_visible(self.media_manager_dock),
                                                     can_shortcuts=True,
                                                     category=UiStrings().View, triggers=self.toggle_media_manager)
        self.view_theme_manager_item = create_action(main_window, 'viewThemeManagerItem', can_shortcuts=True,
                                                     icon=UiIcons().theme,
                                                     checked=_dock_is_visible(self.theme_manager_dock),
                                                     category=UiStrings().View, triggers=self.toggle_theme_manager)
        self.view_service_manager_item = create_action(main_window, 'viewServiceManagerItem', can_shortcuts=True,
                                                       icon=UiIcons().live,
                                                       checked=_dock_is_visible(self.service_manager_dock),
                                                       category=UiStrings().View, triggers=self.toggle_service_manager)
        self.view_preview_panel = create_action(main_window, 'viewPreviewPanel', icon=UiIcons().preview,
                                                can_shortcuts=True, checked=preview_visible,
                                                category=UiStrings().View,
                                                triggers=self.set_preview_panel_visibility)
        self.view_live_panel = create_action(main_window, 'viewLivePanel', icon=UiIcons().live,
                                             can_shortcuts=True, checked=live_visible,
                                             category=UiStrings().View, triggers=self.set_live_panel_visibility)
        self.view_display_output_item = create_action(
            main_window, 'viewDisplayOutputItem',
            icon=UiIcons().get_icon_variant('live_presentation'),
            checked=True,
            can_shortcuts=True,
            context=QtCore.Qt.ShortcutContext.ApplicationShortcut,
            category=UiStrings().View,
            triggers=self.on_view_display_output_toggled)
        self.view_switch_projection_item = create_action(
            main_window, 'viewSwitchProjectionItem', can_shortcuts=True, visible=False,
            context=QtCore.Qt.ShortcutContext.ApplicationShortcut,
            category=UiStrings().View, triggers=self.on_switch_projection_window)
        self.view_switch_projection_item.setAutoRepeat(False)
        self.lock_panel = create_action(main_window, 'lockPanel', icon=UiIcons().lock, can_shortcuts=True,
                                        checked=panel_locked, category=UiStrings().View,
                                        triggers=self.set_lock_panel)
        action_list.add_category(UiStrings().ViewMode, CategoryOrder.standard_menu)
        self.mode_default_item = create_action(
            main_window, 'modeDefaultItem', checked=False,
            category=UiStrings().ViewMode, can_shortcuts=True)
        self.mode_setup_item = create_action(main_window, 'modeSetupItem',
                                             checked=False, category=UiStrings().ViewMode, can_shortcuts=True)
        self.mode_live_item = create_action(main_window, 'modeLiveItem', checked=True,
                                            category=UiStrings().ViewMode, can_shortcuts=True)
        self.mode_group = QtGui.QActionGroup(main_window)
        self.mode_group.addAction(self.mode_default_item)
        self.mode_group.addAction(self.mode_setup_item)
        self.mode_group.addAction(self.mode_live_item)
        self.mode_default_item.setChecked(True)
        self.mode_reset_layout_presets_item = create_action(
            main_window, 'modeResetLayoutPresetsItem', category=UiStrings().ViewMode,
            can_shortcuts=False, triggers=self.on_mode_reset_layout_presets_clicked)
        self.view_layout_preset_tabs_item = create_action(
            main_window,
            'viewLayoutPresetTabsItem',
            checked=show_layout_preset_tabs,
            category=UiStrings().ViewMode,
            can_shortcuts=False,
            triggers=self.on_toggle_layout_preset_tabs)
        action_list.add_category(UiStrings().Tools, CategoryOrder.standard_menu)
        self.tools_add_tool_item = create_action(main_window,
                                                 'toolsAddToolItem', icon=UiIcons().add,
                                                 category=UiStrings().Tools, can_shortcuts=True)
        self.tools_open_data_folder = create_action(main_window,
                                                    'toolsOpenDataFolder', icon=UiIcons().open,
                                                    category=UiStrings().Tools, can_shortcuts=True)
        self.tools_first_time_wizard = create_action(main_window,
                                                     'toolsFirstTimeWizard', icon=UiIcons().undo,
                                                     category=UiStrings().Tools, can_shortcuts=True)
        self.update_theme_images = create_action(main_window,
                                                 'updateThemeImages', icon=UiIcons().refresh,
                                                 category=UiStrings().Tools, can_shortcuts=True)
        action_list.add_category(UiStrings().Settings, CategoryOrder.standard_menu)
        self.settings_plugin_list_item = create_action(main_window,
                                                       'settingsPluginListItem',
                                                       icon=UiIcons().plugin_list,
                                                       can_shortcuts=True,
                                                       category=UiStrings().Settings,
                                                       triggers=self.on_plugin_item_clicked)
        # i18n Language Items
        self.auto_language_item = create_action(main_window, 'autoLanguageItem', checked=LanguageManager.auto_language)
        self.language_group = QtGui.QActionGroup(main_window)
        self.language_group.setExclusive(True)
        self.language_group.setObjectName('languageGroup')
        add_actions(self.language_group, [self.auto_language_item])
        qm_list = LanguageManager.get_qm_list()
        saved_language = LanguageManager.get_language()
        for key in sorted(qm_list.keys()):
            language_item = create_action(main_window, key, checked=qm_list[key] == saved_language)
            add_actions(self.language_group, [language_item])
        self.settings_shortcuts_item = create_action(main_window, 'settingsShortcutsItem',
                                                     icon=UiIcons().keyboard,
                                                     category=UiStrings().Settings, can_shortcuts=True)
        # Formatting Tags were also known as display tags.
        self.formatting_tag_item = create_action(main_window, 'displayTagItem',
                                                 icon=UiIcons().theme, category=UiStrings().Settings,
                                                 can_shortcuts=True)
        self.settings_configure_item = create_action(main_window, 'settingsConfigureItem',
                                                     icon=UiIcons().settings, can_shortcuts=True,
                                                     category=UiStrings().Settings)
        # Give Qt Extra Hint that this is the Preferences Menu Item
        self.settings_configure_item.setMenuRole(QtGui.QAction.MenuRole.PreferencesRole)
        self.settings_import_item = create_action(main_window, 'settingsImportItem',
                                                  category=UiStrings().Import, can_shortcuts=True)
        self.formatting_tags_import_item = create_action(main_window, 'formattingTagsImportItem',
                                                         category=UiStrings().Import, can_shortcuts=True)
        self.settings_export_item = create_action(main_window, 'settingsExportItem',
                                                  category=UiStrings().Export, can_shortcuts=True)
        self.formatting_tags_export_item = create_action(main_window, 'formattingTagsExportItem',
                                                         category=UiStrings().Export, can_shortcuts=True)
        action_list.add_category(UiStrings().Help, CategoryOrder.standard_menu)
        self.about_item = create_action(main_window, 'aboutItem', icon=UiIcons().info,
                                        can_shortcuts=True, category=UiStrings().Help,
                                        triggers=self.on_about_item_clicked)
        # Give Qt Extra Hint that this is an About Menu Item
        self.about_item.setMenuRole(QtGui.QAction.MenuRole.AboutRole)
        if is_win():
            self.local_help_file = AppLocation.get_directory(AppLocation.AppDir) / 'OpenLP.chm'
        elif is_macosx():
            self.local_help_file = AppLocation.get_directory(AppLocation.AppDir) / '..' / 'Resources' / 'OpenLP.help'
        self.user_manual_item = create_action(main_window, 'userManualItem', icon=UiIcons().manual,
                                              can_shortcuts=True, category=UiStrings().Help,
                                              triggers=self.on_help_clicked)
        self.web_site_item = create_action(main_window, 'webSiteItem', icon=UiIcons().web, can_shortcuts=True,
                                           category=UiStrings().Help)
        # Shortcuts not connected to buttons or menu entries.
        self.search_shortcut_action = create_action(main_window,
                                                    'searchShortcut', can_shortcuts=True,
                                                    category=translate('OpenLP.MainWindow', 'General'),
                                                    triggers=self.on_search_shortcut_triggered)
        '''
        Leave until the import projector options are finished
        add_actions(self.file_import_menu, (self.settings_import_item, self.import_theme_item,
                    self.import_projector_item, self.import_language_item, None))
        '''
        add_actions(self.file_import_menu, (self.settings_import_item, self.import_theme_item,
                    self.formatting_tags_import_item,
                    self.import_language_item, None))
        add_actions(self.file_export_menu, (self.settings_export_item, self.export_theme_item,
                    self.formatting_tags_export_item,
                    self.export_language_item, None))
        add_actions(self.file_menu, (self.file_new_item, self.file_open_item,
                    self.file_save_item, self.file_save_as_item, self.recent_files_menu.menuAction(), None,
                    self.file_import_menu.menuAction(), self.file_export_menu.menuAction(), None,
                    self.print_service_order_item, self.file_exit_item))
        add_actions(self.view_mode_menu, (self.mode_default_item, self.mode_setup_item, self.mode_live_item,
                                          None, self.view_layout_preset_tabs_item,
                                          self.mode_reset_layout_presets_item))
        add_actions(self.view_menu, (self.view_mode_menu.menuAction(), None, self.view_media_manager_item,
                    self.view_projector_manager_item, self.view_service_manager_item, self.view_theme_manager_item,
                    None, self.view_preview_panel, self.view_live_panel, self.view_display_output_item,
                    self.view_switch_projection_item, None,
                    self.lock_panel))
        # i18n add Language Actions
        add_actions(self.settings_language_menu, (self.auto_language_item, None))
        add_actions(self.settings_language_menu, self.language_group.actions())
        # Qt on OS X looks for keywords in the menu items title to determine which menu items get added to the main
        # menu. If we are running on Mac OS X the menu items whose title contains those keywords but don't belong in the
        # main menu need to be marked as such with QAction.MenuRole.NoRole.
        if is_macosx():
            self.settings_shortcuts_item.setMenuRole(QtGui.QAction.MenuRole.NoRole)
            self.formatting_tag_item.setMenuRole(QtGui.QAction.MenuRole.NoRole)
        add_actions(self.settings_menu, (self.settings_plugin_list_item, self.settings_language_menu.menuAction(),
                    None, self.formatting_tag_item, self.settings_shortcuts_item, self.settings_configure_item))
        add_actions(self.tools_menu, (self.tools_add_tool_item, None))
        add_actions(self.tools_menu, (self.tools_open_data_folder, None))
        add_actions(self.tools_menu, (self.tools_first_time_wizard, None))
        add_actions(self.tools_menu, [self.update_theme_images])
        add_actions(self.help_menu, (self.user_manual_item, None, self.web_site_item, self.about_item))
        add_actions(self.menu_bar, (self.file_menu.menuAction(), self.view_menu.menuAction(),
                    self.tools_menu.menuAction(), self.settings_menu.menuAction(), self.help_menu.menuAction()))
        add_actions(self, [self.search_shortcut_action])
        # Initialise the translation
        self.retranslate_ui(main_window)
        self.media_tool_box.setCurrentIndex(0)
        _set_dock_visible(self.theme_manager_dock, self.settings.value('user interface/show themes'))
        # Tabified docks report isVisible() false when not the active tab; use saved intent.
        self.view_theme_manager_item.setChecked(self.settings.value('user interface/show themes'))
        # Connect up some signals and slots
        self.file_menu.aboutToShow.connect(self.update_recent_files_menu)
        self.view_menu.aboutToShow.connect(self._sync_view_display_output_menu_action)
        # Hide the entry, as it does not have any functionality yet.
        self.tools_add_tool_item.setVisible(False)
        self.import_language_item.setVisible(False)
        self.export_language_item.setVisible(False)
        self.set_lock_panel(panel_locked)
        self.settings_replaced = False

    def retranslate_ui(self, main_window):
        """
        Set up the translation system
        """
        main_window.setWindowTitle(UiStrings().OpenLP)
        self.file_menu.setTitle(translate('OpenLP.MainWindow', '&File'))
        self.file_import_menu.setTitle(translate('OpenLP.MainWindow', '&Import'))
        self.file_export_menu.setTitle(translate('OpenLP.MainWindow', '&Export'))
        self.recent_files_menu.setTitle(translate('OpenLP.MainWindow', '&Recent Services'))
        self.view_menu.setTitle(translate('OpenLP.MainWindow', '&View'))
        self.view_mode_menu.setTitle(translate('OpenLP.MainWindow', '&Layout Presets'))
        self.tools_menu.setTitle(translate('OpenLP.MainWindow', '&Tools'))
        self.settings_menu.setTitle(translate('OpenLP.MainWindow', '&Settings'))
        self.settings_language_menu.setTitle(translate('OpenLP.MainWindow', '&Language'))
        self.help_menu.setTitle(translate('OpenLP.MainWindow', '&Help'))
        self.service_manager_dock.setWindowTitle(translate('OpenLP.MainWindow', 'Service'))
        self.media_manager_dock.setWindowTitle(translate('OpenLP.MainWindow', 'Library'))
        self.theme_manager_dock.setWindowTitle(translate('OpenLP.MainWindow', 'Themes'))
        self.projector_manager_dock.setWindowTitle(translate('OpenLP.MainWindow', 'Projector Controller'))
        self.file_new_item.setText(translate('OpenLP.MainWindow', '&New Service'))
        self.file_new_item.setToolTip(UiStrings().NewService)
        self.file_new_item.setStatusTip(UiStrings().CreateService)
        self.file_open_item.setText(translate('OpenLP.MainWindow', '&Open Service'))
        self.file_open_item.setToolTip(UiStrings().OpenService)
        self.file_open_item.setStatusTip(translate('OpenLP.MainWindow', 'Open an existing service.'))
        self.file_save_item.setText(translate('OpenLP.MainWindow', '&Save Service'))
        self.file_save_item.setToolTip(UiStrings().SaveService)
        self.file_save_item.setStatusTip(translate('OpenLP.MainWindow', 'Save the current service to disk.'))
        self.file_save_as_item.setText(translate('OpenLP.MainWindow', 'Save Service &As...'))
        self.file_save_as_item.setToolTip(translate('OpenLP.MainWindow', 'Save Service As'))
        self.file_save_as_item.setStatusTip(translate('OpenLP.MainWindow',
                                            'Save the current service under a new name.'))
        self.print_service_order_item.setText(UiStrings().PrintService)
        self.print_service_order_item.setStatusTip(translate('OpenLP.MainWindow', 'Print the current service.'))
        self.file_exit_item.setText(translate('OpenLP.MainWindow', 'E&xit'))
        self.file_exit_item.setStatusTip(translate('OpenLP.MainWindow', 'Close OpenLP+ - Shut down the program.'))
        self.import_theme_item.setText(translate('OpenLP.MainWindow', '&Theme'))
        self.import_language_item.setText(translate('OpenLP.MainWindow', '&Language'))
        self.export_theme_item.setText(translate('OpenLP.MainWindow', '&Theme'))
        self.export_language_item.setText(translate('OpenLP.MainWindow', '&Language'))
        self.settings_shortcuts_item.setText(translate('OpenLP.MainWindow', 'Configure &Shortcuts...'))
        self.formatting_tag_item.setText(translate('OpenLP.MainWindow', 'Configure &Formatting Tags...'))
        self.settings_configure_item.setText(translate('OpenLP.MainWindow', '&Configure OpenLP+...'))
        self.settings_export_item.setStatusTip(
            translate('OpenLP.MainWindow', 'Export settings to a *.config file.'))
        self.settings_export_item.setText(translate('OpenLP.MainWindow', 'Settings'))
        self.formatting_tags_export_item.setStatusTip(
            translate('OpenLP.MainWindow', 'Export formatting tags to a *.json file.'))
        self.formatting_tags_export_item.setText(translate('OpenLP.MainWindow', 'Formatting tags'))
        self.settings_import_item.setStatusTip(
            translate('OpenLP.MainWindow', 'Import settings from a *.config file previously exported from '
                                           'this or another machine.'))
        self.settings_import_item.setText(translate('OpenLP.MainWindow', 'Settings'))
        self.formatting_tags_import_item.setStatusTip(
            translate('OpenLP.MainWindow', 'Import formatting tags from a *.json file.'))
        self.formatting_tags_import_item.setText(translate('OpenLP.MainWindow', 'Formatting tags'))
        self.view_projector_manager_item.setText(translate('OpenLP.MainWindow', '&Projector Controller'))
        self.view_projector_manager_item.setToolTip(translate('OpenLP.MainWindow', 'Hide or show Projectors.'))
        self.view_projector_manager_item.setStatusTip(translate('OpenLP.MainWindow',
                                                                'Toggle visibility of the Projectors.'))
        self.view_media_manager_item.setText(translate('OpenLP.MainWindow', 'L&ibrary'))
        self.view_media_manager_item.setToolTip(translate('OpenLP.MainWindow', 'Hide or show the Library.'))
        self.view_media_manager_item.setStatusTip(translate('OpenLP.MainWindow',
                                                  'Toggle the visibility of the Library.'))
        self.view_theme_manager_item.setText(translate('OpenLP.MainWindow', '&Themes'))
        self.view_theme_manager_item.setToolTip(translate('OpenLP.MainWindow', 'Hide or show themes'))
        self.view_theme_manager_item.setStatusTip(translate('OpenLP.MainWindow',
                                                  'Toggle visibility of the Themes.'))
        self.view_service_manager_item.setText(translate('OpenLP.MainWindow', '&Service'))
        self.view_service_manager_item.setToolTip(translate('OpenLP.MainWindow', 'Hide or show Service.'))
        self.view_service_manager_item.setStatusTip(translate('OpenLP.MainWindow',
                                                    'Toggle visibility of the Service.'))
        self.view_preview_panel.setText(translate('OpenLP.MainWindow', '&Preview'))
        self.view_preview_panel.setToolTip(translate('OpenLP.MainWindow', 'Hide or show Preview.'))
        self.view_preview_panel.setStatusTip(
            translate('OpenLP.MainWindow', 'Toggle visibility of the Preview.'))
        self.view_live_panel.setText(translate('OpenLP.MainWindow', 'Li&ve'))
        self.view_live_panel.setToolTip(translate('OpenLP.MainWindow', 'Hide or show Live'))
        self.lock_panel.setText(translate('OpenLP.MainWindow', 'L&ock visibility of the panels'))
        self.lock_panel.setStatusTip(translate('OpenLP.MainWindow', 'Lock visibility of the panels.'))
        self.view_live_panel.setStatusTip(translate('OpenLP.MainWindow', 'Toggle visibility of the Live.'))
        self.view_display_output_item.setText(translate('OpenLP.MainWindow', 'Display &output'))
        self.view_display_output_item.setToolTip(translate(
            'OpenLP.MainWindow', 'Show or hide the presentation on the main display output.'))
        self.view_display_output_item.setStatusTip(translate(
            'OpenLP.MainWindow', 'Toggle display output (same as Show Presentation / Show Desktop on the Live '
                                'toolbar).'))
        self.view_switch_projection_item.setText(translate(
            'OpenLP.MainWindow', 'Toggle display output'))
        self.view_switch_projection_item.setStatusTip(translate(
            'OpenLP.MainWindow', 'Bring the projection forward. Use the shortcut again to return to OpenLP+.'))
        self.settings_plugin_list_item.setText(translate('OpenLP.MainWindow', '&Manage Plugins'))
        self.settings_plugin_list_item.setStatusTip(translate('OpenLP.MainWindow', 'You can enable and disable plugins '
                                                                                   'from here.'))
        self.about_item.setText(translate('OpenLP.MainWindow', '&About'))
        self.about_item.setStatusTip(
            translate('OpenLP.MainWindow', 'More information about OpenLP+ (a fork of OpenLP).'))
        self.user_manual_item.setText(translate('OpenLP.MainWindow', '&User Manual'))
        self.search_shortcut_action.setText(UiStrings().Search)
        self.search_shortcut_action.setToolTip(
            translate('OpenLP.MainWindow', 'Jump to the search box of the current active plugin.'))
        self.web_site_item.setText(translate('OpenLP.MainWindow', '&Web Site'))
        for item in self.language_group.actions():
            item.setText(item.objectName())
            item.setStatusTip(translate('OpenLP.MainWindow',
                                        'Set the interface language to {name}').format(name=item.objectName()))
        self.auto_language_item.setText(translate('OpenLP.MainWindow', '&Autodetect'))
        self.auto_language_item.setStatusTip(translate('OpenLP.MainWindow', 'Use the system language, if available.'))
        self.tools_add_tool_item.setText(translate('OpenLP.MainWindow', 'Add &Tool...'))
        self.tools_add_tool_item.setStatusTip(translate('OpenLP.MainWindow',
                                                        'Add an application to the list of tools.'))
        self.tools_open_data_folder.setText(translate('OpenLP.MainWindow', 'Open &Data Folder...'))
        self.tools_open_data_folder.setStatusTip(translate('OpenLP.MainWindow',
                                                 'Open the folder where songs, bibles and other data resides.'))
        self.tools_first_time_wizard.setText(translate('OpenLP.MainWindow', 'Re-run First Time Wizard'))
        self.tools_first_time_wizard.setStatusTip(translate('OpenLP.MainWindow',
                                                  'Re-run the First Time Wizard, importing songs, Bibles and themes.'))
        self.update_theme_images.setText(translate('OpenLP.MainWindow', 'Update Theme Images'))
        self.update_theme_images.setStatusTip(translate('OpenLP.MainWindow',
                                                        'Update the preview images for all themes.'))
        self.mode_default_item.setText(translate('OpenLP.MainWindow', '&General'))
        self.mode_default_item.setStatusTip(translate('OpenLP.MainWindow', 'Reset the interface back to the '
                                                                           'default layout and show all the panels.'))
        self.layout_preset_navigation.setItemText(0, translate('OpenLP.MainWindow',
                                                        'General'))
        self.layout_preset_navigation.pane_toggle.setToolTip(translate('OpenLP.MainWindow', 'Toggle Compact mode'))
        self.layout_preset_navigation.pane_toggle.setAccessibleName(
            translate('OpenLP.MainWindow', 'Toggle Compact mode'))
        self.mode_setup_item.setText(translate('OpenLP.MainWindow', '&Setup'))
        self.mode_setup_item.setStatusTip(translate(
            'OpenLP.MainWindow',
            'Service beside Library and Themes, with Preview (Live panel hidden) for setting up the service.'))
        self.layout_preset_navigation.setItemText(1, translate('OpenLP.MainWindow', 'Prepare'))
        self.mode_live_item.setText(translate('OpenLP.MainWindow', '&Live'))
        self.mode_live_item.setStatusTip(translate(
            'OpenLP.MainWindow',
            'Use layout that focuses on Live: Preview and Live slide controllers, without the Library.'))
        self.layout_preset_navigation.setItemText(2, translate('OpenLP.MainWindow', 'Live'))
        self.view_layout_preset_tabs_item.setText(translate('OpenLP.MainWindow', 'Show layout &navigation'))
        self.view_layout_preset_tabs_item.setStatusTip(translate(
            'OpenLP.MainWindow',
            'Show or hide the layout navigation pane on the left side of the window.'))
        self.mode_reset_layout_presets_item.setText(translate('OpenLP.MainWindow', '&Reset'))
        self.mode_reset_layout_presets_item.setStatusTip(translate(
            'OpenLP.MainWindow',
            'Discard saved custom layouts for Show all, Setup, and Live. Built-in preset behaviour is restored.'))


class MainWindow(AdvancedDockingMixin, QtWidgets.QMainWindow, Ui_MainWindow, LogMixin, RegistryProperties):
    """
    The main window.
    """
    def _preset_layout_storage_key(self, mode, fragment):
        return _preset_layout_storage_key(mode, fragment, self._modern_appearance)

    def __init__(self):
        """
        This constructor sets up the interface, the various managers, and the plugins.
        """
        super(MainWindow, self).__init__()
        Registry().register('main_window', self)
        self.clipboard = QtWidgets.QApplication.clipboard()
        self.recent_files = []
        self.timer_id = 0
        self.new_data_path = None
        self.copy_data = False
        self.settings.set_up_default_values()
        # Capture service activation for this session; plugin changes take effect after a restart.
        Registry().set_flag('projector_disabled', self.settings.value('projector/status') != PluginStatus.Active)
        Registry().set_flag('no_web_server', Registry().get_flag('no_web_server') or
                            self.settings.value('remote_interface/status') != PluginStatus.Active)
        self.about_form = AboutForm(self)
        SettingsForm(self)
        self.formatting_tag_form = FormattingTagForm(self)
        self.shortcut_form = ShortcutListForm(self)
        # Set up the interface
        self.setup_ui(self)
        self.view_projector_manager_item.setVisible(not Registry().get_flag('projector_disabled'))
        self.import_projector_item.setVisible(not Registry().get_flag('projector_disabled'))
        self.export_presentation_menu = QtWidgets.create_application_menu(self.file_export_menu)
        self.export_presentation_menu.setTitle(translate('OpenLP.MainWindow', '&Presentation'))
        self.export_presentation_menu.setObjectName('export_presentation_menu')
        self.export_powerpoint_item = self.export_presentation_menu.addAction(
            translate('OpenLP.MainWindow', 'PowerPoint (PPTX)'))
        self.export_powerpoint_item.setObjectName('export_powerpoint_item')
        self.export_powerpoint_item.triggered.connect(
            lambda checked=False: self.service_manager_contents.on_export_presentation('.pptx'))
        self.export_opendocument_item = self.export_presentation_menu.addAction(
            translate('OpenLP.MainWindow', 'OpenDocument (ODP)'))
        self.export_opendocument_item.setObjectName('export_opendocument_item')
        self.export_opendocument_item.triggered.connect(
            lambda checked=False: self.service_manager_contents.on_export_presentation('.odp'))
        self.file_export_menu.addMenu(self.export_presentation_menu)
        # Define the media Dock Manager
        self.media_dock_manager = MediaDockManager(self.media_tool_box)
        # Load settings after setup_ui so default UI sizes are overwritten
        # Once settings are loaded update the menu with the recent files.
        self.update_recent_files_menu()
        self.plugin_form = PluginForm(self)
        # Set up signals and slots
        self.media_manager_dock.visibilityChanged.connect(self.toggle_media_manager)
        self.service_manager_dock.visibilityChanged.connect(self.toggle_service_manager)
        self.theme_manager_dock.visibilityChanged.connect(self.toggle_theme_manager)
        self.projector_manager_dock.visibilityChanged.connect(self.toggle_projector_manager)
        self.import_theme_item.triggered.connect(self.theme_manager_contents.on_import_theme)
        self.export_theme_item.triggered.connect(self.theme_manager_contents.on_export_theme)
        self.web_site_item.triggered.connect(self.on_help_web_site_clicked)
        self.tools_open_data_folder.triggered.connect(self.on_tools_open_data_folder_clicked)
        self.tools_first_time_wizard.triggered.connect(self.on_first_time_wizard_clicked)
        self.update_theme_images.triggered.connect(self.on_update_theme_images)
        self.formatting_tag_item.triggered.connect(self.on_formatting_tag_item_clicked)
        self.settings_configure_item.triggered.connect(self.on_settings_configure_item_clicked)
        self.settings_shortcuts_item.triggered.connect(self.on_settings_shortcuts_item_clicked)
        self.settings_import_item.triggered.connect(self.on_settings_import_item_clicked)
        self.formatting_tags_import_item.triggered.connect(self.on_formatting_tags_import_item_clicked)
        self.settings_export_item.triggered.connect(self.on_settings_export_item_clicked)
        self.formatting_tags_export_item.triggered.connect(self.on_formatting_tags_export_item_clicked)
        # i18n set signals for languages
        self.language_group.triggered.connect(LanguageManager.set_language)
        self.mode_default_item.triggered.connect(self.on_mode_default_item_clicked)
        self.mode_setup_item.triggered.connect(self.on_mode_setup_item_clicked)
        self.mode_live_item.triggered.connect(self.on_mode_live_item_clicked)
        self.layout_preset_navigation.currentChanged.connect(self.on_layout_preset_tab_changed)
        # Media Manager
        self.media_tool_box.currentChanged.connect(self.on_media_tool_box_changed)
        self.application.set_busy_cursor()
        self.should_show_screen_change_message = True
        # Simple message boxes
        Registry().register_function('theme_change_global', self.default_theme_changed)
        Registry().register_function('config_screen_changed', self.screen_changed)
        Registry().register_function('media_dock_refresh_icons', self.refresh_media_dock_icons)
        Registry().register_function('alternate_rows_changed', self.alternate_rows_changed)
        Registry().register_function('bootstrap_post_set_up', self.bootstrap_post_set_up)
        # Reset the cursor
        self.application.set_normal_cursor()
        # Starting up web services
        self.http_server = HttpServer(self)
        self.ws_server = WebSocketServer()
        self.screen_updating_lock = Lock()
        self._projection_topmost_suspended = False

    @contextmanager
    def _mute_left_dock_visibility_signals(self):
        docks = (self.service_manager_dock, self.media_manager_dock, self.theme_manager_dock)
        for dock in docks:
            dock.blockSignals(True)
        try:
            yield
        finally:
            for dock in docks:
                dock.blockSignals(False)

    @contextmanager
    def _show_wait_dialog(self, title: str, message: str):
        """
        Show a wait dialog, wait for some tasks to complete, and then close it.
        """
        try:
            # Display a progress dialog with a message
            wait_dialog = QtWidgets.QProgressDialog(message, '', 0, 0, self)
            wait_dialog.setWindowTitle(title)
            wait_dialog.setMinimumSize(300, 70)
            for window_flag in [QtCore.Qt.WindowType.WindowContextHelpButtonHint]:
                wait_dialog.setWindowFlag(window_flag, False)
            wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            wait_dialog.setAutoClose(False)
            wait_dialog.setCancelButton(None)
            wait_dialog.show()
            QtWidgets.QApplication.processEvents()
            yield
        finally:
            # Finally close the message window
            wait_dialog.close()

    def _wait_for_threads(self):
        """
        Wait for the threads
        """
        # Sometimes the threads haven't finished, let's wait for them
        thread_names = list(self.application.worker_threads.keys())
        for thread_name in thread_names:
            self.log_debug('Waiting for thread %s' % thread_name)
            QtWidgets.QApplication.processEvents()
            if thread_name not in self.application.worker_threads.keys():
                continue
            thread = self.application.worker_threads[thread_name]['thread']
            worker = self.application.worker_threads[thread_name]['worker']
            try:
                if worker and hasattr(worker, 'stop'):
                    # If the worker has a stop method, run it
                    worker.stop()
                if thread and thread.isRunning():
                    # If the thread is running, let's wait 5 seconds for it
                    retry = 0
                    while thread.isRunning() and retry < 50:
                        # Make the GUI responsive while we wait
                        QtWidgets.QApplication.processEvents()
                        thread.wait(100)
                        retry += 1
                    if thread.isRunning():
                        # If the thread is still running after 5 seconds, kill it
                        thread.terminate()
            except RuntimeError:
                # Ignore the RuntimeError that is thrown when Qt has already deleted the C++ thread object
                pass

    def refresh_media_dock_icons(self):
        """
        Refresh library tab icons so updated service theme colors are reflected immediately.
        """
        self.media_dock_manager.refresh_item_icons()

    def alternate_rows_changed(self):
        """
        Update alternating row colors on all open item views.
        """
        use_alternate_rows = self.settings.value('advanced/alternate rows')
        for widget in QtWidgets.QApplication.allWidgets():
            if isinstance(widget, QtWidgets.QAbstractItemView):
                widget.setAlternatingRowColors(use_alternate_rows)

    def bootstrap_post_set_up(self):
        """
        process the bootstrap post setup request
        """
        self.load_settings()
        self.restore_current_media_manager_item()
        Registry().execute('theme_change_global')
        self._sync_view_display_output_menu_action()
        # Escape has one dedicated hide action. Older shortcut settings may
        # also bind it to Show Desktop, which makes Qt treat the key as ambiguous.
        desktop_action = getattr(self.live_controller, 'desktop_screen', None)
        escape_key = QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape)
        if desktop_action is not None:
            desktop_action.setShortcuts([shortcut for shortcut in desktop_action.shortcuts()
                                         if shortcut != escape_key])
            mapped_actions = ActionList.shortcut_map.get(escape_key.toString(), [])
            if desktop_action in mapped_actions:
                mapped_actions.remove(desktop_action)
                if not mapped_actions:
                    del ActionList.shortcut_map[escape_key.toString()]
        esc_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape), self)
        esc_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        esc_shortcut.setAutoRepeat(False)
        esc_shortcut.activated.connect(self._on_escape_hide_presentation_from_main)

    def _on_escape_hide_presentation_from_main(self):
        """
        Hide the live presentation (Show desktop) when Escape is pressed from the main interface.

        Skips when a modal dialog is open or when a text field has focus so Escape keeps its usual behaviour.
        """
        if QtWidgets.QApplication.activeModalWidget():
            return
        fw = QtWidgets.QApplication.focusWidget()
        if fw is not None and isinstance(fw, (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit,
                                               QtWidgets.QAbstractSpinBox)):
            return
        live = self.live_controller
        if not live or not live.display:
            return
        if live.current_hide_mode == HideMode.Screen:
            return
        live.set_hide_mode(HideMode.Screen)

    def restore_current_media_manager_item(self):
        """
        Called on start up to restore the last active media plugin.
        """
        self.log_info('Load data from Settings')
        if self.settings.value('advanced/save current plugin'):
            saved_plugin_id = self.settings.value('advanced/current media plugin')
            if saved_plugin_id != -1:
                self.media_tool_box.setCurrentIndex(saved_plugin_id)

    def on_search_shortcut_triggered(self):
        """
        Called when the search shortcut has been pressed.
        """
        # Make sure the media_dock is visible.
        if not _dock_is_visible(self.media_manager_dock):
            _set_dock_visible(self.media_manager_dock, True)
        widget = self.media_tool_box.currentWidget()
        if widget:
            widget.on_focus()

    def on_media_tool_box_changed(self, index: int):
        """
        Focus a widget when the media toolbox changes.
        """
        widget = self.media_tool_box.widget(index)
        if widget:
            widget.on_focus()

    def on_new_version(self, version: str):
        """
        Notifies the user that a newer version of OpenLP is available. Triggered by delay thread and cannot display
        popup.

        :param version: The Version to be displayed.
        """
        version_text = translate('OpenLP.MainWindow', 'Version {new} of OpenLP+ is now available for download (you are '
                                 'currently running version {current}). \n\nYou can download the latest version from '
                                 'https://openlp.org/.').format(new=version, current=get_version()[u'full'])
        QtWidgets.QMessageBox.question(self, translate('OpenLP.MainWindow', 'OpenLP+ Version Updated'), version_text)

    def on_new_remote_version(self, version: str):
        """
        Notifies the user that a newer version of the web remote is available. Triggered by delay thread and cannot
        display popup.

        :param version: The Version to be displayed.
        """
        Registry().get('settings').setValue('api/last version test', date.today().strftime('%Y-%m-%d'))
        Registry().get('settings_form').api_tab.master_version = version
        version_text = translate('OpenLP.MainWindow', 'Version {version} of the web remote is now available for '
                                 'download.\nTo download this version, go to the Remote settings and click the Upgrade '
                                 'button.').format(version=version)
        self.information_message(translate('OpenLP.MainWindow', 'New Web Remote Version Available'), version_text)

    def show(self):
        """
        Show the main form, as well as the display form
        """
        QtWidgets.QWidget.show(self)
        self.activateWindow()
        # We have -disable-web-security added by our code.
        # If a file is passed in we will have that as well so count of 2
        # If not we need to see if we want to use the previous file.so count of 1
        self.log_info(self.application.args)
        if self.application.args and len(self.application.args) > 1:
            self.open_cmd_line_files(self.application.args)
        elif self.settings.value('core/auto open'):
            self.service_manager_contents.load_last_file()
        # This will store currently used layout preset so it remains enabled on next startup.
        # If any panel is enabled/disabled after preset is set, this setting is not saved.
        view_mode = self.settings.value('core/view mode')
        # If we are using a default mode set accordingly
        if self.settings.value('user interface/is preset layout'):
            if view_mode not in _PRESET_LAYOUT_MODES:
                view_mode = 'default'
                self.settings.setValue('core/view mode', 'default')
            if view_mode == 'default':
                self.mode_default_item.setChecked(True)
                self.mode_setup_item.setChecked(False)
                self.mode_live_item.setChecked(False)
            elif view_mode == 'setup':
                self.mode_setup_item.setChecked(True)
                self.mode_default_item.setChecked(False)
                self.mode_live_item.setChecked(False)
            elif view_mode == 'live':
                self.mode_live_item.setChecked(True)
                self.mode_default_item.setChecked(False)
                self.mode_setup_item.setChecked(False)
            # Applying a preset toggles panel visibility, which emits visibility signals that would
            # otherwise clear the preset flag during startup.
            self.settings.setValue('user interface/is preset layout', True)
            if not _preset_layout_has_saved_state(self.settings, view_mode, self._modern_appearance):
                if view_mode == 'default':
                    self.set_view_mode(True, True, True, True, True, False, 'default')
                elif view_mode == 'setup':
                    self.set_view_mode(True, True, True, True, False, False, 'setup')
                elif view_mode == 'live':
                    self.set_view_mode(False, True, False, True, True, False, 'live')
                self.settings.setValue('user interface/is preset layout', True)
        else:
            self.set_view_mode(
                self.settings.value('user interface/show library'),
                self.settings.value('user interface/show service'),
                self.settings.value('user interface/show themes'),
                self.settings.value('user interface/preview panel'),
                self.settings.value('user interface/live panel'),
                self.settings.value('user interface/show projectors')
            )
        # restoreState() can leave Service/Library/Themes floating or detached; rebuilding the
        # left column must run after the window exists (splitDockWidget crashed during bootstrap).
        self._schedule_left_column_dock_layout()

    def first_time(self):
        """
        Import themes if first time
        """
        self.application.process_events()
        for plugin in State().list_plugins():
            if hasattr(plugin, 'first_time'):
                self.application.process_events()
                plugin.first_time()
        self.application.process_events()
        # Load the themes from files
        self.theme_manager_contents.load_first_time_themes()
        # Update the theme widget
        self.theme_manager_contents.load_themes()
        temp_path = Path(gettempdir(), 'openlp')
        shutil.rmtree(temp_path, True)

    def on_first_time_wizard_clicked(self):
        """
        Re-run the first time wizard.  Prompts the user for run confirmation.If wizard is run, songs, bibles and
        themes are imported.  The default theme is changed (if necessary).  The plugins in pluginmanager are
        set active/in-active to match the selection in the wizard.
        """
        answer = QtWidgets.QMessageBox.warning(self,
                                               translate('OpenLP.MainWindow', 'Re-run First Time Wizard?'),
                                               translate('OpenLP.MainWindow',
                                                         'Are you sure you want to re-run the First '
                                                         'Time Wizard?\n\nRe-running this wizard may make changes to '
                                                         'your current OpenLP+ configuration and possibly add songs to '
                                                         'your existing songs list and change your default theme.'),
                                               QtWidgets.QMessageBox.StandardButton(
                                                   QtWidgets.QMessageBox.StandardButton.Yes |
                                                   QtWidgets.QMessageBox.StandardButton.No),
                                               QtWidgets.QMessageBox.StandardButton.No)
        if answer == QtWidgets.QMessageBox.StandardButton.No:
            return
        first_run_wizard = FirstTimeForm(self)
        first_run_wizard.initialize(ScreenList())
        if first_run_wizard.exec() == QtWidgets.QDialog.DialogCode.Rejected:
            return
        self.application.set_busy_cursor()
        self.first_time()
        # Check if Projectors panel should be visible or not after wizard.
        if self.settings.value('projector/show after wizard') and not Registry().get_flag('projector_disabled'):
            _set_dock_visible(self.projector_manager_dock, True)
        else:
            _set_dock_visible(self.projector_manager_dock, False)
        for plugin in State().list_plugins():
            self.active_plugin = plugin
            old_status = self.active_plugin.status
            self.active_plugin.set_status()
            if old_status != self.active_plugin.status:
                if self.active_plugin.status == PluginStatus.Active:
                    self.active_plugin.toggle_status(PluginStatus.Active)
                    self.active_plugin.app_startup()
                else:
                    self.active_plugin.toggle_status(PluginStatus.Inactive)
        # Set global theme and
        Registry().execute('theme_change_global')
        # Check if any Bibles downloaded.  If there are, they will be processed.
        Registry().execute('bibles_load_list')
        self.application.set_normal_cursor()

    def is_display_blank(self):
        """
        Check and display message if screen blank on setup.
        """
        if self.settings.value('core/screen blank'):
            if self.settings.value('core/blank warning'):
                QtWidgets.QMessageBox.question(self, translate('OpenLP.MainWindow', 'OpenLP+ Main Display Blanked'),
                                               translate('OpenLP.MainWindow', 'The Main Display has been blanked out'))

    def error_message(self, title: str, message: str):
        """
        Display an error message

        :param title: The title of the warning box.
        :param message: The message to be displayed.
        """
        if hasattr(self.application, 'splash'):
            self.application.splash.close()
        QtWidgets.QMessageBox.critical(self, title, message)

    def warning_message(self, title: str, message: str):
        """
        Display a warning message

        :param title:  The title of the warning box.
        :param message: The message to be displayed.
        """
        if hasattr(self.application, 'splash'):
            self.application.splash.close()
        QtWidgets.QMessageBox.warning(self, title, message)

    def information_message(self, title: str, message: str):
        """
        Display an informational message

        :param title: The title of the warning box.
        :param message: The message to be displayed.
        """
        if hasattr(self.application, 'splash'):
            self.application.splash.close()
        QtWidgets.QMessageBox.information(self, title, message)

    @staticmethod
    def on_help_web_site_clicked():
        """
        Load the OpenLP website
        """
        webbrowser.open_new('https://openlp.org/')

    def on_help_clicked(self):
        """
        If is_macosx or is_win, open the local OpenLP help file.
        Use the Online manual in other cases. (Linux)
        """
        webbrowser.open_new('https://manual.openlp.org/')

    def on_about_item_clicked(self):
        """
        Show the About form
        """
        self.about_form.exec()

    def on_plugin_item_clicked(self):
        """
        Show the Plugin form
        """
        self.plugin_form.load()
        self.plugin_form.exec()

    @staticmethod
    def on_tools_open_data_folder_clicked():
        """
        Open data folder
        """
        path = str(AppLocation.get_data_path())
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def on_update_theme_images(self):
        """
        Updates the new theme preview images.
        """
        self.theme_manager_contents._regenerate_previews_with_progress_dialog(
            self.theme_manager_contents.get_theme_names())

    def on_formatting_tag_item_clicked(self):
        """
        Show the Settings dialog
        """
        self.formatting_tag_form.exec()

    def on_settings_configure_item_clicked(self):
        """
        Show the Settings dialog
        """
        self.settings_form.exec()

    def on_default_theme_clicked(self):
        """Open Settings at the Themes section from the footer link."""
        self.settings_form.exec(UiStrings().Themes)

    def on_settings_shortcuts_item_clicked(self):
        """
        Show the shortcuts dialog
        """
        if self.shortcut_form.exec():
            self.shortcut_form.save()

    def on_settings_import_item_clicked(self):
        """
        Import settings from an export CONF or ZIP file
        """
        answer = QtWidgets.QMessageBox.critical(self, translate('OpenLP.MainWindow', 'Import settings?'),
                                                translate('OpenLP.MainWindow', 'Are you sure you want to import '
                                                                               'settings?\n\n Importing settings will '
                                                                               'make permanent changes to your current '
                                                                               'OpenLP+ configuration.\n\n Importing '
                                                                               'incorrect settings may cause erratic '
                                                                               'behaviour or OpenLP+ to terminate '
                                                                               'abnormally.'),
                                                QtWidgets.QMessageBox.StandardButton(
                                                    QtWidgets.QMessageBox.StandardButton.Yes |
                                                    QtWidgets.QMessageBox.StandardButton.No),
                                                QtWidgets.QMessageBox.StandardButton.No)
        if answer == QtWidgets.QMessageBox.StandardButton.No:
            return
        import_file_path, filter_used = FileDialog.getOpenFileName(
            self,
            translate('OpenLP.MainWindow', 'Import settings'),
            None,
            translate('OpenLP.MainWindow', 'OpenLP+ Settings (*.conf *.zip)'))
        if import_file_path is None:
            return

        self.application.set_busy_cursor()
        success = self.settings.import_settings(import_file_path)
        self.application.set_normal_cursor()

        if not success:
            QtWidgets.QMessageBox.critical(self, translate('OpenLP.MainWindow', 'Import settings'),
                                           translate('OpenLP.MainWindow', 'The file you have selected does not appear '
                                                                          'to be a valid OpenLP+ settings file, or is from '
                                                                          'a newer version of OpenLP+.\n\n'
                                                                          'Processing has terminated and '
                                                                          'no changes have been made.'),
                                           QtWidgets.QMessageBox.StandardButton(
                                               QtWidgets.QMessageBox.StandardButton.Ok))
            return

        # We must do an immediate restart or current configuration will overwrite what was just imported when
        # application terminates normally.   We need to exit without saving configuration.
        QtWidgets.QMessageBox.information(self, translate('OpenLP.MainWindow', 'Import settings'),
                                          translate('OpenLP.MainWindow',
                                                    'OpenLP+ will now close. Imported settings will '
                                                    'be applied the next time you start OpenLP+.'))
        self.settings_replaced = True
        self.clean_up()
        QtCore.QCoreApplication.exit()

    def on_settings_export_item_clicked(self):
        """
        Export settings to a ZIP file
        """
        export_file_path, filter_used = FileDialog.getSaveFileName(
            self,
            translate('OpenLP.MainWindow', 'Export Settings File'),
            None,
            translate('OpenLP.MainWindow', 'OpenLP+ Settings Backup (*.zip)'))
        if not export_file_path:
            return
        # Make sure it's a .zip file.
        export_file_path = export_file_path.with_suffix('.zip')
        self.save_settings()
        self.application.set_busy_cursor()
        try:
            self.settings.export_zip(export_file_path)
        except OSError as ose:
            QtWidgets.QMessageBox.critical(self, translate('OpenLP.MainWindow', 'Export setting error'),
                                           translate('OpenLP.MainWindow',
                                                     'An error occurred while exporting the settings: {err}'
                                                     ).format(err=ose.strerror),
                                           QtWidgets.QMessageBox.StandardButton(
                                               QtWidgets.QMessageBox.StandardButton.Ok))
        finally:
            self.application.set_normal_cursor()

    def on_formatting_tags_import_item_clicked(self):
        """
        Import formatting tags using the Formatting Tags dialog handler.
        """
        self.formatting_tag_form.on_import_clicked()

    def on_formatting_tags_export_item_clicked(self):
        """
        Export formatting tags using the Formatting Tags dialog handler.
        """
        self.formatting_tag_form.on_export_clicked()

    def on_mode_default_item_clicked(self):
        """
        Put OpenLP into "Default" view mode.
        """
        self._activate_layout_preset('default')

    @staticmethod
    def _layout_preset_mode_to_tab_index(mode: str) -> int:
        mode_to_index = {'default': 0, 'setup': 1, 'live': 2}
        return mode_to_index.get(mode, 0)

    @staticmethod
    def _layout_preset_tab_index_to_mode(index: int) -> str | None:
        index_to_mode = {0: 'default', 1: 'setup', 2: 'live'}
        return index_to_mode.get(index)

    def _sync_layout_preset_tab_from_settings(self) -> None:
        if not hasattr(self, 'layout_preset_navigation'):
            return
        mode = self.settings.value('core/view mode')
        index = self._layout_preset_mode_to_tab_index(mode)
        signal_blocker = QtCore.QSignalBlocker(self.layout_preset_navigation)
        self.layout_preset_navigation.setCurrentIndex(index)
        del signal_blocker

    def on_layout_preset_tab_changed(self, index: int) -> None:
        """
        Activate a named layout preset when the left preset tab selection changes.
        """
        mode = self._layout_preset_tab_index_to_mode(index)
        if not mode:
            return
        if self.settings.value('core/view mode') == mode and self.settings.value('user interface/is preset layout'):
            return
        self._activate_layout_preset(mode)

    def on_toggle_layout_preset_tabs(self, checked: bool) -> None:
        """
        Show or hide the left layout preset tabs and persist the user preference.
        """
        self.settings.setValue('user interface/show layout preset tabs', checked)
        self.layout_preset_navigation.setNavigationVisible(checked)
        self.view_layout_preset_tabs_item.setChecked(checked)

    def on_mode_setup_item_clicked(self):
        """
        Put OpenLP into "Setup" view mode.
        """
        self._activate_layout_preset('setup')

    def on_mode_live_item_clicked(self):
        """
        Put OpenLP into "Live" view mode (Preview and Live slide controllers; Library hidden).
        """
        self._activate_layout_preset('live')

    def set_view_mode(self, media: bool = True, service: bool = True, theme: bool = True, preview: bool = True,
                      live: bool = True, projector: bool = True, mode: str = '') -> None:
        """
        Set OpenLP to a different view mode.
        """
        if mode:
            self.settings.setValue('core/view mode', mode)
        _set_dock_visible(self.media_manager_dock, media)
        _set_dock_visible(self.service_manager_dock, service)
        _set_dock_visible(self.theme_manager_dock, theme)
        _set_dock_visible(self.projector_manager_dock, projector and not Registry().get_flag('projector_disabled'))
        # Menu reflects layout intent, not QDockWidget.isVisible() (false for inactive tabified tabs).
        self.view_media_manager_item.setChecked(media)
        self.view_service_manager_item.setChecked(service)
        self.view_theme_manager_item.setChecked(theme)
        self.settings.setValue('user interface/show library', media)
        self.settings.setValue('user interface/show service', service)
        self.settings.setValue('user interface/show themes', theme)
        # Preview/Live handlers clear "preset layout" unless we are applying a named preset (mode set).
        if mode:
            self.set_preview_panel_visibility(preview, update_preset_layout_flag=False)
            self.set_live_panel_visibility(live, update_preset_layout_flag=False)
            self.settings.setValue('user interface/is preset layout', True)
        else:
            self.set_preview_panel_visibility(preview)
            self.set_live_panel_visibility(live)

    def screen_changed(self):
        """
        The screen has changed so we have to update components such as the renderer.
        """
        try:
            # If a warning has been shown before, skip showing again to avoid spamming user.
            # Also do not show if the settings window is visible.
            should_show_messagebox = self.settings_form.isHidden() and self.should_show_screen_change_message
            if should_show_messagebox:
                self.should_show_screen_change_message = False
                self.live_controller.toggle_display('desktop')
                QtWidgets.QMessageBox.information(self,
                                                  UiStrings().ScreenSetupHasChangedTitle,
                                                  UiStrings().ScreenSetupHasChanged,
                                                  QtWidgets.QMessageBox.StandardButtons(
                                                      QtWidgets.QMessageBox.StandardButton.Ok))
                self.screen_change_timestamp = datetime.now()
            self.screen_updating_lock.acquire()
            self.application.set_busy_cursor()
            self.renderer.resize(self.live_controller.screens.current.display_geometry.size())
            self.preview_controller.screen_size_changed()
            self._projection_topmost_suspended = False
            self.live_controller.setup_displays()
            self.live_controller.screen_size_changed()
            self._sync_view_display_output_menu_action()
            self.setFocus()
            self.activateWindow()
            self.application.set_normal_cursor()
            # Forcing application to process events to trigger display update
            # We need to wait a little of time as it would otherwise need a mouse move
            # to process the screen change, for example
            QtCore.QTimer.singleShot(150, lambda: self.application.process_events())
        finally:
            self.screen_updating_lock.release()
            self.should_show_screen_change_message = True

    def closeEvent(self, event: QtGui.QCloseEvent):
        """
        Hook to close the main window and display windows on exit
        """
        # The MainApplication did not even enter the event loop (this happens
        # when OpenLP is not fully loaded). Just ignore the event.
        if not self.application.is_event_loop_active:
            event.ignore()
            return
        if self.service_manager_contents.is_modified():
            ret = self.service_manager_contents.save_modified_service()
            if ret == QtWidgets.QMessageBox.StandardButton.Save:
                if self.service_manager_contents.decide_save_method():
                    event.accept()
                else:
                    event.ignore()
            elif ret == QtWidgets.QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            has_open_service = bool(self.service_manager_contents.service_items)
            if self.settings.value('advanced/enable exit confirmation') and has_open_service:
                msg_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question,
                                                translate('OpenLP.MainWindow', 'Exit OpenLP+'),
                                                translate('OpenLP.MainWindow', 'Are you sure you want to exit OpenLP+?'),
                                                QtWidgets.QMessageBox.StandardButton(
                                                    QtWidgets.QMessageBox.StandardButton.Close |
                                                    QtWidgets.QMessageBox.StandardButton.Cancel),
                                                self)
                close_button = msg_box.button(QtWidgets.QMessageBox.StandardButton.Close)
                close_button.setText(translate('OpenLP.MainWindow', '&Exit OpenLP+'))
                msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Close)
                if msg_box.exec() == QtWidgets.QMessageBox.StandardButton.Close:
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()
        if event.isAccepted():
            with self._show_wait_dialog(translate('OpenLP.MainWindow', 'Please Wait'),
                                        translate('OpenLP.MainWindow', 'Waiting for some things to finish...')):
                # Wait for all the threads to complete
                self._wait_for_threads()
                # Keep imported or reset settings from being overwritten on exit.
                self.clean_up(save_settings=not self.settings_replaced)

    def eventFilter(self, obj, event: QtCore.QEvent):
        if event.type() == QtCore.QEvent.Type.FileOpen:
            file_name = event.file()
            self.log_debug('Got open file event for {name}!'.format(name=file_name))
            self.application.args.insert(0, file_name)
            return True
        # Mac OS X should restore app window when user clicked on the OpenLP icon
        # in the Dock bar. However, OpenLP consists of multiple windows and this
        # does not work. This workaround fixes that.
        # The main OpenLP window is restored when it was previously minimized.
        elif event.type() == QtCore.QEvent.Type.ApplicationActivate:
            if is_macosx() and hasattr(self, 'main_window'):
                if self.main_window.isMinimized():
                    # Copied from QWidget.setWindowState() docs on how to restore and activate a minimized window
                    # while preserving its maximized and/or full-screen state.
                    self.main_window.setWindowState(self.main_window.windowState() &
                                                    ~QtCore.Qt.WindowState.WindowMinimized |
                                                    QtCore.Qt.WindowState.WindowActive)
                    return True

        return super(MainWindow, self).eventFilter(obj, event)

    def clean_up(self, save_settings: bool = True):
        """
        Runs all the cleanup code before OpenLP shuts down.

        :param save_settings: Switch to prevent saving settings. Defaults to **True**.
        """
        theme_manager = Registry().get('theme_manager')
        if theme_manager is not None:
            theme_form = getattr(theme_manager, 'theme_form', None)
            if theme_form is not None and theme_form.isVisible():
                # End nested modal loop so shutdown is not blocked (ThemeForm uses QDialog.exec).
                theme_form.reject()
        if save_settings:
            if self.settings.value('advanced/save current plugin'):
                self.settings.setValue('advanced/current media plugin', self.media_tool_box.currentIndex())
        # Call the cleanup method to shutdown plugins.
        self.log_info('cleanup plugins')
        self.plugin_manager.finalise_plugins()
        if save_settings:
            # Save settings
            self.save_settings()
        # Check if we need to change the data directory
        if self.new_data_path:
            self.change_data_directory()
        # Close down WebSocketServer
        self.ws_server.close()
        # Close down the display
        self.live_controller.close_displays()
        # Clean temporary files used by services
        self.service_manager_contents.clean_up()
        if is_win():
            # Needed for Windows to stop crashes on exit
            Registry().remove('application')

    def set_service_modified(self, modified: bool, file_name: Path | str):
        """
        This method is called from the ServiceManager to set the title of the main window.

        :param modified: Whether or not this service has been modified.
        :param file_name: The file name of the service file.
        """
        if modified:
            title = '{title} - {name}*'.format(title=UiStrings().OpenLP, name=file_name)
        else:
            title = '{title} - {name}'.format(title=UiStrings().OpenLP, name=file_name)
        self.setWindowTitle(title)

    def show_status_message(self, message: str, timeout: int = 0):
        """
        Show a message in the status bar

        :param message: The message to display.
        :param timeout: Duration in milliseconds to display the message. 0 keeps it until replaced.
        """
        self.status_bar.showMessage(message, timeout)

    def default_theme_changed(self):
        """
        Update the default theme indicator in the status bar
        """
        theme_name = self.settings.value('themes/global theme')
        self.default_theme_button.setText(theme_name)

    def _dock_hidden_only_as_inactive_tab(self, dock: QtWidgets.QDockWidget) -> bool:
        """
        When Library and Themes are tabified, the inactive tab's dock is hidden but still "in" the layout.
        """
        if isinstance(dock, AdvancedDockWidget) or _dock_is_visible(dock):
            return False
        return any(w.isVisible() for w in self.tabifiedDockWidgets(dock))

    def _sync_left_dock_menu_checks_from_settings(self) -> None:
        self.view_media_manager_item.setChecked(self.settings.value('user interface/show library'))
        self.view_service_manager_item.setChecked(self.settings.value('user interface/show service'))
        self.view_theme_manager_item.setChecked(self.settings.value('user interface/show themes'))

    def _leave_named_preset_layout_if_unpinned(self) -> None:
        """
        Named presets (Show all / Setup / Live) may be customised in place; only leave preset mode when the active
        view mode is not one of those.
        """
        if self.settings.value('core/view mode') not in _PRESET_LAYOUT_MODES:
            self.settings.setValue('user interface/is preset layout', False)

    def _preset_visibility_snapshot_json(self) -> str:
        blob = {
            'show_library': bool(self.settings.value('user interface/show library')),
            'show_service': bool(self.settings.value('user interface/show service')),
            'show_themes': bool(self.settings.value('user interface/show themes')),
            'preview_panel': bool(self.settings.value('user interface/preview panel')),
            'live_panel': bool(self.settings.value('user interface/live panel')),
            'show_projectors': bool(self.settings.value('user interface/show projectors')),
        }
        return json.dumps(blob)

    def _apply_preset_visibility_snapshot(self, raw: str) -> bool:
        """
        Apply per-preset visibility from JSON. Returns True if settings and widgets were updated.
        """
        if not raw or not str(raw).strip():
            return False
        try:
            blob = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False
        show_library = bool(blob.get('show_library', True))
        show_service = bool(blob.get('show_service', True))
        show_themes = bool(blob.get('show_themes', True))
        preview_panel = bool(blob.get('preview_panel', True))
        live_panel = bool(blob.get('live_panel', True))
        show_projectors = bool(blob.get('show_projectors', False))
        self.settings.setValue('user interface/show library', show_library)
        self.settings.setValue('user interface/show service', show_service)
        self.settings.setValue('user interface/show themes', show_themes)
        self.settings.setValue('user interface/preview panel', preview_panel)
        self.settings.setValue('user interface/live panel', live_panel)
        self.settings.setValue('user interface/show projectors', show_projectors)
        with self._mute_left_dock_visibility_signals():
            _set_dock_visible(self.media_manager_dock, show_library)
            _set_dock_visible(self.service_manager_dock, show_service)
            _set_dock_visible(self.theme_manager_dock, show_themes)
        self.view_media_manager_item.setChecked(show_library)
        self.view_service_manager_item.setChecked(show_service)
        self.view_theme_manager_item.setChecked(show_themes)
        self.preview_controller.panel.setVisible(preview_panel)
        self.view_preview_panel.setChecked(preview_panel)
        self.live_controller.panel.setVisible(live_panel)
        self.view_live_panel.setChecked(live_panel)
        show_projectors = show_projectors and not Registry().get_flag('projector_disabled')
        _set_dock_visible(self.projector_manager_dock, show_projectors)
        self.view_projector_manager_item.setChecked(show_projectors)
        return True

    def _apply_canonical_preset_visibility(self, mode: str) -> None:
        """
        Factory visibility for a named layout preset (Show all / Setup / Live).
        """
        if mode == 'default':
            self.set_view_mode(True, True, True, True, True, False, 'default')
        elif mode == 'setup':
            self.set_view_mode(True, True, True, True, False, False, 'setup')
        elif mode == 'live':
            self.set_view_mode(False, True, False, True, True, False, 'live')

    def _save_current_layout_to_preset(self, mode: str) -> None:
        self.settings.setValue(self._preset_layout_storage_key(mode, 'main window state'), self.saveState())
        self.settings.setValue(
            self._preset_layout_storage_key(mode, 'main window splitter geometry'), self.control_splitter.saveState())
        self.settings.setValue(
            self._preset_layout_storage_key(mode, 'live splitter geometry'), self.live_controller.splitter.saveState())
        self.settings.setValue(
            self._preset_layout_storage_key(mode, 'preview splitter geometry'), self.preview_controller.splitter.saveState())
        self.settings.setValue(
            self._preset_layout_storage_key(mode, _PRESET_VISIBILITY_SNAPSHOT_KEY), self._preset_visibility_snapshot_json())

    def _restore_layout_from_preset(self, mode: str) -> None:
        state = self.settings.value(self._preset_layout_storage_key(mode, 'main window state'))
        if state and len(state) > 0:
            self.restoreState(state)
        self.live_controller.splitter.restoreState(
            self.settings.value(self._preset_layout_storage_key(mode, 'live splitter geometry')))
        self.preview_controller.splitter.restoreState(
            self.settings.value(self._preset_layout_storage_key(mode, 'preview splitter geometry')))
        self.control_splitter.restoreState(
            self.settings.value(self._preset_layout_storage_key(mode, 'main window splitter geometry')))
        self.control_splitter.setChildrenCollapsible(False)

    def _activate_layout_preset(self, mode: str) -> None:
        prev = self.settings.value('core/view mode')
        if (self.settings.value('user interface/is preset layout') and prev in _PRESET_LAYOUT_MODES and prev != mode):
            self._save_current_layout_to_preset(prev)
        self.settings.setValue('core/view mode', mode)
        has_saved = _preset_layout_has_saved_state(self.settings, mode, self._modern_appearance)
        if has_saved:
            # restoreState() reapplies saved dock visibility; a stored snapshot (or canonical fallback)
            # must run after so Setup/Live preview+live flags stay correct.
            self._restore_layout_from_preset(mode)
            snap = self.settings.value(self._preset_layout_storage_key(mode, _PRESET_VISIBILITY_SNAPSHOT_KEY)) or ''
            if not self._apply_preset_visibility_snapshot(snap):
                self._apply_canonical_preset_visibility(mode)
        else:
            self._apply_canonical_preset_visibility(mode)
            if getattr(self, 'dock_manager', None):
                self._reset_dock_layout = True
        if mode == 'default':
            self.mode_default_item.setChecked(True)
        elif mode == 'setup':
            self.mode_setup_item.setChecked(True)
        elif mode == 'live':
            self.mode_live_item.setChecked(True)
        self.settings.setValue('user interface/is preset layout', True)
        self.settings.setValue('projector/show after wizard', True)
        if mode == 'default':
            self.mode_setup_item.setChecked(False)
            self.mode_live_item.setChecked(False)
        elif mode == 'setup':
            self.mode_default_item.setChecked(False)
            self.mode_live_item.setChecked(False)
        elif mode == 'live':
            self.mode_default_item.setChecked(False)
            self.mode_setup_item.setChecked(False)
        self._sync_layout_preset_tab_from_settings()
        self._schedule_left_column_dock_layout()

    def on_mode_reset_layout_presets_clicked(self) -> None:
        answer = QtWidgets.QMessageBox.warning(
            self,
            translate('OpenLP.MainWindow', 'Reset layout presets?'),
            translate('OpenLP.MainWindow', 'This will revert customisations for all layout presets.\n\n'
                      'Do you want to continue?'),
            QtWidgets.QMessageBox.StandardButton(
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No),
            QtWidgets.QMessageBox.StandardButton.No)
        # QMessageBox may return StandardButton or int depending on platform / Qt build.
        yes = QtWidgets.QMessageBox.StandardButton.Yes
        if int(answer) != int(yes):
            return
        empty = QtCore.QByteArray()
        for preset_mode in _PRESET_LAYOUT_MODES:
            self.settings.setValue(self._preset_layout_storage_key(preset_mode, 'main window state'), empty)
            self.settings.setValue(self._preset_layout_storage_key(preset_mode, 'main window splitter geometry'), empty)
            self.settings.setValue(self._preset_layout_storage_key(preset_mode, 'live splitter geometry'), empty)
            self.settings.setValue(self._preset_layout_storage_key(preset_mode, 'preview splitter geometry'), empty)
            self.settings.setValue(self._preset_layout_storage_key(preset_mode, _PRESET_VISIBILITY_SNAPSHOT_KEY), '')
        view_mode = self.settings.value('core/view mode')
        if view_mode not in _PRESET_LAYOUT_MODES:
            return
        # Drop in-memory window/dock/splitter state so the factory preset can take effect visually; clearing preset
        # keys alone leaves QMainWindow.restoreState() layout and global splitter bytes unchanged.
        self.restoreState(empty)
        self.settings.setValue(_window_state_storage_key(self._modern_appearance), empty)
        self._reset_dock_layout = True
        self.control_splitter.restoreState(empty)
        self.settings.setValue('user interface/main window splitter geometry', empty)
        self.live_controller.splitter.restoreState(empty)
        self.settings.setValue('user interface/live splitter geometry', empty)
        self.preview_controller.splitter.restoreState(empty)
        self.settings.setValue('user interface/preview splitter geometry', empty)
        self.control_splitter.setChildrenCollapsible(False)
        self.settings.setValue('user interface/is preset layout', True)
        if view_mode == 'default':
            self.set_view_mode(True, True, True, True, True, False, 'default')
        elif view_mode == 'setup':
            self.set_view_mode(True, True, True, True, False, False, 'setup')
        else:
            self.set_view_mode(False, True, False, True, True, False, 'live')
        self.settings.setValue('user interface/is preset layout', True)
        self._deferred_apply_left_column_dock_layout()

    def toggle_media_manager(self):
        """
        Toggle the visibility of the media manager
        """
        if self.sender() is self.view_media_manager_item:
            # Use saved intent, not isVisible() (inactive tabified tab reports hidden).
            want_visible = not self.settings.value('user interface/show library')
            self.settings.setValue('user interface/show library', want_visible)
            _set_dock_visible(self.media_manager_dock, want_visible)
            self.view_media_manager_item.setChecked(want_visible)
            self._leave_named_preset_layout_if_unpinned()
            return
        if self.sender() is self.media_manager_dock and self._dock_hidden_only_as_inactive_tab(self.media_manager_dock):
            self._sync_left_dock_menu_checks_from_settings()
            return
        self.settings.setValue('user interface/show library', _dock_is_visible(self.media_manager_dock))
        self._leave_named_preset_layout_if_unpinned()
        self.view_media_manager_item.setChecked(self.settings.value('user interface/show library'))

    def toggle_projector_manager(self):
        """
        Toggle visibility of the projector manager
        """
        if Registry().get_flag('projector_disabled'):
            _set_dock_visible(self.projector_manager_dock, False)
            self.view_projector_manager_item.setChecked(False)
            return
        if self.sender() is self.view_projector_manager_item:
            _set_dock_visible(self.projector_manager_dock, not _dock_is_visible(self.projector_manager_dock))
        self.view_projector_manager_item.setChecked(_dock_is_visible(self.projector_manager_dock))
        self._leave_named_preset_layout_if_unpinned()
        self.settings.setValue('user interface/show projectors', _dock_is_visible(self.projector_manager_dock))
        # Check/uncheck checkbox on First time wizard based on visibility of this panel.
        if not self.settings.value('projector/show after wizard'):
            self.settings.setValue('projector/show after wizard', True)
        else:
            self.settings.setValue('projector/show after wizard', False)

    def toggle_service_manager(self):
        """
        Toggle the visibility of the service manager
        """
        if self.sender() is self.view_service_manager_item:
            want_visible = not self.settings.value('user interface/show service')
            self.settings.setValue('user interface/show service', want_visible)
            _set_dock_visible(self.service_manager_dock, want_visible)
            self.view_service_manager_item.setChecked(want_visible)
            self._leave_named_preset_layout_if_unpinned()
            return
        if self.sender() is self.service_manager_dock and self._dock_hidden_only_as_inactive_tab(
                self.service_manager_dock):
            self._sync_left_dock_menu_checks_from_settings()
            return
        self.settings.setValue('user interface/show service', _dock_is_visible(self.service_manager_dock))
        self._leave_named_preset_layout_if_unpinned()
        self.view_service_manager_item.setChecked(self.settings.value('user interface/show service'))

    def toggle_theme_manager(self):
        """
        Toggle the visibility of the theme manager
        """
        if self.sender() is self.view_theme_manager_item:
            want_visible = not self.settings.value('user interface/show themes')
            self.settings.setValue('user interface/show themes', want_visible)
            _set_dock_visible(self.theme_manager_dock, want_visible)
            self.view_theme_manager_item.setChecked(want_visible)
            self._leave_named_preset_layout_if_unpinned()
            return
        if self.sender() is self.theme_manager_dock and self._dock_hidden_only_as_inactive_tab(self.theme_manager_dock):
            self._sync_left_dock_menu_checks_from_settings()
            return
        self.settings.setValue('user interface/show themes', _dock_is_visible(self.theme_manager_dock))
        self._leave_named_preset_layout_if_unpinned()
        self.view_theme_manager_item.setChecked(self.settings.value('user interface/show themes'))

    def set_preview_panel_visibility(self, is_visible: bool, *, update_preset_layout_flag: bool = True):
        """
        Sets the visibility of the preview panel including saving the setting and updating the menu.

        :param is_visible: A bool giving the state to set the panel to
                True - Visible
                False - Hidden

        """
        self.preview_controller.panel.setVisible(is_visible)
        self.settings.setValue('user interface/preview panel', is_visible)
        self.view_preview_panel.setChecked(is_visible)
        if update_preset_layout_flag:
            self._leave_named_preset_layout_if_unpinned()

    def set_lock_panel(self, is_locked: bool):
        """
        Lock dock resize/close/float and per-panel visibility toggles; layout presets stay usable.
        """
        if is_locked:
            self.theme_manager_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
            self.service_manager_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
            self.media_manager_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
            self.projector_manager_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
            self.view_media_manager_item.setEnabled(False)
            self.view_service_manager_item.setEnabled(False)
            self.view_theme_manager_item.setEnabled(False)
            self.view_projector_manager_item.setEnabled(False)
            self.view_preview_panel.setEnabled(False)
            self.view_live_panel.setEnabled(False)
        else:
            all_dock_features = (QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable |
                                 QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
                                 QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
            self.theme_manager_dock.setFeatures(all_dock_features)
            self.service_manager_dock.setFeatures(all_dock_features)
            self.media_manager_dock.setFeatures(all_dock_features)
            self.projector_manager_dock.setFeatures(all_dock_features)
            self.view_media_manager_item.setEnabled(True)
            self.view_service_manager_item.setEnabled(True)
            self.view_theme_manager_item.setEnabled(True)
            self.view_projector_manager_item.setEnabled(True)
            self.view_preview_panel.setEnabled(True)
            self.view_live_panel.setEnabled(True)
        self.settings.setValue('user interface/lock panel', is_locked)

    def _left_dock_visibility_from_settings(self) -> tuple[bool, bool, bool]:
        """
        Effective visibility for Library, Service, and Themes.

        Per-pane ``user interface/show *`` keys can be stale (e.g. Themes True but Library/Service
        False) while a layout preset is still active; presets must win.
        """
        mode = self.settings.value('core/view mode')
        lib = self.settings.value('user interface/show library')
        svc = self.settings.value('user interface/show service')
        thm = self.settings.value('user interface/show themes')

        if self.settings.value('user interface/is preset layout'):
            if mode in _PRESET_LAYOUT_MODES and _preset_layout_has_saved_state(self.settings, mode, self._modern_appearance):
                return (lib, svc, thm)
            if mode == 'live':
                return False, True, False
            if mode in ('default', 'setup'):
                return True, True, True

        # Known bad state from tabified-dock visibility bugs: only Themes "on" in settings.
        if not lib and not svc and thm:
            return True, True, True

        return (lib, svc, thm)

    def _reapply_left_column_dock_layout(self) -> None:
        """
        Saved QMainWindow state often tabifies Service with Library. Enforce: Service on top,
        Library + Themes tabified together in the row below (same dock cell as each other only).
        """
        for dock in (self.theme_manager_dock, self.media_manager_dock, self.service_manager_dock):
            dock.setFloating(False)
            self.removeDockWidget(dock)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.service_manager_dock)
        self.splitDockWidget(self.service_manager_dock, self.media_manager_dock,
                             QtCore.Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.media_manager_dock, self.theme_manager_dock)
        self.media_manager_dock.raise_()

    def _reapply_left_column_dock_layout_setup(self) -> None:
        """
        Setup preset: full-height Library + Themes (tabified) | full-height Service, with
        Preview over Live in the central column — three vertical bands (see View → Setup).
        """
        for dock in (self.theme_manager_dock, self.media_manager_dock, self.service_manager_dock):
            dock.setFloating(False)
            self.removeDockWidget(dock)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.media_manager_dock)
        self.splitDockWidget(self.media_manager_dock, self.service_manager_dock,
                             QtCore.Qt.Orientation.Horizontal)
        self.tabifyDockWidget(self.media_manager_dock, self.theme_manager_dock)
        self.media_manager_dock.raise_()

    def _ensure_left_column_dock_sizes(self) -> None:
        """
        After restoreState / rebuild, the left strip can have near-zero width or a collapsed Service/Library split.
        """
        show_lib, show_svc, show_thm = (
            self.settings.value('user interface/show library'),
            self.settings.value('user interface/show service'),
            self.settings.value('user interface/show themes'),
        )
        if not (show_lib or show_svc or show_thm):
            return
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        mode = self.settings.value('core/view mode')
        # Setup: Service | Library+Themes horizontally — size both columns so Library is not squeezed.
        if (
            mode == 'setup'
            and self.settings.value('user interface/is preset layout')
            and show_svc
            and show_lib
        ):
            # Favour a wider Library column in Setup mode so tabs fit on one row on common display widths.
            svc_w = max(200, min(300, int(width * 0.10)))
            lib_w = max(680, min(1200, int(width * 0.52)))
            try:
                self.resizeDocks(
                    [self.media_manager_dock, self.service_manager_dock],
                    [lib_w, svc_w],
                    QtCore.Qt.Orientation.Horizontal)
            except (TypeError, AttributeError):
                pass
            return
        target_w = max(300, min(520, int(width * 0.26)))
        ref = self.service_manager_dock if show_svc else self.media_manager_dock
        try:
            self.resizeDocks([ref], [target_w], QtCore.Qt.Orientation.Horizontal)
        except (TypeError, AttributeError):
            pass
        if getattr(self, 'dock_manager', None) and show_svc and (show_lib or show_thm):
            self.resizeDocks([self.service_manager_dock, self.media_manager_dock],
                             [int(height * 0.35), int(height * 0.65)], QtCore.Qt.Orientation.Vertical)
    def _deferred_apply_left_column_dock_layout(self) -> None:
        """
        Rebuild the left column after the main window is shown. Called via QTimer so
        QMainWindow layout and restoreState have settled (avoids splitDockWidget crashes during bootstrap).
        """
        try:
            mode = self.settings.value('core/view mode')
            skip_for_saved_preset = (
                self.settings.value('user interface/is preset layout')
                and mode in _PRESET_LAYOUT_MODES
                and _preset_layout_has_saved_state(self.settings, mode, self._modern_appearance))
            if getattr(self, 'dock_manager', None):
                # Preserve floating groups and auto-hide positions across restarts, including custom layouts.
                skip_for_saved_preset = skip_for_saved_preset or bool(
                    self.settings.value(_window_state_storage_key(self._modern_appearance)))
                if getattr(self, '_reset_dock_layout', False):
                    skip_for_saved_preset = False
                    self._reset_dock_layout = False
            with self._mute_left_dock_visibility_signals():
                if not skip_for_saved_preset:
                    if mode == 'setup':
                        self._reapply_left_column_dock_layout_setup()
                    else:
                        self._reapply_left_column_dock_layout()
                show_lib, show_svc, show_thm = self._left_dock_visibility_from_settings()
                self.settings.setValue('user interface/show library', show_lib)
                self.settings.setValue('user interface/show service', show_svc)
                self.settings.setValue('user interface/show themes', show_thm)
                _set_dock_visible(self.service_manager_dock, show_svc)
                _set_dock_visible(self.media_manager_dock, show_lib)
                _set_dock_visible(self.theme_manager_dock, show_thm)
            self._sync_left_dock_menu_checks_from_settings()
            if not (getattr(self, 'dock_manager', None) and skip_for_saved_preset):
                self._ensure_left_column_dock_sizes()
            if (is_modern_style() and mode in ('default', 'live') and not skip_for_saved_preset
                    and not self.settings.value('user interface/main window splitter geometry')):
                self.control_splitter.setSizes([600, 600])
        except Exception:
            self.log_exception('Failed to rebuild left column dock layout')

    def _schedule_left_column_dock_layout(self) -> None:
        QtCore.QTimer.singleShot(0, self._deferred_apply_left_column_dock_layout)

    def on_view_display_output_toggled(self, checked: bool = False):
        """
        Show display output or switch to desktop (Show desktop), matching the Live toolbar hide modes.
        """
        live = self.live_controller
        if not live or not live.is_live:
            return
        if not checked and not live.is_desktop_hide_available():
            self._sync_view_display_output_menu_action()
            return
        if checked:
            live.set_hide_mode(None)
        else:
            live.set_hide_mode(HideMode.Screen)

    def _set_projection_windows_topmost(self, enabled: bool):
        """Temporarily release topmost stacking while the operator works in the main window."""
        live = self.live_controller
        display = live.display
        topmost_hint = QtCore.Qt.WindowType.WindowStaysOnTopHint
        for window in (getattr(live, 'media_widget', None), display):
            if not isinstance(window, QtWidgets.QWidget):
                continue
            if bool(window.windowFlags() & topmost_hint) == enabled:
                continue
            was_visible = window.isVisible()
            geometry = window.geometry()
            window.setWindowFlag(topmost_hint, enabled)
            if not enabled:
                window.setWindowState(window.windowState() & ~QtCore.Qt.WindowState.WindowFullScreen)
            window.setGeometry(geometry)
            if was_visible:
                if enabled and window is display and not is_macosx() and \
                        live.screens[display.screen_number].custom_geometry is None:
                    window.showFullScreen()
                else:
                    window.show()
        self._projection_topmost_suspended = not enabled

    def on_switch_projection_window(self):
        """Switch focus on a single screen without changing the presentation hide mode."""
        if len(ScreenList()) != 1 or QtWidgets.QApplication.activeModalWidget():
            return
        live = self.live_controller
        if not live or live.current_hide_mode == HideMode.Screen:
            return
        display = live.display
        if display is None or not display.isVisible():
            return
        active_window = QtWidgets.QApplication.activeWindow()
        media_widget = getattr(live, 'media_widget', None)
        if active_window is display or active_window is media_widget:
            if self.settings.value('core/always on top'):
                self._set_projection_windows_topmost(False)
            if self.isMinimized():
                self.showNormal()
            self.raise_()
            self.activateWindow()
            self.setFocus()
        else:
            if self._projection_topmost_suspended:
                self._set_projection_windows_topmost(True)
            display.raise_()
            display.activateWindow()
            display.setFocus()

    def _sync_view_display_output_menu_action(self):
        """
        Keep the View menu check state aligned with the live output mode.
        """
        live = self.live_controller
        showing = False
        desktop_hide_available = True
        if live and live.is_live and live.display is not None:
            desktop_hide_available = live.is_desktop_hide_available()
            showing = live.current_hide_mode != HideMode.Screen
        if not desktop_hide_available:
            # "Display output" maps to desktop hide/show, so disable it when desktop hide is unavailable.
            showing = True
        self.view_display_output_item.blockSignals(True)
        # Keep this action enabled so users can always re-enable output from the keyboard/menu.
        # If desktop hide is unavailable, toggling off is ignored in on_view_display_output_toggled().
        self.view_display_output_item.setEnabled(True)
        self.view_display_output_item.setChecked(showing)
        self.view_display_output_item.blockSignals(False)
        self.view_switch_projection_item.setVisible(len(ScreenList()) == 1)
        self.view_switch_projection_item.setEnabled(self.view_display_output_item.isChecked())

    def set_live_panel_visibility(self, is_visible: bool, *, update_preset_layout_flag: bool = True):
        """
        Sets the visibility of the live panel including saving the setting and updating the menu.

        :param is_visible: A bool giving the state to set the panel to
                True - Visible
                False - Hidden
        """
        self.live_controller.panel.setVisible(is_visible)
        self.settings.setValue('user interface/live panel', is_visible)
        self.view_live_panel.setChecked(is_visible)
        if update_preset_layout_flag:
            self._leave_named_preset_layout_if_unpinned()

    def _restore_main_window_geometry(self):
        """Restore the last window geometry, or choose a useful first-start size."""
        saved_geometry = self.settings.value('user interface/main window geometry')
        if saved_geometry and self.restoreGeometry(saved_geometry):
            # Restore the normal/maximised state, but never reopen the app minimised.
            self.setWindowState(self.windowState() & ~QtCore.Qt.WindowState.WindowMinimized)
            return
        screen = self.screen() or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        geometry = screen.geometry()
        self.setWindowState(QtCore.Qt.WindowState.WindowNoState)
        if geometry.width() * 9 >= geometry.height() * 21:
            # Use half an ultrawide screen, centred, without covering its taskbar or dock.
            target = QtCore.QRect(available)
            target.setWidth(available.width() // 2)
            target.moveLeft(available.x() + (available.width() - target.width()) // 2)
            handle = self.windowHandle()
            if handle is not None:
                margins = handle.frameMargins()
                target.adjust(margins.left(), margins.top(), -margins.right(), -margins.bottom())
            self.setGeometry(target)
        else:
            self.setWindowState(QtCore.Qt.WindowState.WindowMaximized)

    def load_settings(self):
        """
        Load the main window settings.
        """
        # Remove obsolete entries.
        self.settings.remove('custom slide')
        self.settings.remove('service')
        self.recent_files = self.settings.value('core/recent files')
        self._restore_main_window_geometry()
        self.restoreState(self.settings.value(_window_state_storage_key(self._modern_appearance)))
        if not self._window_position_is_valid(self.pos(), self.geometry()):
            self.move(0, 0)
        self.live_controller.splitter.restoreState(self.settings.value('user interface/live splitter geometry'))
        self.preview_controller.splitter.restoreState(self.settings.value('user interface/preview splitter geometry'))
        self.control_splitter.restoreState(self.settings.value('user interface/main window splitter geometry'))
        # This needs to be called after restoreState(), because saveState() also saves the "Collapsible" property
        # which was True (by default) < OpenLP 2.1.
        self.control_splitter.setChildrenCollapsible(False)
        _set_dock_visible(self.service_manager_dock, self.settings.value('user interface/show service'))
        _set_dock_visible(self.media_manager_dock, self.settings.value('user interface/show library'))
        _set_dock_visible(self.theme_manager_dock, self.settings.value('user interface/show themes'))
        self._sync_left_dock_menu_checks_from_settings()
        if self.settings.value('user interface/is preset layout'):
            mode = self.settings.value('core/view mode')
            if mode in _PRESET_LAYOUT_MODES and _preset_layout_has_saved_state(self.settings, mode, self._modern_appearance):
                self._restore_layout_from_preset(mode)
                snap = self.settings.value(self._preset_layout_storage_key(mode, _PRESET_VISIBILITY_SNAPSHOT_KEY)) or ''
                if not self._apply_preset_visibility_snapshot(snap):
                    self._apply_canonical_preset_visibility(mode)
                self._sync_left_dock_menu_checks_from_settings()
        show_layout_preset_tabs = self.settings.value('user interface/show layout preset tabs')
        if show_layout_preset_tabs is None:
            show_layout_preset_tabs = True
        self.layout_preset_navigation.setNavigationVisible(show_layout_preset_tabs)
        self.view_layout_preset_tabs_item.setChecked(show_layout_preset_tabs)
        self._sync_layout_preset_tab_from_settings()

    def _window_position_is_valid(self, position: QtCore.QPoint, geometry: QtCore.QRect):
        """
        Checks if the saved window position is still valid by checking if the bar at the top of the window
        (which allows the user to move the window) appears on one of the screens.
        This may not be the case if the user has unplugged the monitor where openlp was previously shown,
        or if the displays have been reconfigured.

        :param position: QtCore.QtPoint for the top left position of the window
        :param geometry: QtCore.QRect for the geometry of the window

        :return:    True or False
        """
        screens = ScreenList()
        for screen in screens:
            # window top bar y value must be between top and bottom of a screen
            # plus the left edge must be left of the right of the screen
            # and the right edge must be right of the left of the screen (allowing 50 pixels for control buttons)
            if ((screen.geometry.y() <= position.y() <= screen.geometry.y() + screen.geometry.height()) and
                    (position.x() < screen.geometry.x() + screen.geometry.width()) and
                    (position.x() + geometry.width() > screen.geometry.x() + 50)):
                return True
        return False

    def save_settings(self):
        """
        Save the main window settings.
        """
        # Keep imported or reset settings from being overwritten on exit.
        if self.settings_replaced:
            return
        self.settings.setValue('core/recent files', self.recent_files)
        self.settings.setValue('user interface/main window position', self.pos())
        self.settings.setValue(_window_state_storage_key(self._modern_appearance), self.saveState())
        self.settings.setValue('user interface/main window geometry', self.saveGeometry())
        self.settings.setValue('user interface/live splitter geometry', self.live_controller.splitter.saveState())
        self.settings.setValue('user interface/preview splitter geometry', self.preview_controller.splitter.saveState())
        self.settings.setValue('user interface/main window splitter geometry', self.control_splitter.saveState())
        self.theme_manager.save_settings()
        if self.settings.value('user interface/is preset layout'):
            mode = self.settings.value('core/view mode')
            if mode in _PRESET_LAYOUT_MODES:
                self._save_current_layout_to_preset(mode)

    def update_recent_files_menu(self):
        """
        Updates the recent file menu with the latest list of service files accessed.
        """
        recent_file_count = self.settings.value('advanced/recent file count')
        # This is to get around a weird issue that we're seeing on macOS. We've not been able to reproduce it
        # ourselves, but hopefully this will catch the issue.
        # See https://gitlab.com/openlp/openlp/-/issues/1383
        if isinstance(self.recent_files, str):
            try:
                self.recent_files = json.loads(self.recent_files, cls=OpenLPJSONDecoder)
            except json.JSONDecodeError as e:
                self.log_exception(e)
                self.recent_files = []
        elif isinstance(self.recent_files, list) and self.recent_files and isinstance(self.recent_files[0], str) and \
                self.recent_files[0].startswith('['):
            try:
                self.recent_files = json.loads(self.recent_files[0], cls=OpenLPJSONDecoder)
            except json.JSONDecodeError as e:
                self.log_exception(e)
                self.recent_files = []
        # Now continue as usual...
        self.recent_files_menu.clear()
        count = 0
        for recent_path in self.recent_files:
            if not recent_path:
                continue
            recent_path = Path(recent_path)
            if not recent_path.is_file():
                continue
            count += 1
            self.log_debug('Recent file name: {name}'.format(name=recent_path))
            action = create_action(self, '',
                                   text='&{n}. {name}'.format(n=count, name=recent_path.name),
                                   data=recent_path, triggers=self.service_manager_contents.on_recent_service_clicked)
            self.recent_files_menu.addAction(action)
            if count == recent_file_count:
                break
        clear_recent_files_action = \
            create_action(self, '', text=translate('OpenLP.MainWindow', 'Clear List', 'Clear List of recent files'),
                          statustip=translate('OpenLP.MainWindow', 'Clear the list of recent files.'),
                          enabled=bool(self.recent_files), triggers=self.clear_recent_file_menu)
        add_actions(self.recent_files_menu, (None, clear_recent_files_action))

    def add_recent_file(self, filename: Path | str):
        """
        Adds a service to the list of recently used files.

        :param filename: The service filename to add
        """
        # The max_recent_files value does not have an interface and so never gets
        # actually stored in the settings therefore the default value of 20 will
        # always be used.
        max_recent_files = self.settings.value('advanced/max recent files')
        file_path = Path(filename)
        # Some cleanup to reduce duplication in the recent file list
        file_path = resolve(file_path)
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:max_recent_files]

    def clear_recent_file_menu(self):
        """
        Clears the recent files.
        """
        self.recent_files = []

    def display_progress_bar(self, size: int):
        """
        Make Progress bar visible and set size
        """
        self.load_progress_bar.show()
        self.load_progress_bar.setMaximum(size)
        self.load_progress_bar.setValue(0)
        self.application.process_events()

    def increment_progress_bar(self, increment: int = 1):
        """
        Increase the Progress Bar by the value in increment.

        :param int increment: The value you to increase the progress bar by.
        """
        self.load_progress_bar.setValue(int(self.load_progress_bar.value() + increment))
        self.application.process_events()

    def finished_progress_bar(self):
        """
        Trigger it's removal after 2.5 second
        """
        self.timer_id = self.startTimer(2500)

    def timerEvent(self, event: QtCore.QTimerEvent):
        """
        Remove the Progress bar from view.
        """
        if event.timerId() == self.timer_id:
            self.timer_id = 0
            self.load_progress_bar.hide()
            # Sometimes the timer goes off as OpenLP is shutting down, and the application has already been deleted
            if self.application:
                self.application.process_events()

    def set_copy_data(self, copy_data):
        """
        Set the flag to copy the data
        """
        self.copy_data = copy_data

    def change_data_directory(self):
        """
        Change the data directory.
        """
        self.log_info('Changing data path to {newpath}'.format(newpath=self.new_data_path))
        old_data_path = AppLocation.get_data_path()
        # Copy OpenLP data to new location if requested.
        self.application.set_busy_cursor()
        if self.copy_data:
            self.log_info('Copying data to new path')
            try:
                self.show_status_message(
                    translate('OpenLP.MainWindow', 'Copying OpenLP+ data to new data directory location - {path} '
                              '- Please wait for copy to finish').format(path=self.new_data_path))
                shutil.copytree(str(old_data_path), str(self.new_data_path), dirs_exist_ok=True)
                self.log_info('Copy successful')
            except (OSError, shutil.Error) as why:
                self.application.set_normal_cursor()
                self.log_exception('Data copy failed {err}'.format(err=str(why)))
                err_text = translate('OpenLP.MainWindow',
                                     'OpenLP+ data directory copy failed\n\n{err}').format(err=str(why))
                QtWidgets.QMessageBox.critical(self, translate('OpenLP.MainWindow', 'New Data Directory Error'),
                                               err_text,
                                               QtWidgets.QMessageBox.StandardButton(
                                                   QtWidgets.QMessageBox.StandardButton.Ok))
                return False
        else:
            self.log_info('No data copy requested')
        # Change the location of data directory in config file.
        self.settings.setValue('advanced/data path', self.new_data_path)
        # Check if the new data path is our default.
        if self.new_data_path == AppLocation.get_directory(AppLocation.DataDir):
            self.settings.remove('advanced/data path')
        self.application.set_normal_cursor()

    def open_cmd_line_files(self, args: list):
        """
        Open files passed in through command line arguments

        :param list[str] args: List of remaining positional arguments
        """
        self.log_info(args)
        # Drop this argument, it's obvs not a filename
        if '--disable-web-security' in args:
            args.remove('--disable-web-security')
        # strip platform args, not a filename either
        try:
            platform_idx = args.index('-platform')
            if platform_idx >= 0:
                # remove the platform arg
                args.pop(platform_idx)
                # remove the platform input
                args.pop(platform_idx)
        except (ValueError, IndexError):
            pass
        # It has been known for Microsoft to double quote the path passed in and then encode one of the quotes.
        # Remove these to get the correct path.
        args = list(map(lambda x: x.replace('&quot;', ''), args))
        # Loop through the parameters, and see if we can pull a file out
        file_path = None
        for arg in args:
            try:
                # Resolve the file, and use strict mode to throw an exception if the file does not exist
                file_path = resolve(Path(arg), is_strict=True)
                # Check if this is actually a file
                if file_path.is_file():
                    break
                else:
                    file_path = None
            except FileNotFoundError:
                file_path = None
        # If none of the individual components are files, let's try pulling them together
        if not file_path:
            path_so_far = []
            for arg in args:
                path_so_far.append(arg)
                try:
                    file_path = resolve(Path(' '.join(path_so_far)), is_strict=True)
                    if file_path.is_file():
                        break
                    else:
                        file_path = None
                except FileNotFoundError:
                    file_path = None
            else:
                file_path = None
        if file_path and file_path.suffix in ['.osz', '.oszl']:
            self.log_info("File name found")
            self.service_manager_contents.load_file(file_path)
        else:
            self.log_debug(f"File {file_path} not found for arg {args}")
