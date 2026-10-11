"""Responsive progress feedback for presentation exports."""
from PySide6 import QtCore
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.i18n import translate


class ExportProgressDialog(QtWidgets.QProgressDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._updating = False
        self.setWindowTitle(translate('OpenLP.PresentationExport', 'Export presentation'))
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setMinimumDuration(0)
        self.setMinimumWidth(440)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setCancelButton(None)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, False)
        self.setRange(0, 0)
        self.setLabelText(translate('OpenLP.PresentationExport', 'Preparing export…'))
        self.findChild(QtWidgets.QProgressBar).setFormat('%v / %m')

    @QtCore.Slot(str, int, int)
    def update_progress(self, message, completed, total):
        was_updating = self._updating
        self._updating = True
        try:
            self.setLabelText(message)
            self.setRange(0, total)
            self.setValue(completed)
            if not was_updating:
                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        finally:
            self._updating = was_updating

    def reject(self):
        # Escape must not dismiss an export that is still writing its output.
        if not self._running:
            super().reject()

    def closeEvent(self, event):
        if self._running:
            event.ignore()
        else:
            super().closeEvent(event)

    def finish(self):
        self._running = False
        self.close()
        self.deleteLater()


class _ExportWriter(QtCore.QThread):
    progressed = QtCore.Signal(str, int, int)

    def __init__(self, action):
        super().__init__()
        self.action = action
        self.error = None

    def run(self):
        try:
            self.action(self.progressed.emit)
        except Exception as error:
            self.error = error


def write_with_progress(action, progress):
    """Keep the GUI event loop alive while Qt-safe rendering and packaging run in a worker."""
    worker = _ExportWriter(action)
    loop = QtCore.QEventLoop()
    worker.progressed.connect(progress, QtCore.Qt.ConnectionType.QueuedConnection)
    # Queue completion even when a fast writer finishes before the local loop starts.
    worker.finished.connect(loop.quit, QtCore.Qt.ConnectionType.QueuedConnection)
    worker.start()
    loop.exec()
    worker.wait()
    if worker.error is not None:
        raise worker.error
