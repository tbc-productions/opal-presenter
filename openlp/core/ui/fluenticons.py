"""Render FluentQt's bundled Fluent System Icons as scalable Qt action icons."""
import json
from functools import lru_cache

import fluentqt  # noqa: F401 - Registers the bundled icon resources.
from PySide6 import QtCore, QtGui, QtWidgets


@lru_cache(maxsize=1)
def _icon_font():
    resource = QtCore.QFile(':/res/icons/FluentQtIcons.json')
    if not resource.open(QtCore.QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError('Fluent icon catalogue is unavailable')
    glyphs = json.loads(bytes(resource.readAll()))
    font_id = QtGui.QFontDatabase.addApplicationFont(':/res/icons/FluentQtIcons.ttf')
    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise RuntimeError('Fluent icon font is unavailable')
    return families[0], glyphs


class FluentIconEngine(QtGui.QIconEngine):
    """Draw at the requested size, honouring disabled and selected colours."""
    def __init__(self, name, colors):
        super().__init__()
        self.name = name
        self.colors = colors
        self.family, glyphs = _icon_font()
        self.glyph = chr(glyphs[name])

    def clone(self):
        return FluentIconEngine(self.name, dict(self.colors))

    def paint(self, painter, rect, mode, state):
        palette = QtWidgets.QApplication.palette()
        group = (QtGui.QPalette.ColorGroup.Disabled if mode == QtGui.QIcon.Mode.Disabled
                 else QtGui.QPalette.ColorGroup.Active)
        role = (QtGui.QPalette.ColorRole.HighlightedText if mode == QtGui.QIcon.Mode.Selected
                else QtGui.QPalette.ColorRole.WindowText)
        mode_name = {QtGui.QIcon.Mode.Normal: '', QtGui.QIcon.Mode.Disabled: '_disabled',
                     QtGui.QIcon.Mode.Active: '_active', QtGui.QIcon.Mode.Selected: '_selected'}[mode]
        state_name = '_on' if state == QtGui.QIcon.State.On else '_off'
        color = self.colors.get('color' + state_name + mode_name,
                                self.colors.get('color' + mode_name,
                                                self.colors.get('color' + state_name,
                                                                self.colors.get('color'))))
        if mode == QtGui.QIcon.Mode.Disabled and 'color_disabled' not in self.colors:
            color = None
        painter.save()
        painter.setPen(QtGui.QColor(color) if color is not None else palette.color(group, role))
        font = QtGui.QFont(self.family)
        font.setPixelSize(max(1, min(rect.width(), rect.height())))
        painter.setFont(font)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.glyph)
        painter.restore()

    def pixmap(self, size, mode, state):
        pixmap = QtGui.QPixmap(size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


def fluent_icon(name, **colors):
    """Build a QIcon using an Android-style Fluent System Icon name."""
    return QtGui.QIcon(FluentIconEngine(name, colors))
