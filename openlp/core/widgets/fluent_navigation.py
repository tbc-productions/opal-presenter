"""Native Fluent button navigation retaining logical Qt tab indexes."""
from PySide6 import QtCore, QtGui, QtWidgets as _qt
import fluentqt
from openlp.core.widgets.fluent_buttons import QPushButton


class FluentTabBar(_qt.QWidget):
    """Fluent tab commands supporting library rows and invisible placeholders."""
    Shape = _qt.QTabBar.Shape
    currentChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._current = -1
        self._shape = self.Shape.RoundedNorth
        self._icons = QtCore.QSize(16, 16)
        self._layout = _qt.QBoxLayout(_qt.QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

    def addTab(self, *args):
        icon, text = (args[0], args[1]) if len(args) == 2 else (QtGui.QIcon(), args[0])
        button = QPushButton(text, self)
        button.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)
        button.setIcon(icon)
        button.setIconSize(self._icons)
        button.setCheckable(True)
        button.setFluentSize(fluentqt.Button.ButtonSize.Small)
        button.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)
        button.clicked.connect(lambda checked=False, button=button: self._clicked(button))
        self._items.append({'button': button, 'data': None, 'visible': True})
        self._layout.addWidget(button)
        if self._current < 0:
            self.setCurrentIndex(0)
        return len(self._items) - 1

    def _clicked(self, button):
        for index, item in enumerate(self._items):
            if item['button'] is button:
                self.setCurrentIndex(index)
                return

    def removeTab(self, index):
        item = self._items.pop(index)
        self._layout.removeWidget(item['button'])
        item['button'].deleteLater()
        if self._items:
            self.setCurrentIndex(min(self._current, len(self._items) - 1))
        else:
            self._current = -1

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._current

    def setCurrentIndex(self, index):
        if not 0 <= index < self.count():
            return
        changed = index != self._current
        self._current = index
        for number, item in enumerate(self._items):
            button = item['button']
            button.setChecked(number == index)
            button.setFluentStyle(fluentqt.Button.ButtonStyle.Accent if number == index
                                  else fluentqt.Button.ButtonStyle.Subtle)
        if changed:
            self.currentChanged.emit(index)

    def tabText(self, index):
        return self._items[index]['button'].text()

    def setTabText(self, index, text):
        self._items[index]['button'].setText(text)

    def tabIcon(self, index):
        return self._items[index]['button'].icon()

    def setTabIcon(self, index, icon):
        self._items[index]['button'].setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)
        self._items[index]['button'].setIcon(icon)

    def setTabData(self, index, data):
        self._items[index]['data'] = data

    def tabData(self, index):
        return self._items[index]['data']

    def setTabEnabled(self, index, enabled):
        self._items[index]['button'].setEnabled(enabled)

    def isTabEnabled(self, index):
        return self._items[index]['button'].isEnabled()

    def setTabVisible(self, index, visible):
        self._items[index]['visible'] = visible
        self._items[index]['button'].setVisible(visible)

    def isTabVisible(self, index):
        return self._items[index]['visible']

    def tabRect(self, index):
        return self._items[index]['button'].geometry()

    def tabSizeHint(self, index):
        return self._items[index]['button'].sizeHint()

    def tabAt(self, point):
        for index in range(self.count()):
            if self.isTabVisible(index) and self.tabRect(index).contains(point):
                return index
        return -1

    def setShape(self, shape):
        self._shape = shape
        vertical = shape in (self.Shape.RoundedWest, self.Shape.RoundedEast,
                             self.Shape.TriangularWest, self.Shape.TriangularEast)
        self._layout.setDirection(_qt.QBoxLayout.Direction.TopToBottom if vertical
                                  else _qt.QBoxLayout.Direction.LeftToRight)

    def shape(self):
        return self._shape

    def iconSize(self):
        return self._icons

    def setIconSize(self, size):
        self._icons = size
        for item in self._items:
            item['button'].setIconSize(size)

    def setDocumentMode(self, enabled):
        pass  # Fluent commands own their surfaces.

    def setDrawBase(self, enabled):
        self._draw_base = enabled

    def drawBase(self):
        return getattr(self, '_draw_base', False)

    def setMovable(self, enabled):
        pass  # Application navigation order is fixed.

    def setExpanding(self, enabled):
        for item in self._items:
            item['button'].setSizePolicy(_qt.QSizePolicy.Policy.Expanding if enabled
                                         else _qt.QSizePolicy.Policy.Preferred, _qt.QSizePolicy.Policy.Fixed)

    def setElideMode(self, mode):
        pass  # Native buttons retain complete accessible command text.

    def setUsesScrollButtons(self, enabled):
        pass  # Library navigation wraps into two rows.

    def keyPressEvent(self, event):
        steps = {QtCore.Qt.Key.Key_Right: 1, QtCore.Qt.Key.Key_Down: 1,
                 QtCore.Qt.Key.Key_Left: -1, QtCore.Qt.Key.Key_Up: -1}
        if event.key() in steps:
            step = steps[event.key()]
            index = self.currentIndex() + step
            while 0 <= index < self.count():
                if self.isTabEnabled(index) and self.isTabVisible(index):
                    self.setCurrentIndex(index)
                    break
                index += step
            event.accept()
        else:
            super().keyPressEvent(event)


QTabBar = FluentTabBar
