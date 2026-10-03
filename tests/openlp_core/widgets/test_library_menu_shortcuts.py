"""Library menu layout and keyboard activation regressions."""
import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from openlp.core.common.actions import ActionList
from openlp.core.lib.ui import create_widget_action
from openlp.core.ui.library import _add_library_context_menu_separator
from openlp.core.widgets import fluent
from openlp.core.widgets.views import TreeWidgetWithDnD


def test_library_menu_has_no_empty_rows_or_trailing_gap(qapp, qtbot):
    view = TreeWidgetWithDnD()
    qtbot.addWidget(view)
    menu = fluent.QMenu()
    qtbot.addWidget(menu)
    create_widget_action(view, text='Preview')
    separator = _add_library_context_menu_separator(view)
    create_widget_action(view, text='Delete')
    _add_library_context_menu_separator(view)
    create_widget_action(view, text='Show in folder')
    menu.addActions(view.actions())
    menu.popup(QtCore.QPoint(100, 100))
    QtWidgets.QApplication.processEvents()
    assert separator.isSeparator()
    assert all(action.isSeparator() or action.text() for action in menu.actions())
    last_rect = menu.actionGeometry(menu.actions()[-1])
    assert menu.height() - last_rect.bottom() - 1 == menu.contentsMargins().bottom()
    menu.close()


@pytest.mark.parametrize('width', [300, 500])
def test_menu_shortcuts_share_right_aligned_column(qapp, qtbot, width):
    menu = fluent.QMenu()
    qtbot.addWidget(menu)
    short = menu.addAction('Live')
    short.setShortcut(QtGui.QKeySequence('Shift+Return'))
    long = menu.addAction('Add this item to the service')
    long.setShortcut(QtGui.QKeySequence('+'))
    menu.addAction('A much longer action caption without any shortcut')
    menu.setMinimumWidth(width)
    menu.popup(QtCore.QPoint(100, 100))
    QtWidgets.QApplication.processEvents()
    assert menu.itemShortcutGeometry(short).right() == menu.itemShortcutGeometry(long).right()
    assert menu.itemShortcutGeometry(short).right() < menu.width()
    menu.close()


def test_export_submenu_does_not_shift_shortcuts_inward(qapp, qtbot):
    """Songs/Custom Export menus keep the same shortcut inset as other menus."""
    menu = fluent.QMenu()
    qtbot.addWidget(menu)
    action = menu.addAction('Live')
    action.setShortcut(QtGui.QKeySequence('Shift+Return'))
    menu.popup(QtCore.QPoint(100, 100))
    QtWidgets.QApplication.processEvents()
    inset = menu.width() - menu.itemShortcutGeometry(action).right()
    menu.close()
    export = fluent.QMenu('Export', menu)
    export.addAction('Selected items')
    menu.addMenu(export)
    menu.popup(QtCore.QPoint(100, 100))
    QtWidgets.QApplication.processEvents()
    assert menu.width() - menu.itemShortcutGeometry(action).right() == inset
    menu.close()


@pytest.mark.parametrize('plugin', ['Images', 'Media', 'Presentations'])
def test_library_shortcuts_activate_from_focused_view(settings, qtbot, plugin):
    view = TreeWidgetWithDnD()
    qtbot.addWidget(view)
    fired = []
    actions = []
    for command in ('Preview', 'Live', 'Service', 'Delete'):
        actions.append(create_widget_action(
            view, f'listView{plugin}{command}Item', text=command, can_shortcuts=True,
            triggers=lambda checked=False, command=command: fired.append(command)))
    view.show()
    view.activateWindow()
    view.setFocus()
    QtWidgets.QApplication.processEvents()
    assert view.hasFocus()
    try:
        for key, modifiers, expected in (
                (QtCore.Qt.Key.Key_Return, QtCore.Qt.KeyboardModifier.NoModifier, 'Preview'),
                (QtCore.Qt.Key.Key_Enter, QtCore.Qt.KeyboardModifier.NoModifier, 'Preview'),
                (QtCore.Qt.Key.Key_Return, QtCore.Qt.KeyboardModifier.ShiftModifier, 'Live'),
                (QtCore.Qt.Key.Key_Enter, QtCore.Qt.KeyboardModifier.ShiftModifier, 'Live'),
                (QtCore.Qt.Key.Key_Plus, QtCore.Qt.KeyboardModifier.NoModifier, 'Service'),
                (QtCore.Qt.Key.Key_Equal, QtCore.Qt.KeyboardModifier.NoModifier, 'Service')):
            QtTest.QTest.keyClick(view, key, modifiers)
            assert fired.pop() == expected
        QtTest.QTest.keySequence(view, actions[-1].shortcut())
        assert fired == ['Delete']
    finally:
        for action in actions:
            ActionList.get_instance().remove_action(action)
