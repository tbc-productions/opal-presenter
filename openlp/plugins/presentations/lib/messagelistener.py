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
import copy
import logging
from pathlib import Path

from PySide6 import QtCore

from openlp.core.common.registry import Registry
from openlp.core.lib import ServiceItemContext
from openlp.core.ui import HideMode
from openlp.plugins.presentations.lib.pdfcontroller import PDF_CONTROLLER_FILETYPES
from openlp.plugins.presentations.lib.presentationcontroller import PresentationList


log = logging.getLogger(__name__)


class Controller(object):
    """
    This is the Presentation listener who acts on events from the slide controller and passes the messages on the
    correct presentation handlers.
    """
    log.info('Controller loaded')

    def __init__(self, live):
        """
        Constructor
        """
        self.is_live = live
        self.doc = None
        self.hide_mode = None
        log.info('{name} controller loaded'.format(name=live))

    def add_handler(self, controller, file, hide_mode, slide_no, unique_id, file_hash=None):
        """
        Add a handler, which is an instance of a presentation and slidecontroller combination. If the slidecontroller
        has a display then load the presentation.
        """
        log.debug('Live = {live}, add_handler {handler}'.format(live=self.is_live, handler=file))
        self.controller = controller
        self.doc = self.controller.add_document(file)
        if file_hash and controller.name in ('Powerpoint', 'PowerPointMac'):
            settings = Registry().get('settings')
            choices = settings.value('presentations/powerpoint slide timings by file')
            self.doc.use_slide_timings = bool(choices.get(file_hash, False))
        if not self.doc.load_presentation():
            # Display error message to user
            # Inform slidecontroller that the action failed?
            self.doc.ui_slidenumber = 0
            return
        PresentationList().add(self.doc, f'{unique_id}_is_live_{self.is_live}')
        # SlideController uses zero-based rows; presentation controllers use one-based slide numbers.
        self.doc.ui_slidenumber = max(1, int(slide_no) + 1)
        self.hide_mode = hide_mode
        log.debug('add_handler, slide_number: {slide:d}'.format(slide=slide_no))
        if self.is_live:
            if hide_mode == HideMode.Screen:
                Registry().execute('live_display_hide', HideMode.Screen)
                self.stop()
            elif hide_mode == HideMode.Theme:
                self.blank(hide_mode)
            elif hide_mode == HideMode.Logo:
                self.blank(hide_mode)
            elif hide_mode == HideMode.Blank:
                self.blank(hide_mode)
            else:
                self.doc.start_presentation()
                Registry().execute('live_display_hide', HideMode.Screen)
                if slide_no > 0 and not getattr(self.doc, 'starts_at_selected_slide', False):
                    # Some backends report inactive just after starting. Calling slide() here
                    # would start the show a second time instead of selecting the requested slide.
                    self.doc.goto_slide(int(slide_no) + 1)

    def activate(self):
        """
        Active the presentation, and show it on the screen. Use the last slide number.
        """
        log.debug('Live = {live}, activate'.format(live=self.is_live))
        if not self.doc:
            return False
        if getattr(self.doc, '_opening', False):
            return False
        if self.doc.is_active():
            return True
        if not self.doc.is_loaded():
            if not self.doc.load_presentation():
                log.warning('Failed to activate {path}'.format(path=self.doc.file_path))
                return False
        if self.is_live:
            self.doc.start_presentation()
            if self.doc.ui_slidenumber > 1 and not getattr(self.doc, 'starts_at_selected_slide', False):
                if self.doc.ui_slidenumber > self.doc.get_slide_count():
                    self.doc.ui_slidenumber = self.doc.get_slide_count()
                self.doc.goto_slide(self.doc.ui_slidenumber)
        if self.doc.is_active():
            return True
        else:
            log.warning('Failed to activate {path}'.format(path=self.doc.file_path))
            return False

    def slide(self, slide):
        """
        Go to a specific slide
        """
        log.debug('Live = {live}, slide'.format(live=self.is_live))
        if not self.doc:
            return
        if not self.is_live:
            return
        self.doc.ui_slidenumber = int(slide) + 1
        if self.hide_mode:
            # A native show can still be running while its output is blanked.
            # Keep that show on the operator's selected slide without revealing it.
            if self.doc.is_active():
                self.doc.goto_slide(int(slide) + 1)
            self.poll()
            return
        was_active = self.doc.is_active()
        if not self.activate():
            return
        if was_active or not getattr(self.doc, 'starts_at_selected_slide', False):
            self.doc.goto_slide(int(slide) + 1)
        self.poll()

    def first(self):
        """
        Based on the handler passed at startup triggers the first slide.
        """
        log.debug('Live = {live}, first'.format(live=self.is_live))
        if not self.doc:
            return
        if not self.is_live:
            return
        self.doc.ui_slidenumber = 1
        if self.hide_mode:
            if self.doc.is_active():
                self.doc.goto_slide(1)
            self.poll()
            return
        was_active = self.doc.is_active()
        if not self.activate():
            return
        if getattr(self.doc, 'starts_at_selected_slide', False):
            if was_active:
                self.doc.goto_slide(1)
        else:
            self.doc.start_presentation()
        self.poll()

    def last(self):
        """
        Based on the handler passed at startup triggers the last slide.
        """
        log.debug('Live = {live}, last'.format(live=self.is_live))
        if not self.doc:
            return
        if not self.is_live:
            return
        self.doc.ui_slidenumber = self.doc.get_slide_count()
        if self.hide_mode:
            if self.doc.is_active():
                self.doc.goto_slide(self.doc.ui_slidenumber)
            self.poll()
            return
        if not self.activate():
            return
        self.doc.goto_slide(self.doc.get_slide_count())
        self.poll()

    def next(self, restore_focus=True):
        """
        Based on the handler passed at startup triggers the next slide event.
        """
        log.debug('Live = {live}, next'.format(live=self.is_live))
        if not self.doc:
            return False
        if not self.is_live:
            return False
        if not self.doc.is_active():
            return False
        if self.doc.ui_slidenumber < self.doc.get_slide_count():
            self.doc.ui_slidenumber += 1
        if self.hide_mode:
            self.poll()
            return False
        if not self.activate():
            return False
        try:
            ret = self.doc.next_step(restore_focus=restore_focus)
        except TypeError:
            # Backward compatibility for controllers not yet updated with restore_focus.
            ret = self.doc.next_step()
        self.poll()
        return ret

    def previous(self):
        """
        Based on the handler passed at startup triggers the previous slide event.
        """
        log.debug('Live = {live}, previous'.format(live=self.is_live))
        if not self.doc:
            return False
        if not self.is_live:
            return False
        if not self.doc.is_active():
            return False
        if self.doc.ui_slidenumber > 1:
            self.doc.ui_slidenumber -= 1
        if self.hide_mode:
            self.poll()
            return False
        if not self.activate():
            return False
        ret = self.doc.previous_step()
        self.poll()
        return ret

    def shutdown(self, unique_id):
        """
        Based on the handler passed at startup triggers slide show to shut down.
        """
        log.debug('Live = {live}, shutdown'.format(live=self.is_live))
        presentation_to_close = PresentationList().get_presentation_by_id(f'{unique_id}_is_live_{self.is_live}')
        if presentation_to_close:
            presentation_to_close.close_presentation()
            PresentationList().remove(f'{unique_id}_is_live_{self.is_live}')

    def blank(self, hide_mode):
        """
        Instruct the controller to blank the presentation.
        """
        log.debug('Live = {live}, blank'.format(live=self.is_live))
        self.hide_mode = hide_mode
        if not self.is_live:
            return
        if hide_mode in (HideMode.Theme, HideMode.Logo):
            Registry().execute('live_display_hide', hide_mode)
            if self.doc and self.doc.is_loaded() and self.doc.is_active():
                hide_for_overlay = getattr(self.doc, 'hide_for_overlay', None)
                if callable(hide_for_overlay):
                    hide_for_overlay()
            return
        if not self.doc:
            return
        if hide_mode == HideMode.Blank:
            if not getattr(self.doc, '_hidden_for_overlay', False) and \
                    not self.doc.is_active() and not self.activate():
                return
            self.doc.blank_screen()
            show_after_overlay = getattr(self.doc, 'show_after_overlay', None)
            if callable(show_after_overlay):
                show_after_overlay()
            Registry().execute('live_display_hide', HideMode.Screen)
        elif hide_mode == HideMode.Screen:
            Registry().execute('live_display_hide', HideMode.Screen)
            self.stop()

    def stop(self):
        """
        Instruct the controller to stop and hide the presentation.
        """
        log.debug('Live = {live}, stop'.format(live=self.is_live))
        # The document has not been loaded yet, so don't do anything. This can happen when going live with a
        # presentation while blanked to desktop.
        if not self.doc:
            return
        # Save the current slide number to be able to return to this slide if the presentation is activated again.
        if self.doc.is_active():
            self.doc.ui_slidenumber = self.doc.get_slide_number()
        self.hide_mode = HideMode.Screen
        if not self.doc:
            return
        if not self.is_live:
            return
        if not self.doc.is_loaded():
            return
        if not self.doc.is_active():
            return
        self.doc.stop_presentation()

    def unblank(self):
        """
        Instruct the controller to unblank the presentation.
        """
        log.debug('Live = {live}, unblank'.format(live=self.is_live))
        self.hide_mode = None
        if not self.doc:
            return
        if not self.is_live:
            return
        show_after_overlay = getattr(self.doc, 'show_after_overlay', None)
        if callable(show_after_overlay):
            show_after_overlay()
        if not self.activate():
            return
        # if a different slide has been selected while blank, this will transfer to the correct slide
        self.doc.goto_slide(self.doc.ui_slidenumber)
        self.doc.unblank_screen()
        Registry().execute('live_display_hide', HideMode.Screen)

    def poll(self):
        if not self.doc or getattr(self.doc, '_opening', False):
            return
        self.doc.poll_slidenumber(self.is_live, self.hide_mode)

    def attempt_screenshot(self, index):
        """
        Tries to perform a live screenshot when visible service item uses ProvidesOwnDisplay flag.

        :returns: A tuple: whether the request succedded, and then the image.
        """
        if self.is_live:
            return self.doc.attempt_screenshot(index)
        return (False, None)


