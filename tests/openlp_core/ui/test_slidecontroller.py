# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
Package to test the openlp.core.ui.slidecontroller package.
"""
from collections import namedtuple
import datetime
from time import perf_counter

from unittest.mock import MagicMock, call, patch, sentinel

from PySide6 import QtCore, QtGui
from pytest import mark

from openlp.core.state import State
from openlp.core.common import ThemeLevel
from openlp.core.common.enum import ServiceItemType
from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.core.common.utils import wait_for
from openlp.core.lib import ItemCapabilities, ServiceItemAction
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.lib.theme import TransitionSpeed, TransitionType
from openlp.core.ui import HideMode
from openlp.core.ui.media import MediaState, MediaType
from openlp.core.ui.slidecontroller import DESKTOP_CAPTURE_INTERVAL_MS, NON_TEXT_MENU, WIDE_MENU, NARROW_MENU, \
    InfoLabel, LiveController, PreviewController, SlideController


def test_initial_slide_controller(registry: Registry, settings: Settings):
    """
    Test the initial slide controller state .
    """
    # GIVEN: A new SlideController instance.
    slide_controller = SlideController(None)

    # WHEN: the default controller is built.
    # THEN: The controller should not be a live controller.
    assert slide_controller.is_live is False, 'The base slide controller should not be a live controller'


def test_is_slide_loaded(settings: Settings):
    """
    Test the slide is loaded method
    """
    # GIVEN: A new SlideController and ServiceItem instance with a transition of half a second.
    slide_controller = SlideController(None)
    service_item = ServiceItem(None)
    service_item.add_capability(ItemCapabilities.ProvidesOwnDisplay)
    service_item.theme = 'song_theme'
    mocked_theme_manager = MagicMock()
    mocked_theme_manager.global_theme = 'global_theme'
    Registry().register('theme_manager', mocked_theme_manager)
    settings.setValue('servicemanager/service theme', 'service_theme')
    settings.setValue('themes/theme level', ThemeLevel.Global)
    slide_controller.song_edit = False
    slide_controller.service_item = service_item
    slide_controller._current_hide_mode = None
    slide_controller.slide_changed_time = datetime.datetime.now()

    start = perf_counter()

    # WHEN: The is_slide_loaded method is repeatedly run
    wait_for(slide_controller.is_slide_loaded)

    stop = perf_counter()

    # THEN: The elapsed time should be approximately half a second
    elapsed_time = round(stop - start, 2)
    assert elapsed_time > 0.4 and elapsed_time < 0.6

    # GIVEN: The presentation screen is hidden
    slide_controller.is_live = True
    slide_controller._current_hide_mode = HideMode.Blank
    slide_controller.slide_changed_time = datetime.datetime.now()
    start = perf_counter()

    # WHEN: The is_slide_loaded method is repeatedly run
    wait_for(slide_controller.is_slide_loaded)

    stop = perf_counter()

    # THEN: The elapsed time should be one second
    assert round(stop - start, 2) == 1


def test_slide_selected(settings: Settings):
    """
    Test the slide selected method
    """
    # GIVEN: A new SlideController instance on slide 4 of 10, and is not a command
    slide_controller = SlideController(None)
    slide_controller.update_preview = MagicMock()
    slide_controller.slide_selected_lock = MagicMock()
    slide_controller.service_item = MagicMock()
    slide_controller.service_item.is_command.return_value = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_widget.slide_count.return_value = 10
    slide_controller.preview_widget.current_slide_number.return_value = 4
    mocked_display = MagicMock()
    slide_controller.displays = [mocked_display]

    # WHEN: The slide_selected method is run
    slide_controller.slide_selected(True)

    # THEN: The display is updated with the slide number
    mocked_display.go_to_slide.assert_called_once_with(4, raise_window=True)


def test_preview_presentation_next_previous_select_cached_slide(settings: Settings):
    """The Preview arrow actions select slides without controlling a native show."""
    controller = SlideController(None)
    controller.service_item = MagicMock()
    controller.service_item.is_command.return_value = True
    controller.preview_widget = MagicMock()
    controller.preview_widget.slide_count.return_value = 3
    controller.preview_widget.current_slide_number.side_effect = [1, 2]
    controller.slide_selected = MagicMock()

    with patch.object(Registry, 'execute') as execute:
        controller.on_slide_selected_next()
        controller.on_slide_selected_previous()

    assert controller.preview_widget.change_slide.call_args_list == [call(2), call(1)]
    assert controller.slide_selected.call_count == 2
    execute.assert_not_called()


def test_slide_selected_does_not_raise_display_when_restore_focus_disabled(settings: Settings):
    """
    Test that slide_selected() can update a slide without raising the display window.
    """
    # GIVEN: A non-command slide controller with a selected slide
    slide_controller = SlideController(None)
    slide_controller.update_preview = MagicMock()
    slide_controller.slide_selected_lock = MagicMock()
    slide_controller.service_item = MagicMock()
    slide_controller.service_item.is_command.return_value = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_widget.slide_count.return_value = 10
    slide_controller.preview_widget.current_slide_number.return_value = 4
    mocked_display = MagicMock()
    slide_controller.displays = [mocked_display]

    # WHEN: The timed/auto-play style path disables focus restoration
    slide_controller.slide_selected(restore_focus=False)

    # THEN: The display slide changes without requesting a window raise
    mocked_display.go_to_slide.assert_called_once_with(4, raise_window=False)


@mark.parametrize('always_on_top', [False, True])
def test_single_screen_slide_selected_follows_stacking_setting(always_on_top, settings: Settings):
    """Advancing a slide must not cover the controls when normal window stacking is selected."""
    settings.setValue('core/always on top', always_on_top)
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.screens = [object()]
    slide_controller.update_preview = MagicMock()
    slide_controller.slide_selected_lock = MagicMock()
    slide_controller.service_item = MagicMock()
    slide_controller.service_item.is_command.return_value = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_widget.slide_count.return_value = 10
    slide_controller.preview_widget.current_slide_number.return_value = 4
    mocked_display = MagicMock()
    slide_controller.displays = [mocked_display]

    slide_controller.slide_selected(True)

    mocked_display.go_to_slide.assert_called_once_with(4, raise_window=always_on_top)


def test_slide_selected_defers_when_lock_busy(settings: Settings):
    """
    Test that slide_selected() defers a retry instead of dropping input when lock is busy.
    """
    # GIVEN: A slide controller with a busy slide_selected_lock
    slide_controller = SlideController(None)
    slide_controller.slide_selected_lock = MagicMock()
    slide_controller.slide_selected_lock.acquire.return_value = False
    slide_controller.service_item = MagicMock()
    slide_controller.service_item.is_command.return_value = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_widget.current_slide_number.return_value = 2
    slide_controller.preview_widget.slide_count.return_value = 5
    slide_controller.displays = [MagicMock()]

    # WHEN: slide_selected() is called while lock is held
    with patch.object(QtCore.QTimer, 'singleShot') as mocked_single_shot:
        slide_controller.slide_selected()

    # THEN: A deferred retry should be scheduled and no immediate display update should happen
    assert slide_controller._slide_selected_retry_pending is True
    assert slide_controller._slide_selected_retry_scheduled is True
    mocked_single_shot.assert_called_once_with(0, slide_controller._process_pending_slide_selected)
    slide_controller.displays[0].go_to_slide.assert_not_called()


def test_process_pending_slide_selected_consumes_retry(settings: Settings):
    """
    Test that processing deferred slide selection clears flags and retries once.
    """
    # GIVEN: A slide controller with a pending deferred retry
    slide_controller = SlideController(None)
    slide_controller._slide_selected_retry_pending = True
    slide_controller._slide_selected_retry_scheduled = True
    slide_controller.slide_selected = MagicMock()

    # WHEN: The deferred retry callback is executed
    slide_controller._process_pending_slide_selected()

    # THEN: Flags should be reset and slide_selected retried once
    assert slide_controller._slide_selected_retry_pending is False
    assert slide_controller._slide_selected_retry_scheduled is False
    slide_controller.slide_selected.assert_called_once_with()


def test_text_service_item_blank(settings: Settings):
    """
    Test that loading a text-based service item into the slide controller sets the correct blank menu
    """
    # GIVEN: A new SlideController instance.
    slide_controller = SlideController(None)
    service_item = MagicMock()
    toolbar = MagicMock()
    toolbar.set_widget_visible = MagicMock()
    slide_controller.toolbar = toolbar
    slide_controller.service_item = service_item

    # WHEN: a text based service item is used
    slide_controller.service_item.is_text = MagicMock(return_value=True)
    slide_controller.set_hide_mode_menu(narrow=False)

    # THEN: the call to set the visible items on the toolbar should be correct
    toolbar.set_widget_visible.assert_any_call(NARROW_MENU, False)
    toolbar.set_widget_visible.assert_called_with(WIDE_MENU, True)


def test_non_text_service_item_blank(settings: Settings):
    """
    Test that loading a non-text service item into the slide controller sets the correct blank menu
    """
    # GIVEN: A new SlideController instance.
    slide_controller = SlideController(None)
    service_item = MagicMock()
    toolbar = MagicMock()
    toolbar.set_widget_visible = MagicMock()
    slide_controller.toolbar = toolbar
    slide_controller.service_item = service_item

    # WHEN a non text based service item is used
    slide_controller.service_item.is_text = MagicMock(return_value=False)
    slide_controller.set_hide_mode_menu(narrow=False)

    # THEN: then call set up the toolbar to blank the display screen.
    toolbar.set_widget_visible.assert_any_call(NARROW_MENU, False)
    toolbar.set_widget_visible.assert_called_with(NON_TEXT_MENU, True)


def test_text_service_item_blank_narrow(settings: Settings):
    """
    Test that loading a text-based service item into the slide controller sets the correct blank menu
    """
    # GIVEN: A new SlideController instance.
    slide_controller = SlideController(None)
    service_item = MagicMock()
    toolbar = MagicMock()
    toolbar.set_widget_visible = MagicMock()
    slide_controller.toolbar = toolbar
    slide_controller.service_item = service_item

    # WHEN: a text based service item is used
    slide_controller.service_item.is_text = MagicMock(return_value=True)
    slide_controller.set_hide_mode_menu(narrow=True)

    # THEN: the call to set the visible items on the toolbar should be correct
    toolbar.set_widget_visible.assert_any_call(NARROW_MENU, True)
    toolbar.set_widget_visible.assert_any_call(WIDE_MENU, False)


def test_on_controller_size_changed_wide(settings: Settings):
    """
    Test that on_controller_size_changed
    """
    # GIVEN: A new SlideController instance where the toolbar has a lot of spare space.
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.ignore_toolbar_resize_events = False
    slide_controller.controller = MagicMock(width=MagicMock(return_value=100))
    slide_controller.toolbar = MagicMock(
        sizeHint=MagicMock(return_value=MagicMock(width=MagicMock(return_value=10))),
        minimumSizeHint=MagicMock(return_value=MagicMock(width=MagicMock(return_value=10)))
    )
    slide_controller.hide_menu = MagicMock(isVisible=MagicMock(return_value=False))
    slide_controller.set_hide_mode_menu = MagicMock()

    # WHEN: The on_controller_size_changed function is called
    slide_controller.on_controller_size_changed()

    # THEN: set_hide_mode_menu should have received the correct call
    slide_controller.set_hide_mode_menu.assert_called_with(narrow=False)


def test_on_controller_size_changed_narrow(settings: Settings):
    """
    Test that on_controller_size_changed
    """
    # GIVEN: A new SlideController instance where the toolbar has a lot of spare space.
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.ignore_toolbar_resize_events = False
    slide_controller.controller = MagicMock(width=MagicMock(return_value=100))
    slide_controller.toolbar = MagicMock(
        sizeHint=MagicMock(return_value=MagicMock(width=MagicMock(return_value=110))),
        minimumSizeHint=MagicMock(return_value=MagicMock(width=MagicMock(return_value=110)))
    )
    slide_controller.hide_menu = MagicMock(isVisible=MagicMock(return_value=False))
    slide_controller.set_hide_mode_menu = MagicMock()

    # WHEN: The on_controller_size_changed function is called
    slide_controller.on_controller_size_changed()

    # THEN: set_hide_mode_menu should have received the correct call
    slide_controller.set_hide_mode_menu.assert_called_with(narrow=True)


def test_on_controller_size_changed_can_not_expand(settings: Settings):
    """
    Test that on_controller_size_changed
    """
    # GIVEN: A new SlideController instance where the toolbar has a lot of spare space.
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.ignore_toolbar_resize_events = False
    slide_controller.controller = MagicMock(width=MagicMock(return_value=100))
    slide_controller.toolbar = MagicMock(
        sizeHint=MagicMock(return_value=MagicMock(width=MagicMock(return_value=95))),
        minimumSizeHint=MagicMock(return_value=MagicMock(width=MagicMock(return_value=95)))
    )
    slide_controller.hide_menu = MagicMock(isVisible=MagicMock(return_value=True))
    slide_controller.set_hide_mode_menu = MagicMock()

    # WHEN: The on_controller_size_changed function is called
    slide_controller.on_controller_size_changed()

    # THEN: set_hide_mode_menu should have received the correct call
    slide_controller.set_hide_mode_menu.assert_not_called()


def test_receive_spin_delay(mock_settings: MagicMock):
    """
    Test that the spin box is updated accordingly after a call to receive_spin_delay()
    """
    # GIVEN: A new SlideController instance.
    mock_settings.value.return_value = 1
    mocked_delay_spin_box = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.delay_spin_box = mocked_delay_spin_box

    # WHEN: The receive_spin_delay() method is called
    slide_controller.receive_spin_delay()

    # THEN: The settings value() and delay_spin_box.setValue() methods should have been called correctly
    msv = mock_settings.value
    msv.assert_called_with('core/loop delay')
    mocked_delay_spin_box.setValue.assert_called_with(1)


def test_toggle_display_blank(settings: Settings):
    """
    Check that the toggle_display('blank') method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode

    # WHEN: toggle_display() is called with an argument of "blank"
    slide_controller.toggle_display('blank')

    # THEN: set_hide_mode should have been called with an argument of HideMode.Blank
    mocked_set_hide_mode.assert_called_once_with(HideMode.Blank)


def test_toggle_display_hide(settings: Settings):
    """
    Check that the toggle_display('hide') method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode

    # WHEN: toggle_display() is called with an argument of "hide"
    slide_controller.toggle_display('hide')

    # THEN: set_hide_mode should have been called with an argument of HideMode.Blank
    mocked_set_hide_mode.assert_called_once_with(HideMode.Blank)


def test_toggle_display_theme(settings: Settings):
    """
    Check that the toggle_display('theme') method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode

    # WHEN: toggle_display() is called with an argument of "theme"
    slide_controller.toggle_display('theme')

    # THEN: set_hide_mode should have been called with an argument of HideMode.Theme
    mocked_set_hide_mode.assert_called_once_with(HideMode.Theme)


def test_toggle_display_desktop(settings: Settings):
    """
    Check that the toggle_display('desktop') method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode

    # WHEN: toggle_display() is called with an argument of "desktop"
    slide_controller.toggle_display('desktop')

    # THEN: set_hide_mode should have been called with an argument of HideMode.Screen
    mocked_set_hide_mode.assert_called_once_with(HideMode.Screen)


def test_toggle_display_show(settings: Settings):
    """
    Check that the toggle_display('show') method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode

    # WHEN: toggle_display() is called with an argument of "show"
    slide_controller.toggle_display('show')

    # THEN: set_hide_mode should have been called with an argument of None
    mocked_set_hide_mode.assert_called_once_with(None)


