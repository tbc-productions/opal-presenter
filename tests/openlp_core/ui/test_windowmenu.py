"""Window menu behaviour with real Qt windows and application actions."""
from unittest.mock import Mock

import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import delete

from opal.core.ui.windowmenu import WindowMenu


@pytest.fixture
def window_menu(qapp, qtbot, monkeypatch):
    host = QtWidgets.QMainWindow()
    host.setWindowTitle('Opal Presenter')
    qtbot.addWidget(host)
    host.show()
    controller = WindowMenu(host, host.menuBar())
    host.menuBar().addMenu(controller.menu)
    monkeypatch.setattr(QtWidgets.QApplication, 'activeWindow', lambda: host)
    return controller


def make_window(qtbot, title, flags=QtCore.Qt.WindowType.Window):
    window = QtWidgets.QWidget(None, flags)
    window.setWindowTitle(title)
    qtbot.addWidget(window)
    window.show()
    return window


@pytest.mark.parametrize('macos', [True, False])
def test_platform_commands_and_shortcuts(window_menu, monkeypatch, macos):
    monkeypatch.setattr('opal.core.ui.windowmenu.is_macosx', lambda: macos)
    controller = WindowMenu(window_menu.main_window, window_menu.main_window.menuBar())
    assert controller.menu.title() == '&Window'
    assert controller.zoom_action.text() == ('&Zoom' if macos else 'Ma&ximise')
    assert controller.minimise_action.isEnabled()
    assert controller.zoom_action.isEnabled()
    assert controller.close_action.isEnabled()
    assert controller.close_action.shortcuts() == QtGui.QKeySequence.keyBindings(QtGui.QKeySequence.StandardKey.Close)
    if macos:
        assert controller.full_screen_action.shortcuts() == QtGui.QKeySequence.keyBindings(
            QtGui.QKeySequence.StandardKey.FullScreen)
    else:
        assert controller.full_screen_action.shortcut().toString() == 'Alt+Return'
    assert controller.minimise_action.shortcut().toString() == ('Ctrl+M' if macos else '')


def test_shared_mac_menu_includes_all_application_menus(window_menu, monkeypatch):
    monkeypatch.setattr('opal.core.ui.windowmenu.is_macosx', lambda: True)
    menu_bar = window_menu.main_window.menuBar()
    file_menu = menu_bar.addMenu('File')
    file_menu.addAction('Quit')
    window_menu.share_on_macos(menu_bar)
    assert window_menu._shared_menu_bar.parentWidget() is None
    assert window_menu._shared_menu_bar.actions() == menu_bar.actions()


def test_live_list_filters_surfaces_and_refreshes_titles(window_menu, qtbot):
    editor = make_window(qtbot, 'Song & Slides')
    hidden = make_window(qtbot, 'Closed editor')
    hidden.hide()
    make_window(qtbot, 'Popup', QtCore.Qt.WindowType.Popup)
    make_window(qtbot, 'Tooltip', QtCore.Qt.WindowType.ToolTip)
    make_window(qtbot, '')
    floating = make_window(qtbot, 'Floating Library', QtCore.Qt.WindowType.Tool)
    child = QtWidgets.QWidget(window_menu.main_window)
    child.setWindowTitle('Embedded editor')
    child.show()
    window_menu.menu.aboutToShow.emit()
    assert [action.text() for action in window_menu._window_actions] == [
        'Opal Presenter', 'Floating Library', 'Song && Slides']
    assert [action.isChecked() for action in window_menu._window_actions] == [True, False, False]
    editor.setWindowTitle('Renamed[*]')
    editor.setWindowModified(True)
    floating.hide()
    window_menu.menu.aboutToShow.emit()
    assert [action.text() for action in window_menu._window_actions] == ['Opal Presenter', 'Renamed*']


def test_selecting_minimised_window_preserves_maximised_state(window_menu, qtbot, monkeypatch):
    editor = make_window(qtbot, 'Editor')
    editor.showMaximized()
    editor.showMinimized()
    monkeypatch.setattr(editor, 'raise_', Mock())
    monkeypatch.setattr(editor, 'activateWindow', Mock())
    window_menu.update_menu()
    window_menu._window_actions[1].trigger()
    assert not editor.isMinimized()
    assert editor.isMaximized()
    editor.raise_.assert_called_once()
    editor.activateWindow.assert_called_once()


def test_commands_apply_to_active_editor(window_menu, qtbot, monkeypatch):
    editor = make_window(qtbot, 'Editor')
    monkeypatch.setattr(QtWidgets.QApplication, 'activeWindow', lambda: editor)
    window_menu.sync_actions()
    window_menu.zoom_action.trigger()
    assert editor.isMaximized()
    assert not window_menu.main_window.isMaximized()
    window_menu.zoom_action.trigger()
    assert not editor.isMaximized()
    window_menu.full_screen_action.trigger()
    assert editor.isFullScreen()
    window_menu.sync_actions()
    assert window_menu.full_screen_action.text() == 'Exit &Full Screen'
    window_menu.full_screen_action.trigger()
    assert not editor.isFullScreen()
    window_menu.minimise_action.trigger()
    assert editor.isMinimized()


