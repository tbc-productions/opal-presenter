"""Verify Fluent catalogue coverage and Qt icon rendering states."""
from unittest.mock import patch

from PySide6 import QtGui
import pytest

from openlp.core.ui.fluenticons import fluent_icon
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
