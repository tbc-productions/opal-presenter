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
The service item edit dialog
"""
from pathlib import Path
from copy import deepcopy

from PySide6 import QtCore, QtGui
from fluentqt import Window as FluentWindow
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.mixins import RegistryProperties
from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.lib import build_icon
from openlp.core.ui.serviceitemeditdialog import Ui_ServiceItemEditDialog
from openlp.core.ui.renamedialog import RenameDialog


class ServiceItemEditForm(FluentWindow, Ui_ServiceItemEditDialog, RegistryProperties):
    """
    Reorder, label and remove slides within service items.
    """
    finished = QtCore.Signal(int)

    def __init__(self):
        """
        Constructor
        """
        super().__init__(Registry().get('main_window'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._event_loop = None
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        self.setup_ui(self)
        self._preferred_size = QtCore.QSize(760, 600)
        self.item_list = []
        self._thumbnails = {}
        self.item_grid.currentCellChanged.connect(lambda row, *_: self.on_current_row_changed(row))
        self.item_grid.itemDoubleClicked.connect(self.on_rename_button_clicked)
        self.item_grid.selectionModel().selectionChanged.connect(lambda *_: self.on_current_row_changed())
        self.item_grid.rows_dropped.connect(self.on_rows_dropped)

    def exec(self):
        """Keep the service manager's draft/save contract in a resizable Fluent window."""
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        loop = QtCore.QEventLoop(self)
        self._event_loop = loop
        try:
            # Native parent-window setup can reset a hidden Fluent window to
            # 100x30 on macOS, even below its minimum size. Apply geometry after
            # polishing, immediately before opening the editor.
            self.ensurePolished()
            self.layout().activate()
            self.resize(self._preferred_size.expandedTo(self.minimumSize()))
            self.show()
            self.raise_()
            self.activateWindow()
            loop.exec()
        finally:
            self._event_loop = None
            loop.deleteLater()
        return self._result

    def done(self, result):
        self._result = result
        self._preferred_size = self.size()
        self.hide()
        if self._event_loop is not None:
            self._event_loop.quit()
        self.finished.emit(result)

    def accept(self):
        self.done(QtWidgets.QDialog.DialogCode.Accepted)

    def reject(self):
        self.done(QtWidgets.QDialog.DialogCode.Rejected)

    def closeEvent(self, event):
        self.reject()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
            event.accept()
        else:
            super().keyPressEvent(event)

    def set_service_item(self, item):
        """
        Set the service item to be edited.
        """
        self.item = item
        title = translate('OpenLP.ServiceItemEditForm', '{title}: Reorder/rename Collection items').format(
            title=item.title)
        self.setWindowTitle(title)
        self.window_title_label.setText(title)
        self.item_list = []
        self._thumbnails = {}
        self.data = False
        if self.item.is_image() or self.item.is_slide_set:
            self.data = True
            self.item_list.extend(deepcopy(self.item.slides))
            if self.item.is_slide_set:
                from openlp.core.lib.slideset import set_thumbnail
                for index, frame in enumerate(self.item.display_slides):
                    key = id(self.item_list[frame['raw_index']])
                    if key not in self._thumbnails:
                        self._thumbnails[key] = QtGui.QIcon(set_thumbnail(self.item, index))
        self.load_data()
        self.on_current_row_changed(self.item_grid.currentRow())

    def get_service_item(self):
        """
        Get the modified service item.
        """
        if self.data:
            if self.item.is_slide_set:
                self.item.slides = list(self.item_list)
                self.item._clear_slides_cache()
                self.item._new_item()
                return self.item
            self.item.slides = []
            for item in self.item_list:
                thumb = item.get('thumbnail', None)
                file_hash = item.get('file_hash', None)
                self.item.add_from_image(item['path'], item['title'], thumb, file_hash)
        return self.item

    def load_data(self):
        """
        Load slide labels and available thumbnails.
        """
        self.item_grid.clearContents()
        self.item_grid.setRowCount(len(self.item_list))
        for row, frame in enumerate(self.item_list):
            preview = QtWidgets.QTableWidgetItem()
            thumbnail = frame.get('thumbnail') or frame.get('path')
            if id(frame) in self._thumbnails:
                preview.setIcon(self._thumbnails[id(frame)])
            elif thumbnail and Path(thumbnail).exists():
                preview.setIcon(build_icon(Path(thumbnail)))
            self.item_grid.setItem(row, 0, preview)
            label = QtWidgets.QTableWidgetItem(frame['title'])
            label.setToolTip(frame['title'])
            self.item_grid.setItem(row, 1, label)
        self.on_current_row_changed(self.item_grid.currentRow())

    def on_delete_button_clicked(self):
        """
        Delete the current row.
        """
        rows = self.item_grid.selected_rows()
        if not rows or len(rows) == len(self.item_list):
            return
        for row in reversed(rows):
            self.item_list.pop(row)
        self.load_data()
        self._select_rows([min(rows[0], len(self.item_list) - 1)])

    def on_rename_button_clicked(self, *args):
        """Change the local slide label without changing its projected content."""
        rows = self.item_grid.selected_rows()
        if len(rows) != 1:
            return
        row = rows[0]
        title, accepted = RenameDialog.get_text(
            self, translate('OpenLP.ServiceItemEditForm', 'Rename slide label'),
            translate('OpenLP.ServiceItemEditForm', 'Label'), self.item_list[row]['title'])
        if accepted and title.strip():
            self.item_list[row]['title'] = title.strip()
            self.load_data()
            self._select_rows([row])

    def on_up_button_clicked(self):
        """
        Move the current row up in the list.
        """
        self.__move_item('up')

    def on_down_button_clicked(self):
        """
        Move the current row down in the list
        """
        self.__move_item('down')

    def _select_rows(self, rows):
        selection = self.item_grid.selectionModel()
        selection.clearSelection()
        for row in rows:
            selection.select(self.item_grid.model().index(row, 0),
                             QtCore.QItemSelectionModel.SelectionFlag.Select |
                             QtCore.QItemSelectionModel.SelectionFlag.Rows)
        if rows:
            index = self.item_grid.model().index(rows[0], 0)
            selection.setCurrentIndex(index, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)
            self.item_grid.scrollTo(index)
        self.on_current_row_changed()

    def __move_item(self, direction=''):
        rows = self.item_grid.selected_rows()
        if not rows or direction not in ('up', 'down'):
            return
        offset = -1 if direction == 'up' else 1
        if rows[0] + offset < 0 or rows[-1] + offset >= len(self.item_list):
            return
        for row in rows if offset < 0 else reversed(rows):
            self.item_list[row], self.item_list[row + offset] = self.item_list[row + offset], self.item_list[row]
        self.load_data()
        self._select_rows([row + offset for row in rows])

    def on_rows_dropped(self, rows, destination):
        """Insert selected items together, retaining their relative order and draft data."""
        selected = set(rows)
        moving = [frame for index, frame in enumerate(self.item_list) if index in selected]
        remaining = [frame for index, frame in enumerate(self.item_list) if index not in selected]
        insertion = destination - sum(row < destination for row in rows)
        self.item_list = remaining[:insertion] + moving + remaining[insertion:]
        self.load_data()
        self._select_rows(list(range(insertion, insertion + len(moving))))

    def on_current_row_changed(self, row=None):
        rows = self.item_grid.selected_rows()
        count = len(self.item_list)
        self.rename_action.setEnabled(len(rows) == 1)
        self.delete_action.setEnabled(bool(rows) and len(rows) < count)
        self.up_action.setEnabled(bool(rows) and rows[0] > 0)
        self.down_action.setEnabled(bool(rows) and rows[-1] < count - 1)
