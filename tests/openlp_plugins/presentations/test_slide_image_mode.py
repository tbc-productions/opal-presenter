"""Tests for presenting exported slides in OpenLP instead of a separate slideshow."""
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets
from PySide6.QtCore import QThread, QTimer
from PySide6.QtGui import QImage

from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem
from openlp.plugins.presentations.lib.db import Item
from openlp.plugins.presentations.lib.presentationcontroller import PresentationDocument


def test_image_mode_is_opt_in(media_item):
    file_path = Path('slides.pptx')
    controller = MagicMock(supports_slide_images=True)
    media_item.controllers = {'Powerpoint': controller}
    media_item.automatic = 'Automatic'

    assert not media_item.should_render_as_images(file_path, 'Powerpoint')
    media_item.settings.setValue('presentations/render slide images', QtCore.Qt.CheckState.Checked)
    assert media_item.should_render_as_images(file_path, 'Powerpoint')
    controller.supports_slide_images = False
    assert not media_item.should_render_as_images(file_path, 'Powerpoint')
    assert media_item.should_render_as_images(Path('slides.pdf'), 'Pdf')


def test_powerpoint_snapshot_captures_only_the_named_window(settings):
    import importlib.util
    import openlp.plugins.presentations.lib as presentation_lib

    source = Path(presentation_lib.__file__).parent / 'powerpointmaccontroller.py'
    spec = importlib.util.spec_from_file_location('_openlp_powerpoint_window_capture_test', source)
    module = importlib.util.module_from_spec(spec)
    # test_firsttimeform temporarily patches QtCore.QThread in its own tests.
    # Preserve the real class collected before those tests ran.
    with patch.object(QtCore, 'QThread', QThread):
        spec.loader.exec_module(module)

    def capture_window(command, **kwargs):
        image = QImage(32, 24, QImage.Format.Format_ARGB32)
        image.fill(0xff345678)
        assert image.save(command[-1], 'PNG')
        return MagicMock(returncode=0)

    worker = module._PowerPointWindowSnapshot('PowerPoint Slide Show – [example]')
    # Other presentation tests can replace the imported backend with a mock.
    # Load this source file separately so the window-only capture remains tested.
    find_window = MagicMock(return_value=1256)
    with patch.object(module, '_find_powerpoint_slideshow_window', find_window), \
            patch.object(module.subprocess, 'run', side_effect=capture_window) as capture:
        worker.run()

    find_window.assert_called_once_with('PowerPoint Slide Show – [example]')
    assert capture.call_args.args[0][:4] == ['/usr/sbin/screencapture', '-x', '-l', '1256']
    assert worker.image.size() == QtCore.QSize(32, 24)


def test_slide_image_cache_requires_complete_set_and_matching_screen(settings, tmp_path):
    source_file = tmp_path / 'slides.pptx'
    source_file.write_bytes(b'presentation')
    sources = [tmp_path / 'first.png', tmp_path / 'second.png']
    for number, source in enumerate(sources):
        source.write_bytes(bytes([number]))
    controller = MagicMock()
    controller.thumbnail_folder = tmp_path / 'thumbs'
    controller.temp_folder = tmp_path / 'rendered'
    controller.thumbnail_prefix = 'slide'
    document = PresentationDocument(controller, source_file)
    with patch('openlp.plugins.presentations.lib.presentationcontroller.ScreenList') as screens:
        size = screens.return_value.current.display_geometry.size.return_value
        size.width.return_value = 1920
        size.height.return_value = 1080
        assert document.save_slide_images_from_sources(sources)
        paths = document.get_slide_image_paths()
        assert [path.read_bytes() for path in paths] == [b'\x00', b'\x01']
        paths[1].unlink()
        assert document.get_slide_image_paths() == []
        assert document.save_slide_images_from_sources(sources)
        size.width.return_value = 1280
        assert document.get_slide_image_paths() == []


