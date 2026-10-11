"""Library copies retain records, media paths and originals, including legacy databases."""
import json
import shutil
import sqlite3
from contextlib import closing, nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest

from openlp.core.common.json import OpenLPJSONDecoder, OpenLPJSONEncoder
from openlp.core.lib.opal_libraryimport import copy_opal_library


@pytest.fixture
def opal_source(tmp_path):
    opal_path = tmp_path / 'source'
    (opal_path / 'songs').mkdir(parents=True)
    shutil.copyfile(Path('tests/resources/songs/openlp/songs-2.4.6.sqlite'), opal_path / 'songs/songs.sqlite')
    with sqlite3.connect(opal_path / 'songs/songs.sqlite') as opal_database:
        opal_database.execute('DELETE FROM media_files')
    return opal_path


def test_opal_copy_retains_library_and_rebases_media(opal_source, tmp_path):
    (opal_source / 'images').mkdir()
    (opal_source / 'images/photo.png').write_bytes(b'image')
    (opal_source / 'songs/audio.mp3').write_bytes(b'audio')
    (tmp_path / 'external.png').write_bytes(b'external image')
    (opal_source / 'designer/assets').mkdir(parents=True)
    (opal_source / 'designer/assets/video.mp4').write_bytes(b'video')
    (opal_source / 'themes/My theme').mkdir(parents=True)
    (opal_source / 'themes/My theme/My theme.json').write_text('{}')
    with sqlite3.connect(opal_source / 'images/images.sqlite') as opal_database:
        opal_database.execute('CREATE TABLE item (id INTEGER PRIMARY KEY, file_path TEXT)')
        opal_database.executemany('INSERT INTO item VALUES (?, ?)',
                                  [(1, str(opal_source / 'images/photo.png')), (2, str(tmp_path / 'external.png'))])
    with sqlite3.connect(opal_source / 'songs/songs.sqlite') as opal_database:
        opal_database.execute('ALTER TABLE media_files ADD COLUMN file_path TEXT')
        opal_database.execute('DELETE FROM media_files')
        opal_database.execute('INSERT INTO media_files (id, file_name, file_path, type) VALUES (1, ?, ?, ?)',
                              (str(opal_source / 'songs/audio.mp3'),
                               json.dumps(opal_source / 'songs/audio.mp3', cls=OpenLPJSONEncoder), 'audio'))
    opal_originals = {opal_file.relative_to(opal_source): opal_file.read_bytes()
                      for opal_file in opal_source.rglob('*') if opal_file.is_file()}
    opal_destination = copy_opal_library(opal_source, tmp_path / 'opal')
    with closing(sqlite3.connect(opal_destination / 'images/images.sqlite')) as opal_database:
        opal_paths = opal_database.execute('SELECT file_path FROM item ORDER BY id').fetchall()
        assert opal_paths[0][0] == str(opal_destination / 'images/photo.png')
        assert Path(opal_paths[1][0]).is_relative_to(opal_destination)
        assert Path(opal_paths[1][0]).read_bytes() == b'external image'
        assert (tmp_path / 'external.png').read_bytes() == b'external image'
    with closing(sqlite3.connect(opal_destination / 'songs/songs.sqlite')) as opal_database:
        opal_name, opal_path = opal_database.execute(
            'SELECT file_name, file_path FROM media_files WHERE id=1').fetchone()
        assert opal_name == str(opal_destination / 'songs/audio.mp3')
        assert json.loads(opal_path, cls=OpenLPJSONDecoder,
                          base_path=opal_destination) == opal_destination / 'songs/audio.mp3'
    assert (opal_destination / 'designer/assets/video.mp4').read_bytes() == b'video'
    assert (opal_destination / 'themes/My theme/My theme.json').read_text() == '{}'
    assert all((opal_source / opal_name).read_bytes() == opal_data
               for opal_name, opal_data in opal_originals.items())
    assert copy_opal_library(opal_source, tmp_path / 'opal') != opal_destination


@pytest.mark.parametrize('opal_failure', ['copy', 'corrupt', 'empty', 'future', 'wrong_schema', 'missing_file'])
def test_opal_failed_copy_is_removed(opal_source, tmp_path, opal_failure):
    if opal_failure == 'corrupt':
        (opal_source / 'songs/songs.sqlite').write_bytes(b'not a database')
    elif opal_failure == 'empty':
        (opal_source / 'songs/songs.sqlite').unlink()
    elif opal_failure == 'future':
        with sqlite3.connect(opal_source / 'songs/songs.sqlite') as opal_database:
            opal_database.execute("UPDATE metadata SET value='999' WHERE key='version'")
    elif opal_failure == 'wrong_schema':
        (opal_source / 'songs/songs.sqlite').unlink()
        with sqlite3.connect(opal_source / 'songs/songs.sqlite') as opal_database:
            opal_database.execute('CREATE TABLE unrelated (id INTEGER)')
    elif opal_failure == 'missing_file':
        with sqlite3.connect(opal_source / 'songs/songs.sqlite') as opal_database:
            opal_database.execute('INSERT INTO media_files (id, file_name, type) VALUES (1, ?, ?)',
                                  (str(tmp_path / 'missing.mp3'), 'audio'))
    opal_before = (opal_source / 'songs/songs.sqlite').read_bytes() if opal_failure != 'empty' else None
    with patch('openlp.core.lib.opal_libraryimport.shutil.copytree', side_effect=OSError('disk full')) \
            if opal_failure == 'copy' else nullcontext():
        with pytest.raises((OSError, ValueError, sqlite3.DatabaseError)):
            copy_opal_library(opal_source, tmp_path / 'opal')
    assert list((tmp_path / 'opal').iterdir()) == []
    if opal_before is not None:
        assert (opal_source / 'songs/songs.sqlite').read_bytes() == opal_before


