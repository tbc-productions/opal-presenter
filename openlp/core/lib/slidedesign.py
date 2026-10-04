"""Portable, song-local slide designs shared by the editor and output renderer.

Coordinates are percentages of the output canvas. Images are embedded PNG data
URIs, so saved services do not depend on the original image files.
"""
import copy
import json
import math
import re

from openlp.core.display.screens import ScreenList


DESIGN_VERSION = 1
COLOUR = re.compile(r'^#[0-9a-fA-F]{6}$')
IMAGE = re.compile(r'^data:image/png;base64,[A-Za-z0-9+/=]+$')
KINDS = {'text', 'rectangle', 'ellipse', 'image'}


def _number(value, default, low, high):
    try:
        value = float(value)
        return max(low, min(high, value)) if math.isfinite(value) else default
    except (ValueError, TypeError):
        return default


def _properties(source):
    """Whitelist properties before forwarding stored or imported data to a display."""
    result = {}
    ranges = {'x': (10, 0, 100), 'y': (10, 0, 100), 'width': (40, 1, 100),
              'height': (20, 1, 100), 'rotation': (0, -180, 180), 'opacity': (100, 0, 100),
              'font_size': (40, 1, 400), 'border_width': (0, 0, 40)}
    for key, limits in ranges.items():
        if key in source:
            result[key] = _number(source[key], *limits)
    for key in ('fill', 'colour', 'border_colour'):
        if isinstance(source.get(key), str) and COLOUR.fullmatch(source[key]):
            result[key] = source[key]
    for key in ('bold', 'italic'):
        if isinstance(source.get(key), bool):
            result[key] = source[key]
    if isinstance(source.get('font'), str):
        result['font'] = source['font'][:200]
    if source.get('align') in ('left', 'center', 'right'):
        result['align'] = source['align']
    return result


