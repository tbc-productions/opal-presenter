"""Portable designer media: small inline files and content-addressed archive assets."""
import base64
import copy
import hashlib
import re
from tempfile import NamedTemporaryFile
from pathlib import Path
from shutil import copyfile

from PySide6 import QtCore, QtGui

from opal.core.common.applocation import AppLocation


EMBED_LIMIT = 2 * 1024 * 1024
MIME_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp',
              'gif': 'image/gif', 'bmp': 'image/bmp', 'mp4': 'video/mp4', 'm4v': 'video/mp4',
              'webm': 'video/webm', 'mov': 'video/quicktime', 'ogv': 'video/ogg'}
ASSET = re.compile(r'^assets/([a-f0-9]{64})\.(png|jpg|jpeg|webp|gif|bmp|mp4|m4v|webm|mov|ogv)$')
INLINE = re.compile(r'^data:(image/(?:png|jpeg|webp|gif|bmp)|video/(?:mp4|webm|quicktime|ogg));'
                    r'base64,[A-Za-z0-9+/=]+$')


def asset_root():
    return AppLocation.get_section_data_path('designer')


def media_kind(source):
    if isinstance(source, str) and source.startswith('data:'):
        return 'video' if source.startswith('data:video/') else 'image'
    return 'video' if MIME_TYPES.get(Path(str(source)).suffix.lower().lstrip('.'), '').startswith('video/') else 'image'


def valid_media_source(source, kind=None):
    """Never accept imported filesystem paths, SVG, HTML or remote URLs."""
    if not isinstance(source, str):
        return False
    valid = bool(ASSET.fullmatch(source) or (len(source) <= 8_000_000 and INLINE.fullmatch(source)))
    return valid and (kind is None or media_kind(source) == kind)


def cache_media(path):
    """Keep an independent original so deleting a library entry cannot break a design."""
    path = Path(path)
    extension = path.suffix.lower().lstrip('.')
    if extension not in MIME_TYPES:
        raise ValueError('This media format is not supported.')
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    reference = f'assets/{digest}.{extension}'
    destination = asset_root() / reference
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        copyfile(path, destination)
    if not ASSET.fullmatch('assets/' + path.name):
        remember_media_label(reference, path.name)
    return reference


def remember_media_label(source, label):
    """Retain the friendly name independently of library records and source files."""
    if not label:
        return
    path = Path(materialise_media(source))
    if not ASSET.fullmatch('assets/' + path.name):
        return
    label = Path(str(label)).name[:500]
    if not label or ASSET.fullmatch('assets/' + label):
        return
    destination = asset_root() / 'labels' / (path.stem + '.txt')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(label, encoding='utf-8')


def media_label(source):
    """Never expose a content hash as the name of imported or managed media."""
    path = Path(materialise_media(source))
    if ASSET.fullmatch('assets/' + path.name):
        label = asset_root() / 'labels' / (path.stem + '.txt')
        if label.is_file():
            return label.read_text(encoding='utf-8')
        return 'Video' if media_kind(path) == 'video' else 'Image'
    return path.name


def media_to_source(path):
    """Preserve original bytes; apply the threshold before base64 encoding."""
    path = Path(path)
    mime = MIME_TYPES.get(path.suffix.lower().lstrip('.'))
    if not mime:
        raise ValueError('This media format is not supported.')
    size = QtCore.QSize(1920, 1080)
    if mime.startswith('image/'):
        reader = QtGui.QImageReader(str(path))
        reader.setAutoTransform(True)
        if not reader.canRead() or not reader.size().isValid():
            raise ValueError('This image could not be opened.')
        size = reader.size()
        if reader.transformation() & QtGui.QImageIOHandler.Transformation.TransformationRotate90:
            size.transpose()
    if path.stat().st_size < EMBED_LIMIT:
        return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii'), size
    return cache_media(path), size


def resolve_media(source):
    """Resolve a validated reference only inside the managed asset directory."""
    if isinstance(source, str) and ASSET.fullmatch(source):
        return asset_root() / source
    return source


def display_media(source):
    if valid_media_source(source, 'video'):
        from opal.core.lib.videoplayback import video_playback_path
        return video_playback_path(source).as_uri()
    path = resolve_media(source)
    return path.as_uri() if isinstance(path, Path) else path


def materialise_media(source):
    """Return a local file for theme forms/native playback, retaining inline original bytes."""
    if isinstance(source, str) and INLINE.fullmatch(source):
        mime, encoded = source[5:].split(';base64,', 1)
        extension = next(extension for extension, value in MIME_TYPES.items() if value == mime)
        data = base64.b64decode(encoded, validate=True)
        reference = f'assets/{hashlib.sha256(data).hexdigest()}.{extension}'
        target = resolve_media(reference)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
        return target
    return resolve_media(source)


def media_references(value):
    """Find unique assets in masters, per-slide overrides and embedded themes too."""
    references = set()
    if isinstance(value, dict):
        for child in value.values():
            references.update(media_references(child))
    elif isinstance(value, list):
        for child in value:
            references.update(media_references(child))
    elif isinstance(value, str) and ASSET.fullmatch(value):
        references.add(value)
    return references


def package_media(value):
    """Externalise oversized inline media from earlier designers when exporting."""
    result = copy.deepcopy(value)
    if isinstance(result, dict):
        for key, child in result.items():
            if (key in ('src', 'image', 'background_filename') and isinstance(child, str)
                    and INLINE.fullmatch(child) and len(child.split(',', 1)[1]) * 3 // 4 >= EMBED_LIMIT):
                path = materialise_media(child)
                if path.stat().st_size >= EMBED_LIMIT:
                    result[key] = cache_media(path)
            elif isinstance(child, (dict, list)):
                result[key] = package_media(child)
    elif isinstance(result, list):
        result = [package_media(child) for child in result]
    return result


def write_media(archive, value):
    existing = set(archive.namelist())
    for reference in sorted(media_references(value) - existing):
        archive.write(resolve_media(reference), reference)


def restore_media(value, directory=None, archive=None):
    """Verify content before retaining imported assets outside a temporary extraction."""
    for reference in media_references(value):
        destination = resolve_media(reference)
        if destination.is_file():
            continue
        if archive is not None:
            source_file = archive.open(reference)
        elif directory is not None:
            root = Path(directory).resolve()
            source = (root / reference).resolve()
            if not source.is_relative_to(root):
                raise ValueError('Invalid media asset path.')
            source_file = source.open('rb')
        else:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            digest = hashlib.sha256()
            with source_file, NamedTemporaryFile(dir=destination.parent, delete=False) as output:
                temporary = Path(output.name)
                for chunk in iter(lambda: source_file.read(1024 * 1024), b''):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != ASSET.fullmatch(reference)[1]:
                raise ValueError('The media asset does not match its reference.')
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def resolve_design_media(design):
    """Convert media fields on a detached render document, never on the saved design."""
    for element in design.get('elements', []):
        if element.get('kind') in ('image', 'video'):
            element['src'] = display_media(element['src'])
    if design.get('background', {}).get('image'):
        design['background']['image'] = display_media(design['background']['image'])
    return design
