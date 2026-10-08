"""Native DataGrid collections retaining Qt's flat item API."""
from PySide6 import QtCore, QtWidgets as _qt
import fluentqt


def forward_item_signals(view, names):
    """Emit item-store notifications from the visible adapter, respecting its signal blocking."""
    for name in names:
        getattr(view._item_store, name).connect(getattr(view, name).emit)


class FluentListView(fluentqt.DataGrid):
    """Single-column DataGrid preserving the application's flat-list API."""
    Flow = _qt.QListView.Flow
    Movement = _qt.QListView.Movement
    ResizeMode = _qt.QListView.ResizeMode
    ViewMode = _qt.QListView.ViewMode
    LayoutMode = _qt.QListView.LayoutMode

    def __init__(self, parent=None):
        super().__init__(parent)
        self._list_options = {}
        self.setSelectionBehavior(_qt.QAbstractItemView.SelectionBehavior.SelectRows)
        self.verticalHeader().hide()
        self.horizontalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(_qt.QHeaderView.ResizeMode.Stretch)

    def setSelectionMode(self, mode):
        value = mode.value if hasattr(mode, 'value') else int(mode)
        super().setSelectionMode(fluentqt.SelectionMode(min(value, 3)))

    def selectionMode(self):
        return _qt.QAbstractItemView.SelectionMode(int(super().selectionMode()))

    def setHeaderLabel(self, label):
        # QListWidget's private model cannot store header data. Keep a one-column
        # header model without proxying item indexes or disrupting selections.
        from PySide6 import QtGui
        self._header_model = QtGui.QStandardItemModel(0, 1, self)
        self._header_model.setHorizontalHeaderLabels([label])
        self.horizontalHeader().setModel(self._header_model)
        self.horizontalHeader().show()

    def setViewMode(self, mode):
        self._list_options['viewMode'] = mode
        self._update_row_height()

    def viewMode(self):
        return self._list_options.get('viewMode', self.ViewMode.ListMode)

    def setIconSize(self, size):
        super().setIconSize(size)
        self._update_row_height()

    def _update_row_height(self):
        self.verticalHeader().setDefaultSectionSize(max(36, self.iconSize().height() + 12))

    def setGridSize(self, size):
        self._list_options['gridSize'] = size
        self.verticalHeader().setDefaultSectionSize(max(36, size.height()))

    def gridSize(self):
        return self._list_options.get('gridSize', QtCore.QSize())

    def setFlow(self, flow):
        self._list_options['flow'] = flow

    def flow(self):
        return self._list_options.get('flow', self.Flow.TopToBottom)

    def setMovement(self, movement):
        self._list_options['movement'] = movement

    def setResizeMode(self, mode):
        self._list_options['resizeMode'] = mode

    def setUniformItemSizes(self, enabled):
        self._list_options['uniformItemSizes'] = enabled

    def setSpacing(self, spacing):
        self._list_options['spacing'] = spacing

    def spacing(self):
        return self._list_options.get('spacing', 0)

    def setWrapping(self, enabled):
        self._list_options['wrapping'] = enabled


QListView = FluentListView


