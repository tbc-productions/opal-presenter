"""Modern Windows operator-interface styling and optional native window materials."""
import ctypes
from ctypes import wintypes
import logging
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.platform import is_win
from openlp.core.common.registry import Registry


log = logging.getLogger(__name__)


def is_modern_style():
    """Keep the modern appearance opt-in and confined to Windows."""
    if not is_win():
        return False
    settings = Registry().get('settings')
    return settings is not None and settings.value('advanced/interface style') == 'modern'


def set_modern_palette(app):
    """Use solid content surfaces and a quiet blue accent in either color scheme."""
    palette = app.palette()
    dark = palette.color(QtGui.QPalette.ColorRole.Window).lightness() < 128
    colors = {
        QtGui.QPalette.ColorRole.Window: '#202631' if dark else '#eef3f9',
        QtGui.QPalette.ColorRole.Base: '#171c24' if dark else '#ffffff',
        QtGui.QPalette.ColorRole.AlternateBase: '#202631' if dark else '#f5f8fc',
        QtGui.QPalette.ColorRole.Button: '#293140' if dark else '#f4f7fb',
        QtGui.QPalette.ColorRole.Highlight: '#005fcc' if dark else '#d7e9ff',
        QtGui.QPalette.ColorRole.HighlightedText: '#ffffff' if dark else '#004ca8',
        QtGui.QPalette.ColorRole.Link: '#70b5ff' if dark else '#0067c0',
        QtGui.QPalette.ColorRole.Mid: '#3e495a' if dark else '#d4deeb',
    }
    for role, color in colors.items():
        for group in (QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorGroup.Inactive):
            palette.setColor(group, role, QtGui.QColor(color))
    app.setPalette(palette)
    font = app.font()
    font.setFamily('Segoe UI')
    font.setPointSize(10)
    app.setFont(font)


def get_modern_stylesheet():
    """Style operator controls; projection windows do not use these selectors."""
    return """
QMainWindow#MainWindow { background: palette(window); }
QWidget#main_content { background: palette(window); }
QWidget[modernPanel="true"] { background: palette(window); }
QMainWindow#MainWindow QDockWidget { background: palette(base); }
QMainWindow#MainWindow QDockWidget::title {
    background: palette(window); border: none;
    padding: 4px 6px; font-weight: 600;
}
QMainWindow#MainWindow QToolBar {
    background: palette(window); border: none; spacing: 2px; padding: 2px;
}
QMainWindow#MainWindow QMenuBar { background: palette(window); padding: 4px; }
QMainWindow#MainWindow QMenuBar::item { padding: 5px 10px; }
QMainWindow#MainWindow QMenuBar::item:selected { background: palette(highlight); border-radius: 4px; }
QMainWindow#MainWindow QStatusBar { background: palette(window); padding: 5px 8px; }
QMainWindow#MainWindow QSplitter::handle { background: palette(window); }
QMainWindow#MainWindow::separator { background: palette(window); width: 8px; height: 8px; }
QMainWindow#MainWindow QAbstractItemView {
    background: palette(base); border: 1px solid palette(mid); border-radius: 4px;
    selection-background-color: palette(highlight); selection-color: palette(highlighted-text);
}
QMainWindow#MainWindow QTreeView::item, QMainWindow#MainWindow QListView::item { padding: 3px 4px; }
/* Do not override table headers: slide-number headers carry per-verse background brushes. */
QMainWindow#MainWindow QTreeView QHeaderView::section {
    background: palette(button); border: none; padding: 3px;
}
QMainWindow#MainWindow QLineEdit {
    background: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 3px;
}
QMainWindow#MainWindow QLineEdit:focus { border-color: palette(link); }
QMainWindow#MainWindow QToolButton, QMainWindow#MainWindow QPushButton {
    background: transparent; border: 1px solid transparent; border-radius: 3px; padding: 2px 4px;
}
QMainWindow#MainWindow QToolButton:hover, QMainWindow#MainWindow QPushButton:hover {
    background: palette(button); border-color: palette(mid);
}
QMainWindow#MainWindow QToolButton:checked, QMainWindow#MainWindow QPushButton:pressed {
    background: palette(highlight); color: palette(highlighted-text); border-color: palette(link);
}
QMainWindow#MainWindow QToolButton#qt_toolbar_ext_button { padding: 0; border: none; }
QMainWindow#MainWindow QTabBar::tab { background: palette(window); padding: 5px 8px; border: none; }
QMainWindow#MainWindow QTabBar::tab:selected {
    background: palette(base); color: palette(link); border-bottom: 2px solid palette(link);
}
QMainWindow#MainWindow QToolButton[primaryAction="true"] {
    background: #0067c0; color: white; border-color: #0067c0; padding: 3px 8px; font-weight: 600;
}
QMainWindow#MainWindow QToolButton[primaryAction="true"]:hover { background: #005aab; }
QMainWindow#MainWindow QToolButton[primaryAction="true"]:disabled {
    background: palette(button); color: palette(mid); border-color: palette(mid);
}
QMainWindow#MainWindow QLabel#output_status { border-radius: 3px; padding: 3px 8px; }
QMainWindow#MainWindow QLabel#output_status[onAir="true"] { background: #bceac8; color: #125525; }
QMainWindow#MainWindow QLabel#output_status[onAir="false"] {
    background: palette(button); color: palette(window-text);
}
"""


