"""Live preview fallback for an external presentation window."""
from pathlib import Path
from threading import Lock
from unittest.mock import MagicMock, patch

from opal.core.lib import ItemCapabilities
from opal.core.common.registry import Registry
from opal.core.ui import HideMode
from opal.core.ui.slidecontroller import SlideController


def test_failed_native_capture_uses_selected_slide_thumbnail(settings, tmp_path):
    thumbnail = tmp_path / 'slide2.png'
    thumbnail.touch()
    controller = SlideController(None)
    controller.service_item = MagicMock()
    controller.service_item.is_capable.return_value = True
    controller.service_item.get_rendered_frame.return_value = thumbnail
    controller.selected_row = 1
    controller.preview_display = MagicMock()
    controller._capture_maindisplay = MagicMock(return_value=None)

    controller.display_maindisplay()

    controller.service_item.is_capable.assert_called_once_with(ItemCapabilities.ProvidesOwnDisplay)
    controller.service_item.get_rendered_frame.assert_called_once_with(1)
    controller.preview_display.set_single_image.assert_called_once_with('#000', thumbnail)
    assert controller.screen_capture == thumbnail


def test_native_presentation_window_capture_precedes_desktop_capture(settings):
    from unittest.mock import patch

    controller = SlideController(None)
    controller.service_item = MagicMock()
    controller.service_item.name = 'presentations'
    controller.service_item.is_capable.return_value = True
    controller.service_item.is_command.return_value = True
    controller.selected_row = 4
    capture = MagicMock()
    capture.isNull.return_value = False
    with patch('opal.core.ui.slidecontroller.Registry') as registry, \
            patch.object(controller, '_capture_maindisplay_desktop') as desktop:
        registry.return_value.has_function.return_value = True
        registry.return_value.execute.return_value = [(True, capture)]
        assert controller._capture_maindisplay() is capture
    registry.return_value.execute.assert_called_once_with('presentations_attempt_screenshot',
                                                          [controller.service_item, 4])
    desktop.assert_not_called()


def test_mac_powerpoint_keeps_previous_frame_when_window_capture_fails(settings, tmp_path):
    from unittest.mock import patch

    thumbnail = tmp_path / 'slide5.png'
    thumbnail.touch()
    controller = SlideController(None)
    controller.service_item = MagicMock()
    controller.service_item.name = 'presentations'
    controller.service_item.processor = 'PowerPointMac'
    controller.service_item.is_capable.return_value = True
    controller.service_item.is_command.return_value = True
    controller.service_item.get_rendered_frame.return_value = thumbnail
    controller.selected_row = 4
    controller.screen_capture = b'previous live capture'
    controller.preview_display = MagicMock()
    with patch('opal.core.ui.slidecontroller.Registry') as registry, \
            patch('opal.core.ui.slidecontroller.is_macosx', return_value=True), \
            patch.object(controller, '_capture_maindisplay_desktop') as desktop:
        registry.return_value.has_function.return_value = True
        registry.return_value.execute.return_value = [(False, None)]
        controller.display_maindisplay()
    desktop.assert_not_called()
    controller.preview_display.set_single_image.assert_not_called()
    controller.preview_display.set_single_image_data.assert_not_called()
    assert controller.screen_capture == b'previous live capture'


def test_mac_powerpoint_live_pane_holds_capture_during_slide_change(settings, tmp_path):
    import datetime
    from unittest.mock import patch

    thumbnail = tmp_path / 'slide3.png'
    thumbnail.write_bytes(b'cached image')
    controller = SlideController(None)
    controller.is_live = True
    controller.service_item = MagicMock()
    controller.service_item.processor = 'PowerPointMac'
    controller.service_item.is_capable.return_value = True
    controller.service_item.get_rendered_frame.return_value = thumbnail
    controller.selected_row = 2
    controller.screen_capture = b'previous live capture'
    controller.slide_changed_time = datetime.datetime.now()
    controller.preview_display = MagicMock()
    controller.preview_display.hide_mode = False
    controller._current_hide_mode = None
    controller._schedule_live_preview_capture = MagicMock()
    controller._update_desktop_capture_timer = MagicMock()
    controller.output_has_changed = MagicMock()

    with patch('opal.core.ui.slidecontroller.is_macosx', return_value=True):
        controller.update_preview()

    controller.service_item.get_rendered_frame.assert_not_called()
    controller.preview_display.set_single_image.assert_not_called()
    controller._schedule_live_preview_capture.assert_called_once_with()
    controller._update_desktop_capture_timer.assert_called_once_with(True)
    assert controller.screen_capture == b'previous live capture'


