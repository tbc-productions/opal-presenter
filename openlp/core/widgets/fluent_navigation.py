"""Native Fluent button navigation retaining logical Qt tab indexes."""
from PySide6 import QtCore, QtGui, QtWidgets as _qt
import fluentqt
from openlp.core.widgets.fluent_buttons import QPushButton


class FluentTabBar(_qt.QWidget):
    """Native TabView with stable logical indexes for hidden placeholders."""
    Shape = _qt.QTabBar.Shape
    currentChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._current = -1
        self._shape = self.Shape.RoundedNorth
        self._icons = QtCore.QSize(16, 16)
        self._visible_indexes = []
        self._tabs = fluentqt.TabView(self)
        self._tabs.setTabsClosable(False)
        self._tabs.setAddTabButtonVisible(False)
        self._tabs.setTabReorderEnabled(False)
        self._tabs.setTabWidthMode(fluentqt.TabView.TabWidthMode.SizeToContent)
        layout = _qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tabs)
        self._tabs.currentChanged.connect(self._selected)

    def _selected(self, physical):
        if 0 <= physical < len(self._visible_indexes):
            self.setCurrentIndex(self._visible_indexes[physical])

    def _rebuild(self):
        blocker = QtCore.QSignalBlocker(self._tabs)
        self._tabs.clearTabs()
        self._visible_indexes = []
        for index, item in enumerate(self._items):
            if item['visible']:
                self._visible_indexes.append(index)
                self._tabs.addTab(fluentqt.TabViewItem(item['text'], item['glyph'], False, item['enabled']))
        if self._current in self._visible_indexes:
            self._tabs.setSelectedIndex(self._visible_indexes.index(self._current))
        del blocker
        self.updateGeometry()

    def addTab(self, *args):
        icon, text = (args[0], args[1]) if len(args) == 2 else (QtGui.QIcon(), args[0])
        self._items.append(dict(icon=icon, text=text, glyph='', data=None, visible=True, enabled=True))
        self._rebuild()
        if self._current < 0:
            self.setCurrentIndex(0)
        return self.count() - 1

    def removeTab(self, index):
        self._items.pop(index)
        self._current = min(self._current, self.count() - 1)
        self._rebuild()

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._current

    def setCurrentIndex(self, index):
        if not 0 <= index < self.count():
            return
        changed = self._current != index
        self._current = index
        blocker = QtCore.QSignalBlocker(self._tabs)
        self._tabs.setSelectedIndex(self._visible_indexes.index(index) if index in self._visible_indexes else -1)
        del blocker
        if changed:
            self.currentChanged.emit(index)

    def tabText(self, index):
        return self._items[index]['text']

    def setTabText(self, index, text):
        self._items[index]['text'] = text
        self._rebuild()

    def tabIcon(self, index):
        return self._items[index]['icon']

    def setTabIcon(self, index, icon):
        self._items[index]['icon'] = icon

    def setTabGlyph(self, index, glyph):
        self._items[index]['glyph'] = glyph
        self._rebuild()

    def setTabData(self, index, data):
        self._items[index]['data'] = data

    def tabData(self, index):
        return self._items[index]['data']

    def setTabEnabled(self, index, enabled):
        self._items[index]['enabled'] = enabled
        self._rebuild()

    def isTabEnabled(self, index):
        return self._items[index]['enabled']

    def setTabVisible(self, index, visible):
        self._items[index]['visible'] = visible
        self._rebuild()

    def isTabVisible(self, index):
        return self._items[index]['visible']

    def tabRect(self, index):
        if index not in self._visible_indexes:
            return QtCore.QRect()
        return self._tabs.tabGeometry(self._visible_indexes.index(index)).translated(self._tabs.pos())

    def tabSizeHint(self, index):
        width = self.fontMetrics().horizontalAdvance(self.tabText(index)) + 32
        if self._items[index]['glyph']:
            width += 24
        return QtCore.QSize(width if self.isTabVisible(index) else 0, self._tabs.sizeHint().height())

    def tabAt(self, point):
        for index in self._visible_indexes:
            if self.tabRect(index).contains(point):
                return index
        return -1

    def setShape(self, shape):
        self._shape = shape

    def shape(self):
        return self._shape

    def iconSize(self):
        return self._icons

    def setIconSize(self, size):
        self._icons = size

    def setExpanding(self, enabled):
        self._tabs.setTabWidthMode(fluentqt.TabView.TabWidthMode.Equal if enabled
                                  else fluentqt.TabView.TabWidthMode.SizeToContent)

    def setDocumentMode(self, enabled):
        pass

    def setDrawBase(self, enabled):
        self._draw_base = enabled

    def drawBase(self):
        return getattr(self, '_draw_base', False)

    def setMovable(self, enabled):
        self._tabs.setTabReorderEnabled(enabled)

    def setElideMode(self, mode):
        pass

    def setUsesScrollButtons(self, enabled):
        pass  # Native TabView owns its overflow controls.


QTabBar = FluentTabBar
