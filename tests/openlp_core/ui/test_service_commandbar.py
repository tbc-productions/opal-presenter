"""The Service command row shares a single overflow menu."""
from unittest.mock import MagicMock

from PySide6 import QtCore, QtWidgets

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
    monkeypatch.setattr(manager, 'load_service', load_service)
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
    menu = toolbar.window().findChild(QtWidgets.QWidget, 'FluentCommandBar.OverflowPopup')
    qtbot.waitUntil(menu.isVisible)
    qtbot.mouseClick(toolbar.widgetForAction(manager.open_service_action), QtCore.Qt.MouseButton.LeftButton)
    load_service.assert_called_once_with()
    assert not group.isOverflowOpen()
    assert not manager.recent_services_menu.isVisible()
    assert group.secondaryActions() == [manager.recent_services_action]

    toolbar.setFixedWidth(1000)
    QtWidgets.QApplication.processEvents()
    assert not group.overflowedPrimaryActions()
    assert not more[0].isHidden()
    qtbot.mouseClick(toolbar.widgetForAction(manager.open_service_action), QtCore.Qt.MouseButton.LeftButton)
    assert load_service.call_count == 2
    assert not menu.isVisible()

    toolbar.actions_map['theme_label'].setVisible(True)
    toolbar.actions_map['theme_combo_box'].setVisible(True)
    QtWidgets.QApplication.processEvents()
    assert manager.theme_combo_box.geometry().right() == toolbar.contentsRect().right() - 8
    assert manager.theme_label.x() > toolbar.widgetForAction(manager.save_service_as_action).geometry().right()


def test_recent_services_remain_a_separate_secondary_command(registry, settings, qtbot, monkeypatch):
    from PySide6 import QtGui
    from openlp.core.common.actions import ActionList
    monkeypatch.setattr(ActionList, 'instance', None)
    monkeypatch.setattr(ActionList, 'shortcut_map', {})
    for name in ('main_window', 'live_controller', 'renderer', 'plugin_manager'):
        registry.register(name, MagicMock())
    manager = ServiceManager()
    qtbot.addWidget(manager)
    recent = QtGui.QAction('Sunday service', manager)
    recent.setData('/tmp/sunday.osz')
    manager.main_window.recent_files_menu.actions.return_value = [recent]
    load_recent = MagicMock()
    monkeypatch.setattr(manager, 'on_recent_service_clicked', load_recent)
    manager.setup_ui(manager)
    manager.show()
    group = manager.toolbar._command_actions[manager.recent_services_action]
    group.setOverflowOpen(True)
    qtbot.mouseClick(manager.toolbar.widgetForAction(manager.recent_services_action),
                     QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(manager.recent_services_menu.isVisible)
    assert not group.isOverflowOpen()
    menu = manager.recent_services_menu
    assert menu.actions()[0].text() == 'Sunday service'
    qtbot.mouseClick(menu, QtCore.Qt.MouseButton.LeftButton, pos=menu.actionGeometry(menu.actions()[0]).center())
    assert not menu.isVisible()
    load_recent.assert_called_once_with(False, '/tmp/sunday.osz')
    assert manager.toolbar._command_actions[manager.recent_services_action].secondaryActions() == [
        manager.recent_services_action]


def test_service_context_menu_uses_standard_fluent_row_geometry(registry, settings, qtbot, monkeypatch):
    from openlp.core.common.actions import ActionList
    from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem, ServiceItemType
    from openlp.core.widgets import fluent

    monkeypatch.setattr(ActionList, 'instance', None)
    monkeypatch.setattr(ActionList, 'shortcut_map', {})
    for name in ('main_window', 'live_controller', 'renderer', 'plugin_manager'):
        registry.register(name, MagicMock())
    manager = ServiceManager()
    qtbot.addWidget(manager)
    manager.setup_ui(manager)
    reference = fluent.fluentqt.FluentMenu('', manager)
    reference.setFont(fluent.fluentqt.font_for_role(fluent.fluentqt.FontRole.Body))
    reference.addActions(manager.menu.actions())
    item = ServiceItem(None)
    item.name = 'media'
    item.service_item_type = ServiceItemType.Command
    for capability in (ItemCapabilities.CanEditTitle, ItemCapabilities.HasVariableStartTime,
                       ItemCapabilities.CanAutoStartForLive):
        item.add_capability(capability)
    manager.service_items = [{'service_item': item}]
    row = fluent.QTreeWidgetItem(['All Right Now'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, 1)
    manager.service_manager_list.addTopLevelItem(row)
    manager.show()
    QtWidgets.QApplication.processEvents()
    observed = []

    def inspect():
        menu = manager.menu
        observed.append((menu.size(), reference.sizeHint(), menu.styleSheet(), reference.styleSheet(), [
            (menu.actionGeometry(action), reference.actionGeometry(action))
            for action in menu.actions() if action.isVisible() and not action.isSeparator()]))
        menu.close()

    for _ in range(2):
        QtCore.QTimer.singleShot(0, inspect)
        manager.context_menu(manager.service_manager_list.visualItemRect(row).center())
    assert manager.menu.font() == fluent.fluentqt.font_for_role(fluent.fluentqt.FontRole.Body)
    assert len(observed) == 2
    for size, expected_size, style, expected_style, rows in observed:
        assert style == expected_style
        assert size == expected_size
        assert len(rows) == 7
        assert all(actual == expected for actual, expected in rows)
