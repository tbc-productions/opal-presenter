"""Modern appearance selection, native fallback and operator-state regression tests."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6 import QtCore, QtGui, QtTest
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.ui import HideMode
from openlp.core.ui.modernstyle import (
    ModernPresetTabBar, apply_mica, is_modern_style, refine_modern_layout, set_modern_palette
)
from openlp.core.ui.slidecontroller import SlideController
from openlp.core.ui.style import UiThemes, get_application_stylesheet, get_library_stylesheet, set_default_theme


@pytest.mark.parametrize('windows', [True, False])
def test_modern_supported_platforms(settings, windows):
    settings.setValue('advanced/interface style', 'modern')
    with patch('openlp.core.ui.modernstyle.is_win', return_value=windows):
        assert is_modern_style() is True


@pytest.mark.parametrize('scheme', [UiThemes.DefaultLight, UiThemes.DefaultDark, UiThemes.QDarkStyle])
def test_modern_color_schemes_have_solid_readable_surfaces(settings, qapp, scheme):
    app = QtWidgets.QApplication.instance()
    old_palette, old_font = app.palette(), app.font()
    settings.setValue('advanced/interface style', 'modern')
    settings.setValue('advanced/ui_theme_name', scheme)
    try:
        with patch('openlp.core.ui.modernstyle.is_win', return_value=True):
            set_default_theme(app)
            palette = app.palette()
            base = palette.color(QtGui.QPalette.ColorRole.Base)
            text = palette.color(QtGui.QPalette.ColorRole.Text)
            assert base.alpha() == 255
            assert abs(base.lightness() - text.lightness()) > 160
            assert '#MainWindow' in get_application_stylesheet()
            assert get_library_stylesheet() == ''
    finally:
        app.setPalette(old_palette)
        app.setFont(old_font)


def test_non_windows_does_not_call_native_material_api(settings):
    settings.setValue('advanced/interface style', 'classic')
    with patch('openlp.core.ui.modernstyle.is_win', return_value=False), \
            patch('openlp.core.ui.modernstyle._set_dwm_attribute') as native:
        assert apply_mica(None) is False
        native.assert_not_called()


@pytest.mark.parametrize('build', [19045, 22000])
def test_older_windows_falls_back_without_native_calls(settings, build):
    settings.setValue('advanced/interface style', 'modern')
    with patch('openlp.core.ui.modernstyle.is_win', return_value=True), \
            patch('openlp.core.ui.modernstyle.sys.getwindowsversion', create=True,
                  return_value=SimpleNamespace(build=build)), \
            patch('openlp.core.ui.modernstyle._set_dwm_attribute') as native:
        assert apply_mica(None) is False
        native.assert_not_called()


def test_failed_mica_keeps_solid_fallback(settings):
    settings.setValue('advanced/interface style', 'modern')
    window = QtWidgets.QMainWindow()
    with patch('openlp.core.ui.modernstyle.is_win', return_value=True), \
            patch('openlp.core.ui.modernstyle.sys.getwindowsversion', create=True,
                  return_value=SimpleNamespace(build=22621)), \
            patch('openlp.core.ui.modernstyle._set_dwm_attribute', side_effect=OSError):
        assert apply_mica(window) is False


def test_mica_uses_documented_attributes(settings):
    settings.setValue('advanced/interface style', 'modern')
    window = QtWidgets.QMainWindow()
    with patch('openlp.core.ui.modernstyle.is_win', return_value=True), \
            patch('openlp.core.ui.modernstyle.sys.getwindowsversion', create=True,
                  return_value=SimpleNamespace(build=22621)), \
            patch('openlp.core.ui.modernstyle._set_dwm_attribute', return_value=True) as native:
        assert apply_mica(window) is True
        assert native.call_args.args[1:] == (38, 2)
        assert native.call_args_list[0].args[1] == 20


def test_modern_navigation_preserves_keyboard_selection(settings):
    tabs = ModernPresetTabBar()
    tabs.setShape(QtWidgets.QTabBar.Shape.RoundedWest)
    tabs.setExpanding(False)
    for label in ('Default', 'Setup', 'Live'):
        tabs.addTab(label)
    tabs.show()
    tabs.setFocus()
    QtTest.QTest.keyClick(tabs, QtCore.Qt.Key.Key_Down)
    assert tabs.currentIndex() == 1
    assert tabs.tabRect(1).top() >= tabs.tabRect(0).bottom()
    assert tabs.tabSizeHint(0).width() >= tabs.fontMetrics().horizontalAdvance('Default')


@pytest.mark.parametrize('has_item, hide_mode, displays, expected', [
    (False, None, [], 'Ready'),
    (True, None, [], 'Ready'),
    (True, None, [object()], 'Live'),
    (True, HideMode.Blank, [object()], 'Blank'),
    (True, HideMode.Screen, [object()], 'Desktop'),
])
def test_output_badge_tracks_item_and_hide_state(settings, has_item, hide_mode, displays, expected):
    controller = SlideController(None)
    controller.output_status_label = QtWidgets.QLabel()
    controller._current_hide_mode = hide_mode
    controller.displays = displays
    controller._update_output_status(has_item)
    assert controller.output_status_label.text() == expected
    assert controller.output_status_label.property('onAir') is (expected == 'Live')


def test_modern_header_background_is_actually_rendered(settings):
    """The application stylesheet must not hide section colors set on header items."""
    settings.setValue('advanced/interface style', 'modern')
    window = QtWidgets.QMainWindow()
    window.setObjectName('MainWindow')
    table = QtWidgets.QTableWidget(2, 1, window)
    window.setCentralWidget(table)
    table.setVerticalHeaderLabels(['V1', 'C1'])
    table.verticalHeader().setStyleSheet('QHeaderView::section { padding-left: 2px; padding-right: 2px; }')
    table.verticalHeaderItem(1).setBackground(QtGui.QColor('#38bd65'))
    with patch('openlp.core.ui.modernstyle.is_win', return_value=True):
        window.setStyleSheet(get_application_stylesheet())
    window.resize(400, 200)
    window.show()
    QtWidgets.QApplication.processEvents()
    header = table.verticalHeader()
    pixels = header.grab().toImage()
    y = header.sectionViewportPosition(1) + 5
    color = pixels.pixelColor(5 * pixels.devicePixelRatio(), y * pixels.devicePixelRatio())
    assert color.green() > color.red() + 40
    window.close()


def test_modern_splitter_alignment_and_compact_icons(settings):
    settings.setValue('advanced/interface style', 'modern')
    window = QtWidgets.QMainWindow()
    content = QtWidgets.QWidget(window)
    window.setCentralWidget(content)
    layout = QtWidgets.QHBoxLayout(content)
    splitters = []
    for _ in range(2):
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, content)
        splitter.addWidget(QtWidgets.QWidget())
        splitter.addWidget(QtWidgets.QWidget())
        layout.addWidget(splitter)
        splitters.append(splitter)
    window.preview_controller = SimpleNamespace(splitter=splitters[0])
    window.live_controller = SimpleNamespace(splitter=splitters[1])
    toolbar = QtWidgets.QToolBar(window)
    layout.addWidget(toolbar)
    window.resize(600, 400)
    window.show()
    QtWidgets.QApplication.processEvents()
    splitters[0].setSizes([200, 100])
    splitters[1].setSizes([80, 220])
    with patch('openlp.core.ui.modernstyle.is_win', return_value=True):
        refine_modern_layout(window)
    QtWidgets.QApplication.processEvents()
    assert abs(splitters[0].sizes()[0] - splitters[1].sizes()[0]) <= 1
    splitters[1].moveSplitter(120, 1)
    assert abs(splitters[0].sizes()[0] - splitters[1].sizes()[0]) <= 1
    window.resize(900, 600)
    QtWidgets.QApplication.processEvents()
    QtWidgets.QApplication.processEvents()
    assert abs(splitters[0].sizes()[0] - splitters[1].sizes()[0]) <= 1
    assert toolbar.iconSize() == QtCore.QSize(18, 18)
    window.close()


def test_slide_lists_align_with_different_command_bar_controls(qapp):
    from openlp.core.widgets.toolbar import OpenLPToolbar

    window = QtWidgets.QMainWindow()
    content = QtWidgets.QWidget(window)
    window.setCentralWidget(content)
    layout = QtWidgets.QHBoxLayout(content)
    controllers = []
    for _ in range(2):
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, content)
        panel = QtWidgets.QWidget(splitter)
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        slides = QtWidgets.QWidget(panel)
        panel_layout.addWidget(slides)
        toolbar = OpenLPToolbar(panel)
        toolbar.add_pinned_action(QtGui.QAction('Previous', toolbar))
        panel_layout.addWidget(toolbar)
        splitter.addWidget(QtWidgets.QWidget())
        layout.addWidget(splitter)
        controllers.append(SimpleNamespace(splitter=splitter, toolbar=toolbar, preview_widget=slides))
    preview, live = controllers
    play_button = QtWidgets.QSplitButton(live.toolbar)
    live.toolbar.addWidget(play_button)
    window.preview_controller = preview
    window.live_controller = live
    window.resize(800, 600)
    window.show()
    refine_modern_layout(window)

    def check_alignment():
        for _ in range(3):
            QtWidgets.QApplication.processEvents()
        assert preview.toolbar.height() == live.toolbar.height()
        assert abs(preview.preview_widget.height() - live.preview_widget.height()) <= 1

    check_alignment()
    live.splitter.moveSplitter(250, 1)
    check_alignment()
    window.resize(1000, 800)
    check_alignment()
    play_button.setMinimumHeight(64)
    check_alignment()
    assert preview.toolbar.height() >= 64
    window.close()


def test_macos_modern_does_not_call_windows_api(settings):
    settings.setValue('advanced/interface style', 'modern')
    with patch('openlp.core.ui.modernstyle.is_win', return_value=False), \
            patch('openlp.core.ui.modernstyle._set_dwm_attribute') as native:
        assert is_modern_style()
        assert apply_mica(None) is False
        native.assert_not_called()


def test_macos_modern_preserves_system_font(settings, qapp):
    app = QtWidgets.QApplication.instance()
    old_palette, old_font = app.palette(), app.font()
    try:
        with patch('openlp.core.ui.modernstyle.is_win', return_value=False):
            set_modern_palette(app)
            assert app.font() == old_font
    finally:
        app.setPalette(old_palette)
        app.setFont(old_font)
