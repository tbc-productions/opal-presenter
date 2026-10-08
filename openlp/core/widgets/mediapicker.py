"""Shared Fluent media library picker for the slide and theme designers."""
from pathlib import Path

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.lib.designmedia import (
    MIME_TYPES, cache_media, media_kind, media_label, media_to_source, resolve_media, remember_media_label
)
from openlp.core.lib.pluginmanager import PluginManager
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.edits import PathEdit
from openlp.core.widgets.mediapreview import media_context_menu
from openlp.core.state import State


def tr(text):
    return translate('OpenLP.MediaPicker', text)


class MediaPicker(QtWidgets.QDialog):
    """Browse existing library folders without opening a second editor."""
    def __init__(self, parent=None, kinds=('image', 'video')):
        super().__init__(parent)
        self.kinds = kinds
        self.selected_path = None
        self.entries = []
        self.tiles = []
        self._connected_libraries = set()
        self.setWindowTitle(tr('Choose media'))
        self.resize(800, 600)
        self.setMinimumSize(580, 420)
        layout = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QLabel(tr('Choose media'))
        font = heading.font()
        font.setPointSize(20)
        heading.setFont(font)
        layout.addWidget(heading)
        filters = QtWidgets.QHBoxLayout()
        self.kind_combo = QtWidgets.QComboBox()
        self.kind_combo.addItem(tr('All media'), None)
        for kind in kinds:
            self.kind_combo.addItem(tr('Images') if kind == 'image' else tr('Videos'), kind)
        self.kind_combo.setVisible(len(kinds) > 1)
        filters.addWidget(self.kind_combo)
        self.folder_combo = QtWidgets.QComboBox()
        filters.addWidget(self.folder_combo)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(tr('Search media'))
        self.search.setClearButtonEnabled(True)
        filters.addWidget(self.search, 1)
        self.add_button = QtWidgets.QPushButton(tr('Add files'))
        self.add_button.setIcon(UiIcons().plus)
        self.add_button.clicked.connect(self.add_files)
        filters.addWidget(self.add_button)
        layout.addLayout(filters)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.content)
        self.grid.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.grid.setSpacing(12)
        self.scroll.setWidget(self.content)
        self.scroll.viewport().installEventFilter(self)
        layout.addWidget(self.scroll, 1)
        self.empty = QtWidgets.QLabel(tr('No media'))
        self.empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        cancel = QtWidgets.QPushButton(tr('Cancel'))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.insert_button = QtWidgets.QPushButton(tr('Insert'))
        self.insert_button.setEnabled(False)
        self.insert_button.clicked.connect(self.accept)
        self.insert_button.setDefault(True)
        buttons.addWidget(self.insert_button)
        layout.addLayout(buttons)
        self.kind_combo.currentIndexChanged.connect(self.filter_entries)
        self.folder_combo.currentIndexChanged.connect(self.filter_entries)
        self.search.textChanged.connect(self.filter_entries)
        self.reload()

    def libraries(self):
        for kind, name in (('image', 'images'), ('video', 'media')):
            plugin = PluginManager.get_plugin_by_name(name)
            if kind in self.kinds and plugin and plugin.is_active() and plugin.media_item:
                yield kind, plugin.media_item

    def reload(self, selected_path=None):
        self.entries = []
        with QtCore.QSignalBlocker(self.folder_combo):
            folder = self.folder_combo.currentData()
            self.folder_combo.clear()
            self.folder_combo.addItem(tr('All folders'), None)
            for kind, library in self.libraries():
                if hasattr(library, 'thumbnail_updated') and id(library) not in self._connected_libraries:
                    library.thumbnail_updated.connect(self.thumbnail_ready)
                    self._connected_libraries.add(id(library))
                for group in library.manager.get_all_objects(library.folder_class):
                    self.folder_combo.addItem(group.name, (kind, group.id))
                for item in library.manager.get_all_objects(library.item_class):
                    path = Path(item.file_path)
                    if path.suffix.lower().lstrip('.') in MIME_TYPES and path.is_file():
                        self.entries.append((kind, library, item, path))
            index = self.folder_combo.findData(folder)
            self.folder_combo.setCurrentIndex(max(0, index))
        self.add_button.setEnabled(bool(list(self.libraries())))
        self.selected_path = selected_path
        self.filter_entries()

    def filter_entries(self, *args):
        for tile in self.tiles:
            self.grid.removeWidget(tile)
            tile.deleteLater()
        self.tiles = []
        kind, folder = self.kind_combo.currentData(), self.folder_combo.currentData()
        query = self.search.text().casefold()
        visible_paths = []
        for entry_kind, library, item, path in self.entries:
            if kind and kind != entry_kind or folder and folder != (entry_kind, item.folder_id):
                continue
            name = Path(item.name or path.name).stem
            if query not in name.casefold():
                continue
            tile = QtWidgets.QPushButton()
            tile.setCheckable(True)
            tile.setChecked(path == self.selected_path)
            tile.setFixedSize(164, 132)
            tile.setAccessibleName(name)
            tile.setToolTip(name)
            tile.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            tile.customContextMenuRequested.connect(
                lambda position, tile=tile, path=path, name=item.name:
                media_context_menu(tile, position, path, name))
            tile_layout = QtWidgets.QVBoxLayout(tile)
            tile_layout.setContentsMargins(8, 8, 8, 8)
            image = QtWidgets.QLabel()
            image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if entry_kind == 'image':
                cached = library.generate_thumbnail_path(item) if hasattr(library, 'generate_thumbnail_path') else path
                reader = QtGui.QImageReader(str(cached if cached.is_file() else path))
                reader.setAutoTransform(True)
                reader.setScaledSize(reader.size().scaled(148, 84, QtCore.Qt.AspectRatioMode.KeepAspectRatio))
                thumbnail = QtGui.QPixmap.fromImage(reader.read())
            else:
                thumbnail_path = library.generate_thumbnail_path(item)
                thumbnail = QtGui.QPixmap(str(thumbnail_path))
                if thumbnail.isNull():
                    thumbnail = UiIcons().video.pixmap(64, 64)
                thumbnail = thumbnail.scaled(148, 84, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                             QtCore.Qt.TransformationMode.SmoothTransformation)
            image.setPixmap(thumbnail)
            tile.image_label = image
            image.setFixedHeight(84)
            label = QtWidgets.QLabel(tile.fontMetrics().elidedText(name, QtCore.Qt.TextElideMode.ElideRight, 148))
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            for child in (image, label):
                child.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                tile_layout.addWidget(child)
            tile.clicked.connect(lambda checked=False, path=path: self.select_path(path))
            tile.path = path
            self.tiles.append(tile)
            visible_paths.append(path)
        if self.selected_path not in visible_paths:
            self.selected_path = None
        self.insert_button.setEnabled(self.selected_path is not None)
        self.empty.setVisible(not self.tiles)
        self.reflow()
        for tile in self.tiles:
            if tile.path == self.selected_path:
                self.scroll.ensureWidgetVisible(tile)

    def select_path(self, path):
        self.selected_path = path
        for tile in self.tiles:
            tile.setChecked(tile.path == path)
        self.insert_button.setEnabled(True)

    def thumbnail_ready(self, path):
        entry = next((entry for entry in self.entries if entry[3] == Path(path)), None)
        if not entry:
            return
        thumbnail = QtGui.QPixmap(str(entry[1].generate_thumbnail_path(entry[2])))
        if thumbnail.isNull():
            return
        for tile in self.tiles:
            if tile.path == Path(path):
                tile.image_label.setPixmap(thumbnail.scaled(148, 84, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                            QtCore.Qt.TransformationMode.SmoothTransformation))

    def reflow(self):
        columns = max(1, (self.scroll.viewport().width() - 18) // 176)
        for index, tile in enumerate(self.tiles):
            self.grid.addWidget(tile, index // columns, index % columns)

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QtCore.QEvent.Type.Resize:
            self.reflow()
        return super().eventFilter(watched, event)

    def add_files(self):
        extensions = ' '.join('*.' + extension for extension in MIME_TYPES
                              if media_kind('file.' + extension) in self.kinds)
        paths, _ = FileDialog.getOpenFileNames(self, tr('Add media'), filter=tr('Media files') + f' ({extensions})')
        selected = None
        for path in paths:
            library = next((library for kind, library in self.libraries() if kind == media_kind(path)), None)
            if library is None:
                QtWidgets.QMessageBox.warning(self, tr('Add media'),
                                              tr('Enable the corresponding library plugin first.'))
                continue
            try:
                if media_kind(path) == 'video':
                    supported, error = library.media_controller.is_media_supported(path)
                    if not supported:
                        raise ValueError(error or tr('This video could not be opened.'))
                else:
                    media_to_source(path)  # Validate the image before adding it to the library.
                # Designer media is always retained independently of the original filesystem file.
                reference = cache_media(path)
                stored = resolve_media(reference)
                existing = next((item for item in library.manager.get_all_objects(library.item_class)
                                 if item.file_hash == Path(reference).stem), None)
                if existing:
                    selected = Path(existing.file_path)
                else:
                    item = library.item_class(name=path.name, file_path=str(stored), file_hash=Path(reference).stem)
                    folder = self.folder_combo.currentData()
                    if folder and folder[0] == media_kind(path):
                        item.folder_id = folder[1]
                    if not library.manager.save_object(item):
                        raise OSError(tr('Could not add this file to the library.'))
                    library._insert_saved_items([item], getattr(item, 'folder', None))
                    if hasattr(library, '_queue_thumbnail_generation'):
                        library._queue_thumbnail_generation()
                    selected = stored
            except (OSError, ValueError) as error:
                QtWidgets.QMessageBox.warning(self, tr('Add media'), str(error))
        if selected:
            self.kind_combo.setCurrentIndex(0)
            self.folder_combo.setCurrentIndex(0)
            self.search.clear()
            self.reload(selected)

    def accept(self):
        if not self.selected_path:
            return
        entry = next((entry for entry in self.entries if entry[3] == self.selected_path), None)
        label = (entry[2].name if entry else None) or media_label(self.selected_path)
        try:
            reference = cache_media(self.selected_path)
            remember_media_label(reference, label)
            self.selected_path = resolve_media(reference)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, tr('Insert media'), str(error))
            return
        if media_kind(self.selected_path) == 'video':
            from openlp.core.lib.videoplayback import video_playback_path
            from openlp.core.ui.presentationexportdialog import ExportProgressDialog, write_with_progress
            progress = ExportProgressDialog(self)
            progress.setWindowTitle(tr('Preparing video'))
            progress.setLabelText(label)
            progress.show()
            try:
                write_with_progress(lambda update: video_playback_path(self.selected_path), progress.update_progress)
            except (OSError, ValueError, RuntimeError) as error:
                QtWidgets.QMessageBox.warning(self, tr('Preparing video'), str(error))
                return
            finally:
                progress.finish()
        super().accept()

    @classmethod
    def choose(cls, parent, kinds=('image', 'video')):
        dialog = cls(parent, kinds)
        try:
            return dialog.selected_path if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted else None
        finally:
            dialog.deleteLater()


class MediaLibraryPathEdit(PathEdit):
    """Keep the theme form's path property/signals while selecting from the library."""
    def __init__(self, parent=None, kind='image', **kwargs):
        super().__init__(parent, **kwargs)
        self.kind = kind
        self.line_edit.setReadOnly(True)
        self.browse_button.setIcon(UiIcons().blank_theme if kind == 'image' else UiIcons().video)
        self.browse_button.setToolTip(tr('Choose media'))
        self.line_edit.textChanged.connect(self._refresh_label)
        self.line_edit.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.line_edit.customContextMenuRequested.connect(
            lambda position: media_context_menu(self.line_edit, position, self.path, self.line_edit.text()))

    @QtCore.Property(Path)
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        self._path = Path(value) if value else None
        self._refresh_label()

    def _refresh_label(self, *args):
        name = media_label(self._path) if self._path else ''
        plugin = None
        if getattr(State(), 'modules', None):
            library_name = 'images' if getattr(self, 'kind', 'image') == 'image' else 'media'
            plugin = PluginManager.get_plugin_by_name(library_name)
        if self._path and plugin and plugin.is_active() and plugin.media_item:
            library = plugin.media_item
            item = next((item for item in library.manager.get_all_objects(library.item_class)
                         if Path(item.file_path) == self._path or item.file_hash == self._path.stem), None)
            if item:
                name = item.name or name
        with QtCore.QSignalBlocker(self.line_edit):
            self.line_edit.setText(name)
        self.line_edit.setToolTip(name)

    def on_line_edit_editing_finished(self):
        # The field shows a friendly library name; only the picker changes its stored path.
        pass

    def on_browse_button_clicked(self):
        path = MediaPicker.choose(self, (self.kind,))
        if path:
            self.on_new_path(path)
