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
The :mod:`~openlp.core.ui.media.mediainfo` module for media meta data.
"""
import logging
from pathlib import Path

from time import sleep

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer, QVideoSink

log = logging.getLogger(__name__)


class media_info(QObject):

    @staticmethod
    def _scaled_thumb(pixmap: QtGui.QPixmap) -> QtGui.QPixmap:
        thumb_width = 88
        thumb_height = 50
        scaled = pixmap.scaled(thumb_width, thumb_height,
                               QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                               QtCore.Qt.TransformationMode.SmoothTransformation)
        canvas = QtGui.QPixmap(thumb_width, thumb_height)
        canvas.fill(QtCore.Qt.GlobalColor.black)
        x = (thumb_width - scaled.width()) // 2
        y = (thumb_height - scaled.height()) // 2
        painter = QtGui.QPainter(canvas)
        painter.drawPixmap(x, y, scaled)
        painter.end()
        return canvas

    @staticmethod
    def _save_thumb(pixmap: QtGui.QPixmap, thumb_file: str) -> bool:
        if pixmap.isNull():
            return False
        target = media_info._scaled_thumb(pixmap)
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
    def _pixmap_from_metadata_value(value) -> QtGui.QPixmap:
        if value is None:
            return QtGui.QPixmap()
        if isinstance(value, QtGui.QPixmap):
            return value
        if isinstance(value, QtGui.QImage):
            return QtGui.QPixmap.fromImage(value)
        if isinstance(value, QUrl):
            if value.isLocalFile():
                return QtGui.QPixmap(value.toLocalFile())
            return QtGui.QPixmap()
        if isinstance(value, str):
            return QtGui.QPixmap(value)
        return QtGui.QPixmap()

    @staticmethod
    def _extract_embedded_poster(media_player: QMediaPlayer) -> QtGui.QPixmap:
        metadata = media_player.metaData()
        # Prefer direct image metadata first.
        for key_name in ('ThumbnailImage', 'CoverArtImage', 'PosterImage'):
            pixmap = media_info._pixmap_from_metadata_value(media_info._metadata_value(metadata, key_name))
            if not pixmap.isNull():
                return pixmap
        # Fallback to URL metadata if image fields are missing.
        for key_name in ('ThumbnailUrl', 'CoverArtUrlLarge', 'CoverArtUrlSmall'):
            pixmap = media_info._pixmap_from_metadata_value(media_info._metadata_value(metadata, key_name))
            if not pixmap.isNull():
                return pixmap
        return QtGui.QPixmap()

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
        self.media_player = QMediaPlayer(None)
        self.media_player.errorOccurred.connect(self.error_event)
        self.media_player.durationChanged.connect(self.duration_changed_event)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed_event)
        self.media_player.setSource(QUrl.fromLocalFile(str(media_file)))
        loops = 0
        while not self.got_duration and not self.loaded_media and not self.error_occurred and loops < 100:
            loops += 1
            sleep(0.01)
            QtWidgets.QApplication.instance().processEvents()
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
        self.media_player = QMediaPlayer(None)
        self.media_player.errorOccurred.connect(self.error_event)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed_event)
        self.media_player.setSource(QUrl.fromLocalFile(str(media_file)))
        loops = 0
        while not self.loaded_media and not self.error_occurred and loops < 100:
            loops += 1
            sleep(0.01)
            QtWidgets.QApplication.instance().processEvents()
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
            pixmap = QtGui.QPixmap.fromImage(image)
            if self._save_thumb(pixmap, thumb_file):
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
