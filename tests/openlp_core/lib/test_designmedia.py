"""Designer assets remain portable without bloating XML or trusting imported paths."""
import base64
import hashlib
import json
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui

from openlp.core.lib.designmedia import (
    EMBED_LIMIT, cache_media, media_to_source, media_references, resolve_media, restore_media, valid_media_source,
    write_media
)
from openlp.core.lib.itemexport import write_xml_package
from openlp.core.lib.slidedesign import apply_design, normalise_design
from openlp.core.lib.theme import Theme
from openlp.core.ui.thememanager import ThemeManager


@pytest.fixture
def assets(tmp_path):
    screens = MagicMock()
    screens.current.display_geometry = QtCore.QRect(0, 0, 1920, 1080)
    with patch('openlp.core.lib.designmedia.asset_root', return_value=tmp_path / 'managed'), \
            patch('openlp.core.lib.theme.ScreenList', return_value=screens):
        yield tmp_path


def image_file(path, large=False):
    image = QtGui.QImage(120, 60, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('#315efb'))
    assert image.save(str(path))
    if large:
        with path.open('ab') as output:
            output.write(b'\0' * (EMBED_LIMIT - path.stat().st_size))
    return path


def test_small_media_preserves_original_bytes_and_dimensions(assets):
    path = image_file(assets / 'photo.jpg')
    source, size = media_to_source(path)
    assert source.startswith('data:image/jpeg;base64,')
    assert base64.b64decode(source.split(',', 1)[1]) == path.read_bytes()
    assert size == QtCore.QSize(120, 60)
    assert valid_media_source(source, 'image')


@pytest.mark.parametrize('large', [False, True])
def test_original_jpeg_orientation_matches_designer_and_presentation_export(assets, large):
    from PIL import Image
    from openlp.core.lib.presentationexport import _load_image
    path = assets / 'portrait.jpg'
    image = Image.new('RGB', (120, 60), 'blue')
    metadata = image.getexif()
    metadata[274] = 6
    image.save(path, exif=metadata)
    if large:
        with path.open('ab') as output:
            output.write(b'\0' * EMBED_LIMIT)
    source, size = media_to_source(path)
    assert size == QtCore.QSize(60, 120)
    assert _load_image(source).size() == size


def test_threshold_uses_original_size_and_retains_large_media_after_source_deleted(assets):
    path = image_file(assets / 'photo.png', large=True)
    original = path.read_bytes()
    source, size = media_to_source(path)
    assert source.startswith('assets/')
    assert size == QtCore.QSize(120, 60)
    path.unlink()
    assert resolve_media(source).read_bytes() == original
    assert normalise_design({'version': 1, 'elements': [{'id': 'photo', 'kind': 'image', 'src': source}]})


def test_repeated_assets_in_layouts_are_packaged_once_and_restored_permanently(assets):
    reference = cache_media(image_file(assets / 'photo.png', large=True))
    value = {'masters': {'one': {'background': {'image': reference}}},
             'overrides': {'two': {'elements': [{'src': reference}]}}}
    path = assets / 'package.osz'
    with zipfile.ZipFile(path, 'w') as archive:
        write_media(archive, value)
        write_media(archive, value)
        assert archive.namelist() == [reference]
    managed = resolve_media(reference)
    original = managed.read_bytes()
    managed.unlink()
    with zipfile.ZipFile(path) as archive:
        restore_media(value, archive=archive)
    path.unlink()
    assert managed.read_bytes() == original


def test_tampered_asset_is_rejected_without_retaining_a_partial_file(assets):
    reference = 'assets/' + 'a' * 64 + '.mp4'
    with zipfile.ZipFile(assets / 'tampered.osz', 'w') as archive:
        archive.writestr(reference, b'wrong content')
    with zipfile.ZipFile(assets / 'tampered.osz') as archive, pytest.raises(ValueError, match='does not match'):
        restore_media({'src': reference}, archive=archive)
    assert not resolve_media(reference).exists()
    assert not list((assets / 'managed' / 'assets').iterdir())


@pytest.mark.parametrize('source', ['file:///private/secret.png', 'https://example.com/photo.jpg',
                                    '../assets/' + 'a' * 64 + '.png', 'assets/../secret.png',
                                    'data:image/svg+xml;base64,AAAA', 'assets/' + 'a' * 64 + '.html'])
def test_imported_media_cannot_reference_arbitrary_files_or_active_content(source):
    assert not valid_media_source(source)
    assert not media_references({'src': source})
    assert not normalise_design({'version': 1, 'elements': [{'id': 'bad', 'kind': 'image', 'src': source}]})


