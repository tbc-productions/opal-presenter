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
This module contains tests for the lib submodule of the Presentations plugin.
"""
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from openlp.core.common.registry import Registry
from openlp.core.ui import HideMode
from openlp.plugins.presentations.lib.mediaitem import MessageListener
from openlp.plugins.presentations.lib.messagelistener import Controller


@patch('openlp.plugins.presentations.lib.mediaitem.MessageListener._setup')
def test_start_presentation(media_mock, media_item):
    """
    Find and chose a controller to play a presentations.
    """
    # GIVEN: A single controller and service item wanting to use the controller
    mock_item = MagicMock()
    mock_item.processor = 'Powerpoint'
    mock_item.get_frame_path.return_value = "test.ppt"
    media_item.automatic = False
    mocked_controller = MagicMock()
    mocked_controller.available = True
    mocked_controller.supports = ['ppt']
    controllers = {
        'Powerpoint': mocked_controller
    }
    ml = MessageListener(media_item)
    ml.media_item = media_item
    ml.controllers = controllers
    ml.preview_handler = MagicMock()
    ml.timer = MagicMock()

    # WHEN: request the presentation to start
    ml.startup([mock_item, False, False, False])

    # THEN: The controllers will be setup.
    assert len(controllers) > 0, 'We have loaded a controller'


@patch('openlp.plugins.presentations.lib.mediaitem.MessageListener._setup')
def test_timing_toggle_updates_only_the_current_powerpoint(media_mock, media_item):
    listener = MessageListener(media_item)
    listener.live_handler = MagicMock()
    listener.live_handler.doc.file_path = Path('/tmp/current.pptx')
    item = MagicMock()
    item.processor = 'PowerPointMac'
    item.get_frame_path.return_value = Path('/tmp/current.pptx')

    listener.set_slide_timings([item, False])
    listener.live_handler.doc.set_slide_timings.assert_called_once_with(False)

    item.get_frame_path.return_value = Path('/tmp/other.pptx')
    listener.set_slide_timings([item, True])
    listener.live_handler.doc.set_slide_timings.assert_called_once_with(False)


@patch('openlp.plugins.presentations.lib.mediaitem.MessageListener._setup')
def test_timing_control_only_reports_usable_timings_for_current_mac_show(media_mock, media_item):
    listener = MessageListener(media_item)
    listener.live_handler = MagicMock()
    listener.live_handler.doc.file_path = Path('/tmp/current.pptx')
    listener.live_handler.doc._use_openlp_timing = True
    item = MagicMock()
    item.processor = 'PowerPointMac'
    item.get_frame_path.return_value = Path('/tmp/current.pptx')

    assert listener.has_slide_timings([item])
    listener.live_handler.doc._use_openlp_timing = False
    assert not listener.has_slide_timings([item])
    listener.live_handler.doc._use_openlp_timing = True
    item.get_frame_path.return_value = Path('/tmp/other.pptx')
    assert not listener.has_slide_timings([item])


def test_keynote_import_does_not_block_poll_or_restart():
    controller = Controller(True)
    controller.doc = MagicMock()
    controller.doc._opening = True

    assert controller.activate() is False
    controller.poll()

    controller.doc.is_active.assert_not_called()
    controller.doc.poll_slidenumber.assert_not_called()


def test_first_slide_keeps_native_slideshow_open():
    controller = Controller(True)
    controller.doc = MagicMock()
    controller.doc.starts_at_selected_slide = True
    controller.doc._opening = False
    controller.doc.is_active.return_value = True

    controller.first()

    controller.doc.goto_slide.assert_called_once_with(1)
    controller.doc.start_presentation.assert_not_called()


def test_selecting_slide_moves_running_show_while_logo_is_active():
    controller = Controller(True)
    controller.doc = MagicMock()
    controller.doc.is_active.return_value = True
    controller.hide_mode = HideMode.Logo
    controller.poll = MagicMock()

    controller.slide(4)

    assert controller.doc.ui_slidenumber == 5
    controller.doc.goto_slide.assert_called_once_with(5)
    controller.doc.start_presentation.assert_not_called()
    controller.poll.assert_called_once_with()


def test_logo_overlay_restores_running_presentation_on_selected_slide():
    controller = Controller(True)
    controller.doc = MagicMock()
    controller.doc._opening = False
    controller.doc.is_loaded.return_value = True
    controller.doc.is_active.return_value = True
    controller.doc.ui_slidenumber = 3
    with patch.object(Registry, 'execute') as execute:
        controller.blank(HideMode.Logo)
        controller.unblank()

    controller.doc.hide_for_overlay.assert_called_once_with()
    controller.doc.show_after_overlay.assert_called_once_with()
    controller.doc.goto_slide.assert_called_once_with(3)
    controller.doc.unblank_screen.assert_called_once_with()
    controller.doc.start_presentation.assert_not_called()
    assert execute.call_args_list == [call('live_display_hide', HideMode.Logo),
                                     call('live_display_hide', HideMode.Screen)]


def test_black_from_logo_blanks_native_show_before_revealing_it():
    controller = Controller(True)
    controller.doc = MagicMock()
    controller.doc._hidden_for_overlay = True
    controller.activate = MagicMock()
    with patch.object(Registry, 'execute') as execute:
        controller.blank(HideMode.Blank)

    controller.doc.blank_screen.assert_called_once_with()
    controller.doc.show_after_overlay.assert_called_once_with()
    controller.activate.assert_not_called()
    execute.assert_called_once_with('live_display_hide', HideMode.Screen)


def test_black_screen_returns_to_same_running_presentation():
    controller = Controller(True)
    controller.doc = MagicMock()
    controller.doc._opening = False
    controller.doc._hidden_for_overlay = False
    controller.doc.is_active.return_value = True
    controller.doc.ui_slidenumber = 4
    with patch.object(Registry, 'execute'):
        controller.blank(HideMode.Blank)
        controller.unblank()

    controller.doc.blank_screen.assert_called_once_with()
    controller.doc.unblank_screen.assert_called_once_with()
    controller.doc.goto_slide.assert_called_once_with(4)
    controller.doc.start_presentation.assert_not_called()


@patch('openlp.plugins.presentations.lib.mediaitem.MessageListener._setup')
def test_start_presentation_with_no_player(media_mock, media_item):
    """
    Find and chose a controller to play a presentations when the player is not available.
    """
    # GIVEN: A single controller and service item wanting to use the controller
    mock_item = MagicMock()
    mock_item.processor = 'Powerpoint'
    mock_item.get_frame_path.return_value = "test.ppt"
    media_item.automatic = False
    mocked_controller = MagicMock()
    mocked_controller.available = True
    mocked_controller.supports = ['ppt']
    mocked_controller1 = MagicMock()
    mocked_controller1.available = False
    mocked_controller1.supports = ['ppt']
    controllers = {
        'Impress': mocked_controller,
        'Powerpoint': mocked_controller1
    }
    ml = MessageListener(media_item)
    ml.media_item = media_item
    ml.controllers = controllers
    ml.preview_handler = MagicMock()
    ml.timer = MagicMock()

    # WHEN: request the presentation to start
    ml.startup([mock_item, False, False, False])

    # THEN: The controllers will be setup.
    assert len(controllers) > 0, 'We have loaded a controller'


@patch('openlp.plugins.presentations.lib.mediaitem.MessageListener._setup')
def test_start_pdf_presentation(media_mock, media_item):
    """
    Test the startup of pdf presentation succeed.
    """
    # GIVEN: A sservice item with a pdf
    mock_item = MagicMock()
    mock_item.processor = 'Pdf'
    mock_item.get_frame_path.return_value = "test.pdf"
    expected_identifier = mock_item.unique_identifier
    media_item.generate_slide_data = MagicMock()
    ml = MessageListener(media_item)
    ml.media_item = media_item
    ml.preview_handler = MagicMock()

    # WHEN: request the presentation to start
    ml.startup([mock_item, False, False, False])

    # THEN: The handler should be set to None
    assert ml.handler is None, 'The handler should be None'

    # THEN: unique_identifier should still be the same.
    assert mock_item.unique_identifier == expected_identifier, 'unique_identifier should not be changed'


def test_add_handler_failure():
    """
    Test that add_handler does set doc.slidenumber to 0 in case filed loading
    """
    # GIVEN: A Controller, a mocked doc-controller
    controller = Controller(True)
    mocked_doc_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_doc.load_presentation.return_value = False
    mocked_doc_controller.add_document.return_value = mocked_doc

    # WHEN: calling add_handler that fails
    controller.add_handler(mocked_doc_controller, MagicMock(), True, 0, "uuid")

    # THEN: ui_slidenumber should be 0
    assert controller.doc.ui_slidenumber == 0, 'doc.ui_slidenumber should be 0'


@patch('openlp.plugins.presentations.lib.messagelistener.PresentationList')
@patch('openlp.plugins.presentations.lib.messagelistener.Registry')
def test_add_handler_hide_mode_screen_and_slidenumber_zero(
        mocked_registry: MagicMock, mocked_presentation_list: MagicMock):
    """
    Test that add_handler calls stop() and Registry().execute() when hide_mode is HideMode.Screen.
    Also, verify that ui_slidenumber is set to 1 when slide_no = 0.
    """
    # GIVEN: A Controller, a mocked document controller, and dependencies
    controller = Controller(True)
    mocked_doc_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_doc.load_presentation.return_value = True
    mocked_doc_controller.add_document.return_value = mocked_doc
    mocked_registry_instance = mocked_registry.return_value

    # WHEN: Calling add_handler with hide_mode = HideMode.Screen and slide_no = 0
    with patch.object(controller, 'stop') as mocked_stop:
        controller.add_handler(mocked_doc_controller, MagicMock(), HideMode.Screen, 0, "uuid")

    # THEN: stop() and Registry.execute() should have been called, and ui_slidenumber should be set to 1
    mocked_registry_instance.execute.assert_called_with('live_display_hide', HideMode.Screen)
    mocked_stop.assert_called_once()
    assert controller.doc.ui_slidenumber == 1, 'doc.ui_slidenumber should be 1'


@patch('openlp.plugins.presentations.lib.messagelistener.PresentationList')
def test_add_handler_hide_mode_theme(mocked_presentation_list: MagicMock):
    """
    Test that add_handler calls blank() when hide_mode is HideMode.Theme.
    """
    # GIVEN: A Controller and a mocked document controller
    controller = Controller(True)
    mocked_doc_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_doc.load_presentation.return_value = True
    mocked_doc_controller.add_document.return_value = mocked_doc

    # WHEN: Calling add_handler with hide_mode = HideMode.Theme
    with patch.object(controller, 'blank') as mocked_blank:
        controller.add_handler(mocked_doc_controller, MagicMock(), HideMode.Theme, 1, "uuid")

    # THEN: blank() should have been called with HideMode.Theme
    mocked_blank.assert_called_once_with(HideMode.Theme)


@patch('openlp.plugins.presentations.lib.messagelistener.PresentationList')
def test_add_handler_hide_mode_blank(mocked_presentation_list: MagicMock):
    """
    Test that add_handler calls blank() when hide_mode is HideMode.Blank.
    """
    # GIVEN: A Controller and a mocked document controller
    controller = Controller(True)
    mocked_doc_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_doc.load_presentation.return_value = True
    mocked_doc_controller.add_document.return_value = mocked_doc

    # WHEN: Calling add_handler with hide_mode = HideMode.Blank
    with patch.object(controller, 'blank') as mocked_blank:
        controller.add_handler(mocked_doc_controller, MagicMock(), HideMode.Blank, 1, "uuid")

    # THEN: blank() should have been called with HideMode.Blank
    mocked_blank.assert_called_once_with(HideMode.Blank)


@patch('openlp.plugins.presentations.lib.messagelistener.PresentationList')
@patch('openlp.plugins.presentations.lib.messagelistener.Registry')
def test_add_handler_slidenumber_one(mocked_registry: MagicMock, mocked_presentation_list: MagicMock):
    """
    Test that add_handler starts once and jumps to the selected slide when slide_no = 1.
    """
    # GIVEN: A Controller, a mocked document controller, and dependencies
    controller = Controller(True)
    mocked_doc_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_doc.load_presentation.return_value = True
    mocked_doc.start_presentation = MagicMock()
    mocked_doc.starts_at_selected_slide = False
    mocked_doc_controller.add_document.return_value = mocked_doc
    mocked_registry_instance = mocked_registry.return_value

    # WHEN: Calling add_handler with slide_no = 1
    with patch.object(controller, 'slide') as mocked_slide:
        controller.add_handler(mocked_doc_controller, MagicMock(), None, 1, "uuid")

    # THEN: avoid calling slide(), which can restart the show before it reports active.
    mocked_slide.assert_not_called()
    assert mocked_doc.ui_slidenumber == 2
    mocked_doc.start_presentation.assert_called_once()
    mocked_doc.goto_slide.assert_called_once_with(2)
    mocked_registry_instance.execute.assert_called_with('live_display_hide', HideMode.Screen)


@patch('openlp.plugins.presentations.lib.messagelistener.PresentationList')
@patch('openlp.plugins.presentations.lib.messagelistener.Registry')
def test_add_handler_native_show_starts_at_selected_slide(mocked_registry, mocked_presentation_list):
    controller = Controller(True)
    document = MagicMock()
    document.load_presentation.return_value = True
    document.starts_at_selected_slide = True
    presentation_controller = MagicMock()
    presentation_controller.add_document.return_value = document

    controller.add_handler(presentation_controller, MagicMock(), None, 3, 'uuid')

    assert document.ui_slidenumber == 4
    document.start_presentation.assert_called_once_with()
    document.goto_slide.assert_not_called()


@patch('openlp.plugins.presentations.lib.mediaitem.MessageListener._setup')
def test_message_listener_next_passes_restore_focus_option(media_mock, media_item):
    """
    Test that MessageListener.next forwards restore_focus option to the live handler.
    """
    message_listener = MessageListener(media_item)
    message_listener.live_handler = MagicMock()
    message_listener.live_handler.next.return_value = False

    with patch('openlp.plugins.presentations.lib.messagelistener.Registry') as mocked_registry:
        mocked_registry.return_value.get.return_value.value.return_value = False
        message_listener.next([MagicMock(), True, {'restore_focus': False}])

    message_listener.live_handler.next.assert_called_once_with(restore_focus=False)


def test_controller_next_falls_back_for_legacy_controllers():
    """
    Test that Controller.next falls back when doc.next_step lacks restore_focus kwarg support.
    """
    controller = Controller(True)
    mocked_doc = MagicMock()
    mocked_doc.is_active.return_value = True
    mocked_doc.get_slide_count.return_value = 3
    mocked_doc.ui_slidenumber = 1
    mocked_doc.next_step.side_effect = [TypeError('unexpected keyword'), False]
    controller.doc = mocked_doc
    controller.activate = MagicMock(return_value=True)
    controller.poll = MagicMock()

    result = controller.next(restore_focus=False)

    assert result is False
    assert mocked_doc.next_step.call_count == 2
    mocked_doc.next_step.assert_any_call(restore_focus=False)
    mocked_doc.next_step.assert_any_call()
