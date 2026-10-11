"""Round-trip designs through song XML and custom-slide XML, without source images."""
import base64
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from PySide6 import QtCore, QtGui
from lxml import etree

from opal.core.display.screens import Screen, ScreenList
from opal.core.lib.slidedesign import apply_design, image_to_png_uri, normalise_design, package_design
from opal.core.lib.theme import Theme
from opal.plugins.custom.lib.customxmlhandler import CustomXML
from opal.plugins.songs.lib.db import Song
from opal.plugins.songs.lib.openlyricsxml import OpenLyrics, SongXML, DESIGN_NAMESPACE


def test_song_xml_embeds_images_and_base_theme(settings, registry, monkeypatch, tmp_path):
    monkeypatch.setattr(ScreenList(), 'screens', [Screen(0, QtCore.QRect(0, 0, 1920, 1080), is_primary=True)])
    path = tmp_path / 'background.png'
    image = QtGui.QImage(20, 10, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor('#123456'))
    assert image.save(str(path))
    uri, _ = image_to_png_uri(path)
    theme_uri = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    theme = Theme()
    theme.background_type = 'image'
    theme.background_filename = path
    theme.font_main_size = 48
    theme.font_main_color = '#abcdef'
    manager = MagicMock()
    manager.get_theme_data.return_value = theme
    registry.register('theme_manager', manager)
    lyrics = SongXML()
    lyrics.add_verse_to_lyrics('v', '1', 'Amazing grace\nHow sweet the sound')
    design = {'version': 1, 'canvas_width': 1920, 'canvas_height': 1080,
              'hidden_footers': ['v1:0:0'],
              'lyrics': {'x': 20, 'outline': True, 'outline_width': 2, 'shadow_x': -8},
              'order': ['lyrics', 'image-1'], 'elements': [
                  {'id': 'image-1', 'kind': 'image', 'src': uri, 'x': 5, 'y': 5, 'width': 20, 'height': 20,
                   'shadow': True, 'flip_horizontal': True}]}
    design['background'] = {'type': 'gradient', 'colour': '#123456', 'end_colour': '#654321',
                            'image': uri, 'image_opacity': 42}
    song = Song(title='Amazing Grace', lyrics=lyrics.extract_xml().decode(), last_modified=datetime(2026, 10, 4),
                slide_design=json.dumps(design), theme_name='Original theme')
    handler = OpenLyrics(MagicMock())
    exported = handler.song_to_xml(song)
    root = etree.fromstring(exported.encode() if isinstance(exported, str) else exported)
    stored = json.loads(root.find('{' + DESIGN_NAMESPACE + '}design').text)
    assert stored['theme']['background_filename'] == theme_uri
    assert str(path) not in (exported if isinstance(exported, str) else exported.decode())
    assert 'theme' not in json.loads(song.slide_design), 'Export must not freeze the library theme'
    path.unlink()
    with patch('opal.plugins.songs.lib.openlyricsxml.clean_song'):
        imported = handler.xml_to_song(exported)
    restored = normalise_design(imported.slide_design)
    assert restored['elements'][0]['src'] == uri
    assert restored['canvas_width'] == 1920
    assert restored['hidden_footers'] == ['v1:0:0']
    assert restored['order'] == ['lyrics', 'image-1']
    assert restored['lyrics']['outline_width'] == 2
    assert restored['lyrics']['shadow_x'] == -8
    assert restored['elements'][0]['shadow'] is True
    assert restored['elements'][0]['flip_horizontal'] is True
    assert restored['background']['image'] == uri
    assert restored['background']['image_opacity'] == 42
    assert 'Amazing grace' in imported.lyrics
    rendered_theme = apply_design(Theme(), restored, QtCore.QSize(1280, 720))
    assert rendered_theme.background_type == 'gradient'
    assert rendered_theme.background_start_color == '#123456'
    assert rendered_theme.song_design['background']['image'] == uri
    assert rendered_theme.font_main_x == 256
    assert rendered_theme.font_main_size == 32
    assert rendered_theme.font_main_color == '#abcdef'


def test_custom_xml_retains_design_with_and_without_title():
    custom = CustomXML()
    custom.add_verse_to_lyrics('custom', 1, 'Welcome')
    custom.add_title_and_credit('Welcome', 'Church')
    custom.set_design({'version': 1, 'canvas_width': 1440, 'canvas_height': 1080,
                       'hidden_footers': ['custom-1:0:0'], 'lyrics': {'x': 12}, 'order': ['lyrics', 'box'],
                       'background': {'type': 'solid', 'colour': '#abcdef',
                                      'image': 'data:image/png;base64,AAAA', 'image_opacity': 30},
                       'elements': [{'id': 'box', 'kind': 'rectangle', 'outline': True,
                                     'outline_width': 4, 'shadow': True, 'flip_vertical': True}]})
    for include_title in (False, True):
        restored = CustomXML(custom.extract_xml(include_title).decode())
        assert restored.get_design()['canvas_width'] == 1440
        assert restored.get_design()['hidden_footers'] == ['custom-1:0:0']
        assert restored.get_design()['lyrics']['x'] == 12
        assert restored.get_design()['elements'][0]['outline_width'] == 4
        assert restored.get_design()['elements'][0]['shadow'] is True
        assert restored.get_design()['elements'][0]['flip_vertical'] is True
        assert restored.get_design()['order'] == ['lyrics', 'box']
        assert restored.get_design()['background']['image_opacity'] == 30
        assert restored.get_verses()[0][1] == 'Welcome'
    restored.set_design({})
    assert restored.get_design() == {}


def test_embedded_theme_rejects_imported_file_or_network_references():
    for path in ('file:///private/secret.png', 'https://example.com/image.png'):
        value = {'version': 1, 'lyrics': {'x': 5}, 'theme': {
            'background_type': 'image', 'background_filename': path}}
        assert 'theme' not in normalise_design(value)


def test_reexport_of_imported_design_preserves_embedded_theme():
    original = {'version': 1, 'lyrics': {}, 'elements': [], 'theme': {
        'background_type': 'solid', 'background_color': '#123456', 'font_main_name': 'Arial'}}
    assert package_design(original, None) == normalise_design(original)
