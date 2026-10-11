"""Native Fluent button navigation retaining logical Qt tab indexes."""
from PySide6 import QtCore, QtGui, QtWidgets as _qt
import fluentqt
from opal.core.ui.fluenticons import fluent_icon
from opal.core.widgets.fluent_buttons import QPushButton
from opal.core.widgets.fluent_text import display_text


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
                tab = fluentqt.TabViewItem(display_text(item['text']), item['glyph'], False, item['enabled'])
                self._tabs.addTab(tab)
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
        width = self.fontMetrics().horizontalAdvance(display_text(self.tabText(index))) + 32
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


class LayoutPresetButton(QPushButton):
    """Use native button painting with content aligned to the left in expanded mode."""

    def contentPaintRect(self, surface_rect):
        rect = super().contentPaintRect(surface_rect)
        if self.fluentLayout() != fluentqt.Button.ButtonLayout.IconOnly:
            rect.setWidth(min(rect.width(), self.sizeHint().width()))
        return rect


class LayoutPresetNavigation(fluentqt.NavigationView):
    """Left navigation for presets that share a single dock workspace."""
    currentChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = -1
        self._navigation_visible = True
        self._preferred_mode = self.DisplayMode.LeftCompact
        self.setDisplayMode(self._preferred_mode)
        self.setExpandedPaneWidth(180)
        self.setCompactPaneWidth(48)
        self.setTopBarHeight(0)
        self.setAnimationEnabled(False)
        self.pane = _qt.QWidget(self)
        layout = _qt.QVBoxLayout(self.pane)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.pane_toggle = QPushButton(self.pane)
        self.pane_toggle.setIcon(fluent_icon('ic_fluent_line_horizontal_3_24_regular'))
        self.pane_toggle.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly)
        self.pane_toggle.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)
        self.pane_toggle.clicked.connect(self.toggle_compact)
        self.pane_toggle.setFixedWidth(40)
        layout.addWidget(self.pane_toggle, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.buttons = []
        for index in range(4):
            button = LayoutPresetButton(self.pane)
            button.setCheckable(True)
            button.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)
            button.clicked.connect(lambda _checked=False, index=index: self.setCurrentIndex(index))
            layout.addWidget(button)
            self.buttons.append(button)
        layout.addStretch()
        self.setOwnedMainChromeWidget(self.pane)
        self.displayModeChanged.connect(self._update_button_layout)
        self._update_button_layout(self._preferred_mode)
        self.setPaneOpen(False)
        self.setCurrentIndex(0)

    def setItemText(self, index, text):
        self.buttons[index].setText(text)
        self.buttons[index].setToolTip(text)
        self.buttons[index].setAccessibleName(text)

    def currentIndex(self):
        return self._current

    def setCurrentIndex(self, index):
        if not 0 <= index < len(self.buttons):
            return
        changed = self._current != index
        self._current = index
        for item_index, button in enumerate(self.buttons):
            button.setChecked(item_index == index)
        if changed:
            self.currentChanged.emit(index)

    def toggle_compact(self):
        self.setDisplayMode(self.DisplayMode.LeftCompact if self.displayMode() == self.DisplayMode.Left
                            else self.DisplayMode.Left)
        self.setPaneOpen(self.displayMode() == self.DisplayMode.Left)

    def _update_button_layout(self, mode):
        if self._navigation_visible:
            self._preferred_mode = mode
        compact = mode == self.DisplayMode.LeftCompact
        for button in self.buttons:
            button.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly if compact
                                   else fluentqt.Button.ButtonLayout.IconBefore)

    def setNavigationVisible(self, visible):
        self._navigation_visible = visible
        self.pane.setVisible(visible)
        self.setExpandedPaneWidth(180 if visible else 0)
        self.setCompactPaneWidth(48 if visible else 0)
        self.setDisplayMode(self._preferred_mode if visible else self.DisplayMode.Left)
        self.setPaneOpen(visible and self.displayMode() == self.DisplayMode.Left)

    def isNavigationVisible(self):
        return self._navigation_visible