def test_mac_powerpoint_live_pane_recovers_from_logo(settings, tmp_path):
    import datetime
    from unittest.mock import patch

    thumbnail = tmp_path / 'slide3.png'
    thumbnail.write_bytes(b'cached image')
    controller = SlideController(None)
    controller.is_live = True
    controller.service_item = MagicMock()
    controller.service_item.processor = 'PowerPointMac'
    controller.service_item.is_capable.return_value = True
    controller.service_item.get_rendered_frame.return_value = thumbnail
    controller.selected_row = 2
    controller.slide_changed_time = datetime.datetime.now()
    controller.preview_display = MagicMock()
    controller.preview_display.hide_mode = HideMode.Logo
    controller._current_hide_mode = HideMode.Logo
    controller._schedule_live_preview_capture = MagicMock()
    controller._update_desktop_capture_timer = MagicMock()
    controller.output_has_changed = MagicMock()

    with patch('opal.core.ui.slidecontroller.is_macosx', return_value=True):
        controller.update_preview()

    controller.preview_display.hide_display.assert_not_called()
    controller.preview_display.set_single_image.assert_not_called()
    controller.preview_display.show_display.assert_not_called()

    # Keep Logo up until a fresh native frame is ready after unblanking.
    controller._current_hide_mode = None
    controller._capture_maindisplay = MagicMock(return_value='new capture')
    with patch('opal.core.ui.slidecontroller.is_macosx', return_value=True), \
            patch('opal.core.ui.slidecontroller.image_to_byte', return_value=b'new capture'):
        controller.update_preview()
        controller.display_maindisplay()

    controller.preview_display.show_display.assert_called_once_with()


def test_presentation_preview_uses_generated_image(settings, tmp_path):
    thumbnail = tmp_path / 'slide2.png'
    thumbnail.write_bytes(b'cached image')
    controller = SlideController(None)
    controller.is_live = False
    controller.service_item = MagicMock()
    controller.service_item.is_capable.return_value = True
    controller.service_item.get_rendered_frame.return_value = thumbnail
    controller.selected_row = 1
    controller.preview_display = MagicMock()
    controller._capture_maindisplay = MagicMock()
    controller.output_has_changed = MagicMock()

    controller.update_preview()

    controller.preview_display.set_single_image.assert_called_once_with('#000', thumbnail)
    controller._capture_maindisplay.assert_not_called()


def test_presentation_preview_loads_and_selects_cached_slides(settings, tmp_path):
    images = [tmp_path / 'slide1.png', tmp_path / 'slide2.png']
    for image in images:
        image.write_bytes(b'cached slide')
    item = MagicMock()
    item.name = 'presentations'
    item.title = 'Slides'
    item.slides = [{'image': image} for image in images]
    item.get_rendered_frame.side_effect = lambda index: images[index]
    item.is_command.return_value = True
    item.is_media.return_value = False
    item.is_text.return_value = False
    item.is_image.return_value = False
    item.is_capable.side_effect = lambda capability: capability == ItemCapabilities.ProvidesOwnDisplay
    item.requires_media.return_value = False
    item.from_service = False
    main_window = MagicMock()
    main_window.control_splitter.sizes.return_value = [600]
    Registry().register('main_window', main_window)
    controller = SlideController(None)
    controller.service_item = None
    controller.split = 0
    controller.type_prefix = 'preview'
    controller._current_hide_mode = None
    controller.preview_widget = MagicMock()
    controller.preview_display = MagicMock()
    controller.preview_display.hide_mode = False
    controller.info_label = MagicMock()
    controller.displays = []
    controller.on_stop_loop = MagicMock()
    controller._set_theme = MagicMock()
    controller.enable_tool_bar = MagicMock()
    controller.slide_selected = MagicMock()
    controller._update_slide_action_enabled_state = MagicMock()
    controller.output_has_changed = MagicMock()

    with patch.object(Registry, 'execute'):
        controller._process_item(item, 0)
    controller.preview_widget.current_slide_number.return_value = 1
    controller.preview_widget.slide_count.return_value = 2
    controller.slide_selected_lock = Lock()
    with patch.object(Registry, 'execute'):
        SlideController.slide_selected(controller)

    controller.preview_display.load_images.assert_called_once_with([{'path': images[0]}, {'path': images[1]}])
    assert controller.selected_row == 1
    controller.preview_display.go_to_slide.assert_called_once_with(1)
    controller.preview_display.set_single_image.assert_not_called()


def test_automatic_slide_change_previews_new_row(settings):
    controller = SlideController(None)
    controller.preview_widget = MagicMock()
    selected_during_refresh = []
    controller.update_preview = MagicMock(side_effect=lambda: selected_during_refresh.append(controller.selected_row))

    controller.on_slide_change(7)

    assert selected_during_refresh == [7]