def test_on_toggle_blank(settings: Settings):
    """
    Check that the on_toggle_blank method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance, and get_hide_mode returns none.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode
    slide_controller.get_hide_mode = MagicMock(return_value=None)
    slide_controller._current_hide_mode = None

    # WHEN: on_toggle_blank() is called
    slide_controller.on_toggle_blank()

    # THEN: set_hide_mode should have been called with an argument of HideMode.Blank
    mocked_set_hide_mode.assert_called_once_with(HideMode.Blank)


def test_on_toggle_blank_off(settings: Settings):
    """
    Check that the on_toggle_blank method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance, and get_hide_mode returns blank.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode
    slide_controller.get_hide_mode = MagicMock(return_value=HideMode.Blank)
    slide_controller._current_hide_mode = HideMode.Blank

    # WHEN: on_toggle_blank() is called
    slide_controller.on_toggle_blank()

    # THEN: set_hide_mode should have been called with an argument of None
    mocked_set_hide_mode.assert_called_once_with(None)


def test_on_toggle_theme(settings: Settings):
    """
    Check that the on_toggle_theme method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance, and get_hide_mode returns none.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode
    slide_controller.get_hide_mode = MagicMock(return_value=None)
    slide_controller._current_hide_mode = None

    # WHEN: on_toggle_theme() is called
    slide_controller.on_toggle_theme()

    # THEN: set_hide_mode should have been called with an argument of HideMode.Theme
    mocked_set_hide_mode.assert_called_once_with(HideMode.Theme)


def test_on_toggle_theme_off(settings: Settings):
    """
    Check that the on_toggle_theme method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance, and get_hide_mode returns Theme.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode
    slide_controller.get_hide_mode = MagicMock(return_value=HideMode.Theme)
    slide_controller._current_hide_mode = HideMode.Theme

    # WHEN: on_toggle_theme() is called
    slide_controller.on_toggle_theme()

    # THEN: set_hide_mode should have been called with an argument of None
    mocked_set_hide_mode.assert_called_once_with(None)


