"""Startup window geometry respects saved choices and adapts defaults to the screen."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

from opal.core.ui.mainwindow import MainWindow


class GeometryWindow(QtWidgets.QMainWindow):
    _restore_main_window_geometry = MainWindow._restore_main_window_geometry


@pytest.mark.parametrize(('width', 'height', 'maximised'), [
    (1920, 1080, True),
    (2560, 1440, True),
    (1080, 1920, True),
    (2520, 1080, False),  # Exactly 21:9.
    (3440, 1440, False),
    (5120, 1440, False),
])
@pytest.mark.parametrize('saved', [QtCore.QByteArray(), QtCore.QByteArray(b'invalid geometry')])
def test_first_start_geometry(settings, qtbot, width, height, maximised, saved):
    window = GeometryWindow()
    qtbot.addWidget(window)
    window.settings = settings
    settings.setValue('user interface/main window geometry', saved)
    screen = MagicMock()
    screen.geometry.return_value = QtCore.QRect(-width, 0, width, height)
    available = QtCore.QRect(-width, 30, width, height - 70)
    screen.availableGeometry.return_value = available

    with patch.object(window, 'screen', return_value=screen):
        window._restore_main_window_geometry()

    assert window.isMaximized() is maximised
    if not maximised:
        assert window.width() == width // 2
        assert window.height() == available.height()
        assert window.geometry().center() == available.center()


@pytest.mark.parametrize('maximised', [False, True])
def test_saved_geometry_wins_over_startup_default(settings, qtbot, maximised):
    window = GeometryWindow()
    qtbot.addWidget(window)
    window.settings = settings
    window.setGeometry(50, 50, 600, 400)
    if maximised:
        window.setWindowState(QtCore.Qt.WindowState.WindowMaximized)
    settings.setValue('user interface/main window geometry', window.saveGeometry())
    window.setWindowState(QtCore.Qt.WindowState.WindowNoState)
    window.resize(300, 200)

    with patch.object(window, 'screen') as screen:
        window._restore_main_window_geometry()

    screen.assert_not_called()
    assert window.isMaximized() is maximised
    if not maximised:
        assert window.size() == QtCore.QSize(600, 400)


def test_saved_minimised_window_opens_visible(settings, qtbot):
    window = GeometryWindow()
    qtbot.addWidget(window)
    window.settings = settings
    window.resize(600, 400)
    window.setWindowState(QtCore.Qt.WindowState.WindowMinimized)
    settings.setValue('user interface/main window geometry', window.saveGeometry())

    window._restore_main_window_geometry()

    assert not window.isMinimized()
