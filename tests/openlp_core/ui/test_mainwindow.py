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
Package to test opal.core.ui.mainwindow package.
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from PySide6 import QtCore, QtGui
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.i18n import UiStrings
from opal.core.common.registry import Registry
from opal.core.display.screens import ScreenList
from opal.core.lib.plugin import PluginStatus
from opal.core.state import State
from opal.core.ui.mainwindow import (
    MainWindow,
    _PRESET_LAYOUT_MODES,
    _PRESET_VISIBILITY_SNAPSHOT_KEY,
    _preset_layout_storage_key,
)
from tests.utils.constants import TEST_RESOURCES_PATH, RESOURCE_PATH


JSON_RECENT_FILES = ('[{"parts": ["/", "path", "to", "service-1.osz"], "json_meta": {"class": "Path", "version": 1}},'
                     '{"parts": ["/", "path", "to", "service-2.osz"], "json_meta": {"class": "Path", "version": 1}}]')

QT_QPA_PLATFORM = os.environ.get("QT_QPA_PLATFORM", "")
_MAIN_WINDOWS = []


@pytest.fixture(autouse=True)
def reset_actions_for_existing_tests(monkeypatch):
    from opal.core.common.actions import ActionList
    monkeypatch.setattr(ActionList, 'instance', None)
    monkeypatch.setattr(ActionList, 'shortcut_map', {})


@pytest.fixture
def legacy_classic_appearance(settings):
    settings.setValue('advanced/interface style', 'classic')


@pytest.fixture
def modern_appearance(settings):
    settings.setValue('advanced/interface style', 'modern')
    yield


def test_modern_window_navigation_and_spacing(modern_appearance, main_window):
    from opal.core.widgets.fluent_navigation import LayoutPresetNavigation
    assert isinstance(main_window.layout_preset_navigation, LayoutPresetNavigation)
    assert main_window.layout_preset_navigation.buttons[0].text() == 'Workspace'
    assert not main_window.layout_preset_navigation.buttons[0].icon().isNull()
    assert main_window.main_content_layout.contentsMargins().left() == 6


def test_settings_dialog_has_main_window_as_smoke_host(main_window):
    dialog = main_window.settings_form
    assert dialog.parentWidget() is main_window
    assert not dialog.isWindow()
    assert dialog.isHidden()
    assert dialog.isSmokeEnabled()


def test_legacy_classic_setting_uses_modern_layout(legacy_classic_appearance, main_window, settings):
    from opal.core.widgets.fluent_navigation import LayoutPresetNavigation
    assert isinstance(main_window.layout_preset_navigation, LayoutPresetNavigation)
    assert main_window.layout_preset_navigation.buttons[0].text() == 'Workspace'
    assert main_window.main_content_layout.contentsMargins().left() == 6
    assert main_window.dock_manager is not None
    assert settings.value('advanced/interface style') == 'modern'


def test_window_menu_is_before_help(main_window):
    menus = [action.menu() for action in main_window.menu_bar.actions()]
    assert menus[-2:] == [main_window.window_menu, main_window.help_menu]
    assert main_window.window_menu.title() == '&Window'
    assert main_window.window_menu_controller.menu is main_window.window_menu


def test_modern_presets_restore_autohide_without_touching_classic(modern_appearance, main_window, settings):
    import PySide6QtAds as ads
    main_window._preview_controller = _DummyController()
    main_window._live_controller = _DummyController()
    main_window._preview_controller.splitter = QtWidgets.QSplitter(main_window)
    main_window._live_controller.splitter = QtWidgets.QSplitter(main_window)
    settings.setValue('user interface/preset layout/default/main window state', QtCore.QByteArray(b'classic'))
    main_window.media_manager_dock.setAutoHide(True, ads.SideBarLeft)
    main_window._save_current_layout_to_preset('default')
    main_window.media_manager_dock.setAutoHide(False)
    main_window._restore_layout_from_preset('default')
    assert main_window.media_manager_dock.isAutoHide()
    assert settings.value('user interface/preset layout/default/main window state') == QtCore.QByteArray(b'classic')
    # Deferred startup correction must leave a restored ADS layout alone.
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('core/view mode', 'default')
    main_window._deferred_apply_left_column_dock_layout()
    assert main_window.media_manager_dock.isAutoHide()
    settings.setValue('advanced/interface style', 'classic')
    main_window._save_current_layout_to_preset('default')
    assert settings.value('user interface/preset layout/default/main window state') == QtCore.QByteArray(b'classic')


def test_modern_close_updates_menu_and_preserves_inactive_library(modern_appearance, main_window, settings):
    main_window.theme_manager_dock.toggleView(False)
    assert not settings.value('user interface/show themes')
    assert not main_window.view_theme_manager_item.isChecked()
    assert main_window.media_manager_dock.isDockOpen()


def test_modern_factory_layout_has_usable_library_height(modern_appearance, main_window, settings):
    main_window.resize(1200, 800)
    settings.setValue('core/view mode', 'default')
    main_window._deferred_apply_left_column_dock_layout()
    service = main_window.service_manager_dock
    library = main_window.media_manager_dock
    assert service.dockAreaWidget() is not library.dockAreaWidget()
    assert library.dockAreaWidget().currentDockWidget() is library


@pytest.mark.parametrize('width', [1000, 1200, 1600])
@pytest.mark.parametrize('mode', ['default', 'setup', 'live', 'librarysync'])
def test_factory_presets_reserve_controller_space(main_window, settings, width, mode):
    """Large Library size hints must not squeeze the controllers to slivers."""
    from opal.core.ui.advanceddocking import AdvancedDockWidget
    from opal.core.ui.slidecontroller import PreviewController, LiveController
    Registry().register('application-qt', QtWidgets.QApplication.instance())
    Registry().register('media_controller', MagicMock())

    def display_stub(parent, **kwargs):
        widget = QtWidgets.QWidget(parent)
        widget.show_display = MagicMock()
        widget.set_scale = MagicMock()
        return widget

    class WideLibrary(QtWidgets.QLabel):
        def sizeHint(self):
            return QtCore.QSize(1200, 600)

    main_window.media_manager_dock.setWidget(WideLibrary('Library'))
    main_window.cloud_library_dock = AdvancedDockWidget(main_window, 'cloud_library_dock')
    main_window.cloud_library_dock.setWidget(QtWidgets.QLabel('Cloud Library'))
    main_window.cloud_library_dock.setDockVisible(False)
    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, main_window.cloud_library_dock)
    controllers = (PreviewController(main_window), LiveController(main_window))
    for controller in controllers:
        with patch('opal.core.ui.slidecontroller.DisplayWindow', side_effect=display_stub):
            controller.setup_ui()
        main_window.dock_slide_controller(controller)
    main_window._preview_controller, main_window._live_controller = controllers
    main_window.resize(width, 800)
    QtWidgets.QWidget.setVisible(main_window, True)
    QtWidgets.QApplication.processEvents()
    main_window._activate_layout_preset(mode)
    QtWidgets.QApplication.processEvents()
    available = main_window.dock_manager.width()
    if mode == 'librarysync':
        library_width = main_window.media_manager_dock.width()
        cloud_width = main_window.cloud_library_dock.width()
        assert library_width / available == pytest.approx(0.5, abs=0.03)
        assert cloud_width / available == pytest.approx(0.5, abs=0.03)
    else:
        preview_width = main_window.preview_controller_dock.width()
        assert preview_width / available >= 0.30
        if mode != 'setup':
            live_width = main_window.live_controller_dock.width()
            assert live_width / available >= 0.30
            if mode == 'live':
                assert live_width > preview_width
            else:
                assert live_width == pytest.approx(preview_width, abs=2)
        assert main_window.service_manager_dock.width() >= 190
    measured_docks = (main_window.media_manager_dock, main_window.service_manager_dock,
                      main_window.preview_controller_dock, main_window.live_controller_dock,
                      main_window.cloud_library_dock)
    sizes = [dock.dockAreaWidget().width() for dock in measured_docks if dock.isDockOpen()]
    main_window._activate_layout_preset('live' if mode == 'default' else 'default')
    QtWidgets.QApplication.processEvents()
    main_window._activate_layout_preset(mode)
    QtWidgets.QApplication.processEvents()
    assert [dock.dockAreaWidget().width() for dock in measured_docks if dock.isDockOpen()] == \
        pytest.approx(sizes, abs=2)
    QtWidgets.QWidget.setVisible(main_window, False)


@pytest.mark.parametrize('saved_tab', [None, 'media_manager_dock', 'theme_manager_dock', 'legacy', 'detached'])
@patch('opal.core.ui.mainwindow.MainWindow._schedule_left_column_dock_layout')
def test_live_preset_groups_left_docks_and_defaults_to_service(mock_schedule, saved_tab, main_window, settings):
    """Live opens all three tabs and selects Service, including when restoring older saved layouts."""
    main_window._preview_controller = _DummyController()
    main_window._live_controller = _DummyController()
    main_window._preview_controller.splitter = QtWidgets.QSplitter(main_window)
    main_window._live_controller.splitter = QtWidgets.QSplitter(main_window)
    if saved_tab == 'detached':
        # Library Sync removes Service from the dock layout.
        main_window.removeDockWidget(main_window.service_manager_dock)
    main_window._activate_layout_preset('live')
    main_window._deferred_apply_left_column_dock_layout()
    if saved_tab and saved_tab != 'detached':
        if saved_tab == 'legacy':
            main_window._reapply_left_column_dock_layout()
            main_window.set_view_mode(False, True, False, True, True, False, 'live')
        else:
            getattr(main_window, saved_tab).raise_()
        main_window._activate_layout_preset('setup')
        main_window._deferred_apply_left_column_dock_layout()
        main_window._activate_layout_preset('live')
        main_window._deferred_apply_left_column_dock_layout()

    service = main_window.service_manager_dock
    library = main_window.media_manager_dock
    themes = main_window.theme_manager_dock
    assert set(main_window.tabifiedDockWidgets(service)) == {library, themes}
    assert all(dock.isDockOpen() for dock in (service, library, themes))
    assert all(not dock.isInFloatingContainer() for dock in (service, library, themes))
    assert service.dockAreaWidget().currentDockWidget() is service
    assert main_window._left_dock_visibility_from_settings() == (True, True, True)
    assert all(action.isChecked() for action in (main_window.view_service_manager_item,
                                               main_window.view_media_manager_item,
                                               main_window.view_theme_manager_item))


@pytest.mark.parametrize('locked', [False, True])
def test_rapid_preset_changes_finish_live_layout_before_saving(main_window, settings, locked):
    """A second selection must save the completed layout, without waiting for a zero timer."""
    from PySide6 import QtTest
    main_window._preview_controller = _DummyController()
    main_window._live_controller = _DummyController()
    main_window._preview_controller.splitter = QtWidgets.QSplitter(main_window)
    main_window._live_controller.splitter = QtWidgets.QSplitter(main_window)
    main_window.set_lock_panel(locked)
    created = QtTest.QSignalSpy(main_window.dock_manager.floatingWidgetCreated)
    for mode in ('live', 'setup', 'live', 'default', 'live') * 3:
        main_window.layout_preset_navigation.buttons[main_window._layout_preset_mode_to_tab_index(mode)].click()
        if mode == 'live':
            service = main_window.service_manager_dock
            area = service.dockAreaWidget()
            assert area is main_window.media_manager_dock.dockAreaWidget()
            assert area is main_window.theme_manager_dock.dockAreaWidget()
            assert area.currentDockWidget() is service
            assert not service.isInFloatingContainer()
    QtWidgets.QApplication.processEvents()
    assert created.count() == 0


