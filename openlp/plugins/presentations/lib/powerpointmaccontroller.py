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
import ctypes
import logging
import posixpath
import subprocess
import tempfile
import time
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
try:
    import applescript
    APPLESCRIPT_AVAILABLE = True
except ImportError:
    APPLESCRIPT_AVAILABLE = False

from openlp.plugins.presentations.lib.applescriptbasecontroller import AppleScriptBaseController, \
    AppleScriptBaseDocument

from openlp.core.widgets import fluent as QtWidgets
from PySide6.QtPdf import QPdfDocument
from PySide6.QtCore import Qt, QEventLoop, QThread, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtMultimedia import QMediaCaptureSession, QVideoSink, QWindowCapture

from openlp.core.common.i18n import translate
from openlp.core.common.mac_permissions import (
    accessibility_target_name, has_post_event_access, request_post_event_access)
from openlp.core.common.registry import Registry
from openlp.core.display.screens import ScreenList
from openlp.core.ui import HideMode

log = logging.getLogger(__name__)
_post_event_access_requested = False


def _open_powerpoint_document(document_path):
    """Give PowerPoint the file through Launch Services before scripting it.

    AppleScript's ``open`` command makes sandboxed Office ask for access to
    each library copy. Launch Services delivers the document as a normal open
    event, including macOS's access grant for that file.
    """
    subprocess.run(['/usr/bin/open', '-g', '-b', 'com.microsoft.Powerpoint', str(document_path)],
                   check=True, capture_output=True, text=True)


def _find_powerpoint_slideshow_window(window_title):
    """Find the CGWindowID for one named PowerPoint slideshow window."""
    foundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    graphics = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    foundation.CFRelease.argtypes = [ctypes.c_void_p]
    foundation.CFArrayGetCount.argtypes = [ctypes.c_void_p]
    foundation.CFArrayGetCount.restype = ctypes.c_long
    foundation.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
    foundation.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
    foundation.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    foundation.CFDictionaryGetValue.restype = ctypes.c_void_p
    foundation.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
    foundation.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    foundation.CFStringGetCString.restype = ctypes.c_bool
    foundation.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    foundation.CFNumberGetValue.restype = ctypes.c_bool
    graphics.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    graphics.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p

    def field(window, name):
        key = foundation.CFStringCreateWithCString(None, name, 0x08000100)
        try:
            return foundation.CFDictionaryGetValue(window, key)
        finally:
            foundation.CFRelease(key)

    def string(window, name):
        value = field(window, name)
        buffer = ctypes.create_string_buffer(2048)
        if value and foundation.CFStringGetCString(value, buffer, len(buffer), 0x08000100):
            return buffer.value.decode('utf-8')
        return ''

    windows = graphics.CGWindowListCopyWindowInfo(1, 0)
    if not windows:
        return None
    try:
        for index in range(foundation.CFArrayGetCount(windows)):
            window = foundation.CFArrayGetValueAtIndex(windows, index)
            if string(window, b'kCGWindowOwnerName') != 'Microsoft PowerPoint':
                continue
            if string(window, b'kCGWindowName') != window_title:
                continue
            number = field(window, b'kCGWindowNumber')
            window_id = ctypes.c_int64()
            if number and foundation.CFNumberGetValue(number, 4, ctypes.byref(window_id)):
                return window_id.value
    finally:
        foundation.CFRelease(windows)
    return None


def _read_slide_advance_times(presentation_path):
    """Read PowerPoint transition delays in presentation order, in milliseconds.

    Native PowerPoint reads its advance mode only when starting a slide show.
    OpenLP can control the live clock without reopening the window by running
    the native show in manual mode and scheduling its slide jumps itself.
    """
    if presentation_path.suffix.lower() not in ('.pptx', '.ppsx', '.pptm'):
        return []
    presentation_ns = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
    relationship_ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    package_ns = '{http://schemas.openxmlformats.org/package/2006/relationships}'
    try:
        with ZipFile(presentation_path) as package:
            presentation = ElementTree.fromstring(package.read('ppt/presentation.xml'))
            relationships = ElementTree.fromstring(package.read('ppt/_rels/presentation.xml.rels'))
            targets = {relation.get('Id'): relation.get('Target') for relation in
                       relationships.findall(f'{package_ns}Relationship') if relation.get('TargetMode') != 'External'}
            delays = []
            slide_ids = presentation.find(f'{presentation_ns}sldIdLst')
            if slide_ids is None:
                return []
            for slide_id in slide_ids.findall(f'{presentation_ns}sldId'):
                target = targets.get(slide_id.get(f'{relationship_ns}id'))
                if not target:
                    return []
                slide_path = posixpath.normpath(posixpath.join('ppt', target)).lstrip('/')
                slide = ElementTree.fromstring(package.read(slide_path))
                if slide.get('show') == '0':
                    continue
                transition = slide.find(f'{presentation_ns}transition')
                duration = transition.get('advTm') if transition is not None else None
                delays.append(int(duration) if duration is not None else None)
            return delays
    except (OSError, BadZipFile, KeyError, ValueError, ElementTree.ParseError):
        log.exception('Could not read PowerPoint slide timings from %s', presentation_path)
        return []


