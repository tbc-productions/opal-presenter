"""Pixel checks for CSS effects baked into portable presentation images."""
import pytest
from PySide6 import QtGui

from openlp.core.lib.imagefilters import apply_filters, add_shadow


def _image(colour='#804020', size=20):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(colour))
    return image


@pytest.mark.parametrize('filters, expected', [
    ({'brightness': 50}, (64, 32, 16)),
    ({'contrast': 0}, (128, 128, 128)),
    ({'grayscale': 100}, (75, 75, 75)),
    ({'hue-rotate': 180}, (22, 86, 118)),
    ({'invert': 100}, (127, 191, 223)),
    ({'saturate': 0}, (75, 75, 75)),
    ({'sepia': 100}, (106, 94, 73)),
    # Input dictionary order must not change the display's fixed filter order.
    ({'invert': 100, 'brightness': 50}, (191, 223, 239)),
])
def test_colour_filters_match_css_matrices_and_preserve_alpha(filters, expected):
    source = _image('#80804020')

    result, padding = apply_filters(source, filters)

    assert result.pixelColor(10, 10).getRgb()[:3] == pytest.approx(expected, abs=1)
    assert result.pixelColor(10, 10).alpha() == 128
    assert padding == 0
    assert source.pixelColor(10, 10).getRgb() == (128, 64, 32, 128)


def test_blur_keeps_translucent_edges_coloured_and_scales_overflow():
    source = _image('#ff0000')

    result, padding = apply_filters(source, {'blur': 2}, scale=2, expand=True)
    cropped, cropped_padding = apply_filters(source, {'blur': 2}, scale=2)

    assert padding == 12
    assert result.size().width() == 44
    assert cropped.size() == source.size()
    assert cropped_padding == 0
    assert cropped == result.copy(padding, padding, source.width(), source.height())
    edge = result.pixelColor(padding - 1, padding + 10)
    assert 0 < edge.alpha() < 128
    assert edge.red() >= 250
    assert edge.green() == edge.blue() == 0


def test_unknown_and_neutral_filters_leave_pixels_unchanged():
    source = _image()
    result, padding = apply_filters(source, {'brightness': 100, 'blur': 0, 'unknown': 100})
    assert result == source
    assert padding == 0


def test_shadow_uses_filtered_alpha_with_symmetric_padding():
    source = _image('#ff0000')
    result, padding = add_shadow(source, {'shadow': True, 'shadow_x': 4, 'shadow_y': 0,
                                          'shadow_blur': 0, 'shadow_colour': '#00ff00'}, 1)
    assert padding == 4
    assert result.pixelColor(25, 14).getRgb() == (0, 255, 0, 255)
    assert result.pixelColor(14, 14).getRgb() == (255, 0, 0, 255)
