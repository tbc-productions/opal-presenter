"""A compact, asynchronous cloud browser and permission-aware Library drop target."""
import time
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from fluentqt import Breadcrumb, BreadcrumbItem

from PySide6 import QtCore, QtGui

from openlp.core.common import sha256_file_hash
from openlp.core.common.applocation import AppLocation
from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.lib.pluginmanager import PluginManager
from openlp.core.threading import run_thread
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.fluenticons import service_icon
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.dnd import ItemDragData, ThemeDragData, execute_drag
from openlp.core.widgets.docks import MediaToolBox
from openlp.core.widgets.fluent_commands import SpacedCommandBar
from openlp.core.widgets.fluent_tree import LIBRARY_FOLDER_ROLE
from openlp.core.widgets.libraryfooter import LibraryFooter
from openlp.core.widgets.toolbar import OpenLPToolbar
from openlp.core.widgets.views import DataGridWithDnD, FileTreeWidgetItem
from openlp.plugins.librarysync.lib.cache import CloudCache
from openlp.plugins.librarysync.lib.connectionwizard import ConnectionWizard
from openlp.plugins.librarysync.lib.profile import (
    deserialize_profile, read_profile, serialize_profile, validate_profile, write_profile)
from openlp.plugins.librarysync.lib.provider import CATEGORIES, SyncError, preview_url_allowed
from openlp.plugins.librarysync.lib.transfer import (
    EXTENSION_CATEGORIES, duplicate_key, import_item, item_category, local_item, prepare_upload,
    read_theme_item, read_xml_item, safe_name,
    write_upload)
from openlp.plugins.librarysync.lib.preview import format_local_time, show_preview
from openlp.plugins.librarysync.lib.stream import MediaStream
from openlp.plugins.librarysync.lib.worker import SyncWorker


def tr(text):
    return translate('LibrarySync', text)


class CloudDragData(QtCore.QMimeData):
    def __init__(self, panel, items):
        super().__init__()
        self.panel, self.items = panel, tuple(items)
        self.title, self.icon, self.indexes = items[0].display_name, UiIcons().cloud_library, list(items)
        self.setData('application/x-openlp-cloud-items', b'1')

    def can_import(self, library):
        category = 'themes' if hasattr(library, 'theme_list_widget') else library.plugin.name
        return bool(self.items) and all(not item.folder and item.can_download
                                        and item_category(item) == category for item in self.items)


class CloudTree(DataGridWithDnD):
    def __init__(self, panel, category):
        super().__init__(panel, 'librarysync')
        self.panel = panel
        self.size_column = 2 if category in EXTENSION_CATEGORIES else 1
        self.setup_columns([tr('Name')] + ([tr('File Type')] if self.size_column == 2 else []) +
                           [tr('Size'), tr('Updated')])
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setFont(QtWidgets.fluentqt.font_for_role(QtWidgets.fluentqt.FontRole.Body))
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setAccessibleName(tr('Cloud Library items'))
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(panel.context_menu)

    def startDrag(self, actions):
        items = self.panel.selected_items()
        if items and all(not item.folder and item.can_download and item_category(item) for item in items):
            execute_drag(self, CloudDragData(self.panel, items))

    def dragEnterEvent(self, event):
        if self.panel.can_upload(event.mimeData(), self.drop_folder(event)):
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self.panel.can_upload(event.mimeData(), self.drop_folder(event)):
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def drop_folder(self, event):
        row = self.itemAt(event.position().toPoint())
        item = row.data(0, QtCore.Qt.ItemDataRole.UserRole) if row else None
        return item if item and item.folder else self.panel.folder

    def dropEvent(self, event):
        folder = self.drop_folder(event)
        if self.panel.can_upload(event.mimeData(), folder):
            self.panel.upload(event.mimeData(), folder)
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()


