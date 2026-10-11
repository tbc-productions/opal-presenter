"""Keep application exit from discarding open, independent designer drafts."""
import logging

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.registry import Registry


class DesignerExitGuard(QtCore.QObject):
    def __init__(self, application, main_window):
        super().__init__(application)
        self.application = application
        self.main_window = main_window
        self.windows = []
        self._exit_pending = False
        self._exit_timer = QtCore.QTimer(self)
        self._exit_timer.setSingleShot(True)
        self._exit_timer.timeout.connect(self._close_next_designer)

    def add(self, window):
        if window in self.windows:
            return
        if not self.windows and not self._exit_pending:
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
        self._detach_if_idle()

    def _detach_if_idle(self):
        if not self.windows and not self._exit_pending:
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
        if self._exit_pending:
            return True
        if not self.windows:
            return False
        self._exit_pending = True
        self._exit_timer.start(0)
        return True

    def _close_next_designer(self):
        if not self.windows:
            self._exit_pending = False
            self._detach_if_idle()
            # Resume the normal service-save/exit confirmation only after the designer's
            # nested event loop has unwound and its borrowed controls have been restored.
            self.main_window._closing_designers_for_exit = True
            try:
                self.main_window.close()
            finally:
                self.main_window._closing_designers_for_exit = False
            return
        window = self.windows[-1]
        self.focus_designer()
        try:
            closed = window.request_close_for_exit()
        except Exception:
            logging.getLogger(__name__).exception('Could not close designer during application exit')
            closed = False
        if not closed:
            self._exit_pending = False
            self._detach_if_idle()
            return
        self.remove(window)
        self._exit_timer.start(0)

    def eventFilter(self, watched, event):
        if not self.windows and not self._exit_pending:
            return False
        if event.type() == QtCore.QEvent.Type.WindowActivate and watched in self.windows:
            self.windows.remove(watched)
            self.windows.append(watched)
        exiting = watched is self.main_window and event.type() == QtCore.QEvent.Type.Close
        if exiting:
            event.ignore()
            self.block_exit()
            return True
        return False


def designer_exit_guard():
    application = QtWidgets.QApplication.instance()
    guard = getattr(application, '_slide_designer_exit_guard', None)
    if guard is None:
        guard = DesignerExitGuard(application, Registry().get('main_window'))
        application._slide_designer_exit_guard = guard
    # The main window can be recreated, e.g. during startup or in isolated tests.
    if not guard.windows and not guard._exit_pending:
        guard.main_window = Registry().get('main_window')
    return guard