@pytest.mark.parametrize('startup', [False, True])
def test_saved_floating_live_layout_is_repaired_before_any_window_is_shown(main_window, settings, startup):
    main_window._preview_controller = _DummyController()
    main_window._live_controller = _DummyController()
    main_window._preview_controller.splitter = QtWidgets.QSplitter(main_window)
    main_window._live_controller.splitter = QtWidgets.QSplitter(main_window)
    service = main_window.service_manager_dock
    service.setFloating(True)
    main_window.tabifyDockWidget(service, main_window.media_manager_dock)
    main_window.tabifyDockWidget(service, main_window.theme_manager_dock)
    main_window._save_current_layout_to_preset('live')
    settings.setValue('user interface/modern window state', main_window.saveState())
    main_window._reapply_left_column_dock_layout_live()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    if not startup:
        QtWidgets.QWidget.setVisible(main_window, True)
    shown = []

    class Watch(QtCore.QObject):
        def eventFilter(self, obj, event):
            if event.type() == QtCore.QEvent.Type.Show:
                shown.append(obj)
            return False

    watcher = Watch(main_window)
    main_window.dock_manager.floatingWidgetCreated.connect(lambda floating: floating.installEventFilter(watcher))
    if startup:
        settings.setValue('core/view mode', 'live')
        settings.setValue('user interface/is preset layout', True)
        settings.setValue(_preset_layout_storage_key('live', 'main window state'), QtCore.QByteArray())
        main_window.load_settings()
        QtWidgets.QWidget.setVisible(main_window, True)
    else:
        main_window._activate_layout_preset('live')
    QtWidgets.QApplication.processEvents()
    assert not shown
    assert not service.isInFloatingContainer()
    assert main_window.dock_manager.isVisible()
    QtWidgets.QWidget.setVisible(main_window, False)


class _DummyRenderer:
    def __init__(self, *args, **kwargs):
        pass


class _DummyPluginForm:
    def __init__(self, *args, **kwargs):
        pass


class _DummyAction:
    def __init__(self, name=''):
        self._name = name
        self.triggered = MagicMock()

    def setObjectName(self, name):
        self._name = name

    def objectName(self):
        return self._name

    def setMenuRole(self, role):
        self.menu_role = role

    def setChecked(self, checked):
        self.checked = checked

    def setEnabled(self, enabled):
        self.enabled = enabled


class _DummyActionGroup:
    def __init__(self, *args, **kwargs):
        self._actions = []
        self.triggered = _DummySignal()

    def addAction(self, action):
        self._actions.append(action)

    def actions(self):
        return list(self._actions)

    def setExclusive(self, exclusive):
        self.exclusive = exclusive

    def setObjectName(self, name):
        self.object_name = name


class _DummySplitter:
    def restoreState(self, state):
        self.state = state

    def setChildrenCollapsible(self, collapsible):
        self.collapsible = collapsible


class _DummyPanel:
    def setVisible(self, visible):
        self.visible = visible


class _DummySignal:
    def connect(self, slot):
        self.slot = slot


class _DummyScreenApplication:
    def __init__(self, screen):
        self._screen = screen
        self.primaryScreenChanged = _DummySignal()
        self.screenAdded = _DummySignal()
        self.screenRemoved = _DummySignal()

    def screens(self):
        return [self._screen]

    def primaryScreen(self):
        return self._screen


class _DummyController:
    def __init__(self):
        self.splitter = _DummySplitter()
        self.panel = _DummyPanel()


def _create_mock_action(parent, name, **kwargs):
    """
    Create a fake action with some "real" attributes
    """
    action_parent = parent if isinstance(parent, QtCore.QObject) else None
    action = QtGui.QAction(action_parent)
    action.setObjectName(name)
    action.setText(kwargs.get('text', ''))
    action.setEnabled(kwargs.get('enabled', True))
    action.setCheckable(kwargs.get('checkable', False))
    if 'checked' in kwargs:
        action.setCheckable(True)
        action.setChecked(kwargs['checked'])
    if kwargs.get('triggers'):
        action.triggered.connect(kwargs.pop('triggers'))
    return action


@pytest.fixture()
def main_window(state, settings, qapp, request):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, True)
    app = Registry().get('application')
    app.set_busy_cursor = lambda: None
    app.set_normal_cursor = lambda: None
    app.process_events = lambda: None
    app.args = []
    feature_options = getattr(request, 'param', {})
    for name in ('projector', 'remote_interface'):
        if feature_options.get(name):
            settings.setValue(f'{name}/status', PluginStatus.Active)
    Registry().set_flag('no_web_server', feature_options.get('no_web_server', True))
    add_toolbar_action_patcher = patch('opal.core.ui.mainwindow.create_action', new=_create_mock_action)
    add_toolbar_action_patcher.start()
    plugin_form_patcher = patch('opal.core.ui.mainwindow.PluginForm', new=_DummyPluginForm)
    plugin_form_patcher.start()
    renderer_patcher = patch('opal.core.display.render.Renderer', new=_DummyRenderer)
    renderer_patcher.start()
    action_group_patcher = patch('opal.core.ui.mainwindow.QtGui.QActionGroup', new=_DummyActionGroup)
    action_group_patcher.start()
    qmainwindow_show_patcher = patch('opal.core.ui.mainwindow.QtWidgets.QWidget.show', lambda *_: None)
    qmainwindow_show_patcher.start()
    qmainwindow_show_minimised_patcher = patch('opal.core.ui.mainwindow.QtWidgets.QWidget.showMinimized',
                                               lambda *_: None)
    qmainwindow_show_minimised_patcher.start()
    mocked_screen = MagicMock()
    mocked_screen.geometry.return_value = QtCore.QRect(0, 0, 1024, 768)
    ScreenList.create(_DummyScreenApplication(mocked_screen))
    mainwindow = MainWindow()
    mainwindow.activateWindow = lambda: None
    _MAIN_WINDOWS.append(mainwindow)
    yield mainwindow
    renderer_patcher.stop()
    plugin_form_patcher.stop()
    action_group_patcher.stop()
    qmainwindow_show_minimised_patcher.stop()
    qmainwindow_show_patcher.stop()
    add_toolbar_action_patcher.stop()
    _MAIN_WINDOWS.remove(mainwindow)
    mainwindow.deleteLater()


@pytest.fixture()
def main_window_reduced(main_window):
    return main_window


def test_cmd_line_file(main_window):
    """
    Test that passing a service file from the command line loads the service.
    """
    # GIVEN a service as an argument to openlp
    service = os.path.join(TEST_RESOURCES_PATH, 'service', 'test.osz')

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file:
        main_window.open_cmd_line_files([service])

    # THEN the service from the arguments is loaded
    mocked_load_file.assert_called_with(Path(service))


def test_cmd_line_file_encoded(main_window):
    """
    Test that passing a service file from the command line loads the service where extra encoded quotes are added
    """
    # GIVEN a service as an argument to openlp
    service_base = os.path.join(TEST_RESOURCES_PATH, 'service', 'test.osz')
    service = f'&quot;{service_base}&quot;'

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file:
        main_window.open_cmd_line_files([service])

    # THEN the service from the arguments is loaded
    mocked_load_file.assert_called_with(Path(service_base))


def test_cmd_line_arg_no_service(main_window):
    """
    Test that passing no service file does nothing.
    """
    # GIVEN a command line argument for openlp
    args = ['--disable-web-security']

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file:
        main_window.open_cmd_line_files(args)

        # THEN the file should not be opened
        assert mocked_load_file.called is False, 'load_file should not have been called'


def test_cmd_line_arg_not_service_file(main_window):
    """
    Test that passing a file that is not a service does nothing.
    """
    # GIVEN a non service file as an argument to openlp
    args = ['run_opal_presenter.py']

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file, \
            patch.object(main_window, 'log_error') as mocked_log_error:
        main_window.open_cmd_line_files(args)

        # THEN the file should not be opened
        assert mocked_load_file.called is False, 'load_file should not have been called'
        mocked_log_error.assert_not_called()


def test_cmd_line_arg_service_file_does_not_exist(main_window):
    """
    Test that passing a file that does not exist does nothing.
    """
    # GIVEN a service file that does not exist
    args = ['Service 2022-02-06.osz']

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file:
        main_window.open_cmd_line_files(args)

        # THEN the file should not be opened
        assert mocked_load_file.called is False, 'load_file should not have been called'


def test_cmd_line_arg_other_args(main_window):
    """
    Test that passing a service file with other command line arguments still opens the file
    """
    # GIVEN a valid existing service file and a command line argument
    service_file = os.path.join(TEST_RESOURCES_PATH, 'service', 'test.osz')
    args = ['--disable-web-security', service_file]

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file:
        main_window.open_cmd_line_files(args)

        # THEN the file should not be opened
        assert mocked_load_file.called is True, 'load_file should have been called'
        mocked_load_file.assert_called_with(Path(service_file))


@patch('opal.core.ui.mainwindow.resolve')
def test_cmd_line_filename_with_spaces(mocked_resolve, main_window):
    """
    Test that a service file with spaces that split across arguments loads the file properly
    """
    # GIVEN a set of arguments with a file separated by spaces
    mocked_path_is_file = MagicMock(**{'is_file.return_value': True, 'suffix': '.osz'})
    mocked_resolve.side_effect = [FileNotFoundError, FileNotFoundError, FileNotFoundError, mocked_path_is_file]
    args = ['Service', '2022-02-06.osz']

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file:
        main_window.open_cmd_line_files(args)

        # THEN the file should be looked for
        assert mocked_resolve.call_count == 4
        mocked_load_file.assert_called_with(mocked_path_is_file)


@patch('opal.core.ui.mainwindow.resolve')
def test_cmd_line_filename_with_spaces_and_security(mocked_resolve, main_window):
    """
    Test that passing a service file with spaces and a command line argument loads properly
    """
    # GIVEN a set of arguments with a file separated by spaces
    mocked_path_is_file = MagicMock(**{'is_file.return_value': True, 'suffix': '.osz'})
    mocked_resolve.side_effect = [FileNotFoundError, FileNotFoundError, FileNotFoundError, mocked_path_is_file]
    args = ['--disable-web-security', 'Service', '2022-02-06.osz']

    # WHEN the argument is processed
    with patch.object(main_window.service_manager, 'load_file') as mocked_load_file:
        main_window.open_cmd_line_files(args)

        # THEN the file should be looked for
        assert mocked_resolve.call_count == 4
        mocked_load_file.assert_called_with(mocked_path_is_file)


