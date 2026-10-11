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
This module is for controlling keynote.
"""
import logging
import shutil
import subprocess
from PySide6 import QtCore
try:
    import applescript
    APPLESCRIPT_AVAILABLE = True
except ImportError:
    APPLESCRIPT_AVAILABLE = False

from opal.plugins.presentations.lib.applescriptbasecontroller import AppleScriptBaseController, \
    AppleScriptBaseDocument
from opal.plugins.presentations.lib.applicationdiscovery import find_macos_application, macos_application_version
from opal.core.common.platform import is_macosx
from opal.core.display.screens import ScreenList


log = logging.getLogger(__name__)

KEYNOTE_BUNDLE_IDS = {'com.apple.iWork.Keynote', 'com.apple.Keynote'}


def _open_keynote_document(document_path, application_path):
    """Import through Launch Services so Keynote receives access to the file."""
    subprocess.run(['/usr/bin/open', '-g', '-a', str(application_path), str(document_path)],
                   check=True, capture_output=True, text=True)


def find_keynote_application(application_folders=None):
    """Find both the classic Keynote app and the renamed Creator Studio app."""
    return find_macos_application(KEYNOTE_BUNDLE_IDS, application_folders)


KEYNOTE_APPLESCRIPT = """
on get_version()
    return (version of application "Keynote")
end get_version

on start_application()
    tell application "Keynote"
        launch
    end tell
end start_application

on close_presentation()
    try
        tell application "Keynote"
            -- close presentation
            close front document
            end tell
    end try
end close_presentation

on create_thumbs(documentStem, outputPath)
    set outputPathHfs to POSIX file outputPath
    with timeout of 900 seconds
    tell application "Keynote"
        if playing is true then tell the front document to stop
        repeat with attempt from 1 to 4500
            if (count of documents) > 0 then
                if name of front document is documentStem then exit repeat
            end if
            delay 0.2
        end repeat
        if (count of documents) is 0 then error "Keynote did not import the requested presentation"
        if name of front document is not documentStem then error "Keynote did not import the requested presentation"
        -- hide keynote
        tell application "System Events"
            set visible of application process "Keynote" to false
        end tell
        -- Export slides to png
        export front document as slide images to file outputPathHfs with properties ¬
            {image format:PNG, skipped slides:false}
        return my get_slide_metadata(documentStem)
    end tell
    end timeout
end create_thumbs

on get_slide_metadata(documentStem)
    with timeout of 900 seconds
    tell application "Keynote"
        repeat with attempt from 1 to 4500
            if (count of documents) > 0 then
                if name of front document is documentStem then exit repeat
            end if
            delay 0.2
        end repeat
        if (count of documents) is 0 then error "Keynote did not open the requested presentation"
        if name of front document is not documentStem then error "Keynote did not open the requested presentation"
        set slideTitles to {}
        set slideNotes to {}
        set exportedSlideNumber to 0
        tell the front document
            repeat with presentationSlide in slides
                tell presentationSlide
                    if skipped is false then
                        set exportedSlideNumber to exportedSlideNumber + 1
                        set end of slideNotes to presenter notes of it
                        if title showing is true then
                            set end of slideTitles to object text of default title item
                        else
                            set end of slideTitles to "slide " & exportedSlideNumber
                        end if
                    end if
                end tell
            end repeat
        end tell
        close front document
        return {slideTitles, slideNotes}
    end tell
    end timeout
end get_slide_metadata

on start_presentation(documentStem, new_top, new_left_pos, new_width, new_height, fullscreen, startingSlide)
    with timeout of 900 seconds
    tell application "Keynote"
        if playing is true then
            if name of front document is documentStem then
                set current slide of front document to slide startingSlide of front document
                return
            end if
            tell the front document to stop
        end if
        repeat with attempt from 1 to 4500
            if (count of documents) > 0 then
                if name of front document is documentStem then exit repeat
            end if
            delay 0.2
        end repeat
        if (count of documents) is 0 then error "Keynote did not import the requested presentation"
        if name of front document is not documentStem then error "Keynote did not import the requested presentation"
        start front document from slide startingSlide of front document
        activate
    end tell
    end timeout
end start_presentation

