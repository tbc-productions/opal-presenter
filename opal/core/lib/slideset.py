"""Ordered, portable service Collections containing images and custom text slides."""
import json
import base64
from copy import deepcopy
from pathlib import Path

from PySide6 import QtCore, QtGui

from opal.core.common.enum import ServiceItemType
from opal.core.display.screens import ScreenList
from opal.core.lib import ItemCapabilities, image_to_data_uri
from opal.core.lib.slidedesign import image_to_png_uri, normalise_design, package_design
from opal.core.lib.theme import Theme, TransitionSpeed, TransitionType


def _set_slides(item):
    """Detach slides and capture their source design before combining items."""
    if item.is_slide_set:
        return deepcopy(item.slides)
    slides = []
    if item.is_image():
        for image in item.slides:
            path = Path(image['path'])
            if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.avif'):
                uri = image_to_data_uri(path)
            else:
                uri, _ = image_to_png_uri(path)
            slides.append({
                'title': image['title'], 'text': '', 'verse': '', 'footer_html': '',
                'metadata': {'set_image': uri, 'set_image_fit': item.settings.value('images/fit'),
                             'set_image_colour': item.settings.value('core/logo background color')}
            })
    else:
        design = deepcopy(item.slide_design)
        if not design:
            size = ScreenList().current.display_geometry.size()
            design = {'version': 1, 'canvas_width': size.width(), 'canvas_height': size.height()}
        design = package_design(design, item.get_theme_data(include_design=False))
        for index, raw_slide in enumerate(item.slides):
            slide = deepcopy(raw_slide)
            slide['title'] = slide['title'] or f'{item.title} ({index + 1})'
            metadata = slide.setdefault('metadata', {})
            metadata.setdefault('design_section', f'custom-{index + 1}')
            metadata['set_custom'] = {'theme': item.theme, 'design': design,
                                      'footer': deepcopy(item.raw_footer)}
            slide.setdefault('footer_html', item.footer_html or '<br>'.join(filter(None, item.raw_footer)))
            slides.append(slide)
    return slides


def append_to_set(target, items):
    """Build the complete replacement before mutating the selected service item."""
    if not items:
        return
    if not all(target.can_append_plugin(item.name) and item.name in ('images', 'custom') for item in items):
        raise ValueError('Collections support images and custom slides')
    slides = _set_slides(target)
    for item in items:
        slides.extend(_set_slides(item))
    for index, slide in enumerate(slides):
        slide['verse'] = str(index + 1)
    target.slides = slides
    target.is_slide_set = True
    target.service_item_type = ServiceItemType.Text
    target.name = 'images'
    target.slide_design = {}
    target.edit_id = None
    target.raw_footer = []
    target.footer_html = ''
    target.capabilities = [ItemCapabilities.CanMaintain, ItemCapabilities.CanPreview, ItemCapabilities.CanLoop,
                           ItemCapabilities.CanAppend, ItemCapabilities.CanEditTitle, ItemCapabilities.CanSoftBreak,
                           ItemCapabilities.HasDisplayTitle]
    target._clear_slides_cache()
    target._new_item()
    target.add_icon()


def render_set(item):
    """Render each custom source with its own theme, then number the combined pages."""
    from opal.core.lib.serviceitem import ServiceItem

    rendered, displayed = [], []
    for raw_index, raw_slide in enumerate(item.slides):
        metadata = raw_slide.get('metadata', {})
        if metadata.get('set_image'):
            theme = Theme()
            theme.background_type = 'image'
            theme.background_filename = metadata['set_image']
            theme.background_fit = metadata.get('set_image_fit', 'contain')
            theme.background_border_color = metadata.get('set_image_colour') or '#000000'
            theme.background_color = theme.background_border_color
            rendered.append({'title': raw_slide['title'], 'text': '', 'chords': '', 'verse': len(rendered),
                             'footer': '', 'set_image': metadata['set_image'],
                             'theme': json.loads(theme.export_theme(is_js=True))})
            displayed.append({'title': raw_slide['title'], 'text': raw_slide['title'],
                              'verse': str(len(displayed) + 1), 'raw_index': raw_index})
            continue
        source = metadata.get('set_custom', {})
        custom = ServiceItem()
        custom.name = 'custom'
        custom.service_item_type = ServiceItemType.Text
        custom.from_service = item.from_service
        custom.theme = source.get('theme')
        custom.slide_design = normalise_design(source.get('design'))
        custom.raw_footer = source.get('footer', [])
        custom.capabilities = [ItemCapabilities.CanSoftBreak, ItemCapabilities.CanWordSplit]
        custom.slides = [deepcopy(raw_slide)]
        for slide, display in zip(custom.rendered_slides, custom.display_slides):
            key = slide.get('design_key')
            if 'theme' not in slide:
                theme = custom.get_slide_theme(key) if key else custom.get_theme_data()
                slide['theme'] = json.loads(theme.export_theme(is_js=True))
            slide['verse'] = len(rendered)
            display['verse'] = str(len(displayed) + 1)
            display['raw_index'] = raw_index
            rendered.append(slide)
            displayed.append(display)
    settings = item.slide_transition_settings
    transition_type = settings.get('type', TransitionType.Fade)
    if isinstance(transition_type, str):
        transition_type = TransitionType.from_string(transition_type)
    transition_speed = settings.get('speed', TransitionSpeed.Normal)
    if isinstance(transition_speed, str):
        transition_speed = TransitionSpeed.from_string(transition_speed)
    for slide in rendered:
        slide['theme'].update(
            display_slide_transition=bool(settings.get('enabled', False)),
            display_slide_transition_type=transition_type if transition_type is not None else TransitionType.Fade,
            display_slide_transition_speed=transition_speed if transition_speed is not None else TransitionSpeed.Normal
        )
    return rendered, displayed


def set_thumbnail(item, index):
    """Cache portable image previews and browser-rendered custom pages outside saved slide data."""
    cache = item.__dict__.setdefault('_set_thumbnails', {})
    if index not in cache:
        # Rendering can process Qt events; prevent a nested repaint from capturing the same page.
        cache[index] = QtGui.QPixmap()
        frame = item.rendered_slides[index]
        if frame.get('set_image'):
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(base64.b64decode(frame['set_image'].split(',', 1)[1]))
        else:
            pixmap = item.renderer.generate_slide_preview(frame)
        if isinstance(pixmap, QtGui.QPixmap) and not pixmap.isNull():
            # Browser captures carry the screen's Retina scale; all cached previews
            # use physical pixels so painting them into tree icons keeps their size.
            pixmap.setDevicePixelRatio(1)
            cache[index] = pixmap.scaled(248, 140, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                         QtCore.Qt.TransformationMode.SmoothTransformation)
    return cache[index]