class MessageListener(object):
    """
    This is the Presentation listener who acts on events from the slide controller and passes the messages on the
    correct presentation handlers
    """
    log.info('Message Listener loaded')

    def __init__(self, media_item):
        self._setup(media_item)

    def _setup(self, media_item):
        """
        Start up code moved out to make mocking easier
        :param media_item: The plugin media item handing Presentations
        """
        self.controllers = media_item.controllers
        self.media_item = media_item
        self.preview_handler = Controller(False)
        self.live_handler = Controller(True)
        # messages are sent from core.ui.slidecontroller
        Registry().register_function('presentations_start', self.startup)
        Registry().register_function('presentations_stop', self.shutdown)
        Registry().register_function('presentations_hide', self.hide)
        Registry().register_function('presentations_first', self.first)
        Registry().register_function('presentations_previous', self.previous)
        Registry().register_function('presentations_next', self.next)
        Registry().register_function('presentations_last', self.last)
        Registry().register_function('presentations_slide', self.slide)
        Registry().register_function('presentations_set_slide_timings', self.set_slide_timings)
        Registry().register_function('presentations_has_slide_timings', self.has_slide_timings)
        Registry().register_function('presentations_blank', self.blank)
        Registry().register_function('presentations_unblank', self.unblank)
        Registry().register_function('presentations_attempt_screenshot', self.attempt_live_screenshot)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.timeout)

    def startup(self, message):
        """
        Start of new presentation. Save the handler as any new presentations start here
        """
        log.debug('Startup called with message {text}'.format(text=message))
        is_live = message[1]
        item = message[0]
        hide_mode = message[2]
        file_path = Path(item.get_frame_path())
        self.handler = item.processor
        # When starting presentation from the servicemanager we convert
        # PDF/XPS/OXPS-serviceitems into image-serviceitems. When started from the mediamanager
        # the conversion has already been done at this point.
        render_as_images = self.media_item.should_render_as_images(file_path, self.handler)
        if render_as_images:
            log.debug('Converting presentation to images for serviceitem with file %s', file_path)
            # Create a copy of the original item, and then clear the original item so it can be filled with images
            item_cpy = copy.copy(item)
            item.__init__(None)
            context = ServiceItemContext.Live if is_live else ServiceItemContext.Preview
            if self.media_item.generate_slide_data(item, item=item_cpy, context=context, file_path=file_path):
                # Keep the service identity when replacing a command item with images.
                item.footer = item_cpy.footer
                item.from_service = item_cpy.from_service
                item.from_plugin = item_cpy.from_plugin
                item.name = item_cpy.name
                item.icon = item_cpy.icon
                item.iconic_representation = item_cpy.icon
                item.main = item_cpy.main
                item.theme = item_cpy.theme
                item.unique_identifier = item_cpy.unique_identifier
                self.handler = None
            else:
                log.warning('Could not render presentation slides for %s', file_path)
                item.__dict__.clear()
                item.__dict__.update(item_cpy.__dict__)
                if file_path.suffix.lower()[1:] in PDF_CONTROLLER_FILETYPES:
                    return
        if self.handler is not None:
            if self.handler == self.media_item.automatic:
                self.handler = self.media_item.find_controller_by_type(file_path)
                if not self.handler:
                    return
            else:
                # the saved handler is not present so need to use one based on file_path suffix.
                if self.handler not in self.controllers or not self.controllers[self.handler].available:
                    self.handler = self.media_item.find_controller_by_type(file_path)
                    if not self.handler:
                        return
        if is_live:
            controller = self.live_handler
        else:
            controller = self.preview_handler
        # When presenting PDF/XPS/OXPS, we are using the image presentation code,
        # so handler & processor is set to None, and we skip adding the handler.
        if self.handler is None:
            self.controller = controller
        else:
            controller.add_handler(self.controllers[self.handler], file_path, hide_mode, message[3],
                                   message[0].unique_identifier, message[0].sha256_file_hash)
            self.timer.start()

    def set_slide_timings(self, message):
        """Apply the Live toolbar's timing state to its current PowerPoint show."""
        item, enabled = message
        doc = self.live_handler.doc
        if not doc or item.processor not in ('Powerpoint', 'PowerPointMac'):
            return
        if Path(item.get_frame_path()) != doc.file_path:
            return
        if hasattr(doc, 'set_slide_timings'):
            doc.set_slide_timings(bool(enabled))
        else:
            doc.use_slide_timings = bool(enabled)
        return bool(doc.use_slide_timings)

    def has_slide_timings(self, message):
        """Report whether the current PowerPoint show has controllable timed slides."""
        item = message[0]
        doc = self.live_handler.doc
        if not doc or item.processor != 'PowerPointMac' or Path(item.get_frame_path()) != doc.file_path:
            return False
        return bool(getattr(doc, '_use_openlp_timing', False))

    def slide(self, message):
        """
        React to the message to move to a specific slide.

        :param message: The message {1} is_live {2} slide
        """
        is_live = message[1]
        slide = message[2]
        if is_live:
            self.live_handler.slide(slide)
        else:
            self.preview_handler.slide(slide)

    def first(self, message):
        """
        React to the message to move to the first slide.

        :param message: The message {1} is_live
        """
        is_live = message[1]
        if is_live:
            self.live_handler.first()
        else:
            self.preview_handler.first()

    def last(self, message):
        """
        React to the message to move to the last slide.

        :param message: The message {1} is_live
        """
        is_live = message[1]
        if is_live:
            self.live_handler.last()
        else:
            self.preview_handler.last()

    def next(self, message):
        """
        React to the message to move to the next animation/slide.

        :param message: The message {1} is_live
        """
        is_live = message[1]
        options = message[2] if len(message) > 2 and isinstance(message[2], dict) else {}
        restore_focus = options.get('restore_focus', True)
        if is_live:
            ret = self.live_handler.next(restore_focus=restore_focus)
            if Registry().get('settings').value('core/click live slide to unblank'):
                Registry().execute('slidecontroller_live_unblank')
            return ret
        else:
            return self.preview_handler.next()

    def previous(self, message):
        """
        React to the message to move to the previous animation/slide.

        :param message: The message {1} is_live
        """
        is_live = message[1]
        if is_live:
            ret = self.live_handler.previous()
            if Registry().get('settings').value('core/click live slide to unblank'):
                Registry().execute('slidecontroller_live_unblank')
            return ret
        else:
            return self.preview_handler.previous()

    def shutdown(self, message):
        """
        React to message to shutdown the presentation. I.e. end the show and close the file.

        :param message: The message {1} is_live
        """
        is_live = message[1]
        if is_live:
            self.live_handler.shutdown(message[0].unique_identifier)
            self.timer.stop()
        else:
            self.preview_handler.shutdown(message[0].unique_identifier)

    def hide(self, message):
        """
        React to the message to show the desktop.

        :param message: The message {1} is_live
        """
        is_live = message[1]
        if is_live:
            self.live_handler.stop()

    def blank(self, message):
        """
        React to the message to blank the display.

        :param message: The message {1} is_live {2} slide
        """
        is_live = message[1]
        hide_mode = message[2]
        if is_live:
            self.live_handler.blank(hide_mode)

    def unblank(self, message):
        """
        React to the message to unblank the display.

        :param message: The message {1} is_live
        """
        is_live = message[1]
        if is_live:
            self.live_handler.unblank()

    def timeout(self):
        """
        The presentation may be timed or might be controlled by the application directly, rather than through OpenLP.
        Poll occasionally to check which slide is currently displayed so the slidecontroller view can be updated.
        """
        self.live_handler.poll()

    def attempt_live_screenshot(self, message):
        """
        Tries to perform a live screenshot when visible service item uses ProvidesOwnDisplay flag.

        :returns: A tuple: whether the request succedded, and then the image.
        """
        current_row = message[1]
        result = self.live_handler.attempt_screenshot(current_row)
        return result
