"""Interactive theme area bounds over the rendered slide preview."""
from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.i18n import translate


class ThemeAreaOverlay(QtWidgets.QWidget):
    """Edit in slide pixels, keeping handles and snap tolerance constant on screen."""
    areaSelected = QtCore.Signal(str)
    areaChanged = QtCore.Signal(str, QtCore.QRect)
    gestureFinished = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(translate('OpenLP.ThemeWizard', 'Theme text and footer areas'))
        self.canvas_size = QtCore.QSize(1920, 1080)
        self.areas = {}
        self.selected = 'main'
        self.snapping = True
        self.show_guides = False
        self._gesture = None
        self._dragged = False
        self._snap_lines = []

    def set_areas(self, size, areas):
        self.canvas_size = QtCore.QSize(size)
        self.areas = {name: QtCore.QRectF(rect) for name, rect in areas.items()}
        self.update()

    def select_area(self, area):
        if area not in ('main', 'footer'):
            return
        self.selected = area
        self.areaSelected.emit(area)
        self.update()

    def view_rect(self, rect):
        return QtCore.QRectF(rect.x() * self.width() / self.canvas_size.width(),
                             rect.y() * self.height() / self.canvas_size.height(),
                             rect.width() * self.width() / self.canvas_size.width(),
                             rect.height() * self.height() / self.canvas_size.height())

    def slide_point(self, point):
        return QtCore.QPointF(point.x() * self.canvas_size.width() / max(1, self.width()),
                              point.y() * self.canvas_size.height() / max(1, self.height()))

    def handles(self, rect):
        return {'nw': rect.topLeft(), 'n': QtCore.QPointF(rect.center().x(), rect.top()),
                'ne': rect.topRight(), 'e': QtCore.QPointF(rect.right(), rect.center().y()),
                'se': rect.bottomRight(), 's': QtCore.QPointF(rect.center().x(), rect.bottom()),
                'sw': rect.bottomLeft(), 'w': QtCore.QPointF(rect.left(), rect.center().y())}

    def hit_test(self, point):
        if self.selected in self.areas:
            for handle, centre in self.handles(self.view_rect(self.areas[self.selected])).items():
                if QtCore.QRectF(centre.x() - 6, centre.y() - 6, 12, 12).contains(point):
                    return self.selected, handle
        for area in (self.selected, 'footer' if self.selected == 'main' else 'main'):
            if area in self.areas and self.view_rect(self.areas[area]).contains(point):
                return area, 'move'
        return None, None

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        area, handle = self.hit_test(event.position())
        if area is None:
            return
        self.setFocus()
        self.select_area(area)
        self._gesture = (handle, self.slide_point(event.position()), QtCore.QRectF(self.areas[area]))
        self._dragged = False
        event.accept()

    def snap_rect(self, rect, handle, enabled=True):
        """Snap moving bounds or the active resize edge to slide/other-area anchors."""
        self._snap_lines = []
        if not enabled:
            return rect
        other = self.areas.get('footer' if self.selected == 'main' else 'main')
        for axis, length, pixels in (('x', self.canvas_size.width(), self.width()),
                                     ('y', self.canvas_size.height(), self.height())):
            targets = [0, length / 2, length]
            if other is not None:
                targets.extend((other.left(), other.center().x(), other.right()) if axis == 'x'
                               else (other.top(), other.center().y(), other.bottom()))
            if handle == 'move':
                anchors = [rect.left(), rect.center().x(), rect.right()] if axis == 'x' else \
                    [rect.top(), rect.center().y(), rect.bottom()]
            elif axis == 'x' and ('w' in handle or 'e' in handle):
                anchors = [rect.left() if 'w' in handle else rect.right()]
            elif axis == 'y' and ('n' in handle or 's' in handle):
                anchors = [rect.top() if 'n' in handle else rect.bottom()]
            else:
                continue
            delta, target = min(((target - anchor, target) for target in targets for anchor in anchors),
                                key=lambda pair: abs(pair[0]))
            if abs(delta) > 6 * length / max(1, pixels):
                continue
            candidate = QtCore.QRectF(rect)
            if handle == 'move':
                candidate.translate(delta if axis == 'x' else 0, delta if axis == 'y' else 0)
            elif axis == 'x':
                candidate.setLeft(candidate.left() + delta) if 'w' in handle else \
                    candidate.setRight(candidate.right() + delta)
            else:
                candidate.setTop(candidate.top() + delta) if 'n' in handle else \
                    candidate.setBottom(candidate.bottom() + delta)
            if (candidate.width() >= 1 and candidate.height() >= 1 and candidate.left() >= 0
                    and candidate.top() >= 0 and candidate.right() <= self.canvas_size.width()
                    and candidate.bottom() <= self.canvas_size.height()):
                rect = candidate
                self._snap_lines.append((axis, target))
        return rect

    def gesture_rect(self, point, snap=True):
        handle, start, original = self._gesture
        delta = self.slide_point(point) - start
        rect = QtCore.QRectF(original)
        width, height = self.canvas_size.width(), self.canvas_size.height()
        if handle == 'move':
            rect.moveLeft(max(0, min(width - rect.width(), rect.left() + delta.x())))
            rect.moveTop(max(0, min(height - rect.height(), rect.top() + delta.y())))
        else:
            if 'w' in handle:
                rect.setLeft(max(0, min(rect.right() - 1, rect.left() + delta.x())))
            if 'e' in handle:
                rect.setRight(min(width, max(rect.left() + 1, rect.right() + delta.x())))
            if 'n' in handle:
                rect.setTop(max(0, min(rect.bottom() - 1, rect.top() + delta.y())))
            if 's' in handle:
                rect.setBottom(min(height, max(rect.top() + 1, rect.bottom() + delta.y())))
        rect = self.snap_rect(rect, handle, snap)
        return QtCore.QRect(round(rect.x()), round(rect.y()), max(1, round(rect.width())),
                            max(1, round(rect.height())))

    def mouseMoveEvent(self, event):
        if self._gesture is None:
            _, handle = self.hit_test(event.position())
            cursors = {'move': QtCore.Qt.CursorShape.SizeAllCursor,
                       'n': QtCore.Qt.CursorShape.SizeVerCursor, 's': QtCore.Qt.CursorShape.SizeVerCursor,
                       'e': QtCore.Qt.CursorShape.SizeHorCursor, 'w': QtCore.Qt.CursorShape.SizeHorCursor,
                       'nw': QtCore.Qt.CursorShape.SizeFDiagCursor, 'se': QtCore.Qt.CursorShape.SizeFDiagCursor,
                       'ne': QtCore.Qt.CursorShape.SizeBDiagCursor, 'sw': QtCore.Qt.CursorShape.SizeBDiagCursor}
            self.setCursor(cursors.get(handle, QtCore.Qt.CursorShape.ArrowCursor))
            return
        start = self._gesture[1]
        distance = abs(event.position().x() - start.x() * self.width() / self.canvas_size.width()) + \
            abs(event.position().y() - start.y() * self.height() / self.canvas_size.height())
        if not self._dragged and distance < 2:
            return
        self._dragged = True
        rect = self.gesture_rect(event.position(), self.snapping and not (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier))
        self.areas[self.selected] = QtCore.QRectF(rect)
        self.areaChanged.emit(self.selected, rect)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._gesture is not None:
            self.mouseMoveEvent(event)
            self._gesture = None
            self._snap_lines = []
            if self._dragged:
                self.gestureFinished.emit()
            self.update()
            event.accept()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape and self._gesture is not None:
            original = self._gesture[2].toRect()
            self.areas[self.selected] = QtCore.QRectF(original)
            self.areaChanged.emit(self.selected, original)
            self._gesture = None
            self._snap_lines = []
            self.gestureFinished.emit()
            self.update()
            event.accept()
            return
        moves = {QtCore.Qt.Key.Key_Left: (-1, 0), QtCore.Qt.Key.Key_Right: (1, 0),
                 QtCore.Qt.Key.Key_Up: (0, -1), QtCore.Qt.Key.Key_Down: (0, 1)}
        if event.key() in moves and self.selected in self.areas:
            step = 10 if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier else 1
            dx, dy = moves[event.key()]
            rect = QtCore.QRectF(self.areas[self.selected])
            rect.moveLeft(max(0, min(self.canvas_size.width() - rect.width(), rect.x() + dx * step)))
            rect.moveTop(max(0, min(self.canvas_size.height() - rect.height(), rect.y() + dy * step)))
            self.areas[self.selected] = rect
            self.areaChanged.emit(self.selected, rect.toRect())
            self.gestureFinished.emit()
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        for area, rect in self.areas.items():
            bounds = self.view_rect(rect)
            colour = QtGui.QColor('#0078d4' if area == self.selected else '#999999')
            painter.setPen(QtGui.QPen(colour, 2 if area == self.selected else 1,
                                      QtCore.Qt.PenStyle.SolidLine if area == self.selected else
                                      QtCore.Qt.PenStyle.DashLine))
            painter.drawRect(bounds.adjusted(1, 1, -1, -1))
            if self.show_guides:
                caption = translate('OpenLP.ThemeWizard', 'Main text' if area == 'main' else 'Footer text')
                label = QtCore.QRectF(bounds.left() + 4, bounds.top() + 4,
                                      painter.fontMetrics().horizontalAdvance(caption) + 12, 24)
                painter.fillRect(label, QtGui.QColor('#ffffff'))
                painter.drawText(label, QtCore.Qt.AlignmentFlag.AlignCenter, caption)
            if area == self.selected:
                painter.setBrush(QtGui.QColor('#ffffff'))
                for centre in self.handles(bounds).values():
                    painter.drawRect(QtCore.QRectF(centre.x() - 4, centre.y() - 4, 8, 8))
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor('#e060b0'), 1, QtCore.Qt.PenStyle.DashLine))
        for axis, value in self._snap_lines:
            if axis == 'x':
                x = value * self.width() / self.canvas_size.width()
                painter.drawLine(QtCore.QPointF(x, 0), QtCore.QPointF(x, self.height()))
            else:
                y = value * self.height() / self.canvas_size.height()
                painter.drawLine(QtCore.QPointF(0, y), QtCore.QPointF(self.width(), y))