def test_on_toggle_desktop(settings: Settings):
    """
    Check that the on_toggle_desktop method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance, and get_hide_mode returns none.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode
    slide_controller.get_hide_mode = MagicMock(return_value=None)
    slide_controller._current_hide_mode = None

    # WHEN: on_toggle_desktop() is called
    slide_controller.on_toggle_desktop()

    # THEN: set_hide_mode should have been called with an argument of HideMode.Screen
    mocked_set_hide_mode.assert_called_once_with(HideMode.Screen)


def test_on_toggle_desktop_off(settings: Settings):
    """
    Check that the on_toggle_desktop method calls set_hide_mode with the correct HideMode
    """
    # GIVEN: A new SlideController instance, and get_hide_mode returns Screen.
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode
    slide_controller.get_hide_mode = MagicMock(return_value=HideMode.Screen)
    slide_controller._current_hide_mode = HideMode.Screen

    # WHEN: on_toggle_desktop() is called
    slide_controller.on_toggle_desktop()

    # THEN: set_hide_mode should have been called with an argument of None
    mocked_set_hide_mode.assert_called_once_with(None)


def test_is_desktop_hide_available_with_macos_always_on_top(settings: Settings):
    """
    Show Desktop should remain available on macOS even when Always on top is enabled.
    """
    # GIVEN: A live slide controller with always-on-top enabled
    slide_controller = SlideController(None)
    settings.setValue('core/always on top', True)

    # WHEN: Checking desktop hide availability
    available = slide_controller.is_desktop_hide_available()

    # THEN: Desktop hide should still be available
    assert available is True


def test_on_toggle_desktop_ignored_when_unavailable(settings: Settings):
    """
    Check that toggling desktop does nothing when desktop hide mode is unavailable.
    """
    # GIVEN: A new SlideController instance and unavailable desktop hide mode
    mocked_set_hide_mode = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.set_hide_mode = mocked_set_hide_mode
    slide_controller.is_desktop_hide_available = MagicMock(return_value=False)

    # WHEN: on_toggle_desktop() is called
    slide_controller.on_toggle_desktop()

    # THEN: set_hide_mode should not be called
    mocked_set_hide_mode.assert_not_called()


def test_set_hide_mode_screen_falls_back_when_desktop_unavailable(settings: Settings):
    """
    set_hide_mode(HideMode.Screen) should be converted to show mode when desktop hide is unavailable.
    """
    # GIVEN: A controller where desktop mode is unavailable
    slide_controller = SlideController(None)
    slide_controller.is_desktop_hide_available = MagicMock(return_value=False)
    slide_controller.hide_menu = MagicMock()
    slide_controller.show_screen = MagicMock()
    slide_controller.blank_screen = MagicMock()
    slide_controller.theme_screen = MagicMock()
    slide_controller.logo_screen = MagicMock()
    slide_controller.desktop_screen = MagicMock()
    slide_controller.service_item = None
    slide_controller.update_preview = MagicMock()
    slide_controller.on_toggle_loop = MagicMock()

    # WHEN: Desktop hide mode is requested
    slide_controller.set_hide_mode(HideMode.Screen)

    # THEN: Hide mode should fall back to showing presentation
    assert slide_controller._current_hide_mode is None


@mark.parametrize('hide_mode', [None, HideMode.Screen])
def test_live_hide_mode_refreshes_display_output_actions(hide_mode, settings: Settings, registry: Registry):
    """Live toolbar changes immediately update the View menu and its switch shortcut."""
    main_window = MagicMock()
    registry.register('main_window', main_window)
    live_controller = LiveController(None)
    live_controller.service_item = None
    live_controller._sync_live_hide_action_state = MagicMock()
    live_controller.update_preview = MagicMock()
    live_controller.on_toggle_loop = MagicMock()

    with patch.object(Registry, 'execute'):
        live_controller.set_hide_mode(hide_mode)

    main_window._sync_view_display_output_menu_action.assert_called_once_with()


def test_on_go_live_live_controller(registry: Registry):
    """
    Test that when the on_go_live() method is called the message is sent to the live controller and focus is
    set correctly.
    """
    # GIVEN: A new SlideController instance and plugin preview then pressing go live should respond
    mocked_display = MagicMock()
    mocked_live_controller = MagicMock()
    mocked_preview_widget = MagicMock()
    mocked_service_item = MagicMock()
    mocked_service_item.from_service = False
    mocked_preview_widget.current_slide_number.return_value = 1
    mocked_preview_widget.slide_count = MagicMock(return_value=2)
    mocked_live_controller.preview_widget = MagicMock()
    Registry().register('live_controller', mocked_live_controller)
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_service_item
    slide_controller.preview_widget = mocked_preview_widget
    slide_controller.displays = [mocked_display]

    # WHEN: on_go_live() is called
    slide_controller.on_go_live()

    # THEN: the live controller should have the service item and the focus set to live
    mocked_live_controller.add_service_manager_item.assert_called_once_with(mocked_service_item, 1)
    mocked_live_controller.preview_widget.setFocus.assert_called_once_with()


def test_on_go_live_service_manager(registry: Registry):
    """
    Test that when the on_go_live() method is called the message is sent to the live controller and focus is
    set correctly.
    """
    # GIVEN: A new SlideController instance and service manager preview then pressing go live should respond
    mocked_display = MagicMock()
    mocked_service_manager = MagicMock()
    mocked_live_controller = MagicMock()
    mocked_preview_widget = MagicMock()
    mocked_service_item = MagicMock()
    mocked_service_item.from_service = True
    mocked_service_item.unique_identifier = 42
    mocked_preview_widget.current_slide_number.return_value = 1
    mocked_preview_widget.slide_count = MagicMock(return_value=2)
    mocked_live_controller.preview_widget = MagicMock()
    Registry().register('live_controller', mocked_live_controller)
    Registry().register('service_manager', mocked_service_manager)
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_service_item
    slide_controller.preview_widget = mocked_preview_widget
    slide_controller.displays = [mocked_display]

    # WHEN: on_go_live() is called
    slide_controller.on_go_live()

    # THEN: the service manager should have the service item and the focus set to live
    mocked_service_manager.preview_live.assert_called_once_with(42, 1)
    mocked_live_controller.preview_widget.setFocus.assert_called_once_with()


def test_update_slide_action_enabled_state_preview(settings: Settings):
    """
    Preview controller actions should be disabled with no slides and enabled when slides exist.
    """
    # GIVEN: A preview controller with mocked actions and preview widget
    slide_controller = SlideController(None)
    slide_controller.is_live = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.previous_item = MagicMock()
    slide_controller.next_item = MagicMock()
    slide_controller.go_live_action = MagicMock()
    slide_controller.add_to_service_action = MagicMock()

    # WHEN: There are no slides
    slide_controller.preview_widget.slide_count.return_value = 0
    slide_controller._update_slide_action_enabled_state()

    # THEN: Move/Preview actions should all be disabled
    slide_controller.previous_item.setEnabled.assert_called_with(False)
    slide_controller.next_item.setEnabled.assert_called_with(False)
    slide_controller.go_live_action.setEnabled.assert_called_with(False)
    slide_controller.add_to_service_action.setEnabled.assert_called_with(False)

    # WHEN: Slides exist
    slide_controller.preview_widget.slide_count.return_value = 2
    slide_controller._update_slide_action_enabled_state()

    # THEN: Move/Preview actions should all be enabled
    slide_controller.previous_item.setEnabled.assert_called_with(True)
    slide_controller.next_item.setEnabled.assert_called_with(True)
    slide_controller.go_live_action.setEnabled.assert_called_with(True)
    slide_controller.add_to_service_action.setEnabled.assert_called_with(True)


def test_preview_add_action_hidden_for_service_items(settings: Settings):
    controller = SlideController(None)
    controller.preview_widget = MagicMock()
    controller.preview_widget.slide_count.return_value = 2
    controller.add_to_service_action = MagicMock()
    controller.service_item = ServiceItem()
    controller.service_item.from_service = True

    controller._update_slide_action_enabled_state()
    controller.add_to_service_action.setVisible.assert_called_with(False)

    controller.service_item = ServiceItem()
    controller._update_slide_action_enabled_state()
    controller.add_to_service_action.setVisible.assert_called_with(True)


def test_preview_add_action_hidden_after_adding(settings: Settings):
    controller = SlideController(None)
    controller.preview_widget = MagicMock()
    controller.preview_widget.slide_count.return_value = 2
    controller.add_to_service_action = MagicMock()
    controller.service_item = ServiceItem()
    manager = MagicMock()
    Registry().register('service_manager', manager)
    manager.add_service_item.side_effect = lambda item: setattr(item, 'from_service', True)

    controller.on_preview_add_to_service()

    manager.add_service_item.assert_called_once_with(controller.service_item)
    controller.add_to_service_action.setVisible.assert_called_with(False)


def test_powerpoint_timing_action_remembers_each_presentation(settings: Settings):
    controller = SlideController(None)
    controller.is_live = True
    controller.powerpoint_timings_action = MagicMock()
    item = MagicMock()
    item.is_command.return_value = True
    item.processor = 'PowerPointMac'
    item.slides = [{}]
    item.sha256_file_hash = 'first-file'
    controller.service_item = item

    with patch.object(Registry, 'execute', return_value=[True]):
        controller.on_toggle_powerpoint_timings(False)
        controller._sync_powerpoint_timings_action(item)

    choices = settings.value('presentations/powerpoint slide timings by file')
    assert choices['first-file'] is False
    controller.powerpoint_timings_action.setChecked.assert_called_with(False)

    item.sha256_file_hash = 'second-file'
    with patch.object(Registry, 'execute', return_value=[True]):
        controller._sync_powerpoint_timings_action(item)
    controller.powerpoint_timings_action.setChecked.assert_called_with(False)
    choices['second-file'] = True
    settings.setValue('presentations/powerpoint slide timings by file', choices)
    with patch.object(Registry, 'execute', return_value=[True]):
        controller._sync_powerpoint_timings_action(item)
    controller.powerpoint_timings_action.setChecked.assert_called_with(True)


def test_powerpoint_timing_action_is_hidden_without_timed_slides(settings: Settings):
    controller = SlideController(None)
    controller.is_live = True
    controller.powerpoint_timings_action = MagicMock()
    item = MagicMock()
    item.is_command.return_value = True
    item.processor = 'PowerPointMac'
    item.slides = [{}]

    with patch.object(Registry, 'execute', return_value=[False]):
        controller._sync_powerpoint_timings_action(item)

    controller.powerpoint_timings_action.setVisible.assert_called_once_with(False)
    controller.powerpoint_timings_action.setChecked.assert_not_called()


def test_update_slide_action_enabled_state_live(settings: Settings):
    """
    Live controller actions should be disabled with no live item and enabled when a live item exists.
    """
    # GIVEN: A live controller with mocked actions and preview widget
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.preview_widget = MagicMock()
    slide_controller.previous_item = MagicMock()
    slide_controller.next_item = MagicMock()
    slide_controller.show_screen = MagicMock()
    slide_controller.theme_screen = MagicMock()
    slide_controller.logo_screen = MagicMock()
    slide_controller.blank_screen = MagicMock()
    slide_controller.play_slides_loop = MagicMock()
    slide_controller.play_slides_once = MagicMock()
    slide_controller.desktop_screen = MagicMock()
    slide_controller.hide_menu = MagicMock()
    slide_controller.neutral_hide_action = MagicMock()
    slide_controller.toolbar = MagicMock()
    slide_controller.is_desktop_hide_available = MagicMock(return_value=True)
    mocked_main_window = MagicMock()
    mocked_main_window.view_display_output_item.isChecked.return_value = True
    mocked_main_window.view_display_output_item.isEnabled.return_value = True
    Registry().register('main_window', mocked_main_window)

    # WHEN: There are no slides and no live item
    slide_controller.preview_widget.slide_count.return_value = 0
    slide_controller.service_item = None
    slide_controller._update_slide_action_enabled_state()

    # THEN: Move actions and live controls should be disabled
    slide_controller.previous_item.setEnabled.assert_called_with(False)
    slide_controller.next_item.setEnabled.assert_called_with(False)
    slide_controller.show_screen.setEnabled.assert_called_with(False)
    slide_controller.theme_screen.setEnabled.assert_called_with(False)
    slide_controller.logo_screen.setEnabled.assert_called_with(False)
    slide_controller.blank_screen.setEnabled.assert_called_with(False)
    slide_controller.play_slides_loop.setEnabled.assert_called_with(False)
    slide_controller.play_slides_once.setEnabled.assert_called_with(False)
    slide_controller.desktop_screen.setEnabled.assert_called_with(False)
    slide_controller.show_screen.setChecked.assert_called_with(False)
    slide_controller.theme_screen.setChecked.assert_called_with(False)
    slide_controller.logo_screen.setChecked.assert_called_with(False)
    slide_controller.blank_screen.setChecked.assert_called_with(False)
    slide_controller.desktop_screen.setChecked.assert_called_with(False)
    slide_controller.hide_menu.setDefaultAction.assert_called_with(slide_controller.neutral_hide_action)
    slide_controller.toolbar.set_widget_enabled.assert_any_call([
        'hide_menu',
        'show_screen_button', 'theme_screen_button', 'logo_screen_button', 'blank_screen_button',
        'play_slides_menu', 'delay_spin_box'
    ], False)
    slide_controller.toolbar.set_widget_enabled.assert_any_call('desktop_screen_button', False)

    # WHEN: Slides exist and a live item is loaded
    slide_controller.preview_widget.slide_count.return_value = 3
    slide_controller.service_item = MagicMock()
    slide_controller._current_hide_mode = None
    slide_controller._update_slide_action_enabled_state()

    # THEN: Move actions and live controls should be enabled
    slide_controller.previous_item.setEnabled.assert_called_with(True)
    slide_controller.next_item.setEnabled.assert_called_with(True)
    slide_controller.show_screen.setEnabled.assert_called_with(True)
    slide_controller.theme_screen.setEnabled.assert_called_with(True)
    slide_controller.logo_screen.setEnabled.assert_called_with(True)
    slide_controller.blank_screen.setEnabled.assert_called_with(True)
    slide_controller.play_slides_loop.setEnabled.assert_called_with(True)
    slide_controller.play_slides_once.setEnabled.assert_called_with(True)
    slide_controller.desktop_screen.setEnabled.assert_called_with(True)
    slide_controller.show_screen.setChecked.assert_called_with(True)
    slide_controller.theme_screen.setChecked.assert_called_with(False)
    slide_controller.logo_screen.setChecked.assert_called_with(False)
    slide_controller.blank_screen.setChecked.assert_called_with(False)
    slide_controller.desktop_screen.setChecked.assert_called_with(False)
    slide_controller.hide_menu.setDefaultAction.assert_called_with(slide_controller.show_screen)
    slide_controller.toolbar.set_widget_enabled.assert_any_call([
        'hide_menu',
        'show_screen_button', 'theme_screen_button', 'logo_screen_button', 'blank_screen_button',
        'play_slides_menu', 'delay_spin_box'
    ], True)
    slide_controller.toolbar.set_widget_enabled.assert_any_call('desktop_screen_button', True)


def test_sync_live_hide_action_state_is_neutral_without_live_item(settings: Settings):
    """Live hide-mode actions should look neutral until a live item is loaded."""
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.show_screen = MagicMock()
    slide_controller.theme_screen = MagicMock()
    slide_controller.logo_screen = MagicMock()
    slide_controller.blank_screen = MagicMock()
    slide_controller.desktop_screen = MagicMock()
    slide_controller.hide_menu = MagicMock()
    slide_controller.neutral_hide_action = MagicMock()
    slide_controller._current_hide_mode = None

    slide_controller._sync_live_hide_action_state(has_item=False)

    slide_controller.show_screen.setChecked.assert_called_with(False)
    slide_controller.theme_screen.setChecked.assert_called_with(False)
    slide_controller.logo_screen.setChecked.assert_called_with(False)
    slide_controller.blank_screen.setChecked.assert_called_with(False)
    slide_controller.desktop_screen.setChecked.assert_called_with(False)
    slide_controller.hide_menu.setDefaultAction.assert_called_once_with(slide_controller.neutral_hide_action)


def test_update_desktop_hide_action_state_keeps_hidden_output(settings: Settings):
    """Refreshing the toolbar must not clear Show Desktop when output is hidden."""
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.desktop_screen = MagicMock()
    slide_controller.toolbar = MagicMock()
    slide_controller.is_desktop_hide_available = MagicMock(return_value=True)
    mocked_main_window = MagicMock()
    mocked_main_window.view_display_output_item.isChecked.return_value = False
    mocked_main_window.view_display_output_item.isEnabled.return_value = True
    Registry().register('main_window', mocked_main_window)
    slide_controller._current_hide_mode = HideMode.Screen
    slide_controller.set_hide_mode = MagicMock()

    slide_controller._update_desktop_hide_action_state(has_item=True)

    slide_controller.desktop_screen.setEnabled.assert_called_with(True)
    slide_controller.toolbar.set_widget_enabled.assert_called_with('desktop_screen_button', True)
    slide_controller.set_hide_mode.assert_not_called()
    assert slide_controller.current_hide_mode == HideMode.Screen

    mocked_main_window.view_display_output_item.isChecked.return_value = True
    mocked_main_window.view_display_output_item.isEnabled.return_value = False

    slide_controller._update_desktop_hide_action_state(has_item=True)

    slide_controller.desktop_screen.setEnabled.assert_called_with(False)
    slide_controller.toolbar.set_widget_enabled.assert_called_with('desktop_screen_button', False)
    slide_controller.set_hide_mode.assert_not_called()
    assert slide_controller.current_hide_mode == HideMode.Screen


def test_service_previous(settings: Settings):
    """
    Check that calling the service_previous() method adds the previous key to the queue and processes the queue
    """
    # GIVEN: A new SlideController instance.
    mocked_keypress_queue = MagicMock()
    mocked_process_queue = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.keypress_queue = mocked_keypress_queue
    slide_controller._process_queue = mocked_process_queue

    # WHEN: The service_previous() method is called
    slide_controller.service_previous()

    # THEN: The keypress is added to the queue and the queue is processed
    mocked_keypress_queue.append.assert_called_once_with(ServiceItemAction.Previous)
    mocked_process_queue.assert_called_once_with()


def test_service_next(settings: Settings):
    """
    Check that calling the service_next() method adds the next key to the queue and processes the queue
    """
    # GIVEN: A new SlideController instance and mocked out methods
    mocked_keypress_queue = MagicMock()
    mocked_process_queue = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.keypress_queue = mocked_keypress_queue
    slide_controller._process_queue = mocked_process_queue

    # WHEN: The service_next() method is called
    slide_controller.service_next()

    # THEN: The keypress is added to the queue and the queue is processed
    mocked_keypress_queue.append.assert_called_once_with(ServiceItemAction.Next)
    mocked_process_queue.assert_called_once_with()


def test_update_slide_limits(mock_settings: MagicMock):
    """
    Test that calling the update_slide_limits() method updates the slide limits
    """
    # GIVEN: A mocked out Settings object, a new SlideController and a mocked out main_window
    mock_settings.value.return_value = 10
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    slide_controller = SlideController(None)

    # WHEN: update_slide_limits() is called
    slide_controller.update_slide_limits()

    # THEN: The value of slide_limits should be 10
    msv = mock_settings.value
    msv.assert_called_once_with('advanced/slide limits')
    assert 10 == slide_controller.slide_limits, 'Slide limits should have been updated to 10'


def test_enable_tool_bar_live(settings: Settings):
    """
    Check that when enable_tool_bar on a live slide controller is called, enable_live_tool_bar is called
    """
    # GIVEN: Mocked out enable methods and a real slide controller which is set to live
    mocked_enable_live_tool_bar = MagicMock()
    mocked_enable_preview_tool_bar = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.enable_live_tool_bar = mocked_enable_live_tool_bar
    slide_controller.enable_preview_tool_bar = mocked_enable_preview_tool_bar
    mocked_service_item = MagicMock()

    # WHEN: enable_tool_bar() is called
    slide_controller.enable_tool_bar(mocked_service_item)

    # THEN: The enable_live_tool_bar() method is called, not enable_preview_tool_bar()
    mocked_enable_live_tool_bar.assert_called_once_with(mocked_service_item)
    assert 0 == mocked_enable_preview_tool_bar.call_count, 'The preview method should not have been called'


def test_enable_tool_bar_preview(settings: Settings):
    """
    Check that when enable_tool_bar on a preview slide controller is called, enable_preview_tool_bar is called
    """
    # GIVEN: Mocked out enable methods and a real slide controller which is set to live
    mocked_enable_live_tool_bar = MagicMock()
    mocked_enable_preview_tool_bar = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.is_live = False
    slide_controller.enable_live_tool_bar = mocked_enable_live_tool_bar
    slide_controller.enable_preview_tool_bar = mocked_enable_preview_tool_bar
    mocked_service_item = MagicMock()

    # WHEN: enable_tool_bar() is called
    slide_controller.enable_tool_bar(mocked_service_item)

    # THEN: The enable_preview_tool_bar() method is called, not enable_live_tool_bar()
    mocked_enable_preview_tool_bar.assert_called_once_with(mocked_service_item)
    assert 0 == mocked_enable_live_tool_bar.call_count, 'The live method should not have been called'


def test_refresh_service_item_text(settings: Settings):
    """
    Test that the refresh_service_item() method refreshes a text service item
    """
    # GIVEN: A mock service item and a fresh slide controller
    mocked_service_item = MagicMock()
    mocked_service_item.is_text.return_value = True
    mocked_service_item.is_image.return_value = False
    mocked_process_item = MagicMock()
    mocked_slide_selected = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_service_item
    slide_controller._process_item = mocked_process_item
    slide_controller.slide_selected = mocked_slide_selected
    slide_controller.selected_row = 5

    # WHEN: The refresh_service_item method() is called
    slide_controller.refresh_service_item()

    # THEN: The item should be re-processed
    slide_controller._process_item.assert_called_once_with(mocked_service_item, 5, True)
    slide_controller.slide_selected.assert_called_once()


def test_add_service_item_with_song_edit(settings: Settings):
    """
    Test the add_service_item() method when song_edit is True
    """
    # GIVEN: A slide controller and a new item to add
    mocked_item = MagicMock()
    mocked_process_item = MagicMock()
    slide_controller = SlideController(None)
    slide_controller._process_item = mocked_process_item
    slide_controller.song_edit = True
    slide_controller.selected_row = 2

    # WHEN: The item is added to the service
    slide_controller.add_service_item(mocked_item)

    # THEN: The item is processed, the slide number is correct, and the song is not editable (or something)
    assert slide_controller.song_edit is False, 'song_edit should be False'
    mocked_process_item.assert_called_once_with(mocked_item, 2)


def test_add_service_item_without_song_edit(settings: Settings):
    """
    Test the add_service_item() method when song_edit is False
    """
    # GIVEN: A slide controller and a new item to add
    mocked_item = MagicMock()
    mocked_process_item = MagicMock()
    slide_controller = SlideController(None)
    slide_controller._process_item = mocked_process_item
    slide_controller.song_edit = False
    slide_controller.selected_row = 2

    # WHEN: The item is added to the service
    slide_controller.add_service_item(mocked_item)

    # THEN: The item is processed, the slide number is correct, and the song is not editable (or something)
    assert slide_controller.song_edit is False, 'song_edit should be False'
    mocked_process_item.assert_called_once_with(mocked_item, 0)


def test_replace_service_manager_item_different_items(settings: Settings):
    """
    Test that when the service items are not the same, nothing happens
    """
    # GIVEN: A slide controller and a new item to add
    mocked_item = MagicMock()
    mocked_preview_widget = MagicMock()
    mocked_process_item = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.preview_widget = mocked_preview_widget
    slide_controller._process_item = mocked_process_item
    slide_controller.service_item = None

    # WHEN: The service item is replaced
    slide_controller.replace_service_manager_item(mocked_item)

    # THEN: The service item should not be processed
    assert 0 == mocked_process_item.call_count, 'The _process_item() method should not have been called'
    assert 0 == mocked_preview_widget.current_slide_number.call_count, \
        'The preview_widget current_slide_number.() method should not have been called'


def test_replace_service_manager_item_same_item(settings: Settings):
    """
    Test that when the service item is the same, the service item is reprocessed
    """
    # GIVEN: A slide controller and a new item to add
    mocked_item = MagicMock()
    mocked_preview_widget = MagicMock()
    mocked_preview_widget.current_slide_number.return_value = 7
    mocked_process_item = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.preview_widget = mocked_preview_widget
    slide_controller._process_item = mocked_process_item
    slide_controller.service_item = mocked_item

    # WHEN: The service item is replaced
    slide_controller.replace_service_manager_item(mocked_item)

    # THEN: The service item should not be processed
    mocked_preview_widget.current_slide_number.assert_called_with()
    mocked_process_item.assert_called_once_with(mocked_item, 7)


def test_replace_service_manager_item_same_service_row_different_uuid(settings: Settings):
    """
    Rebuilding a service item (e.g. Bible layout) can change unique_identifier; preview should still reload
    when the service list index matches.
    """
    old_copy = MagicMock()
    old_copy.unique_identifier = 'old-uuid'
    new_canonical = MagicMock()
    new_canonical.unique_identifier = 'new-uuid'
    mocked_preview_widget = MagicMock()
    mocked_preview_widget.current_slide_number.return_value = 3
    mocked_process_item = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.preview_widget = mocked_preview_widget
    slide_controller._process_item = mocked_process_item
    slide_controller.service_item = old_copy
    slide_controller._service_manager_item_index = 2

    slide_controller.replace_service_manager_item(new_canonical, service_list_index=2)

    mocked_process_item.assert_called_once_with(new_canonical, 3)


def test_on_slide_selected_index_no_service_item(settings: Settings):
    """
    Test that when there is no service item, the on_slide_selected_index() method returns immediately
    """
    # GIVEN: A mocked service item and a slide controller without a service item
    mocked_item = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.service_item = None

    # WHEN: The method is called
    slide_controller.on_slide_selected_index([10])

    # THEN: It should have exited early
    assert 0 == mocked_item.is_command.call_count, 'The service item should have not been called'


@patch.object(Registry, 'execute')
def test_on_slide_selected_index_service_item_command(mocked_execute: MagicMock, registry: Registry):
    """
    Test that when there is a command service item, the command is executed
    """
    # GIVEN: A mocked service item and a slide controller with a service item
    mocked_item = MagicMock()
    mocked_item.is_command.return_value = True
    mocked_item.name = 'Mocked Item'
    mocked_update_preview = MagicMock()
    mocked_preview_widget = MagicMock()
    mocked_slide_selected = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_item
    slide_controller.update_preview = mocked_update_preview
    slide_controller.preview_widget = mocked_preview_widget
    slide_controller.slide_selected = mocked_slide_selected
    slide_controller.is_live = True

    # WHEN: The method is called
    slide_controller.on_slide_selected_index([9])

    # THEN: It should have sent a notification
    mocked_item.is_command.assert_called_once_with()
    mocked_execute.assert_called_once_with('mocked item_slide', [mocked_item, True, 9])
    mocked_update_preview.assert_called_once_with()
    assert 0 == mocked_preview_widget.change_slide.call_count, 'Change slide should not have been called'
    assert 0 == mocked_slide_selected.call_count, 'slide_selected should not have been called'


@patch.object(Registry, 'execute')
def test_on_slide_selected_index_service_item_not_command(mocked_execute: MagicMock, registry: Registry):
    """
    Test that when there is a service item but it's not a command, the preview widget is updated
    """
    # GIVEN: A mocked service item and a slide controller with a service item
    mocked_item = MagicMock()
    mocked_item.is_command.return_value = False
    mocked_item.name = 'Mocked Item'
    mocked_update_preview = MagicMock()
    mocked_preview_widget = MagicMock()
    mocked_slide_selected = MagicMock()
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_item
    slide_controller.update_preview = mocked_update_preview
    slide_controller.preview_widget = mocked_preview_widget
    slide_controller.slide_selected = mocked_slide_selected

    # WHEN: The method is called
    slide_controller.on_slide_selected_index([7])

    # THEN: It should have sent a notification
    mocked_item.is_command.assert_called_once_with()
    assert 0 == mocked_execute.call_count, 'Execute should not have been called'
    assert 0 == mocked_update_preview.call_count, 'Update preview should not have been called'
    mocked_preview_widget.change_slide.assert_called_once_with(7)
    mocked_slide_selected.assert_called_once_with()


def test_set_background_image(registry: Registry):
    """
    Test that the display and preview background are set
    """
    # GIVEN: A slide controller
    slide_controller = SlideController(None)
    slide_controller.preview_display = MagicMock()
    mock_display = MagicMock()
    slide_controller.displays = [mock_display]

    # WHEN: set_background_image is called
    slide_controller.set_background_image(sentinel.image)

    # THEN: The preview and main display are called with the new colour and image
    slide_controller.preview_display.set_background_image.assert_called_once_with(sentinel.image)
    mock_display.set_background_image.assert_called_once_with(sentinel.image)


def test_theme_updated(mock_settings: MagicMock):
    """
    Test that the theme_updated function updates the service if hot reload is on
    """
    # GIVEN: A slide controller and settings return true
    slide_controller = SlideController(None)
    slide_controller.service_item = sentinel.service_item
    slide_controller._process_item = MagicMock()
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_widget.current_slide_number.return_value = 14
    mock_settings.value.return_value = True

    # WHEN: theme_updated is called
    slide_controller.on_theme_changed()

    # THEN: process_item is called with the current service_item and slide number
    slide_controller._process_item.assert_called_once_with(sentinel.service_item, 14)


def test_theme_updated_no_reload(mock_settings: MagicMock):
    """
    Test that the theme_updated function does not update the service if hot reload is off
    """
    # GIVEN: A slide controller and settings return false
    slide_controller = SlideController(None)
    slide_controller.service_item = sentinel.service_item
    slide_controller._process_item = MagicMock()
    slide_controller.preview_widget = MagicMock()
    mock_settings.value.return_value = False

    # WHEN: theme_updated is called
    slide_controller.on_theme_changed()

    # THEN: process_item is not called
    assert slide_controller._process_item.call_count == 0


def test_reload_theme(mock_settings: MagicMock):
    """
    Test that the reload_theme function triggers the reload_theme function for the displays
    """
    # GIVEN: A slide controller and mocked displays
    slide_controller = SlideController(None)
    slide_controller.preview_display = MagicMock()
    mock_display = MagicMock()
    slide_controller.displays = [mock_display]

    # WHEN: reload_theme is called
    slide_controller.reload_theme()

    # THEN: reload_theme is called with the preview and main display
    slide_controller.preview_display.reload_theme.assert_called_once_with()
    mock_display.reload_theme.assert_called_once_with()


@patch.object(Registry, 'execute')
def test_process_item(mocked_execute: MagicMock, registry: Registry, state_media: State):
    """
    Test that presentation service-items is closed when followed by a media service-item
    """
    # GIVEN: A mocked presentation service item, a mocked media service item, a mocked Registry.execute
    #        and a slide controller with many mocks.
    mocked_pres_item = MagicMock()
    mocked_pres_item.name = 'mocked_presentation_item'
    mocked_pres_item.is_command.return_value = True
    mocked_pres_item.is_media.return_value = False
    mocked_pres_item.is_image.return_value = False
    mocked_pres_item.from_service = False
    mocked_pres_item.get_frames.return_value = []
    mocked_media_item = MagicMock()
    mocked_media_item.name = 'mocked_media_item'
    mocked_media_item.is_command.return_value = True
    mocked_media_item.is_media.return_value = True
    mocked_media_item.is_image.return_value = False
    mocked_media_item.from_service = False
    mocked_media_item.get_frames.return_value = []
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    Registry().register('media_controller', MagicMock())
    Registry().register('application', MagicMock())
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_pres_item
    slide_controller.is_live = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.enable_tool_bar = MagicMock()
    slide_controller.on_media_start = MagicMock()
    slide_controller.slide_selected = MagicMock()
    slide_controller.on_stop_loop = MagicMock()
    slide_controller.info_label = MagicMock()
    slide_controller.displays = [MagicMock()]
    slide_controller.split = 0
    slide_controller.type_prefix = 'test'

    # WHEN: _process_item is called
    slide_controller._process_item(mocked_media_item, 0)

    # THEN: Registry.execute should have been called to stop the presentation
    assert 1 == mocked_execute.call_count, 'Execute should have been called once'
    assert 'mocked_presentation_item_stop' == mocked_execute.call_args_list[0][0][0], \
        'The presentation should have been stopped.'


@patch.object(Registry, 'execute')
def test_process_item_transition(mocked_execute: MagicMock, registry: Registry, state_media: State):
    """
    Test that the correct actions are taken when a media service-item is closed followed by a image service-item
    """
    # GIVEN: A mocked presentation service item, a mocked media service item, a mocked Registry.execute
    #        and a slide controller with many mocks.
    #        and the setting 'themes/item transitions' = True
    mocked_pres_item = MagicMock()
    mocked_pres_item.name = 'mocked_image_item'
    mocked_pres_item.is_command.return_value = True
    mocked_pres_item.is_media.return_value = True
    mocked_pres_item.is_image.return_value = False
    mocked_pres_item.from_service = False
    mocked_pres_item.get_frames.return_value = []
    mocked_media_item = MagicMock()
    mocked_media_item.name = 'mocked_media_item'
    mocked_media_item.get_transition_delay.return_value = 0
    mocked_media_item.is_text.return_value = False
    mocked_media_item.is_command.return_value = False
    mocked_media_item.is_media.return_value = False
    mocked_media_item.requires_media.return_value = False
    mocked_media_item.is_image.return_value = True
    mocked_media_item.from_service = False
    mocked_media_item.get_frames.return_value = []
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = True
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    Registry().register('media_controller', MagicMock())
    Registry().register('application', MagicMock())
    Registry().register('settings', mocked_settings)
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_pres_item
    slide_controller.is_live = True
    slide_controller._reset_blank = MagicMock()
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.enable_tool_bar = MagicMock()
    slide_controller.on_controller_size_changed = MagicMock()
    slide_controller.on_media_start = MagicMock()
    slide_controller.on_media_close = MagicMock()
    slide_controller.slide_selected = MagicMock()
    slide_controller.set_hide_mode = MagicMock()
    slide_controller.new_song_menu = MagicMock()
    slide_controller.on_stop_loop = MagicMock()
    slide_controller.info_label = MagicMock()
    slide_controller.song_menu = MagicMock()
    slide_controller.displays = [MagicMock()]
    slide_controller.toolbar = MagicMock()
    slide_controller._current_hide_mode = None
    slide_controller.split = 0
    slide_controller.type_prefix = 'test'
    slide_controller.screen_capture = 'old_capture'
    slide_controller.show_screen = MagicMock()
    slide_controller.blank_screen = MagicMock()
    slide_controller.theme_screen = MagicMock()
    slide_controller.logo_screen = MagicMock()
    slide_controller.desktop_screen = MagicMock()
    slide_controller.hide_menu = MagicMock()
    slide_controller.neutral_hide_action = MagicMock()

    # WHEN: _process_item is called
    slide_controller._process_item(mocked_media_item, 0)

    # THEN: Registry.execute should have been called to start the live item
    #       Media should be closed
    #       Controller size change should be called (because it's a live item and the interface might have changed)
    #       The screen capture should have been reset to none
    assert 1 == mocked_execute.call_count, 'Execute should have been called once'
    slide_controller.on_media_close.assert_called_once_with()
    slide_controller.on_controller_size_changed.assert_called_once()
    assert slide_controller.screen_capture is None


@patch.object(Registry, 'execute')
def test_process_item_text(mocked_execute: MagicMock, registry: Registry, state_media: State):
    """
    Test that the correct actions are taken a text item is processed
    """
    # GIVEN: A mocked presentation service item, a mocked media service item, a mocked Registry.execute
    #        and a slide controller with many mocks.
    #        and the setting 'themes/item transitions' = True
    mocked_media_item = MagicMock()
    mocked_media_item.name = 'mocked_media_item'
    mocked_media_item.get_transition_delay.return_value = 0
    mocked_media_item.is_text.return_value = True
    mocked_media_item.is_command.return_value = False
    mocked_media_item.is_media.return_value = False
    mocked_media_item.requires_media.return_value = False
    mocked_media_item.is_image.return_value = False
    mocked_media_item.from_service = False
    mocked_media_item.get_frames.return_value = []
    mocked_media_item.display_slides = [{'verse': 'Verse name'}]
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = True
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    Registry().register('media_controller', MagicMock())
    Registry().register('application', MagicMock())
    Registry().register('settings', mocked_settings)
    slide_controller = SlideController(None)
    slide_controller.service_item = None
    slide_controller.is_live = True
    slide_controller._reset_blank = MagicMock()
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.enable_tool_bar = MagicMock()
    slide_controller.on_controller_size_changed = MagicMock()
    slide_controller.on_media_start = MagicMock()
    slide_controller.on_media_close = MagicMock()
    slide_controller.slide_selected = MagicMock()
    slide_controller.set_hide_mode = MagicMock()
    slide_controller.new_song_menu = MagicMock()
    slide_controller.on_stop_loop = MagicMock()
    slide_controller.info_label = MagicMock()
    slide_controller.song_menu = MagicMock()
    slide_controller.displays = [MagicMock()]
    slide_controller.toolbar = MagicMock()
    slide_controller.split = 0
    slide_controller.type_prefix = 'test'
    slide_controller.screen_capture = 'old_capture'
    slide_controller.show_screen = MagicMock()
    slide_controller.blank_screen = MagicMock()
    slide_controller.theme_screen = MagicMock()
    slide_controller.logo_screen = MagicMock()
    slide_controller.desktop_screen = MagicMock()
    slide_controller.hide_menu = MagicMock()
    slide_controller.neutral_hide_action = MagicMock()

    # WHEN: _process_item is called
    slide_controller._process_item(mocked_media_item, 0)

    # THEN: Registry.execute should have been called to start the live item
    #       Controller size change should be called (because it's a live item and the interface might have changed)
    #       The screen capture should have been reset to none
    #       The slide should have been added to the slide list with the correct index
    assert 1 == mocked_execute.call_count, 'Execute should have been called once'
    slide_controller.on_controller_size_changed.assert_called_once()
    assert slide_controller.screen_capture is None
    assert slide_controller.slide_list['Verse name'] == 0


@patch.object(Registry, 'execute')
def test_process_item_song_media(mocked_execute: MagicMock, registry: Registry, state_media: State):
    """
    Test that media is started if media is present.
    """
    # GIVEN: A mocked presentation service item, a mocked media service item, a mocked Registry.execute
    #        and a slide controller with many mocks.
    mocked_pres_item = MagicMock()
    mocked_pres_item.name = 'mocked_song_item'
    mocked_pres_item.is_command.return_value = False
    mocked_pres_item.is_media.return_value = True
    mocked_pres_item.is_image.return_value = False
    mocked_pres_item.from_service = False
    mocked_pres_item.get_frames.return_value = []
    mocked_media_item = MagicMock()
    mocked_media_item.name = 'mocked_media_item'
    mocked_media_item.is_command.return_value = True
    mocked_media_item.is_media.return_value = True
    mocked_media_item.is_image.return_value = False
    mocked_media_item.from_service = False
    mocked_media_item.get_frames.return_value = []
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    Registry().register('media_controller', MagicMock())
    Registry().register('application', MagicMock())
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_pres_item
    slide_controller.is_live = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.enable_tool_bar = MagicMock()
    slide_controller.slide_selected = MagicMock()
    slide_controller.on_stop_loop = MagicMock()
    slide_controller.info_label = MagicMock()
    slide_controller.displays = [MagicMock()]
    slide_controller.split = 0
    slide_controller.type_prefix = 'test'
    slide_controller._current_hide_mode = None

    # WHEN: _process_item is called
    slide_controller._process_item(mocked_media_item, 0)

    # THEN: Registry.execute should have been called to stop the presentation
    assert 1 == slide_controller.media_controller.load_media.call_count, ' load_media should have been called 1 times'
    assert 2 == slide_controller.preview_display.load_verses.call_count, 'Execute should have been called 2 times'


@patch.object(Registry, 'execute')
def test_process_item_song_no_media(mocked_execute: MagicMock, registry: Registry, state_media: State):
    """
    Test that media is started if medis is present.
    """
    # GIVEN: A mocked presentation service item, a mocked media service item, a mocked Registry.execute
    #        and a slide controller with many mocks.
    State().update_pre_conditions("media", False)
    State().flush_preconditions()
    mocked_pres_item = MagicMock()
    mocked_pres_item.name = 'mocked_song_item'
    mocked_pres_item.is_command.return_value = False
    mocked_pres_item.is_media.return_value = True
    mocked_pres_item.is_image.return_value = False
    mocked_pres_item.from_service = False
    mocked_pres_item.get_frames.return_value = []
    mocked_media_item = MagicMock()
    mocked_media_item.name = 'mocked_media_item'
    mocked_media_item.is_command.return_value = True
    mocked_media_item.is_media.return_value = True
    mocked_media_item.is_image.return_value = False
    mocked_media_item.from_service = False
    mocked_media_item.get_frames.return_value = []
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    Registry().register('media_controller', MagicMock())
    Registry().register('application', MagicMock())
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_pres_item
    slide_controller.is_live = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.enable_tool_bar = MagicMock()
    slide_controller.slide_selected = MagicMock()
    slide_controller.on_stop_loop = MagicMock()
    slide_controller.info_label = MagicMock()
    slide_controller.displays = [MagicMock()]
    slide_controller.split = 0
    slide_controller.type_prefix = 'test'

    # WHEN: _process_item is called
    slide_controller._process_item(mocked_media_item, 0)

    # THEN: Registry.execute should have been called to stop the presentation
    assert 0 == slide_controller.media_controller.load_media.call_count, ' load_media should have been called 0 times'
    assert 2 == slide_controller.preview_display.load_verses.call_count, 'Execute should have been called 2 times'


@mark.parametrize('is_reloading', [False, True])
@patch.object(Registry, 'execute')
def test_process_item_keeps_desktop_hide_mode(mocked_execute: MagicMock, registry: Registry,
                                              state_media: State, is_reloading: bool):
    """
    Auto unblank must leave output hidden when the operator selected Show Desktop.
    """
    # GIVEN: A mocked presentation service item, a mocked media service item, a mocked Registry.execute
    #        and a slide controller with many mocks.
    #        and the setting 'themes/item transitions' = True
    mocked_media_item = MagicMock()
    mocked_media_item.name = 'mocked_media_item'
    mocked_media_item.get_transition_delay.return_value = 0
    mocked_media_item.is_text.return_value = True
    mocked_media_item.is_command.return_value = False
    mocked_media_item.is_media.return_value = False
    mocked_media_item.requires_media.return_value = False
    mocked_media_item.is_image.return_value = False
    mocked_media_item.from_service = False
    mocked_media_item.get_frames.return_value = []
    mocked_media_item.display_slides = [{'verse': 'Verse name'}]
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = True
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    Registry().register('media_controller', MagicMock())
    Registry().register('application', MagicMock())
    Registry().register('settings', mocked_settings)
    slide_controller = SlideController(None)
    slide_controller.service_item = None
    slide_controller.is_live = True
    slide_controller._current_hide_mode = HideMode.Screen
    slide_controller._reset_blank = MagicMock()
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.enable_tool_bar = MagicMock()
    slide_controller.on_controller_size_changed = MagicMock()
    slide_controller.on_media_start = MagicMock()
    slide_controller.on_media_close = MagicMock()
    slide_controller.slide_selected = MagicMock()
    slide_controller.set_hide_mode = MagicMock()
    slide_controller.new_song_menu = MagicMock()
    slide_controller.on_stop_loop = MagicMock()
    slide_controller.info_label = MagicMock()
    slide_controller.song_menu = MagicMock()
    slide_controller.displays = [MagicMock()]
    slide_controller.toolbar = MagicMock()
    slide_controller.split = 0
    slide_controller.type_prefix = 'test'
    slide_controller.screen_capture = 'old_capture'
    slide_controller.show_screen = MagicMock()
    slide_controller.blank_screen = MagicMock()
    slide_controller.theme_screen = MagicMock()
    slide_controller.logo_screen = MagicMock()
    slide_controller.desktop_screen = MagicMock()
    slide_controller.hide_menu = MagicMock()
    slide_controller.neutral_hide_action = MagicMock()

    # WHEN: _process_item is called while Display output is off
    slide_controller._process_item(mocked_media_item, 0, is_reloading=is_reloading)

    # THEN: set_hide_mode should not be called
    slide_controller.set_hide_mode.assert_not_called()


@patch.object(Registry, 'execute')
def test_process_item_provides_own_theme(mocked_execute: MagicMock, registry: Registry, state_media: State):
    """
    Test that media theme is set when media item is flagged with ProvidesOwnTheme
    """
    # GIVEN: A mocked presentation service item that provides it's own theme, a mocked Registry.execute
    #        and a slide controller with many mocks.
    mocked_pres_item = MagicMock()
    mocked_pres_item.name = 'mocked_presentation_item'
    mocked_pres_item.is_command.return_value = True
    mocked_pres_item.is_media.return_value = False
    mocked_pres_item.requires_media.return_value = False
    mocked_pres_item.is_image.return_value = False
    mocked_pres_item.is_text.return_value = False
    # Needed to perform the capability checks
    mocked_pres_item.is_capable = lambda param: ServiceItem.is_capable(mocked_pres_item, param)
    mocked_pres_item.from_service = False
    mocked_pres_item.capabilities = [ItemCapabilities.ProvidesOwnTheme]
    mocked_pres_item.get_frames.return_value = []
    mocked_settings = MagicMock()
    mocked_settings.value.return_value = True
    mocked_main_window = MagicMock()
    Registry().register('settings', mocked_settings)
    Registry().register('main_window', mocked_main_window)
    Registry().register('media_controller', MagicMock())
    Registry().register('application', MagicMock())
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_pres_item
    slide_controller.is_live = False
    slide_controller.preview_widget = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.enable_tool_bar = MagicMock()
    slide_controller.slide_selected = MagicMock()
    slide_controller.on_stop_loop = MagicMock()
    slide_controller.info_label = MagicMock()
    slide_controller._set_theme = MagicMock()
    slide_controller.displays = [MagicMock()]
    slide_controller.split = 0
    slide_controller.type_prefix = 'test'
    slide_controller._current_hide_mode = None

    # WHEN: _process_item is called
    slide_controller._process_item(mocked_pres_item, 0)

    # THEN: _set_theme should be called once
    slide_controller._set_theme.assert_called_once()


@patch.object(Registry, 'execute')
def test_sending_current_presentation_live_selects_requested_slide(mocked_execute, registry, settings):
    item = MagicMock()
    item.name = 'presentations'
    item.title = 'Slides'
    item.processor = 'PowerPointMac'
    item.sha256_file_hash = 'same-presentation'
    item.slides = [{'image': '/tmp/slide.png'} for _ in range(5)]
    item.is_command.return_value = True
    item.is_media.return_value = False
    item.is_text.return_value = False
    item.is_image.return_value = False
    item.is_capable.return_value = False
    item.requires_media.return_value = False
    item.from_service = False
    main_window = MagicMock()
    main_window.control_splitter.sizes.return_value = [600]
    registry.register('main_window', main_window)
    controller = SlideController(None)
    controller.is_live = True
    controller.service_item = item
    controller.selected_row = 0
    controller.split = 0
    controller.type_prefix = 'live'
    controller._current_hide_mode = None
    controller.preview_widget = MagicMock()
    controller.preview_display = MagicMock()
    controller.info_label = MagicMock()
    controller.displays = []
    controller.on_stop_loop = MagicMock()
    controller.on_media_close = MagicMock()
    controller.enable_tool_bar = MagicMock()
    controller.slide_selected = MagicMock()
    controller._reset_blank = MagicMock()
    controller.on_controller_size_changed = MagicMock()
    controller._update_slide_action_enabled_state = MagicMock()
    controller.set_hide_mode = MagicMock()

    controller._process_item(item, 3)

    calls = [call for call in mocked_execute.call_args_list if call.args[0] == 'presentations_slide']
    assert len(calls) == 1
    assert calls[0].args[1][1:] == [True, 3]
    assert not any(call.args[0] == 'presentations_start' for call in mocked_execute.call_args_list)
    assert not any(call.args[0] == 'presentations_stop' for call in mocked_execute.call_args_list)


def test_set_theme_applies_pdf_transition_settings(settings: Settings):
    """
    Test that PDF presentation transition settings override theme transition values.
    """
    # GIVEN: A service item with PDF transition settings and a slide controller with mocked displays
    slide_controller = SlideController(None)
    slide_controller.preview_display = MagicMock()
    slide_controller.displays = [MagicMock()]
    service_item = MagicMock()
    service_item.service_item_type = 'image'
    theme_data = MagicMock()
    theme_data.display_slide_transition = False
    theme_data.display_slide_transition_type = TransitionType.Fade
    theme_data.display_slide_transition_speed = TransitionSpeed.Normal
    service_item.get_theme_data.return_value = theme_data
    service_item.pdf_transition_settings = {
        'enabled': True,
        'type': TransitionType.Zoom,
        'speed': TransitionSpeed.Slow
    }

    # WHEN: _set_theme is called
    slide_controller._set_theme(service_item)

    # THEN: Both displays receive the override without changing the shared theme.
    applied_theme = slide_controller.preview_display.set_theme.call_args.args[0]
    assert applied_theme is not theme_data
    assert applied_theme.display_slide_transition is True
    assert applied_theme.display_slide_transition_type == TransitionType.Zoom
    assert applied_theme.display_slide_transition_speed == TransitionSpeed.Slow
    assert theme_data.display_slide_transition is False
    assert theme_data.display_slide_transition_type == TransitionType.Fade
    assert theme_data.display_slide_transition_speed == TransitionSpeed.Normal
    slide_controller.preview_display.set_theme.assert_called_once_with(applied_theme, service_item_type='image')
    slide_controller.displays[0].set_theme.assert_called_once_with(applied_theme, service_item_type='image')


@mark.parametrize('is_image,expected', [(True, False), (False, True)])
def test_disabled_collection_transition_does_not_inherit_theme(settings, is_image, expected):
    controller = SlideController(None)
    item = MagicMock()
    item.is_image.return_value = is_image
    item.slide_transition_settings = {'enabled': False, 'type': TransitionType.Fade}
    theme = MagicMock(display_slide_transition=True)

    controller._apply_service_item_transitions(item, theme)

    assert theme.display_slide_transition is expected


def test_live_stolen_focus_shortcuts(settings: Settings):
    """
    Test that all the needed shortcuts are available in scenarios where Live has stolen focus.
    These are found under def __add_actions_to_widget(self, widget): in slidecontroller.py
    """
    # GIVEN: A slide controller, actions needed
    slide_controller = SlideController(None)
    mocked_widget = MagicMock()
    slide_controller.previous_item = MagicMock()
    slide_controller.next_item = MagicMock()
    slide_controller.previous_service = MagicMock()
    slide_controller.next_service = MagicMock()
    slide_controller.show_screen = MagicMock()
    slide_controller.desktop_screen = MagicMock()
    slide_controller.blank_screen = MagicMock()
    slide_controller.theme_screen = MagicMock()
    slide_controller.logo_screen = MagicMock()

    # WHEN: __add_actions_to_widget is called
    slide_controller._SlideController__add_actions_to_widget(mocked_widget)

    # THEN: The call to addActions should be correct
    mocked_widget.addActions.assert_called_with([
        slide_controller.previous_item, slide_controller.next_item,
        slide_controller.previous_service, slide_controller.next_service,
        slide_controller.show_screen, slide_controller.desktop_screen,
        slide_controller.theme_screen, slide_controller.logo_screen,
        slide_controller.blank_screen
    ])


def test_on_preview_double_click_unblank_display(mock_settings: MagicMock):
    # GIVEN: A slide controller, actions needed, settings set to True.
    slide_controller = SlideController(None)
    mocked_settings = MagicMock()
    mocked_settings.return_value = True
    mock_settings.return_value = mocked_settings
    slide_controller.service_item = MagicMock()
    slide_controller.service_item.is_media = MagicMock()
    slide_controller.on_media_close = MagicMock()
    slide_controller.on_go_live = MagicMock()
    slide_controller.on_preview_add_to_service = MagicMock()
    slide_controller.media_reset = MagicMock()
    Registry().set_flag('has doubleclick added item to service', True)

    # WHEN: on_preview_double_click is called
    slide_controller.on_preview_double_click()

    # THEN: The call to addActions should be correct
    assert 1 == slide_controller.on_go_live.call_count, 'on_go_live should have been called once.'
    assert 0 == slide_controller.on_preview_add_to_service.call_count, 'Should have not been called.'


def test_on_preview_double_click_add_to_service(mock_settings: MagicMock):
    # GIVEN: A slide controller, actions needed, settings set to False.
    slide_controller = SlideController(None)
    mock_settings.value.return_value = False
    slide_controller.service_item = MagicMock()
    slide_controller.service_item.is_media = MagicMock()
    slide_controller.on_media_close = MagicMock()
    slide_controller.on_go_live = MagicMock()
    slide_controller.on_preview_add_to_service = MagicMock()
    slide_controller.media_reset = MagicMock()
    Registry().set_flag('has doubleclick added item to service', False)

    # WHEN: on_preview_double_click is called
    slide_controller.on_preview_double_click()

    # THEN: The call to addActions should be correct
    assert 0 == slide_controller.on_go_live.call_count, 'on_go_live Should have not been called.'
    assert 1 == slide_controller.on_preview_add_to_service.call_count, 'Should have been called once.'


def test_update_preview_live(settings: Settings):
    """
    Test that the preview screen is updated with a screen grab for live service items
    """
    # GIVEN: A mocked live service item, a mocked Registry,
    #        and a slide controller with many mocks.
    # Mocked Live Item
    mocked_live_item = MagicMock()
    mocked_live_item.get_rendered_frame.return_value = ''
    mocked_live_item.get_transition_delay.return_value = 0
    mocked_live_item.is_capable = MagicMock()
    mocked_live_item.is_capable.side_effect = [True, True]
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    # Mock SlideController
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_live_item
    slide_controller.is_live = True
    slide_controller._current_hide_mode = None
    slide_controller._capture_main_display_for_live_preview = True
    slide_controller.preview_display = MagicMock()
    slide_controller.log_debug = MagicMock()
    slide_controller.selected_row = MagicMock()
    slide_controller.screens = MagicMock()
    slide_controller.screens.current = {'primary': ''}
    slide_controller.displays = [MagicMock()]
    slide_controller.display.preview.return_value = QtGui.QImage()
    slide_controller.display_maindisplay = MagicMock()
    slide_controller.slide_preview = MagicMock()
    slide_controller.slide_count = 0
    slide_controller.slide_changed_time = datetime.datetime.now()
    slide_controller.is_slide_loaded = MagicMock()
    slide_controller.live_preview_capture_timer = MagicMock()

    # WHEN: update_preview is called
    slide_controller.update_preview()

    # THEN: Live preview capture should be deferred, keeping update_preview non-blocking
    assert 0 == slide_controller.slide_preview.setPixmap.call_count, 'setPixmap should NOT have been called'
    assert 0 == slide_controller.display.preview.call_count, 'display.preview() should NOT have been called'
    assert 0 == slide_controller.display_maindisplay.call_count, 'display_maindisplay() should NOT have been called'
    slide_controller.live_preview_capture_timer.start.assert_called_once_with(0)


def test_update_preview_live_hidden_blank(settings: Settings):
    """
    Test that the preview screen is updated with a screen grab for live service items when blank hidden mode.
    """
    # GIVEN: A mocked live service item, a mocked Registry,
    #        and a slide controller with many mocks.
    # Mocked Live Item
    mocked_live_item = MagicMock()
    mocked_live_item.get_rendered_frame.return_value = ''
    mocked_live_item.is_capable = MagicMock()
    mocked_live_item.is_capable.side_effect = [True, True]
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    # Mock SlideController
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_live_item
    slide_controller.is_live = True
    slide_controller._current_hide_mode = HideMode.Blank
    slide_controller._capture_main_display_for_live_preview = True
    slide_controller.preview_display = MagicMock()
    slide_controller.log_debug = MagicMock()
    slide_controller.selected_row = MagicMock()
    slide_controller.screens = MagicMock()
    slide_controller.screens.current = {'primary': ''}
    slide_controller.displays = [MagicMock()]
    slide_controller.display.preview.return_value = QtGui.QImage()
    slide_controller.display_maindisplay = MagicMock()
    slide_controller.slide_preview = MagicMock()
    slide_controller.slide_count = 0
    slide_controller.slide_changed_time = datetime.datetime.now()

    # WHEN: Setting 'core/live preview shows blank screen' is inactive and update_preview is called
    settings.setValue('core/live preview shows blank screen', False)
    slide_controller.update_preview()

    # THEN: A screen_grab should NOT have been called
    assert 0 == slide_controller.slide_preview.setPixmap.call_count, 'setPixmap should NOT have been called'
    assert 0 == slide_controller.display.preview.call_count, 'display.preview() should NOT have been called'
    assert 0 == slide_controller.display_maindisplay.call_count, 'display_maindisplay() should NOT have been called'

    # WHEN: Setting 'core/live preview shows blank screen' is active and update_preview is called
    settings.setValue('core/live preview shows blank screen', True)
    slide_controller.update_preview()

    # THEN: A screen_grab should NOT have been called
    assert 0 == slide_controller.slide_preview.setPixmap.call_count, 'setPixmap should NOT have been called'
    assert 0 == slide_controller.display.preview.call_count, 'display.preview() should NOT have been called'
    assert 0 == slide_controller.display_maindisplay.call_count, 'display_maindisplay() should NOT have been called'


def test_update_preview_presentation(settings: Settings):
    """
    Test that the preview screen is updated with the correct preview for presentation service items
    """
    # GIVEN: A mocked presentation service item, a mocked Registry,
    #        and a slide controller with many mocks.
    # Mocked Presentation Item
    mocked_pres_item = MagicMock()
    mocked_pres_item.get_rendered_frame.return_value = ''
    mocked_pres_item.is_capable = MagicMock()
    mocked_pres_item.is_capable.side_effect = [True, True]
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    # Mock SlideController
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_pres_item
    slide_controller.is_live = False
    slide_controller._current_hide_mode = None
    slide_controller.log_debug = MagicMock()
    slide_controller.selected_row = MagicMock()
    slide_controller.screens = MagicMock()
    slide_controller.screens.current = {'primary': ''}
    slide_controller.displays = [MagicMock()]
    slide_controller.display.preview.return_value = QtGui.QImage()
    slide_controller.display_maindisplay = MagicMock()
    slide_controller.slide_preview = MagicMock()
    slide_controller.slide_count = 0
    slide_controller.preview_display = MagicMock()
    slide_controller.preview_display.hide_display = MagicMock()

    # WHEN: Setting 'core/live preview shows blank screen' is inactive and update_preview is called
    settings.setValue('core/live preview shows blank screen', False)
    slide_controller.update_preview()

    # THEN: A screen_grab should NOT have been called
    assert 1 == slide_controller.preview_display.set_single_image.call_count, 'set_single_image should be called'
    assert 0 == slide_controller.display_maindisplay.call_count, 'display_maindisplay() should NOT have been called'


def test_update_preview_media(settings: Settings):
    """
    Test that the preview screen is updated with the correct preview for media service items
    """
    # GIVEN: A mocked media service item, a mocked Registry,
    #        and a slide controller with many mocks.
    # Mocked Media Item
    mocked_media_item = MagicMock()
    mocked_media_item.get_rendered_frame.return_value = ''
    mocked_media_item.is_capable = MagicMock()
    mocked_media_item.is_capable.side_effect = [True, False]
    # Mock Registry
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    # Mock SlideController
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_media_item
    slide_controller.is_live = False
    slide_controller._current_hide_mode = None
    slide_controller.log_debug = MagicMock()
    slide_controller.selected_row = MagicMock()
    slide_controller.screens = MagicMock()
    slide_controller.screens.current = {'primary': ''}
    slide_controller.displays = [MagicMock()]
    slide_controller.display.preview.return_value = QtGui.QImage()
    slide_controller.display_maindisplay = MagicMock()
    slide_controller.slide_preview = MagicMock()
    slide_controller.slide_count = 0
    slide_controller.preview_display = MagicMock()

    # WHEN: update_preview is called
    settings.setValue('core/live preview shows blank screen', False)
    slide_controller.update_preview()

    # THEN: A screen_grab should NOT have been called
    assert 1 == slide_controller.preview_display.set_single_image.call_count, 'set_single_image should be called'
    assert 0 == slide_controller.display_maindisplay.call_count, 'display_maindisplay() should NOT have been called'


def test_update_preview_image(settings: Settings):
    """
    Test that the preview screen is updated with the correct preview for image service items
    """
    # GIVEN: A mocked image service item, a mocked Registry,
    #        and a slide controller with many mocks.
    # Mocked Image Item
    mocked_img_item = MagicMock()
    mocked_img_item.get_rendered_frame.return_value = ''
    mocked_img_item.is_capable = MagicMock()
    mocked_img_item.is_capable.side_effect = [False, True]
    # Mock Registry
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    # Mock SlideController
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_img_item
    slide_controller.is_live = False
    slide_controller._current_hide_mode = None
    slide_controller.log_debug = MagicMock()
    slide_controller.selected_row = MagicMock()
    slide_controller.screens = MagicMock()
    slide_controller.screens.current = {'primary': ''}
    slide_controller.displays = [MagicMock()]
    slide_controller.display_maindisplay = MagicMock()
    slide_controller.slide_preview = MagicMock()
    slide_controller.slide_count = 0
    slide_controller.preview_display = MagicMock()

    # WHEN: update_preview is called
    settings.setValue('core/live preview shows blank screen', False)
    slide_controller.update_preview()

    # THEN: setPixmap and display.preview should have been called
    assert 0 == slide_controller.preview_display.go_to_slide.call_count, 'go_to_slide should NOT be called'
    assert 0 == slide_controller.display_maindisplay.call_count, 'display_maindisplay() should NOT have been called'


def test_update_preview_live_mirror_presentation_screen(settings: Settings):
    """
    Test that live preview mirrors the presentation display when the related setting is enabled.
    """
    # GIVEN: A mocked text/image style service item shown on live controller
    mocked_live_item = MagicMock()
    mocked_live_item.get_transition_delay.return_value = 0
    mocked_live_item.is_capable.return_value = False
    mocked_main_window = MagicMock()
    Registry().register('main_window', mocked_main_window)
    slide_controller = SlideController(None)
    slide_controller.service_item = mocked_live_item
    slide_controller.is_live = True
    slide_controller._current_hide_mode = None
    slide_controller.log_debug = MagicMock()
    slide_controller.selected_row = 0
    slide_controller.screens = MagicMock()
    slide_controller.screens.current = {'primary': ''}
    slide_controller.displays = [MagicMock()]
    slide_controller.display_maindisplay = MagicMock()
    slide_controller.preview_display = MagicMock()
    slide_controller.slide_count = 0
    slide_controller.slide_changed_time = datetime.datetime.now()
    slide_controller.is_slide_loaded = MagicMock(return_value=True)
    slide_controller.live_preview_capture_timer = MagicMock()

    # WHEN: the mirror-presentation-screen setting is enabled
    settings.setValue('core/live preview shows presentation screen', True)
    slide_controller.update_preview()

    # THEN: Preview should schedule mirrored display capture instead of blocking update_preview
    slide_controller.display_maindisplay.assert_not_called()
    slide_controller.live_preview_capture_timer.start.assert_called_once_with(0)
    assert slide_controller.preview_display.go_to_slide.call_count == 0


@mark.parametrize('item_type', [ServiceItemType.Text, ServiceItemType.Image])
@mark.parametrize('intermediate_mode', [HideMode.Screen, HideMode.Logo, HideMode.Blank, HideMode.Theme, None])
def test_update_preview_restores_slides_after_show_desktop(settings: Settings, item_type, intermediate_mode):
    """A desktop capture is replaced even after a cover or mirror-setting change."""
    controller = SlideController(None)
    controller.is_live = True
    controller._current_hide_mode = None
    controller.service_item = ServiceItem(None)
    controller.service_item.service_item_type = item_type
    controller.service_item._rendered_slides = [{'verse': 'V1', 'text': 'First'},
                                                {'verse': 'V2', 'text': 'Second'}]
    controller.service_item.slides = [{'path': 'first.png'}, {'path': 'second.png'}]
    controller.selected_row = 1
    controller.slide_changed_time = datetime.datetime.now()
    controller.preview_display = MagicMock()
    controller.preview_display.hide_mode = intermediate_mode
    controller.preview_display.show_display.side_effect = lambda: setattr(controller.preview_display, 'hide_mode', None)
    controller._update_desktop_capture_timer = MagicMock()
    controller.output_has_changed = MagicMock()
    controller._capture_maindisplay = MagicMock(return_value='desktop capture')
    with patch('openlp.core.ui.slidecontroller.image_to_byte', return_value='desktop bytes'):
        controller.display_maindisplay()
    assert controller._live_preview_is_capture is True

    # An intermediate cover must not lose track of the captured slide underneath.
    if intermediate_mode is not None:
        controller._current_hide_mode = intermediate_mode
        with patch('openlp.core.ui.slidecontroller.image_to_byte', return_value='desktop bytes'):
            controller.update_preview()
        controller.preview_display.load_verses.assert_not_called()
        controller.preview_display.load_images.assert_not_called()
    controller._current_hide_mode = None

    controller.update_preview()

    if item_type == ServiceItemType.Text:
        controller.preview_display.load_verses.assert_called_once_with(controller.service_item.rendered_slides)
        controller.preview_display.load_images.assert_not_called()
    else:
        controller.preview_display.load_images.assert_called_once_with(controller.service_item.slides)
        controller.preview_display.load_verses.assert_not_called()
    controller.preview_display.go_to_slide.assert_called_once_with(1)
    if intermediate_mode is not None:
        controller.preview_display.show_display.assert_called_once_with()
    assert controller._live_preview_is_capture is False

    # Ordinary slide navigation must not rebuild the deck or lose its transitions.
    controller.preview_display.reset_mock()
    controller.update_preview()
    controller.preview_display.load_verses.assert_not_called()
    controller.preview_display.load_images.assert_not_called()


@mark.parametrize('capture_available', [False, True])
def test_desktop_monitor_captures_screen_without_becoming_transparent(settings: Settings, capture_available):
    """Desktop mode keeps the monitor visible and never uses a native slide thumbnail."""
    controller = SlideController(None)
    controller.is_live = True
    controller._current_hide_mode = HideMode.Screen
    controller.service_item = MagicMock(processor='PowerPointMac')
    controller.preview_display = MagicMock()
    controller.preview_display.hide_mode = HideMode.Logo
    controller.preview_display.show_display.side_effect = lambda: setattr(controller.preview_display, 'hide_mode', None)
    controller.slide_changed_time = datetime.datetime.now()
    controller._capture_maindisplay_desktop = MagicMock(return_value='desktop' if capture_available else None)
    controller._update_desktop_capture_timer = MagicMock()
    controller.output_has_changed = MagicMock()

    with patch('openlp.core.ui.slidecontroller.image_to_byte', return_value='desktop jpeg'):
        controller.update_preview()

    controller._capture_maindisplay_desktop.assert_called_once_with()
    controller.preview_display.hide_display.assert_not_called()
    controller.preview_display.go_to_slide.assert_not_called()
    controller.preview_display.set_single_image.assert_not_called()
    controller._update_desktop_capture_timer.assert_called_once_with()
    if capture_available:
        controller.preview_display.assert_has_calls([
            call.set_single_image_data('#000', 'desktop jpeg'), call.show_display()
        ])
        assert controller._live_preview_is_capture is True
    else:
        controller.preview_display.set_single_image_data.assert_not_called()
        controller.preview_display.show_display.assert_not_called()


def test_on_live_preview_capture_timer_runs_pending_capture(settings: Settings):
    """
    Test that deferred live preview capture executes when pending.
    """
    # GIVEN: A live slide controller with pending capture
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.service_item = MagicMock()
    slide_controller._pending_live_preview_capture = True
    slide_controller.display_maindisplay = MagicMock()

    # WHEN: The deferred capture timer fires
    slide_controller._on_live_preview_capture_timer()

    # THEN: One capture should be executed and pending flag cleared
    slide_controller.display_maindisplay.assert_called_once_with()
    assert slide_controller._pending_live_preview_capture is False


def test_on_live_preview_capture_timer_ignores_when_not_pending(settings: Settings):
    """
    Test that deferred live preview capture does nothing when no capture is pending.
    """
    # GIVEN: A live slide controller without pending capture
    slide_controller = SlideController(None)
    slide_controller.is_live = True
    slide_controller.service_item = MagicMock()
    slide_controller._pending_live_preview_capture = False
    slide_controller.display_maindisplay = MagicMock()

    # WHEN: The deferred capture timer fires
    slide_controller._on_live_preview_capture_timer()

    # THEN: No capture should run
    slide_controller.display_maindisplay.assert_not_called()


def test_update_item_transitions_updates_active_displays(settings: Settings):
    """
    Test that changing item transition settings updates all initialised displays immediately.
    """
    # GIVEN: A slide controller with initialised live/preview displays
    slide_controller = SlideController(None)
    live_display = MagicMock()
    live_display._is_initialised = True
    preview_display = MagicMock()
    preview_display._is_initialised = True
    preview_display.allow_item_transitions = False
    slide_controller.displays = [live_display]
    slide_controller.preview_display = preview_display
    settings.setValue('themes/item transitions', True)
    settings.setValue('themes/item transition speed', 'slow')
    settings.setValue('themes/item transition type', 'ease-in')

    # WHEN: Item transition settings are refreshed
    slide_controller._update_item_transitions()

    # THEN: Both displays should receive the update command
    live_display.run_in_display.assert_called_once_with('updateItemTransitionSettings', True, 1.2, 'ease-in')
    preview_display.run_in_display.assert_called_once_with('updateItemTransitionSettings', False, 1.2, 'ease-in')


@patch('openlp.core.ui.slidecontroller.image_to_byte')
def test_display_maindisplay(mocked_image_to_byte: MagicMock, registry: Registry):
    """
    Test the display_maindisplay method
    Here a string is substituted for what would be a screen capture of the display
    The `image_to_byte` mocked funtion just adds " bytified" to the string
    """
    # GIVEN: A mocked slide controller, with mocked functions
    slide_controller = SlideController(None)
    slide_controller._capture_maindisplay = MagicMock(return_value='placeholder')
    slide_controller.preview_display = MagicMock()
    mocked_image_to_byte.side_effect = lambda x: '{} bytified'.format(x)

    # WHEN: display_maindisplay is called
    slide_controller.display_maindisplay()

    # THEN: Should have grabbed the maindisplay and set to placeholder with a black background
    slide_controller._capture_maindisplay.assert_called_once()
    slide_controller.preview_display.set_single_image_data.assert_called_once_with('#000', 'placeholder bytified')


def test_live_preview_capture_failure_keeps_cached_slide(settings: Settings, tmp_path):
    """A missing native frame must not reload the same slide or flash an older frame."""
    image_path = tmp_path / 'slide.png'
    image_path.touch()
    controller = SlideController(None)
    controller.service_item = MagicMock()
    controller.service_item.is_capable.return_value = True
    controller.service_item.get_rendered_frame.return_value = image_path
    controller.selected_row = 1
    controller.screen_capture = image_path
    controller._capture_maindisplay = MagicMock(return_value=None)
    controller.preview_display = MagicMock()

    controller.display_maindisplay()

    controller.preview_display.set_single_image.assert_not_called()
    assert controller.screen_capture == image_path


CaptureMainDisplayMockReturn = namedtuple('CaptureMainDisplayMockReturn', ['slide_controller', 'mocked_primary_screen',
                                                                           'windowed_screenshot_mock',
                                                                           'mocked_screenlist_instance'])


def _init__capture_maindisplay_mocks(geometry: list, mocked_screenlist: MagicMock,
                                     mocked_application: MagicMock, mocked_is_wayland_compositor: MagicMock):
    mocked_is_wayland_compositor.return_value = False
    slide_controller = SlideController(None)
    windowed_screenshot_mock = QtGui.QPixmap(64, 33)
    display_mock = MagicMock(grab_screenshot_safe=MagicMock(return_value=windowed_screenshot_mock), is_display=True)
    slide_controller.displays = [display_mock]
    slide_controller.service_item = ServiceItem(None)
    mocked_geometry = MagicMock(
        x=MagicMock(return_value=geometry[1][0]),
        y=MagicMock(return_value=geometry[1][1]),
        left=MagicMock(return_value=geometry[1][0]),
        top=MagicMock(return_value=geometry[1][1]),
        width=MagicMock(return_value=geometry[1][2]),
        height=MagicMock(return_value=geometry[1][3])
    )
    mocked_display_geometry = MagicMock(
        x=MagicMock(return_value=geometry[0][0]),
        y=MagicMock(return_value=geometry[0][1]),
        left=MagicMock(return_value=geometry[0][0]),
        top=MagicMock(return_value=geometry[0][1]),
        width=MagicMock(return_value=geometry[0][2]),
        height=MagicMock(return_value=geometry[0][3])
    )
    mocked_screenlist_instance = MagicMock()
    mocked_screenlist.return_value = mocked_screenlist_instance
    mocked_screenlist_instance.current = MagicMock(display_geometry=mocked_display_geometry, geometry=mocked_geometry)
    mocked_primary_screen = MagicMock()
    mocked_application.primaryScreen = MagicMock(return_value=mocked_primary_screen)
    slide_controller.preview_display = MagicMock()
    return CaptureMainDisplayMockReturn(mocked_primary_screen=mocked_primary_screen, slide_controller=slide_controller,
                                        windowed_screenshot_mock=windowed_screenshot_mock,
                                        mocked_screenlist_instance=mocked_screenlist_instance)


@patch('openlp.core.ui.slidecontroller.image_to_byte')
@patch('openlp.core.ui.slidecontroller.ScreenList')
@patch('openlp.core.ui.slidecontroller.QtWidgets.QApplication')
@patch('openlp.core.ui.slidecontroller.is_wayland_compositor')
@mark.parametrize('geometry', [[[34, 67, 77, 42], [0, 0, 800, 600]]])
def test__capture_maindisplay(mocked_is_wayland_compositor: MagicMock, mocked_application: MagicMock,
                              mocked_screenlist: MagicMock, mocked_image_to_byte: MagicMock, geometry: list,
                              registry: Registry, settings: Settings):
    """
    Test the _capture_maindisplay method
    """
    # GIVEN: A mocked slide controller, with mocked functions
    mocks = _init__capture_maindisplay_mocks(geometry, mocked_screenlist, mocked_application,
                                             mocked_is_wayland_compositor)

    # WHEN: _capture_maindisplay is called
    mocks.slide_controller._capture_maindisplay()

    # THEN: Screenshot should have been taken with correct winId and dimensions
    mocks.mocked_screenlist_instance.current.try_grab_screen_part.assert_called_once()


@patch('openlp.core.ui.slidecontroller.ScreenList')
@patch('openlp.core.ui.slidecontroller.QtWidgets.QApplication')
@patch('openlp.core.ui.slidecontroller.is_wayland_compositor')
@mark.parametrize('item_type', [ServiceItemType.Text, ServiceItemType.Image])
def test_capture_rendered_item_uses_display_window(mocked_is_wayland_compositor: MagicMock,
                                                   mocked_application: MagicMock,
                                                   mocked_screenlist: MagicMock, item_type,
                                                   settings: Settings):
    """A rendered Live item is captured from OpenLP's output, not the desktop."""
    mocks = _init__capture_maindisplay_mocks([[34, 67, 77, 42], [0, 0, 800, 600]],
                                             mocked_screenlist, mocked_application,
                                             mocked_is_wayland_compositor)
    mocks.slide_controller.service_item.service_item_type = item_type
    mocks.slide_controller._current_hide_mode = None

    photo = mocks.slide_controller._capture_maindisplay()

    assert photo == mocks.windowed_screenshot_mock
    mocks.mocked_screenlist_instance.current.try_grab_screen_part.assert_not_called()


