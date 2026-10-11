"""Portable, song-local slide designs shared by the editor and output renderer.

Coordinates are stored as percentages of a pixel design canvas for XML compatibility. Small media files are embedded;
larger originals use managed, content-addressed references bundled when exporting.
"""
import copy
import html
import json
import math
import re

from opal.core.display.screens import ScreenList
from opal.core.lib.designmedia import (
    valid_media_source, media_to_source, materialise_media, resolve_media, resolve_design_media
)


DESIGN_VERSION = 1
COLOUR = re.compile(r'^#[0-9a-fA-F]{6}$')
IMAGE = re.compile(r'^data:image/png;base64,[A-Za-z0-9+/=]+$')
KINDS = {'text', 'rectangle', 'ellipse', 'image', 'video'}
FILTER_RANGES = {'blur': (0, 0, 100), 'brightness': (100, 0, 200), 'contrast': (100, 0, 200),
                 'grayscale': (0, 0, 100), 'hue-rotate': (0, -180, 180), 'invert': (0, 0, 100),
                 'saturate': (100, 0, 200), 'sepia': (0, 0, 100)}


def normalise_filters(value):
    """Keep supported numeric CSS filters only, omitting neutral values."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, limits in FILTER_RANGES.items():
        number = _number(value.get(key), *limits)
        if number != limits[0]:
            result[key] = number
    return result


def _number(value, default, low, high):
    try:
        value = float(value)
        return max(low, min(high, value)) if math.isfinite(value) else default
    except (ValueError, TypeError):
        return default


def _properties(source):
    """Whitelist properties before forwarding stored or imported data to a display."""
    result = {}
    ranges = {'x': (10, 0, 100), 'y': (10, 0, 100), 'width': (40, 0.001, 100),
              'height': (20, 0.001, 100), 'rotation': (0, -180, 180), 'opacity': (100, 0, 100),
              'font_size': (40, 1, 400), 'border_width': (0, 0, 40),
              'outline_width': (2, 0, 40), 'shadow_x': (4, -100, 100), 'shadow_y': (4, -100, 100),
              'shadow_blur': (4, 0, 100)}
    for key, limits in ranges.items():
        if key in source:
            result[key] = _number(source[key], *limits)
    for key in ('fill', 'colour', 'border_colour', 'outline_colour', 'shadow_colour'):
        if isinstance(source.get(key), str) and COLOUR.fullmatch(source[key]):
            result[key] = source[key]
    for key in ('bold', 'italic', 'outline', 'shadow', 'flip_horizontal', 'flip_vertical'):
        if isinstance(source.get(key), bool):
            result[key] = source[key]
    if isinstance(source.get('font'), str):
        result['font'] = source['font'][:200]
    if source.get('align') in ('left', 'center', 'right'):
        result['align'] = source['align']
    return result


def layer_order(design):
    """Return all selectable layers from back to front, including the main slide text."""
    defaults = [element['id'] for element in design.get('elements', [])] + ['lyrics']
    requested = design.get('order', [])
    order = []
    for identifier in requested if isinstance(requested, list) else []:
        if isinstance(identifier, str) and identifier in defaults and identifier not in order:
            order.append(identifier)
    return order + [identifier for identifier in defaults if identifier not in order]


def normalise_background(value):
    """A static base fill plus an independently translucent, embedded image."""
    if not isinstance(value, dict) or value.get('type') not in ('solid', 'gradient'):
        return {}
    result = {'type': value['type']}
    for key, default in (('colour', '#000000'), ('end_colour', '#ffffff')):
        colour = value.get(key)
        result[key] = colour if isinstance(colour, str) and COLOUR.fullmatch(colour) else default
    direction = value.get('direction')
    result['direction'] = direction if direction in ('horizontal', 'vertical', 'leftTop', 'leftBottom', 'circular') \
        else 'vertical'
    result['image_opacity'] = _number(value.get('image_opacity'), 100, 0, 100)
    result['fit'] = value.get('fit') if value.get('fit') in ('cover', 'contain', 'stretch', 'repeat') else 'cover'
    image = value.get('image')
    if valid_media_source(image):
        result['image'] = image
    return result


def normalise_design(value, include_layouts=True):
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
    if 'canvas_width' in value:
        result['canvas_width'] = _number(value['canvas_width'], 1920, 320, 16384)
    if 'reference_width' in value and 'reference_height' in value:
        result['reference_width'] = _number(value['reference_width'], 1920, 320, 16384)
        result['reference_height'] = _number(value['reference_height'], 1080, 1, 16384)
    hidden = value.get('hidden_footers', [])
    if isinstance(hidden, list):
        hidden = list(dict.fromkeys(key for key in hidden[:10000]
                                    if isinstance(key, str) and re.fullmatch(r'[a-z0-9-]+:[0-9]+:[0-9]+', key)))
        if hidden:
            result['hidden_footers'] = hidden
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
        if element['kind'] in ('image', 'video'):
            image = element.get('src', '')
            if not valid_media_source(image, element['kind']):
                continue
            clean['src'] = image
            filters = normalise_filters(element.get('filters'))
            if filters:
                clean['filters'] = filters
        result['elements'].append(clean)
    if 'order' in value:
        result['order'] = layer_order({**result, 'order': value['order']})
    embedded_theme = _normalise_theme(value.get('theme'))
    if embedded_theme:
        result['theme'] = embedded_theme
    background = normalise_background(value.get('background'))
    if background:
        result['background'] = background
    filters = normalise_filters(value.get('background_filters'))
    if filters:
        result['background_filters'] = filters
    if include_layouts:
        from opal.core.lib.slidelayouts import normalise_layouts
        result.update(normalise_layouts(value))
    layout_keys = ('masters', 'assignments', 'overrides', 'custom_layout_name', 'default_layout')
    return result if result['lyrics'] or result['elements'] or embedded_theme or background or \
        filters or result.get('hidden_footers') or 'canvas_width' in result or any(
            result.get(key) for key in layout_keys) else {}


def apply_design(theme, value, size=None):
    """Copy a theme and apply song overrides without modifying the shared theme."""
    design = normalise_design(value, False)
    if not design:
        return theme
    result = copy.deepcopy(design_theme(theme, design, size))
    background = design.get('background')
    if background:
        result.background_type = background['type']
        result.background_color = background['colour']
        result.background_start_color = background['colour']
        result.background_end_color = background['end_colour']
        result.background_direction = background['direction']
        result.background_filename = None
    size = size or ScreenList().current.display_geometry.size()
    from opal.core.lib.theme import Theme
    if isinstance(result, Theme):
        result.scale_to_size(size)
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
    if 'bold' in lyrics:
        result.font_main_weight = 0  # An explicit slide override supersedes the theme's weight.
    if 'font_size' in lyrics:
        result.font_main_size = lyrics['font_size'] * size.height() / design['canvas_height']
    if 'align' in lyrics:
        result.display_horizontal_align = ('left', 'right', 'center').index(lyrics['align'])
    if 'canvas_width' in design:
        canvas_width, canvas_height = design['canvas_width'], design['canvas_height']
        scale = min(size.width() / canvas_width, size.height() / canvas_height)
        fitted_width, fitted_height = canvas_width * scale, canvas_height * scale
        left, top = (size.width() - fitted_width) / 2, (size.height() - fitted_height) / 2
        # The inherited theme follows the same fitted frame as all designed objects.
        for part in ('main', 'footer'):
            for key, dimension, fitted, offset in (
                    ('x', size.width(), fitted_width, left), ('width', size.width(), fitted_width, 0),
                    ('y', size.height(), fitted_height, top), ('height', size.height(), fitted_height, 0)):
                attr = 'font_' + part + '_' + key
                setattr(result, attr, getattr(result, attr, 0) / dimension * fitted + offset)
            for suffix in ('size', 'outline_size', 'shadow_size', 'shadow_blur', 'letter_adjustment'):
                attr = 'font_' + part + '_' + suffix
                if hasattr(result, attr):
                    setattr(result, attr, getattr(result, attr) *
                            fitted_height / getattr(result, 'display_size_height', canvas_height))
        if 'font_size' in lyrics:
            result.font_main_size = lyrics['font_size'] * scale
        for element in design['elements']:
            element['x'] = (left + element['x'] / 100 * fitted_width) / size.width() * 100
            element['y'] = (top + element['y'] / 100 * fitted_height) / size.height() * 100
            element['width'] *= fitted_width / size.width()
            element['height'] *= fitted_height / size.height()
        result.font_main_override = result.font_footer_override = True
        result.song_design_output_height = fitted_height
    else:
        # Earlier designs continue to fill the output exactly as before.
        result.song_design_output_height = size.height()
    result.display_size_width = size.width()
    result.display_size_height = size.height()
    result.song_design = resolve_design_media(design)
    from opal.core.display.render import render_tags
    for element in result.song_design['elements']:
        if element['kind'] == 'text':
            text = html.escape(element['text'], quote=False).replace('[', '&#91;').replace(']', '&#93;')
            element['html'] = render_tags(text).replace('\n', '<br>')
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
    """Accept portable theme properties. Never load imported file paths or remote URLs."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, data in value.items():
        if re.fullmatch(r'font_(main|footer)_(x|y|width|height|size|outline_size|shadow_size|shadow_blur|'
                        r'line_adjustment|letter_adjustment)', key):
            result[key] = _number(data, 0, -16384, 16384)
        elif re.fullmatch(r'font_(main|footer)_weight', key):
            result[key] = int(_number(data, 0, 0, 1000))
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
    if value.get('background_type') not in ('solid', 'gradient', 'image', 'video', 'transparent'):
        return {}
    result['background_type'] = value['background_type']
    if isinstance(value.get('background_label'), str):
        result['background_label'] = value['background_label'][:500]
    if value.get('background_direction') in ('horizontal', 'vertical', 'leftTop', 'leftBottom', 'circular'):
        result['background_direction'] = value['background_direction']
    if value.get('background_fit') in ('cover', 'contain', 'stretch', 'repeat'):
        result['background_fit'] = value['background_fit']
    if result['background_type'] in ('image', 'video'):
        image = value.get('background_filename')
        if not valid_media_source(image, result['background_type']):
            return {}
        result['background_filename'] = image
    return result


