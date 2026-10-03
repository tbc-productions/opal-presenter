"""Modern operator-interface styling and optional native window materials."""
import ctypes
from ctypes import wintypes
import logging
import sys

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.platform import is_win
from openlp.core.ui.fluentstyle import fluent_colors


log = logging.getLogger(__name__)


def is_modern_style():
    """Use the selected appearance on every platform."""
    return True


def set_modern_palette(app):
    """Use solid content surfaces and a quiet blue accent in either color scheme."""
    palette = app.palette()
    tokens = fluent_colors(palette)
    colors = {
        QtGui.QPalette.ColorRole.Window: tokens['window'],
        QtGui.QPalette.ColorRole.WindowText: tokens['text'],
        QtGui.QPalette.ColorRole.Base: tokens['surface'],
        QtGui.QPalette.ColorRole.Text: tokens['text'],
        QtGui.QPalette.ColorRole.AlternateBase: tokens['alternate'],
        QtGui.QPalette.ColorRole.Button: tokens['control'],
        QtGui.QPalette.ColorRole.ButtonText: tokens['text'],
        QtGui.QPalette.ColorRole.Highlight: tokens['selection'],
        QtGui.QPalette.ColorRole.HighlightedText: tokens['text'],
        QtGui.QPalette.ColorRole.Link: tokens['accent'],
        QtGui.QPalette.ColorRole.Mid: tokens['border'],
    }
    for role, color in colors.items():
        for group in (QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorGroup.Inactive):
            palette.setColor(group, role, QtGui.QColor(color))
    for role in (QtGui.QPalette.ColorRole.WindowText, QtGui.QPalette.ColorRole.Text,
                 QtGui.QPalette.ColorRole.ButtonText):
        palette.setColor(QtGui.QPalette.ColorGroup.Disabled, role, QtGui.QColor(tokens['disabled']))
    app.setPalette(palette)
    if is_win():
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
QMainWindow#MainWindow QToolButton#qt_toolbar_ext_button { padding: 0; border: none; }
QMainWindow#MainWindow QLabel#output_status {
    background: transparent; color: palette(window-text); border: none; padding: 0;
}
"""


class ModernPresetTabBar(QtWidgets.QWidget):
    """Vertical native Fluent commands retaining preset selection and keyboard navigation."""
    currentChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = []
        self._current = -1
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

    def addTab(self, text):
        index = len(self._buttons)
        button = QtWidgets.QPushButton(text, self)
        button.setCheckable(True)
        button.setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Subtle)
        button.setFixedHeight(56)
        button.clicked.connect(lambda checked=False, index=index: self.setCurrentIndex(index))
        self._buttons.append(button)
        self._layout.addWidget(button)
        if self._current < 0:
            self.setCurrentIndex(0)
        return index

    def count(self):
        return len(self._buttons)

    def tabText(self, index):
        return self._buttons[index].text()

    def setTabText(self, index, text):
        self._buttons[index].setText(text)

    def tabIcon(self, index):
        return self._buttons[index].icon()

    def setTabIcon(self, index, icon):
        self._buttons[index].setIcon(icon)

    def currentIndex(self):
        return self._current

    def setCurrentIndex(self, index):
        if not 0 <= index < self.count():
            return
        changed = self._current != index
        self._current = index
        for number, button in enumerate(self._buttons):
            button.setChecked(number == index)
            button.setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Accent if number == index
                                  else QtWidgets.fluentqt.Button.ButtonStyle.Subtle)
        if changed:
            self.currentChanged.emit(index)

    def tabRect(self, index):
        return self._buttons[index].geometry()

    def tabSizeHint(self, index):
        return self._buttons[index].sizeHint().expandedTo(QtCore.QSize(64, 56))

    def setShape(self, shape):
        pass  # This preset rail is always vertical.

    def setDocumentMode(self, enabled):
        pass  # Native Fluent buttons own their surfaces.

    def setDrawBase(self, enabled):
        pass

    def setMovable(self, enabled):
        pass  # Preset order is fixed by the application.

    def setExpanding(self, enabled):
        pass

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
            step = 1 if event.key() == QtCore.Qt.Key.Key_Down else -1
            self.setCurrentIndex(self.currentIndex() + step)
            event.accept()
        else:
            super().keyPressEvent(event)


def refine_modern_layout(window):
    """Compact operator toolbars and share the screen-preview divider position."""
    if not is_modern_style():
        return
    for toolbar in window.findChildren(QtWidgets.QToolBar):
        toolbar.setIconSize(QtCore.QSize(18, 18))
    preview = window.preview_controller.splitter
    live = window.live_controller.splitter
    command_bars = [controller.toolbar for controller in (window.preview_controller, window.live_controller)
                    if hasattr(controller, 'toolbar')]

    def align_command_bars():
        # The divider includes the command row. Reserve the same height on both
        # sides so a SplitButton cannot shorten just one of the slide lists.
        height = max((toolbar.layout().sizeHint().height() for toolbar in command_bars), default=0)
        for toolbar in command_bars:
            if toolbar.minimumHeight() != height or toolbar.maximumHeight() != height:
                toolbar.setFixedHeight(height)
        for splitter in (preview, live):
            layout = splitter.widget(0).layout()
            if layout:
                layout.activate()

    def align(source, target):
        align_command_bars()
        if not source.isVisible() or not target.isVisible() or not source.sizes():
            return
        position = source.sizes()[0]
        available = max(0, target.height() - target.handleWidth())
        target.setSizes([position, max(0, available - position)])

    # setSizes does not emit splitterMoved, so each divider can drive its peer safely.
    preview.splitterMoved.connect(lambda position, index: align(preview, live))
    live.splitterMoved.connect(lambda position, index: align(live, preview))
    alignment_timer = QtCore.QTimer(window)
    alignment_timer.setSingleShot(True)
    alignment_timer.timeout.connect(lambda: align(preview, live))

    class DividerAlignment(QtCore.QObject):
        def eventFilter(self, watched, event):
            if event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show,
                                QtCore.QEvent.Type.LayoutRequest):
                alignment_timer.start(0)
            return False

    window._divider_alignment = DividerAlignment(window)
    preview.installEventFilter(window._divider_alignment)
    live.installEventFilter(window._divider_alignment)
    for toolbar in command_bars:
        toolbar.installEventFilter(window._divider_alignment)
    alignment_timer.start(0)


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
    if not is_win() or not is_modern_style():
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