@patch('openlp.core.ui.slidecontroller.image_to_byte')
@patch('openlp.core.ui.slidecontroller.ScreenList')
@patch('openlp.core.ui.slidecontroller.QtWidgets.QApplication')
@patch('openlp.core.ui.slidecontroller.is_wayland_compositor')
@mark.parametrize('geometry', [[[34, 67, 77, 42], [0, 0, 800, 600]]])
def test__capture_maindisplay_wayland_fallbacks_to_windowed(mocked_is_wayland_compositor: MagicMock,
                                                            mocked_application: MagicMock,
                                                            mocked_screenlist: MagicMock,
                                                            mocked_image_to_byte: MagicMock, geometry: list,
                                                            registry: Registry, settings: Settings):
    """
    Test the _capture_maindisplay method fallbacks to windowed capture mode if user is running on Wayland compositor
    """
    # GIVEN: A mocked slide controller, with mocked functions
    mocks = _init__capture_maindisplay_mocks(geometry, mocked_screenlist, mocked_application,
                                             mocked_is_wayland_compositor)
    mocked_is_wayland_compositor.return_value = True

    # WHEN: _capture_maindisplay is called
    photo = mocks.slide_controller._capture_maindisplay()

    # THEN: Screenshot should have been taken from DisplayWindow and Screen should not be touched
    assert photo == mocks.windowed_screenshot_mock
    mocks.mocked_primary_screen.grabWindow.assert_not_called()


