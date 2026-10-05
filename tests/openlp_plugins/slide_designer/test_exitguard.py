"""Application close/quit must focus an open draft instead of discarding it."""
from unittest.mock import patch

import pytest
from PySide6 import QtCore, QtWidgets

from openlp.plugins.slide_designer.forms.exitguard import DesignerExitGuard
from openlp.core.app import OpenLPApplication


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


def test_main_window_close_is_blocked_until_last_designer_closes(guard, qtbot):
    window = QtWidgets.QWidget()
    qtbot.addWidget(window)
    window.showMinimized()
    guard.add(window)
    with patch.object(window, 'raise_') as raise_window, patch.object(window, 'activateWindow') as activate:
        assert guard.main_window.close() is False
        assert guard.main_window.isVisible()
        assert not window.isMinimized()
        raise_window.assert_called_once()
        activate.assert_called_once()
    # Closing the designer itself is allowed.
    assert window.close() is True
    guard.remove(window)
    assert guard.main_window.close() is True


def test_application_quit_focuses_most_recent_designer(guard, qtbot):
    first, second = QtWidgets.QWidget(), QtWidgets.QWidget()
    for window in (first, second):
        qtbot.addWidget(window)
        guard.add(window)
    QtCore.QCoreApplication.sendEvent(first, QtCore.QEvent(QtCore.QEvent.Type.WindowActivate))
    quit_event = QtCore.QEvent(QtCore.QEvent.Type.Quit)
    with patch.object(first, 'activateWindow') as activate_first, \
            patch.object(second, 'activateWindow') as activate_second:
        OpenLPApplication.event(guard.application, quit_event)
        assert not quit_event.isAccepted()
        activate_first.assert_called_once()
        activate_second.assert_not_called()
    guard.remove(first)
    with patch.object(second, 'activateWindow') as activate:
        assert guard.main_window.close() is False
        activate.assert_called_once()
    guard.remove(second)
    assert guard.block_exit() is False
    assert guard.application.exit_guards == []
