"""CommandBar-backed toolbar composition with adjacent Fluent input controls."""
from PySide6 import QtCore, QtGui, QtWidgets
import fluentqt


class FluentCommandToolbar(QtWidgets.QWidget):
    """Keep QAction semantics; CommandBar owns command layout and overflow.

    FluentQt excludes QWidgetAction from CommandBar. Inputs and SplitButton
    therefore sit alongside native command groups in this layout container.
    """
    iconSizeChanged = QtCore.Signal(QtCore.QSize)
    toolButtonStyleChanged = QtCore.Signal(object)

    def __init__(self, parent=None, *, single_command_bar=False):
        super().__init__(parent)
        self._single_command_bar = single_command_bar
        self._command_groups = []
        self._command_group = None
        self._command_actions = {}
        self._widget_actions = {}
        self._separator_widgets = {}
        self._icon_size = QtCore.QSize(20, 20)
        self._button_style = QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        self._orientation = QtCore.Qt.Orientation.Horizontal
        self._overflow_timer = QtCore.QTimer(self)
        self._overflow_timer.setSingleShot(True)
        self._overflow_timer.timeout.connect(self._raise_overflow)
        self._layout = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

    def _group(self):
        if self._command_group is None:
            self._command_group = fluentqt.CommandBar(self)
            self._command_group.setBackgroundVisible(False)
            self._command_group.setDynamicOverflowEnabled(True)
            self._command_group.overflowOpenChanged.connect(self._on_overflow_changed)
            self._command_group.setLabelPosition(self._label_position())
            self._command_group.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum,
                                              QtWidgets.QSizePolicy.Policy.Fixed)
            self._layout.insertWidget(self._layout.count() - 1, self._command_group)
            self._command_groups.append(self._command_group)
        return self._command_group

    def _on_overflow_changed(self, opened):
        if opened:
            # CommandBar creates the flyout after emitting this signal.
            self._overflow_timer.start(0)

    def _raise_overflow(self):
        # Flyouts are reparented to the host window. Give their overlay a
        # native surface so embedded WebEngine views cannot cover it.
        for popup in self.window().findChildren(QtWidgets.QWidget):
            if popup.objectName() == 'FluentCommandBar.OverflowPopup' and popup.isVisible():
                popup.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
                popup.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow)
                popup.raise_()

    def _sync_input_stretch(self):
        """Give spare width to visible expanding inputs, otherwise keep it at the end."""
        expanding = False
        for action, widget in self._widget_actions.items():
            grows = bool(widget.sizePolicy().expandingDirections() & QtCore.Qt.Orientation.Horizontal)
            self._layout.setStretch(self._layout.indexOf(widget), 1 if grows else 0)
            expanding |= grows and action.isVisible()
        self._layout.setStretch(self._layout.count() - 1, 0 if expanding else 1)

    def _label_position(self):
        return (fluentqt.CommandBar.LabelPosition.Collapsed
                if self._button_style == QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
                else fluentqt.CommandBar.LabelPosition.Right)

    def addAction(self, action, *args):
        if not isinstance(action, QtGui.QAction):
            if isinstance(action, QtGui.QIcon):
                action = QtGui.QAction(action, args[0], self)
                args = args[1:]
            else:
                action = QtGui.QAction(action, self)
            if args:
                action.triggered.connect(args[0])
        if action.isSeparator() and not self._single_command_bar:
            # A separator-only CommandBar has no command width, but can still
            # create native overflow chrome. Keep dividers outside command groups.
            self._command_group = None
            divider = QtWidgets.QFrame(self)
            divider.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            divider.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
            divider.setFixedSize(1, 24)
            self._layout.insertWidget(self._layout.count() - 1, divider)
            self._separator_widgets[action] = divider
            action.changed.connect(lambda: divider.setVisible(action.isVisible()))
            divider.setVisible(action.isVisible())
        elif isinstance(action, QtWidgets.QWidgetAction):
            widget = action.defaultWidget()
            self._command_group = None
            self._layout.insertWidget(self._layout.count() - 1, widget)
            self._widget_actions[action] = widget
            def sync():
                widget.setVisible(action.isVisible())
                widget.setEnabled(action.isEnabled())
                self._sync_input_stretch()
            action.changed.connect(sync)
            sync()
        else:
            if not action.isSeparator() and not action.text():
                action.setText(action.toolTip() or action.objectName() or 'Command')
                def caption():
                    if action.text() == 'Command' and action.toolTip():
                        action.setText(action.toolTip())
                action.changed.connect(caption)
            group = self._group()
            group.addPrimaryAction(action)
            self._command_actions[action] = group
            action.changed.connect(lambda: self._sync_group_visibility(group))
            self._sync_group_visibility(group)
        QtWidgets.QWidget.addAction(self, action)
        return action

    def _sync_group_visibility(self, group):
        """Do not leave command chrome visible when all its commands are hidden."""
        group.setVisible(any(action.isVisible() and not action.isSeparator()
                             for action, owner in self._command_actions.items()
                             if owner is group))

    def addWidget(self, widget):
        action = QtWidgets.QWidgetAction(self)
        action.setDefaultWidget(widget)
        self.addAction(action)
        return action

    def addSeparator(self):
        action = QtGui.QAction(self)
        action.setSeparator(True)
        self.addAction(action)
        return action

    def widgetForAction(self, action):
        if action in self._widget_actions:
            return self._widget_actions[action]
        if action in self._separator_widgets:
            return self._separator_widgets[action]
        group = self._command_actions.get(action)
        if group is not None:
            for widget in reversed(group.findChildren(QtWidgets.QWidget)):
                if widget.property('commandAction') is action:
                    return widget
        return None

    def removeAction(self, action):
        group = self._command_actions.pop(action, None)
        if group is not None:
            group.removeCommandAction(action)
            self._sync_group_visibility(group)
        divider = self._separator_widgets.pop(action, None)
        if divider is not None:
            self._layout.removeWidget(divider)
            divider.hide()
            divider.deleteLater()
        widget = self._widget_actions.pop(action, None)
        if widget is not None:
            self._layout.removeWidget(widget)
            widget.hide()
            self._sync_input_stretch()
        QtWidgets.QWidget.removeAction(self, action)

    def clear(self):
        for action in self.actions():
            self.removeAction(action)
        for group in self._command_groups:
            self._layout.removeWidget(group)
            group.deleteLater()
        self._command_groups.clear()
        self._command_group = None

    def setIconSize(self, size):
        self._icon_size = size
        self.iconSizeChanged.emit(size)

    def iconSize(self):
        return self._icon_size

    def setToolButtonStyle(self, style):
        self._button_style = style
        for group in self._command_groups:
            group.setLabelPosition(self._label_position())
        self.toolButtonStyleChanged.emit(style)

    def toolButtonStyle(self):
        return self._button_style

    def setOrientation(self, orientation):
        self._orientation = orientation
        self._layout.setDirection(QtWidgets.QBoxLayout.Direction.TopToBottom
                                  if orientation == QtCore.Qt.Orientation.Vertical
                                  else QtWidgets.QBoxLayout.Direction.LeftToRight)

    def orientation(self):
        return self._orientation

    def setMovable(self, movable):
        pass

    def setFloatable(self, floatable):
        pass


QToolBar = FluentCommandToolbar
