"""SplitView hover resets without changing native resizing or child cursors."""
import pytest
from PySide6 import QtCore, QtWidgets as Native

from opal.core.app import OpenLP
from opal.core.widgets import fluent as QtWidgets


@pytest.fixture(scope='session')
def native_application():
    return Native.QApplication.instance() or Native.QApplication([])


@pytest.fixture
def qapp(native_application):
    return OpenLP()


@pytest.mark.parametrize('orientation,cursor', [
    (QtCore.Qt.Orientation.Horizontal, QtCore.Qt.CursorShape.SplitHCursor),
    (QtCore.Qt.Orientation.Vertical, QtCore.Qt.CursorShape.SplitVCursor)])
def test_split_hover_resets_on_pane_entry_and_can_be_hovered_again(qtbot, orientation, cursor):
    view = QtWidgets.SplitView()
    qtbot.addWidget(view)
    view.setOrientation(orientation)
    left, right = QtWidgets.QWidget(), QtWidgets.QLineEdit()
    view.addPane(left)
    view.addPane(right)
    view.resize(600, 400)
    view.show()
    QtWidgets.QApplication.processEvents()
    handle = view.handleGeometry(0).center()
    qtbot.mouseMove(view.windowHandle(), handle)
    assert view.cursor().shape() == cursor
    QtWidgets.QApplication.sendEvent(right, QtCore.QEvent(QtCore.QEvent.Type.Enter))
    assert view.cursor().shape() == QtCore.Qt.CursorShape.ArrowCursor
    assert right.cursor().shape() == QtCore.Qt.CursorShape.IBeamCursor
    qtbot.mouseMove(view.windowHandle(), handle + QtCore.QPoint(1, 1))
    assert view.cursor().shape() == cursor
    QtWidgets.QApplication.sendEvent(left, QtCore.QEvent(QtCore.QEvent.Type.Enter))
    assert view.cursor().shape() == QtCore.Qt.CursorShape.ArrowCursor


def test_split_keeps_resize_cursor_during_drag_and_resets_after_release(qtbot):
    view = QtWidgets.SplitView()
    qtbot.addWidget(view)
    left, right = QtWidgets.QWidget(), QtWidgets.QWidget()
    view.addPane(left)
    view.addPane(right)
    view.resize(600, 400)
    view.show()
    QtWidgets.QApplication.processEvents()
    handle = view.handleGeometry(0).center()
    before = view.paneGeometry(0).width()
    qtbot.mousePress(view, QtCore.Qt.MouseButton.LeftButton, pos=handle)
    assert view.resizing()
    QtWidgets.QApplication.sendEvent(left, QtCore.QEvent(QtCore.QEvent.Type.Enter))
    assert view.cursor().shape() == QtCore.Qt.CursorShape.SplitHCursor
    qtbot.mouseMove(view, handle + QtCore.QPoint(30, 0))
    qtbot.mouseRelease(view, QtCore.Qt.MouseButton.LeftButton, pos=handle + QtCore.QPoint(30, 0))
    assert not view.resizing()
    assert view.paneGeometry(0).width() > before
    QtWidgets.QApplication.sendEvent(left, QtCore.QEvent(QtCore.QEvent.Type.Enter))
    assert view.cursor().shape() == QtCore.Qt.CursorShape.ArrowCursor