on stop_presentation()
    tell application "Keynote"
        --activate
        -- stop presenting
        if playing is true then tell the front document to stop
        -- close presentation
        close front document
        -- hide keynote
        tell application "System Events"
            set visible of application process "Keynote" to false
        end tell
    end tell
end stop_presentation

on is_loaded(documentStem)
    tell application "Keynote"
        if (count of documents) is 0 then return false
        return name of front document is documentStem
    end tell
end is_loaded

on is_active()
    tell application "Keynote"
        -- print(?) true/false playing state
        return playing
    end tell
end is_active


on next_slide()
    tell application "Keynote"
        --activate
        if playing is false then start front document from the first slide of front document
        show next
    end tell
end next_slide

on previous_slide()
    tell application "Keynote"
        if playing is false then start front document from the first slide of front document
        show previous
    end tell
end previous_slide

on goto_slide(slideNumber)
    tell application "Keynote"
        if playing is false then
            start front document from slide slideNumber of front document
        else
            set current slide of front document to slide slideNumber of front document
        end if
    end tell
end goto_slide

on get_current_slide()
    tell application "Keynote"
        repeat with attempt from 1 to 5
            try
                return slide number of current slide of front document
            on error
                delay 0.1
            end try
        end repeat
        return 0
    end tell
end get_current_slide

on blank()
    tell application "Keynote"
        tell application "System Events" to keystroke "b"
    end tell
end blank

on unblank()
    tell application "Keynote"
        tell application "System Events" to keystroke "b"
    end tell
end blank
"""


class _KeynoteStartWorker(QtCore.QThread):
    """Let large PowerPoint imports finish without blocking OpenLP's UI."""

    def __init__(self, script_source, file_path, stem, application_path, geometry, fullscreen, start_slide):
        super().__init__()
        self.script_source = script_source
        self.file_path = file_path
        self.stem = stem
        self.application_path = application_path
        self.geometry = geometry
        self.fullscreen = fullscreen
        self.start_slide = start_slide
        self.error = None

    def run(self):
        try:
            import objc
            with objc.autorelease_pool():
                script = applescript.AppleScript(self.script_source)
                if not script.call('is_loaded', self.stem):
                    _open_keynote_document(self.file_path, self.application_path)
                top, left, width, height = self.geometry
                script.call('start_presentation', self.stem,
                            top, left, width, height, self.fullscreen, self.start_slide)
        except Exception as error:
            self.error = error
            log.exception('Could not start the Keynote slideshow')


class KeynoteController(AppleScriptBaseController):
    """
    Class to control interactions with Keynote.
    As well as triggering the correct activities based on the users input.
    """
    log.info('KeynoteController loaded')
    base_class = False

    def __init__(self, plugin):
        """
        Initialise the class
        """
        log.debug('Initialising')
        super(KeynoteController, self).__init__(plugin, 'Keynote', KeynoteDocument)
        self.keynote_app = find_keynote_application() if is_macosx() else None
        if APPLESCRIPT_AVAILABLE:
            # Compiled script expected to be set by subclasses
            try:
                source = KEYNOTE_APPLESCRIPT
                if self.keynote_app:
                    app_path = str(self.keynote_app).replace('\\', '\\\\').replace('"', '\\"')
                    source = source.replace('application "Keynote"', f'application "{app_path}"')
                self.applescript = applescript.AppleScript(source)
            except applescript.ScriptError:
                log.exception('Compilation of Keynote applescript failed')
            self.supports = ['key']
            self.also_supports = ['ppt', 'pps', 'pptx', 'ppsx', 'pptm']
            self.supports_slide_images = True

    def check_available(self):
        """
        Program is able to run on this machine.
        """
        return bool(APPLESCRIPT_AVAILABLE and macos_application_version(self.keynote_app) >= (10, 1))


