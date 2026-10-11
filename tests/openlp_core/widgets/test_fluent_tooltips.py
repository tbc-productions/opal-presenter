"""Existing Qt tooltip contracts use the native Fluent surface."""
import fluentqt
import pytest
import os
import subprocess
import sys
from PySide6 import QtCore, QtGui, QtWidgets

from opal.core.widgets.fluent_tooltips import FluentToolTip, install_fluent_tooltips
from opal.core.widgets import fluent as FluentWidgets


@pytest.fixture
def tooltip_filter(qapp):
    fluentqt.initialize_resources()
    event_filter = install_fluent_tooltips(QtWidgets.QApplication.instance())
    event_filter.tip.setAnimationEnabled(False)
    yield event_filter
    event_filter.hide()


def hover(widget, point=QtCore.QPoint(10, 10)):
    install_fluent_tooltips(QtWidgets.QApplication.instance()).watch_widgets()
    event = QtGui.QHelpEvent(QtCore.QEvent.Type.ToolTip, point, widget.mapToGlobal(point))
    QtWidgets.QApplication.sendEvent(widget, event)


def test_widget_hints_update_and_clear_without_native_popup(tooltip_filter, qtbot):
    button = QtWidgets.QPushButton('Command')
    qtbot.addWidget(button)
    button.show()
    button.setToolTip('Original hint')
    hover(button)
    assert isinstance(tooltip_filter.tip, fluentqt.ToolTip)
    assert tooltip_filter.tip.isVisible()
    assert not QtWidgets.QToolTip.isVisible()
    button.setToolTip('Updated hint')
    hover(button)
    assert tooltip_filter.tip.text() == 'Updated hint'
    button.setToolTip('')
    hover(button)
    assert not tooltip_filter.tip.isVisible()


@pytest.mark.parametrize('widgets', [QtWidgets, FluentWidgets])
def test_model_hints_follow_hovered_row(tooltip_filter, qtbot, widgets):
    view = widgets.QTreeWidget()
    qtbot.addWidget(view)
    first = widgets.QTreeWidgetItem(view, ['First'])
    first.setToolTip(0, 'First row hint')
    second = widgets.QTreeWidgetItem(view, ['Second'])
    second.setToolTip(0, 'Second row hint')
    view.show()
    hover(view.viewport(), view.visualItemRect(first).center())
    assert tooltip_filter.tip.text() == 'First row hint'
    hover(view.viewport(), view.visualItemRect(second).center())
    assert tooltip_filter.tip.text() == 'Second row hint'
    QtWidgets.QApplication.sendEvent(view.viewport(), QtCore.QEvent(QtCore.QEvent.Type.Leave))
    assert not tooltip_filter.tip.isVisible()


def test_menu_hints_use_current_action(tooltip_filter, qtbot):
    menu = QtWidgets.QMenu()
    qtbot.addWidget(menu)
    action = menu.addAction('Command')
    action.setToolTip('Command hint')
    menu.show()
    hover(menu, menu.actionGeometry(action).center())
    assert tooltip_filter.tip.text() == 'Command hint'


def test_immediate_hints_wrap_expire_and_dismiss(tooltip_filter, qtbot):
    widget = QtWidgets.QWidget()
    qtbot.addWidget(widget)
    widget.show()
    text = 'A long service note with enough words to wrap. ' * 30
    FluentToolTip.showText(widget.mapToGlobal(QtCore.QPoint()), text, widget, msecShowTime=30)
    assert FluentToolTip.isVisible()
    assert FluentToolTip.text() == text
    assert tooltip_filter.tip.width() <= 540
    qtbot.waitUntil(lambda: not FluentToolTip.isVisible())
    FluentToolTip.showText(widget.mapToGlobal(QtCore.QPoint()), 'Drag hint', widget)
    FluentToolTip.hideText()
    assert not FluentToolTip.isVisible()


def test_click_dismisses_hint_and_installation_is_idempotent(tooltip_filter, qtbot):
    widget = QtWidgets.QPushButton('Command')
    qtbot.addWidget(widget)
    widget.setToolTip('Hint')
    widget.show()
    hover(widget)
    qtbot.mouseClick(widget, QtCore.Qt.MouseButton.LeftButton)
    assert not tooltip_filter.tip.isVisible()
    assert install_fluent_tooltips(QtWidgets.QApplication.instance()) is tooltip_filter


def test_tooltip_discovery_registers_later_widgets(tooltip_filter, qtbot):
    widget = QtWidgets.QPushButton('Later command')
    qtbot.addWidget(widget)
    widget.setToolTip('Later hint')
    widget.show()
    qtbot.waitUntil(lambda: widget in tooltip_filter._watched_widgets)
    event = QtGui.QHelpEvent(QtCore.QEvent.Type.ToolTip, QtCore.QPoint(10, 10),
                             widget.mapToGlobal(QtCore.QPoint(10, 10)))
    QtWidgets.QApplication.sendEvent(widget, event)
    assert tooltip_filter.tip.text() == 'Later hint'


def test_tooltips_do_not_filter_internal_quick_objects():
    """Exercise native construction in a subprocess so regressions report safely."""
    result = subprocess.run([sys.executable, '-c', '''
from unittest.mock import patch
from PySide6 import QtWidgets, QtQuickWidgets, QtCore
from opal.core.widgets.fluent_tooltips import install_fluent_tooltips
app = QtWidgets.QApplication([])
with patch.object(app, 'installEventFilter') as global_filter:
    install_fluent_tooltips(app)
    global_filter.assert_not_called()
widget = QtQuickWidgets.QQuickWidget()
widget.setSource(QtCore.QUrl('data:text/plain,import QtQuick; Item { width: 100; height: 100 }'))
widget.show()
for _ in range(5):
    app.processEvents()
assert widget.status() == QtQuickWidgets.QQuickWidget.Status.Ready
'''], env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