POWERPOINT_MAC_APPLESCRIPT = """
on check_available()
    set appID to "com.microsoft.PowerPoint"
    set doesExist to false
    try
        tell application "Finder" to get application file id appID
        set doesExist to true
    end try
    return doesExist
end check_available

on get_version()
    return (version of application "Microsoft PowerPoint")
end get_version

on find_presentation_index(documentName)
    tell application "Microsoft PowerPoint"
        repeat with presentationIndex from 1 to count of presentations
            if name of presentation presentationIndex is documentName then return presentationIndex
        end repeat
    end tell
    error "PowerPoint presentation is not open: " & documentName
end find_presentation_index

on start_application()
    tell application "Microsoft PowerPoint"
        launch
        -- Wait for powerpoint to start
        tell application "System Events"
            repeat while true
                set PowerPointUp to (count of (every process whose name is "Microsoft PowerPoint")) > 0
                if PowerPointUp then
                    exit repeat
                else
                    delay 0.2
                end if
            end repeat
        end tell
    end tell
end start_application

-- helper function to write text to files
on write_file(fileName, theData)
    set fileDescriptor to open for access the fileName with write permission
    write theData to fileDescriptor as «class utf8»
    close access fileDescriptor
end write_file

-- helper function to create empty file
on create_empty_file(f)
    write_file(f, "")
    return (POSIX path of f) as POSIX file
end create_empty_file

on create_thumbs(documentName, outputPath)
    tell application "Microsoft PowerPoint"
        -- wait for document to load
        set exportIndex to 0
        repeat with attempt from 1 to 1500
            try
                set exportIndex to my find_presentation_index(documentName)
                exit repeat
            end try
            delay 0.2
        end repeat
        if exportIndex is 0 then error "PowerPoint did not open the requested presentation"
        set exportPresentation to presentation exportIndex
        -- Export slides to jpg
        --save active presentation in outputPath as save as PNG
        -- Export slides to pdf
        save exportPresentation in my create_empty_file(outputPath & "/tmp.pdf") as save as PDF
        -- Get the Presentation Notes and slide title
        set the slideTitles to ""
        set titleTypes to {placeholder type title placeholder, placeholder type center title placeholder, ¬
            placeholder type vertical title placeholder}
        repeat with tSlide in (get slides of exportPresentation)
            -- Only handle non-hidden slides
            if hidden of slide show transition of tSlide is false then
                --text = slide.Shapes.Title.TextFrame.TextRange.Text
                -- Get the title of the current slide
                repeat with currentShape in (get shapes of tSlide)
                    tell currentShape to if has text frame then tell its text frame to if has text then
                        set aType to placeholder type of currentShape
                        if aType is not missing value and aType is in titleTypes then
                            set slideTitles to slideTitles & (content of its text range) & return
                            exit repeat
                        end if
                    end if
                end repeat
                set the noteText to ""
                repeat with t_shape in (get shapes of notes page of tSlide)
                    tell t_shape to if has text frame then tell its text frame to if has text then
                        -- get the note of this slide
                        set the noteText to (content of its text range)
                        exit repeat
                    end if
                end repeat
                -- Save note to file
                set noteFilename to outputPath & "/slideNotes" & (slide index of tSlide as string) & ".txt"
                my write_file(noteFilename, noteText)
            end if
        end repeat
        -- Save the titles to file
        set titlesFilename to outputPath & "/titles.txt"
        my write_file(titlesFilename, slideTitles)
        close exportPresentation
    end tell
end create_thumbs

on close_presentation()
    tell application "Microsoft PowerPoint"
        -- close presentation
        close active presentation
        -- Hide powerpoint
        tell application "System Events"
            set visible of application process "Microsoft PowerPoint" to false
        end tell
    end tell
end close_presentation

on start_presentation(documentName, new_top, new_left_pos, ¬
        new_width, new_height, startingSlide, useTimings, fullScreen)
    tell application "Microsoft PowerPoint"
        set presentationIndex to 0
        repeat with attempt from 1 to 300
            try
                set presentationIndex to my find_presentation_index(documentName)
                exit repeat
            end try
            delay 0.2
        end repeat
        if presentationIndex is 0 then error "PowerPoint did not open the requested presentation"
        set targetPresentation to presentation presentationIndex
        -- disable presenter console
        set showpresenterview of slide show settings of targetPresentation to 0
        if fullScreen then
            set show type of slide show settings of targetPresentation to slide show type speaker
        else
            set show type of slide show settings of targetPresentation to slide show type window
        end if
        -- Keep every slide in the running show's range so number-and-Return
        -- navigation can also reach slides before the initially selected one.
        set range type of slide show settings of targetPresentation to slide show range show all
        if useTimings then
            set advance mode of slide show settings of targetPresentation to slide show advance use slide timings
        else
            set advance mode of slide show settings of targetPresentation to slide show advance manual advance
        end if
        -- start presentation
        run slide show slide show settings of targetPresentation
        set showWindow to slide show window of targetPresentation
        activate
        return current show position of slide show view of showWindow
    end tell
end start_presentation

on position_slide_show(documentName, new_top, new_left_pos, new_width, new_height)
    tell application "Microsoft PowerPoint"
        set presentationIndex to my find_presentation_index(documentName)
        set showWindow to slide show window of presentation presentationIndex
        set top of showWindow to new_top
        set left position of showWindow to new_left_pos
        set height of showWindow to new_height
        set width of showWindow to new_width
    end tell
end position_slide_show

on get_slide_show_window_title(documentName)
    tell application "Microsoft PowerPoint"
        set presentationIndex to my find_presentation_index(documentName)
        return name of slide show window of presentation presentationIndex
    end tell
end get_slide_show_window_title

on is_slide_show_window_active(documentName)
    tell application "Microsoft PowerPoint"
        set presentationIndex to my find_presentation_index(documentName)
        return active of slide show window of presentation presentationIndex
    end tell
end is_slide_show_window_active

on set_slide_timings(documentName, useTimings)
    tell application "Microsoft PowerPoint"
        set presentationIndex to my find_presentation_index(documentName)
        set targetPresentation to presentation presentationIndex
        if useTimings then
            set advance mode of slide show settings of targetPresentation to slide show advance use slide timings
        else
            set advance mode of slide show settings of targetPresentation to slide show advance manual advance
        end if
    end tell
end set_slide_timings

on stop_presentation()
    tell application "Microsoft PowerPoint"
        -- stop presenting - self.presentation.SlideShowWindow.View.Exit()
        exit slide show slide show view of slide show window 1
        -- close presentation
        close active presentation
        -- Hide powerpoint
        tell application "System Events"
            set visible of application process "Microsoft PowerPoint" to false
        end tell
    end tell
end stop_presentation

on hide_application()
    tell application "System Events"
        set visible of application process "Microsoft PowerPoint" to false
    end tell
end hide_application

on show_application()
    tell application "System Events"
        set visible of application process "Microsoft PowerPoint" to true
    end tell
    tell application "Microsoft PowerPoint" to activate
end show_application

on exit_slide_show(documentName)
    tell application "Microsoft PowerPoint"
        set presentationIndex to my find_presentation_index(documentName)
        exit slide show slide show view of slide show window of presentation presentationIndex
    end tell
end exit_slide_show

on is_loaded(documentName)
    tell application "Microsoft PowerPoint"
        try
            my find_presentation_index(documentName)
            return true
        on error
            return false
        end try
    end tell
end is_loaded

on is_active(documentName)
    tell application "Microsoft PowerPoint"
        try
            set presentationIndex to my find_presentation_index(documentName)
            set showState to slide state of slide show view of slide show window of presentation presentationIndex
            return (showState is slide show state running) or ¬
                (showState is slide show state paused) or ¬
                (showState is slide show state black screen)
        on error
            return false
        end try
    end tell
end is_active

on next_slide()
    tell application "Microsoft PowerPoint"
        --activate
        -- self.presentation.SlideShowWindow.View.Next()
        go to next slide slide show view of slide show window 1
        -- Print(?) slide number
        -- slide number of slide of slideshow view of slide show window of active presentation
    end tell
end next_slide

on previous_slide()
    tell application "Microsoft PowerPoint"
        --activate
        go to previous slide slide show view of slide show window 1
        -- Print(?) slide number
        -- self.presentation.SlideShowWindow.View.Slide.SlideNumber
        -- slide number of slide of view of slide show window of active presentation
    end tell
end previous_slide

on get_current_slide(documentName)
    tell application "Microsoft PowerPoint"
        set presentationIndex to my find_presentation_index(documentName)
        return current show position of slide show view of slide show window of presentation presentationIndex
    end tell
end get_current_slide

on blank()
    tell application "Microsoft PowerPoint"
        --activate
        -- self.presentation.SlideShowWindow.View.State = 3
        --set state of slide of view of slide show window of active presentation to 3
        set slide state of slide show view of slide show window 1 to slide show state black screen
    end tell
end blank

on unblank()
    tell application "Microsoft PowerPoint"
        --activate
        -- self.presentation.SlideShowWindow.View.State = 1
        set slide state of slide show view of slide show window 1 to slide show state running
    end tell
end unblank
"""


