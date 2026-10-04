"""Regression tests for portable designs and non-destructive theme overrides."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSize

from openlp.core.lib.slidedesign import apply_design, normalise_design
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.common.enum import ServiceItemType


DESIGN = {'version': 1, 'canvas_height': 1080, 'lyrics': {'x': 10, 'width': 80, 'font_size': 48},
          'elements': [{'id': 'shape-1', 'kind': 'rectangle', 'x': 5, 'y': 20, 'width': 90,
                        'height': 40, 'fill': '#123456'}]}


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
