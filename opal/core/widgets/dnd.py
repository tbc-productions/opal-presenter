"""In-process item transfers shared by the library and slide/service panes."""
from copy import deepcopy

import fluentqt

from PySide6 import QtCore, QtGui, QtWidgets

from opal.core.common.i18n import translate
from opal.core.lib import ServiceItemContext
from opal.core.ui.fluenticons import service_icon


class ItemDragData(QtCore.QMimeData):
    """Keep item identity independent of the selection while a native drag runs."""

    def __init__(self, *, library=None, item=None, items=None, slide_no=0, controller=None):
        super().__init__()
        self.library = library
        self.items = tuple(items) if items is not None else (() if item is None else (item,))
        self.item = self.items[0] if self.items else None
        self.controller = controller
        self.slide_no = max(0, slide_no)
        self.indexes = []
        if library is not None:
            self.indexes = [QtCore.QPersistentModelIndex(index) for index in library.list_view.selectedIndexes()
                            if index.column() == 0]
            self.title = str(self.indexes[0].data() or '') if self.indexes else ''
            self.icon = library.get_library_tab_icon()
            self.setText(library.plugin.name)
        else:
            item = self.item
            self.title = item.get_display_title()
            self.icon = service_icon(item.icon, item.name) if item.icon else None
        self.setData('application/x-openlp-item-title', self.title.encode('utf-8'))
        self.setData('application/x-openlp-item', b'1')

    def can_drop(self, destination):
        if self.library is not None:
            capability = {'service': 'can_add_to_service', 'preview': 'can_preview',
                          'live': 'can_make_live'}[destination]
            return (bool(self.indexes) and all(index.isValid() for index in self.indexes)
                    and getattr(self.library, capability, False)
                    and (destination == 'service' or self.library.single_service_item or len(self.indexes) == 1))
        return (bool(self.items) and all(item.is_valid for item in self.items)
                and (destination == 'service' or len(self.items) == 1))

    def service_items(self, context=ServiceItemContext.Service):
        if self.library is None:
            return list(self.items)
        if not all(index.isValid() for index in self.indexes):
            return []
        rows = [self.library.list_view.itemFromIndex(QtCore.QModelIndex(index)) for index in self.indexes]
        arguments = [rows] if self.library.single_service_item else rows
        items = [self.library.build_service_item(item=row, context=context) for row in arguments]
        for item in items:
            if item:
                item.from_plugin = context != ServiceItemContext.Service
        return [item for item in items if item]


class ThemeDragData(QtCore.QMimeData):
    """Retain the selected theme names when a drag changes the selection."""
    def __init__(self, manager, indexes):
        super().__init__()
        self.manager = manager
        self.indexes = [QtCore.QPersistentModelIndex(index) for index in indexes if index.column() == 0]
        self.names = tuple(index.data(QtCore.Qt.ItemDataRole.UserRole) or index.data() for index in self.indexes)
        self.title = self.names[0] if self.names else ''
        from opal.core.ui.icons import UiIcons
        self.icon = service_icon(UiIcons().theme, 'themes')
        self.setText('themes')
        self.setData('application/x-openlp-item-title', self.title.encode('utf-8'))

    def can_drop(self, item):
        return (len(self.indexes) == 1 and self.indexes[0].isValid()
                and self.indexes[0].data(QtCore.Qt.ItemDataRole.UserRole) == self.title
                and self.manager is not None and self.title in self.manager.get_theme_names()
                and supports_theme_drop(item))


def supports_theme_drop(item):
    return (item is not None and item.is_valid and item.is_text()
            and item.name in ('songs', 'custom', 'bibles'))


def copy_service_item(item):
    """A service copy needs its own slide data and identity; QIcon is implicitly shared."""
    result = deepcopy(item, {id(item.icon): item.icon})
    result._new_item()
    return result


def execute_drag(source, mime, actions=QtCore.Qt.DropAction.CopyAction):
    """Use native cursors with one compact, readable item card on every pane."""
    drag = QtGui.QDrag(source)
    drag.setMimeData(mime)
    ratio = source.devicePixelRatioF()
    pixmap = QtGui.QPixmap(QtCore.QSize(240, 56) * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    theme_host = fluentqt.FluentWidget(source)
    theme_host.hide()
    colors = theme_host.theme_tokens().colors
    painter.setBrush(colors.bgSolid)
    painter.setPen(QtGui.QPen(colors.accentDefault, 1))
    painter.drawRoundedRect(QtCore.QRectF(1, 1, 238, 54), 6, 6)
    if isinstance(mime.icon, QtGui.QIcon):
        mime.icon.paint(painter, QtCore.QRect(8, 8, 40, 40))
    painter.setFont(fluentqt.font_for_role(fluentqt.FontRole.Body))
    painter.setPen(colors.textPrimary)
    count = len(mime.indexes) or len(getattr(mime, 'items', ()))
    suffix = translate('OpenLP.DragDrop', ' (+{count})').format(count=count - 1) if count > 1 else ''
    metrics = painter.fontMetrics()
    text = metrics.elidedText(mime.title, QtCore.Qt.TextElideMode.ElideRight,
                              178 - metrics.horizontalAdvance(suffix)) + suffix
    painter.drawText(QtCore.QRect(54, 8, 178, 40), QtCore.Qt.AlignmentFlag.AlignVCenter, text)
    painter.end()
    theme_host.deleteLater()
    drag.setPixmap(pixmap)
    drag.setHotSpot(QtCore.QPoint(20, 28))
    cursor = QtGui.QPixmap(QtCore.QSize(24, 28) * ratio)
    cursor.setDevicePixelRatio(ratio)
    cursor.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(cursor)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white, 1.5))
    painter.setBrush(QtCore.Qt.GlobalColor.black)
    painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in
                                        [(3, 2), (3, 21), (8, 17), (12, 25), (16, 23), (12, 15), (19, 15)]]))
    painter.end()
    drag.setDragCursor(cursor, QtCore.Qt.DropAction.CopyAction)
    drag.setDragCursor(cursor, QtCore.Qt.DropAction.MoveAction)
    tooltip_filter = getattr(QtWidgets.QApplication.instance(), '_fluent_tooltip_filter', None)
    QtWidgets.QToolTip.hideText()
    if tooltip_filter:
        tooltip_filter.drag_active = True
        tooltip_filter.hide()
    try:
        return drag.exec(actions, QtCore.Qt.DropAction.CopyAction)
    finally:
        if tooltip_filter:
            tooltip_filter.drag_active = False
            tooltip_filter.hide()
        # Native dragging consumes the release; clear the source's pending hover and view state.
        hover_widget = source.viewport() if isinstance(source, QtWidgets.QAbstractItemView) else source
        QtWidgets.QApplication.sendEvent(hover_widget, QtCore.QEvent(QtCore.QEvent.Type.Leave))
        if isinstance(source, QtWidgets.QAbstractItemView):
            source.setState(QtWidgets.QAbstractItemView.State.NoState)
            source.stopAutoScroll()
