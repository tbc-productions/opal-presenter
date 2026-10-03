"""Theme collections with native Fluent list and thumbnail grid views."""
from PySide6 import QtCore, QtGui
import fluentqt

from openlp.core.lib.ui import MultipleViewModeList
from openlp.core.widgets import fluent as QtWidgets


class ThemeGridView(fluentqt.GridView):
    """Thumbnail grid retaining OpenLP's theme drag payload."""

    def startDrag(self, supported_actions):
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        mime_data = QtCore.QMimeData()
        mime_data.setText('themes')
        mime_data.setData('application/x-openlp-item-title',
                          indexes[0].data(QtCore.Qt.ItemDataRole.DisplayRole).encode('utf-8'))
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(QtCore.Qt.DropAction.CopyAction)


class ThemeViews(QtWidgets.QWidget):
    """One item store and selection shared by DataGrid and GridView."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_view = MultipleViewModeList(self)
        self.grid_view = ThemeGridView(self)
        self.grid_view.setModel(self.list_view.model())
        self.grid_view.setSelectionModel(self.list_view.selectionModel())
        self.grid_view.setSelectionMode(fluentqt.SelectionMode.Extended)
        self.grid_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid_view.setIconSize(QtCore.QSize(176, 100))
        self.grid_view.setCellSize(QtCore.QSize(200, 140))
        self.grid_view.setResizeMode(self.grid_view.ResizeMode.Adjust)
        self.grid_view.setDragEnabled(True)
        self.grid_view.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)
        self._stack = QtWidgets.QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(self.list_view)
        self._stack.addWidget(self.grid_view)
        self.setFocusProxy(self.list_view)
        for view in (self.list_view, self.grid_view):
            view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(
                lambda point, view=view: self.customContextMenuRequested.emit(view.viewport().mapTo(self, point)))
        self.grid_view.doubleClicked.connect(self.list_view.doubleClicked.emit)

    def __getattr__(self, name):
        view = self.__dict__.get('list_view')
        if view is not None:
            return getattr(view, name)
        raise AttributeError(name)

    def setViewMode(self, mode):
        self._stack.setCurrentWidget(self.grid_view if mode == QtWidgets.QListView.ViewMode.IconMode
                                     else self.list_view)
        self.setFocusProxy(self._stack.currentWidget())
        index = self.list_view.currentIndex()
        if index.isValid():
            self._stack.currentWidget().scrollTo(index)

    def viewMode(self):
        return (QtWidgets.QListView.ViewMode.IconMode if self._stack.currentWidget() is self.grid_view
                else QtWidgets.QListView.ViewMode.ListMode)

    def set_icon_size_by_view_mode(self, mode, size):
        if mode == QtWidgets.QListView.ViewMode.IconMode:
            self.grid_view.setIconSize(size)
            self.grid_view.setCellSize(QtCore.QSize(size.width() + 24, size.height() + 40))
        else:
            self.list_view.set_icon_size_by_view_mode(mode, size)

    def itemAt(self, point):
        view = self._stack.currentWidget()
        index = view.indexAt(view.viewport().mapFrom(self, point))
        return self.list_view.itemFromIndex(index)