def test_main_window_title(main_window):
    """
    Test that running a new instance of OpenLP set the window title correctly
    """
    # GIVEN a newly opened OpenLP instance

    # WHEN no changes are made to the service

    # THEN the main window's title should be the same as the OpenLP string in the UiStrings class
    assert main_window.windowTitle() == UiStrings().OpenLP, \
        'The main window\'s title should be the same as the OpenLP string in UiStrings class'


def test_set_service_modified(main_window):
    """
    Test that when setting the service's title the main window's title is set correctly
    """
    # GIVEN a newly opened OpenLP instance

    # WHEN set_service_modified is called with with the modified flag set true and a file name
    main_window.set_service_modified(True, 'test.osz')

    # THEN the main window's title should be set to the
    assert main_window.windowTitle(), '%s - %s*' % (UiStrings().OpenLP, 'test.osz') == \
        'The main window\'s title should be set to "<the contents of UiStrings().OpenLP> - test.osz*"'


def test_set_service_unmodified(main_window):
    """
    Test that when setting the service's title the main window's title is set correctly
    """
    # GIVEN a newly opened OpenLP instance

    # WHEN set_service_modified is called with with the modified flag set False and a file name
    main_window.set_service_modified(False, 'test.osz')

    # THEN the main window's title should be set to the
    assert main_window.windowTitle(), '%s - %s' % (UiStrings().OpenLP, 'test.osz') == \
        'The main window\'s title should be set to "<the contents of UiStrings().OpenLP> - test.osz"'


@pytest.mark.skipif(QT_QPA_PLATFORM in ['offscreen', 'wayland'] or os.name != 'nt',
                    reason='This test is stable only on Windows desktop backends')
def test_load_settings_position_valid(main_window, settings):
    """
    Test that the position of the main window is restored when it's valid
    """
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = _DummySplitter()
    main_window._live_controller = _DummyController()
    main_window._preview_controller = _DummyController()
    # set up a window position and geometry to use in the settings
    main_window.move(QtCore.QPoint(10, 10))
    main_window.resize(1000, 500)
    # need to call show() to ensure the geometry works as expected
    # unfortunately this seems to work on Windows only, not on linux
    main_window.show()
    main_window.hide()
    # store the values in the settings
    settings.setValue('user interface/main window position', main_window.pos())
    settings.setValue('user interface/main window geometry', main_window.saveGeometry())
    settings.setValue('user interface/modern window state', main_window.saveState())
    # change the position and size - then we can test if load_settings() sets it back correctly
    main_window.move(QtCore.QPoint(20, 20))
    main_window.resize(500, 300)

    # WHEN the settings are loaded
    main_window.load_settings()

    # THEN the main window's position and geometry should be set to the saved setting
    # on linux the tests works for the x position only
    assert main_window.pos().x() == 10


@pytest.mark.skipif(QT_QPA_PLATFORM == 'offscreen' or os.name != 'nt',
                    reason='This test is stable only on Windows desktop backends')
def test_load_settings_position_invalid(main_window, settings):
    """
    Test that the position of the main window is not restored when it's invalid, but rather set to (0, 0)
    """
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = _DummySplitter()
    main_window._live_controller = _DummyController()
    main_window._preview_controller = _DummyController()
    # set up a window position outside the parameters of the main_window fixture
    # this can represent a monitor positioned above the primary display, but which has been unplugged
    main_window.move(QtCore.QPoint(-100, -800))
    main_window.resize(1000, 500)
    # need to call show() to ensure the geometry works as expected (works on Windows, but not linux)
    main_window.show()
    main_window.hide()
    # store the values in the settings
    settings.setValue('user interface/main window position', main_window.pos())
    settings.setValue('user interface/main window geometry', main_window.saveGeometry())
    settings.setValue('user interface/modern window state', main_window.saveState())
    # change the position and size
    main_window.move(QtCore.QPoint(20, 20))
    main_window.resize(500, 300)

    # WHEN the settings are loaded
    main_window.load_settings()

    # THEN the main window's position should be a valid position such as (0, 0) or another valid postion,
    #      depending on the window system.
    # -202 is the value our GitLab CI/CD pipeline returns.
    assert main_window.pos().x() >= -202
    assert main_window.pos().y() >= -0


def test_mainwindow_configuration(main_window):
    """
    Check that the Main Window initialises the Registry Correctly
    """
    # GIVEN: A built main window

    # WHEN: you check the started functions

    # THEN: the following registry functions should have been registered
    expected_service_list = {'settings', 'settings_thread', 'application', 'main_window', 'settings_form',
                             'service_manager', 'theme_manager', 'projector_manager', 'http_server',
                             'authentication_token', 'web_socket_server'}
    expected_functions_list = ['bootstrap_post_set_up', 'bootstrap_initialise', 'bootstrap_completion',
                               'config_screen_changed', 'theme_change_global']
    assert set(Registry().service_list.keys()) == expected_service_list, \
        'The service list should have been {}'.format(Registry().service_list.keys())
    assert list(Registry().functions_list.keys()) == expected_functions_list, \
        'The function list should have been {}'.format(Registry().functions_list.keys())
    assert 'application' in Registry().service_list, 'The application should have been registered.'
    assert 'main_window' in Registry().service_list, 'The main_window should have been registered.'
    assert 'settings' in Registry().service_list, 'The settings should have been registered.'


def test_escape_hides_native_show_even_when_openlp_display_is_hidden():
    from opal.core.ui import HideMode

    main_window = MagicMock()
    live = main_window.live_controller
    live.display.isVisible.return_value = False
    live.current_hide_mode = None
    with patch.object(QtWidgets.QApplication, 'activeModalWidget', return_value=None), \
            patch.object(QtWidgets.QApplication, 'focusWidget', return_value=None):
        MainWindow._on_escape_hide_presentation_from_main(main_window)

    live.set_hide_mode.assert_called_once_with(HideMode.Screen)


@pytest.mark.parametrize('always_on_top', [False, True])
def test_switch_projection_to_main_keeps_output_visible(always_on_top):
    """The switch action brings the controls forward without changing the hide mode."""
    main_window = MagicMock()
    main_window.isMinimized.return_value = False
    main_window.settings.value.return_value = always_on_top
    main_window.live_controller.current_hide_mode = None
    main_window.live_controller.display.isVisible.return_value = True
    main_window._projection_topmost_suspended = False
    display = main_window.live_controller.display
    with patch('opal.core.ui.mainwindow.ScreenList', return_value=[object()]), \
            patch.object(QtWidgets.QApplication, 'activeModalWidget', return_value=None), \
            patch.object(QtWidgets.QApplication, 'activeWindow', return_value=display):
        MainWindow.on_switch_projection_window(main_window)

    main_window.raise_.assert_called_once_with()
    main_window.activateWindow.assert_called_once_with()
    main_window.live_controller.set_hide_mode.assert_not_called()
    display.hide.assert_not_called()
    if always_on_top:
        main_window._set_projection_windows_topmost.assert_called_once_with(False)
    else:
        main_window._set_projection_windows_topmost.assert_not_called()


def test_switch_main_to_projection_restores_topmost_setting():
    """Switching back to projection restores its configured stacking when it was suspended."""
    main_window = MagicMock()
    main_window.live_controller.current_hide_mode = None
    main_window.live_controller.display.isVisible.return_value = True
    main_window._projection_topmost_suspended = True
    display = main_window.live_controller.display
    with patch('opal.core.ui.mainwindow.ScreenList', return_value=[object()]), \
            patch.object(QtWidgets.QApplication, 'activeModalWidget', return_value=None), \
            patch.object(QtWidgets.QApplication, 'activeWindow', return_value=main_window):
        MainWindow.on_switch_projection_window(main_window)

    main_window._set_projection_windows_topmost.assert_called_once_with(True)
    display.raise_.assert_called_once_with()
    display.activateWindow.assert_called_once_with()
    main_window.live_controller.set_hide_mode.assert_not_called()


def test_projection_topmost_can_be_temporarily_suspended(qapp):
    """The switch action changes Qt stacking without changing the saved preference."""
    main_window = MagicMock()
    display = QtWidgets.QWidget()
    display.setWindowFlags(QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.WindowStaysOnTopHint)
    main_window.live_controller.display = display
    main_window.live_controller.media_widget = None

    MainWindow._set_projection_windows_topmost(main_window, False)
    assert not display.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint
    assert main_window._projection_topmost_suspended is True

    MainWindow._set_projection_windows_topmost(main_window, True)
    assert display.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint
    assert main_window._projection_topmost_suspended is False


def test_projection_switch_action_is_available_from_view_menu(main_window, settings):
    from opal.core.ui import HideMode

    action = main_window.view_switch_projection_item

    assert action in main_window.view_menu.actions()
    assert action.text() == 'Toggle display output'
    assert settings.get_default_value('shortcuts/viewSwitchProjectionItem')
    live = MagicMock()
    live.is_live = True
    live.current_hide_mode = None
    live.is_desktop_hide_available.return_value = True
    main_window._live_controller = live
    with patch('opal.core.ui.mainwindow.ScreenList', return_value=[object()]):
        main_window._sync_view_display_output_menu_action()
        assert action.isEnabled()
        live.current_hide_mode = HideMode.Screen
        main_window._sync_view_display_output_menu_action()
        assert not action.isEnabled()
    assert action.isVisible()
    with patch('opal.core.ui.mainwindow.ScreenList', return_value=[object(), object()]):
        main_window._sync_view_display_output_menu_action()
    assert not action.isVisible()


def test_projector_manager_hidden_on_startup(main_window):
    """
    Test that the projector manager is hidden on startup
    """
    # GIVEN: A built main window
    # WHEN: OpenLP is started
    # THEN: The projector manager should be hidden
    assert main_window.projector_manager_dock.isVisible() is False


def test_on_search_shortcut_triggered_shows_media_manager(main_window):
    """
    Test that the media manager is made visible when the search shortcut is triggered
    """
    # GIVEN: A build main window set up for testing
    with patch.object(main_window, 'media_manager_dock') as mocked_media_manager_dock, \
            patch.object(main_window, 'media_tool_box') as mocked_media_tool_box:
        mocked_media_manager_dock.isVisible.return_value = False
        mocked_media_tool_box.currentWidget.return_value = None

        # WHEN: The search shortcut is triggered
        main_window.on_search_shortcut_triggered()

        # THEN: The media manager dock is made visible
        mocked_media_manager_dock.setVisible.assert_called_with(True)


def test_on_search_shortcut_triggered_focuses_widget(main_window):
    """
    Test that the focus is set on the widget when the search shortcut is triggered
    """
    # GIVEN: A build main window set up for testing
    with patch.object(main_window, 'media_manager_dock') as mocked_media_manager_dock, \
            patch.object(main_window, 'media_tool_box') as mocked_media_tool_box:
        mocked_media_manager_dock.isVisible.return_value = True
        mocked_widget = MagicMock()
        mocked_media_tool_box.currentWidget.return_value = mocked_widget

        # WHEN: The search shortcut is triggered
        main_window.on_search_shortcut_triggered()

        # THEN: The media manager dock is made visible
        assert 0 == mocked_media_manager_dock.setVisible.call_count
        mocked_widget.on_focus.assert_called_with()


