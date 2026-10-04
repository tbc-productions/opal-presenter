"""Native FluentQt controls and explicit Qt infrastructure compatibility.

Use this namespace in operator UI modules. Qt still owns layout, model, dock,
window and projection infrastructure. Never patch PySide6's global namespace.
Adapter classes use unique Fluent names: Qt accessibility selects native
interfaces from meta-object class names, so naming a different widget type
QTabBar or QToolButton causes unsafe native casts. Qt-style names are aliases.
"""
from PySide6 import QtCore, QtWidgets as _qt
import fluentqt
from openlp.core.common.platform import is_macosx
from openlp.core.widgets.fluent_collections import (  # noqa: F401
    QListView, QListWidget, QListWidgetItem, forward_item_signals)
from openlp.core.widgets.fluent_buttons import QCheckBox, QPushButton, QRadioButton  # noqa: F401
from openlp.core.widgets.fluent_text import MnemonicButtonMixin

QLabel = fluentqt.Label


QLineEdit = fluentqt.LineEdit
QComboBox = fluentqt.ComboBox
MultiSelectComboBox = fluentqt.MultiSelectComboBox
Card = fluentqt.Card
QMenuBar = fluentqt.FluentMenuBar


def create_application_menu_bar(parent):
    """Use the system menu bar on macOS and Fluent chrome elsewhere."""
    native = is_macosx()
    bar = _qt.QMenuBar(parent) if native else fluentqt.FluentMenuBar(parent)
    bar.setNativeMenuBar(native)
    return bar


def create_application_menu(parent):
    """Application-menu submenus use Cocoa on macOS; popups remain Fluent."""
    return _qt.QMenu(parent) if is_macosx() else QMenu(parent)


class FluentMenu(fluentqt.FluentMenu):
    """Accept Qt's title/parent constructor forms."""
    def __init__(self, title='', parent=None):
        if isinstance(title, _qt.QWidget) or title is None:
            parent, title = title, ''
        super().__init__(title, parent)
        self._pressed_action = None

    def mousePressEvent(self, event):
        self._pressed_action = None
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            action = self.actionAt(event.position().toPoint())
            if (action is not None and action.isEnabled() and not action.isSeparator()
                    and action.menu() is None and not isinstance(action, _qt.QWidgetAction)):
                self._pressed_action = action
        # FluentMenu raises the native popup during mouse events. Keep its
        # window stable between press and release, retaining Qt's hover handling.
        _qt.QMenu.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        action, self._pressed_action = self._pressed_action, None
        if event.button() == QtCore.Qt.MouseButton.LeftButton and action is not None:
            if (action in self.actions() and action.isEnabled() and action.isVisible()
                    and self.actionAt(event.position().toPoint()) is action):
                from PySide6 import QtGui
                self.setActiveAction(action)
                # Qt's keyboard path commits immediately and also preserves
                # checkable actions, menu signals and the result of exec().
                _qt.QMenu.keyPressEvent(self, QtGui.QKeyEvent(
                    QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Return,
                    QtCore.Qt.KeyboardModifier.NoModifier))
            event.accept()
            return
        _qt.QMenu.mouseReleaseEvent(self, event)

    def hideEvent(self, event):
        self._pressed_action = None
        super().hideEvent(event)

    def sizeHint(self):
        # FluentMenu repeatedly sets minimumWidth from its hint as actions are
        # added. Qt's native macOS hint incorporates that minimum and margins,
        # causing unbounded growth. Measure the action content independently.
        metrics = self.fontMetrics()
        actions = [action for action in self.actions() if action.isVisible()]
        labels = [action.text().split('\t', 1)[0].replace('&', '')
                  for action in actions if not action.isSeparator()]
        shortcuts = [self.shortcutTextForAction(action) for action in actions if not action.isSeparator()]
        width = (max((metrics.horizontalAdvance(label) for label in labels), default=0)
                 + max((metrics.horizontalAdvance(shortcut) for shortcut in shortcuts), default=0))
        screen = self.screen()
        available = screen.availableGeometry().height() - 32 if screen else 720
        # Use Qt's actual row layout: Fluent's synthetic minimum counts
        # collapsed separators and can exceed the rendered rows' height.
        height = _qt.QMenu.sizeHint(self).height()
        return QtCore.QSize(max(120, width + 100), min(height, available))