def test_xml_archive_contains_design_and_original_media(assets):
    reference = cache_media(image_file(assets / 'large.png', large=True))
    design = {'version': 1, 'background': {'type': 'solid', 'image': reference}}
    xml = '<song xmlns="http://openlyrics.info/namespace/2009/song"><design xmlns="https://openlp.org/ns/slide-design/1">' + json.dumps(design) + '</design></song>'
    path = assets / 'Song.opal-song'
    write_xml_package(path, xml)
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == {'manifest.json', 'song.xml', reference}
        assert archive.read(reference) == resolve_media(reference).read_bytes()
        assert reference.encode() in archive.read('song.xml')


def test_runtime_media_resolution_does_not_mutate_saved_design(assets):
    reference = cache_media(image_file(assets / 'large.png', large=True))
    design = {'version': 1, 'elements': [{'id': 'picture', 'kind': 'image', 'src': reference}]}
    result = apply_design(Theme(), design, QtCore.QSize(1920, 1080))
    assert result.song_design['elements'][0]['src'] == resolve_media(reference).as_uri()
    assert design['elements'][0]['src'] == reference


def test_video_sources_follow_same_embedding_and_archive_rules(assets):
    path = assets / 'clip.mp4'
    path.write_bytes(b'video')
    source, _ = media_to_source(path)
    assert source.startswith('data:video/mp4;base64,')
    assert valid_media_source(source, 'video')
    assert not valid_media_source(source, 'image')
    path.write_bytes(b'v' * EMBED_LIMIT)
    source, _ = media_to_source(path)
    assert source == f'assets/{hashlib.sha256(path.read_bytes()).hexdigest()}.mp4'
    design = normalise_design({'version': 1, 'elements': [{'id': 'clip', 'kind': 'video', 'src': source}]})
    assert design['elements'][0]['kind'] == 'video'


def test_theme_embeds_small_original_and_reloads_it_as_a_native_media_path(assets):
    path = image_file(assets / 'background.jpg')
    original = path.read_bytes()
    theme = Theme()
    theme.background_type = 'image'
    theme.background_filename = path
    theme.background_source = path
    encoded = theme.export_theme()
    assert json.loads(encoded)['background_filename'].startswith('data:image/jpeg;base64,')
    assert json.loads(encoded)['background_source'] is None
    path.unlink()
    restored = Theme()
    restored.load_theme(encoded)
    assert restored.background_filename.read_bytes() == original


@pytest.mark.parametrize('large', [False, True])
def test_theme_archive_inlines_small_backgrounds_and_bundles_large_ones(assets, large):
    from types import SimpleNamespace
    theme_directory = assets / 'themes' / 'Test'
    theme_directory.mkdir(parents=True)
    path = image_file(theme_directory / 'background.png', large=large)
    theme = Theme()
    theme.theme_name = 'Test'
    theme.background_type = 'image'
    theme.background_filename = path
    theme.background_source = path
    (theme_directory / 'Test.json').write_text(theme.export_theme(assets / 'themes'))
    manager = SimpleNamespace(theme_path=assets / 'themes')
    target = assets / 'Test.opal-theme'
    assert ThemeManager._export_theme(manager, target, 'Test')
    with zipfile.ZipFile(target) as archive:
        descriptor = json.loads(archive.read('Test/Test.json'))
        assert str(descriptor['background_filename']).startswith('data:') != large
        assert len(media_references(descriptor)) == (1 if large else 0)
        assert set(archive.namelist()) == {'manifest.json', 'Test/Test.json'} | media_references(descriptor)
        if large:
            reference = descriptor['background_filename']
            resolve_media(reference).unlink()
            restore_media(descriptor, archive=archive)
            assert resolve_media(reference).read_bytes() == path.read_bytes()


def test_legacy_oversized_inline_images_are_packaged_without_changing_the_saved_design(assets):
    from openlp.core.lib.slidedesign import package_design
    path = image_file(assets / 'legacy.png', large=True)
    source = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    design = {'version': 1, 'elements': [{'id': 'photo', 'kind': 'image', 'src': source}]}
    exported = package_design(design, None)
    assert exported['elements'][0]['src'].startswith('assets/')
    assert design['elements'][0]['src'] == source