class ListItemsMixin:
    """Keep Qt's flat item API behind native Fluent collection views."""
    itemClicked = QtCore.Signal(_qt.QListWidgetItem)
    itemDoubleClicked = QtCore.Signal(_qt.QListWidgetItem)
    itemActivated = QtCore.Signal(_qt.QListWidgetItem)
    itemPressed = QtCore.Signal(_qt.QListWidgetItem)
    itemEntered = QtCore.Signal(_qt.QListWidgetItem)
    itemChanged = QtCore.Signal(_qt.QListWidgetItem)
    itemSelectionChanged = QtCore.Signal()
    currentItemChanged = QtCore.Signal(_qt.QListWidgetItem, _qt.QListWidgetItem)
    currentRowChanged = QtCore.Signal(int)
    currentTextChanged = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_store = _qt.QListWidget(self)
        self._item_store.hide()
        self.setModel(self._item_store.model())
        self.setSelectionModel(self._item_store.selectionModel())
        if hasattr(self, 'horizontalHeader'):
            self.horizontalHeader().sortIndicatorChanged.connect(self._sort_items)
            self.horizontalHeader().setSortIndicator(0, QtCore.Qt.SortOrder.AscendingOrder)
        forward_item_signals(self, ('itemClicked', 'itemDoubleClicked', 'itemActivated', 'itemPressed',
                                    'itemEntered', 'itemChanged', 'itemSelectionChanged',
                                    'currentItemChanged', 'currentRowChanged', 'currentTextChanged'))
        for view_signal, item_signal in (('clicked', 'itemClicked'), ('doubleClicked', 'itemDoubleClicked'),
                                         ('activated', 'itemActivated'), ('pressed', 'itemPressed'),
                                         ('entered', 'itemEntered')):
            signal = getattr(self._item_store, item_signal)
            getattr(self, view_signal).connect(lambda index, signal=signal: signal.emit(self.itemFromIndex(index)))

    def __getattr__(self, name):
        store = self.__dict__.get('_item_store')
        if store is not None:
            return getattr(store, name)
        raise AttributeError(name)

    def setSelectionMode(self, mode):
        value = mode.value if hasattr(mode, 'value') else int(mode)
        super().setSelectionMode(fluentqt.SelectionMode(min(value, 3)))
        self._item_store.setSelectionMode(mode)

    def selectionMode(self):
        return _qt.QAbstractItemView.SelectionMode(int(super().selectionMode()))

    def selectedItems(self):
        return self._item_store.selectedItems()

    def setSortingEnabled(self, enabled):
        self._item_store.setSortingEnabled(enabled)
        if hasattr(self, 'horizontalHeader'):
            super().setSortingEnabled(enabled)
            self.horizontalHeader().setSectionsClickable(enabled)
            self._sort_items(0, self.horizontalHeader().sortIndicatorOrder())

    def _sort_items(self, column, order):
        if self._item_store.isSortingEnabled():
            self._item_store.sortItems(order)

    def itemAt(self, *args):
        return self._item_store.itemFromIndex(self.indexAt(*args))

    def visualItemRect(self, item):
        return self.visualRect(self._item_store.indexFromItem(item))

    def scrollToItem(self, item, hint=_qt.QAbstractItemView.ScrollHint.EnsureVisible):
        self.scrollTo(self._item_store.indexFromItem(item), hint)

    def setItemWidget(self, item, widget):
        self.setIndexWidget(self._item_store.indexFromItem(item), widget)

    def itemWidget(self, item):
        return self.indexWidget(self._item_store.indexFromItem(item))

    def removeItemWidget(self, item):
        self.setItemWidget(item, None)

    def clear(self):
        self._item_store.clear()


class FluentListWidget(ListItemsMixin, QListView):
    """Native Fluent collection with Qt's item model kept behind the view."""


QListWidget = FluentListWidget


class FluentListWidgetItem(_qt.QListWidgetItem):
    def __init__(self, *args):
        super().__init__(*(arg._item_store if isinstance(arg, QListWidget) else arg for arg in args))

    def __lt__(self, other):
        from openlp.core.common.i18n import get_natural_key
        return get_natural_key(self.text()) < get_natural_key(other.text())

    def setHidden(self, hidden):
        super().setHidden(hidden)
        store = self.listWidget()
        if store is not None and isinstance(store.parent(), QListWidget):
            store.parent().setRowHidden(store.row(self), hidden)

    def isHidden(self):
        store = self.listWidget()
        if store is not None and isinstance(store.parent(), QListWidget):
            return store.parent().isRowHidden(store.row(self))
        return super().isHidden()


QListWidgetItem = FluentListWidgetItem