class KeynoteDocument(AppleScriptBaseDocument):
    """
    Class which holds information and controls a single presentation.
    """

    def __init__(self, controller, document_path):
        """
        Constructor, store information about the file and initialise.

        :param controller:
        :param pathlib.Path document_path: Path to the document to load
        :rtype: None
        """
        log.debug('Init Presentation KeynoteDocument')
        super().__init__(controller, document_path)
        self.starts_at_selected_slide = True
        self._opening = False
        self._cancelled = False
        self._start_worker = None

    def is_loaded(self):
        """Imported PPTX documents have no file property; Keynote keeps their basename."""
        if self._opening:
            return False
        try:
            self.presentation_loaded = bool(self.controller.applescript.call('is_loaded', self.file_path.stem))
        except Exception:
            log.exception('Could not check whether Keynote opened the presentation')
            self.presentation_loaded = False
        return self.presentation_loaded

    def start_presentation(self):
        """Open and start a native show at the selected slide without freezing OpenLP."""
        if self._opening:
            return
        self._slideshow_started = False
        size = ScreenList().current.display_geometry
        fullscreen = ScreenList().current.custom_geometry is None
        source = KEYNOTE_APPLESCRIPT
        if self.controller.keynote_app:
            app_path = str(self.controller.keynote_app).replace('\\', '\\\\').replace('"', '\\"')
            source = source.replace('application "Keynote"', f'application "{app_path}"')
        self._cancelled = False
        self._opening = True
        self._start_worker = _KeynoteStartWorker(
            source, str(self.file_path), self.file_path.stem, self.controller.keynote_app,
            (size.top(), size.left(), size.width(), size.height()), fullscreen,
            max(1, int(self.ui_slidenumber)))
        self._start_worker.finished.connect(self._finish_start_presentation)
        self._start_worker.start()

    def _finish_start_presentation(self):
        worker = self._start_worker
        self._opening = False
        self._start_worker = None
        if worker.error:
            self.presentation_loaded = False
            return
        if self._cancelled:
            try:
                if self.controller.applescript.call('is_loaded', self.file_path.stem):
                    self.controller.applescript.call('stop_presentation')
            except Exception:
                log.exception('Could not close a cancelled Keynote slideshow')
            return
        self._slideshow_started = True
        self.presentation_loaded = True
        if self.ui_slidenumber != worker.start_slide:
            self.goto_slide(self.ui_slidenumber)

    def is_active(self):
        if self._opening:
            return False
        return super().is_active()

    def close_presentation(self):
        self._cancelled = True
        super().close_presentation()
        self.presentation_loaded = False
        self.is_blanked = False

    def load_presentation(self):
        thumbnail_folder = self.get_thumbnail_folder()
        if not any(thumbnail_folder.iterdir()):
            try:
                _open_keynote_document(self.file_path, self.controller.keynote_app)
                titles, notes = self.controller.applescript.call(
                    'create_thumbs', self.file_path.stem, str(thumbnail_folder))
                self.save_titles_and_notes(titles, notes)
                self.presentation_loaded = True
            except Exception:
                log.exception('Could not export presentation slides from Keynote')
                self.presentation_loaded = False
        else:
            self.presentation_loaded = True
            if not (thumbnail_folder / 'titles.txt').is_file():
                try:
                    _open_keynote_document(self.file_path, self.controller.keynote_app)
                    titles, notes = self.controller.applescript.call('get_slide_metadata', self.file_path.stem)
                    self.save_titles_and_notes(titles, notes)
                except Exception:
                    log.exception('Could not recover Keynote slide titles and notes')
        ret = self.presentation_loaded
        if ret:
            # Keynote will name the thumbnails in the format: <sha256>.001.png, we need to convert to slide1.png
            old_images = list(self.get_thumbnail_folder().glob('*.png'))
            # if the convertion was already done, don't do it again
            if self.get_thumbnail_folder() / 'slide1.png' in old_images:
                self.slide_count = len(list(self.get_thumbnail_folder().glob('slide[0-9]*.png')))
                return True
            self.slide_count = len(old_images)
            for old_image in old_images:
                # get the image name in format 001.png
                number_name = old_image.name.split('.', 1)[1]
                # get the image name in format 1.png
                number_name = number_name.lstrip('0')
                new_name = 'slide' + number_name
                shutil.move(old_image, self.get_thumbnail_folder() / new_name)
        return ret

    def create_slide_images(self):
        """Use Keynote's exported slide images as OpenLP display images."""
        sources = []
        number = 1
        while True:
            source = self.get_thumbnail_path(number, True)
            if source is None:
                break
            sources.append(source)
            number += 1
        return self.save_slide_images_from_sources(sources)
