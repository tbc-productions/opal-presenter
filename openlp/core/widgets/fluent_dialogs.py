"""Native Fluent navigation and feedback controls with Qt modal lifecycle."""
from PySide6 import QtCore, QtWidgets as _qt
import fluentqt
from fluentqt.design import Spacing
from openlp.core.widgets.fluent_buttons import QPushButton


class _ProgressRail(fluentqt.ProgressBar):
    """Expand the native Fluent rail to its allocated layout width."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(_qt.QSizePolicy.Policy.Expanding, _qt.QSizePolicy.Policy.Fixed)
        self.setFixedHeight(Spacing.ControlHeight.Large)

    def resizeEvent(self, event):
        self.setBarWidth(max(1, event.size().width()))
        super().resizeEvent(event)


class FluentProgressBar(_qt.QWidget):
    """Native Fluent progress rail with an optional accessible progress label."""
    valueChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(_qt.QSizePolicy.Policy.Expanding, _qt.QSizePolicy.Policy.Fixed)
        self._bar = _ProgressRail(self)
        self._label = fluentqt.Label(self)
        self._format = '%p%'
        self._text_visible = True
        self._minimum, self._maximum = 0, 100
        self._bar.setRange(0, 100)
        layout = _qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._bar)
        layout.addWidget(self._label, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self._bar.valueChanged.connect(self._changed)
        self._refresh()

    def _changed(self, value):
        self._refresh()
        self.valueChanged.emit(round(value))

    def _refresh(self):
        self._bar.setIsIndeterminate(self.minimum() == 0 and self.maximum() == 0)
        self._label.setText(self.text())
        self._label.setVisible(self._text_visible and not self._bar.isIndeterminate())

    def value(self):
        return round(self._bar.value())

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    def setValue(self, value):
        self._bar.setValue(value)

    def setRange(self, minimum, maximum):
        self._minimum, self._maximum = minimum, max(minimum, maximum)
        self._bar.setRange(minimum, maximum)
        self._refresh()

    def setMinimum(self, value):
        self.setRange(value, self.maximum())

    def setMaximum(self, value):
        self.setRange(self.minimum(), value)

    def setFormat(self, format):
        self._format = format
        self._refresh()

    def format(self):
        return self._format

    def setTextVisible(self, visible):
        self._text_visible = visible
        self._refresh()

    def isTextVisible(self):
        return self._text_visible

    def text(self):
        total = self.maximum() - self.minimum()
        percent = round((self.value() - self.minimum()) * 100 / total) if total else 0
        return self._format.replace('%p', str(percent)).replace('%v', str(self.value())).replace('%m', str(total))

    def reset(self):
        self.setValue(self.minimum())


QProgressBar = FluentProgressBar


class _TabNavigation(fluentqt.TabView):
    def setExpanding(self, expanding):
        self.setTabWidthMode(fluentqt.TabView.TabWidthMode.Equal if expanding
                             else fluentqt.TabView.TabWidthMode.SizeToContent)


class FluentTabWidget(_qt.QWidget):
    """Fluent TabView navigation with Qt's page-stack lifecycle."""
    TabPosition = _qt.QTabWidget.TabPosition
    currentChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs = _TabNavigation(self)
        self._tabs.setTabsClosable(False)
        self._tabs.setAddTabButtonVisible(False)
        self._tabs.setTabWidthMode(fluentqt.TabView.TabWidthMode.SizeToContent)
        self._pages = _qt.QStackedWidget(self)
        self._position = self.TabPosition.North
        self._rail = _qt.QWidget(self)
        self._rail_layout = _qt.QVBoxLayout(self._rail)
        self._rail_layout.setContentsMargins(0, 0, 0, 0)
        self._rail.hide()
        self._rail_buttons = []
        layout = _qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tabs)
        layout.addWidget(self._pages, 1)
        self._tabs.currentChanged.connect(self._selected)

    def _selected(self, index):
        self._pages.setCurrentIndex(index)
        for number, button in enumerate(self._rail_buttons):
            button.setChecked(number == index)
        self.currentChanged.emit(index)

    def addTab(self, page, label):
        index = self._pages.addWidget(page)
        self._tabs.addTab(label)
        self._refresh_rail()
        return index

    def removeTab(self, index):
        page = self.widget(index)
        if page is not None:
            self._pages.removeWidget(page)
            self._tabs.removeTab(index)
            self._refresh_rail()

    def count(self):
        return self._pages.count()

    def widget(self, index):
        return self._pages.widget(index)

    def indexOf(self, page):
        return self._pages.indexOf(page)

    def currentWidget(self):
        return self._pages.currentWidget()

    def currentIndex(self):
        return self._tabs.selectedIndex()

    def setCurrentIndex(self, index):
        self._tabs.setSelectedIndex(index)

    def setCurrentWidget(self, page):
        self.setCurrentIndex(self.indexOf(page))

    def setTabText(self, index, text):
        self._tabs.setTabText(index, text)
        if index < len(self._rail_buttons):
            self._rail_buttons[index].setText(text)

    def tabText(self, index):
        return self._tabs.tabAt(index).text

    def setTabEnabled(self, index, enabled):
        self._tabs.setTabEnabled(index, enabled)
        self.widget(index).setEnabled(enabled)
        if index < len(self._rail_buttons):
            self._rail_buttons[index].setEnabled(enabled)

    def isTabEnabled(self, index):
        return self._tabs.tabAt(index).enabled

    def _refresh_rail(self):
        for button in self._rail_buttons:
            self._rail_layout.removeWidget(button)
            button.deleteLater()
        self._rail_buttons = []
        for index in range(self.count()):
            button = QPushButton(self.tabText(index), self._rail)
            button.setCheckable(True)
            button.setChecked(index == self.currentIndex())
            button.setEnabled(self.isTabEnabled(index))
            button.clicked.connect(lambda checked=False, index=index: self.setCurrentIndex(index))
            self._rail_layout.addWidget(button)
            self._rail_buttons.append(button)

    def setTabPosition(self, position):
        self._position = position
        vertical = position in (self.TabPosition.West, self.TabPosition.East)
        layout = self.layout()
        layout.removeWidget(self._tabs)
        layout.removeWidget(self._rail)
        direction = {self.TabPosition.North: _qt.QBoxLayout.Direction.TopToBottom,
                     self.TabPosition.South: _qt.QBoxLayout.Direction.BottomToTop,
                     self.TabPosition.West: _qt.QBoxLayout.Direction.LeftToRight,
                     self.TabPosition.East: _qt.QBoxLayout.Direction.RightToLeft}[position]
        layout.setDirection(direction)
        layout.insertWidget(0, self._rail if vertical else self._tabs)
        self._rail.setVisible(vertical)
        self._tabs.setVisible(not vertical)

    def tabPosition(self):
        return self._position

    def tabBar(self):
        return self._tabs

    def setExpanding(self, expanding):
        self._tabs.setTabWidthMode(fluentqt.TabView.TabWidthMode.Equal if expanding
                                   else fluentqt.TabView.TabWidthMode.SizeToContent)

    def setDocumentMode(self, enabled):
        # The Fluent TabView owns its surface; page stacks have no Qt tab frame.
        self.setProperty('documentMode', enabled)


