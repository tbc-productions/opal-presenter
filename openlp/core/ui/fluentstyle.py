"""Fluent presentation on existing Qt widgets, without an additional Qt runtime."""
import ctypes

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

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
    """Native Fluent accent command with the existing QAction contract."""
    def __init__(self, parent=None):
        import fluentqt
        super().__init__(parent)
        self.setProperty('fluentAccent', True)
        self.setFluentStyle(fluentqt.Button.ButtonStyle.Accent)
        self.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setIconSize(QtCore.QSize(18, 18))