@patch('opal.core.ui.mainwindow.FirstTimeForm')
@patch('opal.core.ui.mainwindow.QtWidgets.QMessageBox.warning')
def test_on_first_time_wizard_clicked_show_projectors_after(mocked_warning, MockWizard, main_window):
    """Test that the projector manager is shown after the FTW is run"""
    # GIVEN: Main_window, patched things, patched "Yes" as confirmation to re-run wizard, settings to True.
    mocked_warning.return_value = QtWidgets.QMessageBox.StandardButton.Yes
    MockWizard.return_value.was_cancelled = False
    MockWizard.return_value.opal_imported_library = None
    main_window.settings.setValue('projector/show after wizard', True)
    Registry().set_flag('projector_disabled', False)

    with patch.object(main_window, 'projector_manager_dock') as mocked_dock, \
            patch.object(Registry(), 'execute'), patch.object(main_window, 'theme_manager_contents') as theme_manager:
        # WHEN: on_first_time_wizard_clicked is called
        main_window.on_first_time_wizard_clicked()

    # THEN: projector_manager_dock.setVisible should had been called once
    mocked_dock.setVisible.assert_called_once_with(True)
    theme_manager.load_themes.assert_called_once()
    theme_manager.load_first_time_themes.assert_not_called()


@patch('opal.core.ui.mainwindow.FirstTimeForm')
@patch('opal.core.ui.mainwindow.QtWidgets.QMessageBox.warning')
def test_on_first_time_wizard_clicked_hide_projectors_after(mocked_warning, MockWizard, main_window):
    """Test that the projector manager is hidden after the FTW is run"""
    # GIVEN: Main_window, patched things, patched "Yes" as confirmation to re-run wizard, settings to False.
    mocked_warning.return_value = QtWidgets.QMessageBox.StandardButton.Yes
    MockWizard.return_value.was_cancelled = False
    MockWizard.return_value.opal_imported_library = None
    main_window.settings.setValue('projector/show after wizard', False)

    # WHEN: on_first_time_wizard_clicked is called
    with patch.object(main_window, 'projector_manager_dock') as mocked_dock, \
            patch.object(Registry(), 'execute'), patch.object(main_window, 'theme_manager_contents'):
        main_window.on_first_time_wizard_clicked()

    # THEN: projector_manager_dock.setVisible should had been called once
    mocked_dock.setVisible.assert_called_once_with(False)


def test_opal_wizard_library_switch_waits_for_shutdown(main_window, tmp_path):
    opal_current_path = tmp_path / 'current'
    opal_imported_path = tmp_path / 'imported'
    main_window.settings.setValue('advanced/data path', opal_current_path)
    with patch('opal.core.ui.mainwindow.FirstTimeForm') as opal_wizard, \
            patch.object(QtWidgets.QMessageBox, 'warning', return_value=QtWidgets.QMessageBox.StandardButton.Yes), \
            patch.object(QtWidgets.QMessageBox, 'information'), \
            patch.object(main_window.application, 'request_restart') as opal_restart, \
            patch.object(main_window, 'theme_manager_contents') as opal_themes:
        opal_wizard.return_value.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
        opal_wizard.return_value.opal_imported_library = opal_imported_path
        main_window.on_first_time_wizard_clicked()
    assert main_window.new_data_path == opal_imported_path
    assert not main_window.copy_data
    assert not main_window.settings_replaced
    assert main_window.settings.value('advanced/data path') == opal_current_path
    opal_restart.assert_called_once()
    opal_themes.load_themes.assert_not_called()
    with patch('opal.core.ui.mainwindow.shutil.copytree') as opal_copy:
        main_window.change_data_directory()
    opal_copy.assert_not_called()
    assert main_window.settings.value('advanced/data path') == opal_imported_path


def test_increment_progress_bar_default_increment(main_window):
    """
    Test that increment_progress_bar increments the progress bar by 1 when called without the `increment` arg.
    """
    # GIVEN: A mocked progress bar
    with patch.object(main_window, 'load_progress_bar', **{'value.return_value': 0}) as mocked_progress_bar:

        # WHEN: Calling increment_progress_bar without the `increment` arg
        main_window.increment_progress_bar()

    # THEN: The progress bar value should have been incremented by 1
    mocked_progress_bar.setValue.assert_called_once_with(1)


def test_increment_progress_bar_custom_increment(main_window):
    """
    Test that increment_progress_bar increments the progress bar by the `increment` arg when called with the
    `increment` arg with a set value.
    """
    # GIVEN: A mocked progress bar
    with patch.object(main_window, 'load_progress_bar', **{'value.return_value': 0}) as mocked_progress_bar:

        # WHEN: Calling increment_progress_bar with `increment` set to 10
        main_window.increment_progress_bar(increment=10)

    # THEN: The progress bar value should have been incremented by 10
    mocked_progress_bar.setValue.assert_called_once_with(10)


def test_eventFilter(main_window):
    """
    Test the reimplemented event method
    """
    # GIVEN: A file path and a QEvent.
    file_path = str(RESOURCE_PATH / 'church.jpg')
    mocked_file_method = MagicMock(return_value=file_path)
    event = QtCore.QEvent(QtCore.QEvent.Type.FileOpen)
    event.file = mocked_file_method

    # WHEN: Call the vent method.
    result = main_window.eventFilter(MagicMock(), event)

    # THEN: The path should be inserted.
    assert result is True, "The method should have returned True."
    mocked_file_method.assert_called_once_with()
    assert Registry().get('application').args[0] == file_path, "The path should be in args."


@patch('opal.core.ui.mainwindow.is_macosx')
@pytest.mark.skipif(QT_QPA_PLATFORM in ['offscreen', 'wayland'] or os.name != 'nt',
                    reason='Window minimisation behaviour is unstable on non-Windows test backends')
def test_application_activate_event(mocked_is_macosx, main_window):
    """
    Test that clicking on the dock icon on Mac OS X restores the main window if it is minimized
    """
    # GIVEN: Mac OS X and an ApplicationActivate event
    mocked_is_macosx.return_value = True
    event = QtCore.QEvent(QtCore.QEvent.Type.ApplicationActivate)
    main_window.showMinimized()

    # WHEN: The icon in the dock is clicked
    result = main_window.eventFilter(MagicMock(), event)

    # THEN:
    assert result is True, "The method should have returned True."
    assert main_window.isMinimized() is False


@patch('opal.core.app.QtWidgets.QMessageBox.critical')
@patch('opal.core.common.applocation.AppLocation.get_data_path')
@patch('opal.core.common.applocation.AppLocation.get_directory')
def test_change_data_directory(mocked_get_directory, mocked_get_data_path, mocked_critical_box, main_window):
    """
    Test that changing the data directory works if the folder already exists
    """
    # GIVEN: an existing old and new data directory.
    temp_folder = Path(mkdtemp())
    mocked_get_data_path.return_value = temp_folder
    main_window.copy_data = True
    temp_new_data_folder = Path(mkdtemp())
    main_window.new_data_path = temp_new_data_folder

    # WHEN: running change_data_directory
    result = main_window.change_data_directory()

    # THEN: No error shouuld have occured
    assert result is not False
    mocked_critical_box.assert_not_called()

    # Clean up
    rmtree(temp_folder)
    rmtree(temp_new_data_folder)


def test_restore_current_media_manager_item(main_window_reduced):
    """
    Regression test for bug #1152509.
    """
    # The last-used Library tab is always restored.
    main_window_reduced.settings.setValue('advanced/current media plugin', 2)
    main_window_reduced.media_tool_box.setCurrentIndex = MagicMock()

    # WHEN: Call the restore method.
    main_window_reduced.restore_current_media_manager_item()

    # THEN: The current widget should have been set.
    main_window_reduced.media_tool_box.setCurrentIndex.assert_called_with(2)


def test_set_lock_panel_locked(main_window_reduced):
    """
    Projector Manager enable UI options -  bug #1390702
    """
    # GIVEN: A mocked projector manager dock item:
    # WHEN: main_window.set_lock_panel is called
    main_window_reduced.set_lock_panel(True)

    # THEN: Projector manager dock should have been called with disable UI features
    from PySide6QtAds import ads
    no_dock_features = ads.CDockWidget.DockWidgetFeature.NoDockWidgetFeatures
    assert main_window_reduced.theme_manager_dock.features() == no_dock_features
    assert main_window_reduced.service_manager_dock.features() == no_dock_features
    assert main_window_reduced.media_manager_dock.features() == no_dock_features
    assert main_window_reduced.projector_manager_dock.features() == no_dock_features


def test_set_lock_panel_unlocked(main_window_reduced):
    """
    Projector Manager disable UI options -  bug #1390702
    """
    # GIVEN: A mocked projector manager dock item:
    # WHEN: main_window.lock_panel action is triggered
    main_window_reduced.set_lock_panel(False)

    # THEN: Projector manager dock should have been called with enable UI features
    from PySide6QtAds import ads
    all_dock_features = (ads.CDockWidget.DockWidgetFeature.DockWidgetClosable |
                        ads.CDockWidget.DockWidgetFeature.DockWidgetFloatable |
                        ads.CDockWidget.DockWidgetFeature.DockWidgetMovable |
                        ads.CDockWidget.DockWidgetFeature.DockWidgetPinnable |
                        ads.CDockWidget.DockWidgetFeature.DockWidgetFocusable)
    assert main_window_reduced.theme_manager_dock.features() == all_dock_features
    assert main_window_reduced.service_manager_dock.features() == all_dock_features
    assert main_window_reduced.media_manager_dock.features() == all_dock_features
    assert main_window_reduced.projector_manager_dock.features() == all_dock_features


@patch('opal.core.ui.mainwindow.MainWindow.open_cmd_line_files')
@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_show_cmd_line_args(mocked_view_mode, mocked_open_cmd_line_files, main_window, settings):
    """Test that command line arguments are loaded on show"""
    # GIVEN: A newly opened OpenLP instance with some command line arguments
    main_window.application.args = ['-disable-web-security', 'new_file_name.osz']

    # WHEN: MainWindow.show() is called
    main_window.show()

    # THEN: The command line arguments are searched for a file name
    mocked_open_cmd_line_files.assert_called_once_with(main_window.application.args)


@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_show_load_last_file(mocked_view_mode, main_window, settings):
    """Test that the last file opened is loaded on show"""
    # GIVEN: A newly opened OpenLP instance with some command line arguments
    main_window.service_manager_contents.load_last_file = MagicMock()
    main_window.settings.setValue('core/auto open', True)

    # WHEN: MainWindow.show() is called
    main_window.show()

    # THEN: The command line arguments are searched for a file name
    main_window.service_manager_contents.load_last_file.assert_called_once_with()


@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_load_settings_custom_layout(mocked_view_mode, main_window, settings):
    """Test that the view mode is called with the correct parameters for default mode"""
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window.activateWindow = MagicMock()
    main_window.settings.setValue('core/view mode', 'default')
    main_window.settings.setValue('user interface/is preset layout', False)
    main_window.settings.setValue('user interface/show library', True)
    main_window.settings.setValue('user interface/show service', False)
    main_window.settings.setValue('user interface/show themes', True)
    main_window.settings.setValue('user interface/show projectors', False)
    main_window.settings.setValue('user interface/live panel', True)
    main_window.settings.setValue('user interface/preview panel', False)

    # WHEN: we call to show method
    main_window.show()

    # THEN:
    # The default mode should have been called.
    mocked_view_mode.assert_called_with(True, False, True, False, True, False)