def test_full_screen_toggle_preserves_previous_maximised_state(window_menu):
    host = window_menu.main_window
    host.showMaximized()
    window_menu.toggle_full_screen()
    window_menu.toggle_full_screen()
    assert host.isMaximized()
    assert not host.isFullScreen()


def test_close_respects_window_close_handler(window_menu, qtbot, monkeypatch):
    class UnsavedEditor(QtWidgets.QWidget):
        def closeEvent(self, event):
            event.ignore()

    editor = UnsavedEditor()
    editor.setWindowTitle('Unsaved Editor')
    qtbot.addWidget(editor)
    editor.show()
    monkeypatch.setattr(QtWidgets.QApplication, 'activeWindow', lambda: editor)
    window_menu.sync_actions()
    window_menu.close_action.trigger()
    assert editor.isVisible()


def test_deleted_window_action_is_safe(window_menu, monkeypatch):
    editor = QtWidgets.QWidget()
    editor.setWindowTitle('Temporary editor')
    editor.show()
    window_menu.update_menu()
    action = window_menu._window_actions[1]
    delete(editor)
    action.trigger()
    window_menu.update_menu()
    assert len(window_menu._window_actions) == 1


def test_modal_window_blocks_other_window_selection(window_menu, qtbot, monkeypatch):
    dialog = QtWidgets.QDialog(window_menu.main_window)
    dialog.setWindowTitle('Modal editor')
    qtbot.addWidget(dialog)
    dialog.show()
    monkeypatch.setattr(QtWidgets.QApplication, 'activeModalWidget', lambda: dialog)
    monkeypatch.setattr(window_menu.main_window, 'activateWindow', Mock())
    window_menu.update_menu()
    assert not window_menu._window_actions[0].isEnabled()
    assert window_menu._window_actions[1].isEnabled()
    assert window_menu._window_actions[1].isChecked()
    window_menu.activate_window(window_menu.main_window)
    window_menu.main_window.activateWindow.assert_not_called()


def test_bring_all_to_front_restores_windows_and_keeps_active_window(window_menu, qtbot, monkeypatch):
    editor = make_window(qtbot, 'Editor')
    editor.showMinimized()
    calls = []
    for window in (window_menu.main_window, editor):
        monkeypatch.setattr(window, 'activateWindow', lambda window=window: calls.append(window))
    window_menu.bring_all_action.trigger()
    assert not editor.isMinimized()
    assert calls == [window_menu.main_window, editor, window_menu.main_window]


def test_popup_focus_uses_previous_active_window(window_menu, qtbot, monkeypatch):
    editor = make_window(qtbot, 'Editor')
    monkeypatch.setattr(QtWidgets.QApplication, 'activeWindow', lambda: editor)
    window_menu.sync_actions()
    popup = make_window(qtbot, 'Menu', QtCore.Qt.WindowType.Popup)
    monkeypatch.setattr(QtWidgets.QApplication, 'activeWindow', lambda: popup)
    window_menu.minimise()
    assert editor.isMinimized()
    assert not window_menu.main_window.isMinimized()


def test_frameless_output_controls_are_disabled(window_menu, qtbot, monkeypatch):
    output = make_window(qtbot, 'Display Window', QtCore.Qt.WindowType.Window
                         | QtCore.Qt.WindowType.FramelessWindowHint)
    monkeypatch.setattr(QtWidgets.QApplication, 'activeWindow', lambda: output)
    window_menu.sync_actions()
    assert not window_menu.minimise_action.isEnabled()
    assert not window_menu.zoom_action.isEnabled()
    assert not window_menu.full_screen_action.isEnabled()
    assert not window_menu.close_action.isEnabled()


def test_window_menu_never_installs_application_event_filter(window_menu, qapp, monkeypatch):
    # Global Python filters crash when WebEngine constructs native request jobs.
    install_filter = Mock(side_effect=AssertionError('Application-wide event filter is unsafe with WebEngine'))
    app = QtWidgets.QApplication.instance()
    monkeypatch.setattr(app, 'installEventFilter', install_filter)
    controller = WindowMenu(window_menu.main_window, window_menu.main_window.menuBar())
    assert window_menu.main_window in controller._watched_windows
    install_filter.assert_not_called()


def test_focus_discovers_editor_and_state_changes_update_commands(window_menu, qapp, qtbot, monkeypatch):
    monkeypatch.setattr('opal.core.ui.windowmenu.is_macosx', lambda: False)
    editor = make_window(qtbot, 'New editor')
    monkeypatch.setattr(QtWidgets.QApplication, 'activeWindow', lambda: editor)
    app = QtWidgets.QApplication.instance()
    app.focusWindowChanged.emit(editor.windowHandle())
    qtbot.waitUntil(lambda: editor in window_menu._watched_windows)
    editor.showMaximized()
    qtbot.waitUntil(lambda: window_menu.zoom_action.text() == '&Restore')
    editor.showNormal()
    qtbot.waitUntil(lambda: window_menu.zoom_action.text() == 'Ma&ximise')
