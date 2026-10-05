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
The UI widgets for the service item edit dialog
"""
import fluentqt
from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.lib.ui import create_button_box
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.style import use_alternate_rows


class CollectionItemGrid(QtWidgets.DataGrid):
    """Move selected rows as one ordered group without copying table cells."""
    rows_dropped = QtCore.Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drop_row = None
        self._drag_rows = []
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDragDropOverwriteMode(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(False)
        self.setAutoScroll(True)

    def selected_rows(self):
        return sorted({index.row() for index in self.selectionModel().selectedIndexes()})

    def startDrag(self, supported_actions):
        self._drag_rows = self.selected_rows()
        if not self._drag_rows:
            return
        drag = QtGui.QDrag(self)
        drag.setMimeData(self.model().mimeData(self.selectionModel().selectedIndexes()))
        try:
            drag.exec(QtCore.Qt.DropAction.MoveAction)
        finally:
            self._drag_rows = []
            self._drop_row = None
            self.viewport().update()

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        # Retain Qt's edge autoscrolling, but draw a between-row insertion marker.
        super().dragMoveEvent(event)
        self._drop_row = self.insertion_row(event.position().toPoint())
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()
        self.viewport().update()

    def insertion_row(self, position):
        index = self.indexAt(position)
        if not index.isValid():
            return self.rowCount()
        return index.row() + int(position.y() >= self.visualRect(index).center().y())

    def dragLeaveEvent(self, event):
        self._drop_row = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.source() is not self or not self._drag_rows:
            event.ignore()
            return
        destination = self.insertion_row(event.position().toPoint())
        self.rows_dropped.emit(self._drag_rows, destination)
        self._drop_row = None
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_row is not None and self.rowCount():
            if self._drop_row < self.rowCount():
                y = self.visualRect(self.model().index(self._drop_row, 0)).top()
            else:
                y = self.visualRect(self.model().index(self.rowCount() - 1, 0)).bottom()
            painter = QtGui.QPainter(self.viewport())
            painter.setPen(QtGui.QPen(self.palette().highlight().color(), 2))
            painter.drawLine(0, max(1, y), self.viewport().width(), max(1, y))
            painter.end()


class Ui_ServiceItemEditDialog(object):
    """
    The UI widgets for the service item edit dialog
    """
    def setup_ui(self, serviceItemEditDialog):
        """
        Set up the UI
        """
        serviceItemEditDialog.setObjectName('serviceItemEditDialog')
        serviceItemEditDialog.setWindowIcon(UiIcons().main_icon)
        serviceItemEditDialog.resize(760, 600)
        serviceItemEditDialog.setMinimumSize(560, 380)
        self.window_title_label = QtWidgets.QLabel()
        self.window_title_label.setContentsMargins(12, 0, 12, 0)
        self.window_title_label.setFluentTypography(fluentqt.FontRole.BodyStrong)
        serviceItemEditDialog.titleBar().setContentWidget(self.window_title_label)
        self.content_widget = QtWidgets.QWidget()
        serviceItemEditDialog.setContentWidget(self.content_widget)
        self.dialog_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.dialog_layout.setContentsMargins(16, 16, 16, 16)
        self.dialog_layout.setSpacing(8)
        self.dialog_layout.setObjectName('dialog_layout')
        self.command_bar = fluentqt.CommandBar(serviceItemEditDialog)
        self.command_bar.setObjectName('service_item_command_bar')
        self.command_bar.setLabelPosition(fluentqt.CommandBar.LabelPosition.Right)
        self.command_bar.setBackgroundVisible(True)
        self.command_bar.setDynamicOverflowEnabled(True)
        self.command_bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        for name, icon, caption, slot in (
                ('rename_action', UiIcons().edit, 'Rename', serviceItemEditDialog.on_rename_button_clicked),
                ('delete_action', UiIcons().delete, 'Delete', serviceItemEditDialog.on_delete_button_clicked),
                ('up_action', UiIcons().arrow_up, 'Move Up', serviceItemEditDialog.on_up_button_clicked),
                ('down_action', UiIcons().arrow_down, 'Move Down', serviceItemEditDialog.on_down_button_clicked)):
            action = QtGui.QAction(icon, translate('OpenLP.ServiceItemEditForm', caption), self.command_bar)
            action.setObjectName(name)
            action.setEnabled(False)
            action.triggered.connect(slot)
            setattr(self, name, action)
            self.command_bar.addPrimaryAction(action)
        self.dialog_layout.addWidget(self.command_bar)
        self.item_grid = CollectionItemGrid(self.content_widget)
        self.item_grid.setObjectName('collection_item_grid')
        self.item_grid.setColumnCount(2)
        self.item_grid.setAlternatingRowColors(use_alternate_rows())
        self.item_grid.setIconSize(QtCore.QSize(124, 70))
        self.item_grid.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.item_grid.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.item_grid.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.item_grid.setSortingEnabled(False)
        self.item_grid.verticalHeader().hide()
        self.item_grid.horizontalHeader().hide()
        self.item_grid.verticalHeader().setDefaultSectionSize(82)
        self.item_grid.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.item_grid.setColumnWidth(0, 148)
        self.item_grid.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.dialog_layout.addWidget(self.item_grid, 1)
        self.button_box = create_button_box(serviceItemEditDialog, 'button_box', ['cancel', 'save'])
        self.dialog_layout.addWidget(self.button_box)
        self.retranslate_ui(serviceItemEditDialog)

    def retranslate_ui(self, serviceItemEditDialog):
        """
        Translate the UI on the fly
        """
        serviceItemEditDialog.setWindowTitle(translate('OpenLP.ServiceItemEditForm', 'Reorder/rename items'))
        self.window_title_label.setText(serviceItemEditDialog.windowTitle())
        for action, caption, tooltip in (
                (self.rename_action, 'Rename', 'Rename the selected slide label'),
                (self.delete_action, 'Delete', 'Delete the selected slides'),
                (self.up_action, 'Move Up', 'Move the selected slides up'),
                (self.down_action, 'Move Down', 'Move the selected slides down')):
            action.setText(translate('OpenLP.ServiceItemEditForm', caption))
            action.setToolTip(translate('OpenLP.ServiceItemEditForm', tooltip))