@patch('opal.core.ui.mainwindow.QtWidgets.QWidget.show')
@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_load_settings_view_mode_default_mode(mocked_view_mode, mocked_show, main_window, settings):
    """
    Test that the view mode is called with the correct parameters for default mode
    """
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window.activateWindow = MagicMock()
    main_window.settings.setValue('core/view mode', 'default')
    main_window.settings.setValue('user interface/is preset layout', True)

    # WHEN: we call to show method
    main_window.show()

    # THEN:
    # The default mode should have been called.
    mocked_view_mode.assert_called_with(True, True, True, True, True, False, 'default')


@patch('opal.core.ui.mainwindow.QtWidgets.QWidget.show')
@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_load_settings_view_mode_setup_mode(mocked_view_mode, mocked_show, main_window, settings):
    """
    Test that the view mode is called with the correct parameters for setup mode

    Note: for some reason, only when the test is running, the QWidget.show() method resets the layout setting,
          so this is mocked out to prevent it from interferring in the loading of the view layout
    """
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window.settings.setValue('core/view mode', 'setup')
    main_window.settings.setValue('user interface/is preset layout', True)

    # WHEN: we call to show method
    main_window.show()

    # THEN:
    # The default mode should have been called.
    mocked_view_mode.assert_called_with(True, True, True, True, False, False, 'setup')


@patch('opal.core.ui.mainwindow.QtWidgets.QWidget.show')
@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_load_settings_view_mode_live_mode(mocked_view_mode, mocked_show, main_window, settings):
    """
    Test that the view mode is called with the correct parameters for live mode

    Note: for some reason, only when the test is running, the QWidget.show() method resets the layout setting,
          so this is mocked out to prevent it from interferring in the loading of the view layout
    """
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window.settings.setValue('core/view mode', 'live')
    main_window.settings.setValue('user interface/is preset layout', True)

    # WHEN: we call to show method
    main_window.show()

    # THEN:
    # The default mode should have been called.
    mocked_view_mode.assert_called_with(True, True, True, True, True, False, 'live')


@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_load_settings_view_mode_preview(mocked_view_mode, main_window, settings):
    """
    Test that the view mode is called with the correct parameters for default
    """
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window.activateWindow = MagicMock()
    main_window.settings.setValue('core/view mode', 'default')
    main_window.settings.setValue('user interface/is preset layout', False)
    main_window.settings.setValue('user interface/preview panel', False)

    # WHEN: we call to show method
    main_window.show()

    # THEN:
    # The default mode should have been called.
    mocked_view_mode.assert_called_with(True, True, True, False, True, False)


@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_load_settings_view_mode_live(mocked_view_mode, main_window, settings):
    """
    Test that the view mode is called with the correct parameters for default
    """
    # GIVEN a newly opened OpenLP instance, mocked screens and settings for a valid window position
    # mock out some other calls in load_settings()
    main_window.control_splitter = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window.activateWindow = MagicMock()
    main_window.settings.setValue('core/view mode', 'default')
    main_window.settings.setValue('user interface/is preset layout', False)
    main_window.settings.setValue('user interface/live panel', False)

    # WHEN: we call to show method
    main_window.show()

    # THEN:
    # The default mode should have been called.
    mocked_view_mode.assert_called_with(True, True, True, True, False, False)


def test_left_dock_visibility_recover_themes_only_corruption(main_window, settings):
    """
    Tabified docks used to persist only ``show themes``; recover to all three panes intended for the layout.
    """
    settings.setValue('user interface/show library', False)
    settings.setValue('user interface/show service', False)
    settings.setValue('user interface/show themes', True)
    settings.setValue('user interface/is preset layout', False)
    assert main_window._left_dock_visibility_from_settings() == (True, True, True)


def test_set_view_mode_named_preset_keeps_is_preset_layout_flag(main_window, settings):
    """
    Preview/Live visibility updates must not clear the layout-preset flag when applying a named preset.
    """
    main_window._preview_controller = MagicMock()
    main_window._preview_controller.panel = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._live_controller.panel = MagicMock()
    settings.setValue('user interface/is preset layout', False)
    main_window.set_view_mode(True, True, True, True, True, False, 'default')
    assert settings.value('user interface/is preset layout') is True


def test_left_dock_visibility_named_live_preset_without_saved_uses_factory(main_window, settings):
    """
    Live preset without a saved window state still forces the built-in Library/Service/Themes visibility.
    """
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('core/view mode', 'live')
    settings.setValue('user interface/modern preset layout/live/main window state', QtCore.QByteArray())
    settings.setValue('user interface/show library', False)
    settings.setValue('user interface/show themes', False)
    assert main_window._left_dock_visibility_from_settings() == (True, True, True)


def test_left_dock_visibility_named_preset_with_saved_uses_settings(main_window, settings):
    """
    Once a preset has saved layout state, left-pane visibility follows stored settings (user customisation).
    """
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('core/view mode', 'setup')
    settings.setValue('user interface/modern preset layout/setup/main window state', QtCore.QByteArray(b'1'))
    settings.setValue('user interface/show library', True)
    settings.setValue('user interface/show service', False)
    settings.setValue('user interface/show themes', True)
    assert main_window._left_dock_visibility_from_settings() == (True, False, True)


def test_layout_preset_tab_bar_has_expected_tabs(main_window):
    """The sidebar and View menu use matching Workspace, Prepare and Live labels."""
    assert len(main_window.layout_preset_navigation.buttons) == 4
    assert main_window.layout_preset_navigation.buttons[0].text() == 'Workspace'
    assert main_window.layout_preset_navigation.buttons[1].text() == 'Prepare'
    assert main_window.layout_preset_navigation.buttons[2].text() == 'Live'
    assert main_window.layout_preset_navigation.buttons[3].text() == 'Library Sync'
    assert main_window.mode_default_item.text() == '&Workspace'
    assert main_window.mode_setup_item.text() == '&Prepare'
    assert main_window.mode_live_item.text() == '&Live'


def _check_library_sync_preset(main_window, settings):
    from opal.plugins.librarysync.librarysyncplugin import LibrarySyncPlugin
    main_window._preview_controller = _DummyController()
    main_window._live_controller = _DummyController()
    plugin = LibrarySyncPlugin()
    main_window._preview_controller.splitter = QtWidgets.QSplitter(main_window)
    main_window._live_controller.splitter = QtWidgets.QSplitter(main_window)
    assert plugin in State().list_plugins()
    plugin.initialise()
    assert main_window.cloud_library_dock.widget() is plugin.panel
    main_window._activate_layout_preset('librarysync')
    main_window._deferred_apply_left_column_dock_layout()
    assert settings.value('core/view mode') == 'librarysync'
    assert main_window._left_dock_visibility_from_settings() == (True, False, True)
    assert not settings.value('user interface/preview panel')
    assert not settings.value('user interface/live panel')
    assert main_window.theme_manager_dock in main_window.tabifiedDockWidgets(main_window.media_manager_dock)
    QtWidgets.QWidget.setVisible(main_window, True)
    QtWidgets.QApplication.processEvents()
    library_origin = main_window.media_manager_dock.mapTo(main_window, QtCore.QPoint())
    cloud_origin = main_window.cloud_library_dock.mapTo(main_window, QtCore.QPoint())
    assert cloud_origin.x() > library_origin.x()
    assert main_window.media_manager_dock.dockAreaWidget().currentDockWidget() is main_window.media_manager_dock
    assert main_window.layout_preset_navigation.currentIndex() == 3
    assert main_window.mode_library_sync_item.isChecked()
    main_window._activate_layout_preset('default')
    assert settings.value(_preset_layout_storage_key('librarysync', 'main window state'))
    assert not main_window.mode_library_sync_item.isChecked()
    main_window._activate_layout_preset('librarysync')
    assert main_window.mode_library_sync_item.isChecked()
    plugin.finalise()
    assert settings.value('core/view mode') == 'librarysync'
    assert main_window.cloud_library_dock.isDockOpen()
    plugin.initialise()
    plugin.toggle_status(PluginStatus.Inactive)
    assert settings.value('core/view mode') == 'default'
    assert not main_window.mode_library_sync_item.isVisible()
    QtWidgets.QWidget.setVisible(main_window, False)


def test_library_sync_preset_modern(modern_appearance, main_window, settings):
    _check_library_sync_preset(main_window, settings)


def test_layout_preset_tab_syncs_with_current_mode(main_window, settings):
    """The left layout tab bar should reflect the currently selected layout mode."""
    settings.setValue('core/view mode', 'setup')

    main_window._sync_layout_preset_tab_from_settings()

    assert main_window.layout_preset_navigation.currentIndex() == 1


def test_layout_preset_tab_change_activates_mode(main_window):
    """Selecting a layout preset tab should activate the corresponding layout preset."""
    with patch.object(main_window, '_activate_layout_preset') as mock_activate:
        main_window.on_layout_preset_tab_changed(2)

    mock_activate.assert_called_once_with('live')


def test_layout_preset_tabs_toggle_honours_enabled_setting(main_window, settings):
    """Layout preset tabs should be visible when the toggle is enabled."""
    main_window.on_toggle_layout_preset_tabs(True)

    assert main_window.view_layout_preset_tabs_item.isChecked() is True
    assert main_window.layout_preset_navigation.isNavigationVisible() is True


def test_layout_preset_tabs_toggle_persists_off_state(main_window, settings):
    """Turning layout preset tabs off should hide them and persist the preference."""
    main_window.on_toggle_layout_preset_tabs(False)

    assert settings.value('user interface/show layout preset tabs') is False
    assert main_window.layout_preset_navigation.isNavigationVisible() is False
    assert main_window.view_layout_preset_tabs_item.isChecked() is False


@patch('opal.core.ui.mainwindow.MainWindow._schedule_left_column_dock_layout')
def test_activate_layout_preset_saved_state_without_snapshot_applies_canonical(mock_sched, main_window, settings):
    """
    restoreState() from a saved preset can resurrect wrong dock/panel visibility; without a JSON snapshot,
    factory preset visibility must be re-applied when no snapshot exists.
    """
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('core/view mode', 'default')
    settings.setValue('user interface/modern preset layout/setup/main window state', QtCore.QByteArray(b'1'))
    settings.setValue(_preset_layout_storage_key('setup', _PRESET_VISIBILITY_SNAPSHOT_KEY), '')
    main_window.control_splitter = MagicMock()
    main_window.control_splitter.saveState.return_value = QtCore.QByteArray()
    main_window._live_controller = MagicMock()
    main_window._live_controller.splitter.saveState.return_value = QtCore.QByteArray()
    main_window._preview_controller = MagicMock()
    main_window._preview_controller.splitter.saveState.return_value = QtCore.QByteArray()
    with patch.object(main_window, '_restore_layout_from_preset') as mock_restore, \
            patch.object(main_window, '_apply_canonical_preset_visibility') as mock_canonical:
        main_window._activate_layout_preset('setup')
    mock_restore.assert_called_once_with('setup')
    mock_canonical.assert_called_once_with('setup')


