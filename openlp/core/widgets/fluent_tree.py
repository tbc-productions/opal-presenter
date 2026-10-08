"""Consumer row delegate for FluentQt file-library trees.

TreeView deliberately leaves row painting and disclosure hit testing to its
consumer. Follow the FluentQt Gallery's TreeRowDelegate layout, retaining the
view's public reveal and selection-indicator animation APIs.
"""
from PySide6 import QtCore, QtGui, QtWidgets
from fluentqt import FluentWidget
from openlp.core.ui.fluenticons import fluent_icon

LIBRARY_FILE_TYPE_ICON_ROLE = QtCore.Qt.ItemDataRole.UserRole + 101
LIBRARY_FOLDER_ROLE = QtCore.Qt.ItemDataRole.UserRole + 103


def library_folder_icon(colors):
    """Use the active theme's Chart7 colour for library and picker folders."""
    return fluent_icon('ic_fluent_folder_24_regular', color=colors.charts[6], color_disabled=colors.textDisabled)


class FluentLibraryTreeDelegate(QtWidgets.QStyledItemDelegate):
    """Paint compact, indented file rows with Fluent disclosure controls."""

    def __init__(self, view):
        super().__init__(view)
        self._view = view
        # Public FluentWidget token access follows the parent view's theme.
        self._theme_host = FluentWidget(view)
        self._theme_host.hide()

    def sizeHint(self, option, index):
        return QtCore.QSize(0, max(36, self.iconSize(option, index).height() + 12) + self.group_spacing(index))

    def has_next_sibling(self, index):
        model = index.model()
        return any(not self._view.itemFromIndex(model.index(row, 0, index.parent())).isHidden()
                   for row in range(index.row() + 1, model.rowCount(index.parent())))

    def group_spacing(self, index):
        if index.parent().isValid() and not self.has_next_sibling(index) \
                and not (self._view.isExpanded(index) and index.model().hasChildren(index)):
            return 8
        return 0

    def iconSize(self, option, index):
        if index.data(LIBRARY_FOLDER_ROLE):
            return QtCore.QSize(34, 34)
        size = self._view.iconSize()
        return size if size.isValid() else QtCore.QSize(20, 20)

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

    def trailingIcons(self, index):
        icon = index.data(LIBRARY_FILE_TYPE_ICON_ROLE) if index.column() == 0 else None
        return [icon] if isinstance(icon, QtGui.QIcon) and not icon.isNull() else []

    def _text_layout(self, option, index):
        background = self._background_rect(option)
        rtl = option.direction == QtCore.Qt.LayoutDirection.RightToLeft
        chevron = self._chevron_rect(option)
        icon_size = self.iconSize(option, index)
        icon_left = chevron.left() - icon_size.width() - 4 if rtl else chevron.right() + 4
        left = background.left() + 8 if rtl else icon_left + icon_size.width() + 6
        right = icon_left - 6 if rtl else background.right() - 8
        icons = self.trailingIcons(index)
        extent, gap = 16, 6
        available = max(0, right - left - len(icons) * (extent + gap))
        metrics = QtGui.QFontMetrics(option.font)
        text = metrics.elidedText(str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ''),
                                 QtCore.Qt.TextElideMode.ElideLeft if rtl else QtCore.Qt.TextElideMode.ElideRight,
                                 int(available))
        width = min(available, metrics.horizontalAdvance(text))
        text_rect = QtCore.QRectF(right - available if rtl else left, background.top(),
                                 available, background.height())
        edge = right - width if rtl else left + width
        rectangles = []
        for icon in icons:
            x = edge - gap - extent if rtl else edge + gap
            rectangles.append(QtCore.QRectF(x, background.center().y() - extent / 2, extent, extent))
            edge = x if rtl else x + extent
        return text, text_rect, icons, rectangles

    def trailingIconRects(self, option, index):
        option = QtWidgets.QStyleOptionViewItem(option)
        option.rect.adjust(0, 0, 0, -self.group_spacing(index))
        return self._text_layout(option, index)[3]

    def paint(self, painter, option, index):
        option = QtWidgets.QStyleOptionViewItem(option)
        option.rect.adjust(0, 0, 0, -self.group_spacing(index))
        colors = self._theme_host.theme_tokens().colors
        enabled = bool(option.state & QtWidgets.QStyle.StateFlag.State_Enabled)
        selected = bool(option.state & QtWidgets.QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QtWidgets.QStyle.StateFlag.State_MouseOver)
        background = self._background_rect(option)
        rtl = option.direction == QtCore.Qt.LayoutDirection.RightToLeft
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if index.data(LIBRARY_FOLDER_ROLE):
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(colors.subtleSecondary)
            painter.drawRoundedRect(background, 4, 4)
            font = QtGui.QFont(option.font)
            font.setWeight(QtGui.QFont.Weight.DemiBold)
            option.font = font
        if enabled and (selected or hovered):
            pressed = hovered and bool(option.state & QtWidgets.QStyle.StateFlag.State_Sunken)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(colors.subtleTertiary if pressed else colors.subtleSecondary)
            painter.drawRoundedRect(background, 4, 4)
        text_color = colors.textPrimary if enabled else colors.textDisabled
        foreground = index.data(QtCore.Qt.ItemDataRole.ForegroundRole)
        if enabled and isinstance(foreground, QtGui.QBrush) and foreground.style() != QtCore.Qt.BrushStyle.NoBrush:
            text_color = foreground.color()
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
        icon_size = self.iconSize(option, index)
        icon_left = chevron.left() - icon_size.width() - 4 if rtl else chevron.right() + 4
        icon_rect = QtCore.QRectF(icon_left, background.center().y() - icon_size.height() / 2,
                                  icon_size.width(), icon_size.height())
        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        if index.data(LIBRARY_FOLDER_ROLE):
            icon = library_folder_icon(colors)
        if isinstance(icon, QtGui.QIcon):
            pixmap = icon.pixmap(icon_size, QtGui.QIcon.Mode.Normal if enabled else QtGui.QIcon.Mode.Disabled)
            pixmap = pixmap.scaled(icon_size * pixmap.devicePixelRatio(), QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                   QtCore.Qt.TransformationMode.SmoothTransformation)
            target = QtCore.QRectF(QtCore.QPointF(), pixmap.deviceIndependentSize())
            target.moveCenter(icon_rect.center())
            painter.drawPixmap(target, pixmap, QtCore.QRectF(pixmap.rect()))
            if not selected and not index.data(LIBRARY_FOLDER_ROLE):
                painter.setPen(QtGui.QPen(colors.strokeCard, 1))
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(target.adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)
        text, text_rect, trailing_icons, trailing_rects = self._text_layout(option, index)
        painter.setFont(option.font)
        painter.setPen(text_color)
        alignment = QtCore.Qt.AlignmentFlag.AlignRight if rtl else QtCore.Qt.AlignmentFlag.AlignLeft
        painter.drawText(text_rect, alignment | QtCore.Qt.AlignmentFlag.AlignVCenter, text)
        if isinstance(index.data(LIBRARY_FILE_TYPE_ICON_ROLE), QtGui.QIcon):
            painter.setOpacity(painter.opacity() * 0.65)
        for icon, rect in zip(trailing_icons, trailing_rects):
            icon.paint(painter, rect.toRect(), QtCore.Qt.AlignmentFlag.AlignCenter,
                       QtGui.QIcon.Mode.Normal if enabled else QtGui.QIcon.Mode.Disabled)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if (event.type() in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease)
                and event.button() == QtCore.Qt.MouseButton.LeftButton
                and model.hasChildren(index) and self._chevron_rect(option).contains(event.position())):
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                self._view.toggleExpanded(index)
            return True
        return super().editorEvent(event, model, option, index)
