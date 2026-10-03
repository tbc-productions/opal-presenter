"""Present existing widget, action and model hints with FluentQt's tooltip surface."""
import fluentqt
import weakref
from PySide6 import QtCore, QtGui, QtWidgets


class FluentToolTipFilter(QtCore.QObject):
    """Keep Qt's hover timing and tooltip text while replacing its popup."""

    def __init__(self, app):
        super().__init__(app)
        self.tip = fluentqt.ToolTip()
        # FluentQt paints its own shadow. Cocoa's additional window shadow
        # outlines the entire translucent backing window, including its margin.
        self.tip.setWindowFlag(QtCore.Qt.WindowType.NoDropShadowWindowHint)
        self.tip.setObjectName('openlp_fluent_tooltip')
        self.owner = None
        self.area = QtCore.QRect()
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        app.aboutToQuit.connect(self.tip.deleteLater)
        self._watched_widgets = weakref.WeakSet()
        self._discovery_timer = QtCore.QTimer(self)
        self._discovery_timer.setInterval(250)
        self._discovery_timer.timeout.connect(self.watch_widgets)
        self._discovery_timer.start()
        self.watch_widgets()

    def watch_widgets(self):
        # An application-wide Python filter asks Shiboken to wrap every event
        # receiver, including Qt Quick objects still under construction. That
        # can crash before eventFilter is entered. Only observe QWidget targets.
        for widget in QtWidgets.QApplication.allWidgets():
            if widget not in self._watched_widgets:
                widget.installEventFilter(self)
                self._watched_widgets.add(widget)

    def show_text(self, position, text, widget=None, rect=None, duration=-1):
        if not text:
            self.hide()
            return
        self.owner = widget
        self.watch_widgets()
        self.area = QtCore.QRect(rect) if rect is not None else QtCore.QRect()
        self.tip.setThemeSource(widget)
        self.tip.setText(text)
        label = self.tip.findChild(fluentqt.Label)
        screen = QtGui.QGuiApplication.screenAt(position) or QtGui.QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        # Long notes and filenames should wrap rather than extend off the screen.
        label.setWordWrap(False)
        label.setMaximumWidth(min(480, max(80, available.width() - 64)))
        label.setWordWrap(label.sizeHint().width() > label.maximumWidth())
        self.tip.adjustSize()
        margin = self.tip.shadowMargin()
        x = min(position.x(), available.right() - self.tip.width() + margin)
        y = position.y() + 20
        if y + self.tip.height() - margin > available.bottom():
            y = position.y() - self.tip.height() + margin - 4
        self.tip.move(max(available.left() - margin, x - margin),
                      max(available.top() - margin, y - margin))
        self.tip.show()
        self.tip.raise_()
        self.timer.start(duration if duration >= 0 else 10000 + 40 * max(0, len(text) - 100))

    def hide(self):
        self.timer.stop()
        self.tip.hide()
        self.owner = None

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QtCore.QEvent.Type.ToolTip and isinstance(watched, QtWidgets.QWidget):
            text = watched.toolTip()
            area = watched.rect()
            parent = watched.parentWidget()
            if isinstance(parent, QtWidgets.QHeaderView) and watched is parent.viewport():
                section = parent.logicalIndexAt(event.pos())
                model = parent.model()
                text = model.headerData(section, parent.orientation(), QtCore.Qt.ItemDataRole.ToolTipRole) \
                    if section >= 0 and model is not None else ''
            elif isinstance(parent, QtWidgets.QAbstractItemView) and watched is parent.viewport():
                index = parent.indexAt(event.pos())
                text = (index.data(QtCore.Qt.ItemDataRole.ToolTipRole) if index.isValid() else '') or text
                area = parent.visualRect(index)
            elif isinstance(watched, QtWidgets.QMenu):
                action = watched.actionAt(event.pos())
                text = action.toolTip() if action is not None else ''
                area = watched.actionGeometry(action) if action is not None else area
            if text:
                self.show_text(event.globalPos(), text, watched, area, watched.toolTipDuration())
                event.accept()
                return True
            self.hide()
        elif self.owner is not None:
            if kind in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.KeyPress,
                        QtCore.QEvent.Type.Wheel, QtCore.QEvent.Type.WindowDeactivate):
                self.hide()
            elif watched is self.owner or watched is self.owner.window():
                if kind in (QtCore.QEvent.Type.Leave, QtCore.QEvent.Type.Hide,
                            QtCore.QEvent.Type.Destroy):
                    self.hide()
                elif kind == QtCore.QEvent.Type.MouseMove and not self.area.isNull():
                    if not self.area.contains(event.position().toPoint()):
                        self.hide()
        return False


def install_fluent_tooltips(app):
    """Install once, retaining the Python filter for the application's lifetime."""
    if not hasattr(app, '_fluent_tooltip_filter'):
        app._fluent_tooltip_filter = FluentToolTipFilter(app)
    app._fluent_tooltip_filter.watch_widgets()
    return app._fluent_tooltip_filter


class FluentToolTip:
    """Qt-compatible entry points for immediate service notes and drag hints."""

    @staticmethod
    def showText(position, text, widget=None, rect=None, msecShowTime=-1):
        install_fluent_tooltips(QtWidgets.QApplication.instance()).show_text(
            position, text, widget, rect, msecShowTime)

    @staticmethod
    def hideText():
        app = QtWidgets.QApplication.instance()
        if hasattr(app, '_fluent_tooltip_filter'):
            app._fluent_tooltip_filter.hide()

    @staticmethod
    def isVisible():
        app = QtWidgets.QApplication.instance()
        return hasattr(app, '_fluent_tooltip_filter') and app._fluent_tooltip_filter.tip.isVisible()

    @staticmethod
    def text():
        app = QtWidgets.QApplication.instance()
        return app._fluent_tooltip_filter.tip.text() if FluentToolTip.isVisible() else ''


QToolTip = FluentToolTip
