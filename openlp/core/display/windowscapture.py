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
Windows-only desktop capture backend.

This module is intentionally self-contained and safe to import on non-Windows
systems. Capture strategy:
- Preferred: dxcam (DXGI desktop duplication, GPU-accelerated path)
- Fallback: Pillow ImageGrab
"""
import logging
import platform

from PySide6 import QtCore, QtGui

log = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == 'Windows'
HAS_DXCAM = False
HAS_IMAGE_GRAB = False
WINDOWS_CAPTURE_IMPORT_ERROR = None

dxcam = None
ImageGrab = None

if IS_WINDOWS:
    try:
        import dxcam  # type: ignore[reportMissingImports]
        HAS_DXCAM = True
    except Exception as e:
        WINDOWS_CAPTURE_IMPORT_ERROR = str(e)
    try:
        from PIL import ImageGrab  # type: ignore[reportMissingImports]
        HAS_IMAGE_GRAB = True
    except Exception as e:
        WINDOWS_CAPTURE_IMPORT_ERROR = str(e)

HAS_WINDOWS_CAPTURE = IS_WINDOWS and (HAS_DXCAM or HAS_IMAGE_GRAB)


class WindowsCaptureBackend(object):
    """Windows desktop capture backend with DXGI-first strategy."""

    def __init__(self):
        self.camera = None

    @staticmethod
    def is_available():
        return HAS_WINDOWS_CAPTURE

    @staticmethod
    def _capture_rect(display_rect):
        left = int(display_rect.x())
        top = int(display_rect.y())
        right = left + int(display_rect.width())
        bottom = top + int(display_rect.height())
        return left, top, right, bottom

    @staticmethod
    def _imagegrab_to_qpixmap(image):
        if image is None:
            return None
        rgba = image.convert('RGBA')
        raw = rgba.tobytes('raw', 'RGBA')
        q_image = QtGui.QImage(raw, rgba.width, rgba.height, rgba.width * 4, QtGui.QImage.Format.Format_RGBA8888)
        return QtGui.QPixmap.fromImage(q_image.copy())

    @staticmethod
    def _dxcam_to_qpixmap(frame):
        """
        Convert dxcam ndarray frame (BGR, uint8) to QPixmap.
        """
        if frame is None:
            return None
        try:
            height, width, _channels = frame.shape
            stride = frame.strides[0]
            q_image = QtGui.QImage(frame.data, width, height, stride, QtGui.QImage.Format.Format_BGR888)
            return QtGui.QPixmap.fromImage(q_image.copy())
        except Exception:
            log.exception('Failed converting dxcam frame to QPixmap')
            return None

    def _capture_with_dxcam(self, display_rect):
        if not HAS_DXCAM or dxcam is None:
            return None
        try:
            if self.camera is None:
                self.camera = dxcam.create()
            region = self._capture_rect(display_rect)
            frame = self.camera.grab(region=region)
            return self._dxcam_to_qpixmap(frame)
        except Exception:
            log.exception('dxcam desktop capture failed')
            return None

    def _capture_with_imagegrab(self, display_rect):
        if not HAS_IMAGE_GRAB or ImageGrab is None:
            return None
        try:
            bbox = self._capture_rect(display_rect)
            image = ImageGrab.grab(bbox=bbox, all_screens=True)
            return self._imagegrab_to_qpixmap(image)
        except Exception:
            log.exception('Pillow ImageGrab desktop capture failed')
            return None

    def capture_display(self, display_rect):
        """
        Capture a region of the virtual desktop and return a QPixmap.

        :param QtCore.QRect display_rect: Virtual desktop rectangle to capture.
        :return: A QPixmap when capture succeeds, otherwise None.
        :rtype: QtGui.QPixmap | None
        """
        if not self.is_available():
            log.debug('Windows capture backend unavailable: %s', WINDOWS_CAPTURE_IMPORT_ERROR)
            return None
        if not isinstance(display_rect, QtCore.QRect):
            log.debug('Windows capture called with invalid display_rect type: %s', type(display_rect))
            return None
        image = self._capture_with_dxcam(display_rect)
        if image:
            return image
        return self._capture_with_imagegrab(display_rect)