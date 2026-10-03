"""Consumer row delegate for FluentQt file-library trees.

TreeView deliberately leaves row painting and disclosure hit testing to its
consumer. Follow the FluentQt Gallery's TreeRowDelegate layout, retaining the
view's public reveal and selection-indicator animation APIs.
"""
from PySide6 import QtCore, QtGui, QtWidgets
from fluentqt import FluentWidget


class FluentLibraryTreeDelegate(QtWidgets.QStyledItemDelegate):
    """Paint compact, indented file rows with Fluent disclosure controls."""

    def __init__(self, view):
        super().__init__(view)
        self._view = view
        # Public FluentWidget token access follows the parent view's theme.
        self._theme_host = FluentWidget(view)
        self._theme_host.hide()

    def sizeHint(self, option, index):
        return QtCore.QSize(0, 36)

    def _background_rect(self, option):
        top = option.rect.top() + 2
        height = option.rect.height() - 4
        if option.direction == QtCore.Qt.LayoutDirection.RightToLeft:
            return QtCore.QRectF(2, top, max(0, option.rect.right() - 3), height)
        left = option.rect.left() + 2
        return QtCore.QRectF(left, top, max(0, self._view.viewport().width() - 2 - left), height)

    @staticmethod
    def _chevron_rect(option):
        rtl = option.direction == QtCore.Qt.LayoutDirection.RightToLeft
        left = option.rect.right() - 31 if rtl else option.rect.left() + 12
        return QtCore.QRectF(left, option.rect.top() + 2, 20, option.rect.height() - 4)

    def paint(self, painter, option, index):
        colors = self._theme_host.theme_tokens().colors
        enabled = bool(option.state & QtWidgets.QStyle.StateFlag.State_Enabled)
        selected = bool(option.state & QtWidgets.QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QtWidgets.QStyle.StateFlag.State_MouseOver)
        background = self._background_rect(option)
        rtl = option.direction == QtCore.Qt.LayoutDirection.RightToLeft
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if enabled and (selected or hovered):
            pressed = hovered and bool(option.state & QtWidgets.QStyle.StateFlag.State_Sunken)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(colors.subtleTertiary if pressed else colors.subtleSecondary)
            painter.drawRoundedRect(background, 4, 4)
        text_color = colors.textPrimary if enabled else colors.textDisabled
        chevron = self._chevron_rect(option)
        if index.model().hasChildren(index):
            painter.save()
            painter.translate(chevron.center())
            painter.rotate((-1 if rtl else 1) * self._view.chevronRotation(index) * 90)
            painter.setPen(QtGui.QPen(text_color, 1.5, QtCore.Qt.PenStyle.SolidLine,
                                      QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))
            path = QtGui.QPainterPath()
            direction = -1 if rtl else 1
            path.moveTo(-2 * direction, -4)
            path.lineTo(2 * direction, 0)
            path.lineTo(-2 * direction, 4)
            painter.drawPath(path)
            painter.restore()
        icon_left = chevron.left() - 24 if rtl else chevron.right() + 4
        icon_rect = QtCore.QRectF(icon_left, background.center().y() - 10, 20, 20)
        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QtGui.QIcon):
            icon.paint(painter, icon_rect.toRect(), QtCore.Qt.AlignmentFlag.AlignCenter,
                       QtGui.QIcon.Mode.Normal if enabled else QtGui.QIcon.Mode.Disabled)
        text_left = background.left() + 8 if rtl else icon_rect.right() + 6
        text_right = icon_rect.left() - 6 if rtl else background.right() - 8
        text_rect = QtCore.QRectF(text_left, background.top(), max(0, text_right - text_left), background.height())
        painter.setFont(option.font)
        painter.setPen(text_color)
        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or '')
        text = painter.fontMetrics().elidedText(
            text, QtCore.Qt.TextElideMode.ElideLeft if rtl else QtCore.Qt.TextElideMode.ElideRight,
            int(text_rect.width()))
        alignment = QtCore.Qt.AlignmentFlag.AlignRight if rtl else QtCore.Qt.AlignmentFlag.AlignLeft
        painter.drawText(text_rect, alignment | QtCore.Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if (event.type() in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease)
                and event.button() == QtCore.Qt.MouseButton.LeftButton
                and model.hasChildren(index) and self._chevron_rect(option).contains(event.position())):
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                self._view.toggleExpanded(index)
            return True
        return super().editorEvent(event, model, option, index)