@patch('opal.core.ui.mainwindow.MainWindow._schedule_left_column_dock_layout')
def test_activate_layout_preset_saved_state_with_snapshot_skips_canonical(mock_sched, main_window, settings):
    """
    When a visibility snapshot exists, it defines panel state; canonical factory visibility is not applied.
    """
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('core/view mode', 'default')
    settings.setValue('user interface/modern preset layout/setup/main window state', QtCore.QByteArray(b'1'))
    settings.setValue(
        _preset_layout_storage_key('setup', _PRESET_VISIBILITY_SNAPSHOT_KEY),
        '{"show_library": true, "show_service": true, "show_themes": true, '
        '"preview_panel": true, "live_panel": false, "show_projectors": false}')
    main_window.control_splitter = MagicMock()
    main_window.control_splitter.saveState.return_value = QtCore.QByteArray()
    main_window._live_controller = MagicMock()
    main_window._live_controller.splitter.saveState.return_value = QtCore.QByteArray()
    main_window._preview_controller = MagicMock()
    main_window._preview_controller.splitter.saveState.return_value = QtCore.QByteArray()
    with patch.object(main_window, '_restore_layout_from_preset') as mock_restore, \
            patch.object(main_window, '_apply_canonical_preset_visibility') as mock_canonical:
        main_window._activate_layout_preset('setup')
    mock_restore.assert_called_once_with('setup')
    mock_canonical.assert_called_once_with('setup')


@patch('opal.core.ui.mainwindow.MainWindow._ensure_left_column_dock_sizes')
def test_deferred_left_column_setup_preset_uses_setup_dock_geometry(mock_sizes, main_window, settings):
    """
    Setup mode without saved preset layout should build full-height Library+Themes | Service
    (tabified), not the Default preset's Service-over-Library stack.
    """
    settings.setValue('core/view mode', 'setup')
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('user interface/modern preset layout/setup/main window state', QtCore.QByteArray())
    with patch.object(main_window, '_reapply_left_column_dock_layout_setup') as mock_setup, \
            patch.object(main_window, '_reapply_left_column_dock_layout') as mock_default:
        main_window._deferred_apply_left_column_dock_layout()
    mock_setup.assert_called_once()
    mock_default.assert_not_called()


def test_reapply_left_column_dock_layout_setup_places_library_before_service(main_window):
    """Setup dock layout should position Library/Themes before Service."""
    with patch.object(main_window, 'addDockWidget') as mock_add, \
            patch.object(main_window, 'splitDockWidget') as mock_split:
        main_window._reapply_left_column_dock_layout_setup()

    mock_add.assert_called_once_with(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, main_window.media_manager_dock)
    mock_split.assert_called_once_with(
        main_window.media_manager_dock,
        main_window.service_manager_dock,
        QtCore.Qt.Orientation.Horizontal)


@patch('opal.core.ui.mainwindow.MainWindow._ensure_left_column_dock_sizes')
def test_deferred_left_column_default_preset_uses_default_dock_geometry(mock_sizes, main_window, settings):
    """Default mode without saved preset should use the standard left-column dock layout."""
    settings.setValue('core/view mode', 'default')
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('user interface/modern preset layout/default/main window state', QtCore.QByteArray())
    with patch.object(main_window, '_reapply_left_column_dock_layout_setup') as mock_setup, \
            patch.object(main_window, '_reapply_left_column_dock_layout') as mock_default:
        main_window._deferred_apply_left_column_dock_layout()
    mock_default.assert_called_once()
    mock_setup.assert_not_called()


@patch('opal.core.ui.mainwindow.QtWidgets.QWidget.show')
@patch('opal.core.ui.mainwindow.MainWindow.set_view_mode')
def test_show_skips_factory_set_view_mode_when_saved_preset_layout(mocked_view_mode, mocked_show, main_window, settings):
    """
    Startup should not re-apply factory preset visibility when that preset already has saved layout.
    """
    main_window.control_splitter = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window.activateWindow = MagicMock()
    settings.setValue('core/view mode', 'default')
    settings.setValue('user interface/is preset layout', True)
    settings.setValue('user interface/modern preset layout/default/main window state', QtCore.QByteArray(b'x'))

    main_window.show()

    mocked_view_mode.assert_not_called()


@patch('opal.core.ui.mainwindow.QtWidgets.QMessageBox.warning')
@patch('opal.core.ui.mainwindow.QtCore.QTimer.singleShot')
def test_reset_layout_presets_clears_storage(mocked_timer, mocked_warning, main_window, settings):
    """
    Reset clears per-preset saved window state and visibility snapshots.
    """
    main_window._preview_controller = MagicMock()
    main_window._preview_controller.panel = MagicMock()
    main_window._live_controller = MagicMock()
    main_window._live_controller.panel = MagicMock()
    mocked_warning.return_value = QtWidgets.QMessageBox.StandardButton.Reset
    for mode in _PRESET_LAYOUT_MODES:
        settings.setValue(_preset_layout_storage_key(mode, 'main window state'), QtCore.QByteArray(b'1'))
        settings.setValue(_preset_layout_storage_key(mode, _PRESET_VISIBILITY_SNAPSHOT_KEY), '{"show_library": true}')
    settings.setValue('core/view mode', 'default')
    settings.setValue('user interface/is preset layout', True)

    main_window.on_mode_reset_layout_presets_clicked()

    for mode in _PRESET_LAYOUT_MODES:
        st = settings.value(_preset_layout_storage_key(mode, 'main window state'))
        assert len(st) == 0
        assert settings.value(_preset_layout_storage_key(mode, _PRESET_VISIBILITY_SNAPSHOT_KEY)) in ('', None)


@patch('opal.core.ui.mainwindow.QtWidgets.QMessageBox.warning')
def test_cancel_reset_layout_presets_preserves_storage(mocked_warning, main_window, settings):
    mocked_warning.return_value = QtWidgets.QMessageBox.StandardButton.Cancel
    key = _preset_layout_storage_key('live', 'main window state')
    settings.setValue(key, QtCore.QByteArray(b'saved layout'))
    main_window.on_mode_reset_layout_presets_clicked()
    assert settings.value(key) == QtCore.QByteArray(b'saved layout')
    assert mocked_warning.call_args.args[-1] == QtWidgets.QMessageBox.StandardButton.Cancel


@patch('opal.core.ui.mainwindow.QtCore.QTimer.singleShot')
@patch('opal.core.ui.mainwindow.show_screen_setup_message', return_value=False)
def test_screen_changed_modal(mocked_information: MagicMock, mocked_timer_singleshot: MagicMock,
                              main_window: MainWindow):
    """
    Test that the screen changed modal is shown whether a 'config_screen_changed' event is dispatched
    """
    # GIVEN: a newly opened OpenLP instance, mocked screens and renderer
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window._renderer = MagicMock()

    # WHEN: we trigger a 'config_screen_changed' event
    Registry().execute('config_screen_changed')

    # THEN: The modal should be called once
    mocked_information.assert_called_once()


@patch('opal.core.ui.mainwindow.QtCore.QTimer.singleShot')
@patch('opal.core.ui.mainwindow.show_screen_setup_message', return_value=False)
def test_screen_changed_modal_sets_timestamp_after_blocking_on_modal(mocked_information: MagicMock,
                                                                     mocked_timer_singleshot: MagicMock,
                                                                     main_window: MainWindow):
    """
    Test that the screen changed modal indicator is set back to True after showing warning message at the very end of
    the method, so that duplicate modals due to event spamming on 'config_screen_changed' is mitigated.
    """
    # GIVEN: a newly opened OpenLP instance, mocked screens, renderer and an special QMessageBox warning handler
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window._renderer = MagicMock()

    # WHEN: we trigger a 'config_screen_changed' event
    Registry().execute('config_screen_changed')

    # THEN: main_window.should_show_screen_change_message should be true, indicating that the next time the screen is
    # changed the warning message will be displayed again
    mocked_information.assert_called_once()
    assert main_window.should_show_screen_change_message is True


@patch('opal.core.ui.mainwindow.QtWidgets.QMessageBox.critical')
@patch('opal.core.ui.mainwindow.FileDialog')
def test_on_settings_import_item_clicked(mock_dialog, mock_crit, main_window_reduced):
    """
    Check we don't attempt to import incompatible settings from the future.
    import_settings() now encapsulates the from_future check; when it returns False
    (e.g. the file is from a newer version), the error dialog should be shown and
    no further processing should happen.
    """
    # GIVEN: A file dialog that returns a path, and import_settings returning False
    mock_import_file = MagicMock()
    mock_dialog.getOpenFileName.return_value = [mock_import_file, '']
    Registry().register('plugin_manager', MagicMock())
    # First call is the confirmation dialog; returning Yes lets execution proceed
    mock_crit.return_value = QtWidgets.QMessageBox.StandardButton.Yes

    with patch.object(main_window_reduced.settings, 'import_settings', return_value=False) as mock_import_settings:
        # WHEN: the function is called
        main_window_reduced.on_settings_import_item_clicked()

    # THEN: import_settings should have been called with the chosen file path
    mock_import_settings.assert_called_once_with(mock_import_file)
    # AND: An error dialog should have been shown (import failed / from future)
    assert mock_crit.call_count >= 2, 'Expected at least the confirmation and the failure dialog'


@patch('opal.core.ui.mainwindow.Path')
@patch('opal.core.ui.mainwindow.add_actions')
@patch('opal.core.ui.mainwindow.create_action')
def test_update_recent_files_menu(mocked_create_action, mocked_add_actions, MockPath, settings, registry,
                                  main_window_reduced):
    """Test that the update_recent_files_menu() method works correctly"""
    # GIVEN: A mocked settings object, and some other fixtures
    MockPath.return_value.is_file.side_effect = [False, True]
    settings.setValue('advanced/recent file count', 5)
    main_window_reduced.recent_files = [None, '/fake/path', Path('/path/to/real/file')]
    main_window_reduced.recent_files_menu = MagicMock()

    # WHEN: update_recent_files_menu() is called
    main_window_reduced.update_recent_files_menu()

    # THEN: There should be no errors
    assert mocked_create_action.call_count == 2


@patch('opal.core.ui.mainwindow.Path')
@patch('opal.core.ui.mainwindow.add_actions')
@patch('opal.core.ui.mainwindow.create_action')
def test_update_recent_files_menu_as_string(mocked_create_action, mocked_add_actions, MockPath, settings, registry,
                                            main_window_reduced):
    """Test that the update_recent_files_menu() method works correctly when the entry is a string instead of a list"""
    # GIVEN: A mocked settings object, and some other fixtures
    MockPath.return_value.is_file.side_effect = [False, True]
    settings.setValue('advanced/recent file count', 5)
    main_window_reduced.recent_files = JSON_RECENT_FILES
    main_window_reduced.recent_files_menu = MagicMock()

    # WHEN: update_recent_files_menu() is called
    main_window_reduced.update_recent_files_menu()

    # THEN: There should be no errors
    assert mocked_create_action.call_count == 2


