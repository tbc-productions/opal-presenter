"""Fluent presentation on existing Qt widgets, without an additional Qt runtime."""
import ctypes

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.platform import is_win


def fluent_colors(palette=None):
    palette = palette or QtWidgets.QApplication.palette()
    dark = palette.color(QtGui.QPalette.ColorRole.Window).lightness() < 128
    return {
        'window': '#202020' if dark else '#f3f3f3',
        'surface': '#272727' if dark else '#ffffff',
        'alternate': '#2c2c2c' if dark else '#f9f9f9',
        'control': '#333333' if dark else '#ffffff',
        'hover': '#3b3b3b' if dark else '#f5f5f5',
        'pressed': '#303030' if dark else '#ebebeb',
        'border': '#484848' if dark else '#d6d6d6',
        'text': '#f5f5f5' if dark else '#1a1a1a',
        'secondary': '#c5c5c5' if dark else '#5c5c5c',
        'disabled': '#929292' if dark else '#777777',
        'accent': '#60cdff' if dark else '#0067c0',
        'accent_text': '#003347' if dark else '#ffffff',
        'selection': '#304653' if dark else '#e5f1fb',
    }


def get_fluent_controls_stylesheet():
    """Scope controls to the operator window, its dialogs and ADS floating windows."""
    c = fluent_colors()
    # Existing widgets retain their models, validators, signals, shortcuts and accessibility roles.
    rules = {
        '': f'background: {c["window"]}; color: {c["text"]};',
        'QGroupBox': f'background: {c["surface"]}; border: 1px solid {c["border"]}; '
                     'border-radius: 6px; margin-top: 18px; padding: 12px 8px 8px;',
        'QGroupBox::title': 'subcontrol-origin: margin; subcontrol-position: top left; '
                            'padding: 0 4px; font-weight: 600;',
        'QPushButton': f'background: {c["control"]}; border: 1px solid {c["border"]}; '
                       'border-radius: 4px; padding: 4px 10px;',
        'QPushButton:hover': f'background: {c["hover"]};',
        'QPushButton:pressed': f'background: {c["pressed"]};',
        'QPushButton:default': f'background: {c["accent"]}; color: {c["accent_text"]}; '
                               f'border-color: {c["accent"]};',
        'QPushButton:focus': f'border: 2px solid {c["accent"]}; padding: 3px 9px;',
        'QPushButton:disabled': f'color: {c["disabled"]}; background: {c["alternate"]};',
        'QToolBar': f'background: {c["window"]}; border: none; spacing: 2px; padding: 2px;',
        'QToolButton': 'background: transparent; border: 1px solid transparent; '
                       'border-radius: 4px; padding: 2px 4px;',
        'QToolButton:hover': f'background: {c["hover"]};',
        'QToolButton:pressed': f'background: {c["pressed"]};',
        'QToolButton:checked': f'background: {c["selection"]}; border-color: {c["accent"]};',
        'QToolButton:focus': f'border-color: {c["accent"]};',
        'QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox':
            f'background: {c["control"]}; color: {c["text"]}; border: 1px solid {c["border"]}; '
            f'border-bottom: 1px solid {c["secondary"]}; border-radius: 4px; padding: 4px;',
        'QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus':
            f'border-bottom: 2px solid {c["accent"]}; padding-bottom: 3px;',
        'QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled':
            f'color: {c["disabled"]}; background: {c["alternate"]};',
        'QComboBox': 'padding-right: 22px;',
        'QComboBox::drop-down': 'border: none; width: 20px;',
        'QCheckBox, QRadioButton': 'spacing: 8px; padding: 2px;',
        'QAbstractItemView': f'background: {c["surface"]}; border: 1px solid {c["border"]}; '
                             f'border-radius: 4px; selection-background-color: {c["selection"]}; '
                             f'selection-color: {c["text"]};',
        'QTabBar::tab': 'background: transparent; border: none; margin: 2px; padding: 5px 8px;',
        'QTabBar::tab:selected': f'background: {c["selection"]}; border-radius: 4px; '
                                 f'border-bottom: 2px solid {c["accent"]}; color: {c["text"]};',
        'QTabBar::tab:hover:!selected': f'background: {c["hover"]}; border-radius: 4px;',
        'QMenuBar': 'background: transparent; padding: 2px;',
        'QMenuBar::item': 'padding: 5px 10px;',
        'QMenuBar::item:selected': f'background: {c["hover"]}; border-radius: 4px;',
    }
    result = []
    for controls, body in rules.items():
        selectors = [f'QWidget[fluentUi="true"] {control.strip()}'.strip() for control in controls.split(',')]
        result.append(', '.join(selectors) + ' { ' + body + ' }')
    result.append(f'QMenu[fluentUi="true"] {{ background: {c["surface"]}; '
                  f'color: {c["text"]}; border: 1px solid {c["border"]}; padding: 4px; }}')
    result.append('QMenu[fluentUi="true"]::item { padding: 5px 24px; border-radius: 4px; margin: 1px; }')
    result.append(f'QMenu[fluentUi="true"]::item:selected {{ background: {c["selection"]}; }}')
    result.append(f'QMenu[fluentUi="true"]::item:disabled {{ color: {c["disabled"]}; }}')
    return '\n'.join(result)


