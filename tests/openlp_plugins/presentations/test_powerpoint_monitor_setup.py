"""Fullscreen PowerPoint monitor selection and its manual setup action."""
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest
from PySide6 import QtCore

from openlp.core.common.registry import Registry
from openlp.core.display.screens import Screen
from openlp.plugins.presentations.lib.db import Item
from openlp.plugins.presentations.lib.powerpointmaccontroller import (
    PowerPointMacController, PowerPointMacDocument, _keep_operator_window_on_top, _powerpoint_monitor_name)


@pytest.mark.parametrize('previous_level', [0, 150])
@pytest.mark.parametrize('fails', [False, True])
def test_operator_window_level_is_restored_after_native_setup(previous_level, fails):
    native_window = MagicMock()
    native_window.level.return_value = previous_level
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._operator_native_window',
               return_value=native_window), \
            patch.dict('sys.modules', {'AppKit': SimpleNamespace(NSPopUpMenuWindowLevel=101)}):
        try:
            with _keep_operator_window_on_top():
                native_window.setLevel_.assert_called_once_with(max(previous_level, 102))
                native_window.orderFrontRegardless.assert_called_once()
                if fails:
                    raise RuntimeError('PowerPoint setup failed')
        except RuntimeError:
            assert fails
    assert [call.args[0] for call in native_window.setLevel_.call_args_list] == [
        max(previous_level, 102), previous_level]


def test_operator_window_guard_does_not_block_launch_when_native_window_unavailable():
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._operator_native_window',
               side_effect=RuntimeError('Native window unavailable')):
        with _keep_operator_window_on_top():
            reached_launch = True
    assert reached_launch


@pytest.mark.parametrize('secondary_x,secondary_y', [(-1920, 0), (1920, 0), (0, -1080)])
def test_monitor_selection_does_not_use_qt_screen_order(secondary_x, secondary_y):
    primary = Screen(1, QtCore.QRect(0, 0, 1920, 1080), is_primary=True)
    secondary = Screen(0, QtCore.QRect(secondary_x, secondary_y, 1920, 1080))
    screens = [secondary, primary]
    assert _powerpoint_monitor_name(primary, screens) == 'Primary Monitor'
    assert _powerpoint_monitor_name(secondary, screens) == 'Monitor 2'


def test_monitor_selection_rejects_ambiguous_secondary_screens():
    primary = Screen(0, QtCore.QRect(0, 0, 1920, 1080), is_primary=True)
    second = Screen(1, QtCore.QRect(1920, 0, 1920, 1080))
    third = Screen(2, QtCore.QRect(-1920, 0, 1920, 1080))
    assert _powerpoint_monitor_name(primary, [primary, second, third]) == 'Primary Monitor'
    with pytest.raises(RuntimeError, match='cannot be matched'):
        _powerpoint_monitor_name(second, [primary, second, third])


def test_controller_selects_monitor_for_requested_deck(tmp_path):
    controller = object.__new__(PowerPointMacController)
    controller.applescript = MagicMock()
    primary = Screen(0, QtCore.QRect(0, 0, 1920, 1080), is_primary=True)
    path = tmp_path / 'slides.pptx'
    controller.configure_slide_show_monitor(path, primary, [primary])
    controller.applescript.call.assert_called_once_with('select_slide_show_monitor', path.name, 'Primary Monitor')


def test_controller_opens_settings_without_starting_a_show(tmp_path):
    controller = object.__new__(PowerPointMacController)
    controller.applescript = MagicMock()
    path = tmp_path / 'slides.pptx'
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document') as open_document:
        controller.show_slide_show_settings(path)
    open_document.assert_called_once_with(path)
    controller.applescript.call.assert_called_once_with('show_slide_show_settings', path.name)


@pytest.mark.parametrize('manual', [False, True])
def test_monitor_selection_failure_does_not_launch_on_wrong_screen(settings, tmp_path, manual):
    settings.setValue('presentations/powerpoint auto select display',
                      QtCore.Qt.CheckState.Unchecked if manual else QtCore.Qt.CheckState.Checked)
    controller = MagicMock()
    controller.applescript.call.return_value = 1
    controller.configure_slide_show_monitor.side_effect = RuntimeError('Cannot select monitor')
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.ui_slidenumber = 1
    main_window = MagicMock()
    Registry().register('main_window', main_window)
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.ScreenList') as screens, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document'), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._read_slide_advance_times',
                  return_value=[]):
        screens.return_value.current.custom_geometry = None
        document.start_presentation()
    assert document._slideshow_started is manual
    if manual:
        controller.configure_slide_show_monitor.assert_not_called()
        assert controller.applescript.call.call_args_list[0].args[-2] is True
    else:
        controller.applescript.call.assert_not_called()
        main_window.show_status_message.assert_called_once()