def test_native_presentation_can_be_rendered_as_openlp_images(media_item, tmp_path):
    source = tmp_path / 'slides.pptx'
    source.write_bytes(b'presentation')
    images = [tmp_path / 'slide1.png', tmp_path / 'slide2.png']
    for image in images:
        image.write_bytes(b'image')
    controller = MagicMock(supports_slide_images=True)
    document = controller.add_document.return_value
    document.get_slide_image_paths.side_effect = [[], images]
    document.load_presentation.return_value = True
    document.create_slide_images.return_value = True
    document.get_titles_and_notes.return_value = (['One', 'Two'], ['', 'Note'])
    document.get_thumbnail_path.side_effect = lambda number, exists: images[number - 1]
    media_item.controllers = {'Powerpoint': controller}
    media_item.automatic = 'Automatic'
    media_item.find_controller_by_type = MagicMock(return_value='Powerpoint')
    media_item.settings.setValue('presentations/render slide images', QtCore.Qt.CheckState.Checked)
    media_item.display_type_combo_box = MagicMock()
    media_item.display_type_combo_box.currentText.return_value = 'Powerpoint'
    media_item.display_type_combo_box.itemData.return_value = 'automatic'
    tree_item = QtWidgets.QTreeWidgetItem(None)
    tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, Item(id=1, file_path=str(source)))
    service_item = ServiceItem(None)

    assert media_item.generate_slide_data(service_item, item=tree_item, file_path=source)
    assert service_item.is_image()
    assert service_item.is_valid
    assert service_item.processor is None
    assert [slide['path'] for slide in service_item.slides] == images
    assert [slide['display_title'] for slide in service_item.slides] == ['One', 'Two']
    assert all(slide['use_background_image'] for slide in service_item.slides)
    assert service_item.is_capable(ItemCapabilities.CanPreview)
    document.load_presentation.assert_called_once()
    document.create_slide_images.assert_called_once()
    document.close_presentation.assert_called_once()


