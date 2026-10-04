"""Regression tests for portable designs and non-destructive theme overrides."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSize

from openlp.core.lib.slidedesign import apply_design, normalise_design, layer_order
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.common.enum import ServiceItemType


DESIGN = {'version': 1, 'canvas_height': 1080, 'lyrics': {'x': 10, 'width': 80, 'font_size': 48},
          'order': ['lyrics', 'shape-1'],
          'elements': [{'id': 'shape-1', 'kind': 'rectangle', 'x': 5, 'y': 20, 'width': 90,
                        'height': 40, 'fill': '#123456'}]}


def test_legacy_designs_keep_lyrics_above_decorations():
    legacy = copy.deepcopy(DESIGN)
    del legacy['order']
    assert layer_order(normalise_design(legacy)) == ['shape-1', 'lyrics']


@pytest.mark.parametrize('order', [['lyrics', 'missing', 'lyrics', {}, 3], None, 'lyrics'])
def test_layer_order_rejects_unknown_or_duplicate_ids_and_preserves_all_objects(order):
    result = normalise_design({**DESIGN, 'order': order})
    assert len(result['order']) == 2
    assert set(result['order']) == {'shape-1', 'lyrics'}


@pytest.mark.parametrize('value', [None, '', 'not json', [], {'version': 2}, {'version': 1, 'elements': None}])
def test_invalid_or_empty_design_inherits_theme(value):
    theme = SimpleNamespace()
    assert normalise_design(value) == {}
    assert apply_design(theme, value) is theme


def test_design_validation_rejects_external_images_and_clamps_values():
    source = copy.deepcopy(DESIGN)
    source['lyrics'].update(x=float('nan'), width=200, opacity=-10, colour='url(https://example.com)', unsafe='data')
    source['elements'].append({'id': 'remote-image', 'kind': 'image', 'src': 'https://example.com/a.png'})
    result = normalise_design(source)
    assert result['lyrics'] == {'x': 10, 'width': 100, 'opacity': 0, 'font_size': 48}
    assert len(result['elements']) == 1
    result['elements'][0]['fill'] = '#ffffff'
    assert source['elements'][0]['fill'] == '#123456'


def test_apply_design_scales_geometry_without_mutating_theme():
    theme = SimpleNamespace(font_main_x=20, font_main_width=1000, font_main_size=32, font_main_override=False)
    before = copy.deepcopy(theme.__dict__)
    result = apply_design(theme, DESIGN, QSize(1280, 720))
    assert theme.__dict__ == before
    assert result.font_main_x == 128
    assert result.font_main_width == 1024
    assert result.font_main_size == 32
    assert result.font_main_override is True
    assert result.song_design_output_height == 720


def test_service_header_round_trip_keeps_portable_design(settings):
    item = ServiceItem()
    item.service_item_type = ServiceItemType.Text
    item.slide_design = normalise_design(DESIGN)
    item.add_from_text('Lyrics', 'V1')
    with patch.object(item, 'get_theme_data', return_value=None):
        saved = json.loads(json.dumps(item.get_service_repr(False)))
    restored = ServiceItem()
    with patch('openlp.core.lib.serviceitem.State') as state, patch.object(restored, '_create_slides'):
        state.return_value.check_preconditions.return_value = False
        restored.set_from_service({'serviceitem': saved}, None)
    assert restored.slide_design == item.slide_design


def test_service_packages_base_theme_without_applying_canvas_fit_twice(settings, registry):
    from openlp.core.lib.theme import Theme

    with patch('openlp.core.lib.theme.ScreenList') as screens:
        from PySide6.QtCore import QRect
        screens.return_value.current.display_geometry = QRect(0, 0, 1440, 1080)
        theme = Theme()
    theme.font_main_x = 100
    theme.font_main_size = 48
    manager = MagicMock()
    manager.get_theme_data.return_value = theme
    registry.register('theme_manager', manager)
    item = ServiceItem()
    item.service_item_type = ServiceItemType.Text
    item.slide_design = {'version': 1, 'canvas_width': 1920, 'canvas_height': 1080,
                         'lyrics': {}, 'elements': []}
    with patch('openlp.core.lib.slidedesign.ScreenList') as screens:
        screens.return_value.current.display_geometry.size.return_value = QSize(1440, 1080)
        before = item.get_theme_data()
        saved = item.get_service_repr(False)['header']['slide_design']
        after = apply_design(theme, saved, QSize(1440, 1080))
    assert saved['theme']['font_main_x'] == 100
    assert saved['theme']['font_main_size'] == 48
    for part in ('main', 'footer'):
        for key in ('x', 'y', 'width', 'height', 'size'):
            assert getattr(after, f'font_{part}_{key}') == pytest.approx(getattr(before, f'font_{part}_{key}'))


def test_service_resolves_design_on_a_copy_of_the_selected_theme(settings, registry):
    manager = MagicMock()
    manager.get_theme_data.return_value = SimpleNamespace(background_type='solid', font_main_x=0)
    registry.register('theme_manager', manager)
    item = ServiceItem()
    item.slide_design = DESIGN
    with patch('openlp.core.lib.slidedesign.ScreenList') as screens:
        screens.return_value.current.display_geometry.size.return_value = QSize(1920, 1080)
        result = item.get_theme_data()
    assert result.font_main_x == 192
    assert manager.get_theme_data.return_value.font_main_x == 0


def test_background_only_design_applies_fill_on_a_theme_copy():
    theme = SimpleNamespace(background_type='image', background_filename='original.png')
    design = {'version': 1, 'background': {
        'type': 'gradient', 'colour': '#123456', 'end_colour': '#654321',
        'image': 'data:image/png;base64,AAAA', 'image_opacity': 35}}
    result = apply_design(theme, design, QSize(1920, 1080))
    assert result.background_type == 'gradient'
    assert result.background_start_color == '#123456'
    assert result.background_end_color == '#654321'
    assert result.background_filename is None
    assert result.song_design['background']['image_opacity'] == 35
    assert theme.background_filename == 'original.png'


@pytest.mark.parametrize('source', ['file:///private/test.png', 'https://example.com/image.png', 'javascript:alert(1)'])
def test_background_rejects_external_images_and_clamps_opacity(source):
    design = normalise_design({'version': 1, 'background': {
        'type': 'solid', 'colour': 'url(unsafe)', 'image': source, 'image_opacity': -20}})
    assert 'image' not in design['background']
    assert design['background']['colour'] == '#000000'
    assert design['background']['image_opacity'] == 0


def test_effects_validation_and_json_roundtrip():
    source = {'version': 1, 'lyrics': {'outline': False, 'shadow': True, 'shadow_x': -8, 'shadow_y': 12,
                                       'shadow_blur': 6, 'shadow_colour': '#123456', 'flip_horizontal': True},
              'elements': [{'id': 'shape', 'kind': 'rectangle', 'outline': True, 'outline_width': 3.5,
                            'outline_colour': '#abcdef', 'flip_vertical': True}]}
    design = normalise_design(source)
    assert normalise_design(json.dumps(design)) == design
    assert design['lyrics'] == source['lyrics']
    assert design['elements'][0]['outline_width'] == 3.5
    assert design['elements'][0]['flip_vertical'] is True
    invalid = normalise_design({'version': 1, 'lyrics': {
        'shadow_x': float('nan'), 'shadow_y': -500, 'outline_width': 1000, 'shadow': 'true',
        'outline_colour': 'red; display:none', 'flip_vertical': 'true'}})
    assert invalid['lyrics'] == {'shadow_x': 4, 'shadow_y': -100, 'outline_width': 40}


@pytest.mark.parametrize('width,height', [(1920, 1080), (1920, 1200), (2520, 1080), (1440, 1080), (1280, 720)])
def test_pixel_canvas_fits_uniformly_on_every_output_aspect(width, height):
    theme = SimpleNamespace(font_main_x=0, font_main_y=0, font_main_width=width, font_main_height=height,
                            font_main_size=40, font_footer_x=0, font_footer_y=height * .9,
                            font_footer_width=width, font_footer_height=height * .1, font_footer_size=12)
    design = {'version': 1, 'canvas_width': 1920, 'canvas_height': 1080,
              'lyrics': {'x': 10, 'y': 20, 'width': 80, 'height': 60, 'font_size': 40},
              'elements': [{'id': 'shape', 'kind': 'ellipse', 'x': 10, 'y': 20, 'width': 10, 'height': 10}]}
    original = copy.deepcopy(design)
    result = apply_design(theme, design, QSize(width, height))
    scale = min(width / 1920, height / 1080)
    left, top = (width - 1920 * scale) / 2, (height - 1080 * scale) / 2
    assert result.font_main_x == pytest.approx(left + 192 * scale)
    assert result.font_main_y == pytest.approx(top + 216 * scale)
    assert result.font_main_size == pytest.approx(40 * scale)
    element = result.song_design['elements'][0]
    assert element['width'] / 100 * width == pytest.approx(192 * scale)
    assert element['height'] / 100 * height == pytest.approx(108 * scale)
    assert result.song_design_output_height == pytest.approx(1080 * scale)
    assert design == original


def test_footer_only_design_and_pixel_dimensions_roundtrip():
    value = {'version': 1, 'canvas_width': 1440, 'canvas_height': 1080,
             'hidden_footers': ['v1:0:0', 'custom-2:0:1', 'invalid', {}, 'v1:0:0']}
    design = normalise_design(value)
    assert design['hidden_footers'] == ['v1:0:0', 'custom-2:0:1']
    assert normalise_design(json.dumps(design)) == design


def test_service_hides_only_the_selected_verse_page_footer(settings, registry):
    renderer = MagicMock()
    renderer.format_slide.return_value = ['Page one', 'Page two']
    registry.register('renderer', renderer)
    item = ServiceItem()
    item.name = 'songs'
    item.raw_footer = ['Credits']
    item.slide_design = normalise_design({'version': 1, 'hidden_footers': ['v1:0:1']})
    item.add_from_text('Verse', 'V1', metadata={'design_section': 'v1', 'design_split': 0})
    item.add_from_text('Chorus', 'C1', metadata={'design_section': 'c1', 'design_split': 0})
    assert [slide['footer'] for slide in item.rendered_slides] == ['Credits', '', 'Credits', 'Credits']


def test_custom_footer_flags_follow_insertions_edits_and_deletions():
    from openlp.core.lib.slidedesign import remap_custom_footers
    design = {'version': 1, 'hidden_footers': ['custom-1:0:0', 'custom-2:0:1', 'custom-3:0:0']}
    changed = remap_custom_footers(design, ['One', 'Two', 'Three'], ['New', 'One', 'Changed two', 'Three'])
    assert changed['hidden_footers'] == ['custom-2:0:0', 'custom-3:0:1', 'custom-4:0:0']
    changed = remap_custom_footers(changed, ['Changed two'], [], offset=2)
    assert changed['hidden_footers'] == ['custom-2:0:0', 'custom-3:0:0']
    assert design['hidden_footers'] == ['custom-1:0:0', 'custom-2:0:1', 'custom-3:0:0']


def test_pixel_canvas_accepts_one_pixel_textbox_and_imported_theme_scales_once():
    design = {'version': 1, 'canvas_width': 1920, 'canvas_height': 1080,
              'lyrics': {'width': 100 / 1920},
              'theme': {'background_type': 'solid', 'font_main_size': 48,
                        'display_size_width': 1920, 'display_size_height': 1080}}
    normalised = normalise_design(design)
    assert normalised['lyrics']['width'] == pytest.approx(100 / 1920)
    result = apply_design(SimpleNamespace(), design, QSize(1280, 720))
    assert result.font_main_size == 32
    assert result.font_main_width == pytest.approx(2 / 3)
