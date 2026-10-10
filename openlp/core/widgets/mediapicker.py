"""Shared Fluent media library picker for the slide and theme designers."""
from pathlib import Path
from types import SimpleNamespace

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.db.mixins import FolderMixin, ItemMixin
from openlp.core.lib.designmedia import (
    MIME_TYPES, cache_media, media_kind, media_label, media_to_source, resolve_media, remember_media_label
)
from openlp.core.lib.pluginmanager import PluginManager
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.edits import PathEdit
from openlp.core.widgets.mediapreview import media_context_menu
from openlp.core.widgets.libraryview import LibraryView, LIBRARY_THUMBNAIL_ROLE
from openlp.core.widgets.fluent_tree import LIBRARY_FOLDER_ROLE
from openlp.core.widgets.views import TreeWidgetWithDnD
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
        self.folders = []
        self._connected_libraries = set()
        self.setWindowTitle(tr('Choose media'))
        self.resize(800, 600)
        self.setMinimumSize(580, 420)
        layout = QtWidgets.QVBoxLayout(self)
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
        self.settings = Registry().get('settings')
        self.plugin = SimpleNamespace(name='media_picker')
        self.item_class, self.folder_class = ItemMixin, FolderMixin
        self.list_view = TreeWidgetWithDnD(self, 'images')
        self.list_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.browser = LibraryView(self, grid_only=True)
        self.browser.grid.setBackgroundVisible(True)
        for view in (self.list_view, self.browser.grid):
            view.setDragEnabled(False)
            view.setAcceptDrops(False)
            view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self.context_menu)
        self.list_view.itemSelectionChanged.connect(self.selection_changed)
        self.list_view.doubleClicked.connect(self.on_double_clicked)
        layout.addWidget(self.browser, 1)
        self.empty = QtWidgets.QLabel(tr('No media'))
        self.empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        self.insert_button = QtWidgets.QPushButton(tr('Insert'))
        self.insert_button.setEnabled(False)
        self.insert_button.clicked.connect(self.accept)
        self.insert_button.setDefault(True)
        buttons.addWidget(self.insert_button)
        cancel = QtWidgets.QPushButton(tr('Cancel'))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
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
        self.folders = []
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
                    self.folders.append((kind, group))
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
        kind, folder = self.kind_combo.currentData(), self.folder_combo.currentData()
        query = self.search.text().casefold()
        selected_path = self.selected_path
        visible_paths = []
        with QtCore.QSignalBlocker(self.list_view):
            self.list_view.clear()
            groups = {}
            if not query and not folder:
                for entry_kind, group in self.folders:
                    if kind and kind != entry_kind:
                        continue
                    node = QtWidgets.QTreeWidgetItem([group.name])
                    node.setData(0, QtCore.Qt.ItemDataRole.UserRole, group)
                    node.setData(0, LIBRARY_FOLDER_ROLE, True)
                    node.setIcon(0, UiIcons().fluent_folder)
                    groups[(entry_kind, group.id)] = node
                for entry_kind, group in self.folders:
                    node = groups.get((entry_kind, group.id))
                    if node is None:
                        continue
                    parent = groups.get((entry_kind, group.parent_id))
                    if parent is not None:
                        parent.addChild(node)
                    else:
                        self.list_view.addTopLevelItem(node)
            for entry_kind, library, item, path in self.entries:
                if kind and kind != entry_kind or folder and folder != (entry_kind, item.folder_id):
                    continue
                name = Path(item.name or path.name).stem
                if query not in name.casefold():
                    continue
                node = QtWidgets.QTreeWidgetItem([name])
                node.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
                node.setToolTip(0, item.name or path.name)
                thumbnail_path = library.generate_thumbnail_path(item) if hasattr(library, 'generate_thumbnail_path') \
                    else path
                node.setData(0, LIBRARY_THUMBNAIL_ROLE, path if entry_kind == 'image' else thumbnail_path)
                icon = QtGui.QIcon(str(thumbnail_path))
                if icon.isNull():
                    icon = UiIcons().video if entry_kind == 'video' else QtGui.QIcon(str(path))
                node.setIcon(0, icon)
                parent = groups.get((entry_kind, item.folder_id))
                if parent is not None:
                    parent.addChild(node)
                else:
                    self.list_view.addTopLevelItem(node)
                visible_paths.append(path)
                if path == selected_path:
                    self.list_view.setCurrentItem(node)
                    node.setSelected(True)
            self.list_view.expandAll()
        self.browser.folder = QtCore.QPersistentModelIndex()
        current = self.list_view.currentItem()
        if current and self.browser.grid_button.isChecked():
            self.browser.folder = QtCore.QPersistentModelIndex(self.list_view.indexFromItem(current.parent()))
        self.selected_path = selected_path if selected_path in visible_paths else None
        self.insert_button.setEnabled(self.selected_path is not None)
        self.empty.setVisible(not visible_paths)
        self.browser.refresh()

    def selection_changed(self):
        selected = self.list_view.selectedItems()
        item = selected[0].data(0, QtCore.Qt.ItemDataRole.UserRole) if selected else None
        self.selected_path = Path(item.file_path) if isinstance(item, ItemMixin) else None
        self.insert_button.setEnabled(self.selected_path is not None)

    def select_path(self, path):
        iterator = QtWidgets.QTreeWidgetItemIterator(self.list_view)
        while iterator.value():
            node = iterator.value()
            item = node.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(item, ItemMixin) and Path(item.file_path) == path:
                self.list_view.setCurrentItem(node)
                node.setSelected(True)
                break
            iterator += 1
        self.selection_changed()

    def on_double_clicked(self, index):
        node = self.list_view.itemFromIndex(index)
        if node and isinstance(node.data(0, QtCore.Qt.ItemDataRole.UserRole), ItemMixin):
            self.select_path(Path(node.data(0, QtCore.Qt.ItemDataRole.UserRole).file_path))
            self.accept()

    def context_menu(self, position):
        view = self.sender() or self.list_view
        node = view.tree_item(view.itemAt(position)) if view is self.browser.grid else view.itemAt(position)
        item = node.data(0, QtCore.Qt.ItemDataRole.UserRole) if node else None
        if isinstance(item, ItemMixin):
            media_context_menu(view.viewport(), position, Path(item.file_path), item.name)

    def thumbnail_ready(self, path):
        entry = next((entry for entry in self.entries if entry[3] == Path(path)), None)
        if not entry:
            return
        thumbnail_path = entry[1].generate_thumbnail_path(entry[2])
        icon = QtGui.QIcon(str(thumbnail_path))
        if icon.isNull():
            return
        iterator = QtWidgets.QTreeWidgetItemIterator(self.list_view)
        while iterator.value():
            node = iterator.value()
            if node.data(0, QtCore.Qt.ItemDataRole.UserRole) is entry[2]:
                node.setIcon(0, icon)
                node.setData(0, LIBRARY_THUMBNAIL_ROLE, entry[3] if entry[0] == 'image' else thumbnail_path)
            iterator += 1

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
                    if not folder:
                        node = self.browser.folder_item() or self.list_view.currentItem()
                        if node and isinstance(node.data(0, QtCore.Qt.ItemDataRole.UserRole), ItemMixin):
                            node = node.parent()
                        if node:
                            group = node.data(0, QtCore.Qt.ItemDataRole.UserRole)
                            folder = next(((kind, group.id) for kind, candidate in self.folders if candidate is group),
                                          None)
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