QMenu = FluentMenu


class FluentSlider(fluentqt.Slider):
    """Accept Qt's orientation/parent constructor forms."""
    def __init__(self, orientation=QtCore.Qt.Orientation.Horizontal, parent=None, *, value_formatter=None):
        if isinstance(orientation, _qt.QWidget) or orientation is None:
            parent, orientation = orientation, QtCore.Qt.Orientation.Horizontal
        super().__init__(parent)
        self.setOrientation(orientation)
        self._value_formatter = value_formatter
        self._value_tooltip = None

    def mousePressEvent(self, event):
        # FluentQt 1.9.2 owns a lazily created top-level tooltip, but exposes
        # neither the tooltip nor a value formatter. Capture only the popup
        # created by this press, then retain it for subsequent drags.
        capture = self._value_tooltip is None and event.button() == QtCore.Qt.MouseButton.LeftButton
        existing = set(_qt.QApplication.topLevelWidgets()) if capture else set()
        super().mousePressEvent(event)
        if capture:
            self._value_tooltip = next(
                (widget for widget in _qt.QApplication.topLevelWidgets()
                 if widget not in existing and isinstance(widget, fluentqt.ToolTip)), None)
            if self._value_tooltip is not None:
                # FluentQt paints its own shadow. Cocoa's window shadow adds
                # an outline around the translucent margin of the popup.
                tip = self._value_tooltip
                position = tip.pos()
                tip.setWindowFlag(QtCore.Qt.WindowType.NoDropShadowWindowHint)
                tip.move(position)
                # Changing window flags hides an already visible widget.
                tip.show()
        self._format_value_tooltip()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._format_value_tooltip()

    def _format_value_tooltip(self):
        tip = self._value_tooltip
        if self._value_formatter is None or tip is None or not tip.isVisible():
            return
        # The native handler has positioned the numeric popup over the handle.
        # Preserve that anchor when the formatted text changes its dimensions.
        old_size = tip.size()
        tip.setText(self._value_formatter(self.sliderPosition()))
        if self.orientation() == QtCore.Qt.Orientation.Horizontal:
            tip.move(tip.x() + (old_size.width() - tip.width()) // 2,
                     tip.y() + old_size.height() - tip.height())
        else:
            tip.move(tip.x(), tip.y() + (old_size.height() - tip.height()) // 2)


QSlider = FluentSlider


class FluentToolButton(MnemonicButtonMixin, fluentqt.Button):
    """Fluent icon button retaining the application's QAction wiring."""
    ToolButtonPopupMode = _qt.QToolButton.ToolButtonPopupMode

    def __init__(self, parent=None):
        super().__init__(parent)
        self._action = None
        self._popup_mode = self.ToolButtonPopupMode.DelayedPopup
        self._menu = None
        self.setFluentSize(fluentqt.Button.ButtonSize.Small)
        self.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly)
        self.clicked.connect(self._activate)

    def sizeHint(self):
        hint = super().sizeHint()
        if self.fluentLayout() == fluentqt.Button.ButtonLayout.IconOnly:
            return QtCore.QSize(max(32, self.iconSize().width() + 16), max(32, self.iconSize().height() + 8))
        return hint

    def minimumSizeHint(self):
        return self.sizeHint()

    def setDefaultAction(self, action):
        if self._action is not None:
            self._action.changed.disconnect(self._sync_action)
        self._action = action
        action.changed.connect(self._sync_action)
        self._sync_action()

    def defaultAction(self):
        return self._action

    def _sync_action(self):
        action = self._action
        self.setIcon(action.icon())
        self.setText(action.text())
        self.setToolTip(action.toolTip())
        self.setEnabled(action.isEnabled())
        self.setVisible(action.isVisible())
        self.setCheckable(action.isCheckable())
        self.setChecked(action.isChecked())

    def _activate(self):
        if self._menu is not None and self._popup_mode == self.ToolButtonPopupMode.InstantPopup:
            self.showMenu()
        elif self._action is not None:
            self._action.trigger()

    def setMenu(self, menu):
        self._menu = menu

    def menu(self):
        return self._menu

    def showMenu(self):
        if self._menu is not None:
            self._menu.popup(self.mapToGlobal(QtCore.QPoint(0, self.height())))

    def setPopupMode(self, mode):
        self._popup_mode = mode

    def popupMode(self):
        return self._popup_mode

    def setAutoRaise(self, enabled):
        self.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle if enabled else fluentqt.Button.ButtonStyle.Standard)

    def setToolButtonStyle(self, style):
        layout = {QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly: fluentqt.Button.ButtonLayout.IconOnly,
                  QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly: fluentqt.Button.ButtonLayout.TextOnly}
        self.setFluentLayout(layout.get(style, fluentqt.Button.ButtonLayout.IconBefore))


