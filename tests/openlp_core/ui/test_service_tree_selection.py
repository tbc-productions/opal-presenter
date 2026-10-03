"""Service tree clicks select individual items and disclose their slides."""
from unittest.mock import MagicMock

from PySide6 import QtCore, QtWidgets
import fluentqt

from openlp.core.widgets import fluent
from openlp.core.ui.servicemanager import ServiceManager, ServiceManagerList


def test_service_tree_row_and_child_selection(qapp, qtbot):
    view = ServiceManagerList(MagicMock())
    qtbot.addWidget(view)
    first = fluent.QTreeWidgetItem(view, ['First song'])
    child = fluent.QTreeWidgetItem(first, ['Verse 1'])
    second = fluent.QTreeWidgetItem(view, ['Second song'])
    view.resize(400, 240)
    view.show()
    QtWidgets.QApplication.processEvents()
    assert isinstance(view, fluentqt.TreeView)
    changes = []
    view.itemSelectionChanged.connect(lambda: changes.append(view.currentItem()))
    for item in (first, second):
        qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                         pos=view.visualItemRect(item).center())
        assert view.selectedItems() == [item]
        assert view.currentItem() is item
        assert view.selectedIndicatorRect().isValid()
    index = view._item_store.indexFromItem(first)
    rect = view.visualRect(index)
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=QtCore.QPoint(rect.left() + 22, rect.center().y()))
    qtbot.waitUntil(lambda: view.isExpanded(index))
    qtbot.wait(250)
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=view.visualItemRect(child).center())
    assert view.selectedItems() == [child]
    assert view.currentItem() is child
    assert changes


def test_service_notes_indicator_allows_row_clicks(settings, qtbot):
    view = ServiceManagerList(MagicMock())
    qtbot.addWidget(view)
    item = fluent.QTreeWidgetItem(view, ['Song with notes'])
    manager = MagicMock()
    manager.service_manager_list = view
    manager._get_service_item_transition_settings.return_value = {'enabled': False}
    ServiceManager._update_indicator_widget(manager, item, MagicMock(notes='Notes'), ['Notes'])
    container = view.itemWidget(item, 1)
    assert container.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    view.resize(400, 200)
    view.show()
    QtWidgets.QApplication.processEvents()
    point = view.visualRect(view._item_store.indexFromItem(item, 1)).center()
    assert QtWidgets.QApplication.widgetAt(view.viewport().mapToGlobal(point)) is view.viewport()
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert view.selectedItems() == [item]
    assert view.currentItem() is item
