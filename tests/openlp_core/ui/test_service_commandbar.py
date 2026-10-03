"""The Service command row shares a single overflow menu."""
from unittest.mock import MagicMock

from PySide6 import QtWidgets

from openlp.core.ui.servicemanager import ServiceManager


def test_service_commandbar_shares_overflow_across_sections(registry, settings, qtbot):
    for name in ('main_window', 'live_controller', 'renderer', 'plugin_manager'):
        registry.register(name, MagicMock())
    manager = ServiceManager()
    qtbot.addWidget(manager)
    manager.setup_ui(manager)
    manager.order_toolbar.setFixedWidth(180)
    manager.show()
    QtWidgets.QApplication.processEvents()
    toolbar = manager.order_toolbar
    assert len(toolbar._command_groups) == 1
    group = toolbar._command_groups[0]
    assert sum(not action.isSeparator() for action in group.primaryActions()) == 9
    assert group.overflowedPrimaryActions()
    more = [widget for widget in toolbar.findChildren(QtWidgets.QWidget)
            if widget.objectName() == 'FluentCommandBar.MoreButton' and widget.isVisible()]
    assert len(more) == 1
    toolbar.setFixedWidth(1000)
    QtWidgets.QApplication.processEvents()
    assert not group.overflowedPrimaryActions()
    assert more[0].isHidden()