@pytest.fixture
def monitor_document(settings, tmp_path):
    controller = MagicMock()
    controller.applescript.call.return_value = 1
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = PowerPointMacDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.ui_slidenumber = 1
    primary = Screen(0, QtCore.QRect(0, 0, 1920, 1080), is_primary=True)
    output = Screen(1, QtCore.QRect(1920, 0, 1920, 1080))
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.ScreenList') as screens, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._open_powerpoint_document') \
            as open_deck, \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller._read_slide_advance_times',
                  return_value=[]):
        screens.return_value.current = output
        screens.return_value.__iter__.side_effect = lambda: iter([primary, output])
        yield document, screens, open_deck


def test_failed_monitor_setup_is_not_retried_by_slide_clicks(monitor_document):
    from openlp.plugins.presentations.lib.messagelistener import Controller

    document, screens, open_deck = monitor_document
    document.controller.configure_slide_show_monitor.side_effect = RuntimeError('Monitor unavailable')
    document.is_active = MagicMock(return_value=False)
    document.is_loaded = MagicMock(return_value=True)
    listener = Controller(True)
    listener.doc = document
    for slide in (0, 1, 2):
        listener.slide(slide)
    document.controller.configure_slide_show_monitor.assert_called_once()
    open_deck.assert_called_once()
    document.controller.applescript.call.assert_not_called()
    assert not document._opening

    # An explicit stop/restart allows a fresh setup attempt.
    document.stop_presentation()
    listener.slide(0)
    assert document.controller.configure_slide_show_monitor.call_count == 2


def test_monitor_setup_is_reused_until_output_changes(monitor_document):
    document, screens, open_deck = monitor_document
    document.start_presentation()
    document.start_presentation()
    document.controller.configure_slide_show_monitor.assert_called_once()
    assert document._slideshow_started

    screens.return_value.current = list(screens.return_value)[0]
    document.start_presentation()
    assert document.controller.configure_slide_show_monitor.call_count == 2


def test_fullscreen_uses_separate_displays_with_two_monitors(monitor_document):
    document, screens, open_deck = monitor_document
    document.start_presentation()
    launch = document.controller.applescript.call.call_args_list[0]
    assert launch.args[0] == 'start_presentation'
    assert launch.args[-2:] == (True, True)


def test_single_monitor_does_not_launch_presenter_view(monitor_document):
    document, screens, open_deck = monitor_document
    primary = list(screens.return_value)[0]
    screens.return_value.current = primary
    screens.return_value.__iter__.side_effect = lambda: iter([primary])
    document.start_presentation()
    launch = document.controller.applescript.call.call_args_list[0]
    assert launch.args[0] == 'start_presentation'
    assert launch.args[-2:] == (True, False)


def test_manual_override_recovers_from_failed_monitor_setup(monitor_document, settings):
    document, screens, open_deck = monitor_document
    document.controller.configure_slide_show_monitor.side_effect = RuntimeError('Monitor unavailable')
    document.start_presentation()
    settings.setValue('presentations/powerpoint auto select display', QtCore.Qt.CheckState.Unchecked)
    document.start_presentation()
    assert document._slideshow_started
    document.controller.configure_slide_show_monitor.assert_called_once()


def test_native_setup_cannot_reenter_launch(monitor_document):
    document, screens, open_deck = monitor_document
    document.controller.configure_slide_show_monitor.side_effect = lambda *args: document.start_presentation()
    document.start_presentation()
    document.controller.configure_slide_show_monitor.assert_called_once()
    open_deck.assert_called_once()
    assert document._slideshow_started
    assert not document._opening


@pytest.mark.parametrize('suffix,enabled,multiple,valid', [
    ('pptx', True, False, True), ('ppt', True, False, True), ('pdf', True, False, False),
    ('pptx', False, False, False), ('pptx', True, True, False)
])
def test_settings_action_only_targets_one_powerpoint_deck(media_item, tmp_path, suffix, enabled, multiple, valid):
    path = tmp_path / ('slides.' + suffix)
    path.write_bytes(b'presentation')
    item = MagicMock()
    item.data.return_value = Item(file_path=str(path), name=path.name)
    media_item.list_view = MagicMock()
    media_item.list_view.selectedItems.return_value = [item, item] if multiple else [item]
    controller = MagicMock()
    controller.enabled.return_value = enabled
    media_item.controllers = {'PowerPointMac': controller}

    media_item.on_powerpoint_slide_show_settings()

    if valid:
        controller.show_slide_show_settings.assert_called_once_with(path)
    else:
        controller.show_slide_show_settings.assert_not_called()
