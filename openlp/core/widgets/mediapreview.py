"""Large media previews, original-file metadata and platform file-manager actions."""
from pathlib import Path

from PySide6 import QtCore, QtGui
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer, QVideoSink

from openlp.core.common.platform import is_macosx, is_win
from openlp.core.common.i18n import translate
from openlp.core.lib.designmedia import media_kind, media_label
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets import fluent as QtWidgets


def tr(text):
    return translate('OpenLP.MediaPreview', text)


def reveal_caption():
    return tr('Show in Finder') if is_macosx() else tr('Show in Explorer') if is_win() else tr('Show in file manager')


def reveal_media(path, parent=None):
    path = Path(path).resolve()
    if not path.is_file():
        QtWidgets.QMessageBox.warning(parent, tr('File not found'), tr('This media file is no longer available.'))
        return
    if is_macosx():
        QtCore.QProcess.startDetached('open', ['-R', str(path)])
    elif is_win():
        QtCore.QProcess.startDetached('explorer', ['/select,', str(path)])
    else:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path.parent)))


def media_context_menu(widget, position, path, label=None):
    if not path:
        return
    menu = QtWidgets.QMenu(widget)
    menu.addAction(UiIcons().preview, tr('Preview'), lambda: MediaPreview.show_media(widget, path, label))
    menu.addAction(UiIcons().folder, reveal_caption(), lambda: reveal_media(path, widget))
    menu.exec(widget.mapToGlobal(position))
    menu.deleteLater()


class MediaPreview(QtWidgets.QDialog):
    def __init__(self, parent, path, label=None):
        super().__init__(parent)
        self.path = Path(path)
        self.player = None
        self.image = QtGui.QImage()
        name = label or media_label(self.path)
        self.setWindowTitle(name)
        self.resize(1000, 660)
        self.setMinimumSize(680, 440)
        layout = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QLabel(name)
        heading.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        font = heading.font()
        font.setPointSize(20)
        heading.setFont(font)
        layout.addWidget(heading)
        body = QtWidgets.QHBoxLayout()
        video = media_kind(self.path) == 'video'
        self.viewer = QtWidgets.QLabel()
        self.viewer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.viewer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
        if video:
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.audio.setMuted(True)
            self.player.setAudioOutput(self.audio)
            self.video_sink = QVideoSink(self)
            self.video_sink.videoFrameChanged.connect(self.update_video_frame)
            self.player.setVideoSink(self.video_sink)
            self.player.setLoops(QMediaPlayer.Loops.Infinite)
        else:
            reader = QtGui.QImageReader(str(self.path))
            reader.setAutoTransform(True)
            self.image = reader.read()
        self.viewer.setMinimumSize(320, 240)
        body.addWidget(self.viewer, 1)
        metadata = QtWidgets.QWidget()
        metadata.setFixedWidth(230)
        fields = QtWidgets.QFormLayout(metadata)
        fields.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.metadata = {}
        keys = ['File size', 'File type', 'Resolution'] + (['Frame rate', 'Duration', 'Video codec'] if video else [])
        for key in keys:
            value = QtWidgets.QLabel('—')
            value.setWordWrap(True)
            value.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            value.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            self.metadata[key] = value
            fields.addRow(QtWidgets.QLabel(tr(key)), value)
        size = self.path.stat().st_size
        unit = 'B'
        for next_unit in ('KB', 'MB', 'GB', 'TB'):
            if size < 1024:
                break
            size /= 1024
            unit = next_unit
        self.metadata['File size'].setText(f'{size:,.0f} {unit}' if unit == 'B' else f'{size:,.1f} {unit}')
        mime = QtCore.QMimeDatabase().mimeTypeForFile(str(self.path))
        self.metadata['File type'].setText(f'{self.path.suffix.lstrip(".").upper()} · {mime.name()}')
        if video:
            self.player.metaDataChanged.connect(self.update_video_metadata)
            self.player.durationChanged.connect(self.update_video_metadata)
            self.player.setSource(QtCore.QUrl.fromLocalFile(str(self.path.resolve())))
            self.player.play()
        elif not self.image.isNull():
            self.metadata['Resolution'].setText(f'{self.image.width()} × {self.image.height()}')
        body.addWidget(metadata)
        layout.addLayout(body, 1)
        buttons = QtWidgets.QHBoxLayout()
        reveal = QtWidgets.QPushButton(reveal_caption())
        reveal.setIcon(UiIcons().folder)
        reveal.clicked.connect(lambda: reveal_media(self.path, self))
        buttons.addWidget(reveal)
        buttons.addStretch()
        close = QtWidgets.QPushButton(tr('Close'))
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.finished.connect(self.stop_video)

    def update_video_metadata(self, *args):
        metadata = self.player.metaData()
        resolution = metadata.value(QMediaMetaData.Key.Resolution)
        if isinstance(resolution, QtCore.QSize) and resolution.isValid():
            self.metadata['Resolution'].setText(f'{resolution.width()} × {resolution.height()}')
        rate = metadata.value(QMediaMetaData.Key.VideoFrameRate)
        if isinstance(rate, (int, float)) and rate > 0:
            self.metadata['Frame rate'].setText(f'{rate:g} fps')
        seconds = self.player.duration() // 1000
        if self.player.duration() > 0:
            hours, seconds = divmod(seconds, 3600)
            minutes, seconds = divmod(seconds, 60)
            self.metadata['Duration'].setText(f'{hours:02}:{minutes:02}:{seconds:02}')
        codec = metadata.stringValue(QMediaMetaData.Key.VideoCodec)
        if codec:
            self.metadata['Video codec'].setText(codec)

    def update_video_frame(self, frame):
        if frame.isValid():
            self.image = frame.toImage()
            self.fit_image()

    def stop_video(self, *args):
        if self.player:
            self.player.stop()
            self.player.setSource(QtCore.QUrl())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.image.isNull():
            QtCore.QTimer.singleShot(0, self.fit_image)

    def fit_image(self):
        self.viewer.setPixmap(QtGui.QPixmap.fromImage(self.image).scaled(
            self.viewer.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation))

    @classmethod
    def show_media(cls, parent, path, label=None):
        try:
            dialog = cls(parent, path, label)
        except OSError:
            QtWidgets.QMessageBox.warning(parent, tr('Preview'), tr('This media file is no longer available.'))
            return
        try:
            dialog.exec()
        finally:
            dialog.stop_video()
            dialog.deleteLater()