@patch('opal.core.ui.mainwindow.Path')
@patch('opal.core.ui.mainwindow.add_actions')
@patch('opal.core.ui.mainwindow.create_action')
def test_update_recent_files_menu_as_list_with_string(mocked_create_action, mocked_add_actions, MockPath, settings,
                                                      registry, main_window_reduced):
    """Test that the update_recent_files_menu() method works correctly when the entry is a string instead of a list"""
    # GIVEN: A mocked settings object, and some other fixtures
    MockPath.return_value.is_file.side_effect = [False, True]
    settings.setValue('advanced/recent file count', 5)
    main_window_reduced.recent_files = [JSON_RECENT_FILES]
    main_window_reduced.recent_files_menu = MagicMock()

    # WHEN: update_recent_files_menu() is called
    main_window_reduced.update_recent_files_menu()

    # THEN: There should be no errors
    assert mocked_create_action.call_count == 2


@patch('opal.core.ui.mainwindow.QtWidgets.QProgressDialog')
def test_show_wait_dialog(MockProcessDialog, main_window_reduced):
    """Test that the show wait dialog context manager works correctly"""
    # GIVEN: A mocked out QProgressDialog and a minimal main window
    mocked_wait_dialog = MagicMock()
    MockProcessDialog.return_value = mocked_wait_dialog

    # WHEN: Calling _show_wait_dialog()
    with main_window_reduced._show_wait_dialog('Test', 'This is a test'):
        pass

    # THEN: The correct methods should have been called
    MockProcessDialog.assert_called_once_with('This is a test', '', 0, 0, main_window_reduced)
    mocked_wait_dialog.setWindowTitle.assert_called_once_with('Test')
    mocked_wait_dialog.setWindowFlag.assert_called_once_with(QtCore.Qt.WindowContextHelpButtonHint, False)
    mocked_wait_dialog.setWindowModality.assert_called_once_with(QtCore.Qt.WindowModal)
    mocked_wait_dialog.setAutoClose.assert_called_once_with(False)
    mocked_wait_dialog.setCancelButton.assert_called_once_with(None)
    mocked_wait_dialog.show.assert_called_once_with()
    mocked_wait_dialog.close.assert_called_once_with()


@patch('opal.core.ui.mainwindow.QtWidgets.QApplication')
def test_wait_for_threads(MockApp, main_window_reduced):
    """Test that the wait_for_threads() method correctly stops the threads"""
    # GIVEN: A mocked application, and a reduced main window
    mocked_http_thread = MagicMock()
    mocked_http_thread.isRunning.side_effect = [True, True, False, False]
    mocked_http_worker = MagicMock()
    mocked_http_worker.stop = MagicMock()
    main_window_reduced.application.worker_threads = {
        'http': {'thread': mocked_http_thread, 'worker': mocked_http_worker}
    }

    # WHEN: _wait_for_threads() is called
    main_window_reduced._wait_for_threads()

    # THEN: The correct methods should have been called
    assert MockApp.processEvents.call_count == 2, 'processEvents() should have been called twice'
    mocked_http_worker.stop.assert_called_once()
    assert mocked_http_thread.isRunning.call_count == 4, 'isRunning() should have been called 4 times'
    mocked_http_thread.wait.assert_called_once_with(100)


@patch('opal.core.ui.mainwindow.QtWidgets.QApplication')
def test_wait_for_threads_no_threads(MockApp, main_window_reduced):
    """Test that the wait_for_threads() method exits early when there are no threads"""
    # GIVEN: A mocked application, and a reduced main window
    main_window_reduced.application.worker_threads = {}

    # WHEN: _wait_for_threads() is called
    main_window_reduced._wait_for_threads()

    # THEN: The correct methods should have been called
    assert MockApp.processEvents.call_count == 0, 'processEvents() should not have been called'


@patch('opal.core.ui.mainwindow.QtWidgets.QApplication')
def test_wait_for_threads_disappearing_thread(MockApp, main_window_reduced):
    """Test that the wait_for_threads() method correctly ignores threads that resolve themselves"""
    # GIVEN: A mocked application, and a reduced main window
    # WHEN: _wait_for_threads() is called
    with patch.object(main_window_reduced.application, 'worker_threads') as worker_threads_mock:
        worker_threads_mock.keys.side_effect = [['http'], []]
        main_window_reduced._wait_for_threads()

    # THEN: The correct methods should have been called
    assert MockApp.processEvents.call_count == 1, 'processEvents() should have only been called once'


@patch('opal.core.ui.mainwindow.QtWidgets.QApplication')
def test_wait_for_threads_stuck_thread(MockApp, main_window_reduced):
    """Test that the wait_for_threads() method correctly stops the threads"""
    # GIVEN: A mocked application, and a reduced main window
    mocked_http_thread = MagicMock()
    mocked_http_thread.isRunning.return_value = True
    mocked_http_worker = MagicMock()
    mocked_http_worker.stop = MagicMock()
    main_window_reduced.application.worker_threads = {
        'http': {'thread': mocked_http_thread, 'worker': mocked_http_worker}
    }

    # WHEN: _wait_for_threads() is called
    main_window_reduced._wait_for_threads()

    # THEN: The correct methods should have been called
    assert MockApp.processEvents.call_count == 51, 'processEvents() should have been called 51 times'
    mocked_http_worker.stop.assert_called_once()
    assert mocked_http_thread.isRunning.call_count == 53, 'isRunning() should have been called 53 times'
    mocked_http_thread.wait.assert_called_with(100)
    mocked_http_thread.terminate.assert_called_once()


@patch('opal.core.ui.mainwindow.QtWidgets.QApplication')
def test_wait_for_threads_runtime_error(MockApp, main_window_reduced):
    """Test that the wait_for_threads() method handles a runtime error"""
    # GIVEN: A mocked application, and a reduced main window
    mocked_http_thread = MagicMock()
    mocked_http_thread.isRunning.side_effect = RuntimeError
    mocked_http_worker = MagicMock()
    mocked_http_worker.stop = MagicMock()
    main_window_reduced.application.worker_threads = {
        'http': {'thread': mocked_http_thread, 'worker': mocked_http_worker}
    }

    # WHEN: _wait_for_threads() is called
    main_window_reduced._wait_for_threads()

    # THEN: The correct methods should have been called
    assert MockApp.processEvents.call_count == 1, 'processEvents() should have been called once'
    mocked_http_worker.stop.assert_called_once()
    assert mocked_http_thread.isRunning.call_count == 1, 'isRunning() should have been called once'
    mocked_http_thread.wait.assert_not_called()
    mocked_http_thread.terminate.assert_not_called()


@patch('opal.core.ui.mainwindow.QtWidgets.QApplication')
def test_network_worker_can_unwind_after_default_shutdown_limit(MockApp, main_window_reduced):
    """A bounded cloud request can clean up after the default five-second allowance."""
    from opal.plugins.librarysync.lib.worker import SyncWorker
    worker = SyncWorker('job', {}, MagicMock())
    thread = MagicMock()
    thread.isRunning.side_effect = [True] * 55 + [False, False]
    main_window_reduced.application.worker_threads = {'librarysync-job': {'thread': thread, 'worker': worker}}
    main_window_reduced._wait_for_threads()
    assert worker.cancel.is_set()
    assert thread.wait.call_count > 50
    thread.terminate.assert_not_called()


def test_layout_navigation_compact_mode_keeps_workspace_and_selection(main_window):
    """The pane toggle exposes Compact mode without changing the active workspace."""
    navigation = main_window.layout_preset_navigation
    host = navigation.contentHost()
    workspace = host.pageWidget(0)
    assert host.currentIndex() == 0
    assert workspace == main_window.dock_manager
    with patch.object(main_window, '_activate_layout_preset') as activate:
        navigation.buttons[1].click()
        activate.assert_called_once_with('setup')
        assert navigation.displayMode() == navigation.DisplayMode.LeftCompact
        assert not navigation.isPaneOpen()
        assert navigation.currentIndex() == 1
        assert navigation.buttons[1].isChecked()
        assert all(button.fluentLayout() == QtWidgets.fluentqt.Button.ButtonLayout.IconOnly
                   for button in navigation.buttons)
        assert host.pageWidget(0) == workspace
        main_window.on_toggle_layout_preset_tabs(False)
        main_window.on_toggle_layout_preset_tabs(True)
        assert navigation.displayMode() == navigation.DisplayMode.LeftCompact
        navigation.pane_toggle.click()
        assert navigation.displayMode() == navigation.DisplayMode.Left
        assert all(button.fluentLayout() == QtWidgets.fluentqt.Button.ButtonLayout.IconBefore
                   for button in navigation.buttons)
        for button in navigation.buttons:
            content = button.contentPaintRect(QtCore.QRectF(0, 0, 172, 32))
            assert content.left() == 0
            assert content.width() == button.sizeHint().width()
        activate.assert_called_once_with('setup')


def test_modern_navigation_contains_entire_dock_workspace(modern_appearance, main_window):
    """Navigation sits to the left of the dock manager, including Library and Service."""
    navigation = main_window.layout_preset_navigation
    assert main_window.centralWidget() == navigation
    assert navigation.contentHost().pageWidget(0) == main_window.dock_manager
    assert navigation.contentHost().currentIndex() == 0
    navigation.resize(1000, 600)
    navigation.show()
    QtWidgets.QApplication.processEvents()
    assert navigation.paneGeometry().left() == 0
    assert navigation.displayMode() == navigation.DisplayMode.LeftCompact
    assert navigation.contentGeometry().left() == navigation.compactPaneWidth()
    navigation.pane_toggle.click()
    QtWidgets.QApplication.processEvents()
    assert navigation.contentGeometry().left() == navigation.expandedPaneWidth()