def get_fluent_dock_stylesheet():
    """Append to ADS's stylesheet so its icons and docking overlays remain available."""
    c = fluent_colors()
    return f"""
ads--CDockAreaWidget {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; }}
ads--CDockAreaTitleBar {{ background: {c['window']}; border: none; padding: 2px; }}
ads--CDockWidgetTab {{ background: transparent; border: none; margin: 2px; padding: 3px 6px; }}
ads--CDockWidgetTab[activeTab="true"] {{ background: {c['selection']}; border-radius: 4px;
    border-bottom: 2px solid {c['accent']}; }}
ads--CDockWidgetTab:hover {{ background: {c['hover']}; border-radius: 4px; }}
ads--CDockWidgetTab QLabel {{ color: {c['secondary']}; }}
ads--CDockWidgetTab[activeTab="true"] QLabel {{ color: {c['text']}; }}
ads--CDockContainerWidget ads--CDockSplitter::handle {{ background: {c['window']}; }}
ads--CAutoHideSideBar {{ background: {c['window']}; }}
ads--CAutoHideTab {{ background: {c['control']}; border: 1px solid {c['border']};
    border-radius: 4px; padding: 4px; color: {c['text']}; }}
ads--CAutoHideTab:hover {{ background: {c['selection']}; }}
"""


class FluentSurfaceFilter(QtCore.QObject):
    """Apply Modern form styling to dialogs and floated docks, including ones created later."""
    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.Type.Polish, QtCore.QEvent.Type.Show):
            if (isinstance(watched, (QtWidgets.QDialog, QtWidgets.QMenu)) or
                    watched.metaObject().className() == 'ads::CFloatingDockContainer'):
                if not watched.property('fluentUi'):
                    watched.setProperty('fluentUi', True)
                    if event.type() == QtCore.QEvent.Type.Show:
                        watched.style().unpolish(watched)
                        watched.style().polish(watched)
        return False


def configure_fluent_surfaces(app, enabled):
    """Install once at appearance startup; Classic never acquires Fluent form styling."""
    if not isinstance(app, QtWidgets.QApplication):
        return
    previous = getattr(app, '_fluent_surface_filter', None)
    if previous:
        app.removeEventFilter(previous)
        previous.deleteLater()
        app._fluent_surface_filter = None
    if enabled:
        app._fluent_surface_filter = FluentSurfaceFilter(app)
        app.installEventFilter(app._fluent_surface_filter)


def animations_enabled():
    """Respect Windows' animation preference, with an immediate fallback elsewhere."""
    if not is_win():
        return False
    try:
        enabled = ctypes.c_int()
        return bool(ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0) and enabled.value)
    except (AttributeError, OSError):
        return False


class FluentAccentButton(QtWidgets.QToolButton):
    """Compact accent command retaining QToolButton's QAction and keyboard behavior."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('fluentAccent', True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setIconSize(QtCore.QSize(18, 18))
        self._hover = 0.0
        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setDuration(90)
        self._animation.valueChanged.connect(self._set_hover)

    def _set_hover(self, value):
        self._hover = value
        self.update()

    def _animate_hover(self, target):
        self._animation.stop()
        if animations_enabled() and self.isEnabled():
            self._animation.setStartValue(self._hover)
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self._set_hover(target)

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def sizeHint(self):
        width = self.fontMetrics().horizontalAdvance(self.text()) + 24
        if not self.icon().isNull():
            width += self.iconSize().width() + 6
        return QtCore.QSize(width, max(28, self.fontMetrics().height() + 10))

    def paintEvent(self, event):
        # A transparent QSS background changes this widget's Window role to transparent black.
        # Choose the scheme from the application palette rather than that local role.
        c = fluent_colors()
        color = QtGui.QColor(c['accent'] if self.isEnabled() else c['control'])
        if self.isEnabled():
            color = color.darker(110 if self.isDown() else int(100 + 6 * self._hover))
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QColor(c['border']) if not self.isEnabled() else QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        foreground = QtGui.QColor(c['accent_text'] if self.isEnabled() else c['disabled'])
        rect = self.rect().adjusted(12, 0, -12, 0)
        if not self.icon().isNull():
            icon_rect = QtCore.QRect(rect.left(), (self.height() - self.iconSize().height()) // 2,
                                     self.iconSize().width(), self.iconSize().height())
            # Tint the existing action icon, retaining the user's familiar glyph.
            pixmap = self.icon().pixmap(self.iconSize() * self.devicePixelRatioF())
            pixmap.setDevicePixelRatio(self.devicePixelRatioF())
            icon_painter = QtGui.QPainter(pixmap)
            icon_painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
            icon_painter.fillRect(pixmap.rect(), foreground)
            icon_painter.end()
            painter.drawPixmap(icon_rect, pixmap)
            rect.setLeft(icon_rect.right() + 6)
        painter.setPen(foreground)
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.text())
        if self.hasFocus():
            painter.setPen(QtGui.QPen(foreground, 1.5))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(3, 3, -3, -3), 3, 3)
