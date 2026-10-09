"""Native Fluent navigation and feedback controls with Qt modal lifecycle."""
from PySide6 import QtCore, QtWidgets as _qt
import fluentqt
from fluentqt.design import Spacing
from openlp.core.widgets.fluent_buttons import QPushButton
from openlp.core.widgets.fluent_text import display_text


class _DialogSizingMixin:
    """Native Fluent dialog accepting the legacy parent/window-flags signature."""
    def __init__(self, parent=None, flags=QtCore.Qt.WindowType(0)):
        # Native Dialog owns its same-window presentation. Legacy title-bar
        # flags must not turn an embedded dialog back into a separate Qt window.
        # Fluent resolves and retains the overlay window at construction time.
        # Draft editors can be hidden while their controls live in another window.
        ancestor = parent
        while ancestor is not None:
            host = getattr(ancestor, '_fluent_dialog_host', None)
            if isinstance(host, _qt.QWidget):
                parent = host
                break
            ancestor = ancestor.parentWidget()
        super().__init__(parent)
        # Qt's opacity-effect capture conflicts with accelerated WebEngine views
        # on macOS, leaving dialog children blank until a later repaint. Keep the
        # native effect alive (FluentQt owns it), but paint the contents directly.
        self.graphicsEffect().setEnabled(False)
        self.setSmokeEnabled(True)
        self.setAnimationEnabled(True)
        if isinstance(self, fluentqt.ContentDialog):
            self.setMaximumWidth(560)
        self._preferred_minimum = QtCore.QSize()
        if self.parentWidget() is not None:
            self.parentWidget().installEventFilter(self)
        # Embedded widgets are automatically shown with their parent unless
        # explicitly hidden. Dialogs must wait for show(), open() or exec().
        self.hide()

    def _prepare_size(self):
        """Measure content including Fluent's shadow and generous inner padding."""
        layout = self.layout()
        if layout is None:
            return
        if not isinstance(self, fluentqt.ContentDialog):
            padding = Spacing.Padding.Dialog
            margins = layout.contentsMargins()
            layout.setContentsMargins(max(padding, margins.left()), max(padding, margins.top()),
                                      max(padding, margins.right()), max(padding, margins.bottom()))
            layout.setSpacing(max(Spacing.Medium, layout.spacing()))
        # Fluent inputs need their full control height even in compact forms.
        for control_type in (fluentqt.LineEdit, fluentqt.ComboBox, _qt.QAbstractSpinBox):
            for control in self.findChildren(control_type):
                control.setMinimumHeight(max(32, control.minimumHeight()))
        for form in self.findChildren(_qt.QFormLayout):
            form.setHorizontalSpacing(max(Spacing.Medium, form.horizontalSpacing()))
            form.setVerticalSpacing(max(Spacing.Medium, form.verticalSpacing()))
        self.ensurePolished()
        layout.invalidate()
        layout.activate()
        self._preferred_minimum = self._preferred_minimum.expandedTo(self.minimumSize())
        preferred = self.sizeHint().expandedTo(self.minimumSizeHint()).expandedTo(self._preferred_minimum)
        width = max(420, self.width(), preferred.width())
        parent = self.parentWidget()
        available = parent.size() if parent is not None else self.screen().availableGeometry().size()
        width = min(width, available.width(), self.maximumWidth())
        height = max(self.height(), preferred.height(), layout.totalHeightForWidth(width))
        height = min(height, available.height(), self.maximumHeight())
        self.setMinimumSize(self._preferred_minimum.boundedTo(available))
        self.resize(width, height)
        layout.activate()

    def _constrain_position(self):
        parent = self.parentWidget()
        if parent is not None:
            self.move(max(0, min(self.x(), parent.width() - self.width())),
                      max(0, min(self.y(), parent.height() - self.height())))

    def open(self):
        self._prepare_size()
        super().open()

    def exec(self):
        self._prepare_size()
        return super().exec()

    def showEvent(self, event):
        self._prepare_size()
        super().showEvent(event)
        self._prepare_size()
        self._constrain_position()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._constrain_position()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QtCore.QEvent.Type.Resize and self.isVisible():
            self._prepare_size()
            self._constrain_position()
        return super().eventFilter(watched, event)


