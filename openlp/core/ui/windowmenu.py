"""Window controls and a live list of the application's open windows."""
from weakref import WeakSet, ref

from PySide6 import QtCore, QtGui
from shiboken6 import isValid

from openlp.core.common.i18n import translate
from openlp.core.common.platform import is_macosx
from openlp.core.widgets import fluent as QtWidgets


class WindowMenu(QtCore.QObject):
    """Share window commands through the native or Fluent application menu."""

    def __init__(self, main_window, menu_bar):
        super().__init__(main_window)
        self.main_window = main_window
        self.menu = QtWidgets.create_application_menu(menu_bar)
        self.menu.setObjectName('windowMenu')
        self._last_active = lambda: None
        self._window_actions = []
        self._watched_windows = WeakSet()
        self.minimise_action = self._action('windowMinimise', self.minimise)
        self.zoom_action = self._action('windowZoom', self.zoom)
        self.full_screen_action = self._action('windowFullScreen', self.toggle_full_screen)
        self.close_action = self._action('windowClose', self.close_window)
        self.menu.addSeparator()
        self.bring_all_action = self._action('windowBringAllToFront', self.bring_all_to_front)
        self.menu.addSeparator()
        if is_macosx():
            self.minimise_action.setShortcut(QtGui.QKeySequence('Ctrl+M'))
            self.full_screen_action.setShortcuts(QtGui.QKeySequence.StandardKey.FullScreen)
        else:
            # F11 already toggles OpenLP's Preview panel.
            self.full_screen_action.setShortcut(QtGui.QKeySequence('Alt+Return'))
        self.close_action.setShortcuts(QtGui.QKeySequence.StandardKey.Close)
        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self.sync_actions)
        # A Python application-wide filter wraps every native QObject, including
        # WebEngine request jobs while their C++ constructors are still running.
        # PySide can recurse and segfault there. Watch fully constructed windows
        # only, and discover new windows when application focus changes.
        self._watch_window(main_window)
        QtWidgets.QApplication.instance().focusWindowChanged.connect(self._schedule_sync)
        self.menu.aboutToShow.connect(self.update_menu)
        self.sync_actions()

    def share_on_macos(self, menu_bar):
        """Supply the same native menus when an unparented editor is active."""
        if is_macosx():
            self._shared_menu_bar = QtWidgets.create_application_menu_bar(None)
            self._shared_menu_bar.addActions(menu_bar.actions())
            self.main_window.destroyed.connect(self._shared_menu_bar.deleteLater)

    def _action(self, name, callback):
        action = QtGui.QAction(self)
        action.setObjectName(name)
        action.setMenuRole(QtGui.QAction.MenuRole.NoRole)
        action.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        action.triggered.connect(callback)
        self.main_window.addAction(action)
        self.menu.addAction(action)
        return action

    def _watch_window(self, window):
        if window not in self._watched_windows:
            window.installEventFilter(self)
            self._watched_windows.add(window)

    def _schedule_sync(self, window=None):
        self._update_timer.start(0)

    @staticmethod
    def _is_open_window(window):
        return (window is not None and isValid(window) and window.isWindow()
                and window.windowType() in (QtCore.Qt.WindowType.Window, QtCore.Qt.WindowType.Dialog,
                                            QtCore.Qt.WindowType.Tool, QtCore.Qt.WindowType.Sheet)
                and (window.isVisible() or window.isMinimized()) and bool(window.windowTitle()))

    def open_windows(self):
        """Exclude hidden editor drafts, menus, tooltips and other temporary surfaces."""
        return sorted((window for window in QtWidgets.QApplication.topLevelWidgets()
                       if self._is_open_window(window)),
                      key=lambda window: (window is not self.main_window, window.windowTitle().casefold(), id(window)))

    def current_window(self):
        modal = QtWidgets.QApplication.activeModalWidget()
        if self._is_open_window(modal):
            return modal
        active = QtWidgets.QApplication.activeWindow()
        if self._is_open_window(active):
            self._last_active = ref(active)
            return active
        previous = self._last_active()
        if self._is_open_window(previous):
            return previous
        return self.main_window if self._is_open_window(self.main_window) else None

    @staticmethod
    def _can_activate(window):
        if not WindowMenu._is_open_window(window) or not window.isEnabled():
            return False
        modal = QtWidgets.QApplication.activeModalWidget()
        return modal is None or modal is window or modal.isAncestorOf(window)

    def eventFilter(self, obj, event):
        if isinstance(obj, QtWidgets.QWidget) and event.type() in (
                QtCore.QEvent.Type.WindowActivate, QtCore.QEvent.Type.WindowStateChange,
                QtCore.QEvent.Type.Show, QtCore.QEvent.Type.Hide, QtCore.QEvent.Type.Close):
            if obj.isWindow():
                if event.type() == QtCore.QEvent.Type.WindowActivate and self._is_open_window(obj):
                    self._last_active = ref(obj)
                self._update_timer.start(0)
        return super().eventFilter(obj, event)

    def sync_actions(self):
        windows = self.open_windows()
        for item in windows:
            self._watch_window(item)
        window = self.current_window()
        flags = window.windowFlags() if window else QtCore.Qt.WindowType.Widget
        enabled = window is not None and self._can_activate(window)
        self.menu.setTitle(translate('OpenLP.MainWindow', '&Window'))
        self.minimise_action.setText(translate('OpenLP.MainWindow', '&Minimise'))
        self.minimise_action.setEnabled(enabled and bool(flags & QtCore.Qt.WindowType.WindowMinimizeButtonHint))
        if is_macosx():
            self.zoom_action.setText(translate('OpenLP.MainWindow', '&Zoom'))
        elif window and (window.isMaximized() or window.isFullScreen() or window.isMinimized()):
            self.zoom_action.setText(translate('OpenLP.MainWindow', '&Restore'))
        else:
            self.zoom_action.setText(translate('OpenLP.MainWindow', 'Ma&ximise'))
        resizable = enabled and bool(flags & QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        self.zoom_action.setEnabled(resizable)
        self.full_screen_action.setText(translate('OpenLP.MainWindow', 'Exit &Full Screen')
                                        if window and window.isFullScreen()
                                        else translate('OpenLP.MainWindow', 'Enter &Full Screen'))
        self.full_screen_action.setEnabled(resizable)
        self.close_action.setText(translate('OpenLP.MainWindow', '&Close Window'))
        self.close_action.setEnabled(enabled and bool(flags & QtCore.Qt.WindowType.WindowCloseButtonHint))
        self.bring_all_action.setText(translate('OpenLP.MainWindow', 'Bring All to &Front'))
        self.bring_all_action.setEnabled(any(self._can_activate(item) for item in windows))

    def update_menu(self):
        self.sync_actions()
        for action in self._window_actions:
            self.menu.removeAction(action)
            action.deleteLater()
        self._window_actions.clear()
        active = self.current_window()
        for window in self.open_windows():
            title = window.windowTitle().replace('[*]', '*' if window.isWindowModified() else '')
            action = QtGui.QAction(title.replace('&', '&&'), self.menu)
            action.setMenuRole(QtGui.QAction.MenuRole.NoRole)
            action.setCheckable(True)
            action.setChecked(window is active)
            action.setEnabled(self._can_activate(window))
            target = ref(window)
            action.triggered.connect(lambda checked=False, target=target: self.activate_window(target()))
            self.menu.addAction(action)
            self._window_actions.append(action)

    def activate_window(self, window):
        """Restore minimised windows without discarding maximised or full screen state."""
        if not self._can_activate(window):
            return
        if window.isMinimized():
            window.setWindowState(window.windowState() & ~QtCore.Qt.WindowState.WindowMinimized)
            window.show()
        window.raise_()
        window.activateWindow()

    def minimise(self):
        window = self.current_window()
        if window and self._can_activate(window):
            window.showMinimized()

    def zoom(self):
        window = self.current_window()
        if window and self._can_activate(window):
            if window.isMaximized() or window.isFullScreen() or window.isMinimized():
                window.showNormal()
            else:
                window.showMaximized()

    def toggle_full_screen(self):
        window = self.current_window()
        if window and self._can_activate(window):
            if window.isFullScreen():
                window.setWindowState(window.windowState() & ~QtCore.Qt.WindowState.WindowFullScreen)
                window.show()
            else:
                window.setWindowState(window.windowState() | QtCore.Qt.WindowState.WindowFullScreen)
                window.show()

    def close_window(self):
        window = self.current_window()
        if window and self._can_activate(window):
            window.close()

    def bring_all_to_front(self):
        active = self.current_window()
        for window in self.open_windows():
            self.activate_window(window)
        self.activate_window(active)
