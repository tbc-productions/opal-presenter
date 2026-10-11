"""Use native Library formats and importers; keep all database access on the GUI thread."""
import zipfile
import json
import unicodedata
from pathlib import Path
from tempfile import NamedTemporaryFile

from lxml import etree
from PySide6 import QtCore

from opal.core.common import clean_filename
from opal.core.lib.designmedia import media_references, restore_media, valid_media_source, write_media
from opal.core.common.registry import Registry
from opal.core.lib.itemexport import write_xml_package, xml_design, export_archive
from opal.core.lib.nativefile import read_manifest, SYNC_NAMESPACE, LEGACY_SYNC_NAMESPACE
from opal.core.widgets import fluent as QtWidgets
from opal.core.widgets.views import remove_local_row
from opal.plugins.librarysync.lib.provider import CATEGORIES, SyncError, friendly_name


MAX_XML = 8 * 1024 * 1024
EXTENSION_CATEGORIES = ('images', 'media', 'presentations')
FILE_TYPES = {
    'images': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.webp', '.svg'},
    'presentations': {'.ppt', '.pptx', '.odp', '.pdf', '.key'},
    'media': {'.mp3', '.mp4', '.wav', '.ogg', '.ogv', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.m4a', '.flac', '.wmv'},
    'themes': {'.opal-theme', '.otz'},
}
THEME_TAG = '{' + SYNC_NAMESPACE + '}theme'
LEGACY_THEME_TAG = '{' + LEGACY_SYNC_NAMESPACE + '}theme'


def package_manifest(archive, file_type, required=False):
    try:
        return read_manifest(archive, file_type, required)
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        raise SyncError(str(error)) from error


def name_key(name):
    return unicodedata.normalize('NFKC', name).strip().casefold()


def duplicate_key(category, title, extension=''):
    """Files with different formats can share a title; editable Library items cannot."""
    return name_key(title), extension.casefold() if category in EXTENSION_CATEGORIES else ''


def local_item(category, plugin, title, extension=''):
    """Use saved records, including items outside the current filter/folder."""
    if category == 'themes':
        manager = Registry().get('theme_manager')
        # Thumbnail generation reloads the visible list later; a saved theme already reserves its name.
        names = set(manager.get_theme_names()) | {path.stem for path in manager.theme_path.glob('*/*.json')}
        records = [name for name in names if name_key(name) == name_key(title)]
    else:
        if category == 'songs':
            from opal.plugins.songs.lib.db import Song
            records = plugin.manager.get_all_objects(Song)
        elif category == 'custom':
            from opal.plugins.custom.lib.db import CustomSlide
            records = plugin.db_manager.get_all_objects(CustomSlide)
        else:
            records = plugin.media_item.manager.get_all_objects(plugin.media_item.item_class)
        records = [record for record in records if duplicate_key(
            category, friendly_name(record.name) if category in FILE_TYPES else record.title,
            Path(record.file_path).suffix if category in EXTENSION_CATEGORIES else '') ==
            duplicate_key(category, title, extension)]
    if len(records) > 1:
        raise SyncError('Several local items have this name. Rename them before downloading a replacement.')
    return records[0] if records else None


def item_category(item):
    suffix = Path(item.name).suffix.lower()
    if item.category in CATEGORIES:
        if (item.category in FILE_TYPES and suffix in FILE_TYPES[item.category]
                or item.category in ('songs', 'custom') and suffix in ('.xml', '.osz', '.opal-song' if item.category == 'songs' else '.opal-slides')):
            return item.category
        return ''
    return next((category for category, extensions in FILE_TYPES.items() if suffix in extensions), '')


def safe_name(name):
    """Remote display names must never become paths."""
    return (clean_filename(Path(name.replace('\\', '/')).name).strip(' .') or 'Item')[:220]


def safe_xml(data):
    if len(data) > MAX_XML or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise SyncError('The cloud XML contains unsafe declarations or is too large.')
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        root = etree.fromstring(data, parser)
        return root, etree.tostring(root, encoding='unicode')
    except etree.XMLSyntaxError as error:
        raise SyncError('The cloud item contains invalid XML.') from error


def read_xml_item(path):
    from opal.core.lib.itemexport import read_xml_package
    kind = 'song' if path.suffix.lower() == '.opal-song' else 'slides' if path.suffix.lower() == '.opal-slides' else None
    try:
        return read_xml_package(path, kind)
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        raise SyncError(str(error)) from error


def read_theme_item(path):
    """Only portable JSON themes and verified media can cross the cloud boundary."""
    from opal.core.lib.theme import Theme
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 2000 or sum(info.file_size for info in members) > 1024 * 1024 * 1024:
            raise SyncError('The cloud theme expands beyond the supported size.')
        manifest = package_manifest(archive, 'theme', required=path.suffix.lower() == '.opal-theme')
        descriptors = ([archive.getinfo(manifest['payload'])] if manifest else
                       [info for info in members if info.filename.lower().endswith('.json')])
        if len(descriptors) != 1 or descriptors[0].file_size > MAX_XML:
            raise SyncError('The cloud theme must contain one small JSON descriptor.')
        data = json.loads(archive.read(descriptors[0]))
        if not isinstance(data, dict) or not isinstance(data.get('theme_name'), str):
            raise SyncError('The cloud theme has invalid metadata.')
        # Theme.expand_json accepts arbitrary attributes; keep the existing theme schema only.
        allowed = Theme().__dict__
        data = {key: value for key, value in data.items() if key in allowed}
        background = data.get('background_filename')
        if background and not valid_media_source(background):
            raise SyncError('This theme must be exported again with a portable background.')
        data['background_source'] = None
        if data.get('background_type') == 'stream':
            raise SyncError('Remote streaming themes cannot be previewed or imported from the cloud.')
        restore_media(data, archive=archive)
        theme = Theme()
        theme.load_theme(json.dumps(data))
        return theme


def prepare_upload(mime, directory):
    """Snapshot the dragged rows before selection changes; export editable text in its native XML."""
    from opal.core.widgets.dnd import ThemeDragData
    if isinstance(mime, ThemeDragData):
        result = []
        for position, name in enumerate(mime.names):
            theme = mime.manager.get_theme_data(name)
            descriptor = theme.export_theme(mime.manager.theme_path)
            result.append(('themes', directory / str(position) / (safe_name(name) + '.opal-theme'), descriptor, name))
        return result
    library = mime.library
    category = library.plugin.name
    if category not in CATEGORIES or not mime.indexes or not all(index.isValid() for index in mime.indexes):
        raise SyncError('Select supported Library items to upload.')
    rows = [library.list_view.itemFromIndex(QtCore.QModelIndex(index)) for index in mime.indexes]
    result = []
    if category in FILE_TYPES:
        for row in rows:
            item = row.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if not isinstance(item, library.item_class):
                raise SyncError('Select files inside a folder to upload.')
            source = Path(item.file_path)
            if not source.is_file():
                raise SyncError(f'The local file is missing: {source.name}')
            title = friendly_name(item.name or source.name)
            result.append((category, source, None, title))
        return result
    for position, row in enumerate(rows):
        item_id = row.data(QtCore.Qt.ItemDataRole.UserRole)
        if category == 'songs':
            from opal.plugins.songs.lib.db import Song
            from opal.plugins.songs.lib.openlyricsxml import OpenLyrics
            record = library.plugin.manager.get_object(Song, item_id)
            xml = OpenLyrics(library.plugin.manager).song_to_xml(record)
        else:
            from opal.plugins.custom.lib.db import CustomSlide
            from opal.plugins.custom.lib.customxmlhandler import CustomXML
            from opal.core.lib.slidedesign import package_design
            record = library.plugin.db_manager.get_object(CustomSlide, item_id)
            custom = CustomXML(record.text)
            custom.add_title_and_credit(record.title, record.credits or '')
            service = library.build_service_item(item=row)
            custom.set_design(package_design(service.slide_design, service.get_theme_data(include_design=False)))
            xml = custom.extract_xml(keep_title_and_credit=True)
        suffix = '.opal-song' if category == 'songs' else '.opal-slides'
        if record.theme_name:
            root, _ = safe_xml(xml.encode('utf-8') if isinstance(xml, str) else xml)
            etree.SubElement(root, THEME_TAG).text = record.theme_name
            xml = etree.tostring(root, encoding='unicode')
        name = safe_name(record.title) + suffix
        result.append((category, directory / str(position) / name, xml, record.title))
    return result


def write_upload(source, contents):
    if contents is None:
        return
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == '.opal-theme':
        with export_archive(source, 'theme', f'{source.stem}/{source.stem}.json') as archive:
            archive.writestr(f'{source.stem}/{source.stem}.json', contents)
            write_media(archive, json.loads(contents))
        return
    write_xml_package(source, contents)


def import_item(item, path, plugin, target=None, prepared=None, overwrite=None):
    category = item_category(item)
    existing = local_item(category, plugin, item.display_name, Path(item.name).suffix) \
        if category == 'themes' or plugin else None
    if existing is not None and overwrite is None:
        raise SyncError('This name already exists in the local Library. Confirm overwrite before downloading.')
    if overwrite is not None and (existing is None or (existing if category == 'themes' else existing.id) != overwrite):
        raise SyncError('The local item changed. Download again to confirm the replacement.')
    if category == 'themes':
        manager = Registry().get('theme_manager')
        theme = prepared or read_theme_item(path)
        theme.theme_name = existing or item.display_name
        if safe_name(theme.theme_name) != theme.theme_name:
            raise SyncError('The theme name contains unsupported path characters.')
        descriptor = manager.theme_path / theme.theme_name / (theme.theme_name + '.json')
        descriptor.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=descriptor.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(theme.export_theme(manager.theme_path))
            temporary.replace(descriptor)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        manager.update_preview_images([theme.theme_name])
        return
    if not plugin or not plugin.is_active() or plugin.name != category:
        raise SyncError('Enable the matching Library plugin before downloading this item.')
    library = plugin.media_item
    if category in FILE_TYPES and overwrite is not None:
        existing.name = safe_name(item.display_name) + path.suffix
        existing.file_path = str(path)
        existing.file_hash = prepared
        if not library.manager.save_object(existing):
            raise SyncError('The replacement could not be saved. The original file has been retained.')
        remove_local_row(library.list_view, existing.id, tree=True)
        library._insert_saved_items([existing], existing.folder)
    elif category in FILE_TYPES:
        if not library.validate_and_load([path], target, file_hashes={path: prepared} if prepared else None,
                                         file_names={path: safe_name(item.display_name) + path.suffix}):
            raise SyncError('The file already exists or could not be saved in the local Library.')
    else:
        root, text = prepared or read_xml_item(path)
        if category == 'songs':
            from opal.plugins.songs.lib.openlyricsxml import OpenLyrics
            if root.tag != '{http://openlyrics.info/namespace/2009/song}song':
                raise SyncError('This cloud item is not an OpenLyrics song.')
            title = root.find('{http://openlyrics.info/namespace/2009/song}properties/'
                              '{http://openlyrics.info/namespace/2009/song}titles/'
                              '{http://openlyrics.info/namespace/2009/song}title')
            if title is not None:
                title.text = item.title or title.text
                text = etree.tostring(root, encoding='unicode')
            song = OpenLyrics(plugin.manager).xml_to_song(text, update_song_id=overwrite)
            if not song or not song.id:
                raise SyncError('The cloud song could not be imported.')
            from opal.plugins.songs.lib.mediaitem import SongListWidget
            row = SongListWidget.make_item(song.title, song.song_author_display, song.id, song.song_has_audio)
        else:
            from opal.plugins.custom.lib.customxmlhandler import CustomXML
            from opal.plugins.custom.lib.db import CustomSlide
            if root.tag != 'song' or root.find('lyrics') is None or not root.findall('lyrics/verse'):
                raise SyncError('This cloud item is not a Custom Slides document.')
            custom = CustomXML(text)
            record = existing if overwrite is not None else CustomSlide()
            record.title = item.title or root.findtext('title') or item.display_name
            record.credits = root.findtext('credit') or ''
            record.theme_name = root.findtext(THEME_TAG) or root.findtext(LEGACY_THEME_TAG) or ''
            record.text = custom.extract_xml().decode('utf-8')
            if not plugin.db_manager.save_object(record):
                raise SyncError('The cloud item could not be saved in the local Library.')
            row = QtWidgets.QListWidgetItem(record.title)
            row.setData(QtCore.Qt.ItemDataRole.UserRole, record.id)
        # Importing must not clear existing rows or rerun a filter that can hide the entire library.
        if overwrite is not None:
            remove_local_row(library.list_view, overwrite, tree=category == 'songs')
        library.list_view.setSortingEnabled(True)
        library.list_view.addItem(row)
        library.list_view.setCurrentItem(row)
        library.list_view.scrollToItem(row)
