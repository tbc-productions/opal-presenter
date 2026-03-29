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
macOS-only ScreenCaptureKit backend for desktop capture.

This module is intentionally self-contained and safe to import on non-macOS
systems. On non-macOS platforms it simply reports as unavailable.
"""
import logging
import platform
import threading

from PySide6 import QtCore, QtGui

log = logging.getLogger(__name__)

IS_MACOS = platform.system() == 'Darwin'
HAS_SCREEN_CAPTURE_KIT = False
SCREEN_CAPTURE_KIT_IMPORT_ERROR = None
HAS_QUARTZ_CAPTURE = False

Quartz = None
ScreenCaptureKit = None

if IS_MACOS:
    try:
        import Quartz  # type: ignore[reportMissingImports]
        HAS_QUARTZ_CAPTURE = True
    except Exception as e:
        SCREEN_CAPTURE_KIT_IMPORT_ERROR = str(e)
    try:
        import ScreenCaptureKit  # type: ignore[reportMissingImports]
        HAS_SCREEN_CAPTURE_KIT = True
    except Exception as e:
        SCREEN_CAPTURE_KIT_IMPORT_ERROR = str(e)


class ScreenCaptureKitBackend(object):
    """
    macOS ScreenCaptureKit backend.

    Captures single frames on macOS using:
    - ScreenCaptureKit SCScreenshotManager when available (macOS 14+)
    - Quartz CGWindowListCreateImage as compatibility fallback
    """

    def __init__(self, timeout_seconds=0.5):
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def is_available():
        """Return True when ScreenCaptureKit can be used on this host."""
        return IS_MACOS and (HAS_SCREEN_CAPTURE_KIT or HAS_QUARTZ_CAPTURE)

    @staticmethod
    def _cgimage_to_qpixmap(cg_image):
        """Convert a Quartz CGImage to QPixmap."""
        if not cg_image or not Quartz:
            return None
        try:
            width = int(Quartz.CGImageGetWidth(cg_image))
            height = int(Quartz.CGImageGetHeight(cg_image))
            bytes_per_row = int(Quartz.CGImageGetBytesPerRow(cg_image))
            provider = Quartz.CGImageGetDataProvider(cg_image)
            if not provider:
                return None
            data_ref = Quartz.CGDataProviderCopyData(provider)
            if not data_ref:
                return None
            raw = bytes(data_ref)
            image = QtGui.QImage(raw, width, height, bytes_per_row, QtGui.QImage.Format.Format_ARGB32)
            return QtGui.QPixmap.fromImage(image.copy())
        except Exception:
            log.exception('Failed converting CGImage to QPixmap')
            return None

    def _capture_with_screenshot_manager(self, display_rect):
        """Use ScreenCaptureKit's SCScreenshotManager if available."""
        if not HAS_SCREEN_CAPTURE_KIT or not ScreenCaptureKit or not Quartz:
            return None
        manager = getattr(ScreenCaptureKit, 'SCScreenshotManager', None)
        if not manager:
            return None
        capture_method = getattr(manager, 'captureImageIn_completionHandler_', None)
        if not capture_method:
            return None

        capture_rect = Quartz.CGRectMake(display_rect.x(), display_rect.y(),
                                         display_rect.width(), display_rect.height())
        result = {'image': None, 'error': None}
        done = threading.Event()

        def _completion_handler(image, error):
            result['image'] = image
            result['error'] = error
            done.set()

        try:
            capture_method(capture_rect, _completion_handler)
            if not done.wait(self.timeout_seconds):
                log.debug('ScreenCaptureKit capture timed out')
                return None
            if result['error']:
                log.debug('ScreenCaptureKit capture returned error: %s', result['error'])
                return None
            return self._cgimage_to_qpixmap(result['image'])
        except Exception:
            log.exception('ScreenCaptureKit capture failed')
            return None

    @staticmethod
    def _capture_with_quartz(display_rect):
        """Compatibility path for macOS versions where SCScreenshotManager is unavailable."""
        if not HAS_QUARTZ_CAPTURE or not Quartz:
            return None
        try:
            capture_rect = Quartz.CGRectMake(display_rect.x(), display_rect.y(),
                                             display_rect.width(), display_rect.height())
            cg_image = Quartz.CGWindowListCreateImage(
                capture_rect,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault
            )
            return ScreenCaptureKitBackend._cgimage_to_qpixmap(cg_image)
        except Exception:
            log.exception('Quartz desktop capture failed')
            return None

    def capture_display(self, display_rect):
        """
        Capture a region of the virtual desktop and return a QPixmap.

        :param QtCore.QRect display_rect: Virtual desktop rectangle to capture.
        :return: A QPixmap when capture succeeds, otherwise None.
        :rtype: QtGui.QPixmap | None
        """
        if not self.is_available():
            log.debug('ScreenCaptureKit backend requested but unavailable: %s', SCREEN_CAPTURE_KIT_IMPORT_ERROR)
            return None
        if not isinstance(display_rect, QtCore.QRect):
            log.debug('ScreenCaptureKit capture called with invalid display_rect type: %s', type(display_rect))
            return None
        screenshot = self._capture_with_screenshot_manager(display_rect)
        if screenshot:
            return screenshot
        return self._capture_with_quartz(display_rect)