class FluentDialog(_DialogSizingMixin, fluentqt.Dialog):
    """Fluent form dialog with content sizing and bounded dragging."""

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, '_heading'):
            self._heading.setText(title)
            self._heading.setVisible(bool(title))

    def _prepare_size(self):
        layout = self.layout()
        if layout is not None and not hasattr(self, '_heading'):
            self._heading = fluentqt.Label(self.windowTitle(), self)
            self._heading.setFluentTypography(fluentqt.FontRole.Subtitle)
            self._heading.setWordWrap(True)
            if isinstance(layout, _qt.QHBoxLayout):
                content = _qt.QWidget(self)
                content.setLayout(layout)
                layout.setContentsMargins(0, 0, 0, 0)
                layout = _qt.QVBoxLayout(self)
                layout.addWidget(self._heading)
                layout.addWidget(content)
            elif isinstance(layout, _qt.QBoxLayout):
                layout.insertWidget(0, self._heading)
            elif isinstance(layout, _qt.QFormLayout):
                layout.insertRow(0, self._heading)
            elif isinstance(layout, _qt.QGridLayout):
                positions = [layout.getItemPosition(index) for index in range(layout.count())]
                items = [layout.takeAt(0) for _ in positions]
                for item, (row, column, rows, columns) in zip(items, positions):
                    layout.addItem(item, row + 1, column, rows, columns)
                layout.addWidget(self._heading, 0, 0, 1, layout.columnCount())
        if hasattr(self, '_heading'):
            self._heading.setVisible(bool(self.windowTitle()))
        super()._prepare_size()


class _ContentScrollArea(_qt.QScrollArea):
    """Use the content's natural height until the dialog needs a scrollbar."""
    def sizeHint(self):
        return self.widget().sizeHint() if self.widget() is not None else QtCore.QSize()

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)

    def hasHeightForWidth(self):
        return self.widget() is not None and self.widget().hasHeightForWidth()

    def heightForWidth(self, width):
        return self.widget().heightForWidth(width) if self.hasHeightForWidth() else self.sizeHint().height()


class FluentContentDialog(_DialogSizingMixin, fluentqt.ContentDialog):
    """ContentDialog with shared presentation and scrollable, window-bounded content."""
    def __init__(self, parent=None, flags=QtCore.Qt.WindowType(0)):
        super().__init__(parent, flags)
        self.setDragEnabled(False)
        self.setMinimumWidth(420)
        self.layout().setSizeConstraint(_qt.QLayout.SizeConstraint.SetNoConstraint)
        self._content_scroll = _ContentScrollArea(self)
        self._content_scroll.setFrameShape(_qt.QFrame.Shape.NoFrame)
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setMinimumSize(0, 0)
        self._content_scroll.viewport().setAutoFillBackground(False)
        fluentqt.ContentDialog.setContent(self, self._content_scroll)
        self._native_commands = {}
        for slot, setter in (('primary', self.setPrimaryButtonText),
                             ('secondary', self.setSecondaryButtonText), ('close', self.setCloseButtonText)):
            setter(slot)
            self._native_commands[slot] = next(button for button in self.findChildren(fluentqt.Button)
                                               if button.text() == slot)
            setter('')

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        self.setTitle(title)

    def setContent(self, content):
        self._validate_content(content, self)
        current = self.content()
        if current is content:
            return
        if current is not None:
            self._content_scroll.takeWidget()
        if isinstance(content, fluentqt.Label):
            content.setFluentTypography(fluentqt.FontRole.Body)
        self._content_scroll.setWidget(content)
        if content is not None:
            content.setAutoFillBackground(False)

    def takeContent(self):
        return self._content_scroll.takeWidget()

    def content(self):
        return self._content_scroll.widget()

    def _prepare_size(self):
        buttons = [button for button in self._native_commands.values() if button.text()]
        if buttons:
            margins = self.layout().contentsMargins()
            # Native footer buttons share equal widths, including the longest caption.
            width = max(button.sizeHint().width() for button in buttons) * len(buttons)
            width += Spacing.Small * (len(buttons) - 1) + 2 * Spacing.Padding.Dialog
            width += margins.left() + margins.right() + 2 * self.shadowSize()
            self.resize(max(self.width(), width), self.height())
        super()._prepare_size()

    def _click_default_command(self):
        slot = {fluentqt.ContentDialogButton.Primary: 'primary',
                fluentqt.ContentDialogButton.Secondary: 'secondary',
                fluentqt.ContentDialogButton.Close: 'close'}.get(fluentqt.ContentDialog.defaultButton(self))
        button = self._native_commands.get(slot)
        if self.isOpen() and button is not None and button.isVisible():
            button.click()
            return True
        return False

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter) and self._click_default_command():
            event.accept()
            return
        super().keyPressEvent(event)


