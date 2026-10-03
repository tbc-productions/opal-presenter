"""Fluent appearance preserves action behavior and isolates output windows."""
from unittest.mock import Mock, patch

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from openlp.core.ui.fluentstyle import FluentAccentButton, configure_fluent_surfaces


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


def test_reduced_motion_hover_is_immediate(qapp):
    button = FluentAccentButton()
    with patch('openlp.core.ui.fluentstyle.animations_enabled', return_value=False):
        button._animate_hover(1.0)
    assert button._hover == 1.0
    assert button._animation.state() == QtCore.QAbstractAnimation.State.Stopped


@pytest.mark.parametrize('window_color, accent', [('#f3f3f3', '#0067c0'), ('#202020', '#60cdff')])
def test_accent_render_uses_application_scheme_with_transparent_widget_palette(qapp, window_color, accent):
    app = QtWidgets.QApplication.instance()
    original = app.palette()
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


def test_fluent_surfaces_include_dialogs_but_exclude_output_windows(qapp):
    app = QtWidgets.QApplication.instance()
    configure_fluent_surfaces(app, True)
    dialog, menu, output = QtWidgets.QDialog(), QtWidgets.QMenu(), QtWidgets.QWidget()
    try:
        for widget in (dialog, menu, output):
            widget.ensurePolished()
        assert dialog.property('fluentUi') is True
        assert menu.property('fluentUi') is True
        assert output.property('fluentUi') is None
        configure_fluent_surfaces(app, False)
        classic_dialog = QtWidgets.QDialog()
        classic_dialog.ensurePolished()
        assert classic_dialog.property('fluentUi') is None
    finally:
        configure_fluent_surfaces(app, False)
