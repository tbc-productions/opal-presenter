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
The :mod:`~opal.core.ui.media.mediainfo` module for media meta data.
"""
import logging
from pathlib import Path

from time import sleep

from PySide6 import QtCore, QtGui
from opal.core.widgets import fluent as QtWidgets
from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer, QVideoSink

from opal.core.common.i18n import translate
from opal.core.common.path import ensure_local_file

log = logging.getLogger(__name__)


class media_info(QObject):

    @staticmethod
    def _scaled_thumb(image: QtGui.QImage | QtGui.QPixmap) -> QtGui.QImage:
        if isinstance(image, QtGui.QPixmap):
            image = image.toImage()
        thumb_width = 88
        thumb_height = 50
        scaled = image.scaled(thumb_width, thumb_height,
                              QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                              QtCore.Qt.TransformationMode.SmoothTransformation)
        canvas = QtGui.QImage(thumb_width, thumb_height, QtGui.QImage.Format.Format_ARGB32)
        canvas.fill(QtCore.Qt.GlobalColor.black)
        x = (thumb_width - scaled.width()) // 2
        y = (thumb_height - scaled.height()) // 2
        painter = QtGui.QPainter(canvas)
        painter.drawImage(x, y, scaled)
        painter.end()
        return canvas

    @staticmethod
    def _save_thumb(image: QtGui.QImage | QtGui.QPixmap, thumb_file: str) -> bool:
        if image.isNull():
            return False
        target = media_info._scaled_thumb(image)
        thumb_path = Path(thumb_file)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        return target.save(str(thumb_path), 'PNG')

    @staticmethod
    def _metadata_value(metadata: QMediaMetaData, key_name: str):
        # PySide/Qt variants expose metadata keys either at QMediaMetaData.Key or directly on QMediaMetaData.
        key = None
        if hasattr(QMediaMetaData, 'Key') and hasattr(QMediaMetaData.Key, key_name):
            key = getattr(QMediaMetaData.Key, key_name)
        elif hasattr(QMediaMetaData, key_name):
            key = getattr(QMediaMetaData, key_name)
        if key is None:
            return None
        return metadata.value(key)

    @staticmethod
    def _pixmap_from_metadata_value(value) -> QtGui.QImage:
        if value is None:
            return QtGui.QImage()
        if isinstance(value, QtGui.QImage):
            return value
        if isinstance(value, QtGui.QPixmap):
            return value.toImage()
        if isinstance(value, QUrl):
            if value.isLocalFile():
                local_file = value.toLocalFile()
                if not ensure_local_file(local_file):
                    return QtGui.QImage()
                return QtGui.QImage(local_file)
            return QtGui.QImage()
        if isinstance(value, str):
            if not ensure_local_file(value):
                return QtGui.QImage()
            return QtGui.QImage(value)
        return QtGui.QImage()

    @staticmethod
    def _extract_embedded_poster(media_player: QMediaPlayer) -> QtGui.QImage:
        metadata = media_player.metaData()
        # Prefer direct image metadata first.
        for key_name in ('ThumbnailImage', 'CoverArtImage', 'PosterImage'):
            image = media_info._pixmap_from_metadata_value(media_info._metadata_value(metadata, key_name))
            if not image.isNull():
                return image
        # Fallback to URL metadata if image fields are missing.
        for key_name in ('ThumbnailUrl', 'CoverArtUrlLarge', 'CoverArtUrlSmall'):
            image = media_info._pixmap_from_metadata_value(media_info._metadata_value(metadata, key_name))
            if not image.isNull():
                return image
        return QtGui.QImage()

    def __init__(self):
        super().__init__()
        self.got_duration = False
        self.error_occurred = False
        self.duration = 0
        self.loaded_media = False
        self.error_message = ''

    def get_media_duration(self, media_file: str) -> int:
        """
        Set up a headless media player to parse the mediafile and get duration.

        :param controller: The controller where the media is
        :param display: The display where the media is.
        :return:
        """
        self.got_duration = False
        self.error_occurred = False
        self.duration = 0
        self.loaded_media = False
        self.error_message = ''
        if not ensure_local_file(media_file):
            return 0
        self.media_player = QMediaPlayer(None)
        self.media_player.errorOccurred.connect(self.error_event)
        self.media_player.durationChanged.connect(self.duration_changed_event)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed_event)
        self.media_player.setSource(QUrl.fromLocalFile(str(media_file)))
        loops = 0
        while not self.got_duration and not self.error_occurred and loops < 100:
            loops += 1
            sleep(0.01)
            QtWidgets.QApplication.instance().processEvents()
        if hasattr(self.media_player, 'stop'):
            self.media_player.stop()
        return self.duration

    def is_media_supported(self, media_file: str) -> tuple[bool, str]:
        """
        Probe whether the current platform/backend can load the media source.

        :param media_file: The file path to probe.
        :return: (is_supported, error_message)
        """
        self.got_duration = False
        self.error_occurred = False
        self.duration = 0
        self.loaded_media = False
        self.error_message = ''
        if not ensure_local_file(media_file):
            return (
                False,
                translate('OpenLP.MediaController', 'The media file could not be downloaded from cloud storage.')
            )
        self.media_player = QMediaPlayer(None)
        self.media_player.errorOccurred.connect(self.error_event)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed_event)
        self.media_player.setSource(QUrl.fromLocalFile(str(media_file)))
        loops = 0
        while not self.loaded_media and not self.error_occurred and loops < 100:
            loops += 1
            sleep(0.01)
            QtWidgets.QApplication.instance().processEvents()
        if hasattr(self.media_player, 'stop'):
            self.media_player.stop()
        return (not self.error_occurred, self.error_message)

    def create_media_thumbnail(self, media_file: str, thumb_file: str) -> bool:
        """
        Create a thumbnail for video media by grabbing the first available decoded frame.

        :param media_file: The media file path.
        :param thumb_file: The target thumbnail path.
        :return: True on success, False otherwise.
        """
        self.error_occurred = False
        self.error_message = ''
        if not ensure_local_file(media_file):
            return False
        frame_captured = False
        media_player = QMediaPlayer(None)
        audio_output = QAudioOutput()
        audio_output.setVolume(0.0)
        media_player.setAudioOutput(audio_output)
        video_sink = QVideoSink()
        media_player.setVideoOutput(video_sink)

        def on_error(error, error_text=''):
            self.error_occurred = True
            self.error_message = str(error_text or media_player.errorString() or error)

        def try_save_embedded_poster():
            nonlocal frame_captured
            if frame_captured or self.error_occurred:
                return
            poster = self._extract_embedded_poster(media_player)
            if self._save_thumb(poster, thumb_file):
                frame_captured = True
                media_player.stop()

        def on_frame_changed(video_frame):
            nonlocal frame_captured
            if frame_captured or self.error_occurred:
                return
            if not video_frame.isValid():
                return
            image = video_frame.toImage()
            if image.isNull():
                return
            if self._save_thumb(image, thumb_file):
                frame_captured = True
                media_player.stop()

        media_player.errorOccurred.connect(on_error)
        media_player.metaDataChanged.connect(try_save_embedded_poster)
        video_sink.videoFrameChanged.connect(on_frame_changed)
        media_player.setSource(QUrl.fromLocalFile(str(media_file)))
        try_save_embedded_poster()
        media_player.play()

        loops = 0
        while not frame_captured and not self.error_occurred and loops < 250:
            loops += 1
            sleep(0.01)
            QtWidgets.QApplication.instance().processEvents()
        media_player.stop()
        return frame_captured

    def duration_changed_event(self, duration: int):
        self.got_duration = True
        self.duration = duration

    def media_status_changed_event(self, status) -> None:
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self.loaded_media = True

    def error_event(self, error, error_text='') -> None:
        self.error_occurred = True
        self.error_message = str(error_text or self.media_player.errorString() or error)