ContentDialog = FluentContentDialog


class FluentFormDialog(FluentContentDialog):
    """ContentDialog retaining existing form validation and Qt button-box results."""
    def __init__(self, parent=None, flags=QtCore.Qt.WindowType(0)):
        super().__init__(parent, flags)
        self.content_widget = _qt.QWidget()
        self.setContent(self.content_widget)
        self._button_box = None
        self._content_commands = {}
        self.setDefaultButton(fluentqt.ContentDialogButton.Primary)
        for slot, button in self._native_commands.items():
            button.clicked.disconnect()
            button.clicked.connect(lambda checked=False, slot=slot: self._click_command(slot))

    def setButtonBox(self, button_box):
        self._button_box = button_box

    def _click_command(self, slot):
        button = self._content_commands.get(slot)
        if button is not None:
            if button.isEnabled():
                button.click()
        elif slot == 'close':
            self.reject()

    def _sync_buttons(self):
        if self._button_box is None:
            return
        roles = _qt.QDialogButtonBox.ButtonRole
        self._content_commands.clear()
        buttons = sorted(self._button_box.buttons(),
                         key=lambda button: self._button_box.buttonRole(button) != roles.AcceptRole)
        for button in buttons:
            role = self._button_box.buttonRole(button)
            slot = None
            if role in (roles.AcceptRole, roles.YesRole, roles.ApplyRole):
                slot = 'primary' if 'primary' not in self._content_commands else 'secondary'
            elif role in (roles.RejectRole, roles.NoRole):
                slot = 'close'
            elif role in (roles.DestructiveRole, roles.HelpRole):
                slot = 'secondary'
            if slot is not None and slot not in self._content_commands:
                self._content_commands[slot] = button
                button.hide()
                button.installEventFilter(self)
            else:
                button.show()
        from openlp.core.common.i18n import UiStrings
        for slot, setter in (('primary', self.setPrimaryButtonText),
                             ('secondary', self.setSecondaryButtonText), ('close', self.setCloseButtonText)):
            command = self._content_commands.get(slot)
            setter(command.text() if command is not None else UiStrings().Cancel if slot == 'close' else '')
            self._native_commands[slot].setEnabled(command is None or command.isEnabled())
        self._button_box.setVisible(any(button not in self._content_commands.values()
                                        for button in self._button_box.buttons()))

    def _prepare_size(self):
        self._sync_buttons()
        layout = self.content_widget.layout()
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(Spacing.Medium)
        super()._prepare_size()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Type.EnabledChange:
            for slot, button in self._content_commands.items():
                if watched is button:
                    self._native_commands[slot].setEnabled(button.isEnabled())
        return super().eventFilter(watched, event)


FormDialog = FluentFormDialog