QToolButton = FluentToolButton


class FluentSplitButton(MnemonicButtonMixin, fluentqt.SplitButton):
    """Native split control with OpenLP's existing tool-button action API."""
    ToolButtonPopupMode = QToolButton.ToolButtonPopupMode
    setDefaultAction = QToolButton.setDefaultAction
    defaultAction = QToolButton.defaultAction
    _activate = QToolButton._activate
    showMenu = QToolButton.showMenu
    setPopupMode = QToolButton.setPopupMode
    popupMode = QToolButton.popupMode
    setAutoRaise = QToolButton.setAutoRaise
    setToolButtonStyle = QToolButton.setToolButtonStyle

    def __init__(self, parent=None, *, checked_accent=True):
        super().__init__('', parent)
        self._checked_accent = checked_accent
        self._action = None
        self._menu = None
        self._popup_mode = self.ToolButtonPopupMode.MenuButtonPopup
        self.setMinimumHeight(40)
        self.setSizePolicy(_qt.QSizePolicy.Policy.Maximum, _qt.QSizePolicy.Policy.Fixed)
        self.setFluentSize(fluentqt.Button.ButtonSize.Small)
        self.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly)
        self.clicked.connect(self._activate)

    def _sync_action(self):
        QToolButton._sync_action(self)
        if not self._checked_accent:
            # The menu actions retain selection; keep the split surface neutral
            # so its palette-coloured QIcon matches the native chevron.
            self.setCheckable(False)

    def sizeHint(self):
        hint = super().sizeHint()
        if self.fluentLayout() == fluentqt.Button.ButtonLayout.IconOnly:
            return QtCore.QSize(max(32, self.iconSize().width() + 16) + self.secondaryWidth(),
                                max(40, self.iconSize().height() + 8))
        return hint

    def paintEvent(self, event):
        super().paintEvent(event)
        # Upstream SplitButton supports icon-font glyphs, while OpenLP actions
        # supply QIcons. Retain its native surface and draw the action icon in
        # the primary segment, without touching the chevron hit target.
        if self.iconGlyph() or self.icon().isNull():
            return
        from PySide6 import QtGui
        painter = QtGui.QPainter(self)
        primary = self.width() - self.secondaryWidth()
        x = (primary - self.iconSize().width()) // 2
        if self.layoutDirection() == QtCore.Qt.LayoutDirection.RightToLeft:
            x += self.secondaryWidth()
        rect = QtCore.QRect(x, (self.height() - self.iconSize().height()) // 2,
                            self.iconSize().width(), self.iconSize().height())
        mode = QtGui.QIcon.Mode.Normal if self.isEnabled() else QtGui.QIcon.Mode.Disabled
        state = QtGui.QIcon.State.On if self.isChecked() else QtGui.QIcon.State.Off
        self.icon().paint(painter, rect, QtCore.Qt.AlignmentFlag.AlignCenter, mode, state)

    def minimumSizeHint(self):
        return self.sizeHint()

    def setMenu(self, menu):
        self._menu = menu
        super().setMenu(menu)


