"""Native Fluent input adapters retaining OpenLP field semantics."""
from difflib import SequenceMatcher

from PySide6 import QtCore, QtGui, QtWidgets as _qt
import fluentqt
from openlp.core.widgets.fluent_buttons import QCheckBox
from openlp.core.widgets.fluent_text import display_text


class FluentTimeEdit(fluentqt.TimePicker):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setClockIdentifier(fluentqt.TimePicker.ClockIdentifier.TwentyFourHourClock)


QTimeEdit = FluentTimeEdit


class FluentCalendarWidget(fluentqt.CalendarView):
    VerticalHeaderFormat = _qt.QCalendarWidget.VerticalHeaderFormat
    HorizontalHeaderFormat = _qt.QCalendarWidget.HorizontalHeaderFormat
    selectionChanged = QtCore.Signal()
    clicked = QtCore.Signal(QtCore.QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selectedDateChanged.connect(lambda date: self.selectionChanged.emit())
        self.dateActivated.connect(self.clicked)

    def setGridVisible(self, visible):
        self.setProperty('gridVisible', visible)

    def setVerticalHeaderFormat(self, format):
        self.setProperty('verticalHeaderFormat', format.value)

    def setHorizontalHeaderFormat(self, format):
        self.setProperty('horizontalHeaderFormat', format.value)

    def setMinimumDate(self, date):
        self.setMinDate(date)

    def setMaximumDate(self, date):
        self.setMaxDate(date)


QCalendarWidget = FluentCalendarWidget


class _FontOptionDelegate(_qt.QStyledItemDelegate):
    """Paint font previews using the popup's Fluent tokens and selection indicator."""

    def __init__(self, view):
        super().__init__(view)
        self._view = view
        self._theme_host = fluentqt.FluentWidget(view)
        self._theme_host.hide()

    def sizeHint(self, option, index):
        font = index.data(QtCore.Qt.ItemDataRole.FontRole)
        metrics = QtGui.QFontMetrics(font if isinstance(font, QtGui.QFont) else option.font)
        return QtCore.QSize(metrics.horizontalAdvance(str(index.data() or '')) + 32,
                            max(40, metrics.height() + 16))

    def paint(self, painter, option, index):
        font = index.data(QtCore.Qt.ItemDataRole.FontRole)
        if not isinstance(font, QtGui.QFont):
            super().paint(painter, option, index)
            return
        colors = self._theme_host.theme_tokens().colors
        text_rect = option.rect.adjusted(16, 0, -16, 0)
        painter.save()
        painter.setClipRect(option.rect, QtCore.Qt.ClipOperation.IntersectClip)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        enabled = bool(option.state & _qt.QStyle.StateFlag.State_Enabled)
        active = bool(option.state & (_qt.QStyle.StateFlag.State_Selected | _qt.QStyle.StateFlag.State_MouseOver))
        if enabled and active:
            pressed = bool(option.state & _qt.QStyle.StateFlag.State_Sunken)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(colors.subtleTertiary if pressed else colors.subtleSecondary)
            painter.drawRoundedRect(QtCore.QRectF(option.rect.adjusted(0, 2, 0, -2)), 4, 4)
        if enabled and self._view.selectionIndicatorVisible():
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(colors.accentDefault)
            painter.drawRoundedRect(self._view.selectedIndicatorRect(), 1.5, 1.5)
        painter.setFont(font)
        painter.setPen(colors.textPrimary if enabled else colors.textDisabled)
        rtl = option.direction == QtCore.Qt.LayoutDirection.RightToLeft
        alignment = QtCore.Qt.AlignmentFlag.AlignRight if rtl else QtCore.Qt.AlignmentFlag.AlignLeft
        text = QtGui.QFontMetrics(font).elidedText(
            str(index.data() or ''), QtCore.Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, alignment | QtCore.Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()


class FontPreviewComboBox(fluentqt.ComboBox):
    """Opt in to per-option fonts on the Fluent dropdown's actual ListView."""

    def showPopup(self):
        super().showPopup()
        # The Fluent flyout belongs to the window, rather than the combo itself.
        # Identify its visible list by the shared model; ignore Qt's hidden fallback.
        for view in _qt.QApplication.allWidgets():
            if (isinstance(view, _qt.QListView) and view.isVisible() and view.model() is self.model()
                    and not isinstance(view.itemDelegate(), _FontOptionDelegate)):
                view.setItemDelegate(_FontOptionDelegate(view))
                view.doItemsLayout()


class FluentFontComboBox(FontPreviewComboBox):
    currentFontChanged = QtCore.Signal(QtGui.QFont)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems([family for family in QtGui.QFontDatabase.families() if not family.startswith('.')])
        for index in range(self.count()):
            self._set_item_font(index)
        self._font = QtGui.QFont(self.currentText())
        # Render the standard Fluent select chrome; its editable variant styles
        # the arrow as a separate button and uses text-field padding.
        self._select_chrome = fluentqt.ComboBox(self)
        self._select_chrome.addItem('')
        self._select_chrome.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._select_chrome.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Keep the editor outside QComboBox's editable layout. Qt repositions its
        # managed line edit on focus/popup changes, overriding Fluent's padding.
        editor = self._font_editor = _qt.QLineEdit(self)
        editor.setFrame(False)
        editor.setStyleSheet('QLineEdit { background: transparent; border: none; padding: 0; }')
        editor.setText(super().currentText())
        self.setFocusProxy(editor)
        self.setInsertPolicy(_qt.QComboBox.InsertPolicy.NoInsert)
        completer = _qt.QCompleter(self.model(), editor)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(_qt.QCompleter.CompletionMode.InlineCompletion)
        editor.setCompleter(completer)
        # Handle Enter/Escape before QCompleter consumes them.
        editor.installEventFilter(self)
        editor.textEdited.connect(self._highlight_font_match)
        self.currentIndexChanged.connect(
            lambda index: self._font_selected(self.itemText(index)) if index >= 0 else self.setCurrentText(''))
        self.lineEdit().editingFinished.connect(self._commit_font_name)

    def lineEdit(self):
        return self._font_editor

    def currentText(self):
        if hasattr(self, '_font_editor'):
            return self._font_editor.text()
        return super().currentText()

    def setCurrentText(self, text):
        if hasattr(self, '_font_editor'):
            self._font_editor.setText(text)
        else:
            super().setCurrentText(text)

    def paintEvent(self, event):
        if not hasattr(self, '_select_chrome'):
            return super().paintEvent(event)
        # The standard select child paints the whole surface, including the chevron.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_select_chrome'):
            self._select_chrome.setGeometry(self.rect())
            padding = self._select_chrome.contentPaddingH()
            trailing = padding * 2 + self.chevronSize()
            self.lineEdit().setGeometry(padding, 0, max(0, self.width() - padding - trailing), self.height())
            # Match the select's text inset, accounting for QLineEdit's extra inset.
            self.lineEdit().setTextMargins(-2, 0, 0, 0)
            self.lineEdit().raise_()

    def enterEvent(self, event):
        super().enterEvent(event)
        if hasattr(self, '_select_chrome'):
            self._select_chrome.setAttribute(QtCore.Qt.WidgetAttribute.WA_UnderMouse, True)
            self._select_chrome.enterEvent(event)
            self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if hasattr(self, '_select_chrome'):
            self._select_chrome.setAttribute(QtCore.Qt.WidgetAttribute.WA_UnderMouse, False)
            self._select_chrome.leaveEvent(event)
            self.update()

    def eventFilter(self, watched, event):
        if watched is self.lineEdit() and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                QtCore.QTimer.singleShot(0, self, self.showPopup)
                QtCore.QTimer.singleShot(0, self, self.lineEdit().selectAll)
        if (watched is self.lineEdit() and event.type() == QtCore.QEvent.Type.ShortcutOverride
                and event.key() == QtCore.Qt.Key.Key_Escape):
            # The Fluent flyout otherwise consumes Escape before the editor sees
            # KeyPress. Restore the committed name and keep Escape in this field.
            self.setCurrentText(self._font.family() if self.currentIndex() >= 0 else '')
            self.hidePopup()
            event.accept()
            return True
        if watched is self.lineEdit() and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                self._commit_font_name()
                self.hidePopup()
                return True
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.setCurrentText(self._font.family() if self.currentIndex() >= 0 else '')
                self.hidePopup()
                return True
            if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
                self._step_font(-1 if event.key() == QtCore.Qt.Key.Key_Up else 1)
                return True
        return super().eventFilter(watched, event)

    def showPopup(self):
        super().showPopup()
        self._highlight_font_match(self.currentText())
        self.lineEdit().setFocus(QtCore.Qt.FocusReason.PopupFocusReason)

    def _font_list(self):
        return next((view for view in _qt.QApplication.allWidgets()
                     if isinstance(view, _qt.QListView) and view.isVisible() and view.model() is self.model()), None)

    def _closest_font_index(self, text):
        """Prefer exact names, prefixes and substrings before matching spelling."""
        query = text.strip().casefold()
        if not query:
            return self.currentIndex()

        def score(row):
            family = self.itemText(row).casefold()
            return (family == query, family.startswith(query), query in family,
                    SequenceMatcher(None, query, family).ratio())

        return max(range(self.count()), key=score, default=-1)

    def _highlight_font_match(self, text):
        view = self._font_list()
        if view is None:
            return
        row = self._closest_font_index(text)
        if row >= 0:
            view.setCurrentIndex(self.model().index(row, 0))
            view.scrollTo(view.currentIndex())

    def _step_font(self, step):
        view = self._font_list()
        if view is None:
            self.showPopup()
            view = self._font_list()
        if view is None:
            return
        row = view.currentIndex().row() + step
        if 0 <= row < self.count():
            view.setCurrentIndex(self.model().index(row, 0))
            view.scrollTo(view.currentIndex())
            self.setCurrentFont(QtGui.QFont(self.itemText(row)))
            self.activated.emit(row)
            self.lineEdit().selectAll()

    def _commit_font_name(self):
        """Apply a completed name, rather than re-rendering with each partially typed family."""
        name = self.currentText().strip()
        if not name:
            if self.currentIndex() >= 0:
                self.setCurrentText(self._font.family())
            return
        # Retain an existing hidden system family without adding it to the picker.
        if name == self._font.family() and name.startswith('.'):
            return
        row = self._closest_font_index(name)
        if row < 0:
            return
        match = self.itemText(row)
        if match != self._font.family() or self.currentIndex() < 0:
            self.setCurrentFont(QtGui.QFont(match))
            self.activated.emit(self.currentIndex())
        else:
            self.setCurrentText(match)

    def _set_item_font(self, index):
        font = QtGui.QFont(self.font())
        font.setStyleName('')
        font.setFamily(self.itemText(index))
        self.setItemData(index, font, QtCore.Qt.ItemDataRole.FontRole)

    def _font_selected(self, text):
        self._font.setFamily(text)
        self.setCurrentText(text)
        self.currentFontChanged.emit(self.currentFont())

    def currentFont(self):
        return QtGui.QFont(self._font)

    def setCurrentFont(self, font):
        self._font = QtGui.QFont(font)
        if self.findText(font.family()) < 0 and not font.family().startswith('.'):
            self.addItem(font.family())
            self._set_item_font(self.count() - 1)
        self.setCurrentIndex(self.findText(font.family()))
        self.setCurrentText(font.family())
        if self.currentIndex() < 0:
            self.currentFontChanged.emit(self.currentFont())


QFontComboBox = FluentFontComboBox


class FluentSpinBox(_qt.QWidget):
    """Integer adapter composed from a native Fluent NumberBox and unit label."""
    valueChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._field = fluentqt.NumberBox(self)
        self._unit = fluentqt.Label(self)
        self._unit.hide()
        self._last_value = 0
        layout = _qt.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._field, 1)
        layout.addWidget(self._unit)
        self.setFocusProxy(self._field)
        self._field.setDisplayPrecision(0)
        self._field.setRange(0, 99)
        self._field.setValue(0)
        self._field.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
        self._field.valueChanged.connect(self._value_changed)

    def __getattr__(self, name):
        field = self.__dict__.get('_field')
        if field is not None:
            return getattr(field, name)
        raise AttributeError(name)

    def _value_changed(self, value):
        import math
        if not math.isfinite(value):
            self._field.setValue(self._last_value)
            return
        integer = round(value)
        if value != integer:
            self._field.setValue(integer)
            return
        self._last_value = integer
        self.valueChanged.emit(integer)

    def value(self):
        return self._last_value

    def setValue(self, value):
        self._field.setValue(round(value))

    def minimum(self):
        return int(self._field.minimum())

    def maximum(self):
        return int(self._field.maximum())

    def setMinimum(self, value):
        self._field.setMinimum(value)

    def setMaximum(self, value):
        self._field.setMaximum(value)

    def setRange(self, minimum, maximum):
        self._field.setRange(minimum, maximum)

    def setSingleStep(self, step):
        self._field.setSmallChange(step)

    def singleStep(self):
        return int(self._field.smallChange())

    def setSuffix(self, suffix):
        self._unit.setText(suffix)
        self._unit.setVisible(bool(suffix))

    def suffix(self):
        return self._unit.text()

    def setCompactWidth(self, digits):
        """Fit a toolbar number field to its digits, spin controls and unit."""
        field = self._field
        text_width = max(field.fontMetrics().horizontalAdvance(str(digit) * digits) for digit in range(10))
        margins = field.contentMargins()
        spin_width = (field.compactSpinButtonReservedWidth()
                      + field.spinButtonRightMargin() + field.spinButtonTextGap() + 24)
        width = text_width + max(margins.left() + margins.right() + 8, spin_width)
        field.setFixedWidth(width)
        unit_width = self._unit.sizeHint().width() + self.layout().spacing() if self._unit.text() else 0
        self.setFixedWidth(width + unit_width)
        self.setSizePolicy(_qt.QSizePolicy.Policy.Fixed, _qt.QSizePolicy.Policy.Fixed)

    def keyPressEvent(self, event):
        steps = {QtCore.Qt.Key.Key_Up: 1, QtCore.Qt.Key.Key_Down: -1,
                 QtCore.Qt.Key.Key_PageUp: 10, QtCore.Qt.Key.Key_PageDown: -10}
        if event.key() in steps:
            self.setValue(self.value() + steps[event.key()] * self.singleStep())
            event.accept()
        else:
            super().keyPressEvent(event)

    def sizeHint(self):
        size = self._field.sizeHint()
        if self._unit.text():
            size.setWidth(size.width() + self._unit.sizeHint().width() + 4)
        return size

    numericValue = QtCore.Property(int, value, setValue, notify=valueChanged)


QSpinBox = FluentSpinBox


class FluentGroupBox(fluentqt.Card):
    """Fluent card with native heading/check controls and Qt grouping semantics."""
    toggled = QtCore.Signal(bool)
    clicked = QtCore.Signal(bool)

    def __init__(self, title='', parent=None):
        if isinstance(title, _qt.QWidget) or title is None:
            parent, title = title, ''
        super().__init__(parent)
        self._heading = fluentqt.Label(display_text(title), self)
        self._toggle = QCheckBox(title, self)
        self._toggle.setChecked(True)
        self._toggle.hide()
        self._checkable = False
        self._layout_margins = None
        self._disabled_children = {}
        self._toggle.toggled.connect(self._toggle_content)
        self._toggle.clicked.connect(self.clicked)

    def title(self):
        return self._heading.text()

    def setTitle(self, title):
        self._heading.setText(display_text(title))
        self._toggle.setText(title)
        self._position_heading()

    def setHeadingTypography(self, role):
        """Apply Fluent typography to both plain and checkable card headings."""
        self._heading.setFluentTypography(role)
        self._toggle.setFont(self._heading.font())
        self._position_heading()

    def setCheckable(self, checkable):
        self._checkable = checkable
        self._heading.setVisible(not checkable)
        self._toggle.setVisible(checkable)
        self._toggle_content(self.isChecked() if checkable else True)
        self._position_heading()

    def isCheckable(self):
        return self._checkable

    def setChecked(self, checked):
        self._toggle.setChecked(checked)

    def isChecked(self):
        return self._toggle.isChecked()

    def _toggle_content(self, checked):
        self._sync_content_enabled(checked)
        if self._checkable:
            self.toggled.emit(checked)

    def _sync_content_enabled(self, checked=None):
        if checked is None:
            checked = not self._checkable or self.isChecked()
        children = self.findChildren(_qt.QWidget, options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly)
        for child in list(self._disabled_children):
            if child not in children:
                del self._disabled_children[child]
        for child in children:
            if child in (self._heading, self._toggle):
                continue
            if checked:
                if child in self._disabled_children:
                    child.setEnabled(self._disabled_children.pop(child))
            else:
                if child not in self._disabled_children:
                    self._disabled_children[child] = child.isEnabledTo(self)
                child.setEnabled(False)

    def childEvent(self, event):
        super().childEvent(event)
        if not hasattr(self, '_disabled_children'):
            return
        if event.added() or event.removed():
            # ChildAdded arrives before the child's derived C++ constructor,
            # and ChildRemoved may arrive during destruction. Asking Shiboken
            # to wrap event.child() at either point can crash in type discovery.
            QtCore.QTimer.singleShot(0, self, self._sync_content_enabled)
        elif event.polished():
            self._sync_content_enabled()

    def setFlat(self, flat):
        self.setBorderVisible(not flat)

    def setAlignment(self, alignment):
        self._heading.setAlignment(alignment)

    def _position_heading(self):
        if not hasattr(self, '_heading'):
            return
        heading = self._toggle if self._checkable else self._heading
        height = max(24, heading.sizeHint().height())
        heading.setGeometry(12, 6, max(0, self.width() - 24), height)
        layout = _qt.QWidget.layout(self)
        if layout is not None:
            if self._layout_margins is None:
                self._layout_margins = layout.contentsMargins()
            margins = self._layout_margins
            layout.setContentsMargins(margins.left(), margins.top() + height + 8,
                                      margins.right(), margins.bottom())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_heading()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_heading()


QGroupBox = FluentGroupBox