def test_slide_controller_action_buttons_use_native_commandbars(modern_appearance, main_window):
    from PySide6 import QtGui
    from opal.core.widgets import fluent
    from opal.core.ui.slidecontroller import PreviewController, LiveController
    Registry().register('application-qt', QtWidgets.QApplication.instance())
    Registry().register('media_controller', MagicMock())

    def display_stub(parent, window_title, embedded=False):
        widget = QtWidgets.QWidget(parent)
        widget.window_title = window_title
        widget.show_display = MagicMock()
        return widget

    controllers = (PreviewController(main_window), LiveController(main_window))
    for controller in controllers:
        with patch('opal.core.ui.slidecontroller.DisplayWindow', side_effect=display_stub):
            controller.setup_ui()
        toolbar = controller.toolbar
        for action in (controller.previous_item, controller.next_item):
            wrapper, button, _ = toolbar._fluent_actions[action]
            assert isinstance(button, fluent.fluentqt.Button)
            assert button.defaultAction() is action
            assert wrapper.defaultWidget() is button
            assert wrapper in toolbar.actions()
            assert action not in toolbar._command_actions
        assert toolbar.maximumHeight() > toolbar._command_groups[0].sizeHint().height()
    preview = controllers[0]
    toolbar = preview.toolbar
    button = preview.go_live_button
    assert toolbar.widgetForAction(preview.go_live_action) is button
    assert preview.top_label_horizontal.indexOf(button) == -1
    assert button.text() == 'Go Live'
    assert button.fluentLayout() == fluent.fluentqt.Button.ButtonLayout.IconBefore
    assert preview.go_live_action not in toolbar._command_actions
    parent = toolbar.parentWidget()
    preview.controller_layout.removeWidget(toolbar)
    toolbar.setParent(None)
    try:
        toolbar.set_widget_visible(['editSong', 'clear'], True)
        toolbar.setVisible(True)
        for width in (260, 800):
            toolbar.resize(width, toolbar.sizeHint().height())
            QtWidgets.QApplication.processEvents()
            assert button.isVisible()
            separator = toolbar.widgetForAction(preview.go_live_separator)
            group = toolbar._command_groups[0]
            assert separator.isVisible()
            assert group.geometry().right() < separator.x() < button.x()
            assert button.x() - separator.geometry().right() <= 8
            if width == 800:
                assert button.geometry().right() < toolbar.contentsRect().right() - 100
            preview.go_live_action.setVisible(False)
            assert separator.isHidden()
            preview.go_live_action.setVisible(True)
            assert separator.isVisible()
            preview.go_live_action.setEnabled(True)
            assert button.isEnabled()
            preview.go_live_action.setEnabled(False)
            assert not button.isEnabled()
            if width == 260:
                assert toolbar._command_groups[0].overflowedPrimaryActions()
    finally:
        toolbar.setParent(parent)
        preview.controller_layout.insertWidget(1, toolbar)
    controller = controllers[1]
    for name in ('show_screen_button', 'theme_screen_button', 'logo_screen_button',
                 'blank_screen_button', 'desktop_screen_button'):
        action = controller.toolbar.actions_map[name]
        assert isinstance(action, QtGui.QAction)
        assert not isinstance(action, QtWidgets.QWidgetAction)
        wrapper, button, _ = controller.toolbar._fluent_actions[action]
        assert wrapper in controller.toolbar.actions()
        assert button.defaultAction() is action
        assert action not in controller.toolbar._command_actions
    toolbar = controller.toolbar
    action = controller.song_menu_action
    assert action not in toolbar._command_actions
    wrapper, button, _ = toolbar._fluent_actions[action]
    assert button.defaultAction() is action
    next_button = toolbar.widgetForAction(controller.next_item)
    assert toolbar.layout().indexOf(button) == toolbar.layout().indexOf(next_button) + 1
    assert action.menu() is None
    assert controller.song_menu is not None
    parent = toolbar.parentWidget()
    controller.controller_layout.removeWidget(toolbar)
    toolbar.setParent(None)
    try:
        toolbar.set_widget_visible('song_menu', True)
        toolbar.resize(700, toolbar.sizeHint().height())
        toolbar.setVisible(True)
        QtWidgets.QApplication.processEvents()
        assert button.isVisible()
        assert button.x() > next_button.geometry().right()
        assert not any(widget.isVisible() for widget in toolbar.findChildren(QtWidgets.QWidget)
                       if widget.objectName() == 'FluentCommandBar.MoreButton')
        controller.song_menu.addAction('Verse 1')
        button.click()
        QtWidgets.QApplication.processEvents()
        assert controller.song_menu.isVisible()
        controller.song_menu.close()
    finally:
        toolbar.setParent(parent)
        controller.controller_layout.insertWidget(1, toolbar)


def test_preview_renderers_are_embedded_below_dialogs(main_window):
    from opal.core.ui.slidecontroller import PreviewController, LiveController
    Registry().register('application-qt', QtWidgets.QApplication.instance())
    Registry().register('media_controller', MagicMock())

    def display_stub(parent, window_title, embedded=False):
        widget = QtWidgets.QWidget(parent, QtCore.Qt.WindowType.Widget if embedded else QtCore.Qt.WindowType.Tool)
        widget.window_title = window_title
        widget.show_display = MagicMock()
        return widget

    for controller_class in (PreviewController, LiveController):
        controller = controller_class(main_window)
        with patch('opal.core.ui.slidecontroller.DisplayWindow', side_effect=display_stub):
            controller.setup_ui()
        main_window.dock_slide_controller(controller)
        assert not controller.preview_display.isWindow()
        assert controller.preview_display.window() is main_window

def test_shutdown_wait_dialog_has_room_for_text_and_progress(qapp):
    parent = QtWidgets.QWidget()
    parent.resize(900, 600)
    parent.show()
    with MainWindow._show_wait_dialog(parent, 'Please Wait', 'Waiting for some things to finish...'):
        dialog = parent.findChild(QtWidgets.QProgressDialog)
        assert dialog is not None
        assert dialog.width() >= 360
        assert dialog.height() > 70
        assert dialog._label.height() >= dialog._label.heightForWidth(dialog._label.width())
        assert dialog.layout().contentsMargins().left() >= 24
        assert parent.rect().contains(dialog.geometry())
    parent.close()


def test_default_theme_footer_link_opens_themes_settings(main_window, settings):
    """The current theme name links directly to the translated Themes settings section."""
    settings.setValue('themes/global theme', 'Sunday worship')
    main_window.default_theme_changed()
    button = main_window.default_theme_button
    assert isinstance(button, QtWidgets.fluentqt.HyperlinkButton)
    assert button.text() == 'Sunday worship'
    assert main_window.default_theme_label.text() == 'Default Theme'
    assert button.fontRole() == QtWidgets.fluentqt.FontRole.Caption
    assert main_window.default_theme_label.font() == QtWidgets.fluentqt.font_for_role(QtWidgets.fluentqt.FontRole.Caption)
    with patch.object(main_window.settings_form, 'exec') as open_settings:
        button.click()
    open_settings.assert_called_once_with(UiStrings().Themes)
    settings.setValue('themes/global theme', 'Evening worship')
    main_window.default_theme_changed()
    assert button.text() == 'Evening worship'


def test_footer_has_large_padding_around_progress_and_theme(modern_appearance, main_window):
    from fluentqt.design import Spacing
    footer = main_window.status_bar
    main_window.show_status_message('Loading Sunday service')
    assert footer.contentsMargins().left() == Spacing.Large
    assert footer.contentsMargins().right() == Spacing.Large
    assert footer.message_label.text() == 'Loading Sunday service'
    assert footer.left_content.layout().indexOf(footer.message_label) == 0
    assert footer.left_content.layout().indexOf(main_window.load_progress_bar) == 1
    assert footer.right_content.layout().indexOf(main_window.default_theme_container) == 0


@pytest.mark.parametrize('name', ['preview', 'live'])
def test_modern_controller_close_and_view_toggle_sync(modern_appearance, main_window, settings, name):
    dock = getattr(main_window, f'{name}_controller_dock')
    action = getattr(main_window, f'view_{name}_panel')
    dock.toggleView(False)
    assert not settings.value(f'user interface/{name} panel')
    assert not action.isChecked()
    getattr(main_window, f'set_{name}_panel_visibility')(True)
    assert dock.isDockOpen()
    assert settings.value(f'user interface/{name} panel')
    assert action.isChecked()


def test_modern_controller_lock_and_preset_visibility(modern_appearance, main_window, settings):
    import json
    import PySide6QtAds as ads
    main_window.set_lock_panel(True)
    for dock in (main_window.preview_controller_dock, main_window.live_controller_dock):
        assert dock.features() == ads.CDockWidget.DockWidgetFeature.NoDockWidgetFeatures
    main_window.set_lock_panel(False)
    assert main_window.live_controller_dock.features() & ads.CDockWidget.DockWidgetFeature.DockWidgetPinnable
    settings.setValue('user interface/is preset layout', True)
    assert main_window._apply_preset_visibility_snapshot(json.dumps({'preview_panel': False, 'live_panel': True}))
    assert main_window.preview_controller_dock.isClosed()
    assert main_window.live_controller_dock.isDockOpen()
    assert settings.value('user interface/is preset layout')


@pytest.mark.parametrize('main_window', [{'no_web_server': False}], indirect=True)
def test_unused_features_disabled_on_startup(main_window):
    """Unused optional features hide controls and disable network services."""
    assert Registry().get_flag('projector_disabled') is True
    assert Registry().get_flag('no_web_server') is True
    assert main_window.view_projector_manager_item.isVisible() is False
    assert main_window.import_projector_item.isVisible() is False
    with patch('opal.core.api.http.server.run_thread') as http_thread, \
            patch('opal.core.api.websockets.run_thread') as websocket_thread:
        main_window.http_server.bootstrap_post_set_up()
        main_window.ws_server.bootstrap_post_set_up()
        http_thread.assert_not_called()
        websocket_thread.assert_not_called()
    with patch.object(main_window, 'set_preview_panel_visibility'), \
            patch.object(main_window, 'set_live_panel_visibility'):
        main_window.set_view_mode(projector=True)
    assert main_window.projector_manager_dock.isVisible() is False


@pytest.mark.parametrize('main_window', [
    {'projector': True, 'remote_interface': True, 'no_web_server': False},
], indirect=True)
def test_enabled_features_start_on_next_session(main_window):
    """Saved activation restores projector controls and starts both remote servers."""
    assert Registry().get_flag('projector_disabled') is False
    assert Registry().get_flag('no_web_server') is False
    assert main_window.view_projector_manager_item.isVisible() is True
    assert main_window.import_projector_item.isVisible() is True
    with patch('opal.core.api.http.server.run_thread') as http_thread, \
            patch('opal.core.api.websockets.run_thread') as websocket_thread:
        main_window.http_server.bootstrap_post_set_up()
        main_window.ws_server.bootstrap_post_set_up()
        http_thread.assert_called_once()
        websocket_thread.assert_called_once()
    main_window.ws_server.close()


@pytest.mark.parametrize('main_window', [
    {'remote_interface': True, 'no_web_server': True},
], indirect=True)
def test_command_line_disable_overrides_enabled_remote(main_window):
    """The existing command-line override still prevents both remote servers."""
    assert Registry().get_flag('no_web_server') is True
    with patch('opal.core.api.http.server.run_thread') as http_thread, \
            patch('opal.core.api.websockets.run_thread') as websocket_thread:
        main_window.http_server.bootstrap_post_set_up()
        main_window.ws_server.bootstrap_post_set_up()
        http_thread.assert_not_called()
        websocket_thread.assert_not_called()
    main_window.ws_server.close()


@patch('opal.core.ui.mainwindow.QtCore.QTimer.singleShot')
@patch('opal.core.ui.mainwindow.show_screen_setup_message', return_value=True)
def test_screen_changed_configure_action_follows_display_refresh(message, timer, main_window):
    main_window._live_controller = MagicMock()
    main_window._preview_controller = MagicMock()
    main_window._renderer = MagicMock()

    def request_configuration():
        assert not main_window.screen_updating_lock.locked()
        main_window.live_controller.setup_displays.assert_called_once()
        main_window.renderer.resize.assert_called_once()

    with patch('opal.core.ui.mainwindow.request_screen_configuration',
               side_effect=request_configuration) as configure:
        main_window.screen_changed()
    configure.assert_called_once()