class TextEditorDialog(FluentDialog):
    """Resizable text editor with content sizing bounded by the parent window."""

    def _prepare_size(self):
        """Fit the text and controls inside the host window with room around the dialog."""
        parent = self.parentWidget()
        available = parent.size() if parent is not None else self.screen().availableGeometry().size()
        available -= QtCore.QSize(48, 48)
        available = available.expandedTo(QtCore.QSize(1, 1))
        self.setMaximumSize(available)
        editor = self._text_editor
        block = editor.document().begin()
        text_height = 2 * editor.document().documentMargin()
        while block.isValid():
            text_height += max(editor.fontMetrics().lineSpacing(), editor.blockBoundingRect(block).height())
            block = block.next()
        editor_height = text_height + editor.viewportMargins().top() + 2 * editor.frameWidth()
        controls_height = self.layout().sizeHint().height() - editor.sizeHint().height()
        target_height = max(self.height(), round(editor_height + controls_height))
        self.resize(min(self.width(), available.width()), min(target_height, available.height()))
        super()._prepare_size()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._constrain_position()

    def _constrain_position(self):
        """Keep padding above and below the embedded, resizable editor."""
        super()._constrain_position()
        parent = self.parentWidget()
        if parent is not None:
            self.move(max(24, min(self.x(), parent.width() - self.width() - 24)),
                      max(24, min(self.y(), parent.height() - self.height() - 24)))


