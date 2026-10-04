"""The Service command row shares a single overflow menu."""
from unittest.mock import MagicMock

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.ui.servicemanager import ServiceManager


def test_service_commandbar_shares_overflow_across_sections(registry, settings, qtbot, monkeypatch):
    from openlp.core.common.actions import ActionList
    monkeypatch.setattr(ActionList, 'instance', None)
    monkeypatch.setattr(ActionList, 'shortcut_map', {})
    for name in ('main_window', 'live_controller', 'renderer', 'plugin_manager'):
        registry.register(name, MagicMock())
    manager = ServiceManager()
    qtbot.addWidget(manager)
    preview = MagicMock()
    go_live = MagicMock()
    monkeypatch.setattr(manager, 'make_preview', preview)
    monkeypatch.setattr(manager, 'on_make_live_action_triggered', go_live)
    manager.setup_ui(manager)
    manager.order_toolbar.setFixedWidth(180)
    manager.show()
    QtWidgets.QApplication.processEvents()
    toolbar = manager.order_toolbar
    assert len(toolbar._command_groups) == 1
    group = toolbar._command_groups[0]
    assert sum(not action.isSeparator() for action in group.primaryActions()) == 7
    assert group.overflowedPrimaryActions()
    assert group.isPrimaryActionOverflowed(manager.delete_action)
    assert group.isPrimaryActionOverflowed(manager.expand_collapse_action)
    assert group.isPrimaryActionOverflowed(manager.note_toolbar_action)
    for action in (manager.make_preview_action, manager.make_live_action):
        button = toolbar.widgetForAction(action)
        assert button.isVisible()
        assert not button.isEnabled()
        action.setEnabled(True)
        assert button.isEnabled()
        assert not group.isPrimaryActionOverflowed(action)
        qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    preview.assert_called_once()
    go_live.assert_called_once()
    more = [widget for widget in toolbar.findChildren(QtWidgets.QWidget)
            if widget.objectName() == 'FluentCommandBar.MoreButton' and widget.isVisible()]
    assert len(more) == 1
    toolbar.setFixedWidth(1000)
    QtWidgets.QApplication.processEvents()
    assert not group.overflowedPrimaryActions()
    assert more[0].isHidden()


def test_top_service_commandbar_shares_overflow_and_opens_services(registry, settings, qtbot, monkeypatch):
    from openlp.core.common.actions import ActionList
    from openlp.core.widgets import fluent
    monkeypatch.setattr(ActionList, 'instance', None)
    monkeypatch.setattr(ActionList, 'shortcut_map', {})
    for name in ('main_window', 'live_controller', 'renderer', 'plugin_manager'):
        registry.register(name, MagicMock())
    manager = ServiceManager()
    qtbot.addWidget(manager)
    load_service = MagicMock()
    recent_service = MagicMock()
    recent_action = QtGui.QAction('Sunday service', manager)
    recent_action.setData('/tmp/sunday.osz')
    manager.main_window.recent_files_menu.actions.return_value = [recent_action]
    monkeypatch.setattr(manager, 'on_load_service_clicked', load_service)
    monkeypatch.setattr(manager, 'on_recent_service_clicked', recent_service)
    manager.setup_ui(manager)
    toolbar = manager.toolbar
    toolbar.actions_map['theme_label'].setVisible(False)
    toolbar.actions_map['theme_combo_box'].setVisible(False)
    toolbar.actions_map['unsaved_changes_container'].setVisible(False)
    toolbar.setFixedWidth(70)
    manager.show()
    QtWidgets.QApplication.processEvents()

    assert len(toolbar.findChildren(fluent.fluentqt.CommandBar)) == 1
    group = toolbar._command_groups[0]
    assert [action.objectName() for action in group.primaryActions()] == [
        'newService', 'openService', 'saveService', 'saveServiceAs']
    assert group.isPrimaryActionOverflowed(manager.open_service_action)
    more = [widget for widget in toolbar.findChildren(QtWidgets.QWidget)
            if widget.objectName() == 'FluentCommandBar.MoreButton' and widget.isVisible()]
    assert len(more) == 1

    group.setOverflowOpen(True)
    QtWidgets.QApplication.processEvents()
    open_row = toolbar.widgetForAction(manager.open_service_action)
    qtbot.mouseClick(open_row, QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(manager.open_service_recent_menu.isVisible)
    assert not group.isOverflowOpen()
    menu = manager.open_service_recent_menu
    menu.actions()[0].trigger()
    load_service.assert_called_once_with(False)
    menu.actions()[2].trigger()
    recent_service.assert_called_once_with(False, '/tmp/sunday.osz')
    menu.close()

    toolbar.setFixedWidth(1000)
    QtWidgets.QApplication.processEvents()
    assert not group.overflowedPrimaryActions()
    assert more[0].isHidden()
    qtbot.mouseClick(toolbar.widgetForAction(manager.open_service_action), QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(menu.isVisible)
    menu.close()

    toolbar.actions_map['theme_label'].setVisible(True)
    toolbar.actions_map['theme_combo_box'].setVisible(True)
    QtWidgets.QApplication.processEvents()
    assert manager.theme_combo_box.geometry().right() == toolbar.contentsRect().right() - 8
    assert manager.theme_label.x() > toolbar.widgetForAction(manager.save_service_as_action).geometry().right()
