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
"""Tests for media_info thumbnail utilities."""

from pathlib import Path
from unittest.mock import patch

from PySide6 import QtCore, QtGui

from opal.core.ui.media.mediainfo import media_info


def test_scaled_thumb_is_fixed_size(qapp):
    """Scaled thumbnails should always fit the fixed 88x50 canvas."""
    wide = QtGui.QPixmap(1920, 1080)
    wide.fill(QtCore.Qt.GlobalColor.red)
    tall = QtGui.QPixmap(1080, 1920)
    tall.fill(QtCore.Qt.GlobalColor.blue)

    wide_thumb = media_info._scaled_thumb(wide)
    tall_thumb = media_info._scaled_thumb(tall)

    assert wide_thumb.width() == 88
    assert wide_thumb.height() == 50
    assert tall_thumb.width() == 88
    assert tall_thumb.height() == 50


def test_save_thumb_writes_fixed_size_png(qapp, tmp_path):
    """Saved thumbnails should be written as PNG at fixed icon dimensions."""
    pixmap = QtGui.QPixmap(640, 360)
    pixmap.fill(QtCore.Qt.GlobalColor.green)
    thumb_path = tmp_path / 'thumb.png'

    assert media_info._save_thumb(pixmap, str(thumb_path)) is True
    assert thumb_path.exists()

    loaded = QtGui.QPixmap(str(thumb_path))
    assert loaded.width() == 88
    assert loaded.height() == 50


def test_get_media_duration_waits_for_duration_after_loaded_status(qapp):
    """Duration probing should continue until durationChanged even when LoadedMedia happens first."""

    class _Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

    class _FakePlayer:
        def __init__(self, _parent):
            self.errorOccurred = _Signal()
            self.durationChanged = _Signal()
            self.mediaStatusChanged = _Signal()

        def setSource(self, _source):
            return

    probe = media_info()
    event_step = {'count': 0}

    def _process_events_side_effect():
        event_step['count'] += 1
        if event_step['count'] == 1:
            probe.loaded_media = True
        elif event_step['count'] == 2:
            probe.duration_changed_event(5000)

    with patch('opal.core.ui.media.mediainfo.QMediaPlayer', _FakePlayer), \
            patch('opal.core.ui.media.mediainfo.sleep', lambda _x: None), \
            patch('opal.core.ui.media.mediainfo.QtWidgets.QApplication.instance') as mocked_instance:
        mocked_instance.return_value.processEvents.side_effect = _process_events_side_effect

        duration = probe.get_media_duration('C:/video.mp4')

    assert duration == 5000