QDialog = FluentDialog


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
    """Full-width row containing a Fluent progress rail and optional trailing label."""
    valueChanged = QtCore.Signal(int)

    def __init__(self, parent=None, *, compact=False):
        super().__init__(parent)
        self.setSizePolicy(_qt.QSizePolicy.Policy.Expanding, _qt.QSizePolicy.Policy.Fixed)
        self._bar = _ProgressRail(self)
        self._label = fluentqt.Label(self)
        if compact:
            self._bar.setFixedHeight(Spacing.ControlHeight.Small)
            self._label.setFluentTypography(fluentqt.FontRole.Caption)
        self._format = '%p%'
        self._text_visible = True
        self._minimum, self._maximum = 0, 100
        self._bar.setRange(0, 100)
        layout = _qt.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._bar, stretch=1)
        layout.addWidget(self._label, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
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
        self._tab_labels = []
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
        self._tab_labels.append(label)
        self._tabs.addTab(display_text(label))
        self._refresh_rail()
        return index

    def removeTab(self, index):
        page = self.widget(index)
        if page is not None:
            self._pages.removeWidget(page)
            self._tab_labels.pop(index)
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
        self._tab_labels[index] = text
        self._tabs.setTabText(index, display_text(text))
        if index < len(self._rail_buttons):
            self._rail_buttons[index].setText(text)

    def tabText(self, index):
        return self._tab_labels[index]

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


class FluentProgressDialog(FluentDialog):
    """Native Fluent dialog with progress and cancellation contracts."""
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
        self._label.setWordWrap(True)
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


class _MessageBoxCommands(_qt.QMessageBox):
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
            if candidate is None and len(self.buttons()) == 1:
                candidate = self.buttons()[0]
            if candidate is None:
                for role in (self.ButtonRole.RejectRole, self.ButtonRole.NoRole):
                    rejection = [button for button in self.buttons() if self.buttonRole(button) == role]
                    if len(rejection) == 1:
                        candidate = rejection[0]
                        break
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


class FluentMessageBox(FluentContentDialog):
    """Iconless ContentDialog retaining Qt message button/result contracts."""
    Icon = _qt.QMessageBox.Icon
    StandardButton = _qt.QMessageBox.StandardButton
    StandardButtons = _qt.QMessageBox.StandardButtons
    Ok = StandardButton.Ok
    ButtonRole = _qt.QMessageBox.ButtonRole
    buttonClicked = QtCore.Signal(_qt.QAbstractButton)

    def __init__(self, *args, **kwargs):
        self._commands = _MessageBoxCommands(*args, **kwargs)
        super().__init__(self._commands.parentWidget())
        self._commands.setParent(self)
        self._commands.hide()
        # QMessageBox suppresses window titles on macOS; Fluent displays them
        # inside the dialog, so retain the explicitly supplied title.
        title = kwargs.get('title', args[1] if len(args) > 1 else self._commands.windowTitle())
        self.setWindowTitle(title)
        self._commands.finished.connect(self.done)
        self._commands.buttonClicked.connect(self.buttonClicked.emit)
        content = _qt.QWidget()
        layout = _qt.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.Medium)
        self._text = fluentqt.Label(content)
        self._info = fluentqt.Label(content)
        self._details = fluentqt.Label(content)
        for label in (self._text, self._info, self._details):
            label.setWordWrap(True)
            layout.addWidget(label)
        self._buttons = _qt.QHBoxLayout()
        self._buttons.addStretch()
        layout.addLayout(self._buttons)
        self.setContent(content)
        self._content_commands = {}
        # Bind the native button bar directly to the Qt command model. Native
        # ContentDialog handlers otherwise finish again with their 0/1/2 results.
        for slot, button in self._native_commands.items():
            button.clicked.disconnect()
            button.clicked.connect(lambda checked=False, slot=slot: self._click_command(slot))

    def _click_command(self, slot):
        button = self._content_commands.get(slot)
        if button is not None and button.isEnabled():
            button.click()

    def defaultButton(self):
        return self._commands.defaultButton()

    def setDefaultButton(self, button):
        self._commands.setDefaultButton(button)

    def __getattr__(self, name):
        commands = self.__dict__.get('_commands')
        if commands is not None:
            return getattr(commands, name)
        raise AttributeError(name)

    def _sync_content(self):
        self._commands._replace_commands()
        self.setTitle(self.windowTitle())
        self._text.setTextFormat(self._commands.textFormat())
        for label, text in ((self._text, self.text()),
                            (self._info, self.informativeText()), (self._details, self.detailedText())):
            label.setText(text)
            label.setVisible(bool(text))
        while self._buttons.count() > 1:
            self._buttons.takeAt(1)
        buttons = self.buttons()
        if self.defaultButton() is None and buttons:
            self.setDefaultButton(buttons[0])
        self._content_commands.clear()
        if len(buttons) <= 3:
            remaining = list(buttons)
            escape = self.escapeButton()
            if escape in remaining and (len(buttons) > 1 or
                                        self.buttonRole(escape) == self.ButtonRole.RejectRole):
                self._content_commands['close'] = escape
                remaining.remove(escape)
            remaining.sort(key=lambda button: self.buttonRole(button) not in (
                self.ButtonRole.AcceptRole, self.ButtonRole.YesRole, self.ButtonRole.ApplyRole))
            for slot, button in zip(('primary', 'secondary', 'close'), remaining):
                self._content_commands[slot] = button
            for button in buttons:
                button.hide()
        else:
            # Messages with more actions keep their full command row.
            for button in buttons:
                self._buttons.addWidget(button)
                button.show()
        self.setPrimaryButtonText(self._content_commands['primary'].text()
                                  if 'primary' in self._content_commands else '')
        self.setSecondaryButtonText(self._content_commands['secondary'].text()
                                    if 'secondary' in self._content_commands else '')
        self.setCloseButtonText(self._content_commands['close'].text()
                                if 'close' in self._content_commands else '')
        for slot, button in self._native_commands.items():
            command = self._content_commands.get(slot)
            button.setEnabled(command.isEnabled() if command is not None else True)
        for slot, native in (('primary', fluentqt.ContentDialogButton.Primary),
                             ('secondary', fluentqt.ContentDialogButton.Secondary),
                             ('close', fluentqt.ContentDialogButton.Close)):
            if self._content_commands.get(slot) is self.defaultButton():
                fluentqt.ContentDialog.setDefaultButton(self, native)
                break

    def showEvent(self, event):
        self._sync_content()
        self.adjustSize()
        super().showEvent(event)

    def exec(self):
        self._sync_content()
        super().exec()
        return self._commands.result()

    def keyPressEvent(self, event):
        button = None
        if event.key() == QtCore.Qt.Key.Key_Escape:
            button = self.escapeButton()
            if button is None:
                event.accept()
                return
        elif event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            button = self.defaultButton()
        if button is not None:
            if button.isEnabled():
                button.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def reject(self):
        button = self.escapeButton()
        if button is not None and button.isEnabled():
            button.click()

    _message = classmethod(_MessageBoxCommands._message.__func__)
    information = classmethod(_MessageBoxCommands.information.__func__)
    warning = classmethod(_MessageBoxCommands.warning.__func__)
    critical = classmethod(_MessageBoxCommands.critical.__func__)
    question = classmethod(_MessageBoxCommands.question.__func__)


