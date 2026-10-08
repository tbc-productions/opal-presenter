"""Theme view switching retains records and native collection behaviour."""
from unittest.mock import patch

import fluentqt
from PySide6 import QtCore, QtTest

from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.themeviews import ThemeViews


def test_theme_views_share_items_selection_and_wrap(qapp):
    view = ThemeViews()
    view.resize(650, 400)
    for name in ('First', 'Second', 'Third', 'Fourth'):
        view.addItem(QtWidgets.QListWidgetItem(name))
    view.setCurrentRow(1)
    view.show()
    qapp.process_events()
    assert isinstance(view.list_view, fluentqt.DataGrid)
    assert isinstance(view.grid_view, fluentqt.GridView)
    assert view.viewMode() == QtWidgets.QListView.ViewMode.ListMode
    selected = view.currentItem()

    view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
    qapp.process_events()
    assert view.currentItem() is selected
    assert view.selectedItems() == [selected]
    grid = view.grid_view
    first = grid.visualRect(grid.model().index(0, 0))
    second = grid.visualRect(grid.model().index(1, 0))
    fourth = grid.visualRect(grid.model().index(3, 0))
    assert second.left() > first.left()
    assert fourth.top() > first.top()

    QtTest.QTest.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=first.center())
    assert view.currentRow() == 0
    view.setViewMode(QtWidgets.QListView.ViewMode.ListMode)
    assert view.currentItem().text() == 'First'
    view.takeItem(0)
    assert grid.model().rowCount() == 3
    view.clear()
    assert grid.model().rowCount() == 0
    view.close()


def test_theme_grid_context_menu_and_activation(qapp):
    view = ThemeViews()
    view.addItem('Theme')
    view.resize(400, 300)
    view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
    view.show()
    qapp.process_events()
    grid = view.grid_view
    index = grid.model().index(0, 0)
    point = grid.visualRect(index).center()
    context_items = []
    activated = []
    view.customContextMenuRequested.connect(lambda pos: context_items.append(view.itemAt(pos)))
    view.doubleClicked.connect(lambda index: activated.append(index.row()))
    grid.customContextMenuRequested.emit(point)
    grid.doubleClicked.emit(index)
    assert context_items == [view.item(0)]
    assert activated == [0]
    view.close()


def test_theme_grid_drag_payload(qapp):
    view = ThemeViews()
    view.addItem('Theme (default)')
    view.item(0).setData(QtCore.Qt.ItemDataRole.UserRole, 'Theme')
    view.setCurrentRow(0)
    with patch('openlp.core.widgets.themeviews.execute_drag') as drag:
        view.grid_view.startDrag(QtCore.Qt.DropAction.CopyAction)
    mime = drag.call_args.args[1]
    assert mime.text() == 'themes'
    assert bytes(mime.data('application/x-openlp-item-title')) == b'Theme'
    assert mime.names == ('Theme',)
    assert mime.manager is view.manager