def package_design(value, theme):
    """Snapshot a portable base theme for XML or service export, leaving the library theme inherited.

    Streams remain external. Images and video files follow the portable media policy.
    """
    from opal.core.lib.theme import Theme
    from opal.core.lib.designmedia import package_media

    design = package_media(normalise_design(value))
    if not design or design.get('theme') or not isinstance(theme, Theme):
        return design
    snapshot = copy.deepcopy(theme.__dict__)
    if theme.background_type in ('image', 'video'):
        if valid_media_source(theme.background_filename):
            snapshot['background_filename'] = theme.background_filename
        else:
            snapshot['background_filename'], _ = media_to_source(theme.background_filename)
    size = ScreenList().current.display_geometry.size()
    snapshot.update(display_size_width=size.width(), display_size_height=size.height())
    snapshot = _normalise_theme(snapshot)
    if snapshot:
        design['theme'] = snapshot
    return design


def design_theme(theme, value, size=None):
    """Use an embedded base theme after import, scaling its geometry for the destination output."""
    design = normalise_design(value, False)
    snapshot = design.get('theme')
    if not snapshot:
        return theme
    result = copy.deepcopy(theme)
    size = size or ScreenList().current.display_geometry.size()
    for key, data in snapshot.items():
        if re.fullmatch(r'font_(main|footer)_(x|width)', key):
            data *= size.width() / snapshot.get('display_size_width', size.width())
        elif re.fullmatch(r'font_(main|footer)_(y|height|size|outline_size|shadow_size|shadow_blur|'
                          r'letter_adjustment)', key):
            data *= size.height() / snapshot.get('display_size_height', size.height())
        setattr(result, key, data)
    result.display_size_width = size.width()
    result.display_size_height = size.height()
    source = snapshot.get('background_filename')
    result.background_filename = materialise_media(source) if snapshot['background_type'] == 'video' else \
        resolve_media(source)
    return result


