"""Large media previews, original-file metadata and platform file-manager actions."""
from pathlib import Path

from PySide6 import QtCore, QtGui
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer, QVideoSink
from PySide6.QtPdf import QPdfDocument

from openlp.core.common.platform import is_macosx, is_win
from openlp.core.common.i18n import translate
from openlp.core.lib.designmedia import media_kind, media_label
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.metadataview import MetadataView


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


class MediaPreviewMixin:
    """Shared inspector content for local dialogs and Cloud Library windows."""
    def __init__(self, parent, path, label=None, *, kind=None, preview_paths=None,
                 extra_metadata=None, allow_reveal=True, source_url=None, file_size=None, cover_path=None):
        super().__init__(parent)
        self.path = Path(path)
        self.player = None
        self.image = QtGui.QImage()
        name = label or media_label(self.path)
        self.setWindowTitle(name)
        self.resize(1000, 660)
        self.setMinimumSize(680, 440)
        content = self.contentWidget() if isinstance(self, QtWidgets.fluentqt.Window) else self
        layout = QtWidgets.QVBoxLayout(content)
        heading = QtWidgets.QLabel(name)
        heading.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        font = heading.font()
        font.setPointSize(20)
        heading.setFont(font)
        layout.addWidget(heading)
        body = QtWidgets.QHBoxLayout()
        mime = QtCore.QMimeDatabase().mimeTypeForFile(str(self.path))
        video = media_kind(self.path) == 'video' if kind is None else kind == 'media'
        audio_only = video and mime.name().startswith('audio/')
        self.preview_paths = list(preview_paths or [])
        self.pdf_document = None
        self.page_count = len(self.preview_paths)
        if kind == 'presentation' and self.path.suffix.lower() == '.pdf':
            self.pdf_document = QPdfDocument(self)
            self.pdf_document.load(str(self.path))
            if self.pdf_document.status() == QPdfDocument.Status.Ready:
                self.page_count = self.pdf_document.pageCount()
            else:
                self.pdf_document = None
        self.page = 0
        self.viewer = QtWidgets.QLabel()
        self.viewer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.viewer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
        if video:
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.audio.setMuted(not audio_only)
            self.player.setAudioOutput(self.audio)
            self.video_sink = QVideoSink(self)
            self.video_sink.videoFrameChanged.connect(self.update_video_frame)
            self.player.setVideoSink(self.video_sink)
            self.player.setLoops(QMediaPlayer.Loops.Infinite)
            self.player.errorOccurred.connect(lambda error, message:
                                              self.viewer.setText(tr('This media preview could not be played.')))
            if audio_only:
                self.viewer.setText(tr('Audio preview'))
            else:
                self.viewer.setText(tr('Loading media…'))
        else:
            reader = QtGui.QImageReader(str(cover_path or (self.preview_paths[0] if self.preview_paths else self.path)))
            reader.setAutoTransform(True)
            self.image = reader.read()
            if self.image.isNull():
                self.viewer.setText(tr('No preview available'))
        self.viewer.setMinimumSize(320, 240)
        body.addWidget(self.viewer, 1)
        keys = ['File size', 'File type']
        resolution_key = 'Preview resolution' if cover_path else 'Resolution'
        if not audio_only:
            keys.append(resolution_key)
        if video:
            keys += ['Duration', 'Audio codec'] if audio_only else ['Frame rate', 'Duration', 'Video codec']
        if kind == 'presentation':
            keys.append('Slides')
        keys += [key for key in (extra_metadata or {}) if key not in keys]
        metadata = MetadataView(dict.fromkeys(keys, '—'), self)
        metadata.setFixedWidth(300 if extra_metadata else 230)
        self.metadata = metadata.fields
        size = self.path.stat().st_size if file_size is None else file_size
        unit = 'B'
        for next_unit in ('KB', 'MB', 'GB', 'TB'):
            if size < 1024:
                break
            size /= 1024
            unit = next_unit
        self.metadata['File size'].setText(f'{size:,.0f} {unit}' if unit == 'B' else f'{size:,.1f} {unit}')
        self.metadata['File type'].setText(f'{self.path.suffix.lstrip(".").upper()} · {mime.name()}')
        for key, value in (extra_metadata or {}).items():
            self.metadata[key].setText(value)
        if kind == 'presentation' and self.page_count:
            self.metadata['Slides'].setText(str(self.page_count))
        if video:
            self.player.metaDataChanged.connect(self.update_video_metadata)
            self.player.durationChanged.connect(self.update_video_metadata)
            self.player.setSource(source_url or QtCore.QUrl.fromLocalFile(str(self.path.resolve())))
            self.player.play()
        elif not self.image.isNull():
            self.metadata[resolution_key].setText(f'{self.image.width()} × {self.image.height()}')
        body.addWidget(metadata)
        layout.addLayout(body, 1)
        if video:
            playback = QtWidgets.QHBoxLayout()
            self.play_button = QtWidgets.QPushButton(tr('Pause'))
            self.play_button.clicked.connect(self.toggle_playback)
            playback.addWidget(self.play_button)
            self.position_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.position_slider.setRange(0, 0)
            self.position_slider.sliderMoved.connect(self.player.setPosition)
            self.player.positionChanged.connect(self.position_slider.setValue)
            self.player.durationChanged.connect(lambda duration: self.position_slider.setRange(0, duration))
            playback.addWidget(self.position_slider, 1)
            self.mute_button = QtWidgets.QPushButton(tr('Mute'))
            self.mute_button.setCheckable(True)
            self.mute_button.setChecked(not audio_only)
            self.mute_button.toggled.connect(self.audio.setMuted)
            playback.addWidget(self.mute_button)
            layout.addLayout(playback)
        if self.page_count:
            pages = QtWidgets.QHBoxLayout()
            self.previous_button = QtWidgets.QPushButton(tr('Previous'))
            self.previous_button.clicked.connect(lambda: self.change_page(-1))
            pages.addWidget(self.previous_button)
            self.page_label = QtWidgets.QLabel()
            self.page_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            pages.addWidget(self.page_label, 1)
            self.next_button = QtWidgets.QPushButton(tr('Next'))
            self.next_button.clicked.connect(lambda: self.change_page(1))
            pages.addWidget(self.next_button)
            layout.addLayout(pages)
            self.change_page(0)
        buttons = QtWidgets.QHBoxLayout()
        if allow_reveal:
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
        if 'Resolution' in self.metadata and isinstance(resolution, QtCore.QSize) and resolution.isValid():
            self.metadata['Resolution'].setText(f'{resolution.width()} × {resolution.height()}')
        rate = metadata.value(QMediaMetaData.Key.VideoFrameRate)
        if 'Frame rate' in self.metadata and isinstance(rate, (int, float)) and rate > 0:
            self.metadata['Frame rate'].setText(f'{rate:g} fps')
        seconds = self.player.duration() // 1000
        if self.player.duration() > 0:
            hours, seconds = divmod(seconds, 3600)
            minutes, seconds = divmod(seconds, 60)
            self.metadata['Duration'].setText(f'{hours:02}:{minutes:02}:{seconds:02}')
        codec_key = 'Audio codec' if 'Audio codec' in self.metadata else 'Video codec'
        codec = metadata.stringValue(QMediaMetaData.Key.AudioCodec if codec_key == 'Audio codec'
                                     else QMediaMetaData.Key.VideoCodec)
        if codec:
            self.metadata[codec_key].setText(codec)

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_button.setText(tr('Play'))
        else:
            self.player.play()
            self.play_button.setText(tr('Pause'))

    def change_page(self, step):
        self.page = max(0, min(self.page_count - 1, self.page + step))
        if self.pdf_document:
            size = self.pdf_document.pagePointSize(self.page).toSize().scaled(
                1600, 1000, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.image = self.pdf_document.render(self.page, size)
        else:
            reader = QtGui.QImageReader(str(self.preview_paths[self.page]))
            reader.setAutoTransform(True)
            self.image = reader.read()
        self.page_label.setText(tr('Slide {page} of {count}').format(page=self.page + 1, count=self.page_count))
        self.previous_button.setEnabled(self.page > 0)
        self.next_button.setEnabled(self.page < self.page_count - 1)
        if not self.image.isNull():
            self.metadata['Resolution'].setText(f'{self.image.width()} × {self.image.height()}')
            self.fit_image()
        else:
            self.viewer.clear()
            self.viewer.setText(tr('No preview available'))

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
    def show_media(cls, parent, path, label=None, **kwargs):
        try:
            dialog = cls(parent, path, label, **kwargs)
        except OSError:
            QtWidgets.QMessageBox.warning(parent, tr('Preview'), tr('This media file is no longer available.'))
            return
        try:
            dialog.exec()
        finally:
            dialog.stop_video()
            dialog.deleteLater()


class MediaPreview(MediaPreviewMixin, QtWidgets.QDialog):
    """Local Library inspector with its existing modal dialog lifecycle."""