def _send_slide_number_to_powerpoint(slide_no):
    """Send PowerPoint's number-and-Return shortcut to its process."""
    global _post_event_access_requested
    try:
        from AppKit import NSRunningApplication

        applications = NSRunningApplication.runningApplicationsWithBundleIdentifier_('com.microsoft.Powerpoint')
        if len(applications) != 1:
            return False
        process_id = applications[0].processIdentifier()
        foundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        graphics = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        if not has_post_event_access():
            if not _post_event_access_requested:
                _post_event_access_requested = True
                request_post_event_access()
            if not has_post_event_access():
                log.warning('PowerPoint slide selection needs macOS Accessibility permission for %s',
                            accessibility_target_name())
                return False
        foundation.CFRelease.argtypes = [ctypes.c_void_p]
        graphics.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
        graphics.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
        graphics.CGEventKeyboardSetUnicodeString.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                                             ctypes.POINTER(ctypes.c_uint16)]
        graphics.CGEventPostToPid.argtypes = [ctypes.c_int, ctypes.c_void_p]
        digit_keycodes = {'0': 29, '1': 18, '2': 19, '3': 20, '4': 21,
                          '5': 23, '6': 22, '7': 26, '8': 28, '9': 25}
        for character in str(slide_no) + '\r':
            keycode = 36 if character == '\r' else digit_keycodes[character]
            unicode_character = (ctypes.c_uint16 * 1)(ord(character))
            for pressed in (True, False):
                event = graphics.CGEventCreateKeyboardEvent(None, keycode, pressed)
                if not event:
                    return False
                try:
                    graphics.CGEventKeyboardSetUnicodeString(event, 1, unicode_character)
                    graphics.CGEventPostToPid(process_id, event)
                finally:
                    foundation.CFRelease(event)
        return True
    except Exception:
        log.exception('Could not send a slide number to the PowerPoint slide-show window')
        return False


