"""Main-window footer with status text that shares space with progress controls."""
from PySide6 import QtCore, QtWidgets
from fluentqt import FontRole, Label
from fluentqt.design import Spacing


class FooterStatusBar(QtWidgets.QStatusBar):
    """Lay out messages as a widget instead of Qt's separately painted status text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(Spacing.Large, 0, Spacing.Large, 0)
        self.setSizeGripEnabled(False)
        self.content = QtWidgets.QWidget(self)
        row = QtWidgets.QHBoxLayout(self.content)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.Medium)
        self.left_content = QtWidgets.QWidget(self.content)
        self._left_layout = QtWidgets.QHBoxLayout(self.left_content)
        self._left_layout.setContentsMargins(0, 0, 0, 0)
        self._left_layout.setSpacing(Spacing.Medium)
        self.right_content = QtWidgets.QWidget(self.content)
        self.right_content.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)
        self._right_layout = QtWidgets.QHBoxLayout(self.right_content)
        self._right_layout.setContentsMargins(0, 0, 0, 0)
        self._right_layout.setSpacing(Spacing.Medium)
        row.addWidget(self.left_content, 1)
        row.addWidget(self.right_content)
        super().addPermanentWidget(self.content, 1)
        self.message_label = Label(self.left_content)
        self.message_label.setFluentTypography(FontRole.Caption)
        self.message_label.setObjectName('footer_status_message')
        self.message_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.message_label.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.message_label.setMinimumWidth(0)
        self.message_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.message_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._left_layout.addWidget(self.message_label)
        self._left_layout.addSpacerItem(QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum))
        self.message_label.hide()
        self._message_timer = QtCore.QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self.clearMessage)
        if parent is not None:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        # QMainWindow handles status tips through C++ QStatusBar.showMessage,
        # bypassing the Python override and its padded message label.
        if watched is self.parentWidget() and event.type() == QtCore.QEvent.Type.StatusTip:
            self.showMessage(event.tip())
            return True
        return super().eventFilter(watched, event)

    def add_left_widget(self, widget, stretch=0):
        """Add a control after the status message and before the flexible empty space."""
        self._left_layout.insertWidget(self._left_layout.count() - 1, widget, stretch)

    def add_right_widget(self, widget, *, before=False):
        """Keep permanent controls anchored at the right, independent of progress visibility."""
        self._right_layout.insertWidget(0 if before else self._right_layout.count(), widget)

    def showMessage(self, message, timeout=0):
        self._message_timer.stop()
        previous = self.currentMessage()
        self.message_label.setText(message)
        self.message_label.setToolTip(message)
        self._size_message()
        self.message_label.setVisible(bool(message))
        if message and timeout > 0:
            self._message_timer.start(timeout)
        if previous != message:
            self.messageChanged.emit(message)

    def clearMessage(self):
        self.showMessage('')

    def currentMessage(self):
        return self.message_label.text()

    def _size_message(self):
        # Reserve room for progress while giving ordinary messages their full text width.
        text_width = self.message_label.fontMetrics().horizontalAdvance(self.currentMessage()) + 4
        self.message_label.setFixedWidth(min(text_width, max(0, self.contentsRect().width() // 3)))

    def resizeEvent(self, event):
        self._size_message()
        super().resizeEvent(event)
