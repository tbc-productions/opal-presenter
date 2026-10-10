"""Service tree clicks select individual items and disclose their slides."""
from unittest.mock import MagicMock, patch

from PySide6 import QtCore, QtGui, QtWidgets
import fluentqt

from openlp.core.widgets import fluent
from openlp.core.ui.servicemanager import ServiceManager, ServiceManagerList


def test_service_type_icons_have_no_border_but_child_thumbnails_do(qapp, qtbot):
    view = ServiceManagerList(MagicMock())
    qtbot.addWidget(view)
    item = fluent.QTreeWidgetItem(view, ['Song'])
    child = fluent.QTreeWidgetItem(item, ['Image'])
    pixmap = QtGui.QPixmap(80, 80)
    pixmap.fill(QtCore.Qt.GlobalColor.red)
    option = QtWidgets.QStyleOptionViewItem()
    option.rect = QtCore.QRect(0, 0, 400, 60)
    option.state = QtWidgets.QStyle.StateFlag.State_Enabled
    delegate = view.itemDelegateForColumn(0)
    for row, bordered in ((item, False), (child, True)):
        row.setIcon(0, QtGui.QIcon(pixmap))
        painter = MagicMock()
        delegate.paint(painter, option, view.indexFromItem(row))
        assert painter.drawRoundedRect.call_count == int(bordered)


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


def test_service_tree_click_keeps_selection_without_native_focus_ring(qapp, qtbot):
    view = ServiceManagerList(MagicMock())
    qtbot.addWidget(view)
    item = fluent.QTreeWidgetItem(view, ['Song'])
    view.resize(400, 200)
    view.show()
    QtWidgets.QApplication.processEvents()
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=view.visualItemRect(item).center())
    assert not view.testAttribute(QtCore.Qt.WidgetAttribute.WA_MacShowFocusRect)
    assert view.selectedItems() == [item]
    assert view.selectedIndicatorRect().isValid()
    assert view.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus


def test_service_tree_double_click_live_and_subsequent_preview(settings, qtbot):
    """The real mouse signal sequence previews promptly, goes Live once, then accepts another click."""
    settings.setValue('advanced/single click service preview', True)
    manager = ServiceManager(None)
    qtbot.addWidget(manager)
    view = ServiceManagerList(manager)
    qtbot.addWidget(view)
    first = fluent.QTreeWidgetItem(view, ['First song'])
    second = fluent.QTreeWidgetItem(view, ['Second song'])
    view.clicked.connect(manager.on_single_click_preview)
    view.doubleClicked.connect(manager.on_double_click_live)
    view.resize(400, 200)
    view.show()
    QtWidgets.QApplication.processEvents()
    with patch.object(manager, 'make_preview') as preview, patch.object(manager, 'make_live') as live:
        point = view.visualItemRect(first).center()
        qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
        preview.assert_called_once_with()
        qtbot.mouseDClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
        qtbot.mouseRelease(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
        live.assert_called_once_with()
        preview.assert_called_once_with()
        qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                         pos=view.visualItemRect(second).center())
        assert preview.call_count == 2
        assert view.currentItem() is second


def test_service_notes_indicator_allows_row_clicks(settings, qtbot):
    view = ServiceManagerList(MagicMock())
    qtbot.addWidget(view)
    item = fluent.QTreeWidgetItem(view, ['Song with notes'])
    manager = MagicMock()
    manager.service_manager_list = view
    manager._get_service_item_transition_settings.return_value = {'enabled': False}
    ServiceManager._update_item_indicators(manager, item, MagicMock(notes='Notes'), ['Notes'])
    view.resize(400, 200)
    view.show()
    QtWidgets.QApplication.processEvents()
    index = view._item_store.indexFromItem(item, 0)
    option = QtWidgets.QStyleOptionViewItem()
    option.rect = view.visualRect(index)
    option.font = view.font()
    point = view.itemDelegateForColumn(0).trailingIconRects(option, index)[0].center().toPoint()
    assert QtWidgets.QApplication.widgetAt(view.viewport().mapToGlobal(point)) is view.viewport()
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert view.selectedItems() == [item]
    assert view.currentItem() is item


def test_service_inline_indicators_follow_label_and_fit_width(settings, qtbot):
    from openlp.core.ui.servicemanager import SERVICE_ITEM_INDICATORS_ROLE
    view = ServiceManagerList(MagicMock())
    qtbot.addWidget(view)
    item = fluent.QTreeWidgetItem(view, ['Short label'])
    item.setData(0, SERVICE_ITEM_INDICATORS_ROLE, ['shape_subtract', 'note'])
    view.resize(400, 150)
    view.show()
    QtWidgets.QApplication.processEvents()
    delegate = view.itemDelegateForColumn(0)
    for direction in (QtCore.Qt.LayoutDirection.LeftToRight, QtCore.Qt.LayoutDirection.RightToLeft):
        view.setLayoutDirection(direction)
        for title in ('Short label', 'A very long service label ' * 8):
            item.setText(0, title)
            QtWidgets.QApplication.processEvents()
            index = view._item_store.indexFromItem(item, 0)
            option = QtWidgets.QStyleOptionViewItem()
            option.rect = view.visualRect(index)
            option.font = view.font()
            option.direction = direction
            text, text_rect, icons, rectangles = delegate._text_layout(option, index)
            assert view.columnCount() == 1
            assert view.header().sectionSize(0) == view.viewport().width()
            assert len(icons) == len(rectangles) == 2
            assert all(view.viewport().rect().contains(rect.toRect()) for rect in rectangles)
            width = view.fontMetrics().horizontalAdvance(text)
            if direction == QtCore.Qt.LayoutDirection.LeftToRight:
                assert abs(rectangles[0].left() - (text_rect.left() + width + 6)) <= 1
                assert rectangles[0].right() < rectangles[1].left()
            else:
                assert abs(rectangles[0].right() - (text_rect.right() - width - 6)) <= 1
                assert rectangles[1].right() < rectangles[0].left()
    view.close()
