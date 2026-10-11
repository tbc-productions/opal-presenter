"""Button menus commit a short click without depending on native hover timing."""
from PySide6 import QtCore, QtTest, QtWidgets

from opal.core.widgets import fluent


def test_short_menu_click_survives_hover_reset_and_toggles_once(qapp, qtbot):
    menu = fluent.QMenu()
    qtbot.addWidget(menu)
    action = menu.addAction('Select')
    action.setCheckable(True)
    triggered = []
    selected = []
    action.triggered.connect(lambda checked: triggered.append(checked))
    menu.triggered.connect(lambda chosen: selected.append(chosen))
    for expected in (True, False):
        menu.popup(QtCore.QPoint(100, 100))
        QtWidgets.QApplication.processEvents()
        point = menu.actionGeometry(action).center()
        QtTest.QTest.mousePress(menu, QtCore.Qt.MouseButton.LeftButton, pos=point)
        menu.setActiveAction(None)
        QtTest.QTest.mouseRelease(menu, QtCore.Qt.MouseButton.LeftButton, pos=point)
        assert action.isChecked() is expected
        assert not menu.isVisible()
    assert triggered == [True, False]
    assert selected == [action, action]


def test_short_click_returns_selected_action_from_exec(qapp, qtbot):
    menu = fluent.QMenu()
    qtbot.addWidget(menu)
    action = menu.addAction('Select')
    QtCore.QTimer.singleShot(0, lambda: QtTest.QTest.mouseClick(
        menu, QtCore.Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center()))
    assert menu.exec(QtCore.QPoint(100, 100)) is action


def test_menu_click_cancel_and_disabled_action_do_not_activate(qapp, qtbot):
    menu = fluent.QMenu()
    qtbot.addWidget(menu)
    action = menu.addAction('Select')
    fired = []
    action.triggered.connect(lambda: fired.append(True))
    menu.popup(QtCore.QPoint(100, 100))
    QtWidgets.QApplication.processEvents()
    point = menu.actionGeometry(action).center()
    QtTest.QTest.mousePress(menu, QtCore.Qt.MouseButton.LeftButton, pos=point)
    QtTest.QTest.mouseRelease(menu, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(-10, -10))
    assert fired == []
    action.setEnabled(False)
    QtTest.QTest.mouseClick(menu, QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert fired == []
    menu.close()
