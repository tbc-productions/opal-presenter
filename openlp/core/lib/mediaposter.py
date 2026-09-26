"""Decode full-resolution video poster frames without disturbing live playback."""
from PySide6 import QtCore, QtGui
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink


def video_frame(media_file, position_ms=1000, timeout_ms=5000):
    """Decode a poster silently, with a bounded wait and no dependency on external tools."""
    image = QtGui.QImage()
    player = QMediaPlayer()
    sink = QVideoSink(player)
    player.setVideoOutput(sink)
    # No audio output is attached: decoding must never play sound during export.
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    finished = False
    started = False
    target_ms = max(0, int(position_ms))

    def finish(*_args):
        nonlocal finished
        finished = True
        loop.quit()

    def loaded(status):
        nonlocal started, target_ms
        if status in (QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.EndOfMedia):
            finish()
        elif status == QMediaPlayer.MediaStatus.LoadedMedia and not started:
            started = True
            if player.duration() > 0:
                target_ms = min(target_ms, max(0, player.duration() - 100))
            player.setPosition(target_ms)
            player.play()

    def capture(frame):
        nonlocal image
        if finished or not started or not frame.isValid():
            return
        if 0 <= frame.startTime() < target_ms * 1000 - 100000:
            return
        decoded = frame.toImage()
        if not decoded.isNull():
            image = decoded.copy()
            finish()

    timer.timeout.connect(finish)
    player.errorOccurred.connect(finish)
    player.mediaStatusChanged.connect(loaded)
    sink.videoFrameChanged.connect(capture)
    try:
        timer.start(timeout_ms)
        player.setSource(QtCore.QUrl.fromLocalFile(str(media_file)))
        if not finished:
            loop.exec()
    finally:
        timer.stop()
        sink.videoFrameChanged.disconnect(capture)
        player.mediaStatusChanged.disconnect(loaded)
        player.errorOccurred.disconnect(finish)
        player.stop()
        player.setVideoOutput(None)
        player.setSource(QtCore.QUrl())
        player.deleteLater()
    return image