class ModernPresetTabBar(QtWidgets.QTabBar):
    """Keep the existing preset tab API, with upright icon-and-label navigation."""

    def tabSizeHint(self, index):
        width = max(64, self.fontMetrics().horizontalAdvance(self.tabText(index)) + 16)
        return QtCore.QSize(width, 56)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
            step = 1 if event.key() == QtCore.Qt.Key.Key_Down else -1
            index = self.currentIndex() + step
            while 0 <= index < self.count():
                if self.isTabEnabled(index) and self.isTabVisible(index):
                    self.setCurrentIndex(index)
                    break
                index += step
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        for index in range(self.count()):
            rect = self.tabRect(index).adjusted(4, 4, -4, -4)
            selected = index == self.currentIndex()
            if selected:
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(palette.highlight())
                painter.drawRoundedRect(rect, 5, 5)
            icon_rect = QtCore.QRect(rect.center().x() - 10, rect.top() + 5, 20, 20)
            self.tabIcon(index).paint(painter, icon_rect)
            painter.setPen(palette.highlightedText().color() if selected else palette.windowText().color())
            text_rect = rect.adjusted(2, 27, -2, -2)
            painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.tabText(index))
            if selected and self.hasFocus():
                option = QtWidgets.QStyleOptionFocusRect()
                option.initFrom(self)
                option.rect = rect.adjusted(2, 2, -2, -2)
                self.style().drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_FrameFocusRect, option, painter, self)


def refine_modern_layout(window):
    """Compact operator toolbars and share the screen-preview divider position."""
    if not is_modern_style():
        return
    for toolbar in window.findChildren(QtWidgets.QToolBar):
        toolbar.setIconSize(QtCore.QSize(18, 18))
    preview = window.preview_controller.splitter
    live = window.live_controller.splitter

    def align(source, target):
        if not source.isVisible() or not target.isVisible() or not source.sizes():
            return
        position = source.sizes()[0]
        available = max(0, target.height() - target.handleWidth())
        target.setSizes([position, max(0, available - position)])

    # setSizes does not emit splitterMoved, so each divider can drive its peer safely.
    preview.splitterMoved.connect(lambda position, index: align(preview, live))
    live.splitterMoved.connect(lambda position, index: align(live, preview))
    QtCore.QTimer.singleShot(0, lambda: align(preview, live))


def _set_dwm_attribute(hwnd, attribute, value):
    """Call the documented DWM API using pointer-sized HWND arguments."""
    dwm = ctypes.WinDLL('dwmapi')
    set_attribute = dwm.DwmSetWindowAttribute
    set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    set_attribute.restype = ctypes.c_long
    data = ctypes.c_int(value)
    return set_attribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data)) == 0


def apply_mica(window):
    """Enable native Mica behind the window frame, leaving Qt content opaque.

    Windows 11 22H2 introduced DWMWA_SYSTEMBACKDROP_TYPE. The system manages
    material fallbacks; failed calls retain the normal solid window appearance.
    """
    if not is_modern_style():
        return False
    try:
        if sys.getwindowsversion().build < 22621:
            return False
        hwnd = int(window.winId())
        dark = window.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128
        _set_dwm_attribute(hwnd, 20, int(dark))  # DWMWA_USE_IMMERSIVE_DARK_MODE
        return _set_dwm_attribute(hwnd, 38, 2)  # DWMWA_SYSTEMBACKDROP_TYPE / DWMSBT_MAINWINDOW
    except (OSError, AttributeError):
        log.debug('Native Mica is unavailable; retaining solid window chrome', exc_info=True)
        return False
