"""A command-only toolbar shares one responsive overflow across separators."""
import pytest
from PySide6 import QtCore, QtWidgets

from openlp.core.widgets.toolbar import OpenLPToolbar


def test_single_command_bar_has_one_overflow_and_keeps_separator_order(qapp, qtbot):
    toolbar = OpenLPToolbar(None)
    qtbot.addWidget(toolbar)
    commands = []
    expected = []
    for section in (('Top', 'Up', 'Down', 'Bottom'), ('Delete',), ('Expand', 'Notes'), ('Preview', 'Live')):
        if commands:
            expected.append(toolbar.addSeparator())
        for name in section:
            action = toolbar.add_toolbar_action(name, text=name)
            commands.append(action)
            expected.append(action)
    toolbar.resize(140, 48)
    toolbar.show()
    QtWidgets.QApplication.processEvents()
    assert len(toolbar._command_groups) == 1
    group = toolbar._command_groups[0]
    assert group.primaryActions() == expected
    more_buttons = [widget for widget in toolbar.findChildren(QtWidgets.QWidget)
                    if widget.objectName() == 'FluentCommandBar.MoreButton' and widget.isVisible()]
    assert len(more_buttons) == 1
    assert group.overflowedPrimaryActions()
    toolbar.resize(1000, 48)
    QtWidgets.QApplication.processEvents()
    assert not group.overflowedPrimaryActions()
    assert not more_buttons[0].isVisible()
    for action in commands:
        action.setVisible(False)
    assert group.isHidden()


@pytest.mark.parametrize('direction', [QtCore.Qt.LayoutDirection.LeftToRight, QtCore.Qt.LayoutDirection.RightToLeft])
def test_library_commands_align_right_with_one_shared_overflow(qapp, qtbot, direction):
    toolbar = OpenLPToolbar(None)
    toolbar.setLayoutDirection(direction)
    qtbot.addWidget(toolbar)
    left = [toolbar.add_toolbar_action(name, text=name) for name in ('New', 'Edit', 'Delete')]
    toolbar.addSeparator()
    toolbar.add_toolbar_action('Maintenance', text='Maintenance')
    toolbar.add_spacer()
    right = [toolbar.add_toolbar_action(name, text=name) for name in ('Preview', 'Live', 'Service')]
    toolbar.show()
    for width in (800, 180, 600):
        toolbar.resize(width, 48)
        qtbot.wait(20)
        assert len(toolbar._command_groups) == 1
        group = toolbar._command_groups[0]
        visible = [toolbar.widgetForAction(action) for action in right
                   if not group.isPrimaryActionOverflowed(action)]
        more = group.findChild(QtWidgets.QWidget, 'FluentCommandBar.MoreButton')
        if more.isVisible():
            visible.append(more)
        if direction == QtCore.Qt.LayoutDirection.LeftToRight:
            assert max(widget.geometry().right() for widget in visible) == group.contentsRect().right()
            assert toolbar.widgetForAction(left[0]).x() == group.contentsRect().left()
        else:
            assert min(widget.x() for widget in visible) == group.contentsRect().left()
            assert toolbar.widgetForAction(left[0]).geometry().right() == group.contentsRect().right()
        more_buttons = [widget for widget in toolbar.findChildren(QtWidgets.QWidget)
                        if widget.objectName() == 'FluentCommandBar.MoreButton' and widget.isVisible()]
        assert len(more_buttons) <= 1
    right[-1].setVisible(False)
    qtbot.wait(20)
    if direction == QtCore.Qt.LayoutDirection.LeftToRight:
        assert toolbar.widgetForAction(right[-2]).geometry().right() == group.contentsRect().right()
    else:
        assert toolbar.widgetForAction(right[-2]).x() == group.contentsRect().left()


@pytest.mark.parametrize('width', [180, 800])
def test_library_page_switch_aligns_commands_before_returning_from_show(qapp, qtbot, width):
    pages = QtWidgets.QStackedWidget()
    qtbot.addWidget(pages)
    toolbars = []
    for _ in range(2):
        toolbar = OpenLPToolbar(None)
        for name in ('New', 'Edit', 'Delete', 'Maintenance'):
            toolbar.add_toolbar_action(name, text=name)
        toolbar.add_spacer()
        for name in ('Preview', 'Live', 'Service'):
            toolbar.add_toolbar_action(name, text=name)
        pages.addWidget(toolbar)
        toolbars.append(toolbar)
    pages.resize(width, 48)
    pages.show()
    qapp.process_events()
    for index in (1, 0, 1, 0):
        pages.setCurrentIndex(index)
        group = toolbars[index]._command_groups[0]
        visible = [toolbars[index].widgetForAction(action) for action in group.trailing_actions
                   if not group.isPrimaryActionOverflowed(action)]
        more = group.findChild(QtWidgets.QWidget, 'FluentCommandBar.MoreButton')
        if more.isVisible():
            visible.append(more)
        # Do not drain the event queue: the next paint must already see the
        # final positions, even while the deferred alignment timer is pending.
        assert max(widget.geometry().right() for widget in visible) == group.contentsRect().right()
