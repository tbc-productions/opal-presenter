"""Native Fluent input adapters retaining OpenLP field semantics."""
from PySide6 import QtCore, QtGui, QtWidgets as _qt
import fluentqt


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


class FluentFontComboBox(fluentqt.ComboBox):
    currentFontChanged = QtCore.Signal(QtGui.QFont)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(QtGui.QFontDatabase.families())
        self._font = QtGui.QFont(self.currentText())
        self.currentTextChanged.connect(self._font_selected)

    def _font_selected(self, text):
        self._font.setFamily(text)
        self.currentFontChanged.emit(self.currentFont())

    def currentFont(self):
        return QtGui.QFont(self._font)

    def setCurrentFont(self, font):
        self._font = QtGui.QFont(font)
        if self.findText(font.family()) < 0:
            self.addItem(font.family())
        self.setCurrentText(font.family())


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
        self._heading = fluentqt.Label(title, self)
        self._toggle = fluentqt.CheckBox(title, self)
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
        self._heading.setText(title)
        self._toggle.setText(title)
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
        for child in self.findChildren(_qt.QWidget, options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly):
            if child in (self._heading, self._toggle):
                continue
            if checked:
                child.setEnabled(self._disabled_children.pop(child, True))
            else:
                if child not in self._disabled_children:
                    self._disabled_children[child] = child.isEnabledTo(self)
                child.setEnabled(False)
        if self._checkable:
            self.toggled.emit(checked)

    def childEvent(self, event):
        super().childEvent(event)
        if not hasattr(self, '_disabled_children'):
            return
        child = event.child()
        if (event.added() or event.polished()) and isinstance(child, _qt.QWidget):
            if self._checkable and not self.isChecked() and child not in (self._heading, self._toggle):
                if child not in self._disabled_children:
                    self._disabled_children[child] = child.isEnabledTo(self)
                child.setEnabled(False)
        elif event.removed():
            self._disabled_children.pop(child, None)

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
