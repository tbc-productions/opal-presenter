"""Verify Fluent catalogue coverage and Qt icon rendering states."""
from unittest.mock import patch

import fluentqt
from PySide6 import QtCore, QtGui
import pytest

from openlp.core.ui.fluenticons import fluent_icon, service_icon
from openlp.core.ui.icons import UiIcons


@pytest.mark.parametrize('dark', [False, True])
def test_catalogue_renders(settings, dark):
    """Every mapped Fluent glyph must render visible pixels, without a fallback."""
    with patch('openlp.core.ui.icons.is_ui_theme_dark', return_value=dark):
        icons = object.__new__(UiIcons)
        icons.__init__()
    for name, spec in icons._icon_list.items():
        if not spec['icon'].startswith('ic_fluent_'):
            assert spec['icon'] in {'mdi.projector', 'mdi.copyright', 'op.live-logo'}
            continue
        icon = fluent_icon(spec['icon'])
        for size in (16, 24, 48):
            image = icon.pixmap(size, size).toImage()
            assert any(image.pixelColor(x, y).alpha() for x in range(size) for y in range(size)), name


@pytest.mark.parametrize('mode,state,color', [
    (QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off, 'red'),
    (QtGui.QIcon.Mode.Disabled, QtGui.QIcon.State.Off, 'blue'),
    (QtGui.QIcon.Mode.Active, QtGui.QIcon.State.Off, 'green'),
    (QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On, 'white'),
])
def test_mode_and_state_colours(settings, mode, state, color):
    """Disabled, active and checked actions keep their requested colours."""
    icon = fluent_icon('ic_fluent_add_24_regular', color='red', color_disabled='blue',
                       color_off_active='green', color_on='white')
    image = icon.pixmap(24, 24, mode, state).toImage()
    pixels = [image.pixelColor(x, y) for x in range(24) for y in range(24)
              if image.pixelColor(x, y).alpha() > 200]
    assert pixels
    assert all(pixel.name() == QtGui.QColor(color).name() for pixel in pixels)


@pytest.mark.parametrize('theme', [fluentqt.Theme.Light, fluentqt.Theme.Dark])
@pytest.mark.parametrize('plugin,token', [
    ('songs', 'systemCaution'), ('bibles', 'systemSuccess'), ('presentations', 'purple'),
    ('images', 'systemInfo'), ('media', 'systemCritical'), ('custom', 'orange')
])
def test_service_icon_uses_fluent_theme_tokens(qapp, theme, plugin, token):
    """Service colours follow Fluent tokens in both appearances and preserve scalable glyphs."""
    previous = fluentqt.current_theme()
    try:
        fluentqt.set_theme(theme)
        host = fluentqt.FluentWidget()
        colors = host.theme_tokens().colors
        expected = (colors.charts[11 if theme == fluentqt.Theme.Dark else 6] if token == 'purple'
                    else colors.charts[6 if theme == fluentqt.Theme.Dark else 11] if token == 'orange'
                    else getattr(colors, token))
        original = fluent_icon('ic_fluent_add_24_regular')
        icon = service_icon(original, plugin)
        assert icon.name() == original.name()
        for mode in (QtGui.QIcon.Mode.Normal, QtGui.QIcon.Mode.Disabled):
            image = icon.pixmap(48, 48, mode).toImage()
            reference = fluent_icon(original.name(), color=expected, color_disabled=colors.textDisabled)
            assert image == reference.pixmap(48, 48, mode).toImage()
            assert any(image.pixelColor(x, y).alpha() for x in range(48) for y in range(48))
    finally:
        fluentqt.set_theme(previous)


def test_service_icon_preserves_raster_alpha_and_dpr(qapp):
    pixmap = QtGui.QPixmap(80, 80)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.fillRect(20, 20, 40, 40, QtGui.QColor('white'))
    painter.end()
    icon = service_icon(QtGui.QIcon(pixmap), 'songs')
    image = icon.pixmap(QtCore.QSize(40, 40), 2).toImage()
    assert image.devicePixelRatio() == 2
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(40, 40).alpha() == 255
    assert image.pixelColor(40, 40).name() == fluentqt.FluentWidget().theme_tokens().colors.systemCaution.name()


def test_service_icon_preserves_unknown_plugin_and_null_icons(qapp):
    original = fluent_icon('ic_fluent_add_24_regular')
    assert service_icon(original, 'unknown').cacheKey() == original.cacheKey()
    assert service_icon(QtGui.QIcon(), 'songs').isNull()


@pytest.mark.parametrize('plugin', ['songs', 'bibles', 'presentations', 'images', 'media', 'custom'])
def test_service_and_library_share_icon_colours(qapp, plugin):
    from types import SimpleNamespace
    from openlp.core.lib.mediamanageritem import MediaManagerItem
    from openlp.core.ui.servicemanager import ServiceManager

    original = fluent_icon('ic_fluent_add_24_regular')
    library = SimpleNamespace(plugin=SimpleNamespace(name=plugin, icon=original))
    library_icon = MediaManagerItem.get_library_tab_icon(library)
    item = SimpleNamespace(name=plugin)
    service = ServiceManager._create_colored_service_icon(None, original, item)
    assert library_icon.pixmap(32, 32).toImage() == service.pixmap(32, 32).toImage()