@patch('openlp.core.ui.slidecontroller.image_to_byte')
@patch('openlp.core.ui.slidecontroller.ScreenList')
@patch('openlp.core.ui.slidecontroller.QtWidgets.QApplication')
@patch('openlp.core.ui.slidecontroller.is_wayland_compositor')
@mark.parametrize('geometry', [[[400, 400, 800, 600], [0, 0, 800, 600]], [[510, 0, 800, 600], [0, 0, 800, 600]],
                               [[0, 320, 800, 600], [0, 0, 800, 600]], [[-200, -100, 800, 600], [0, 0, 800, 600]],
                               [[-120, 0, 800, 600], [0, 0, 800, 600]], [[0, -140, 800, 600], [0, 0, 800, 600]],
                               [[-150, 0, 800, 600], [-152, 0, 800, 600]], [[0, -210, 800, 600], [0, -200, 800, 600]],
                               [[200, 0, 800, 600], [120, 0, 800, 600]], [[0, 230, 800, 600], [0, 110, 800, 600]]])
def test__capture_maindisplay_offscreen_fallbacks_to_windowed(mocked_is_wayland_compositor: MagicMock,
                                                              mocked_application: MagicMock,
                                                              mocked_screenlist: MagicMock,
                                                              mocked_image_to_byte: MagicMock, geometry: list,
                                                              registry: Registry, settings: Settings):
    """
    Test the _capture_maindisplay method fallbacks to windowed capture mode if user have a display
    above/beyond screen boundaries.
    """
    # GIVEN: A mocked slide controller, with mocked functions and offscreen geometry
    mocks = _init__capture_maindisplay_mocks(geometry, mocked_screenlist, mocked_application,
                                             mocked_is_wayland_compositor)
    mocked_is_wayland_compositor.return_value = False

    # WHEN: _capture_maindisplay is called
    photo = mocks.slide_controller._capture_maindisplay()

    # THEN: Screenshot should have been taken from DisplayWindow and Screen should not be touched
    assert photo == mocks.windowed_screenshot_mock
    mocks.mocked_primary_screen.grabWindow.assert_not_called()