def test_item_archive_restores_large_assets_before_temporary_service_files_are_removed(assets):
    from openlp.core.lib.itemexport import write_item_service
    from openlp.core.lib.serviceitem import ServiceItem
    reference = cache_media(image_file(assets / 'photo.png', large=True))
    design = {'version': 1, 'elements': [{'id': 'photo', 'kind': 'image', 'src': reference}]}
    with patch('openlp.core.lib.serviceitem.UiIcons'):
        source_item = ServiceItem()
        source_item.add_from_text('Welcome')
        header = source_item.get_service_repr(False)
    header['header'].update(title='Welcome', name='custom', slide_design=design)
    exported = MagicMock()
    exported.get_service_repr.return_value = header
    archive_path = assets / 'Welcome.opal-slides'
    write_item_service(archive_path, exported)
    resolve_media(reference).unlink()
    extracted = assets / 'extracted'
    with zipfile.ZipFile(archive_path) as archive:
        service = json.loads(archive.read('service.json'))
        archive.extractall(extracted)
    with patch('openlp.core.lib.serviceitem.UiIcons'):
        item = ServiceItem()
    with patch.object(item, 'add_icon'), patch.object(item, '_create_slides'), \
            patch('openlp.core.lib.serviceitem.State') as state:
        state.return_value.check_preconditions.return_value = False
        item.set_from_service(service[1], path=extracted, version=3)
    import shutil
    shutil.rmtree(extracted)
    assert resolve_media(item.slide_design['elements'][0]['src']).is_file()


@pytest.mark.parametrize('suffix', ['.xml', '.osz', '.opal-song'])
def test_song_import_retains_media_from_xml_companions_or_an_archive(assets, suffix):
    from types import SimpleNamespace
    from openlp.plugins.songs.lib.importers.openlyrics import OpenLyricsImport
    reference = cache_media(image_file(assets / 'photo.png', large=True))
    design = {'version': 1, 'background': {'type': 'solid', 'image': reference}}
    xml = '<song xmlns="http://openlyrics.info/namespace/2009/song"><design xmlns="https://openlp.org/ns/slide-design/1">' + json.dumps(design) + '</design></song>'
    path = assets / ('Song' + suffix)
    if suffix in ('.xml', '.osz'):
        if suffix == '.osz':
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('song.xml', xml)
                write_media(archive, design)
        else:
            path.write_text(xml)
            (assets / reference).parent.mkdir(parents=True, exist_ok=True)
            (assets / reference).write_bytes(resolve_media(reference).read_bytes())
    else:
        write_xml_package(path, xml)
    resolve_media(reference).unlink()
    importer = SimpleNamespace(import_source=[path], stop_import_flag=False,
                               import_wizard=MagicMock(), open_lyrics=MagicMock(), log_error=MagicMock())
    OpenLyricsImport.do_import(importer)
    importer.log_error.assert_not_called()
    importer.open_lyrics.xml_to_song.assert_called_once()
    assert resolve_media(reference).is_file()


def test_failed_archive_export_preserves_existing_destination(assets):
    reference = 'assets/' + 'c' * 64 + '.png'
    xml = '<song xmlns="http://openlyrics.info/namespace/2009/song"><design xmlns="https://openlp.org/ns/slide-design/1">' + json.dumps(
        {'version': 1, 'elements': [{'id': 'picture', 'kind': 'image', 'src': reference}]}) + '</design></song>'
    path = assets / 'Song.opal-song'
    path.write_bytes(b'previous export')
    with pytest.raises(OSError):
        write_xml_package(path, xml)
    assert path.read_bytes() == b'previous export'
    assert sorted(item.name for item in assets.iterdir()) == ['Song.opal-song']


@pytest.mark.parametrize('kind', ['image', 'video'])
def test_theme_retains_original_and_friendly_label_after_library_source_is_deleted(assets, kind):
    from openlp.core.lib.designmedia import media_label
    source = image_file(assets / 'Church background.png') if kind == 'image' else assets / 'Church background.mp4'
    if kind == 'video':
        source.write_bytes(b'original video')
    original = source.read_bytes()
    theme = Theme()
    theme.theme_name = 'Sunday'
    theme.background_type = kind
    theme.background_filename = source
    manager = MagicMock(theme_path=assets / 'themes', old_background_image_path=None)
    ThemeManager.save_theme(manager, theme)
    source.unlink()
    assert theme.background_filename.read_bytes() == original
    assert media_label(theme.background_filename) == source.name
    descriptor = (manager.theme_path / 'Sunday' / 'Sunday.json').read_text()
    reloaded = Theme()
    reloaded.load_theme(descriptor)
    assert reloaded.background_filename.read_bytes() == original
    assert media_label(reloaded.background_filename) == source.name


def test_html_video_background_does_not_start_native_media_but_linked_audio_still_does():
    from openlp.core.lib.serviceitem import ServiceItem
    from openlp.core.lib import ItemCapabilities
    item = MagicMock()
    capabilities = {ItemCapabilities.HasBackgroundVideo}
    item.is_capable.side_effect = lambda capability: capability in capabilities
    assert not ServiceItem.requires_media(item)
    capabilities.add(ItemCapabilities.HasBackgroundAudio)
    assert ServiceItem.requires_media(item)
    capabilities.clear()
    capabilities.add(ItemCapabilities.HasBackgroundStream)
    assert ServiceItem.requires_media(item)
