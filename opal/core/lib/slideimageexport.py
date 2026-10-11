"""Capture custom slides with the same browser renderer used for projection."""
from collections import defaultdict

from PySide6 import QtCore

from opal.core.common import clean_filename
from opal.core.common.enum import ServiceItemType
from opal.core.common.i18n import translate
from opal.core.common.utils import wait_for
from opal.core.display.screens import ScreenList
from opal.core.display.window import DisplayWindow
from opal.core.lib.presentationexport import service_pages


def render_slide_images(items, directory, progress=None):
    """Return (PNG path, library name) pairs, numbered independently for each item."""
    pages = service_pages(items, progress=progress)
    if not pages:
        return []
    size = ScreenList().current.display_geometry.size()
    display = DisplayWindow(can_show_startup_screen=False)
    display.allow_theme_transitions = False
    display.allow_item_transitions = False
    display.show_transparency = False
    display.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
    display.setGeometry(-size.width() - 10000, -size.height() - 10000, size.width(), size.height())
    result, counts, ready = [], defaultdict(int), set()
    display.display_watcher.register_event_listener(
        'imageExportReady', lambda value: ready.add(value.toVariant() if hasattr(value, 'toVariant') else value), False)
    try:
        display.show()
        if not wait_for(lambda: display._is_initialised):
            raise RuntimeError('The slide renderer could not be initialised.')
        for index, page in enumerate(pages):
            if progress:
                progress(translate('CustomPlugin.MediaItem', 'Saving images…'), index, len(pages))
            display.set_theme(page.theme, is_sync=True, service_item_type=ServiceItemType.Text)
            display.load_verses([{'verse': 'image-export', 'text': page.html_text,
                                  'footer': page.html_footer}], is_sync=True)
            display.run_in_display('goToSlide', 'image-export', is_sync=True)
            display.run_in_display('waitForDesignPreview', index + 1, return_event_name='imageExportReady')
            if not wait_for(lambda: index + 1 in ready):
                raise RuntimeError('The slide did not finish rendering.')
            counts[page.section_index] += 1
            number = counts[page.section_index]
            title = page.section_name or translate('CustomPlugin.MediaItem', 'Custom Slide')
            name = title + (f' ({number})' if number > 1 else '')
            filename = (clean_filename(name).strip(' .') or 'Custom Slide') + '.png'
            target = directory / str(page.section_index) / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            image = display.webview.grab().toImage()
            image.setDevicePixelRatio(1)
            if image.size() != size:
                image = image.scaled(size, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                                     QtCore.Qt.TransformationMode.SmoothTransformation)
            if image.isNull() or not image.save(str(target), 'PNG'):
                raise OSError(f'Could not save the slide image: {target}')
            result.append((target, filename))
        if progress:
            progress(translate('CustomPlugin.MediaItem', 'Saving images…'), len(pages), len(pages))
        return result
    finally:
        display.hide()
        display.deleteLater()