QTabWidget = FluentTabWidget


class FluentProgressDialog(_qt.QDialog):
    """Qt modal lifecycle with native Fluent label, rail and cancellation button."""
    canceled = QtCore.Signal()

    def __init__(self, *args):
        label, cancel, minimum, maximum, parent = '', 'Cancel', 0, 100, None
        if args and isinstance(args[0], str):
            label, cancel, minimum, maximum = args[:4]
            if len(args) > 4:
                parent = args[4]
        elif args:
            parent = args[0]
        super().__init__(parent)
        self._label = fluentqt.Label(label, self)
        self._progress = QProgressBar(self)
        self._progress.setRange(minimum, maximum)
        self._cancel = QPushButton(cancel, self)
        self._cancel.setVisible(bool(cancel))
        self._cancel.clicked.connect(self.cancel)
        self._auto_close = True
        self._auto_reset = True
        self._canceled = False
        self._duration = 4000
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.show)
        layout = _qt.QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._progress)
        layout.addWidget(self._cancel, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.setMinimumWidth(300)

    def setLabelText(self, text):
        self._label.setText(text)

    def labelText(self):
        return self._label.text()

    def setRange(self, minimum, maximum):
        self._progress.setRange(minimum, maximum)

    def setMinimum(self, minimum):
        self._progress.setMinimum(minimum)

    def setMaximum(self, maximum):
        self._progress.setMaximum(maximum)

    def minimum(self):
        return self._progress.minimum()

    def maximum(self):
        return self._progress.maximum()

    def value(self):
        return self._progress.value()

    def setValue(self, value):
        if self._canceled:
            return
        self._progress.setValue(value)
        if self.maximum() > self.minimum() and value >= self.maximum():
            self._timer.stop()
            if self._auto_close:
                self.hide()
            if self._auto_reset:
                self._progress.reset()
        elif not self.isVisible() and not self._timer.isActive():
            self._timer.start(self._duration)
        if self.windowModality() != QtCore.Qt.WindowModality.NonModal:
            _qt.QApplication.processEvents()

    def setMinimumDuration(self, duration):
        self._duration = duration
        if self._timer.isActive():
            self._timer.start(duration)

    def minimumDuration(self):
        return self._duration

    def setCancelButton(self, button):
        self._cancel.hide()
        if button is not None:
            self._cancel = button
            button.setParent(self)
            self.layout().addWidget(button)
            button.clicked.connect(self.cancel)

    def setCancelButtonText(self, text):
        self._cancel.setText(text)
        self._cancel.setVisible(bool(text))

    def setAutoClose(self, enabled):
        self._auto_close = enabled

    def autoClose(self):
        return self._auto_close

    def setAutoReset(self, enabled):
        self._auto_reset = enabled

    def autoReset(self):
        return self._auto_reset

    def wasCanceled(self):
        return self._canceled

    def cancel(self):
        self._canceled = True
        self._timer.stop()
        self.hide()
        self.canceled.emit()

    def reject(self):
        self.cancel()
        super().reject()

    def reset(self):
        self._timer.stop()
        self._canceled = False
        self._progress.reset()
        if self._auto_close:
            self.hide()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


QProgressDialog = FluentProgressDialog


class FluentMessageBox(_qt.QMessageBox):
    """Qt message/result contracts with native Fluent command controls."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fluent_commands = {}
        self._replace_commands()

    def _replace_commands(self):
        default = self.defaultButton()
        escape = self.escapeButton()
        for old in list(super().buttons()):
            if isinstance(old, fluentqt.Button):
                continue
            standard = super().standardButton(old)
            role = self.buttonRole(old)
            button = QPushButton(old.text(), self)
            button.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)
            button.setIcon(old.icon())
            button.setEnabled(old.isEnabled())
            super().removeButton(old)
            old.deleteLater()
            super().addButton(button, role)
            if standard != self.StandardButton.NoButton:
                self._fluent_commands[standard] = button
            if old is default:
                super().setDefaultButton(button)
            if old is escape:
                super().setEscapeButton(button)
        if self.escapeButton() is None:
            candidate = self._fluent_commands.get(self.StandardButton.Cancel)
            if candidate is None:
                rejection = [button for button in self.buttons() if self.buttonRole(button)
                             in (self.ButtonRole.RejectRole, self.ButtonRole.NoRole)]
                if len(rejection) == 1:
                    candidate = rejection[0]
            if candidate is not None:
                super().setEscapeButton(candidate)

    def showEvent(self, event):
        self._replace_commands()
        super().showEvent(event)

    def addButton(self, *args):
        if isinstance(args[0], str):
            button = QPushButton(args[0], self)
            button.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)
            super().addButton(button, args[1])
            return button
        if isinstance(args[0], _qt.QAbstractButton):
            return super().addButton(*args)
        super().addButton(*args)
        self._replace_commands()
        return self.button(args[0])

    def button(self, standard):
        return self._fluent_commands.get(standard) or super().button(standard)

    def standardButton(self, button):
        for standard, command in self._fluent_commands.items():
            if command is button:
                return standard
        return super().standardButton(button)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape and self.escapeButton() is not None:
            self.escapeButton().click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def standardButtons(self):
        buttons = super().standardButtons()
        for standard in self._fluent_commands:
            buttons |= standard
        return buttons

    def setStandardButtons(self, buttons):
        for button in self._fluent_commands.values():
            super().removeButton(button)
            button.deleteLater()
        self._fluent_commands.clear()
        super().setStandardButtons(buttons)
        self._replace_commands()

    def setDefaultButton(self, button):
        if isinstance(button, self.StandardButton) and button in self._fluent_commands:
            button = self._fluent_commands[button]
        super().setDefaultButton(button)

    def setEscapeButton(self, button):
        if isinstance(button, self.StandardButton) and button in self._fluent_commands:
            button = self._fluent_commands[button]
        super().setEscapeButton(button)

    def removeButton(self, button):
        for standard, command in list(self._fluent_commands.items()):
            if command is button:
                del self._fluent_commands[standard]
        super().removeButton(button)

    def done(self, result):
        standard = self.standardButton(self.clickedButton())
        super().done(int(standard) if standard != self.StandardButton.NoButton else result)

    def exec(self):
        result = super().exec()
        standard = self.standardButton(self.clickedButton())
        return int(standard) if standard != self.StandardButton.NoButton else result

    @classmethod
    def _message(cls, icon, parent, title, text, buttons, default):
        box = cls(icon, title, text, buttons, parent)
        if default != cls.StandardButton.NoButton:
            box.setDefaultButton(default)
        return cls.StandardButton(box.exec())

    @classmethod
    def information(cls, parent, title, text, buttons=_qt.QMessageBox.StandardButton.Ok,
                    defaultButton=_qt.QMessageBox.StandardButton.NoButton):
        return cls._message(cls.Icon.Information, parent, title, text, buttons, defaultButton)

    @classmethod
    def warning(cls, parent, title, text, buttons=_qt.QMessageBox.StandardButton.Ok,
                defaultButton=_qt.QMessageBox.StandardButton.NoButton):
        return cls._message(cls.Icon.Warning, parent, title, text, buttons, defaultButton)

    @classmethod
    def critical(cls, parent, title, text, buttons=_qt.QMessageBox.StandardButton.Ok,
                 defaultButton=_qt.QMessageBox.StandardButton.NoButton):
        return cls._message(cls.Icon.Critical, parent, title, text, buttons, defaultButton)

    @classmethod
    def question(cls, parent, title, text,
                 buttons=_qt.QMessageBox.StandardButton.Yes | _qt.QMessageBox.StandardButton.No,
                 defaultButton=_qt.QMessageBox.StandardButton.NoButton):
        return cls._message(cls.Icon.Question, parent, title, text, buttons, defaultButton)


QMessageBox = FluentMessageBox


class FluentColorDialog:
    """Expose the colour-selection contract using the native Fluent ColorPicker."""
    ColorDialogOption = _qt.QColorDialog.ColorDialogOption

    @staticmethod
    def getColor(initial=None, parent=None, title='', options=_qt.QColorDialog.ColorDialogOption(0)):
        from PySide6 import QtGui
        dialog = fluentqt.Dialog(parent)
        dialog.setWindowTitle(title or 'Choose a colour')
        picker = fluentqt.ColorPicker(dialog)
        if initial is not None:
            picker.setColor(initial)
        picker.setAlphaEnabled(bool(options & QColorDialog.ColorDialogOption.ShowAlphaChannel))
        layout = _qt.QVBoxLayout(dialog)
        layout.addWidget(picker)
        # Import at invocation after the shared construction namespace is ready.
        from openlp.core.widgets.fluent import QDialogButtonBox
        buttons = QDialogButtonBox(_qt.QDialogButtonBox.StandardButton.Ok
                                   | _qt.QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == _qt.QDialog.DialogCode.Accepted:
            return picker.color()
        return QtGui.QColor()


QColorDialog = FluentColorDialog