QSplitButton = FluentSplitButton


def __getattr__(name):
    """Explicit bridge for Qt layout, model, window and legacy collection APIs."""
    return getattr(_qt, name)


class FluentDialogButtonBox(_qt.QDialogButtonBox):
    """Keep Qt dialog roles and signals while rendering native Fluent buttons."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._standard_buttons = {}
        self._replace_buttons()

    def _replace_buttons(self):
        for old in self.buttons():
            if isinstance(old, fluentqt.Button):
                continue
            standard = self.standardButton(old)
            role = self.buttonRole(old)
            button = QPushButton(old.text(), self)
            button.setEnabled(old.isEnabled())
            button.setDefault(old.isDefault())
            button.setAutoDefault(old.autoDefault())
            button.setIcon(old.icon())
            self.removeButton(old)
            old.deleteLater()
            self.addButton(button, role)
            if standard != self.StandardButton.NoButton:
                self._standard_buttons[standard] = button

    def addButton(self, *args):
        if isinstance(args[0], _qt.QAbstractButton):
            return super().addButton(*args)
        old = super().addButton(*args)
        standard, role = self.standardButton(old), self.buttonRole(old)
        button = QPushButton(old.text(), self)
        button.setIcon(old.icon())
        button.setDefault(old.isDefault())
        button.setAutoDefault(old.autoDefault())
        super().removeButton(old)
        old.deleteLater()
        super().addButton(button, role)
        if standard != self.StandardButton.NoButton:
            self._standard_buttons[standard] = button
        return button

    def removeButton(self, button):
        for standard, candidate in list(self._standard_buttons.items()):
            if candidate is button:
                del self._standard_buttons[standard]
        super().removeButton(button)

    def button(self, standard):
        return self._standard_buttons.get(standard)

    def standardButton(self, button):
        for standard, candidate in getattr(self, '_standard_buttons', {}).items():
            if candidate is button:
                return standard
        return super().standardButton(button)

    def standardButtons(self):
        buttons = self.StandardButton.NoButton
        for standard in self._standard_buttons:
            buttons |= standard
        return buttons

    def setStandardButtons(self, buttons):
        for button in self.buttons():
            self.removeButton(button)
            button.deleteLater()
        self._standard_buttons = {}
        super().setStandardButtons(buttons)
        self._replace_buttons()


QDialogButtonBox = FluentDialogButtonBox


class FluentWizard(_qt.QWizard):
    """Preserve wizard page/lifecycle APIs and replace its command buttons."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDefaultProperty('QSpinBox', 'numericValue', 'valueChanged(int)')
        # Qt's macOS fallback loads a wizard background from NSBundle.
        # Unbundled/offscreen Python has no bundle URL, so supply our own canvas.
        from PySide6 import QtGui
        background = QtGui.QPixmap(1, 1)
        background.fill(QtCore.Qt.GlobalColor.transparent)
        self.setPixmap(self.WizardPixmap.BackgroundPixmap, background)
        for role in (self.WizardButton.BackButton, self.WizardButton.NextButton,
                     self.WizardButton.CommitButton, self.WizardButton.FinishButton,
                     self.WizardButton.CancelButton, self.WizardButton.HelpButton,
                     self.WizardButton.CustomButton1, self.WizardButton.CustomButton2,
                     self.WizardButton.CustomButton3):
            old = self.button(role)
            button = QPushButton(old.text(), self)
            self.setButton(role, button)


QWizard = FluentWizard


