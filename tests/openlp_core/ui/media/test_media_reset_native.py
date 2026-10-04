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
"""Exercise native MP4 cleanup in a child process so a deadlock cannot hang pytest."""
import os
from pathlib import Path
import subprocess
import sys


def test_hidden_mp4_reset_and_replay():
    """A paused, hidden MP4 must stop synchronously and allow the next load."""
    root = Path(__file__).resolve().parents[4]
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONPATH=str(root))
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(root / 'tests/resources/media/mp4_file.mp4')],
        cwd=root, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Hidden MP4 reset and replay completed' in result.stdout


def run_native_reset(media_file):
    from types import SimpleNamespace

    from PySide6 import QtCore, QtWidgets
    from PySide6.QtMultimedia import QAudioOutput, QMediaCaptureSession, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    from openlp.core.ui.media import MediaPlayItem, MediaType
    from openlp.core.ui.media.mediaplayer import MediaPlayer

    app = QtWidgets.QApplication([])
    player = MediaPlayer()
    item = MediaPlayItem()
    item.media_type = MediaType.Video
    item.media_file = Path(media_file)
    player.controller = SimpleNamespace(media_play_item=item)
    player.media_player = QMediaPlayer()
    player.media_capture_session = QMediaCaptureSession()
    player.audio_output = QAudioOutput()
    player.audio_output.setMuted(True)
    player.video_widget = QVideoWidget()
    player.video_widget.resize(320, 180)
    player._apply_audio_output_setting = lambda: None
    positions = []
    player.media_player.positionChanged.connect(positions.append)
    errors = []
    player.media_player.errorOccurred.connect(lambda *args: errors.append(str(args)))

    def retire_media():
        assert any(position > 0 for position in positions), 'MP4 did not start'
        player.pause()
        player.video_widget.hide()
        positions.clear()
        player.reset()
        assert not positions, 'Reset re-entered callbacks for the retired item'
        assert not player.media_player.signalsBlocked()
        assert player.media_player.videoOutput() is None
        assert player.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
        assert player.load()
        assert player.media_player.videoOutput() is player.video_widget
        player.video_widget.show()
        player.play()
        QtCore.QTimer.singleShot(1500, finish)

    def finish():
        assert any(position > 0 for position in positions), 'MP4 did not play after reset'
        assert not errors, errors
        player.reset()
        print('Hidden MP4 reset and replay completed', flush=True)
        app.quit()

    def fail_on_callback_exception(kind, value, traceback):
        sys.__excepthook__(kind, value, traceback)
        app.exit(1)

    sys.excepthook = fail_on_callback_exception
    player.video_widget.show()
    assert player.load()
    player.play()
    QtCore.QTimer.singleShot(1500, retire_media)
    return app.exec()


if __name__ == '__main__':
    sys.exit(run_native_reset(sys.argv[1]))