@patch('openlp.core.ui.slidecontroller.ScreenList')
@patch('openlp.core.ui.slidecontroller.QtWidgets.QApplication')
@patch('openlp.core.ui.slidecontroller.is_wayland_compositor')
@mark.parametrize('geometry', [[[34, 67, 77, 42], [0, 0, 800, 600]]])
def test__capture_maindisplay_offscreen_command_screenshot(mocked_is_wayland_compositor: MagicMock,
                                                           mocked_application: MagicMock,
                                                           mocked_screenlist: MagicMock, geometry: list,
                                                           registry: Registry, settings: Settings):
    """
    Test the _capture_maindisplay method invoke '{text}_attempt_screenshot' event on command-based service items.
    """
    # GIVEN: A mocked slide controller, with mocked functions and offscreen geometry
    mocks = _init__capture_maindisplay_mocks(geometry, mocked_screenlist, mocked_application,
                                             mocked_is_wayland_compositor)
    mocked_is_wayland_compositor.return_value = True
    mocks.slide_controller.service_item.capabilities = [ItemCapabilities.ProvidesOwnDisplay]
    mocks.slide_controller.service_item.name = 'screenshottable'
    mocks.slide_controller.service_item.service_item_type = ServiceItemType.Command
    mocks.slide_controller.selected_row = 0
    pixmap = QtGui.QPixmap(1, 1)

    def attempt_screenshot(params):
        nonlocal pixmap  # noqa: F824
        return True, pixmap

    registry.register_function('screenshottable_attempt_screenshot', attempt_screenshot)

    # WHEN: _capture_maindisplay is called
    photo = mocks.slide_controller._capture_maindisplay()

    # THEN: Screenshot should have been taken from DisplayWindow and Screen should not be touched
    assert photo == pixmap


