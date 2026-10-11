"""Copy an existing local library without overwriting either installation's data."""
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from importlib import import_module
from pathlib import Path
from tempfile import mkdtemp
from xml.etree import ElementTree

from opal.core.common.json import OpenLPJSONDecoder, OpenLPJSONEncoder


def copy_opal_library_file(opal_path, opal_source_path, opal_destination):
    """Keep linked files in the imported library, including files outside its data folder."""
    opal_path = (opal_source_path / opal_path).resolve()
    if not opal_path.is_file():
        raise FileNotFoundError(f'File not found: {opal_path}')
    if opal_path.is_relative_to(opal_source_path):
        opal_target = opal_destination / opal_path.relative_to(opal_source_path)
    else:
        opal_digest = hashlib.sha256(str(opal_path).encode()).hexdigest()
        opal_target = opal_destination / 'external' / opal_digest / opal_path.name
    if not opal_target.exists():
        opal_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(opal_path, opal_target)
    return opal_target


def copy_opal_library(opal_source_path, opal_destination_parent):
    """Return a separate data folder; remove incomplete copies on any failure."""
    opal_source_path = Path(opal_source_path).resolve()
    opal_destination_parent = Path(opal_destination_parent).resolve()
    if not opal_source_path.is_dir():
        raise ValueError('Select an existing data folder.')
    if opal_destination_parent == opal_source_path or opal_destination_parent.is_relative_to(opal_source_path):
        raise ValueError('The source folder cannot contain Opal Presenter storage.')
    opal_sections = ('songs', 'bibles', 'custom', 'images', 'media', 'presentations', 'themes', 'designer')
    if not any((opal_source_path / opal_section).is_dir() for opal_section in opal_sections):
        raise ValueError('This folder does not contain an OpenLP library.')
    opal_destination_parent.mkdir(parents=True, exist_ok=True)
    opal_destination = Path(mkdtemp(prefix='opal-library-', dir=opal_destination_parent))
    try:
        for opal_section in opal_sections:
            if (opal_source_path / opal_section).is_dir():
                shutil.copytree(opal_source_path / opal_section, opal_destination / opal_section)
        opal_has_library = any((opal_destination / 'themes').glob('*/*.xml')) or \
            any((opal_destination / 'themes').glob('*/*.json')) or \
            any((opal_destination / 'themes').glob('*.otz'))
        for opal_database in opal_destination.glob('*/*.sqlite'):
            with closing(sqlite3.connect(opal_database)) as opal_connection, opal_connection:
                if opal_connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError(f'The database is damaged: {opal_database.name}')
                opal_tables = {row[0] for row in opal_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'")}
                opal_expected = {
                    'songs': {'songs'}, 'custom': {'custom_slide'}, 'images': {'image_filenames', 'item'},
                    'media': {'item'}, 'presentations': {'item'}, 'bibles': {'book', 'verse'}
                }.get(opal_database.parent.name, set())
                if opal_tables & opal_expected:
                    opal_has_library = True
                elif opal_database.name == f'{opal_database.parent.name}.sqlite':
                    raise ValueError(f'Unrecognised library database: {opal_database.name}')
                if 'metadata' in opal_tables and opal_database.parent.name in ('songs', 'images', 'bibles'):
                    opal_version = opal_connection.execute(
                        'SELECT value FROM metadata WHERE key = ?', ('version',)).fetchone()
                    opal_upgrade = import_module(f'opal.plugins.{opal_database.parent.name}.lib.upgrade')
                    if opal_version and int(opal_version[0]) > opal_upgrade.__version__:
                        raise ValueError(f'The database uses a newer version: {opal_database.name}')
                for opal_table in opal_tables:
                    opal_quoted_table = '"' + opal_table.replace('"', '""') + '"'
                    opal_columns = {row[1] for row in opal_connection.execute(
                        f'PRAGMA table_info({opal_quoted_table})')}
                    for opal_column in opal_columns & {'file_path', 'file_name', 'filename'}:
                        for opal_row_id, opal_value in opal_connection.execute(
                                f'SELECT rowid, "{opal_column}" FROM {opal_quoted_table}').fetchall():
                            if not isinstance(opal_value, str) or not opal_value:
                                continue
                            try:
                                opal_decoded = json.loads(opal_value, cls=OpenLPJSONDecoder)
                            except (ValueError, TypeError):
                                opal_decoded = None
                            opal_path = opal_decoded if isinstance(opal_decoded, Path) else Path(opal_value)
                            opal_path = copy_opal_library_file(opal_path, opal_source_path, opal_destination)
                            opal_rebased = (json.dumps(opal_path, cls=OpenLPJSONEncoder, base_path=opal_destination)
                                            if isinstance(opal_decoded, Path) else str(opal_path))
                            opal_connection.execute(
                                f'UPDATE {opal_quoted_table} SET "{opal_column}" = ? WHERE rowid = ?',
                                (opal_rebased, opal_row_id))
        for opal_descriptor in (opal_destination / 'themes').glob('*/*.json'):
            opal_theme = json.loads(opal_descriptor.read_text(), cls=OpenLPJSONDecoder,
                                    base_path=opal_source_path / 'themes')
            if opal_theme.get('background_type') not in ('image', 'video'):
                continue
            opal_background = opal_theme.get('background_filename') or opal_theme.get('background_source')
            if not opal_background or isinstance(opal_background, str) and \
                    opal_background.startswith(('assets/', 'data:')):
                continue
            opal_theme['background_filename'] = copy_opal_library_file(
                opal_source_path / 'themes' / opal_background, opal_source_path, opal_destination)
            opal_theme['background_source'] = None
            opal_descriptor.write_text(json.dumps(opal_theme, cls=OpenLPJSONEncoder,
                                                  base_path=opal_destination / 'themes'))
        for opal_descriptor in (opal_destination / 'themes').glob('*/*.xml'):
            opal_theme = ElementTree.parse(opal_descriptor)
            opal_background = opal_theme.find('background/filename')
            if opal_background is not None and opal_background.text:
                opal_background.text = str(copy_opal_library_file(
                    opal_source_path / 'themes' / opal_descriptor.parent.name / opal_background.text,
                    opal_source_path, opal_destination))
                opal_theme.write(opal_descriptor, encoding='utf-8', xml_declaration=True)
        if not opal_has_library:
            raise ValueError('This folder does not contain a recognised library database or theme.')
        return opal_destination
    except Exception:
        shutil.rmtree(opal_destination)
        raise