def remap_custom_footers(value, before, after, offset=0):
    """Keep per-page flags on their logical custom slide across text edits, insertions and deletions."""
    from difflib import SequenceMatcher

    design = copy.deepcopy(value)
    if not any(design.get(key) for key in ('hidden_footers', 'assignments', 'overrides')) or before == after:
        return design
    mapping = {}
    for operation, old_start, old_end, new_start, new_end in SequenceMatcher(
            a=before, b=after, autojunk=False).get_opcodes():
        if operation in ('equal', 'replace'):
            for step, old_index in enumerate(range(old_start, old_end)):
                mapping[old_index] = new_start + step if new_start + step < new_end else None
        elif operation == 'delete':
            mapping.update((index, None) for index in range(old_start, old_end))

    def remap(key):
        section, split, page = key.split(':')
        if section.startswith('custom-'):
            index = int(section[7:]) - 1
            if offset <= index < offset + len(before):
                destination = mapping.get(index - offset)
                if destination is None:
                    return None
                index = offset + destination
            elif index >= offset + len(before):
                index += len(after) - len(before)
            section = f'custom-{index + 1}'
        return f'{section}:{split}:{page}'

    if 'hidden_footers' in design:
        design['hidden_footers'] = [destination for key in design['hidden_footers']
                                    if (destination := remap(key)) is not None]
    for collection in ('assignments', 'overrides'):
        if collection in design:
            design[collection] = {destination: value for key, value in design[collection].items()
                                  if (destination := remap(key)) is not None}
    return design