@patch('openlp.core.ui.slidecontroller.ScreenList')
@patch('openlp.core.ui.slidecontroller.QtWidgets.QApplication')
@patch('openlp.core.ui.slidecontroller.is_wayland_compositor')
@mark.parametrize('geometry', [[[-800, -600, 800, 600], [0, 0, 800, 600]]])
def test__capture_maindisplay_window_fakes_black_screen_when_blank(mocked_is_wayland_compositor: MagicMock,
                                                                    mocked_application: MagicMock,
                                                                    mocked_screenlist: MagicMock,
                                                                    geometry: list,
                                                                    registry: Registry, settings: Settings):
    """
    Test the _capture_maindisplay_window method fakes a black screen if display mode is Screen or Blank.
    """
    # GIVEN: A mocked slide controller, with mocked functions and offscreen geometry
    mocks = _init__capture_maindisplay_mocks(geometry, mocked_screenlist, mocked_application,
                                             mocked_is_wayland_compositor)
    screen_size = QtCore.QSize(geometry[1][2], geometry[1][3])
    mocked_display = MagicMock()
    mocked_display.is_display = True
    mocked_display.hide_mode = HideMode.Blank
    mocked_display.size = MagicMock(return_value=screen_size)
    mocks.slide_controller.displays = [mocked_display]

    # WHEN: _capture_maindisplay is called
    pixmap = mocks.slide_controller._capture_maindisplay()

    # THEN: A fake black screen should be returned
    photo_size = pixmap.size()
    image = pixmap.toImage()
    assert photo_size.width() == screen_size.width()
    assert photo_size.height() == screen_size.height()
    assert image.pixelColor(int(geometry[1][2] / 2), int(geometry[1][3] / 2)).isValid()
    assert image.pixelColor(int(geometry[1][2] / 2), int(geometry[1][3] / 2)) == QtGui.QColorConstants.Black


@patch('openlp.core.ui.slidecontroller.ScreenList')
@patch('openlp.core.ui.slidecontroller.QtWidgets.QApplication')
@patch('openlp.core.ui.slidecontroller.is_wayland_compositor')
@mark.parametrize('geometry', [[[-800, -600, 800, 600], [0, 0, 800, 600]]])
def test__capture_maindisplay_window_uses_desktop_capture_when_screen_hidden(mocked_is_wayland_compositor: MagicMock,
                                                                              mocked_application: MagicMock,
                                                                              mocked_screenlist: MagicMock,
                                                                              geometry: list,
                                                                              registry: Registry,
                                                                              settings: Settings):
    """
    Test the _capture_maindisplay_window method mirrors the desktop if hide mode is Screen.
    """
    # GIVEN: A mocked slide controller with a display hidden to screen/desktop mode
    mocks = _init__capture_maindisplay_mocks(geometry, mocked_screenlist, mocked_application,
                                             mocked_is_wayland_compositor)
    mocked_display = MagicMock()
    mocked_display.is_display = True
    mocked_display.hide_mode = HideMode.Screen
    mocks.slide_controller.displays = [mocked_display]
    mocks.slide_controller._capture_maindisplay_desktop = MagicMock(return_value='desktop_capture')

    # WHEN: _capture_maindisplay_window is called
    pixmap = mocks.slide_controller._capture_maindisplay_window()

    # THEN: Desktop capture should be used for mirrored output
    assert pixmap == 'desktop_capture'
    mocks.slide_controller._capture_maindisplay_desktop.assert_called_once_with()


@patch('openlp.core.ui.slidecontroller.ScreenList')
def test__capture_maindisplay_desktop_uses_qt_capture(mocked_screenlist: MagicMock, settings: Settings):
    """
    Test that desktop capture always uses the Qt capture path.
    """
    # GIVEN: A slide controller with a current display geometry
    slide_controller = SlideController(None)
    mocked_current_screen = MagicMock()
    mocked_display_rect = MagicMock()
    mocked_current_screen.display_geometry = mocked_display_rect
    mocked_screenlist.return_value.current = mocked_current_screen
    slide_controller._capture_maindisplay_desktop_qt = MagicMock(return_value='qt_capture')

    # WHEN: desktop capture is requested
    pixmap = slide_controller._capture_maindisplay_desktop()

    # THEN: the Qt capture path should be used
    assert pixmap == 'qt_capture'
    slide_controller._capture_maindisplay_desktop_qt.assert_called_once_with(mocked_current_screen,
                                                                              mocked_display_rect)


def test__update_desktop_capture_timer_uses_fixed_interval(settings: Settings):
    """
    Test that desktop capture refresh uses the fixed interval.
    """
    # GIVEN: A slide controller with a desktop capture timer
    slide_controller = SlideController(None)
    slide_controller.desktop_capture_timer = MagicMock()
    slide_controller.desktop_capture_timer.isActive.return_value = False
    slide_controller.desktop_capture_timer.interval.return_value = 0
    slide_controller._current_hide_mode = None

    # WHEN: live preview mirroring enables the timer
    slide_controller._update_desktop_capture_timer(mirror_live_preview=True)

    # THEN: the timer should start with the fixed capture interval
    slide_controller.desktop_capture_timer.start.assert_called_once_with(DESKTOP_CAPTURE_INTERVAL_MS)


@mark.parametrize('media_type', [MediaType.Video, MediaType.DeviceStream, MediaType.NetworkStream])
@mark.parametrize('state', [MediaState.Playing, MediaState.Paused])
def test_live_media_monitor_keeps_refreshing_without_screen_mirroring(settings: Settings, media_type, state):
    """The timer that starts for native video must survive its first tick."""
    settings.setValue('core/live preview shows presentation screen', False)
    controller = SlideController(None)
    controller.is_live = True
    controller.service_item = ServiceItem(None)
    controller.service_item.name = 'media'
    controller.service_item.service_item_type = ServiceItemType.Command
    controller.service_item.capabilities = [ItemCapabilities.RequiresMedia]
    controller._current_hide_mode = None
    controller.media_play_item.media_type = media_type
    controller.media_play_item.is_playing = state
    controller.preview_display = MagicMock(hide_mode=None)
    controller.desktop_capture_timer = MagicMock()
    controller.desktop_capture_timer.isActive.return_value = False
    controller.slide_changed_time = datetime.datetime.now()
    controller._schedule_live_preview_capture = MagicMock()
    controller.output_has_changed = MagicMock()
    controller._capture_maindisplay_desktop = MagicMock(return_value='video frame')

    controller.update_preview()
    with patch('openlp.core.ui.slidecontroller.image_to_byte', return_value='video jpeg'):
        controller._on_desktop_capture_timer()
        controller._on_desktop_capture_timer()

    controller.desktop_capture_timer.start.assert_called_once_with(DESKTOP_CAPTURE_INTERVAL_MS)
    controller.desktop_capture_timer.stop.assert_not_called()
    assert controller._capture_maindisplay_desktop.call_count == 2
    assert controller.preview_display.set_single_image_data.call_count == 2
    controller.preview_display.set_single_image_data.assert_called_with('#000', 'video jpeg')
    controller.preview_display.go_to_slide.assert_not_called()

    # A cover must stop media-specific mirroring, even before playback pauses.
    for mode in (HideMode.Logo, HideMode.Blank, HideMode.Theme):
        controller._current_hide_mode = mode
        controller._on_desktop_capture_timer()
    assert controller.desktop_capture_timer.stop.call_count == 3
    assert controller._capture_maindisplay_desktop.call_count == 2

    # A retired video's delayed cleanup must not keep capturing over a new song.
    controller._current_hide_mode = None
    controller.service_item.name = 'songs'
    controller.service_item.capabilities = []
    controller._on_desktop_capture_timer()
    assert controller.desktop_capture_timer.stop.call_count == 4
    assert controller._capture_maindisplay_desktop.call_count == 2


