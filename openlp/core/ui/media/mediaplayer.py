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
The :mod:`~openlp.core.ui.media.mediaplayer` module for media playing.
"""
import logging
import os
import re
import sysconfig
import time

from PySide6 import QtCore, QtWidgets
from PySide6.QtMultimedia import QAudioInput, QAudioOutput, QCamera, QMediaDevices, QMediaCaptureSession, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import QUrl

from openlp.core.common.mixins import LogMixin
from openlp.core.common.platform import is_macosx, is_win
from openlp.core.common.registry import Registry
from openlp.core.display.window import DisplayWindow
from openlp.core.ui.slidecontroller import SlideController
from openlp.core.ui.media.mediabase import MediaBase
from openlp.core.ui.media import MediaType

log = logging.getLogger(__name__)

# A workaround for https://bugreports.qt.io/browse/PYSIDE-2935
if is_win():
    pyside6_path = os.path.join(sysconfig.get_path('purelib'), 'PySide6')
    if os.path.exists(pyside6_path):
        os.add_dll_directory(pyside6_path)


class MediaPlayer(MediaBase, LogMixin):
    """
    A specialised version of the MediaPlayer class, which provides an media player for media when the main media class
    is also in use.
    """

    def __init__(self, parent=None):
        """
        Constructor
        """
        super(MediaPlayer, self).__init__(parent, "qt6")
        self.parent = parent
        self._active_playback = False
        self._ffmpeg_message_timestamp = 0.0
        self._ffmpeg_last_message = ''

    # Class-level Qt message handler state
    _qt_handler_installed = False
    _qt_previous_handler = None
    _registered_players = set()

    @classmethod
    def _notify_ffmpeg_error(cls, text: str):
        # Only surface errors for players that are actively trying to play media.
        for player in list(cls._registered_players):
            if not getattr(player, '_active_playback', False):
                continue
            now = time.monotonic()
            if player._ffmpeg_last_message == text and now - player._ffmpeg_message_timestamp < 1.5:
                continue
            player._ffmpeg_last_message = text
            player._ffmpeg_message_timestamp = now
            Registry().get("media_controller").handle_media_playback_error(player.controller, text)
            break

    def setup(self, controller: SlideController, display: DisplayWindow) -> None:
        """
        Set up an media and audio player and bind it to a controller and display

        :param controller: The controller where the media is
        :param display: The display where the media is.
        :return:
        """
        self.controller = controller
        self.display = display
        if controller.is_live:
            # Create media widget as a top-level window with tool window flags
            # This ensures it renders on the presentation display and stays visible
            # when OpenLP loses focus (due to WindowStaysOnTopHint)
            controller.media_widget = QtWidgets.QWidget(None)
            controller.media_widget.setWindowFlags(
                QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.Tool
                | QtCore.Qt.WindowType.WindowStaysOnTopHint)
            controller.media_widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_X11NetWmWindowTypeDialog)
            # On macOS, Tool windows are hidden when the app is deactivated unless this is set.
            # Matches the same attribute used on DisplayWindow.
            if is_macosx():
                controller.media_widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
            # Prevent the media widget from stealing focus when shown
            controller.media_widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        else:
            controller.media_widget = QtWidgets.QWidget(display)
        self.media_player = QMediaPlayer(None)
        self.audio_output = QAudioOutput()
        self._apply_audio_output_setting()
        self.media_player.setAudioOutput(self.audio_output)
        qtwidgets_is_mocked = not isinstance(getattr(QtWidgets, 'QWidget', None), type)
        if qtwidgets_is_mocked:
            # Keep tests from instantiating native video widgets when QtWidgets is patched.
            self.video_widget = QtWidgets.QWidget()
            if hasattr(self.video_widget, 'isVisible'):
                self.video_widget.isVisible.return_value = False
        else:
            self.video_widget = QVideoWidget(controller.media_widget)
        layout = QtWidgets.QVBoxLayout(controller.media_widget)
        layout.addWidget(self.video_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.media_player.positionChanged.connect(self.position_changed_event)
        self.media_player.durationChanged.connect(self.duration_changed_event)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed_event)
        self.media_player.errorOccurred.connect(self.error_occurred_event)
        self._install_qt_message_handler()
        MediaPlayer._registered_players.add(self)
        # device stream objects. setVideoOutput is called when loading stream, video_widget can't be used by both
        # QMediaCaptureSession and QMediaPlayer
        self.media_capture_session = QMediaCaptureSession()
        self.media_capture_session.setAudioOutput(self.audio_output)
        self.device_video_input = None
        self.device_audio_input = None
        self.set_visible(False)  # Hide player till needed

    def _apply_audio_output_setting(self) -> None:
        """
        Apply the configured audio output device for this controller, if one is selected.
        """
        if not hasattr(self, 'controller') or self.controller is None:
            return
        setting_key = 'media/live audio output' if self.controller.is_live else 'media/preview audio output'
        settings = None
        try:
            settings = Registry().get('settings')
        except Exception:
            return
        if not settings:
            return
        output_name = settings.value(setting_key)
        if not output_name:
            return
        for output_device in QMediaDevices.audioOutputs():
            if output_device.description() == output_name:
                self.audio_output.setDevice(output_device)
                break

    def media_status_changed_event(self, event):
        """
        Handle the end of Media event and update UI
        """
        if self.controller.media_play_item.media_type == MediaType.Dual:
            return
        if event == QMediaPlayer.MediaStatus.LoadedMedia:
            self._active_playback = True
        if event in (QMediaPlayer.MediaStatus.EndOfMedia,
                     QMediaPlayer.MediaStatus.InvalidMedia,
                     QMediaPlayer.MediaStatus.NoMedia):
            self._active_playback = False
        if event in (QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.StalledMedia):
            message = self.media_player.errorString() or 'Media decode failed to start on this platform.'
            Registry().get("media_controller").handle_media_playback_error(self.controller, message)
            return
        if event == QMediaPlayer.MediaStatus.EndOfMedia:
            self._pause_on_last_frame_if_not_looping()
            if self.controller.is_live:
                Registry().get("media_controller").live_media_status_changed.emit()
            else:
                Registry().get("media_controller").preview_media_status_changed.emit()

    def _pause_on_last_frame_if_not_looping(self) -> None:
        """Keep the final video frame visible when playback reaches the end without looping."""
        if self.controller.media_play_item.media_type != MediaType.Video:
            return
        loops = self.media_player.loops()
        if loops != QMediaPlayer.Loops.Once or not self.media_player.isSeekable():
            return
        duration = max(int(self.media_player.duration() or 0),
                       int(getattr(self.controller.media_play_item, 'length', 0) or 0))
        if duration <= 0:
            return
        last_frame_position = max(duration - 1, 0)
        self.media_player.setPosition(last_frame_position)
        self.media_player.pause()
        self.controller.media_play_item.timer = last_frame_position

    def position_changed_event(self, position) -> None:
        """
        Media callback for position changed event.  Saves position and calls UI updates.
        :param event: The media position has changed
        :return: None
        """
        if self.controller.media_play_item.media_type == MediaType.Dual:
            return
        self.controller.media_play_item.timer = position
        if self.controller.is_live:
            Registry().get("media_controller").live_media_tick.emit()
        else:
            Registry().get("media_controller").preview_media_tick.emit()

    def duration_changed_event(self, duration: int) -> None:
        """
        Update controller media length when backend reports duration at runtime.
        """
        if self.controller.media_play_item.media_type == MediaType.Dual:
            return
        if duration is None or duration <= 0:
            return
        self.controller.media_play_item.length = int(duration)
        if hasattr(self.controller, 'mediabar') and self.controller.mediabar:
            self.controller.mediabar.seek_slider.setTickInterval(max(self.controller.media_play_item.length // 10, 1))
            self.controller.mediabar.seek_slider.setMaximum(self.controller.media_play_item.length)
        Registry().get('media_controller')._update_seek_ui(self.controller)

    def error_occurred_event(self, error, error_text='') -> None:
        """
        Handle media backend errors and pass to media controller for user feedback.
        """
        if error == QMediaPlayer.Error.NoError:
            return
        self._active_playback = False
        message = str(error_text or self.media_player.errorString() or error)
        self.log_debug(f"Media player error: {message}")
        Registry().get("media_controller").handle_media_playback_error(self.controller, message)

    @staticmethod
    def _looks_like_ffmpeg_decode_error(message: str) -> bool:
        text = (message or '').lower()
        return ('[av' in text and 'error' in text) or \
            ('ffmpeg' in text and ('error' in text or 'failed' in text)) or \
            ('hardware accelerated' in text and 'decoding' in text) or \
            ('get current frame error' in text) or \
            ('failed to get pixel format' in text)

    @classmethod
    def _install_qt_message_handler(cls):
        if cls._qt_handler_installed:
            return

        def _handler(msg_type, context, message):
            text = str(message)
            if cls._looks_like_ffmpeg_decode_error(text):
                cls._notify_ffmpeg_error(text)
            if cls._qt_previous_handler:
                cls._qt_previous_handler(msg_type, context, message)

        cls._qt_previous_handler = QtCore.qInstallMessageHandler(_handler)
        cls._qt_handler_installed = True

    def toggle_loop(self, loop_required: bool) -> None:
        """
        Switch the loop toggle setting

        :param loop_required: Do I need to loop
        """
        if loop_required:
            self.media_player.setLoops(QMediaPlayer.Loops.Infinite)
        else:
            self.media_player.setLoops(QMediaPlayer.Loops.Once)

    def load(self) -> bool:
        """
        Load a media file into the player

        :return:  Success or Failure
        """
        self.log_debug("load external media stream in Media Player")
        if self.controller.media_play_item.media_file:
            self._apply_audio_output_setting()
            self.media_capture_session.setVideoOutput(None)
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.setVideoOutput(self.video_widget)
            self.media_player.setPlaybackRate(1.0)
            self.media_player.setSource(QUrl.fromLocalFile(str(self.controller.media_play_item.media_file)))
            return True
        return False

    def load_stream(self) -> bool:
        """
        Load a media stream into the player
        :return:  Success or Failure
        """
        self.log_debug("load stream  in Media Player")

        if self.controller.media_play_item.external_stream:
            self._apply_audio_output_setting()
            mrl = self.controller.media_play_item.external_stream[0]
            if self.controller.media_play_item.media_type == MediaType.DeviceStream:
                self.media_player.setVideoOutput(None)
                self.media_capture_session.setVideoOutput(self.video_widget)
                vdev_name = re.search(r'qt6video=(.+);', mrl)
                self.device_video_input = None
                if vdev_name:
                    for vdev in QMediaDevices.videoInputs():
                        if vdev.description() == vdev_name.group(1):
                            self.device_video_input = QCamera(vdev)
                            self.media_capture_session.setCamera(self.device_video_input)
                            break
                adev_name = re.search(r'qt6audio=(.+)', mrl)
                self.device_audio_input = None
                if adev_name:
                    for adev in QMediaDevices.audioInputs():
                        if adev.description() == adev_name.group(1):
                            self.device_audio_input = QAudioInput()
                            self.device_audio_input.setDevice(adev)
                            self.device_audio_input.setMuted(True)
                            self.media_capture_session.setAudioInput(self.device_audio_input)
                            break
                return True
            elif self.controller.media_play_item.media_type == MediaType.NetworkStream:
                self.media_capture_session.setVideoOutput(None)
                self.media_player.setVideoOutput(self.video_widget)
                self.media_player.setPlaybackRate(1.0)
                self.media_player.setSource(QUrl(mrl))
                return True
        return False

    def play(self) -> None:
        """
        Play the current loaded audio item
        :return:
        """
        if self.controller.media_play_item.media_type == MediaType.DeviceStream:
            if self.device_video_input:
                self.device_video_input.start()
            if self.device_audio_input:
                self.device_audio_input.setMuted(False)
        else:
            self.media_player.play()
        self._active_playback = True
        # TODO handle variable start times for first play

    def pause(self) -> None:
        """
        Pause the current item

        :param controller: The controller which is managing the display
        :return:
        """
        if self.controller.media_play_item.media_type == MediaType.DeviceStream:
            if self.device_video_input:
                self.device_video_input.stop()
            if self.device_audio_input:
                self.device_audio_input.setMuted(True)
        else:
            self.media_player.pause()
        self._active_playback = False

    def stop(self) -> None:
        """
        Stop the current item

        :param controller: The controller where the media is
        :return:
        """
        if self.controller.media_play_item.media_type == MediaType.DeviceStream:
            if self.device_video_input:
                self.device_video_input.stop()
            if self.device_audio_input:
                self.device_audio_input.setMuted(True)
        else:
            self.media_player.stop()
        self._active_playback = False

    def duration(self) -> int:
        """
        Obtain the duration of the playing
        """
        return self.media_player.duration()