class CloudLibrary(QtWidgets.QWidget):
    """Only the selected folder/page and selected preview generate network traffic."""
    def __init__(self, plugin, parent):
        super().__init__(parent)
        self.plugin = plugin
        self.profile = None
        self.connected = False
        self.folder = None
        self.history = []
        self.page_token = ''
        self.jobs = {}
        self.cache = {}
        self.cached_listing = False
        self.cache_checked = True
        self.out_of_date = False
        self.last_auto_refresh = None
        self.change_token = ''
        self.generation = 0
        self.category = next(iter(CATEGORIES))
        self.preview_windows = set()
        self.pending_view = None
        self.drop_views = {}
        self.imported = set()
        self.closing = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.import_info = QtWidgets.fluentqt.InfoBar(self)
        info_policy = self.import_info.sizePolicy()
        info_policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Policy.Expanding)
        self.import_info.setSizePolicy(info_policy)
        self.import_info.setMessage(tr('Import your organisation’s connection file.'))
        self.import_info.setIsClosable(False)
        self.import_button = QtWidgets.fluentqt.HyperlinkButton(tr('Import connection'), self.import_info)
        self.import_button.clicked.connect(self.import_connection)
        self.import_info.setActionWidget(self.import_button)
        layout.addWidget(self.import_info)
        self.roots = QtWidgets.QComboBox(self)
        self.roots.setAccessibleName(tr('Shared cloud folder'))
        self.roots.setMinimumWidth(180)
        self.roots.setMaximumWidth(360)
        self.sections = MediaToolBox(self)
        self.type_icons = {'songs': UiIcons().music, 'images': UiIcons().picture, 'custom': UiIcons().custom,
                           'media': UiIcons().media, 'presentations': UiIcons().presentation, 'themes': UiIcons().theme}
        self.trees = {}
        for category, label in CATEGORIES.items():
            tree = CloudTree(self, category)
            tree.itemDoubleClicked.connect(self.activate_item)
            tree.itemSelectionChanged.connect(self.selection_changed)
            self.trees[category] = tree
            self.sections.addItem(tree, service_icon(self.type_icons[category], category), tr(label))
        self.tree = self.sections.currentWidget()
        self.sections.currentChanged.connect(self.change_type)
        layout.addWidget(self.sections, 1)
        self.toolbar = OpenLPToolbar(self)
        self.toolbar.addWidget(self.roots)
        self.connect_action = QtGui.QAction(UiIcons().cloud_arrow_right, tr('Connect'), self)
        self.connect_action.triggered.connect(self.connect_drive)
        self.toolbar.add_pinned_action(self.connect_action)
        self.refresh_action = self.toolbar.addAction(UiIcons().refresh, tr('Refresh'), self.refresh)
        self.download_action = self.toolbar.addAction(UiIcons().download, tr('Add to Library'), self.download_selected)
        self.preview_action = self.toolbar.addAction(UiIcons().eye, tr('View'), self.open_preview)
        self.settings_action = self.toolbar.addAction(UiIcons().settings, tr('Connection'), self.configure)
        self.rename_action = QtGui.QAction(UiIcons().edit, tr('Rename'), self)
        self.rename_action.triggered.connect(self.rename_selected)
        self.delete_action = QtGui.QAction(UiIcons().delete, tr('Delete'), self)
        self.delete_action.triggered.connect(self.delete_selected)
        controls = QtWidgets.QWidget(self)
        controls_layout = QtWidgets.QVBoxLayout(controls)
        controls_layout.setContentsMargins(8, 8, 8, 8)
        controls_layout.setSpacing(0)
        controls_layout.addWidget(self.toolbar)
        self.navigation = QtWidgets.QWidget(controls)
        navigation_layout = QtWidgets.QHBoxLayout(self.navigation)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(8)
        self.navigation_commands = SpacedCommandBar(self.navigation)
        self.navigation_commands.setBackgroundVisible(False)
        self.navigation_commands.setDynamicOverflowEnabled(False)
        self.navigation_commands.setLabelPosition(QtWidgets.fluentqt.CommandBar.LabelPosition.Collapsed)
        self.navigation_commands.setFixedHeight(QtWidgets.fluentqt.Spacing.ControlHeight.Large)
        self.navigation_commands.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum,
                                               QtWidgets.QSizePolicy.Policy.Fixed)
        self.up_action = QtGui.QAction(UiIcons().arrow_turn_left_up, tr('Up'), self)
        self.up_action.triggered.connect(self.go_up)
        self.folder_action = QtGui.QAction(UiIcons().folder_plus, tr('New folder'), self)
        self.folder_action.triggered.connect(self.create_folder)
        self.navigation_commands.addPrimaryAction(self.folder_action)
        self.navigation_commands.addPrimaryAction(self.up_action)
        navigation_layout.addWidget(self.navigation_commands)
        self.breadcrumbs = Breadcrumb(self.navigation)
        self.breadcrumbs.setAutoTruncateOnItemClick(False)
        self.breadcrumbs.setOverflowMode(Breadcrumb.OverflowMode.Middle)
        self.breadcrumbs.itemActivated.connect(self.activate_breadcrumb)
        navigation_layout.addWidget(self.breadcrumbs, 1)
        controls_layout.addWidget(self.navigation)
        controls_layout.addSpacing(8)
        self.search = QtWidgets.QLineEdit(self)
        self.search.setMinimumHeight(QtWidgets.fluentqt.Spacing.ControlHeight.Large)
        search_icon = self.search.addAction(UiIcons().search, QtWidgets.QLineEdit.ActionPosition.LeadingPosition)
        search_icon.setEnabled(False)
        self.search.setPlaceholderText(tr('Filter this folder…'))
        self.search.setAccessibleName(tr('Filter loaded cloud items'))
        self.search.textChanged.connect(self.filter_items)
        controls_layout.addWidget(self.search)
        self.sections.layout().insertWidget(1, controls)
        self.more_button = QtWidgets.QPushButton(tr('Load more'), self)
        self.more_button.clicked.connect(self.load_more)
        self.more_button.hide()
        layout.addWidget(self.more_button)
        self.status = QtWidgets.QLabel(tr('Not connected'), self)
        self.status.setFluentTypography(QtWidgets.fluentqt.FontRole.Caption)
        self.status.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.status.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.status.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        self.footer = LibraryFooter(self)
        self.footer.layout().setStretch(0, 0)
        self.transfer_progress = QtWidgets.QWidget(self.footer)
        self.transfer_progress.setMaximumWidth(360)
        progress_layout = QtWidgets.QHBoxLayout(self.transfer_progress)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        self.progress = QtWidgets.QProgressBar(self, compact=True)
        self.progress.setRange(0, 0)
        self.progress.setMinimumWidth(80)
        self.progress.setAccessibleName(tr('Transfer progress'))
        self.progress.hide()
        progress_layout.addWidget(self.progress, 1)
        self.cancel_button = QtWidgets.QPushButton(tr('Cancel'), self)
        self.cancel_button.setFluentSize(QtWidgets.fluentqt.Button.ButtonSize.Small)
        self.cancel_button.setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Subtle)
        self.cancel_button.clicked.connect(self.cancel_transfer)
        self.cancel_button.hide()
        progress_layout.addWidget(self.cancel_button)
        self.footer.layout().addWidget(self.transfer_progress, 1)
        self.footer.layout().addWidget(self.status, 1)
        self.refresh_button = QtWidgets.QPushButton(tr('Refresh'), self.footer)
        self.refresh_button.setIcon(UiIcons().refresh)
        self.refresh_button.setFluentSize(QtWidgets.fluentqt.Button.ButtonSize.Small)
        self.refresh_button.setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Subtle)
        self.refresh_button.clicked.connect(self.refresh)
        self.refresh_button.hide()
        self.footer.layout().addWidget(self.refresh_button)
        layout.addWidget(self.footer)
        self.roots.currentIndexChanged.connect(self.change_root)
        self.change_timer = QtCore.QTimer(self)
        self.change_timer.setInterval(10000)
        self.change_timer.timeout.connect(self.poll_changes)
        self.auto_refresh_timer = QtCore.QTimer(self)
        self.auto_refresh_timer.setSingleShot(True)
        self.auto_refresh_timer.timeout.connect(self.auto_refresh)
        self._status_theme = QtWidgets.fluentqt.FluentWidget(self)
        self._status_theme.hide()
        self.update_actions()

    def set_status(self, text, detail='', *, error=False):
        if self.out_of_date:
            detail = '\n'.join(part for part in (text, detail) if part)
            text = tr('Out of date')
        elif self.cached_listing:
            text = tr('Cached · {status}').format(status=text)
        color = self._status_theme.theme_tokens().colors.systemCritical if self.out_of_date or error else None
        self.status.setStyleSheet('color: ' + color.name() + ';' if color is not None else '')
        self.status.setText(text)
        self.refresh_button.setVisible(self.out_of_date)
        self.status.setToolTip(text + '\n' + detail if detail else text)

    def set_ready_status(self):
        self.set_status(tr('Drag-and-drop items to upload') if self.folder and self.folder.can_upload else
                        tr('Read-only') if self.folder else tr('Ready'))

    def startup(self):
        raw = self.plugin.settings.value('librarysync/profile')
        if raw:
            try:
                self.set_profile(deserialize_profile(raw))
                self.browse()
            except (SyncError, ValueError) as error:
                self.set_status(str(error), error=True)
        self.install_drop_targets()

    def set_profile(self, profile, save=True):
        self.auto_refresh_timer.stop()
        self.pending_view = None
        self.profile = validate_profile(profile)
        self.connected = False
        self.out_of_date = False
        self.cache_checked = True
        self.change_token = ''
        self.cached_listing = False
        self.generation += 1
        self.cache.clear()
        self.folder, self.history, self.page_token = None, [], ''
        for tree in self.trees.values():
            tree.clear()
        with QtCore.QSignalBlocker(self.roots):
            self.roots.clear()
            for folder in self.profile['folders']:
                self.roots.addItem(folder['name'], folder)
        if save:
            self.plugin.settings.setValue('librarysync/profile', serialize_profile(self.profile))
            self.plugin.settings.sync()
        self.update_breadcrumbs()
        self.update_actions()

    def configure(self):
        if self.jobs:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction(UiIcons().arrow_import, tr('Import connection…'), self.import_connection)
        export = menu.addAction(UiIcons().arrow_export, tr('Export connection…'), self.export_connection)
        export.setEnabled(bool(self.profile) and self.connected)
        menu.addSeparator()
        menu.addAction(UiIcons().plus, tr('Set up connection…'), self.setup_connection)
        disconnect = menu.addAction(UiIcons().plug_disconnected, tr('Disconnect…'), self.disconnect)
        disconnect.setEnabled(bool(self.profile) and self.connected)
        menu.exec(QtGui.QCursor.pos())

    def import_connection(self):
        path, _ = FileDialog.getOpenFileName(
            self, tr('Import Library Sync connection'), filter=tr('Library Sync connection (*.json)'))
        if path:
            try:
                self.set_profile(read_profile(path))
                self.set_status(tr('Connection imported'))
            except (OSError, SyncError) as error:
                self.set_status(str(error), error=True)

    def setup_connection(self):
        wizard = ConnectionWizard(self, existing_names=[self.profile['name']] if self.profile else [])
        if wizard.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.set_profile(wizard.profile)
            self.set_status(tr('Connection saved'))

    def export_connection(self):
        if not self.profile or not self.connected:
            return
        path, _ = FileDialog.getSaveFileName(
            self, tr('Export Library Sync connection'),
            Path('organisation-library.librarysync.json'), tr('Connection file (*.json)'))
        if path:
            try:
                write_profile(path, self.profile)
                self.set_status(tr('Connection exported'))
            except (OSError, SyncError) as error:
                self.set_status(str(error), error=True)

    def connect_drive(self):
        if not self.profile:
            self.import_connection()
            if not self.profile:
                return
        if self.jobs:
            return
        self.cache.clear()
        self.cached_listing = False
        self.out_of_date = False
        self.change_token = ''
        self.folder, self.history, self.page_token = None, [], ''
        self.footer.set_count(0)
        self.update_breadcrumbs()
        for window in list(self.preview_windows):
            window.reject()
        for tree in self.trees.values():
            tree.clear()
        self.set_status(tr('Sign in in your browser…'))
        self.start_job('connect', lambda provider, cancel, progress, browser, publish:
                       provider.sign_in(cancel, browser))

    def disconnect(self):
        if not self.profile or not self.connected or self.jobs:
            return
        dialog = QtWidgets.ContentDialog(self.window())
        dialog.setTitle(tr('Disconnect connection?'))
        message = QtWidgets.QLabel(tr('Disconnect “{name}”? Previews will close and the local cache will be cleared. '
                                      'Your library files will be kept.').format(name=self.profile['name']))
        message.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        message.setFluentTypography(QtWidgets.fluentqt.FontRole.Body)
        message.setWordWrap(True)
        dialog.setContent(message)
        dialog.setMinimumWidth(420)
        dialog.setPrimaryButtonText(tr('Disconnect'))
        dialog.setCloseButtonText(tr('Cancel'))
        dialog.setDefaultButton(QtWidgets.fluentqt.ContentDialogButton.Close)
        try:
            if dialog.exec() != dialog.ResultPrimary:
                return
        finally:
            dialog.deleteLater()
        profile = self.profile

        def operation(provider, *args):
            cache = CloudCache(profile, provider.cache_account())
            provider.disconnect()
            cache.clear()
        self.start_job('disconnect', operation)

    def start_job(self, kind, operation, context=None):
        if self.closing or not self.profile:
            return
        job_id = uuid4().hex
        profile = self.profile
        if kind in ('upload', 'copy', 'folder', 'rename', 'delete', 'connect', 'disconnect'):
            for job in self.jobs.values():
                if job['kind'] == 'changes' and job.get('worker'):
                    job['worker'].stop()
        if kind in ('upload', 'copy', 'folder', 'rename', 'delete'):
            mutate = operation

            def operation(provider, *args):
                try:
                    return mutate(provider, *args)
                finally:
                    CloudCache(profile, provider.cache_account()).clear_listings()
        if kind not in ('browse', 'changes'):
            self.progress.setRange(0, 0)
            self.progress.setValue(0)
        worker = SyncWorker(job_id, profile, operation)
        self.jobs[job_id] = {'worker': worker, 'kind': kind, 'context': context, 'generation': self.generation}
        run_thread(worker, 'librarysync-' + job_id, queued_connections=[
            (worker.ready, self.job_ready), (worker.failed, self.job_failed), (worker.completed, self.job_completed),
            (worker.progress, self.job_progress), (worker.browser, self.open_browser)])
        self.update_actions()

    @QtCore.Slot(str)
    def open_browser(self, url):
        if QtCore.QUrl(url).scheme() == 'https':
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    @QtCore.Slot(str, object)
    def job_ready(self, job_id, value):
        job = self.jobs.get(job_id)
        if (self.closing or not job or job['generation'] != self.generation
                or job.get('worker') and job['worker'].cancel.is_set()):
            return
        if job['kind'] == 'browse':
            self.cached_listing = len(value) > 3 and value[3]
            self.cache_checked = not self.cached_listing
            self.change_token, self.out_of_date = value[4] if len(value) > 4 else ('', False)
            job['background'] = self.cached_listing
            if not self.cached_listing:
                self.connected = True
            else:
                job['cached'] = True
            selected_ids = {item.id for item in self.selected_items()}
            folder, items, token = value[:3]
            self.folder, self.page_token = folder, token
            if not job['context']:
                self.tree.clear()
            for item in items:
                if item.folder:
                    if (self.category in ('songs', 'custom') or not folder.category
                            or item.category not in ('', self.category)):
                        continue
                    item = replace(item, category=self.category)
                    access = tr('View, edit') if item.can_upload else tr('View')
                else:
                    if item_category(item) != self.category:
                        continue
                    access = tr('View, edit') if item.can_edit else tr('View')
                modified = QtCore.QDateTime.fromString(item.modified, QtCore.Qt.DateFormat.ISODate)
                updated = format_local_time(item.modified)
                values = [item.display_name]
                if self.tree.size_column == 2:
                    values.append(tr('Folder') if item.folder else Path(item.name).suffix.lstrip('.').upper() or '—')
                row = FileTreeWidgetItem(values + ['—' if item.folder else self.format_size(item.size), updated])
                row.set_sort_data(self.tree.size_column, item.size)
                row.set_sort_data(self.tree.size_column + 1, modified.toMSecsSinceEpoch() if modified.isValid() else 0)
                row.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
                row.setData(0, LIBRARY_FOLDER_ROLE, item.folder)
                row.setIcon(0, UiIcons().folder if item.folder else service_icon(
                    self.type_icons[self.category], self.category))
                row.setToolTip(0, '\n'.join([item.display_name, access] + (
                    [self.format_size(item.size)] if not item.folder else [])))
                self.tree.addTopLevelItem(row)
                row.setSelected(item.id in selected_ids)
            if not job['context'] and not self.cached_listing:
                self.cache[(self.category, folder.id)] = (time.monotonic(), value)
                if not self.history:
                    self.cache[(self.category, self.roots.currentData()['id'])] = (time.monotonic(), value)
            self.update_breadcrumbs()
            self.set_status(tr('Checking for updates…') if self.cached_listing else
                            tr('Drag-and-drop items to upload') if folder.can_upload else
                            tr('Read-only'))
            self.filter_items(self.search.text())
            self.more_button.setVisible(bool(token))
            self.footer.set_count(self.tree.topLevelItemCount())
        elif job['kind'] == 'changes':
            self.connected = True
            self.change_token, changed = value
            self.cache_checked = True
            if changed:
                self.out_of_date = True
                self.cache.clear()
                self.set_status('')
            elif not self.out_of_date:
                self.set_status(tr('Up to date'))
        elif job['kind'] == 'preview':
            item, path, prepared = value[:3]
            try:
                window = show_preview(self.window(), item, path, prepared)
                self.add_preview_commands(window, item)
                self.preview_windows.add(window)
                window.finished.connect(lambda: self.release_preview(window, job['context']))
                window.finished.connect(job['worker'].stop)
                window.show()
                job['context'].preview_window = window
                self.set_ready_status()
            except Exception:
                self.set_status(tr('Couldn’t open item'), error=True)
        elif job['kind'] == 'download':
            job.setdefault('downloads', []).append(value)
        elif job['kind'] in ('upload', 'copy'):
            self.cache.clear()
            self.set_status(tr('Uploaded 1 item') if value == 1 else tr('Uploaded {count} items').format(count=value))
        elif job['kind'] == 'prepare-upload':
            job['candidates'] = value
        elif job['kind'] in ('rename', 'delete'):
            self.cache.clear()
            self.set_status(tr('Item renamed') if job['kind'] == 'rename' else tr('Moved to bin'))
        elif job['kind'] == 'folder':
            self.cache.clear()
            self.set_status(tr('Folder created'), detail=value.display_name)
        self.update_actions()

    def apply_download(self, value, context):
        item, path, prepared = value
        category = item_category(item)
        plugin = PluginManager.get_plugin_by_name(category) if category != 'themes' else None
        target = None
        index = context.get('target') if context else None
        if index and index.isValid() and plugin and plugin.media_item:
            target = plugin.media_item.list_view.itemFromIndex(QtCore.QModelIndex(index))
        try:
            overwrite = context['overwrites'].get(item.id) if context else None
            if category in ('songs', 'custom') and not item.title:
                root = prepared[0]
                title = root.findtext('{http://openlyrics.info/namespace/2009/song}properties/'
                                      '{http://openlyrics.info/namespace/2009/song}titles/'
                                      '{http://openlyrics.info/namespace/2009/song}title') if category == 'songs' else \
                    root.findtext('title')
                if title:
                    item = replace(item, title=title)
            existing = local_item(category, plugin, item.display_name, Path(item.name).suffix)
            if existing is not None and overwrite is None:
                if not self.confirm_overwrite(item.display_name, tr('local Library')):
                    self.set_status(tr('Download skipped'))
                    return
                overwrite = existing if category == 'themes' else existing.id
            import_item(item, path, plugin, target, prepared=prepared, overwrite=overwrite)
            self.imported.add((item.id, item.version))
            self.set_status(tr('Downloaded {name}').format(name=item.display_name))
            if plugin and plugin.media_item:
                toolbox = self.plugin.main_window.media_tool_box
                for index in range(toolbox.count()):
                    if toolbox.widget(index) is plugin.media_item:
                        toolbox.setCurrentIndex(index)
                        break
        except Exception as error:
            self.set_status(tr('Download failed'),
                            detail=str(error) if isinstance(error, SyncError) else '', error=True)

    @QtCore.Slot(str, str)
    def job_failed(self, job_id, message):
        job = self.jobs.get(job_id)
        if not self.closing and job and job['generation'] == self.generation:
            job['failed'] = True
            context = job.get('context')
            if (job['kind'] == 'preview' and getattr(context, 'view_id', None)
                    and not context.refreshed and not hasattr(context, 'preview_window')):
                job['retry_view'] = context.view_id
                return
            if job['kind'] in ('browse', 'connect'):
                self.connected = False
            self.set_status(tr('Couldn’t check for updates') if job['kind'] == 'changes' else
                            tr('Refresh failed') if job.get('cached') else message, detail=message
                            if job['kind'] == 'changes' or job.get('cached') else '', error=True)

    @QtCore.Slot(str)
    def job_completed(self, job_id):
        job = self.jobs.pop(job_id, None)
        if job and job['kind'] in ('upload', 'copy', 'folder', 'rename', 'delete'):
            self.cache.clear()
        if job and job['kind'] == 'browse' and job['generation'] != self.generation:
            self.update_actions()
            return
        if job and job['kind'] == 'preview' and not hasattr(job['context'], 'preview_window'):
            job['context'].cleanup()
        if job and job['kind'] == 'prepare-upload':
            accepted = []
            if (job.get('candidates') and not self.closing and not job.get('failed')
                    and not (job.get('worker') and job['worker'].cancel.is_set())):
                for source, existing in job['candidates']:
                    title = source.display_name if job['context']['copy'] else source[3]
                    if existing is not None:
                        if job['context']['copy'] and not source.can_delete:
                            self.set_status(tr('You don’t have permission to move {name}').format(
                                name=title), error=True)
                            continue
                        if not existing.can_edit or existing.folder:
                            self.set_status(tr('{name} is read-only').format(name=title), error=True)
                            continue
                        if not self.confirm_overwrite(title, tr('Cloud Library')):
                            continue
                    accepted.append((source, existing))
            if accepted and not self.closing and not (job.get('worker') and job['worker'].cancel.is_set()):
                self.run_upload(job['context'], accepted)
            else:
                job['context']['temporary'].cleanup()
                if job['context'].get('switched') and not self.closing:
                    self.browse()
        elif job and job['kind'] == 'download' and not self.closing:
            for value in job.get('downloads', []):
                self.apply_download(value, job['context'])
        elif job and job['kind'] in ('upload', 'copy') and job.get('context'):
            job['context']['temporary'].cleanup()
        if self.closing or not job:
            return
        cancelled = job.get('worker') and job['worker'].cancel.is_set()
        if job.get('retry_view') and not cancelled:
            self.pending_view = job['retry_view']
            self.refresh()
        elif job['kind'] == 'browse' and self.pending_view:
            item_id = self.pending_view
            row = next((self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())
                        if self.tree.topLevelItem(index).data(0, QtCore.Qt.ItemDataRole.UserRole).id == item_id), None)
            if not job.get('failed') and not cancelled and not self.out_of_date and row is None and self.page_token:
                self.load_more()
            else:
                self.pending_view = None
                if not job.get('failed') and not cancelled and not self.out_of_date and row is not None:
                    self.tree.clearSelection()
                    self.tree.setCurrentItem(row)
                    self.open_preview(refreshed=True)
                elif not job.get('failed') and not cancelled:
                    self.set_status(tr('Couldn’t open item'), error=True)
        if job['kind'] == 'preview' and cancelled:
            if hasattr(job['context'], 'preview_window'):
                self.set_ready_status()
            else:
                self.set_status(tr('Cancelled'))
        elif job['kind'] in ('connect', 'upload', 'download', 'copy', 'folder') and cancelled:
            self.set_status(tr('Cancelled'), detail=tr('Completed copies are kept.')
                            if job['kind'] != 'connect' else '')
        if job['kind'] == 'connect' and not job.get('failed') and not cancelled:
            self.refresh()
        elif (job['kind'] in ('upload', 'copy', 'folder', 'rename', 'delete')
              and not job.get('failed') and not cancelled):
            self.cache.clear()
            if job['kind'] == 'delete':
                self.set_status(tr('Moved to bin'))
            self.refresh()
        elif job['kind'] == 'disconnect' and not job.get('failed'):
            self.connected = False
            self.folder = None
            for tree in self.trees.values():
                tree.clear()
            for window in list(self.preview_windows):
                window.reject()
            self.cache.clear()
            self.cached_listing = False
            self.out_of_date = False
            self.change_token = ''
            self.set_status(tr('Disconnected'))
        self.update_actions()
        if job['kind'] == 'browse' and self.cached_listing:
            QtCore.QTimer.singleShot(0, self, self.poll_changes)
        if not job.get('failed') and not cancelled:
            self.schedule_auto_refresh()

    @QtCore.Slot(str, str, object, object)
    def job_progress(self, job_id, name, current, total):
        job = self.jobs.get(job_id)
        if job and job['generation'] == self.generation and not self.closing:
            self.set_status(name)
            self.progress.setRange(0, 100 if total else 0)
            if total:
                self.progress.setValue(int(current * 100 / total))

    @staticmethod
    def format_size(size):
        return f'{size / (1024 * 1024):.1f} MB' if size >= 1024 * 1024 else f'{size / 1024:.0f} KB'

    def busy(self):
        return any(job['kind'] in ('connect', 'download', 'upload', 'disconnect', 'preview', 'folder', 'copy',
                                   'prepare-upload', 'rename', 'delete')
                   and not (job['kind'] == 'preview' and getattr(job.get('context'), 'preview_window', None))
                   for job in self.jobs.values())

    def update_actions(self):
        browsing = any(job['kind'] == 'browse' and not job.get('background') for job in self.jobs.values())
        busy = self.busy()
        read_only = self.out_of_date or self.cached_listing and not self.cache_checked
        selected = self.selected_items() if hasattr(self, 'tree') else []
        self.import_info.setVisible(not self.profile)
        self.navigation.setVisible(bool(self.profile))
        self.connect_action.setEnabled(bool(self.profile) and not self.jobs)
        self.connect_action.setText(tr('Reconnect') if self.connected else tr('Connect'))
        self.connect_action.setIcon(UiIcons().library_sync if self.connected else UiIcons().cloud_arrow_right)
        self.connect_action.setToolTip(self.connect_action.text())
        self.settings_action.setEnabled(not self.jobs)
        self.roots.setEnabled(bool(self.roots.count()) and not busy and not browsing)
        self.sections.setEnabled(not busy and not browsing)
        self.up_action.setEnabled(bool(self.history) and not busy and not browsing)
        self.refresh_action.setEnabled(bool(self.profile) and not busy and not browsing)
        self.refresh_button.setEnabled(self.refresh_action.isEnabled())
        self.refresh_button.setVisible(self.out_of_date)
        self.more_button.setEnabled(not busy and not browsing)
        self.download_action.setEnabled(bool(selected) and not busy and all(
            not item.folder and item.can_download and item_category(item) for item in selected))
        self.preview_action.setEnabled(len(selected) == 1 and not selected[0].folder and not busy and (
            selected[0].can_download or preview_url_allowed(selected[0].preview_url)))
        self.folder_action.setEnabled(bool(self.folder and self.folder.can_upload
                                           and self.folder.category in ('', self.category))
                                      and self.category not in ('songs', 'custom') and not busy and not browsing
                                      and not read_only)
        self.rename_action.setEnabled(len(selected) == 1 and selected[0].can_edit and not busy
                                      and not read_only)
        self.delete_action.setEnabled(bool(selected) and all(item.can_edit and item.can_delete for item in selected)
                                      and not busy and not read_only)
        for window in self.preview_windows:
            available = self.profile == window.cloud_profile and not busy and not browsing
            item = window.cloud_item
            window.cloud_commands['download'].setEnabled(available and item.can_download)
            window.cloud_commands['rename'].setEnabled(available and item.can_edit and not read_only)
            window.cloud_commands['delete'].setEnabled(available and item.can_edit and item.can_delete
                                                       and not read_only)
        self.transfer_progress.setVisible(busy)
        self.progress.setVisible(busy)
        self.cancel_button.setVisible(busy)
        if not busy:
            self.progress.setValue(0)

    def selected_items(self):
        return [row.data(0, QtCore.Qt.ItemDataRole.UserRole) for row in self.tree.selectedItems()]

    def filter_items(self, text):
        for index in range(self.tree.topLevelItemCount()):
            row = self.tree.topLevelItem(index)
            row.setHidden(text.casefold() not in row.text(0).casefold())

    def change_root(self, index):
        if not self.profile or self.busy():
            return
        self.folder, self.history = None, []
        self.generation += 1
        self.browse()

    def change_type(self, index, *, browse=True):
        self.category = list(CATEGORIES)[index]
        self.tree = self.sections.widget(index)
        self.folder, self.history, self.page_token = None, [], ''
        self.tree.clear()
        self.search.clear()
        self.more_button.hide()
        self.footer.set_count(0)
        self.generation += 1
        self.update_breadcrumbs()
        if browse:
            self.browse()

    def update_breadcrumbs(self):
        crumbs = [BreadcrumbItem(tr(CATEGORIES[self.category]), None)]
        for position, folder in enumerate(self.history[1:] + ([self.folder] if self.history else [])):
            crumbs.append(BreadcrumbItem(folder.display_name, position + 1))
        self.breadcrumbs.setItems(crumbs)

    def activate_breadcrumb(self, index, item):
        if self.busy() or any(job['kind'] == 'browse' and not job.get('background')
                              for job in self.jobs.values()):
            return
        depth = item.data
        folder = (self.history[depth] if depth is not None and depth < len(self.history) else
                  self.folder if depth is not None else None)
        self.history = self.history[:depth] if depth is not None else []
        self.search.clear()
        self.browse(folder)

    def browse(self, folder=None, page_token='', force=False):
        browsing = any(job['kind'] == 'browse' and not job.get('background') for job in self.jobs.values())
        if not self.profile or self.busy() or browsing:
            return
        root = self.roots.currentData()
        if not root:
            return
        for job in self.jobs.values():
            if job['kind'] in ('browse', 'changes') and job.get('worker'):
                job['worker'].stop()
        self.generation += 1
        self.cancel_previews()
        cached = self.cache.get((self.category, folder.id if folder else root['id']))
        if cached and not force and not page_token and time.monotonic() - cached[0] < 60:
            job_id = uuid4().hex
            self.jobs[job_id] = {'kind': 'browse', 'context': False, 'generation': self.generation}
            self.job_ready(job_id, cached[1])
            self.jobs.pop(job_id)
            self.update_actions()
            return
        self.set_status(tr('Loading…'))
        category, profile = self.category, self.profile
        previous_cursor, previous_outdated = self.change_token, self.out_of_date

        def operation(provider, cancel, progress, browser, publish):
            cache = CloudCache(profile, provider.cache_account())
            key = folder.id if folder else root['id']
            if not force and not page_token:
                snapshot = cache.listing(category, key)
                if snapshot is not None and not cancel.is_set():
                    current, items, token, cursor, outdated = snapshot
                    if cursor:
                        return current, items, token, True, (cursor, outdated)
                    publish((current, items, token, True, ('', outdated)))
            cursor = previous_cursor if page_token else provider.change_token()
            outdated = previous_outdated if page_token else False
            if not isinstance(cursor, str):
                cursor = ''
            current = folder
            if current is not None and not page_token:
                current = replace(provider.folder(current.id, current.resource_key), category=current.category)
            if current is None or not current.category:
                shared = current or provider.folder(root['id'], root['resource_key'])
                current = provider.type_folder(shared, category, create=False) or shared
            items, token = provider.list_folder(current, page_token)
            if not cancel.is_set() and not page_token:
                cache.save_listing(category, key, (current, items, token), cursor)
                cache.save_listing(category, current.id, (current, items, token), cursor)
            return current, items, token, False, (cursor, outdated)
        self.start_job('browse', operation, bool(page_token))

    def showEvent(self, event):
        super().showEvent(event)
        self.change_timer.start()
        self.schedule_auto_refresh()
        QtCore.QTimer.singleShot(0, self, self.poll_changes)

    def hideEvent(self, event):
        self.change_timer.stop()
        self.auto_refresh_timer.stop()
        for job in self.jobs.values():
            if job['kind'] == 'changes' and job.get('worker'):
                job['worker'].stop()
        super().hideEvent(event)

    def poll_changes(self):
        if (self.closing or not self.isVisible() or self.window().isMinimized() or not self.profile
                or not self.folder or not self.change_token or self.busy()
                or any(job['kind'] in ('browse', 'changes') for job in self.jobs.values())):
            return
        category, profile, folder, cursor = self.category, self.profile, self.folder, self.change_token
        items = [self.tree.topLevelItem(index).data(0, QtCore.Qt.ItemDataRole.UserRole)
                 for index in range(self.tree.topLevelItemCount())]
        parents = {folder.id, self.roots.currentData()['id'], *(ancestor.id for ancestor in self.history)}
        watched = parents | {item.id for item in items}
        token, outdated = self.page_token, self.out_of_date
        keys = {folder.id, self.roots.currentData()['id']} if not self.history else {folder.id}

        def operation(provider, cancel, *args):
            changes, next_token = provider.changes(cursor)
            changed = outdated or any(
                (change.all_items and (not change.drive_id or change.drive_id == folder.drive_id))
                or change.id in watched or parents.intersection(change.parents) for change in changes)
            cache = CloudCache(profile, provider.cache_account())
            for key in keys:
                if not cancel.is_set():
                    cache.save_listing(category, key, (folder, items, token), next_token, changed)
            return next_token, changed
        self.start_job('changes', operation)

    def schedule_auto_refresh(self):
        self.auto_refresh_timer.stop()
        if (self.closing or not self.out_of_date or not self.isVisible() or self.window().isMinimized()
                or not self.profile or not self.folder or self.busy()
                or any(job['kind'] in ('browse', 'changes') for job in self.jobs.values())):
            return
        delay = max(0, 10 - (time.monotonic() - self.last_auto_refresh)) if self.last_auto_refresh is not None else 0
        self.auto_refresh_timer.start(int(delay * 1000 + 0.999))
        return delay == 0

    def auto_refresh(self):
        if self.schedule_auto_refresh():
            self.last_auto_refresh = time.monotonic()
            self.refresh()

    def refresh(self):
        self.auto_refresh_timer.stop()
        self.browse(self.folder, force=True)

    def load_more(self):
        if self.page_token:
            self.browse(self.folder, self.page_token, force=True)

    def activate_item(self, row, column=0):
        item = row.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if (item.folder and self.folder and not self.busy()
                and not any(job['kind'] == 'browse' and not job.get('background') for job in self.jobs.values())):
            self.history.append(self.folder)
            self.search.clear()
            self.browse(item)
        elif not item.folder:
            self.open_preview()

    def go_up(self):
        if self.history:
            parent = self.history.pop()
            self.search.clear()
            self.browse(parent)

    def cancel_previews(self):
        for job in self.jobs.values():
            if job['kind'] == 'preview' and not getattr(job.get('context'), 'preview_window', None):
                job['worker'].cancel.set()

    def selection_changed(self):
        self.update_actions()

    def context_menu(self, point):
        row = self.tree.itemAt(point)
        if row is None:
            return
        if not row.isSelected():
            self.tree.clearSelection()
            self.tree.setCurrentItem(row)
        self.update_actions()
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.preview_action)
        menu.addAction(self.download_action)
        menu.addAction(self.rename_action)
        menu.addAction(self.delete_action)
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def request_name(self, title, label, button, text='', parent=None):
        dialog = QtWidgets.ContentDialog(parent or self.window())
        dialog.graphicsEffect().setEnabled(False)
        dialog.setSmokeEnabled(True)
        dialog.setDragEnabled(False)
        dialog.setMinimumWidth(420)
        dialog.setMaximumWidth(560)
        dialog.setTitle(title)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        prompt = QtWidgets.QLabel(label, content)
        field = QtWidgets.QLineEdit(content)
        field.setAccessibleName(label)
        field.setText(text)
        field.selectAll()
        prompt.setBuddy(field)
        layout.addWidget(prompt)
        layout.addWidget(field)
        dialog.setContent(content)
        dialog.setPrimaryButtonText(button)
        dialog.setCloseButtonText(tr('Cancel'))
        dialog.setDefaultButton(QtWidgets.fluentqt.ContentDialogButton.Primary)
        primary = dialog._native_commands['primary']
        field.textChanged.connect(lambda value: primary.setEnabled(bool(value.strip())))
        primary.setEnabled(bool(text.strip()))
        QtCore.QTimer.singleShot(0, field, field.setFocus)
        try:
            return field.text().strip() if dialog.exec() == dialog.ResultPrimary else None
        finally:
            dialog.deleteLater()

    def rename_selected(self):
        if not self.rename_action.isEnabled():
            return
        item = self.selected_items()[0]
        self.rename_item(item, self.folder)

    def rename_item(self, item, folder, parent=None):
        if (not item.can_edit or self.busy() or self.out_of_date
                or self.cached_listing and not self.cache_checked):
            return False
        name = self.request_name(tr('Rename cloud item'), tr('Name'), tr('Rename'), item.display_name, parent=parent)
        if name is not None and name.strip() != item.display_name:
            self.start_job('rename', lambda provider, *args: provider.rename(item, folder, name))
            return True
        return False

    def delete_selected(self):
        if not self.delete_action.isEnabled():
            return
        self.delete_items(self.selected_items())

    def delete_items(self, items, parent=None):
        if (not items or self.busy() or self.out_of_date or self.cached_listing and not self.cache_checked
                or any(not item.can_edit or not item.can_delete for item in items)):
            return False
        if QtWidgets.QMessageBox.question(parent or self.window(), tr('Delete cloud items'),
                                          tr('Move {count} item(s) to the cloud bin?').format(count=len(items)),
                                          defaultButton=QtWidgets.QMessageBox.StandardButton.No) != \
                QtWidgets.QMessageBox.StandardButton.Yes:
            return False

        def operation(provider, cancel, *args):
            for item in items:
                if cancel.is_set():
                    raise SyncError('Transfer cancelled.')
                provider.delete(item)
        self.start_job('delete', operation)
        return True

    def confirm_overwrite(self, title, destination):
        return QtWidgets.QMessageBox.question(
            self.window(), tr('Item already exists'),
            tr('“{name}” already exists in {destination}. Do you want to overwrite it?')
            .format(name=title, destination=destination), defaultButton=QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes

    def open_preview(self, *, refreshed=False):
        selected = self.selected_items()
        if len(selected) != 1 or selected[0].folder or self.busy():
            return
        item = selected[0]
        if self.out_of_date:
            if refreshed:
                self.set_status(tr('Couldn’t open item'), error=True)
            else:
                self.pending_view = item.id
                self.refresh()
            return
        if not item.can_download:
            if preview_url_allowed(item.preview_url):
                window = show_preview(self.window(), item, None)
                self.add_preview_commands(window, item)
                self.preview_windows.add(window)
                window.finished.connect(lambda: self.release_preview(window))
                window.show()
                self.set_ready_status()
            else:
                self.set_status(tr('This item cannot be viewed'), error=True)
            return
        temporary = TemporaryDirectory(prefix='openlp-cloud-preview-')
        temporary.view_id, temporary.refreshed = item.id, refreshed
        destination = Path(temporary.name) / (safe_name(item.display_name) + Path(item.name).suffix)
        self.set_status(tr('Opening {name}…').format(name=item.display_name))
        profile = self.profile
        exporter = None
        if item_category(item) == 'presentations' and destination.suffix.lower() != '.pdf':
            from openlp.plugins.presentations.lib.pdfexport import PDF_EXPORT_CONTROLLERS
            plugin = PluginManager.get_plugin_by_name('presentations')
            if plugin and plugin.is_active():
                controller_name = plugin.media_item.find_controller_by_type(destination)
                controller = plugin.media_item.controllers.get(controller_name)
                if controller and controller.name in PDF_EXPORT_CONTROLLERS:
                    exporter = (controller.name, getattr(controller, 'keynote_app', None),
                                getattr(controller, 'com_obj_name', None))

        def operation(provider, cancel, progress, browser, publish):
            cache = CloudCache(profile, provider.cache_account())
            if item_category(item) == 'media':
                if cache.preview(item, destination):
                    return item, destination, None, True
                stream = MediaStream(provider, item, cancel)
                publish((item, None, stream.url))
                stream.serve()
                return None
            if item_category(item) == 'presentations' and destination.suffix.lower() != '.pdf' and not exporter:
                thumbnail = destination.with_name('cover.png')
                if cache.preview(item, thumbnail, cover=True):
                    progress(tr('Opening {name}…').format(name=item.display_name), 0, 0)
                    return item, destination, thumbnail, True
                kind, image = provider.preview(item, cancel)
                if kind == 'image':
                    thumbnail = destination.with_name('cover.png')
                    thumbnail.write_bytes(image)
                    cache.save_preview(item, thumbnail, cover=True)
                    return item, destination, thumbnail
            cache_hit = cache.preview(item, destination)
            if cache_hit:
                progress(tr('Opening {name}…').format(name=item.display_name), 0, 0)
            else:
                provider.download(item, destination, cancel, lambda current, total: progress(
                    tr('Opening {name}…').format(name=item.display_name), current, total))
                if not cancel.is_set():
                    cache.save_preview(item, destination)
            category = item_category(item)
            if exporter:
                rendered = destination.with_suffix('.pdf')
                if not cache.preview(item, rendered, slides=True):
                    from openlp.plugins.presentations.lib.pdfexport import export_to_pdf
                    progress(tr('Opening {name}…').format(name=item.display_name), 0, 0)
                    rendered = export_to_pdf(exporter[0], destination, keynote_app=exporter[1],
                                             com_name=exporter[2], cancel_event=cancel)
                    if not cancel.is_set():
                        cache.save_preview(item, rendered, slides=True)
                prepared = rendered
            else:
                prepared = (read_xml_item(destination) if category in ('songs', 'custom') else
                            read_theme_item(destination) if category == 'themes' else None)
            return item, destination, prepared, cache_hit
        self.start_job('preview', operation, temporary)

    def add_preview_commands(self, window, item):
        window.resize(1480, 900)
        window.cloud_item, window.cloud_folder, window.cloud_profile = item, self.folder, self.profile
        window.cloud_commands = {}
        toolbar = OpenLPToolbar(window)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for command, icon, label, allowed in (
                ('download', UiIcons().download, tr('Add to Library'), item.can_download),
                ('rename', UiIcons().edit, tr('Rename'), item.can_edit),
                ('delete', UiIcons().delete, tr('Delete'), item.can_edit and item.can_delete)):
            action = toolbar.addAction(icon, label, lambda checked=False, command=command:
                                       self.preview_command(window, command))
            action.setEnabled(allowed)
            window.cloud_commands[command] = action
        window.contentWidget().layout().insertWidget(1, toolbar)

    def preview_command(self, window, command):
        if (not window.cloud_commands[command].isEnabled() or self.profile != window.cloud_profile or self.busy()
                or command != 'download' and (self.out_of_date or self.cached_listing and not self.cache_checked)):
            return
        item = window.cloud_item
        if command == 'download':
            self.download([item])
        elif command == 'rename':
            if self.rename_item(item, window.cloud_folder, window):
                window.accept()
        elif command == 'delete' and self.delete_items([item], window):
            window.accept()

    def release_preview(self, window, temporary=None):
        self.preview_windows.discard(window)
        if temporary:
            temporary.cleanup()
        window.deleteLater()

    def create_folder(self):
        if not self.folder_action.isEnabled():
            return
        name = self.request_name(tr('New cloud folder'), tr('Folder name'), tr('Create'))
        if name is not None:
            folder, category = self.folder, self.category
            self.start_job('folder', lambda provider, *args: provider.create_folder(folder, category, name))

    def download_selected(self):
        self.download(self.selected_items())

    def download(self, items, library=None, target=None):
        if not items or self.busy():
            return
        library_category = None
        if library:
            library_category = 'themes' if hasattr(library, 'theme_list_widget') else library.plugin.name
        if library and any(item_category(item) != library_category for item in items):
            self.set_status(tr('Choose the matching Library type'), error=True)
            return
        if any(not item_category(item) or not item.can_download or item.folder for item in items):
            self.set_status(tr('This item can only be viewed'), error=True)
            return
        if any(item_category(item) != 'themes' and (
                not (plugin := PluginManager.get_plugin_by_name(item_category(item))) or not plugin.is_active())
               for item in items):
            self.set_status(tr('Enable the matching Library plugin'), error=True)
            return
        accepted, overwrites, names = [], {}, set()
        try:
            for item in items:
                category = item_category(item)
                key = duplicate_key(category, item.display_name, Path(item.name).suffix)
                if key in names:
                    raise SyncError('Choose one cloud item per name. Rename duplicates before downloading.')
                names.add(key)
                plugin = PluginManager.get_plugin_by_name(category) if category != 'themes' else None
                existing = local_item(category, plugin, item.display_name, Path(item.name).suffix)
                if existing is not None:
                    if not self.confirm_overwrite(item.display_name, tr('local Library')):
                        continue
                    overwrites[item.id] = existing if category == 'themes' else existing.id
                accepted.append(item)
        except SyncError as error:
            self.set_status(str(error), error=True)
            return
        items = accepted
        if not items:
            self.set_status(tr('Download skipped'))
            return
        self.cancel_previews()
        context = {'target': (QtCore.QPersistentModelIndex(library.list_view.indexFromItem(target))
                              if target is not None and library is not None else None), 'overwrites': overwrites}
        directory = AppLocation.get_section_data_path('librarysync') / 'downloads'
        data_directory = AppLocation.get_data_path()

        def operation(provider, cancel, progress, browser, publish):
            for position, item in enumerate(items, 1):
                if cancel.is_set():
                    raise SyncError('Transfer cancelled.')
                category = item_category(item)
                storage = (data_directory / category / 'library' if category in ('images', 'media', 'presentations')
                           else directory)
                path = storage / uuid4().hex / (safe_name(item.display_name) + Path(item.name).suffix)
                provider.download(item, path, cancel, lambda current, total:
                                  progress(tr('Downloading {name} ({number}/{count})').format(
                                      name=item.display_name, number=position, count=len(items)), current, total))
                prepared = (read_xml_item(path) if category in ('songs', 'custom') else
                            read_theme_item(path) if category == 'themes' else sha256_file_hash(path))
                if not cancel.is_set():
                    publish((item, path, prepared))
        self.start_job('download', operation, context)

    @staticmethod
    def local_drag_category(mime):
        if isinstance(mime, ThemeDragData):
            category = 'themes' if mime.names else ''
        elif isinstance(mime, ItemDragData) and mime.library is not None:
            category = mime.library.plugin.name
        else:
            return ''
        return category if (category in CATEGORIES and mime.indexes
                            and all(index.isValid() for index in mime.indexes)) else ''

    def can_upload(self, mime, folder=None):
        folder = folder or self.folder
        if (not folder or self.busy() or self.out_of_date
                or self.cached_listing and not self.cache_checked
                or any(job['kind'] == 'browse' for job in self.jobs.values())):
            return False
        category = self.local_drag_category(mime)
        if category and category != self.category:
            return bool(self.profile and self.roots.currentData())
        if not folder.can_upload or folder.category not in ('', self.category):
            return False
        if isinstance(mime, CloudDragData):
            return (mime.panel is self and bool(mime.items) and all(
                not item.folder and item.can_move and item_category(item) == self.category for item in mime.items))
        return category == self.category

    def upload(self, mime, folder=None):
        folder = folder or self.folder
        if not self.can_upload(mime, folder):
            return
        temporary = TemporaryDirectory(prefix='openlp-librarysync-')
        try:
            is_copy = isinstance(mime, CloudDragData)
            sources = list(mime.items) if is_copy else prepare_upload(mime, Path(temporary.name))
            titles = [source.display_name if is_copy else source[3] for source in sources]
            extensions = [Path(source.name).suffix if is_copy else source[1].suffix for source in sources]
            category = self.local_drag_category(mime) or self.category
            if len({duplicate_key(category, title, extension) for title, extension in zip(titles, extensions)}) != \
                    len(titles):
                raise SyncError('Each item must have a unique name. Rename duplicates before uploading.')
        except Exception as error:
            temporary.cleanup()
            self.set_status(tr('Couldn’t prepare upload'),
                            detail=str(error) if isinstance(error, SyncError) else '', error=True)
            return
        self.cancel_previews()
        switched = category != self.category
        root = self.roots.currentData()
        if switched:
            index = list(CATEGORIES).index(category)
            with QtCore.QSignalBlocker(self.sections):
                self.sections.setCurrentIndex(index)
            self.change_type(index, browse=False)
        context = {'folder': None if switched else folder, 'temporary': temporary, 'copy': is_copy,
                   'switched': switched}

        def prepare(provider, *args):
            target = folder
            if switched:
                shared = provider.folder(root['id'], root['resource_key'])
                target = provider.type_folder(shared, category, create=False) or shared
                if target.category not in ('', category):
                    raise SyncError('Choose the matching item-type folder or the shared Library root.')
                if not target.can_upload:
                    raise SyncError('You have read-only access to this folder. '
                                    'Ask a folder owner for upload permission.')
                context['folder'] = target
            return [(source, provider.find_item(target, category, title,
                                                exclude=source.id if is_copy else '', extension=extension))
                    for source, title, extension in zip(sources, titles, extensions)]
        self.set_status(tr('Preparing upload…'))
        self.start_job('prepare-upload', prepare, context)

    def run_upload(self, context, plan):
        temporary, folder = context['temporary'], context['folder']
        profile = self.profile

        def operation(provider, cancel, progress, *args):
            cache = CloudCache(profile, provider.cache_account())
            for position, (source, existing) in enumerate(plan, 1):
                if cancel.is_set():
                    raise SyncError('Transfer cancelled.')
                if context['copy']:
                    item = source
                    if existing is None:
                        provider.move(item, folder)
                        continue
                    source = Path(temporary.name) / (safe_name(item.display_name) + Path(item.name).suffix)
                    provider.download(item, source, cancel, lambda current, total: progress(
                        tr('Copying {name}…').format(name=item.display_name), current, total))
                    category, contents, title = item.category, None, item.display_name
                else:
                    category, source, contents, title = source
                progress(tr('Uploading {name} ({number}/{count})').format(
                    name=title, number=position, count=len(plan)), 0, 0)
                write_upload(source, contents)
                before = source.stat()
                uploaded = provider.upload(folder, category, source, cancel, lambda current, total:
                                           progress(tr('Uploading {name} ({number}/{count})').format(
                                               name=title, number=position, count=len(plan)), current, total),
                                           title=title, overwrite=existing)
                try:
                    after = source.stat()
                    if (not cancel.is_set() and before.st_mtime_ns == after.st_mtime_ns
                            and before.st_size == after.st_size == uploaded.size):
                        cache.save_preview(uploaded, source)
                except OSError:
                    pass  # Cache failures must not turn a successful upload into a failed transfer.
                if context['copy']:
                    provider.delete(item)
            return len(plan)
        self.start_job('copy' if context['copy'] else 'upload', operation, context)

    def cancel_transfer(self):
        for job in self.jobs.values():
            if job['kind'] in ('connect', 'upload', 'download', 'preview', 'folder', 'copy', 'prepare-upload',
                               'rename', 'delete'):
                job['worker'].cancel.set()
        self.set_status(tr('Cancelling…'), detail=tr('Completed copies are kept.'))

    def install_drop_targets(self):
        if self.closing:
            return
        for category in CATEGORIES:
            plugin = PluginManager.get_plugin_by_name(category) if category != 'themes' else None
            library = (Registry().get('theme_manager') if Registry().has('theme_manager') else None) \
                if category == 'themes' else plugin.media_item if plugin else None
            if library is None or category == 'themes' and not hasattr(library, 'theme_list_widget'):
                continue
            views = ([library.theme_list_widget.list_view, library.theme_list_widget.grid_view]
                     if category == 'themes' else [library.list_view])
            browser = getattr(library, 'library_view', None)
            if browser is not None:
                views.append(browser.grid)
            for view in views:
                viewport = view.viewport()
                if viewport not in self.drop_views:
                    self.drop_views[viewport] = (library, view, view.acceptDrops(), viewport.acceptDrops())
                    view.setAcceptDrops(True)
                    viewport.setAcceptDrops(True)
                    viewport.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched in self.drop_views and event.type() in (
                QtCore.QEvent.Type.DragEnter, QtCore.QEvent.Type.DragMove, QtCore.QEvent.Type.Drop):
            mime = event.mimeData()
            if isinstance(mime, CloudDragData):
                library, view, _, _ = self.drop_views[watched]
                if mime.panel is not self or self.busy() or not mime.can_import(library):
                    event.ignore()
                    return True
                if event.type() == QtCore.QEvent.Type.Drop:
                    if hasattr(library, 'theme_list_widget'):
                        self.download(list(mime.items), library)
                        event.setDropAction(QtCore.Qt.DropAction.CopyAction)
                        event.accept()
                        return True
                    row = view.itemAt(event.position().toPoint())
                    if view is not library.list_view:
                        row = view.tree_item(row) or view.browser.folder_item()
                    if row and hasattr(library, 'item_class') and isinstance(
                            row.data(0, QtCore.Qt.ItemDataRole.UserRole), library.item_class):
                        row = row.parent()
                    self.download(list(mime.items), library, row if hasattr(library, 'folder_class') else None)
                event.setDropAction(QtCore.Qt.DropAction.CopyAction)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def shutdown(self):
        self.closing = True
        self.pending_view = None
        self.change_timer.stop()
        self.auto_refresh_timer.stop()
        for job in self.jobs.values():
            if job.get('worker'):
                job['worker'].cancel.set()
        for viewport, (library, view, view_accepts, viewport_accepts) in self.drop_views.items():
            try:
                viewport.removeEventFilter(self)
                view.setAcceptDrops(view_accepts)
                viewport.setAcceptDrops(viewport_accepts)
            except RuntimeError:
                pass
        self.drop_views.clear()
        for window in list(self.preview_windows):
            window.reject()