QMessageBox = FluentMessageBox


class FluentColorDialog:
    """Expose the colour-selection contract using the native Fluent ColorPicker."""
    ColorDialogOption = _qt.QColorDialog.ColorDialogOption

    @staticmethod
    def getColor(initial=None, parent=None, title='', options=_qt.QColorDialog.ColorDialogOption(0)):
        from PySide6 import QtGui
        from openlp.core.common.i18n import translate, UiStrings
        dialog = FluentContentDialog(parent)
        dialog.setTitle(title or translate('OpenLP.ColorDialog', 'Choose a colour'))
        picker = fluentqt.ColorPicker(dialog)
        if initial is not None:
            picker.setColor(initial)
        picker.setAlphaEnabled(bool(options & QColorDialog.ColorDialogOption.ShowAlphaChannel))
        dialog.setContent(picker)
        dialog.setPrimaryButtonText(translate('OpenLP.Ui', 'Save'))
        dialog.setCloseButtonText(UiStrings().Cancel)
        dialog.setDefaultButton(fluentqt.ContentDialogButton.Primary)
        accepted = dialog.exec() == dialog.ResultPrimary
        colour = picker.color() if accepted else QtGui.QColor()
        dialog.deleteLater()
        return colour


QColorDialog = FluentColorDialog


class FluentInputDialog:
    """Input prompts using Fluent dialogs and native Fluent fields."""
    @staticmethod
    def _prompt(parent, title, label, field):
        from openlp.core.common.i18n import UiStrings, translate
        dialog = FluentContentDialog(parent)
        dialog.setTitle(title)
        content = _qt.QWidget()
        layout = _qt.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.Medium)
        prompt = fluentqt.Label(label, content)
        prompt.setWordWrap(True)
        prompt.setBuddy(field)
        field.setAccessibleName(label.rstrip(':'))
        layout.addWidget(prompt)
        layout.addWidget(field)
        dialog.setContent(content)
        dialog.setPrimaryButtonText(translate('OpenLP.Ui', 'OK'))
        dialog.setCloseButtonText(UiStrings().Cancel)
        dialog.setDefaultButton(fluentqt.ContentDialogButton.Primary)
        QtCore.QTimer.singleShot(0, field, field.setFocus)
        return dialog, dialog.exec() == dialog.ResultPrimary

    @classmethod
    def getText(cls, parent, title, label, echo=_qt.QLineEdit.EchoMode.Normal, text='',
                flags=QtCore.Qt.WindowType(0), inputMethodHints=QtCore.Qt.InputMethodHint.ImhNone):
        field = fluentqt.LineEdit()
        field.setEchoMode(echo)
        field.setText(text)
        field.setInputMethodHints(inputMethodHints)
        field.selectAll()
        dialog, accepted = cls._prompt(parent, title, label, field)
        value = field.text() if accepted else ''
        dialog.deleteLater()
        return value, accepted

    @classmethod
    def getInt(cls, parent, title, label, value=0, min=-2147483647, max=2147483647, step=1,
               flags=QtCore.Qt.WindowType(0)):
        from openlp.core.widgets.fluent_inputs import QSpinBox
        field = QSpinBox()
        field.setRange(min, max)
        field.setSingleStep(step)
        field.setValue(value)
        initial = field.value()
        dialog, accepted = cls._prompt(parent, title, label, field)
        value = field.value() if accepted else initial
        dialog.deleteLater()
        return value, accepted

    @classmethod
    def getItem(cls, parent, title, label, items, current=0, editable=True,
                flags=QtCore.Qt.WindowType(0), inputMethodHints=QtCore.Qt.InputMethodHint.ImhNone):
        field = fluentqt.ComboBox()
        field.addItems(items)
        field.setCurrentIndex(current)
        field.setEditable(editable)
        field.setInputMethodHints(inputMethodHints)
        dialog, accepted = cls._prompt(parent, title, label, field)
        value = field.currentText() if accepted else ''
        dialog.deleteLater()
        return value, accepted


QInputDialog = FluentInputDialog
