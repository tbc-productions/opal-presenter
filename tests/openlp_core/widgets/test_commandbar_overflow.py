"""A command-only toolbar shares one responsive overflow across separators."""
from PySide6 import QtWidgets

from openlp.core.widgets.toolbar import OpenLPToolbar


def test_single_command_bar_has_one_overflow_and_keeps_separator_order(qapp, qtbot):
    toolbar = OpenLPToolbar(None, single_command_bar=True)
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
