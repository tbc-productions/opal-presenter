"""Application close/quit resolves designer drafts before the normal service prompt."""
from unittest.mock import patch

import pytest
from PySide6 import QtCore, QtWidgets

from opal.plugins.slide_designer.forms.exitguard import DesignerExitGuard
from opal.core.app import OpenLPApplication


@pytest.fixture
def guard(qapp, qtbot):
    main = QtWidgets.QWidget()
    main.resize(800, 600)
    main.show()
    qtbot.addWidget(main)
    result = DesignerExitGuard(QtWidgets.QApplication.instance(), main)
    yield result
    for window in list(result.windows):
        result.remove(window)
    result.deleteLater()


class DraftWindow(QtWidgets.QWidget):
    def __init__(self, result=True):
        super().__init__()
        self.result = result
        self.requests = 0

    def request_close_for_exit(self):
        self.requests += 1
        if self.result:
            self.hide()
        return self.result


def test_main_close_finishes_designer_then_resumes_normal_close(guard, qtbot):
    window = DraftWindow()
    qtbot.addWidget(window)
    window.showMinimized()
    guard.add(window)
    assert guard.main_window.close() is False  # The initial close is deferred.
    assert guard.main_window.isVisible()
    qtbot.waitUntil(lambda: not guard.main_window.isVisible())
    assert window.requests == 1
    assert not guard.windows
    assert guard.application.exit_guards == []


def test_quit_cancel_keeps_main_and_draft_open_without_duplicate_prompts(guard, qtbot):
    first, second = DraftWindow(False), DraftWindow()
    for window in (first, second):
        qtbot.addWidget(window)
        guard.add(window)
    QtCore.QCoreApplication.sendEvent(first, QtCore.QEvent(QtCore.QEvent.Type.WindowActivate))
    quit_event = QtCore.QEvent(QtCore.QEvent.Type.Quit)
    OpenLPApplication.event(guard.application, quit_event)
    assert not quit_event.isAccepted()
    assert guard.block_exit()  # A repeated request while the prompt is pending is consumed.
    qtbot.waitUntil(lambda: first.requests == 1 and not guard._exit_pending)
    assert guard.main_window.isVisible()
    assert first.isVisible()
    assert second.requests == 0
    first.result = True
    guard.main_window.close()
    qtbot.waitUntil(lambda: not guard.main_window.isVisible())
    assert first.requests == 2
    assert second.requests == 1


def test_service_close_can_still_cancel_after_designers_close(guard, qtbot):
    window = DraftWindow()
    qtbot.addWidget(window)
    guard.add(window)
    calls = []

    def normal_close():
        calls.append('service prompt')
        assert not guard.windows
        assert not window.isVisible()
        return False  # Simulate cancellation of the main window's existing service prompt.

    with patch.object(guard.main_window, 'close', side_effect=normal_close):
        assert guard.block_exit()
        qtbot.waitUntil(lambda: len(calls) == 1)
    assert guard.main_window.isVisible()
    assert guard.application.exit_guards == []


def test_save_exception_does_not_continue_quitting(guard, qtbot):
    window = DraftWindow()
    qtbot.addWidget(window)
    guard.add(window)
    with patch.object(window, 'request_close_for_exit', side_effect=RuntimeError('Save failed')) as request:
        guard.main_window.close()
        qtbot.waitUntil(lambda: request.called and not guard._exit_pending)
    assert guard.main_window.isVisible()
    assert window in guard.windows