class TreeItemsMixin:
    """Native Fluent hierarchy retaining OpenLP's item-based data API."""
    itemClicked = QtCore.Signal(_qt.QTreeWidgetItem, int)
    itemDoubleClicked = QtCore.Signal(_qt.QTreeWidgetItem, int)
    itemActivated = QtCore.Signal(_qt.QTreeWidgetItem, int)
    itemPressed = QtCore.Signal(_qt.QTreeWidgetItem, int)
    itemEntered = QtCore.Signal(_qt.QTreeWidgetItem, int)
    itemChanged = QtCore.Signal(_qt.QTreeWidgetItem, int)
    itemSelectionChanged = QtCore.Signal()
    currentItemChanged = QtCore.Signal(_qt.QTreeWidgetItem, _qt.QTreeWidgetItem)
    itemExpanded = QtCore.Signal(_qt.QTreeWidgetItem)
    itemCollapsed = QtCore.Signal(_qt.QTreeWidgetItem)

    def setSelectionMode(self, mode):
        value = mode.value if hasattr(mode, 'value') else int(mode)
        super().setSelectionMode(fluentqt.SelectionMode(min(value, 3)))
        self._item_store.setSelectionMode(mode)

    def selectionMode(self):
        return _qt.QAbstractItemView.SelectionMode(int(super().selectionMode()))

    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_store = _qt.QTreeWidget(self)
        self._item_store.hide()
        self.setModel(self._item_store.model())
        self.setSelectionModel(self._item_store.selectionModel())
        forward_item_signals(self, ('itemClicked', 'itemDoubleClicked', 'itemActivated', 'itemPressed',
                                    'itemEntered', 'itemChanged', 'itemSelectionChanged',
                                    'currentItemChanged', 'itemExpanded', 'itemCollapsed'))
        for view_signal, item_signal in (('clicked', 'itemClicked'), ('doubleClicked', 'itemDoubleClicked'),
                                         ('activated', 'itemActivated'), ('pressed', 'itemPressed'),
                                         ('entered', 'itemEntered')):
            signal = getattr(self._item_store, item_signal)
            getattr(self, view_signal).connect(
                lambda index, signal=signal: signal.emit(self._item_store.itemFromIndex(index), index.column()))
        if isinstance(self, fluentqt.TreeView):
            self.expanded.connect(
                lambda index: self._item_store.itemExpanded.emit(self._item_store.itemFromIndex(index)))
            self.collapsed.connect(
                lambda index: self._item_store.itemCollapsed.emit(self._item_store.itemFromIndex(index)))

    def __getattr__(self, name):
        store = self.__dict__.get('_item_store')
        if store is not None:
            return getattr(store, name)
        raise AttributeError(name)

    def selectedItems(self):
        return self._item_store.selectedItems()

    def itemBelow(self, item):
        return self._item_store.itemFromIndex(self.indexBelow(self._item_store.indexFromItem(item)))

    def itemAbove(self, item):
        return self._item_store.itemFromIndex(self.indexAbove(self._item_store.indexFromItem(item)))

    def itemAt(self, *args):
        return self._item_store.itemFromIndex(self.indexAt(*args))

    def visualItemRect(self, item):
        return self.visualRect(self._item_store.indexFromItem(item))

    def scrollToItem(self, item, hint=_qt.QAbstractItemView.ScrollHint.EnsureVisible):
        self.scrollTo(self._item_store.indexFromItem(item), hint)

    def setItemWidget(self, item, column, widget):
        self.setIndexWidget(self._item_store.indexFromItem(item, column), widget)

    def itemWidget(self, item, column):
        return self.indexWidget(self._item_store.indexFromItem(item, column))

    def expandItem(self, item):
        self.expand(self._item_store.indexFromItem(item))

    def collapseItem(self, item):
        self.collapse(self._item_store.indexFromItem(item))

    def setHeaderLabels(self, labels):
        self._item_store.setHeaderLabels(labels)
        self.header().show()

    def clear(self):
        self._item_store.clear()


class FluentTreeWidget(TreeItemsMixin, fluentqt.TreeView):
    """Native hierarchy with visible headers when column labels are supplied."""


QTreeWidget = FluentTreeWidget


