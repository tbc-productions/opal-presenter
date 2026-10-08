"""Fluent button glyphs follow native text colours without changing reusable icons."""
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
import fluentqt

from openlp.core.app import OpenLP
from openlp.core.ui.fluenticons import _icon_font, fluent_icon
from openlp.core.widgets import fluent
from openlp.core.widgets.toolbar import OpenLPToolbar


@pytest.fixture(scope='session')
def native_application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def qapp(native_application):
    return OpenLP()


@pytest.mark.parametrize('kind', ['push', 'tool', 'split'])
@pytest.mark.parametrize('dark', [False, True])
@pytest.mark.parametrize('checked,enabled', [(False, True), (True, True), (True, False)])
def test_icon_matches_native_glyph_colours(qtbot, kind, dark, checked, enabled):
    previous_theme = fluentqt.current_theme()
    fluentqt.set_theme(fluentqt.Theme.Dark if dark else fluentqt.Theme.Light)
    try:
        factory = {'push': fluent.QPushButton, 'tool': fluent.QToolButton, 'split': fluent.QSplitButton}[kind]
        button = factory()
        reference = fluentqt.SplitButton() if kind == 'split' else fluentqt.Button()
        for control in (button, reference):
            qtbot.addWidget(control)
            control.setText('Grid')
            control.setFluentSize(button.fluentSize())
            control.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)
            control.setFocusVisual(False)
            control.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            control.setCheckable(True)
            control.setChecked(checked)
            control.setEnabled(enabled)
            control.resize(160, 40)
        icon = fluent_icon('ic_fluent_grid_24_regular', color='red', color_disabled='red', color_on='red')
        family, glyphs = _icon_font()
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(20, 20))
        reference.setIconGlyph(chr(glyphs[icon.name()]), 20, family)
        button.show()
        reference.show()
        qtbot.wait(30)
        assert button.grab().toImage() == reference.grab().toImage()
        assert button.icon().name() == icon.name()
        # An action or menu can still request the source icon's explicit colour.
        image = icon.pixmap(20, 20).toImage()
        assert any(image.pixelColor(x, y).name() == '#ff0000' for x in range(20) for y in range(20))
    finally:
        fluentqt.set_theme(previous_theme)


def test_replacing_fluent_glyph_with_raster_icon_preserves_image(qtbot):
    button = fluent.QPushButton('Preview')
    qtbot.addWidget(button)
    button.setIcon(fluent_icon('ic_fluent_grid_24_regular'))
    pixmap = QtGui.QPixmap(20, 20)
    pixmap.fill(QtGui.QColor('#00ff00'))
    icon = QtGui.QIcon(pixmap)
    button.setIcon(icon)
    assert not button.iconGlyph()
    assert button.icon().cacheKey() == icon.cacheKey()
    button.show()
    image = button.grab().toImage()
    assert any(image.pixelColor(x, y).name() == '#00ff00'
               for x in range(image.width()) for y in range(image.height()))


def test_native_commandbar_updates_glyphs_after_action_changes(qtbot):
    toolbar = OpenLPToolbar(None)
    qtbot.addWidget(toolbar)
    first = fluent_icon('ic_fluent_grid_24_regular', color='red')
    second = fluent_icon('ic_fluent_apps_list_24_regular', color='red')
    action = toolbar.add_toolbar_action('view', text='View', icon=first)
    toolbar.show()
    family, glyphs = _icon_font()
    qtbot.waitUntil(lambda: toolbar.widgetForAction(action).iconGlyph() == chr(glyphs[first.name()]))
    action.setIcon(second)
    qtbot.waitUntil(lambda: toolbar.widgetForAction(action).iconGlyph() == chr(glyphs[second.name()]))
    assert toolbar.widgetForAction(action).iconFontFamily() == family
