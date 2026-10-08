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

    def iconName(self):
        return self.name

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


@lru_cache(maxsize=1)
def _service_icon_theme():
    return fluentqt.FluentWidget()


def service_icon(icon, plugin_name):
    """Colour service, Library and Settings icons with the active Fluent palette."""
    token = {'songs': 'systemCaution', 'bibles': 'systemSuccess', 'images': 'systemInfo',
             'media': 'systemCritical', 'presentations': 'purple', 'custom': 'orange'}.get(plugin_name)
    if token is None:
        return icon
    theme = _service_icon_theme()
    colors = theme.theme_tokens().colors
    dark = fluentqt.theme_uses_dark_appearance(theme.effective_theme())
    if token == 'purple':
        color = colors.charts[11 if dark else 6]
    elif token == 'orange':
        color = colors.charts[6 if dark else 11]
    else:
        color = getattr(colors, token)
    if icon.name().startswith('ic_fluent_'):
        return fluent_icon(icon.name(), color=color, color_disabled=colors.textDisabled)
    base_pixmap = icon.pixmap(80, 80)
    if base_pixmap.isNull():
        return icon
    tinted_pixmap = QtGui.QPixmap(base_pixmap.size())
    tinted_pixmap.setDevicePixelRatio(base_pixmap.devicePixelRatio())
    tinted_pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(tinted_pixmap)
    painter.drawPixmap(0, 0, base_pixmap)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted_pixmap.rect(), color)
    painter.end()
    return QtGui.QIcon(tinted_pixmap)
