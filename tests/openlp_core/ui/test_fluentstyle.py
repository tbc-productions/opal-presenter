"""Fluent appearance preserves action behavior and isolates output windows."""
from unittest.mock import Mock

import pytest
from PySide6 import QtCore, QtGui, QtTest
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.ui.fluentstyle import FluentAccentButton


def test_accent_button_keeps_action_mouse_keyboard_and_disabled_behavior(qapp):
    button = FluentAccentButton()
    action = QtGui.QAction('Go live', button)
    triggered = Mock()
    action.triggered.connect(triggered)
    button.setDefaultAction(action)
    button.show()
    QtTest.QTest.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    QtTest.QTest.keyClick(button, QtCore.Qt.Key.Key_Space)
    assert triggered.call_count == 2
    action.setEnabled(False)
    QtTest.QTest.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    QtTest.QTest.keyClick(button, QtCore.Qt.Key.Key_Space)
    assert triggered.call_count == 2
    assert not button.isEnabled()
    button.close()


def test_accent_uses_native_style_and_motion(qapp):
    import fluentqt
    button = FluentAccentButton()
    assert isinstance(button, fluentqt.Button)
    assert button.fluentStyle() == fluentqt.Button.ButtonStyle.Accent


@pytest.mark.parametrize('window_color, accent', [('#f3f3f3', '#005fb8'), ('#202020', '#60cdff')])
def test_accent_render_uses_application_scheme_with_transparent_widget_palette(qapp, window_color, accent):
    app = QtWidgets.QApplication.instance()
    original = app.palette()
    import fluentqt
    original_theme = fluentqt.current_theme()
    fluentqt.initialize_resources()
    fluentqt.set_theme(fluentqt.Theme.Dark if window_color == '#202020' else fluentqt.Theme.Light)
    palette = QtGui.QPalette(original)
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(window_color))
    app.setPalette(palette)
    button = FluentAccentButton()
    button.setStyleSheet('background: transparent;')
    button.resize(100, 32)
    try:
        rendered = button.grab().toImage()
        assert rendered.pixelColor(8, 16).name() == accent
    finally:
        app.setPalette(original)
        fluentqt.set_theme(original_theme)


def test_native_controls_do_not_install_a_projection_stylesheet(settings):
    from openlp.core.ui.style import get_application_stylesheet, set_default_theme
    from PySide6 import QtWidgets as NativeQt
    import fluentqt
    app = QtWidgets.QApplication.instance()
    set_default_theme(app)
    output = NativeQt.QWidget()
    field = QtWidgets.QLineEdit()
    assert isinstance(field, fluentqt.LineEdit)
    assert not output.styleSheet()
    assert 'QLineEdit {' not in get_application_stylesheet()