def normalise_design(value):
    """Return a detached, validated v1 document, or an empty inherited design."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    if not isinstance(value, dict) or value.get('version') != DESIGN_VERSION:
        return {}
    result = {'version': DESIGN_VERSION, 'canvas_height': _number(value.get('canvas_height'), 1080, 1, 16384),
              'lyrics': _properties(value.get('lyrics', {}) if isinstance(value.get('lyrics'), dict) else {}),
              'elements': []}
    seen = set()
    elements = value.get('elements', [])
    for element in elements[:100] if isinstance(elements, list) else []:
        if not isinstance(element, dict) or element.get('kind') not in KINDS:
            continue
        identifier = element.get('id')
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', identifier):
            continue
        if identifier == 'lyrics' or identifier in seen:
            continue
        seen.add(identifier)
        clean = _properties(element)
        clean.update(id=identifier, kind=element['kind'])
        for key, default in (('x', 10), ('y', 10), ('width', 40), ('height', 20)):
            clean.setdefault(key, default)
        clean['text'] = str(element.get('text', ''))[:10000]
        if element['kind'] == 'image':
            image = element.get('src', '')
            if not isinstance(image, str) or len(image) > 8_000_000 or not IMAGE.fullmatch(image):
                continue
            clean['src'] = image
        result['elements'].append(clean)
    embedded_theme = _normalise_theme(value.get('theme'))
    if embedded_theme:
        result['theme'] = embedded_theme
    return result if result['lyrics'] or result['elements'] or embedded_theme else {}


def apply_design(theme, value, size=None):
    """Copy a theme and apply song overrides without modifying the shared theme."""
    design = normalise_design(value)
    if not design:
        return theme
    result = copy.deepcopy(design_theme(theme, design, size))
    size = size or ScreenList().current.display_geometry.size()
    lyrics = design['lyrics']
    for key, dimension in (('x', size.width()), ('width', size.width()),
                           ('y', size.height()), ('height', size.height())):
        if key in lyrics:
            setattr(result, 'font_main_' + key, dimension * lyrics[key] / 100)
    if any(key in lyrics for key in ('x', 'y', 'width', 'height')):
        result.font_main_override = True
    for key, attribute in (('font', 'name'), ('colour', 'color'), ('bold', 'bold'), ('italic', 'italics')):
        if key in lyrics:
            setattr(result, 'font_main_' + attribute, lyrics[key])
    if 'font_size' in lyrics:
        result.font_main_size = lyrics['font_size'] * size.height() / design['canvas_height']
    if 'align' in lyrics:
        result.display_horizontal_align = ('left', 'right', 'center').index(lyrics['align'])
    result.song_design = design
    result.song_design_output_height = size.height()
    return result


def image_to_png_uri(path):
    """Embed a raster image at presentation resolution, independent of its source path."""
    import base64
    from PySide6 import QtCore, QtGui

    reader = QtGui.QImageReader(str(path))
    if reader.size().isValid():
        reader.setScaledSize(reader.size().scaled(1920, 1080, QtCore.Qt.AspectRatioMode.KeepAspectRatio))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ValueError('This image could not be opened.')
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    buffer.close()
    uri = 'data:image/png;base64,' + base64.b64encode(bytes(data)).decode('ascii')
    if len(uri) > 8_000_000:
        raise ValueError('Please choose a smaller image.')
    return uri, image.size()


def _normalise_theme(value):
    """Accept only static theme properties. Never load imported file paths or remote URLs."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, data in value.items():
        if re.fullmatch(r'font_(main|footer)_(x|y|width|height|size|outline_size|shadow_size|shadow_blur|'
                        r'line_adjustment|letter_adjustment)', key):
            result[key] = _number(data, 0, -16384, 16384)
        elif re.fullmatch(r'font_(main|footer)_(bold|italics|override|outline|shadow|wrap)', key):
            if isinstance(data, bool):
                result[key] = data
        elif re.fullmatch(r'(font_(main|footer)_(color|outline_color|shadow_color)|'
                          r'background_(color|border_color|start_color|end_color))', key):
            if isinstance(data, str) and COLOUR.fullmatch(data):
                result[key] = data
        elif key in ('font_main_name', 'font_footer_name', 'theme_name') and isinstance(data, str):
            result[key] = data[:200]
        elif re.fullmatch(r'display_(horizontal_align|vertical_align)(_footer)?', key):
            result[key] = int(_number(data, 0, 0, 3))
        elif key in ('display_size_width', 'display_size_height'):
            result[key] = _number(data, 1080, 1, 16384)
    if value.get('background_type') not in ('solid', 'gradient', 'image', 'transparent'):
        return {}
    result['background_type'] = value['background_type']
    if value.get('background_direction') in ('horizontal', 'vertical', 'leftTop', 'leftBottom', 'circular'):
        result['background_direction'] = value['background_direction']
    if value.get('background_fit') in ('cover', 'contain', 'stretch', 'repeat'):
        result['background_fit'] = value['background_fit']
    if result['background_type'] == 'image':
        image = value.get('background_filename')
        if not isinstance(image, str) or len(image) > 8_000_000 or not IMAGE.fullmatch(image):
            return {}
        result['background_filename'] = image
    return result


def package_design(value, theme):
    """Snapshot a static base theme for XML or service export, leaving the library theme inherited.

    Video/stream backgrounds remain external media and are not represented by this
    static design format. No snapshot is made for those backgrounds.
    """
    from openlp.core.lib.theme import Theme

    design = normalise_design(value)
    if not design or design.get('theme') or not isinstance(theme, Theme):
        return design
    snapshot = copy.deepcopy(theme.__dict__)
    if theme.background_type == 'image':
        snapshot['background_filename'], _ = image_to_png_uri(theme.background_filename)
    size = ScreenList().current.display_geometry.size()
    snapshot.update(display_size_width=size.width(), display_size_height=size.height())
    snapshot = _normalise_theme(snapshot)
    if snapshot:
        design['theme'] = snapshot
    return design


def design_theme(theme, value, size=None):
    """Use an embedded base theme after import, scaling its geometry for the destination output."""
    design = normalise_design(value)
    snapshot = design.get('theme')
    if not snapshot:
        return theme
    result = copy.deepcopy(theme)
    size = size or ScreenList().current.display_geometry.size()
    for key, data in snapshot.items():
        if re.fullmatch(r'font_(main|footer)_(x|width)', key):
            data *= size.width() / snapshot.get('display_size_width', size.width())
        elif re.fullmatch(r'font_(main|footer)_(y|height|size)', key):
            data *= size.height() / snapshot.get('display_size_height', size.height())
        setattr(result, key, data)
    result.background_filename = snapshot.get('background_filename')
    return result
