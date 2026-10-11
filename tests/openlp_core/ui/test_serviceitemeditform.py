# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
Package to test the :mod:`~opal.core.ui.serviceitemeditform` package.
"""
import pytest
import fluentqt
from unittest.mock import MagicMock, call, patch

from PySide6 import QtCore, QtTest

from opal.core.ui.serviceitemeditform import ServiceItemEditForm
from opal.core.widgets import fluent as QtWidgets


@pytest.fixture
def form(registry, settings):
    registry.register('main_window', None)
    frm = ServiceItemEditForm()
    yield frm
    frm.deleteLater()


def populate(form):
    item = MagicMock(title='Sunday announcements', is_slide_set=False)
    item.is_image.return_value = True
    item.slides = [{'title': 'First', 'path': 'first.png'}, {'title': 'Second', 'path': 'second.png'},
                   {'title': 'Third', 'path': 'third.png'}]
    form.set_service_item(item)
    return item


def test_collection_window_and_grid_resize(form):
    populate(form)
    assert isinstance(form, fluentqt.Window)
    assert isinstance(form.item_grid, fluentqt.DataGrid)
    assert form.window_title_label.text() == form.windowTitle()
    assert form.windowTitle() == 'Sunday announcements: Reorder/rename Collection items'
    assert form.item_grid.horizontalHeader().isHidden()
    assert form.item_grid.columnCount() == 2
    assert form.item_grid.item(0, 0).text() == ''
    assert form.item_grid.item(0, 1).text() == 'First'
    form.show()
    QtWidgets.QApplication.processEvents()
    before = form.item_grid.size()
    label_width = form.item_grid.columnWidth(1)
    form.resize(form.width() + 200, form.height() + 200)
    QtWidgets.QApplication.processEvents()
    assert form.item_grid.height() > before.height()
    assert form.item_grid.columnWidth(1) > label_width
    assert form.item_grid.columnWidth(0) == 148
    form.hide()


def test_commands_follow_selected_row_in_either_column(form):
    populate(form)
    assert form.command_bar.primaryActions() == [form.rename_action, form.delete_action,
                                                 form.up_action, form.down_action]
    assert form.dialog_layout.indexOf(form.command_bar) < form.dialog_layout.indexOf(form.item_grid)
    form.item_grid.setCurrentCell(0, 1)
    assert not form.up_action.isEnabled()
    assert form.down_action.isEnabled()
    form.down_action.trigger()
    assert [slide['title'] for slide in form.item_list] == ['Second', 'First', 'Third']
    assert form.item_grid.currentRow() == 1
    form.item_grid.setCurrentCell(1, 0)
    with patch('opal.core.ui.serviceitemeditform.RenameDialog.get_text', return_value=('Renamed', True)):
        form.rename_action.trigger()
    assert form.item_grid.item(1, 1).text() == 'Renamed'
    form.delete_action.trigger()
    assert [slide['title'] for slide in form.item_list] == ['Second', 'Third']
    assert form.item_grid.currentRow() == 1
    assert not form.down_action.isEnabled()
    form.up_action.trigger()
    assert [slide['title'] for slide in form.item_list] == ['Third', 'Second']


@pytest.mark.parametrize('finish', ['save', 'cancel', 'close', 'escape'])
def test_window_completion_preserves_save_cancel_contract(form, finish):
    original = populate(form)
    form.item_grid.selectRow(0)
    form.on_down_button_clicked()
    assert original.slides[0]['title'] == 'First'
    def complete():
        if finish == 'close':
            form.close()
        elif finish == 'escape':
            QtTest.QTest.keyClick(form, QtCore.Qt.Key.Key_Escape)
        else:
            button = form.button_box.StandardButton.Save if finish == 'save' else form.button_box.StandardButton.Cancel
            form.button_box.button(button).click()
    QtCore.QTimer.singleShot(20, complete)
    result = form.exec()
    assert result == (QtWidgets.QDialog.DialogCode.Accepted if finish == 'save' else
                      QtWidgets.QDialog.DialogCode.Rejected)
    assert not form.isVisible()
    assert original.slides[0]['title'] == 'First'
    if result:
        form.get_service_item()
        assert original.add_from_image.call_args_list == [call('second.png', 'Second', None, None),
                                                          call('first.png', 'First', None, None),
                                                          call('third.png', 'Third', None, None)]


def test_no_selection_or_single_item_disables_invalid_commands(form):
    form.load_data()
    assert not any(action.isEnabled() for action in form.command_bar.primaryActions())
    form.on_delete_button_clicked()
    form.on_up_button_clicked()
    form.item_list = [{'title': 'Only slide'}]
    form.load_data()
    form.item_grid.selectRow(0)
    assert form.rename_action.isEnabled()
    assert not form.up_action.isEnabled()
    assert not form.down_action.isEnabled()
    assert not form.delete_action.isEnabled()


def test_exec_restores_opening_size_and_remembers_user_resize(form):
    populate(form)
    # Reproduce native startup replacing the hidden window's initial geometry.
    form.resize(form.minimumSize())
    observed = []
    def first_open():
        observed.append(form.size())
        observed.append(form.item_grid.height())
        form.resize(980, 780)
        form.reject()
    QtCore.QTimer.singleShot(20, first_open)
    form.exec()
    assert observed[0] == QtCore.QSize(760, 600)
    assert observed[1] > 300
    form.resize(form.minimumSize())
    def second_open():
        observed.append(form.size())
        form.reject()
    QtCore.QTimer.singleShot(20, second_open)
    form.exec()
    assert observed[2] == QtCore.QSize(980, 780)
    assert form.windowTitle() == 'Sunday announcements: Reorder/rename Collection items'


@pytest.mark.parametrize('rows', [[1, 2], [1, 3]])
def test_move_multiple_rows_keeps_order_selection_and_draft(form, rows):
    original = populate(form)
    form.item_list = [{'title': str(i), 'metadata': {'source': i}} for i in range(5)]
    form.load_data()
    form._select_rows(rows)
    selected = [form.item_list[i] for i in rows]
    assert not form.rename_action.isEnabled()
    form.on_up_button_clicked()
    assert form.item_grid.selected_rows() == [i - 1 for i in rows]
    assert [form.item_list[i] for i in form.item_grid.selected_rows()] == selected
    assert not form.up_action.isEnabled()
    form.on_down_button_clicked()
    assert [frame['title'] for frame in form.item_list] == ['0', '1', '2', '3', '4']
    assert form.item_grid.selected_rows() == rows
    assert original.slides[0]['title'] == 'First'


@pytest.mark.parametrize('rows,destination,expected', [
    ([0, 2], 5, ['1', '3', '4', '0', '2']),
    ([3, 4], 0, ['3', '4', '0', '1', '2']),
    ([1, 2], 2, ['0', '1', '2', '3', '4'])
])
def test_drag_inserts_group_without_losing_items(form, rows, destination, expected):
    form.item_list = [{'title': str(i), 'metadata': {'source': i}} for i in range(5)]
    form.load_data()
    selected = [form.item_list[i] for i in rows]
    form.on_rows_dropped(rows, destination)
    assert [frame['title'] for frame in form.item_list] == expected
    assert [form.item_list[i] for i in form.item_grid.selected_rows()] == selected
    assert len({id(frame) for frame in form.item_list}) == 5
    assert all(frame['metadata']['source'] == int(frame['title']) for frame in form.item_list)


def test_drag_events_move_selected_rows_and_reject_external_drops(form):
    populate(form)
    form.show()
    QtWidgets.QApplication.processEvents()
    form._select_rows([0, 1])
    grid = form.item_grid
    # Exercise the Qt drag lifecycle, including calculating a drop below the last row.
    destination = grid.visualRect(grid.model().index(2, 0)).bottomLeft() + QtCore.QPoint(2, 0)
    event = MagicMock()
    event.source.return_value = grid
    event.position.return_value = QtCore.QPointF(destination)
    def drag_loop(*_):
        grid.dragEnterEvent(event)
        grid.dropEvent(event)
        return QtCore.Qt.DropAction.MoveAction
    with patch('opal.core.ui.serviceitemeditdialog.QtGui.QDrag') as drag:
        drag.return_value.exec.side_effect = drag_loop
        grid.startDrag(QtCore.Qt.DropAction.MoveAction)
    assert [frame['title'] for frame in form.item_list] == ['Third', 'First', 'Second']
    assert grid.selected_rows() == [1, 2]
    event.accept.assert_called()
    assert grid._drag_rows == []
    event.reset_mock()
    event.source.return_value = None
    grid.dropEvent(event)
    event.ignore.assert_called_once()
    form.hide()


def test_shift_click_selects_multiple_rows(form):
    populate(form)
    form.show()
    QtWidgets.QApplication.processEvents()
    grid = form.item_grid
    first = grid.visualRect(grid.model().index(0, 1)).center()
    last = grid.visualRect(grid.model().index(2, 1)).center()
    QtTest.QTest.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=first)
    QtTest.QTest.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton,
                           QtCore.Qt.KeyboardModifier.ShiftModifier, last)
    QtTest.QTest.keyRelease(grid, QtCore.Qt.Key.Key_Shift)
    assert grid.selected_rows() == [0, 1, 2]
    assert not form.rename_action.isEnabled()
    assert not form.delete_action.isEnabled()
    form.hide()
