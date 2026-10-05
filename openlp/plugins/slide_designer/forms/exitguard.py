"""Keep application exit from discarding open, independent designer drafts."""
from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.registry import Registry


class DesignerExitGuard(QtCore.QObject):
    def __init__(self, application, main_window):
        super().__init__(application)
        self.application = application
        self.main_window = main_window
        self.windows = []

    def add(self, window):
        if window in self.windows:
            return
        if not self.windows:
            if not hasattr(self.application, 'exit_guards'):
                self.application.exit_guards = []
            self.application.exit_guards.append(self.block_exit)
            if isinstance(self.main_window, QtWidgets.QWidget):
                self.main_window.installEventFilter(self)
        self.windows.append(window)
        window.installEventFilter(self)

    def remove(self, window):
        if window in self.windows:
            self.windows.remove(window)
            window.removeEventFilter(self)
        if not self.windows:
            if self.block_exit in getattr(self.application, 'exit_guards', []):
                self.application.exit_guards.remove(self.block_exit)
            if isinstance(self.main_window, QtWidgets.QWidget):
                self.main_window.removeEventFilter(self)

    def focus_designer(self):
        window = self.windows[-1]
        window.setWindowState(window.windowState() & ~QtCore.Qt.WindowState.WindowMinimized)
        window.show()
        window.raise_()
        window.activateWindow()

    def block_exit(self):
        if not self.windows:
            return False
        self.focus_designer()
        return True

    def eventFilter(self, watched, event):
        if not self.windows:
            return False
        if event.type() == QtCore.QEvent.Type.WindowActivate and watched in self.windows:
            self.windows.remove(watched)
            self.windows.append(watched)
        exiting = watched is self.main_window and event.type() == QtCore.QEvent.Type.Close
        if exiting:
            event.ignore()
            self.focus_designer()
            return True
        return False


def designer_exit_guard():
    application = QtWidgets.QApplication.instance()
    guard = getattr(application, '_slide_designer_exit_guard', None)
    if guard is None:
        guard = DesignerExitGuard(application, Registry().get('main_window'))
        application._slide_designer_exit_guard = guard
    # The main window can be recreated, e.g. during startup or in isolated tests.
    if not guard.windows:
        guard.main_window = Registry().get('main_window')
    return guard