def test_opal_rejects_recursive_copy(opal_source):
    with pytest.raises(ValueError, match='contain'):
        copy_opal_library(opal_source, opal_source / 'nested')
    assert not (opal_source / 'nested').exists()


def test_opal_copied_legacy_songs_upgrade(settings, opal_source, tmp_path):
    from openlp.core.db.manager import DBManager
    from openlp.plugins.songs.lib import upgrade
    from openlp.plugins.songs.lib.db import Song, init_schema
    opal_destination = copy_opal_library(opal_source, tmp_path / 'opal')
    settings.setValue('advanced/data path', opal_destination)
    opal_manager = DBManager('songs', init_schema, upgrade_mod=upgrade)
    try:
        assert opal_manager.get_all_objects(Song)[0].title
        with closing(sqlite3.connect(opal_destination / 'songs/songs.sqlite')) as opal_database:
            assert opal_database.execute("SELECT value FROM metadata WHERE key='version'").fetchone()[0] == \
                str(upgrade.__version__)
    finally:
        opal_manager.finalise()


def test_opal_copied_legacy_images_upgrade(settings, opal_source, tmp_path):
    from openlp.core.db.manager import DBManager
    from openlp.plugins.images.lib import upgrade
    from openlp.plugins.images.lib.db import Item, init_schema
    (opal_source / 'images').mkdir()
    opal_image = opal_source / 'images/photo.png'
    opal_image.write_bytes(b'image')
    shutil.copyfile(Path('tests/resources/images/image-v0.sqlite'), opal_source / 'images/images.sqlite')
    with sqlite3.connect(opal_source / 'images/images.sqlite') as opal_database:
        opal_database.execute('UPDATE image_filenames SET filename=?', (str(opal_image),))
    opal_destination = copy_opal_library(opal_source, tmp_path / 'opal')
    settings.setValue('advanced/data path', opal_destination)
    opal_manager = DBManager('images', init_schema, upgrade_mod=upgrade)
    try:
        opal_images = opal_manager.get_all_objects(Item)
        assert opal_images
        assert all(Path(opal_item.file_path) == opal_destination / 'images/photo.png' for opal_item in opal_images)
    finally:
        opal_manager.finalise()


@pytest.mark.parametrize('opal_format', ['string', 'absolute_json', 'relative_json'])
def test_opal_legacy_image_path_copy(opal_source, tmp_path, opal_format):
    (opal_source / 'images').mkdir()
    opal_path = opal_source / 'images/photo.png'
    opal_path.write_bytes(b'image')
    opal_value = str(opal_path) if opal_format == 'string' else json.dumps(
        opal_path, cls=OpenLPJSONEncoder, base_path=opal_source if opal_format == 'relative_json' else None)
    with sqlite3.connect(opal_source / 'images/images.sqlite') as opal_database:
        opal_column = 'filename' if opal_format == 'string' else 'file_path'
        opal_database.execute(f'CREATE TABLE image_filenames (id INTEGER PRIMARY KEY, {opal_column} TEXT)')
        opal_database.execute('INSERT INTO image_filenames VALUES (1, ?)', (opal_value,))
    opal_destination = copy_opal_library(opal_source, tmp_path / 'opal')
    with closing(sqlite3.connect(opal_destination / 'images/images.sqlite')) as opal_database:
        opal_value = opal_database.execute(f'SELECT {opal_column} FROM image_filenames').fetchone()[0]
    opal_result = Path(opal_value) if opal_format == 'string' else json.loads(
        opal_value, cls=OpenLPJSONDecoder, base_path=opal_destination)
    assert opal_result == opal_destination / 'images/photo.png'
    assert opal_result.read_bytes() == b'image'


@pytest.mark.parametrize('opal_format', ['json', 'xml'])
def test_opal_external_theme_background_is_copied(opal_source, tmp_path, opal_format):
    opal_external = tmp_path / 'background.png'
    opal_external.write_bytes(b'background')
    opal_theme_directory = opal_source / 'themes/My theme'
    opal_theme_directory.mkdir(parents=True)
    opal_descriptor = opal_theme_directory / f'My theme.{opal_format}'
    if opal_format == 'json':
        opal_descriptor.write_text(json.dumps({'background_type': 'image', 'background_filename': opal_external},
                                              cls=OpenLPJSONEncoder))
    else:
        opal_descriptor.write_text(f'<theme><background type="image"><filename>{opal_external}</filename>'
                                   '</background></theme>')
    opal_original = opal_descriptor.read_bytes()
    opal_destination = copy_opal_library(opal_source, tmp_path / 'opal')
    opal_copied = opal_destination / opal_descriptor.relative_to(opal_source)
    if opal_format == 'json':
        opal_background = json.loads(opal_copied.read_text(), cls=OpenLPJSONDecoder,
                                     base_path=opal_destination / 'themes')['background_filename']
    else:
        from xml.etree import ElementTree
        opal_background = Path(ElementTree.parse(opal_copied).findtext('background/filename'))
    opal_external.unlink()
    assert opal_background.is_relative_to(opal_destination)
    assert opal_background.read_bytes() == b'background'
    assert opal_descriptor.read_bytes() == opal_original