class _PowerPointThumbnailExport(QThread):
    """Export on a worker thread so PowerPoint cannot stall the OpenLP event loop."""

    def __init__(self, source_path, source_name, thumbnail_folder):
        super().__init__()
        self.source_path = source_path
        self.source_name = source_name
        self.thumbnail_folder = thumbnail_folder
        self.error = None

    def run(self):
        try:
            import objc
            # Each worker owns its script; NSAppleScript instances must not be shared across threads.
            with objc.autorelease_pool():
                _open_powerpoint_document(self.source_path)
                script = applescript.AppleScript(POWERPOINT_MAC_APPLESCRIPT)
                script.call('create_thumbs', self.source_name, self.thumbnail_folder)
        except Exception as error:
            self.error = error
            log.exception('Could not export PowerPoint thumbnails')


class _PowerPointWindowSnapshot(QThread):
    """Capture only the native slideshow window without blocking OpenLP's UI."""

    def __init__(self, window_title):
        super().__init__()
        self.window_title = window_title
        self.image = None
        self.error = None

    def run(self):
        try:
            window_id = _find_powerpoint_slideshow_window(self.window_title)
            if window_id is None:
                return
            with tempfile.TemporaryDirectory(prefix='openlp-presentation-capture-') as folder:
                output = f'{folder}/window.png'
                result = subprocess.run(['/usr/sbin/screencapture', '-x', '-l', str(window_id), output],
                                        capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    image = QImage(output)
                    if not image.isNull():
                        self.image = image.copy()
                else:
                    self.error = result.stderr
        except (OSError, subprocess.TimeoutExpired) as error:
            self.error = str(error)


class PowerPointMacController(AppleScriptBaseController):
    """
    Class to control interactions with a Powerpoint for Mac.
    As well as triggering the correct activities based on the users input.
    """
    log.info('PowerPointMacController loaded')
    base_class = False

    def __init__(self, plugin):
        """
        Initialise the class
        """
        log.debug('Initialising')
        super(PowerPointMacController, self).__init__(plugin, 'PowerPointMac', PowerPointMacDocument)
        self.display_name = translate('PresentationPlugin.Controller', 'PowerPoint (macOS)')
        if APPLESCRIPT_AVAILABLE:
            # Compiled script expected to be set by subclasses
            try:
                self.applescript = applescript.AppleScript(POWERPOINT_MAC_APPLESCRIPT)
            except applescript.ScriptError:
                log.exception('Compilation of Powerpoint applescript failed')
            self.supports = ['ppt', 'pps', 'pptx', 'ppsx', 'pptm']
            self.also_supports = ['odp']
            self.supports_slide_images = True

    def check_available(self):
        """
        Program is able to run on this machine.
        """
        ret = super().check_available()
        if ret:
            # Powerpoint is available! now check if the version is 15 (Powerpoint 2016) or above
            try:
                version = self.applescript.call('get_version')
            except Exception:
                log.exception('script execution failed')
                return False
            try:
                major_version = int(version.split('.')[0])
            except ValueError:
                return False
            if major_version >= 15:
                return True
        return False


class PowerPointMacDocument(AppleScriptBaseDocument):
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
        log.debug('Init Presentation Applescript')
        super().__init__(controller, document_path)
        self.presentation_loaded = False
        self.is_blanked = False
        self.starts_at_selected_slide = True
        self._starting_slide = 1
        self._window_capture = None
        self._capture_session = None
        self._video_sink = None
        self._captured_image = None
        self._qt_capture_has_frame = False
        self._capture_resume_at = 0.0
        self._capture_generation = 0
        self._snapshot_worker = None
        self._retired_snapshot_workers = set()
        self._slideshow_window_title = None
        self._hidden_for_overlay = False
        self._slide_advance_times = []
        self._use_openlp_timing = False
        self._timing_slide = None
        self._automatic_slide_timer = QTimer()
        self._automatic_slide_timer.setSingleShot(True)
        self._automatic_slide_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._automatic_slide_timer.timeout.connect(self._advance_automatically)

    def _schedule_automatic_slide(self, slide_number):
        self._automatic_slide_timer.stop()
        if not (self._slideshow_started and self._use_openlp_timing and
                getattr(self, 'use_slide_timings', False)):
            return
        if 1 <= slide_number < len(self._slide_advance_times):
            duration = self._slide_advance_times[slide_number - 1]
            if duration is not None:
                self._automatic_slide_timer.start(max(50, duration))

    def _advance_automatically(self):
        """Advance the native show without asking PowerPoint to own its timer."""
        if not (self._slideshow_started and self._use_openlp_timing and
                getattr(self, 'use_slide_timings', False)):
            return
        current = self.get_slide_number()
        if 1 <= current < len(self._slide_advance_times):
            if self.goto_slide(current + 1):
                self.poll_slidenumber(True, None)

    def _stop_window_capture(self):
        worker = self._snapshot_worker
        if worker is not None:
            worker.finished.disconnect(self._finish_window_snapshot)
            self._snapshot_worker = None
            if worker.isRunning():
                # The process has its own timeout. Keep the QThread alive until it
                # finishes instead of blocking the UI or deleting a running thread.
                self._retired_snapshot_workers.add(worker)
                worker.finished.connect(lambda worker=worker: self._dispose_snapshot_worker(worker))
            else:
                worker.deleteLater()
        if self._window_capture:
            self._window_capture.stop()
        self._window_capture = None
        self._capture_session = None
        self._video_sink = None
        self._captured_image = None
        self._qt_capture_has_frame = False
        self._capture_resume_at = 0.0
        self._capture_generation += 1
        self._slideshow_window_title = None

    def _dispose_snapshot_worker(self, worker):
        self._retired_snapshot_workers.discard(worker)
        worker.deleteLater()

    def _on_video_frame(self, frame):
        if time.monotonic() >= self._capture_resume_at and frame.isValid():
            image = frame.toImage()
            if not image.isNull():
                self._captured_image = image
                self._qt_capture_has_frame = True

    def _finish_window_snapshot(self):
        worker = self._snapshot_worker
        if worker is None:
            return
        if (worker.image is not None and worker.capture_generation == self._capture_generation and
                time.monotonic() >= self._capture_resume_at):
            self._captured_image = worker.image
        elif worker.error:
            log.debug('Could not capture the PowerPoint slideshow window: %s', worker.error)
        self._snapshot_worker = None
        worker.deleteLater()

    def _start_window_snapshot(self):
        if self._qt_capture_has_frame or self._snapshot_worker is not None or not self._slideshow_window_title:
            return
        worker = _PowerPointWindowSnapshot(self._slideshow_window_title)
        worker.capture_generation = self._capture_generation
        self._snapshot_worker = worker
        worker.finished.connect(self._finish_window_snapshot)
        worker.start()

    def _start_window_capture(self):
        """Capture PowerPoint's real slide show window for OpenLP's Live pane."""
        if self._window_capture:
            return
        windows = QWindowCapture.capturableWindows()
        title = self.file_path.stem.lower()
        slide_show_windows = [window for window in windows if 'powerpoint slide show' in window.description().lower()]
        matching_windows = [window for window in slide_show_windows if title in window.description().lower()]
        if matching_windows:
            window = matching_windows[0]
        elif len(slide_show_windows) == 1:
            window = slide_show_windows[0]
        else:
            return
        self._window_capture = QWindowCapture()
        self._capture_session = QMediaCaptureSession()
        self._video_sink = QVideoSink()
        self._capture_session.setWindowCapture(self._window_capture)
        self._capture_session.setVideoSink(self._video_sink)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame)
        self._window_capture.setWindow(window)
        self._window_capture.start()

    def stop_presentation(self):
        self._automatic_slide_timer.stop()
        self._stop_window_capture()
        self._hidden_for_overlay = False
        super().stop_presentation()

    def close_presentation(self):
        self._automatic_slide_timer.stop()
        self._stop_window_capture()
        self._hidden_for_overlay = False
        super().close_presentation()

    def hide_for_overlay(self):
        """Reveal OpenLP's Logo or Theme display without ending the slide show."""
        if self._hidden_for_overlay:
            return
        try:
            self._stop_window_capture()
            self.controller.applescript.call('hide_application')
            self._hidden_for_overlay = True
        except Exception:
            log.exception('Could not hide PowerPoint behind the OpenLP display')

    def show_after_overlay(self):
        """Restore the same PowerPoint slide show after Logo or Theme."""
        if not self._hidden_for_overlay:
            return
        try:
            self.controller.applescript.call('show_application')
            self._hidden_for_overlay = False
            self._slideshow_window_title = self.controller.applescript.call(
                'get_slide_show_window_title', self.file_path.name)
        except Exception:
            log.exception('Could not restore PowerPoint after the OpenLP display')

    def is_loaded(self):
        try:
            return bool(self.controller.applescript.call('is_loaded', self.file_path.name))
        except Exception:
            log.exception('Could not check whether PowerPoint opened the presentation')
            return False

    def is_active(self):
        try:
            return bool(self.controller.applescript.call('is_active', self.file_path.name))
        except Exception:
            log.exception('Could not check whether the PowerPoint slide show is active')
            return False

    def poll_slidenumber(self, is_live, hide_mode):
        """Treat PowerPoint's Escape/end-show as Show Desktop in OpenLP."""
        if is_live and self._slideshow_started and not hide_mode and not self.is_active():
            self._slideshow_started = False
            try:
                self.controller.applescript.call('hide_application')
            except Exception:
                log.exception('Could not hide PowerPoint after its slide show ended')
            live_controller = Registry().get('live_controller')
            if live_controller and live_controller.service_item and \
                    live_controller.service_item.processor == 'PowerPointMac' and \
                    Path(live_controller.service_item.get_frame_path()) == self.file_path:
                live_controller.set_hide_mode(HideMode.Screen)
            return
        super().poll_slidenumber(is_live, hide_mode)

    def start_presentation(self):
        """Start a full-range show, select the requested slide, then move it to output."""
        self._automatic_slide_timer.stop()
        self._timing_slide = None
        self._stop_window_capture()
        self._slideshow_started = False
        start_slide = max(1, int(self.ui_slidenumber))
        use_timings = getattr(self, 'use_slide_timings', False)
        self._slide_advance_times = _read_slide_advance_times(self.file_path)
        self._use_openlp_timing = bool(len(self._slide_advance_times) == self.slide_count and
                                       any(delay is not None for delay in self._slide_advance_times))
        # Keep the native show manual. Only OpenLP's parsed timer can be toggled
        # while a slideshow is already running.
        self.use_slide_timings = bool(use_timings and self._use_openlp_timing)
        native_use_timings = False
        screen = ScreenList().current
        size = screen.display_geometry
        full_screen = screen.custom_geometry is None
        try:
            _open_powerpoint_document(self.file_path)
            actual = self.controller.applescript.call('start_presentation',
                                                      self.file_path.name, size.top(), size.left(),
                                                      size.width(), size.height(), start_slide, native_use_timings,
                                                      full_screen)
            self._slideshow_started = int(actual) >= 1
            self._starting_slide = 1
            if self._slideshow_started and start_slide != int(actual):
                if not self.goto_slide(start_slide):
                    log.warning('PowerPoint started but could not select slide %s', start_slide)
            if self._slideshow_started:
                self._slideshow_window_title = self.controller.applescript.call(
                    'get_slide_show_window_title', self.file_path.name)
                if not full_screen:
                    self.controller.applescript.call('position_slide_show', self.file_path.name,
                                                     size.top(), size.left(), size.width(), size.height())
                self._timing_slide = self.get_slide_number()
                self._schedule_automatic_slide(self._timing_slide)
            self.presentation_loaded = self._slideshow_started
            if not self._slideshow_started:
                log.warning('PowerPoint could not show the selected slide %s', start_slide)
        except Exception:
            log.exception('Could not start the PowerPoint slide show')

    def set_slide_timings(self, enabled):
        """Start or stop OpenLP's clock without interrupting the native slideshow."""
        enabled = bool(enabled)
        if getattr(self, 'use_slide_timings', None) == enabled:
            return True
        if self._use_openlp_timing:
            self.use_slide_timings = enabled
            self._schedule_automatic_slide(self.get_slide_number())
            return True
        if self.is_active():
            # PowerPoint snapshots this setting when the show starts. The saved
            # preference will apply next time; the current native show stays up.
            return False
        self.use_slide_timings = enabled
        if not self.is_loaded():
            return True
        try:
            self.controller.applescript.call('set_slide_timings', self.file_path.name, enabled)
        except Exception:
            log.exception('Could not apply PowerPoint slide timings')
            return False
        return True

    def get_slide_number(self):
        try:
            number = int(self.controller.applescript.call('get_current_slide', self.file_path.name))
            if number > 0 and number != self._timing_slide:
                self._timing_slide = number
                self._schedule_automatic_slide(number)
            return number
        except Exception:
            log.exception('Could not read the PowerPoint slide number')
            return 0

    def goto_slide(self, slide_no):
        """Jump within the running PowerPoint show without restarting its window."""
        slide_no = int(slide_no)
        if slide_no < 1:
            return False
        current_slide = self.get_slide_number()
        if current_slide == slide_no:
            self._schedule_automatic_slide(slide_no)
            return True
        self._automatic_slide_timer.stop()
        # Keep the previous live capture visible while the native show changes.
        # Discard frames captured before the jump settles.
        self._capture_generation += 1
        self._capture_resume_at = float('inf')
        self._captured_image = None
        self._qt_capture_has_frame = False
        try:
            show_active = False
            try:
                show_active = self.controller.applescript.call('is_slide_show_window_active', self.file_path.name)
                moved = bool(show_active) and _send_slide_number_to_powerpoint(slide_no)
            except Exception:
                log.exception('Could not target the PowerPoint slide-show window')
                moved = False
            if not moved:
                log.warning('PowerPoint could not select slide %s directly; leaving the show on slide %s',
                            slide_no, current_slide)
                self.ui_slidenumber = current_slide
                self.slide_number = 0
                main_window = Registry().get('main_window')
                if main_window:
                    if not show_active:
                        message = translate('PresentationPlugin.PowerPointMac',
                                            'Could not select a PowerPoint slide. Activate its slideshow window.')
                    elif not has_post_event_access():
                        message = translate(
                            'PresentationPlugin.PowerPointMac',
                            'Could not select a PowerPoint slide. '
                            'Allow {name} in macOS Accessibility settings.').format(name=accessibility_target_name())
                    else:
                        message = translate('PresentationPlugin.PowerPointMac',
                                            'Could not send a slide number to the PowerPoint slideshow window.')
                    main_window.show_status_message(message, 10000)
                self._schedule_automatic_slide(current_slide)
                return False
            self.ui_slidenumber = slide_no
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                if self.get_slide_number() == slide_no:
                    self._schedule_automatic_slide(slide_no)
                    return True
                time.sleep(0.04)
            log.warning('PowerPoint did not navigate to slide %s', slide_no)
            self.ui_slidenumber = current_slide
            self.slide_number = 0
            self._schedule_automatic_slide(current_slide)
            return False
        finally:
            self._capture_resume_at = time.monotonic() + 0.4

    def attempt_screenshot(self, index):
        """Capture PowerPoint's slide show window for OpenLP's Live preview."""
        if time.monotonic() < self._capture_resume_at:
            return False, None
        try:
            self._start_window_capture()
            self._start_window_snapshot()
            if self._captured_image is not None:
                return True, QPixmap.fromImage(self._captured_image)
        except Exception:
            log.debug('Could not capture the PowerPoint slide show window', exc_info=True)
        return False, None

    def _export_thumbnails(self):
        """Keep the GUI event loop running while PowerPoint exports a large deck."""
        source_path = str(self.file_path)
        source_name = self.file_path.name
        thumbnail_folder = str(self.get_thumbnail_folder())
        app = QtWidgets.QApplication.instance()
        if not app or QThread.currentThread() != app.thread():
            _open_powerpoint_document(source_path)
            self.controller.applescript.call('create_thumbs', source_name, thumbnail_folder)
            return True
        worker = _PowerPointThumbnailExport(source_path, source_name, thumbnail_folder)
        dialog = QtWidgets.QProgressDialog(
            translate('PresentationPlugin.PowerPointMac', 'Preparing slide previews…'), '', 0, 0)
        dialog.setCancelButton(None)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        loop = QEventLoop()
        worker.finished.connect(dialog.accept, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(loop.quit, Qt.ConnectionType.QueuedConnection)
        # Show before starting work so native widget setup cannot consume a
        # fast worker's completion before the progress event loop is running.
        dialog.show()
        worker.start()
        loop.exec()
        dialog.close()
        worker.wait()
        if worker.error:
            return False
        return True

    def load_presentation(self):
        thumbnail_folder = self.get_thumbnail_folder()
        pdf_file = thumbnail_folder / 'tmp.pdf'
        if not pdf_file.is_file() and not self.get_thumbnail_path(1, True):
            try:
                ret = self._export_thumbnails()
            except Exception:
                log.exception('Could not export PowerPoint thumbnails')
                ret = False
            self.presentation_loaded = ret
        else:
            ret = super().load_presentation()
        if ret:
            # we make powerpoint export to PDF and then convert the pdf to thumbnails
            # if the pdf file does not exists anymore it is assume the convertion has been done
            if not pdf_file.exists():
                self.slide_count = len(list(self.get_thumbnail_folder().glob('slide[0-9]*.png')))
                return self.slide_count > 0
            log.debug('converting pdf to png thumbnails using QPdf')
            pdf_doc = QPdfDocument(Registry().get('application'))
            pdf_doc.load(str(pdf_file))
            # wait for loading to complete
            while pdf_doc.status() == QPdfDocument.Status.Loading:
                QtWidgets.QApplication.processEvents()
            if pdf_doc.status() != QPdfDocument.Status.Ready:
                log.error('Could not read PowerPoint PDF export: %s', pdf_file)
                return False
            self.slide_count = pdf_doc.pageCount()
            if self.slide_count < 1:
                return False
            if all(self.get_thumbnail_path(number, True) for number in range(1, self.slide_count + 1)):
                return True
            # Generate images from PDF
            log.debug('loading presentation using QPdfDocument')
            painter = QPainter()
            progress = QtWidgets.QProgressDialog(
                translate('PresentationPlugin.PowerPointMac', 'Rendering slide previews…'),
                '', 0, self.slide_count)
            progress.setCancelButton(None)
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setMinimumDuration(250)
            try:
                for i in range(self.slide_count):
                    png_filename = self.get_thumbnail_folder() / f'slide{i + 1}.png'
                    if not png_filename.is_file():
                        page_size = pdf_doc.pagePointSize(i).toSize()
                        scaled_page_size = page_size.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
                        image = pdf_doc.render(i, scaled_page_size)
                        # The PDF renderer leaves transparent regions; thumbnails need a white background.
                        image_redraw = QImage(image.size(), QImage.Format_ARGB32)
                        image_redraw.fill(QColor(Qt.white).rgb())
                        painter.begin(image_redraw)
                        painter.drawImage(0, 0, image)
                        saved = image_redraw.save(str(png_filename), 'png')
                        painter.end()
                        if not saved:
                            return False
                    progress.setValue(i + 1)
            finally:
                progress.close()
            # Retain the PDF for full-size rendering if OpenLP image mode is selected.
        return ret

    def create_slide_images(self):
        """Render PowerPoint's PDF export at the configured display size."""
        pdf_file = self.get_thumbnail_folder() / 'tmp.pdf'
        if not pdf_file.is_file():
            try:
                if not self._export_thumbnails():
                    return False
            except Exception:
                log.exception('Could not export PowerPoint slides to PDF')
                return False
        if not pdf_file.is_file():
            return False
        pdf_doc = QPdfDocument(Registry().get('application'))
        pdf_doc.load(str(pdf_file))
        while pdf_doc.status() == QPdfDocument.Status.Loading:
            QtWidgets.QApplication.processEvents()
        if pdf_doc.status() != QPdfDocument.Status.Ready or pdf_doc.pageCount() < 1:
            return False
        self.invalidate_slide_images()
        folder = self.get_temp_folder()
        folder.mkdir(parents=True, exist_ok=True)
        size = ScreenList().current.display_geometry.size()
        painter = QPainter()
        for index in range(pdf_doc.pageCount()):
            page_size = pdf_doc.pagePointSize(index).toSize()
            render_size = page_size.scaled(size, Qt.AspectRatioMode.KeepAspectRatio)
            image = pdf_doc.render(index, render_size)
            if image.isNull():
                return False
            white_image = QImage(image.size(), QImage.Format_ARGB32)
            white_image.fill(QColor(Qt.white).rgb())
            painter.begin(white_image)
            painter.drawImage(0, 0, image)
            painter.end()
            if not white_image.save(str(folder / f'mainslide{index + 1:03d}.png'), 'png'):
                return False
        self.save_slide_image_manifest(pdf_doc.pageCount())
        return True