def test_powerpoint_exports_visible_slides_at_screen_resolution(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointcontroller import PowerpointDocument

    with patch('openlp.plugins.presentations.lib.powerpointcontroller.PresentationDocument._setup'):
        document = PowerpointDocument(MagicMock(), tmp_path / 'slides.pptx')
    document.index_map = {1: 2, 2: 4}
    document.presentation = MagicMock()
    document.presentation.PageSetup.SlideWidth = 4
    document.presentation.PageSetup.SlideHeight = 3
    document.get_temp_folder = MagicMock(return_value=tmp_path)
    document.invalidate_slide_images = MagicMock()
    document.save_slide_image_manifest = MagicMock()
    with patch('openlp.plugins.presentations.lib.powerpointcontroller.ScreenList') as screens:
        size = screens.return_value.current.display_geometry.size.return_value
        size.width.return_value = 1920
        size.height.return_value = 1080
        assert document.create_slide_images()

    assert document.presentation.Slides.call_args_list == [call(2), call(4)]
    assert document.presentation.Slides.return_value.Export.call_args_list == [
        call(str(tmp_path / 'mainslide001.png'), 'png', 1440, 1080),
        call(str(tmp_path / 'mainslide002.png'), 'png', 1440, 1080)
    ]
    document.save_slide_image_manifest.assert_called_once_with(2)


def test_keynote_cached_exports_restore_slide_count(settings, tmp_path):
    from openlp.plugins.presentations.lib.keynotecontroller import KeynoteDocument

    (tmp_path / 'slide1.png').write_bytes(b'first')
    (tmp_path / 'slide2.png').write_bytes(b'second')
    controller = MagicMock()
    with patch('openlp.plugins.presentations.lib.keynotecontroller.AppleScriptBaseDocument.load_presentation',
               return_value=True), patch(
                   'openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = KeynoteDocument(controller, tmp_path / 'slides.key')
        document.get_thumbnail_folder = MagicMock(return_value=tmp_path)
        assert document.load_presentation()
    assert document.get_slide_count() == 2


def test_applescript_export_does_not_close_unrelated_front_document(settings, tmp_path):
    from openlp.plugins.presentations.lib.applescriptbasecontroller import AppleScriptBaseDocument

    source = tmp_path / 'slides.key'
    source.write_bytes(b'presentation')
    controller = MagicMock()
    controller.thumbnail_folder = tmp_path / 'thumbs'
    controller.temp_folder = tmp_path / 'temp'
    document = AppleScriptBaseDocument(controller, source)
    document.presentation_loaded = True  # Export completed and closed its own document.

    document.close_presentation()

    controller.applescript.call.assert_not_called()
    controller.remove_doc.assert_called_once_with(document)


def test_render_mode_checkbox_saves_setting(settings):
    from openlp.core.common.registry import Registry
    from openlp.plugins.presentations.lib.presentationtab import PresentationTab

    Registry().register('settings_form', MagicMock())
    tab = PresentationTab(None, 'Presentations', None, {}, None)
    assert not tab.render_slide_images_check_box.isChecked()
    tab.activated = True
    tab.render_slide_images_check_box.setChecked(True)
    tab.save()
    assert settings.value('presentations/render slide images') == QtCore.Qt.CheckState.Checked


def test_failed_image_export_keeps_native_service_item(media_item, tmp_path):
    from openlp.plugins.presentations.lib.messagelistener import MessageListener

    source = tmp_path / 'slides.pptx'
    source.write_bytes(b'presentation')
    item = ServiceItem(None)
    item.processor = 'Powerpoint'
    item.add_from_command(str(tmp_path), source.name, 'thumbnail.png')
    original_identifier = item.unique_identifier
    media_item.automatic = 'Automatic'
    media_item.should_render_as_images = MagicMock(return_value=True)
    media_item.generate_slide_data = MagicMock(return_value=False)
    controller = MagicMock(available=True)
    with patch.object(MessageListener, '_setup'):
        listener = MessageListener(media_item)
    listener.media_item = media_item
    listener.controllers = {'Powerpoint': controller}
    listener.live_handler = MagicMock()
    listener.timer = MagicMock()

    listener.startup([item, True, None, 0])

    assert item.processor == 'Powerpoint'
    assert item.unique_identifier == original_identifier
    assert item.is_command()
    listener.live_handler.add_handler.assert_called_once()


def test_saved_native_item_converts_to_images_on_startup(media_item, tmp_path):
    from openlp.plugins.presentations.lib.messagelistener import MessageListener

    source = tmp_path / 'slides.pptx'
    source.write_bytes(b'presentation')
    rendered = tmp_path / 'mainslide001.png'
    rendered.write_bytes(b'image')
    item = ServiceItem(None)
    item.processor = 'Powerpoint'
    item.add_from_command(str(tmp_path), source.name, 'thumbnail.png')
    item.name = 'presentations'
    original_identifier = item.unique_identifier
    media_item.automatic = 'Automatic'
    media_item.should_render_as_images = MagicMock(return_value=True)

    def generate(target, **kwargs):
        target.add_from_image(rendered, 'slides', thumbnail=rendered)
        return True

    media_item.generate_slide_data = MagicMock(side_effect=generate)
    with patch.object(MessageListener, '_setup'):
        listener = MessageListener(media_item)
    listener.media_item = media_item
    listener.preview_handler = MagicMock()
    listener.timer = MagicMock()

    listener.startup([item, False, None, 0])

    assert item.is_image()
    assert item.name == 'presentations'
    assert item.unique_identifier == original_identifier
    assert listener.handler is None
    listener.preview_handler.add_handler.assert_not_called()


def test_native_presentation_uses_real_file_path_when_library_name_is_custom(media_item, tmp_path):
    source = tmp_path / 'survivor-deck.pptx'
    source.write_bytes(b'presentation')
    thumbnail = tmp_path / 'slide1.png'
    thumbnail.write_bytes(b'image')
    document = MagicMock()
    document.get_thumbnail_path.side_effect = [thumbnail, thumbnail, None]
    document.get_titles_and_notes.return_value = ([], [])
    document.get_sha256_file_hash.return_value = 'source-hash'
    controller = MagicMock()
    controller.add_document.return_value = document
    media_item.controllers = {'Powerpoint': controller}
    media_item.find_controller_by_type = MagicMock(return_value='Powerpoint')
    media_item.display_type_combo_box = MagicMock()
    media_item.display_type_combo_box.currentText.return_value = 'Powerpoint'
    media_item.display_type_combo_box.itemData.return_value = 'automatic'
    tree_item = QtWidgets.QTreeWidgetItem(None)
    tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole,
                      Item(id=1, name='Survivor', file_path=str(source)))
    service_item = ServiceItem(None)
    service_item.name = 'presentations'

    assert media_item.generate_slide_data(service_item, item=tree_item)
    assert service_item.title == 'Survivor'
    assert service_item.get_frame_path() == source
    assert service_item.is_valid


def test_existing_presentation_item_recovers_source_from_content_hash(settings, tmp_path):
    from openlp.core.common import sha256_file_hash

    source = tmp_path / 'survivor-deck.pptx'
    source.write_bytes(b'presentation')
    item = ServiceItem(None)
    item.name = 'presentations'
    item.title = 'Survivor'
    item.add_capability(ItemCapabilities.CanEditTitle)
    item.add_from_command(str(tmp_path), 'Survivor', 'thumbnail.png', file_hash=sha256_file_hash(source))

    assert item.is_valid
    assert item.title == 'Survivor'
    assert item.get_frame_path() == source


def test_large_native_presentation_validates_once(media_item, tmp_path):
    source = tmp_path / 'large-deck.pptx'
    source.write_bytes(b'presentation')
    slide_count = 125
    document = MagicMock()
    document.get_thumbnail_path.side_effect = lambda number, exists: (
        tmp_path / f'slide{number}.png' if number <= slide_count else None
    )
    document.get_titles_and_notes.return_value = ([], [])
    document.get_sha256_file_hash.return_value = 'source-hash'
    controller = MagicMock()
    controller.add_document.return_value = document
    media_item.controllers = {'Powerpoint': controller}
    media_item.find_controller_by_type = MagicMock(return_value='Powerpoint')
    media_item.display_type_combo_box = MagicMock()
    media_item.display_type_combo_box.currentText.return_value = 'Powerpoint'
    media_item.display_type_combo_box.itemData.return_value = 'automatic'
    tree_item = QtWidgets.QTreeWidgetItem(None)
    tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, Item(id=1, file_path=str(source)))
    service_item = ServiceItem(None)
    service_item.name = 'presentations'

    with patch.object(service_item, 'validate_item', wraps=service_item.validate_item) as validate:
        assert media_item.generate_slide_data(service_item, item=tree_item)

    assert len(service_item.slides) == slide_count
    assert service_item.is_valid
    validate.assert_called_once()
    document.get_sha256_file_hash.assert_called_once()


