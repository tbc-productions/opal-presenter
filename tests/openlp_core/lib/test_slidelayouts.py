"""Master layouts remain portable and editable independently of slide overrides."""
import copy
import json
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QRect, QSize

from openlp.core.lib.slidedesign import normalise_design, remap_custom_footers
from openlp.core.lib.slidelayouts import slide_design, set_slide_design


def document():
    return normalise_design({'version': 1, 'masters': {'welcome': {'name': 'Welcome', 'design': {
        'version': 1, 'canvas_width': 1920, 'canvas_height': 1080, 'lyrics': {'font_size': 48},
        'elements': [{'id': 'heading', 'kind': 'text', 'text': 'Welcome', 'x': 20, 'font_size': 36}]}}},
        'assignments': {'custom-1:0:0': 'welcome', 'custom-2:0:0': 'welcome'}})


def test_master_updates_preserve_only_the_properties_changed_on_a_slide():
    source = document()
    edited = slide_design(source, 'custom-1:0:0')
    edited['elements'][0]['text'] = 'Good morning'
    source = set_slide_design(source, 'custom-1:0:0', edited)
    source['masters']['welcome']['design']['elements'][0].update(x=35, font_size=60)
    first = slide_design(source, 'custom-1:0:0')['elements'][0]
    second = slide_design(source, 'custom-2:0:0')['elements'][0]
    assert first['text'] == 'Good morning'
    assert second['text'] == 'Welcome'
    assert first['x'] == second['x'] == 35
    assert first['font_size'] == second['font_size'] == 60
    source['overrides'].pop('custom-1:0:0')
    assert slide_design(source, 'custom-1:0:0') == slide_design(source, 'custom-2:0:0')


def test_local_layer_additions_deletions_and_master_additions_are_preserved():
    source = document()
    edited = slide_design(source, 'custom-1:0:0')
    edited['elements'] = [{'id': 'local', 'kind': 'rectangle', 'fill': '#123456'}]
    source = set_slide_design(source, 'custom-1:0:0', edited)
    source['masters']['welcome']['design']['elements'].append({'id': 'new', 'kind': 'ellipse'})
    assert [element['id'] for element in slide_design(source, 'custom-1:0:0')['elements']] == ['new', 'local']
    assert [element['id'] for element in slide_design(source, 'custom-2:0:0')['elements']] == ['heading', 'new']


def test_layouts_and_overrides_round_trip_and_follow_custom_slide_insertions():
    source = document()
    edited = slide_design(source, 'custom-1:0:0')
    edited['lyrics']['font_size'] = 72
    source = set_slide_design(source, 'custom-1:0:0', edited)
    before = copy.deepcopy(source)
    restored = normalise_design(json.loads(json.dumps(source)))
    assert restored == source
    moved = remap_custom_footers(restored, ['First', 'Second'], ['New', 'First', 'Second'])
    assert moved['assignments'] == {'custom-2:0:0': 'welcome', 'custom-3:0:0': 'welcome'}
    assert slide_design(moved, 'custom-2:0:0')['lyrics']['font_size'] == 72
    assert source == before


def test_master_validation_rejects_external_images_and_recursive_documents():
    source = document()
    master = source['masters']['welcome']['design']
    master['masters'] = {'recursive': {'name': 'Nested', 'design': {'version': 1}}}
    master['elements'].append({'id': 'unsafe', 'kind': 'image', 'src': '/private/image.png'})
    result = normalise_design(source)
    assert 'masters' not in result['masters']['welcome']['design']
    assert len(result['masters']['welcome']['design']['elements']) == 1


def test_assigned_layouts_reach_live_frames_and_presentation_exports(settings, registry):
    from openlp.core.lib.theme import Theme
    from openlp.core.lib.serviceitem import ServiceItem
    from openlp.core.lib.presentationexport import service_pages

    with patch('openlp.core.lib.theme.ScreenList') as screens:
        screens.return_value.current.display_geometry = QRect(0, 0, 1920, 1080)
        theme = Theme()
    manager = MagicMock()
    manager.get_theme_data.return_value = theme
    registry.register('theme_manager', manager)
    renderer = MagicMock()
    renderer.format_slide.side_effect = lambda text, item: [text]
    registry.register('renderer', renderer)
    item = ServiceItem()
    item.slide_design = document()
    local = slide_design(item.slide_design, 'custom-1:0:0')
    local['lyrics']['font_size'] = 72
    item.slide_design = set_slide_design(item.slide_design, 'custom-1:0:0', local)
    item.add_from_text('First')
    item.add_from_text('Second')
    with patch('openlp.core.lib.slidedesign.ScreenList') as screens:
        screens.return_value.current.display_geometry.size.return_value = QSize(1920, 1080)
        item._create_slides()
        frames = item.rendered_slides
        assert [frame['theme']['font_main_size'] for frame in frames] == [72, 48]
        assert frames[0]['theme']['song_design']['elements'][0]['text'] == 'Welcome'
        pages = service_pages([item])
        assert [page.theme.font_main_size for page in pages] == [72, 48]


def test_custom_xml_retains_named_masters_assignments_and_local_images():
    from openlp.plugins.custom.lib.customxmlhandler import CustomXML

    source = document()
    source['custom_layout_name'] = 'Opening slides'
    source['background_filters'] = {'sepia': 50}
    local = slide_design(source, 'custom-1:0:0')
    local['elements'].append({'id': 'photo', 'kind': 'image', 'src': 'data:image/png;base64,AAAA',
                              'filters': {'blur': 4, 'brightness': 80}})
    source = set_slide_design(source, 'custom-1:0:0', local)
    xml = CustomXML()
    xml.add_verse_to_lyrics('custom', 1, 'Welcome')
    xml.set_design(source)
    restored = CustomXML(xml.extract_xml().decode('utf-8'))
    assert restored.get_design() == source


def test_default_layout_is_theme_without_discarding_saved_shared_designs():
    from openlp.core.lib.slidelayouts import layout_for_slide
    assert layout_for_slide({}, 'v1:0:0') == 'theme'
    source = set_slide_design({}, 'v1:0:0', {'version': 1, 'lyrics': {'x': 20}})
    assert layout_for_slide(source, 'v1:0:0') == 'theme'
    assert slide_design(source, 'v1:0:0')['lyrics']['x'] == 20
    assert slide_design(source, 'v2:0:0') == {}
    legacy = {'version': 1, 'lyrics': {'font_size': 60}}
    assert layout_for_slide(legacy, 'v1:0:0') == 'default'
    assert slide_design(legacy, 'v1:0:0')['lyrics']['font_size'] == 60