class FluentTreeDataGrid(TreeItemsMixin, fluentqt.DataGrid):
    """Flat, multi-column DataGrid retaining the Qt tree-item record API."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.verticalHeader().hide()
        self.horizontalHeader().sortIndicatorChanged.connect(self._sort_items)
        self.setSelectionBehavior(_qt.QAbstractItemView.SelectionBehavior.SelectRows)

    def header(self):
        return self.horizontalHeader()

    def setHeaderHidden(self, hidden):
        self.horizontalHeader().setVisible(not hidden)

    def _sort_items(self, column, order):
        if self.isSortingEnabled():
            self._item_store.sortItems(column, order)

    def setRootIsDecorated(self, enabled):
        pass  # Flat records do not have disclosure controls.

    def setUniformRowHeights(self, enabled):
        pass  # DataGrid already uses fixed row heights.

    def setAllColumnsShowFocus(self, enabled):
        pass  # DataGrid uses row selection.

    def setIndentation(self, indentation):
        pass  # Flat records have no indentation.

    def itemBelow(self, item):
        index = self._item_store.indexFromItem(item)
        return self._item_store.itemFromIndex(self.model().index(index.row() + 1, 0))

    def itemAbove(self, item):
        index = self._item_store.indexFromItem(item)
        return self._item_store.itemFromIndex(self.model().index(index.row() - 1, 0))


QTreeDataGrid = FluentTreeDataGrid


class FluentTreeWidgetItem(_qt.QTreeWidgetItem):
    def __init__(self, *args):
        super().__init__(*(arg._item_store if isinstance(arg, (QTreeWidget, QTreeDataGrid)) else arg for arg in args))

    def setExpanded(self, expanded):
        super().setExpanded(expanded)
        store = self.treeWidget()
        if store is not None and isinstance(store.parent(), (QTreeWidget, QTreeDataGrid)):
            view = store.parent()
            view.setExpanded(store.indexFromItem(self), expanded)

    def isExpanded(self):
        store = self.treeWidget()
        if store is not None and isinstance(store.parent(), (QTreeWidget, QTreeDataGrid)):
            return store.parent().isExpanded(store.indexFromItem(self))
        return super().isExpanded()

    def setHidden(self, hidden):
        super().setHidden(hidden)
        store = self.treeWidget()
        if store is not None and isinstance(store.parent(), (QTreeWidget, QTreeDataGrid)):
            index = store.indexFromItem(self)
            store.parent().setRowHidden(index.row(), index.parent(), hidden)


QTreeWidgetItem = FluentTreeWidgetItem


class FluentTreeWidgetItemIterator(_qt.QTreeWidgetItemIterator):
    def __init__(self, *args):
        super().__init__(*(arg._item_store if isinstance(arg, (QTreeWidget, QTreeDataGrid)) else arg for arg in args))


QTreeWidgetItemIterator = FluentTreeWidgetItemIterator


class FluentTableWidget(fluentqt.DataGrid):
    """Native Fluent data grid with Qt's item-based table model."""
    itemClicked = QtCore.Signal(_qt.QTableWidgetItem)
    itemDoubleClicked = QtCore.Signal(_qt.QTableWidgetItem)
    itemActivated = QtCore.Signal(_qt.QTableWidgetItem)
    itemPressed = QtCore.Signal(_qt.QTableWidgetItem)
    itemEntered = QtCore.Signal(_qt.QTableWidgetItem)
    itemChanged = QtCore.Signal(_qt.QTableWidgetItem)
    itemSelectionChanged = QtCore.Signal()
    currentItemChanged = QtCore.Signal(_qt.QTableWidgetItem, _qt.QTableWidgetItem)
    cellClicked = QtCore.Signal(int, int)
    cellDoubleClicked = QtCore.Signal(int, int)
    cellActivated = QtCore.Signal(int, int)
    cellPressed = QtCore.Signal(int, int)
    cellEntered = QtCore.Signal(int, int)
    cellChanged = QtCore.Signal(int, int)
    currentCellChanged = QtCore.Signal(int, int, int, int)

    def __init__(self, *args):
        parent = args[-1] if args and isinstance(args[-1], _qt.QWidget) else None
        super().__init__(parent)
        self._item_store = _qt.QTableWidget(*args)
        self._item_store.setParent(self)
        self._item_store.hide()
        self.setModel(self._item_store.model())
        self.setSelectionModel(self._item_store.selectionModel())
        forward_item_signals(self, ('itemClicked', 'itemDoubleClicked', 'itemActivated', 'itemPressed',
                                    'itemEntered', 'itemChanged', 'itemSelectionChanged', 'currentItemChanged',
                                    'cellClicked', 'cellDoubleClicked', 'cellActivated', 'cellPressed',
                                    'cellEntered', 'cellChanged', 'currentCellChanged'))
        # Verse-number headers carry per-row brushes authored by OpenLP.
        # FluentQt's default header painter intentionally ignores those roles.
        self.setVerticalHeader(_qt.QHeaderView(QtCore.Qt.Orientation.Vertical, self))
        self.verticalHeader().show()
        for view_signal, cell_signal, item_signal in (
                ('clicked', 'cellClicked', 'itemClicked'), ('doubleClicked', 'cellDoubleClicked', 'itemDoubleClicked'),
                ('activated', 'cellActivated', 'itemActivated'), ('pressed', 'cellPressed', 'itemPressed'),
                ('entered', 'cellEntered', 'itemEntered')):
            def notify(index, cell_signal=cell_signal, item_signal=item_signal):
                getattr(self._item_store, cell_signal).emit(index.row(), index.column())
                item = self._item_store.item(index.row(), index.column())
                if item is not None:
                    getattr(self._item_store, item_signal).emit(item)
            getattr(self, view_signal).connect(notify)

    def __getattr__(self, name):
        store = self.__dict__.get('_item_store')
        if store is not None:
            return getattr(store, name)
        raise AttributeError(name)

    def setSelectionMode(self, mode):
        value = mode.value if hasattr(mode, 'value') else int(mode)
        super().setSelectionMode(fluentqt.SelectionMode(min(value, 3)))

    def selectionMode(self):
        return _qt.QAbstractItemView.SelectionMode(int(super().selectionMode()))

    def rowCount(self):
        return self._item_store.rowCount()

    def columnCount(self):
        return self._item_store.columnCount()

    def currentRow(self):
        return self.currentIndex().row()

    def currentColumn(self):
        return self.currentIndex().column()

    def itemAt(self, *args):
        index = self.indexAt(*args)
        return self._item_store.item(index.row(), index.column())

    def setCellWidget(self, row, column, widget):
        self.setIndexWidget(self.model().index(row, column), widget)

    def cellWidget(self, row, column):
        return self.indexWidget(self.model().index(row, column))

    def removeCellWidget(self, row, column):
        self.setCellWidget(row, column, None)

    def visualItemRect(self, item):
        return self.visualRect(self._item_store.indexFromItem(item))

    def scrollToItem(self, item, hint=_qt.QAbstractItemView.ScrollHint.EnsureVisible):
        self.scrollTo(self._item_store.indexFromItem(item), hint)

    def clear(self):
        self._item_store.clear()

    def clearContents(self):
        self._item_store.clearContents()


QTableWidget = FluentTableWidget
DataGrid = FluentTableWidget


from openlp.core.widgets.fluent_inputs import (  # noqa: E402,F401
    QTimeEdit, QCalendarWidget, QFontComboBox, QSpinBox, QGroupBox)
from openlp.core.widgets.fluent_dialogs import (  # noqa: E402,F401
    QDialog, QInputDialog, QProgressBar, QProgressDialog, QTabWidget, QMessageBox, QColorDialog)

from openlp.core.widgets.fluent_navigation import QTabBar  # noqa: E402,F401

from openlp.core.widgets.fluent_commands import QToolBar  # noqa: E402,F401

from openlp.core.widgets.fluent_tooltips import QToolTip  # noqa: E402,F401