def test_powerpoint_mac_keeps_the_full_slide_range_available():
    from openlp.plugins.presentations.lib.powerpointmaccontroller import POWERPOINT_MAC_APPLESCRIPT

    handler = POWERPOINT_MAC_APPLESCRIPT.split('on start_presentation(', 1)[1].split(
        'end start_presentation', 1)[0]
    assert 'set range type of slide show settings of targetPresentation to slide show range show all' in handler
    assert 'set starting slide of slide show settings of targetPresentation to startingSlide' not in handler
    assert 'run slide show slide show settings of targetPresentation' in handler
    assert 'current show position of slide show view of showWindow' in handler
    assert 'on goto_slide(' not in POWERPOINT_MAC_APPLESCRIPT


def test_powerpoint_mac_opens_through_launch_services(tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import (
        POWERPOINT_MAC_APPLESCRIPT, _open_powerpoint_document)

    path = tmp_path / 'slides.pptx'
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.subprocess.run') as run:
        _open_powerpoint_document(path)

    run.assert_called_once_with(
        ['/usr/bin/open', '-g', '-b', 'com.microsoft.Powerpoint', str(path)],
        check=True, capture_output=True, text=True)
    assert 'open documentPath' not in POWERPOINT_MAC_APPLESCRIPT


def test_powerpoint_mac_captures_slideshow_window(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        controller = MagicMock()
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    image = MagicMock()
    document._captured_image = image
    document._start_window_capture = MagicMock()
    pixmap = MagicMock()
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.QPixmap.fromImage', return_value=pixmap):
        assert document.attempt_screenshot(0) == (True, pixmap)
    document._start_window_capture.assert_called_once_with()
    controller.applescript.call.assert_not_called()


def test_powerpoint_mac_ignores_capture_frames_during_slide_jump(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(MagicMock(), tmp_path / 'slides.pptx')
    frame = MagicMock()
    frame.isValid.return_value = True
    frame.toImage.return_value.isNull.return_value = False
    document._capture_resume_at = float('inf')

    document._on_video_frame(frame)
    assert document.attempt_screenshot(1) == (False, None)
    assert document._captured_image is None
    frame.toImage.assert_not_called()

    document._capture_resume_at = 0.0
    document._on_video_frame(frame)
    assert document._captured_image is frame.toImage.return_value


def test_powerpoint_mac_selects_matching_slideshow_window(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(MagicMock(), tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    other = MagicMock()
    other.description.return_value = 'PowerPoint Slide Show – [other]'
    matching = MagicMock()
    matching.description.return_value = 'PowerPoint Slide Show – [slides]'
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.QWindowCapture') as capture_class, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.QMediaCaptureSession'), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.QVideoSink'):
        capture_class.capturableWindows.return_value = [other, matching]
        document._start_window_capture()
        capture_class.return_value.setWindow.assert_called_once_with(matching)
        capture_class.return_value.start.assert_called_once_with()


def test_powerpoint_mac_export_runs_with_gui_event_loop(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    class FinishedExport(QtCore.QThread):
        def __init__(self, source_path, source_name, thumbnail_folder):
            super().__init__()
            self.error = None

        def run(self):
            pass

    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(MagicMock(), tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.get_thumbnail_folder = MagicMock(return_value=tmp_path)
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._PowerPointThumbnailExport', FinishedExport), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document'):
        assert document._export_thumbnails()


def test_powerpoint_mac_reexports_when_cache_has_no_slide(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    (tmp_path / 'titles.txt').write_text('Old export metadata')
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(MagicMock(), tmp_path / 'slides.pptx')
    document.get_thumbnail_folder = MagicMock(return_value=tmp_path)
    document.get_thumbnail_path = MagicMock(side_effect=lambda number, exists:
                                            tmp_path / f'slide{number}.png'
                                            if (tmp_path / f'slide{number}.png').is_file() else None)

    def export():
        (tmp_path / 'slide1.png').write_bytes(b'cached image')
        return True

    document._export_thumbnails = MagicMock(side_effect=export)

    assert document.load_presentation()
    assert document.slide_count == 1
    document._export_thumbnails.assert_called_once_with()


def test_powerpoint_mac_starts_on_selected_slide(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    controller.applescript.call.side_effect = lambda name, *args: (
        1 if name == 'start_presentation' else 'PowerPoint Slide Show – [slides]')
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.ui_slidenumber = 3
    document.use_slide_timings = True
    document.get_slide_number = MagicMock(side_effect=[1, 3, 3])
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.ScreenList') as screens, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document') \
            as open_document, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._send_slide_number_to_powerpoint',
                  return_value=True) as send_slide_number:
        screen = screens.return_value.current.display_geometry
        screen.top.return_value = 10
        screen.left.return_value = 20
        screen.width.return_value = 1200
        screen.height.return_value = 700
        screens.return_value.current.custom_geometry = None
        document.start_presentation()

    open_document.assert_called_once_with(document.file_path)
    assert controller.applescript.call.call_args_list[0].args == (
        'start_presentation', 'slides.pptx', 10, 20, 1200, 700, 3, False, True)
    assert not any(call.args[0] == 'position_slide_show' for call in controller.applescript.call.call_args_list)
    send_slide_number.assert_called_once_with(3)
    assert not any(call.args[0] == 'goto_slide' for call in controller.applescript.call.call_args_list)
    assert document._slideshow_started
    assert document._starting_slide == 1


def test_powerpoint_mac_keeps_running_if_initial_slide_jump_fails(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    controller.applescript.call.side_effect = lambda name, *args: (
        1 if name == 'start_presentation' else 'PowerPoint Slide Show – [slides]')
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.ui_slidenumber = 3
    document.goto_slide = MagicMock(return_value=False)
    document.get_slide_number = MagicMock(return_value=1)

    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.ScreenList'), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document'):
        document.start_presentation()

    document.goto_slide.assert_called_once_with(3)
    assert document._slideshow_started
    assert document.presentation_loaded


def test_powerpoint_escape_marks_live_output_hidden(settings, tmp_path):
    from openlp.core.common.registry import Registry
    from openlp.core.ui import HideMode
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    source = tmp_path / 'slides.pptx'
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(MagicMock(), source)
    document.file_path = source
    document._slideshow_started = True
    document.is_active = MagicMock(return_value=False)
    live = MagicMock()
    live.service_item.processor = 'PowerPointMac'
    live.service_item.get_frame_path.return_value = source
    Registry().register('live_controller', live)

    document.poll_slidenumber(True, None)

    document.controller.applescript.call.assert_called_once_with('hide_application')
    live.set_hide_mode.assert_called_once_with(HideMode.Screen)
    assert not document._slideshow_started


def test_powerpoint_mac_logo_hides_and_restores_same_show(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import (
        POWERPOINT_MAC_APPLESCRIPT, PowerPointMacDocument)

    source = tmp_path / 'slides.pptx'
    native = MagicMock()
    native.applescript.call.side_effect = lambda name, *args: (
        'PowerPoint Slide Show – [slides]' if name == 'get_slide_show_window_title' else None)
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(native, source)
    document.file_path = source
    document._stop_window_capture = MagicMock()

    document.hide_for_overlay()
    assert document._hidden_for_overlay
    document.show_after_overlay()

    assert not document._hidden_for_overlay
    assert document._slideshow_window_title == 'PowerPoint Slide Show – [slides]'
    document._stop_window_capture.assert_called_once_with()
    assert native.applescript.call.call_args_list == [
        call('hide_application'), call('show_application'),
        call('get_slide_show_window_title', 'slides.pptx')]
    active_handler = POWERPOINT_MAC_APPLESCRIPT.split('on is_active(', 1)[1].split('end is_active', 1)[0]
    assert 'showState is slide show state black screen' in active_handler


def test_powerpoint_mac_can_disable_slide_timings(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    settings.setValue('presentations/powerpoint use slide timings', QtCore.Qt.CheckState.Unchecked)
    controller = MagicMock()
    controller.applescript.call.return_value = 1
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.ui_slidenumber = 1
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.ScreenList'), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document'):
        document.start_presentation()

    start_call = controller.applescript.call.call_args_list[0]
    assert start_call.args[0] == 'start_presentation'
    assert start_call.args[-2] is False


def test_powerpoint_mac_timed_deck_starts_with_manual_advance(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    controller.applescript.call.side_effect = lambda name, *args: (
        1 if name == 'start_presentation' else 'PowerPoint Slide Show – [slides]')
    # Other tests may import this module while QtCore.QTimer is patched. Use the real timer here.
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.QTimer', QTimer):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.slide_count = 1
    document.ui_slidenumber = 1
    document.get_slide_number = MagicMock(return_value=1)
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._read_slide_advance_times',
               return_value=[2000]), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.ScreenList') as screens, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document'):
        screens.return_value.current.custom_geometry = None
        document.start_presentation()

    assert document._use_openlp_timing
    assert document.use_slide_timings is False
    assert controller.applescript.call.call_args_list[0].args[-2:] == (False, True)
    assert not document._automatic_slide_timer.isActive()


def test_powerpoint_mac_jumps_back_without_restarting(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document._starting_slide = 3
    document.get_slide_number = MagicMock(side_effect=[3, 2])
    controller.applescript.call.return_value = 'PowerPoint Slide Show – [slides]'

    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._send_slide_number_to_powerpoint',
               return_value=True) as send_slide_number:
        assert document.goto_slide(2)

    controller.applescript.call.assert_called_once_with('is_slide_show_window_active', 'slides.pptx')
    send_slide_number.assert_called_once_with(2)
    assert document.ui_slidenumber == 2


def test_powerpoint_mac_jumps_to_distant_slide_without_restarting(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.get_slide_number = MagicMock(side_effect=[1, 80])
    document.start_presentation = MagicMock()
    controller.applescript.call.return_value = 'PowerPoint Slide Show – [slides]'

    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._send_slide_number_to_powerpoint',
               return_value=True) as send_slide_number:
        assert document.goto_slide(80)

    controller.applescript.call.assert_called_once_with('is_slide_show_window_active', 'slides.pptx')
    send_slide_number.assert_called_once_with(80)
    document.start_presentation.assert_not_called()
    assert document.ui_slidenumber == 80


def test_powerpoint_mac_does_not_walk_slides_when_number_shortcut_is_unavailable(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    controller.applescript.call.return_value = 'PowerPoint Slide Show – [slides]'
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.get_slide_number = MagicMock(return_value=1)
    document.ui_slidenumber = 80
    document.slide_number = 80

    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._send_slide_number_to_powerpoint',
               return_value=False) as send_slide_number, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.has_post_event_access',
                  return_value=False), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.accessibility_target_name',
                  return_value='Example IDE'), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.Registry') as registry:
        assert not document.goto_slide(80)
        registry.return_value.get.return_value.show_status_message.assert_called_once_with(
            'Could not select a PowerPoint slide. Allow Example IDE in macOS Accessibility settings.', 10000)

    controller.applescript.call.assert_called_once_with('is_slide_show_window_active', 'slides.pptx')
    send_slide_number.assert_called_once_with(80)
    assert document.ui_slidenumber == 1
    assert document.slide_number == 0


def test_powerpoint_mac_does_not_type_into_inactive_slideshow(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    controller.applescript.call.return_value = False
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.get_slide_number = MagicMock(return_value=1)

    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._send_slide_number_to_powerpoint') as send, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.Registry'):
        assert not document.goto_slide(4)

    controller.applescript.call.assert_called_once_with('is_slide_show_window_active', 'slides.pptx')
    send.assert_not_called()


def test_powerpoint_mac_jumps_past_builds_without_restarting(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.get_slide_number = MagicMock(side_effect=[1, 2])
    controller.applescript.call.return_value = 'PowerPoint Slide Show – [slides]'

    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._send_slide_number_to_powerpoint',
               return_value=True):
        assert document.goto_slide(2)

    controller.applescript.call.assert_called_once_with('is_slide_show_window_active', 'slides.pptx')
    assert document.ui_slidenumber == 2


def test_powerpoint_mac_timing_toggle_does_not_restart_slideshow(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    controller = MagicMock()
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document._use_openlp_timing = True
    document._slide_advance_times = [4000, 2000]
    document._slideshow_started = True
    document.get_slide_number = MagicMock(return_value=1)
    document._automatic_slide_timer = MagicMock()
    document.use_slide_timings = True
    document.start_presentation = MagicMock()

    assert document.set_slide_timings(False)
    assert document.set_slide_timings(True)

    document._automatic_slide_timer.stop.assert_called()
    document._automatic_slide_timer.start.assert_called_once_with(4000)
    controller.applescript.call.assert_not_called()
    document.start_presentation.assert_not_called()


def test_powerpoint_mac_auto_advance_selects_next_slide_without_restarting(settings, tmp_path):
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacDocument

    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(MagicMock(), tmp_path / 'slides.pptx')
    document._use_openlp_timing = True
    document._slide_advance_times = [4000, 2000]
    document._slideshow_started = True
    document.use_slide_timings = True
    document.get_slide_number = MagicMock(return_value=1)
    document.goto_slide = MagicMock(return_value=True)
    document.poll_slidenumber = MagicMock()

    document._advance_automatically()

    document.goto_slide.assert_called_once_with(2)
    document.poll_slidenumber.assert_called_once_with(True, None)


def test_powerpoint_mac_reads_slide_timings_in_presentation_order(tmp_path):
    from zipfile import ZipFile
    from openlp.plugins.presentations.lib.powerpointmaccontroller import _read_slide_advance_times

    source = tmp_path / 'timed.pptx'
    with ZipFile(source, 'w') as package:
        package.writestr('ppt/presentation.xml', '''<p:presentation
            xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
            <p:sldIdLst><p:sldId r:id="rId2"/><p:sldId r:id="rId1"/></p:sldIdLst>
            </p:presentation>''')
        package.writestr('ppt/_rels/presentation.xml.rels', '''<Relationships
            xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
            <Relationship Id="rId1" Target="slides/slide1.xml"/>
            <Relationship Id="rId2" Target="slides/slide2.xml"/>
            </Relationships>''')
        package.writestr('ppt/slides/slide1.xml', '''<p:sld
            xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
            <p:transition advTm="2000"/></p:sld>''')
        package.writestr('ppt/slides/slide2.xml', '''<p:sld
            xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
            <p:transition advTm="4000"/></p:sld>''')

    assert _read_slide_advance_times(source) == [4000, 2000]