@patch('openlp.core.ui.slidecontroller.image_to_byte')
def test_grab_maindisplay(mocked_image_to_byte: MagicMock, registry: Registry):
    """
    Test the grab_maindisplay method
    """
    # GIVEN: A mocked slide controller, with mocked functions
    registry.register('application', MagicMock())
    slide_controller = SlideController(None)
    slide_controller._capture_maindisplay = MagicMock(return_value='placeholder')
    slide_controller.preview_display = MagicMock()
    slide_controller.fetching_screenshot = False
    slide_controller.screen_capture = None
    slide_controller.service_item = MagicMock(get_transition_delay=MagicMock(return_value=1))
    slide_controller.slide_changed_time = datetime.datetime.now() - datetime.timedelta(seconds=10)
    mocked_image_to_byte.side_effect = lambda x: '{} bytified'.format(x)

    # WHEN: grab_maindisplay is called
    grabbed_stuff = slide_controller.grab_maindisplay()

    # THEN: Should have grabbed the maindisplay and ran image_to_byte on it
    slide_controller._capture_maindisplay.assert_called_once()
    assert grabbed_stuff == 'placeholder bytified'


@patch('openlp.core.ui.slidecontroller.image_to_byte')
def test_grab_maindisplay_cached(mocked_image_to_byte: MagicMock, registry: Registry):
    """
    Test the grab_maindisplay method with pre-cached screenshot
    """
    # GIVEN: A mocked slide controller, with mocked functions
    registry.register('application', MagicMock())
    slide_controller = SlideController(None)
    slide_controller._capture_maindisplay = MagicMock(return_value='placeholder')
    slide_controller.preview_display = MagicMock()
    slide_controller.fetching_screenshot = False
    slide_controller.screen_capture = 'cached screen_capture'
    mocked_image_to_byte.side_effect = lambda x: '{} bytified'.format(x)

    # WHEN: grab_maindisplay is called
    grabbed_stuff = slide_controller.grab_maindisplay()

    # THEN: Should have not grabbed the maindisplay and returned the cached image
    assert slide_controller._capture_maindisplay.call_count == 0
    assert grabbed_stuff == 'cached screen_capture'


def test_paint_event_text_fits():
    """
    Test the paintEvent method when text fits the label
    """
    font = QtGui.QFont()
    metrics = QtGui.QFontMetrics(font)

    with patch('openlp.core.ui.slidecontroller.QtWidgets.QLabel'), \
            patch('openlp.core.ui.slidecontroller.QtGui.QPainter') as mocked_qpainter:

        # GIVEN: An instance of InfoLabel, with horizontal padding and mocked text
        info_label = InfoLabel()
        test_string = 'Label Text'
        mocked_text = MagicMock()
        mocked_text.return_value = test_string
        info_label.setContentsMargins(8, 0, 8, 0)
        info_label.text = mocked_text

        # WHEN: The instance is wider than its text, and the paintEvent method is called
        info_label.resize(metrics.boundingRect(test_string).width() + 36, 30)
        info_label.paintEvent(MagicMock())

        # THEN: The text should be drawn left with the complete test_string
        mocked_qpainter().drawText.assert_called_once_with(info_label.contentsRect(),
                                                           QtCore.Qt.AlignmentFlag.AlignLeft |
                                                           QtCore.Qt.AlignmentFlag.AlignVCenter, test_string)


def test_paint_event_text_doesnt_fit():
    """
    Test the paintEvent method when text fits the label
    """
    font = QtGui.QFont()
    metrics = QtGui.QFontMetrics(font)

    with patch('openlp.core.ui.slidecontroller.QtWidgets.QLabel'), \
            patch('openlp.core.ui.slidecontroller.QtGui.QPainter') as mocked_qpainter:

        # GIVEN: An instance of InfoLabel, with horizontal padding and mocked text
        info_label = InfoLabel()
        test_string = 'Label Text'
        mocked_text = MagicMock()
        mocked_text.return_value = test_string
        info_label.setContentsMargins(8, 0, 8, 0)
        info_label.text = mocked_text

        # WHEN: The instance is narrower than its text, and the paintEvent method is called
        label_width = metrics.boundingRect(test_string).width() - 20
        info_label.resize(label_width + 16, 30)
        info_label.paintEvent(MagicMock())

        # THEN: The text should be drawn aligned left with an elided test_string
        elided_test_string = metrics.elidedText(test_string, QtCore.Qt.TextElideMode.ElideRight, label_width)
        mocked_qpainter().drawText.assert_called_once()
        draw_args = mocked_qpainter().drawText.call_args.args
        assert draw_args[0] == info_label.contentsRect()
        assert draw_args[1] == (QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        assert draw_args[2].endswith('…')
        assert len(draw_args[2]) <= len(test_string)


@patch('builtins.super')
def test_set_text(mocked_super: MagicMock):
    """
    Test the reimplemented setText method
    """
    # GIVEN: An instance of InfoLabel and mocked setToolTip method
    info_label = InfoLabel()
    set_tool_tip_mock = MagicMock()
    info_label.setToolTip = set_tool_tip_mock

    # WHEN: Calling the instance method setText
    info_label.setText('Label Text')

    # THEN: The setToolTip and super class setText methods should have been called with the same text
    set_tool_tip_mock.assert_called_once_with('Label Text')
    mocked_super().setText.assert_called_once_with('Label Text')


def test_initial_live_controller(registry: Registry):
    """
    Test the initial live slide controller state .
    """
    # GIVEN: A new SlideController instance.
    live_controller = LiveController(None)

    # WHEN: the default controller is built.
    # THEN: The controller should not be a live controller.
    assert live_controller.is_live is True, 'The slide controller should be a live controller'


def test_initial_preview_controller(registry: Registry):
    """
    Test the initial preview slide controller state.
    """
    # GIVEN: A new SlideController instance.
    preview_controller = PreviewController(None)

    # WHEN: the default controller is built.
    # THEN: The controller should not be a live controller.
    assert preview_controller.is_live is False, 'The slide controller should be a Preview controller'


@patch('openlp.core.ui.slidecontroller.DisplayWindow')
def test_live_display_receives_switch_action(mocked_display_class, registry: Registry):
    """The switch shortcut remains active when the independent projection window has focus."""
    main_window = MagicMock()
    main_window.view_switch_projection_item = QtGui.QAction()
    registry.register('main_window', main_window)
    live_controller = LiveController(None)
    live_controller._current_hide_mode = None
    live_controller.screens = [MagicMock(is_display=True)]
    live_controller.close_displays = MagicMock()
    live_controller._reset_blank = MagicMock()

    with patch.object(live_controller, '_SlideController__add_actions_to_widget'):
        live_controller.setup_displays()

    mocked_display_class.return_value.addAction.assert_called_once_with(main_window.view_switch_projection_item)


def test_close_displays(registry: Registry):
    """
    Test that closing the displays calls the correct methods
    """
    # GIVEN: A Live controller and a mocked display
    mocked_display = MagicMock()
    live_controller = LiveController(None)
    live_controller.displays = [mocked_display]

    # WHEN: close_displays() is called
    live_controller.close_displays()

    # THEN: The display is closed
    mocked_display.deregister_display.assert_called_once()
    mocked_display.setParent.assert_called_once_with(None)
    mocked_display.close.assert_called_once()
    assert live_controller.displays == []


@mark.parametrize('hide_mode', [HideMode.Logo, HideMode.Blank])
@mark.parametrize('new_media', [False, True])
def test_process_item_preserves_cover_after_video(settings, registry, hide_mode, new_media):
    """Going live from a covered video must not make the display transparent or unblank it."""
    registry.register('main_window', MagicMock())
    registry.register('media_controller', MagicMock())
    settings.setValue('core/auto unblank', False)
    controller = SlideController(None)
    controller.is_live = True
    controller._current_hide_mode = hide_mode
    controller.service_item = MagicMock()
    controller.service_item.is_media.return_value = True
    controller.service_item.is_command.return_value = True
    controller.service_item.is_capable.return_value = False
    controller.displays = [MagicMock()]
    for name in ('preview_widget', 'preview_display', 'enable_tool_bar', 'on_controller_size_changed',
                 'on_media_start', 'on_media_close', 'slide_selected', 'on_stop_loop', 'info_label',
                 'song_menu', 'toolbar', '_update_slide_action_enabled_state', '_reset_blank', 'set_hide_mode'):
        setattr(controller, name, MagicMock())
    controller.split = 0
    controller.type_prefix = 'live'
    item = MagicMock()
    item.is_text.return_value = not new_media
    item.is_command.return_value = new_media
    item.is_media.return_value = new_media
    item.is_image.return_value = False
    item.requires_media.return_value = False
    item.is_capable.return_value = False
    item.display_slides = []
    item.from_service = False

    controller._process_item(item, 0)

    assert controller.current_hide_mode == hide_mode
    controller.set_hide_mode.assert_not_called()
    controller.display.show_display.assert_not_called()
    controller.display.hide_display.assert_not_called()
    controller.toolbar.remove_widget.assert_not_called()
    controller.toolbar.add_toolbar_widget.assert_not_called()


@mark.parametrize('is_media', [False, True])
def test_live_toolbar_does_not_hide_or_force_compact_layout(settings, is_media):
    """Changing an item should update the existing controls without collapsing the toolbar."""
    controller = SlideController(None)
    for name in ('toolbar', 'mediabar', 'song_menu', 'play_slides_once', 'play_slides_loop',
                 'previous_item', 'next_item', 'set_hide_mode_menu'):
        setattr(controller, name, MagicMock())
    item = MagicMock()
    item.is_media.return_value = is_media

    controller.enable_live_tool_bar(item)

    controller.toolbar.hide.assert_not_called()
    controller.toolbar.show.assert_not_called()
    controller.mediabar.hide.assert_not_called()
    controller.set_hide_mode_menu.assert_not_called()
    controller.previous_item.setVisible.assert_not_called()
    controller.next_item.setVisible.assert_not_called()
    controller.previous_item.setEnabled.assert_called_once_with(not is_media)


@mark.parametrize('is_text', [False, True])
def test_wide_hide_controls_are_not_temporarily_hidden(settings, is_text):
    """Logo and Show must keep their positions while the current item's controls change."""
    controller = SlideController(None)
    controller.toolbar = MagicMock()
    controller.service_item = MagicMock()
    controller.service_item.is_text.return_value = is_text

    controller.set_hide_mode_menu(narrow=False)

    for args, kwargs in controller.toolbar.set_widget_visible.call_args_list:
        if len(args) > 1 and args[1] is False:
            assert 'logo_screen_button' not in args[0]
            assert 'show_screen_button' not in args[0]


@mark.parametrize('hide_mode,has_item,has_display,expected_icon', [
    (None, True, True, True),
    (HideMode.Blank, True, True, True),
    (HideMode.Theme, True, True, True),
    (HideMode.Logo, True, True, True),
    (HideMode.Screen, True, True, False),
    (None, False, True, True),
    (None, True, False, False),
])
def test_live_status_record_icon(settings, hide_mode, has_item, has_display, expected_icon):
    """Record indicates an active OpenLP display, including blank, theme and logo output."""
    from fluentqt import FontIcon
    from openlp.core.widgets import fluent as QtWidgets

    controller = SlideController(None)
    controller.output_status_label = QtWidgets.QLabel(controller)
    controller.output_status_icon = FontIcon('ic_fluent_record_24_regular', controller)
    controller.displays = [MagicMock()] if has_display else []
    controller._current_hide_mode = hide_mode

    controller._update_output_status(has_item)

    assert controller.output_status_icon.isHidden() is not expected_icon
    assert controller.output_status_label.property('onAir') is (has_item and hide_mode is None and has_display)
    if hide_mode == HideMode.Screen:
        assert controller.output_status_label.text() == 'Desktop'

    controller.close_displays()
    assert controller.output_status_icon.isHidden()


@mark.parametrize('narrow', [False, True])
def test_priority_display_modes_stay_visible(settings, narrow):
    """Resizing cannot move priority Live display modes into a menu."""
    controller = SlideController(None)
    controller._pinned_display_controls = True
    controller.toolbar = MagicMock()
    controller._update_desktop_hide_action_state = MagicMock()

    controller.set_hide_mode_menu(narrow)

    visible = {name for args in controller.toolbar.set_widget_visible.call_args_list
               for name in args.args[0] if args.args[1]}
    assert visible == set(WIDE_MENU + NON_TEXT_MENU)
    controller._update_desktop_hide_action_state.assert_called_once()


def test_slides_to_end_shows_stop_icon_when_started(settings):
    """Starting playback shows the Stop command on the selected action."""
    from openlp.core.common.i18n import UiStrings
    from openlp.core.ui.icons import UiIcons

    controller = SlideController(None)
    controller.play_slides_once = QtGui.QAction(controller)
    controller.play_slides_once.setCheckable(True)
    controller.play_slides_loop = QtGui.QAction(controller)
    controller.play_slides_menu = MagicMock()
    controller.on_toggle_loop = MagicMock()

    controller.on_play_slides_once(True)

    assert controller.play_slides_once.isChecked()
    assert controller.play_slides_once.icon().cacheKey() == UiIcons().stop.cacheKey()
    assert controller.play_slides_once.text() == UiStrings().StopPlaySlidesToEnd
    controller.play_slides_menu.setDefaultAction.assert_called_once_with(controller.play_slides_once)
    controller.on_toggle_loop.assert_called_once()


def test_pinned_live_modes_have_no_unmanaged_dropdown(settings, registry, qapp):
    """Mode changes must not reveal the old dropdown over the pinned buttons."""
    from openlp.core.widgets.toolbar import OpenLPToolbar
    from openlp.core.widgets import fluent as QtWidgets

    registry.register('application-qt', QtWidgets.QApplication.instance())
    controller = SlideController(None)
    controller.is_live = True
    controller._pinned_display_controls = True
    controller.category = 'Live'
    controller.toolbar = OpenLPToolbar(controller)
    controller._update_desktop_hide_action_state = MagicMock()
    controller._setup_display_mode_actions()
    controller.toolbar.resize(400, 48)
    controller.toolbar.show()
    qapp.process_events()

    assert not hasattr(controller, 'hide_menu')
    assert controller.toolbar.findChildren(QtWidgets.QSplitButton) == []
    actions = [controller.show_screen, controller.theme_screen, controller.logo_screen,
               controller.blank_screen, controller.desktop_screen]
    for mode in (None, HideMode.Theme, HideMode.Logo, HideMode.Blank, HideMode.Screen):
        controller._current_hide_mode = mode
        controller._sync_live_hide_action_state(True)
        qapp.process_events()
        buttons = [controller.toolbar.widgetForAction(action) for action in actions]
        assert all(not button.isHidden() for button in buttons)
        assert controller.toolbar.findChildren(QtWidgets.QSplitButton) == []
        for left, right in zip(buttons, buttons[1:]):
            assert left.geometry().right() < right.geometry().left()
    controller._sync_live_hide_action_state(False)
    assert not any(action.isChecked() for action in actions)
    controller.toolbar.close()
