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
from openlp.plugins.librarysync.lib.connectionwizard import ConnectionWizard
from openlp.plugins.librarysync.lib.profile import (
    deserialize_profile, read_profile, serialize_profile, validate_profile, write_profile)
from openlp.plugins.librarysync.lib.provider import CATEGORIES, SyncError, preview_url_allowed
from openlp.plugins.librarysync.lib.transfer import (
    import_item, item_category, local_item, name_key, prepare_upload, read_theme_item, read_xml_item, safe_name,
    write_upload)
from openlp.plugins.librarysync.lib.preview import show_preview
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
    def __init__(self, panel):
        super().__init__(panel, 'librarysync')
        self.panel = panel
        self.setup_columns([tr('Name'), tr('Size'), tr('Updated')])
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setFont(QtWidgets.fluentqt.font_for_role(QtWidgets.fluentqt.FontRole.Body))
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
        self.generation = 0
        self.category = next(iter(CATEGORIES))
        self.preview_windows = set()
        self.drop_views = {}
        self.imported = set()
        self.closing = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 6)
        layout.setSpacing(6)
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
            tree = CloudTree(self)
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
        self.preview_action = self.toolbar.addAction(UiIcons().preview, tr('Open cloud preview'), self.open_preview)
        self.settings_action = self.toolbar.addAction(UiIcons().settings, tr('Connection'), self.configure)
        self.rename_action = QtGui.QAction(UiIcons().edit, tr('Rename'), self)
        self.rename_action.triggered.connect(self.rename_selected)
        self.delete_action = QtGui.QAction(UiIcons().delete, tr('Delete'), self)
        self.delete_action.triggered.connect(self.delete_selected)
        controls = QtWidgets.QWidget(self)
        controls_layout = QtWidgets.QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 8, 0, 8)
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
        progress_layout = QtWidgets.QHBoxLayout()
        self.progress = QtWidgets.QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.hide()
        progress_layout.addWidget(self.progress, 1)
        self.cancel_button = QtWidgets.QPushButton(tr('Cancel'), self)
        self.cancel_button.clicked.connect(self.cancel_transfer)
        self.cancel_button.hide()
        progress_layout.addWidget(self.cancel_button)
        layout.addLayout(progress_layout)
        self.footer = LibraryFooter(self)
        self.footer.layout().setStretch(0, 0)
        self.footer.layout().addWidget(self.status, 1)
        layout.addWidget(self.footer)
        self.roots.currentIndexChanged.connect(self.change_root)
        self.update_actions()

    def set_status(self, text):
        self.status.setText(text)
        self.status.setToolTip(text)

    def startup(self):
        raw = self.plugin.settings.value('librarysync/profile')
        if raw:
            try:
                self.set_profile(deserialize_profile(raw))
                self.refresh()
            except (SyncError, ValueError) as error:
                self.set_status(str(error))
        self.install_drop_targets()

    def set_profile(self, profile, save=True):
        self.profile = validate_profile(profile)
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
        menu.addAction(tr('Import connection file…'), self.import_connection)
        menu.addAction(tr('Set up Google Drive…'), self.setup_connection)
        export = menu.addAction(tr('Export connection file…'), self.export_connection)
        export.setEnabled(bool(self.profile))
        disconnect = menu.addAction(tr('Disconnect account'), self.disconnect)
        disconnect.setEnabled(bool(self.profile))
        menu.exec(QtGui.QCursor.pos())

    def import_connection(self):
        path, _ = FileDialog.getOpenFileName(
            self, tr('Import Library Sync connection'), filter=tr('Library Sync connection (*.json)'))
        if path:
            try:
                self.set_profile(read_profile(path))
                self.set_status(tr('Connection imported. Choose Connect to sign in with your own Google account.'))
            except (OSError, SyncError) as error:
                self.set_status(str(error))

    def setup_connection(self):
        wizard = ConnectionWizard(self)
        if wizard.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.set_profile(wizard.profile)
            self.set_status(tr('Connection saved. Choose Connect to sign in with your own Google account.'))

    def export_connection(self):
        if not self.profile:
            return
        path, _ = FileDialog.getSaveFileName(
            self, tr('Export Library Sync connection'),
            Path('organisation-library.librarysync.json'), tr('Connection file (*.json)'))
        if path:
            try:
                write_profile(path, self.profile)
                self.set_status(tr('Connection exported. Each person signs in separately; tokens are excluded.'))
            except (OSError, SyncError) as error:
                self.set_status(str(error))

    def connect_drive(self):
        if not self.profile:
            self.import_connection()
            if not self.profile:
                return
        if self.jobs:
            return
        self.set_status(tr('Complete sign-in in your browser…'))
        self.start_job('connect', lambda provider, cancel, progress, browser, publish:
                       provider.sign_in(cancel, browser))

    def disconnect(self):
        if self.profile and not self.jobs:
            self.start_job('disconnect', lambda provider, *args: provider.disconnect())

    def start_job(self, kind, operation, context=None):
        if self.closing or not self.profile:
            return
        job_id = uuid4().hex
        worker = SyncWorker(job_id, self.profile, operation)
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
            self.connected = True
            folder, items, token = value
            self.folder, self.page_token = folder, token
            if not job['context']:
                self.tree.clear()
            for item in items:
                if item.folder:
                    if (self.category in ('songs', 'custom') or not folder.category
                            or item.category not in ('', self.category)):
                        continue
                    item = replace(item, category=self.category)
                    access = tr('Can upload') if item.can_upload else tr('Read only')
                else:
                    if item_category(item) != self.category:
                        continue
                    access = tr('Download') if item.can_download else tr('Preview only')
                modified = QtCore.QDateTime.fromString(item.modified, QtCore.Qt.DateFormat.ISODate)
                updated = (QtCore.QLocale().toString(modified.toLocalTime(), QtCore.QLocale.FormatType.ShortFormat)
                           if modified.isValid() else '—')
                row = FileTreeWidgetItem([item.display_name,
                                          '—' if item.folder else self.format_size(item.size), updated])
                row.set_sort_data(1, item.size)
                row.set_sort_data(2, modified.toMSecsSinceEpoch() if modified.isValid() else 0)
                row.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
                row.setData(0, LIBRARY_FOLDER_ROLE, item.folder)
                row.setIcon(0, UiIcons().folder if item.folder else service_icon(
                    self.type_icons[self.category], self.category))
                row.setToolTip(0, '\n'.join([item.display_name, access] + (
                    [self.format_size(item.size)] if not item.folder else [])))
                self.tree.addTopLevelItem(row)
            if not job['context']:
                self.cache[(self.category, folder.id)] = (time.monotonic(), value)
                if not self.history:
                    self.cache[(self.category, self.roots.currentData()['id'])] = (time.monotonic(), value)
            self.update_breadcrumbs()
            self.set_status(tr('Drop Library items here to share a new copy.') if folder.can_upload else
                            tr('Read-only folder. Preview items or drag them to the local Library.'))
            self.filter_items(self.search.text())
            self.more_button.setVisible(bool(token))
            self.footer.set_count(self.tree.topLevelItemCount())
        elif job['kind'] == 'preview':
            item, path, prepared = value
            try:
                window = show_preview(self.window(), item, path, prepared)
                self.preview_windows.add(window)
                window.finished.connect(lambda: self.release_preview(window, job['context']))
                window.finished.connect(job['worker'].stop)
                window.show()
                job['context'].preview_window = window
                self.set_status(tr('Preview: {name}').format(name=item.display_name))
            except Exception:
                self.set_status(tr('This item could not be previewed.'))
        elif job['kind'] == 'download':
            job.setdefault('downloads', []).append(value)
        elif job['kind'] in ('upload', 'copy'):
            self.cache.clear()
            self.set_status(tr('Shared {count} item(s).').format(count=value))
        elif job['kind'] == 'prepare-upload':
            job['candidates'] = value
        elif job['kind'] in ('rename', 'delete'):
            self.cache.clear()
            self.set_status(tr('Cloud item renamed.') if job['kind'] == 'rename' else tr('Moved to the cloud bin.'))
        elif job['kind'] == 'folder':
            self.cache.clear()
            self.set_status(tr('Created folder: {name}').format(name=value.display_name))
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
            existing = local_item(category, plugin, item.display_name)
            if existing is not None and overwrite is None:
                if not self.confirm_overwrite(item.display_name, tr('local Library')):
                    self.set_status(tr('Download skipped.'))
                    return
                overwrite = existing if category == 'themes' else existing.id
            import_item(item, path, plugin, target, prepared=prepared, overwrite=overwrite)
            self.imported.add((item.id, item.version))
            self.set_status(tr('Added to Library: {name}').format(name=item.display_name))
            if plugin and plugin.media_item:
                toolbox = self.plugin.main_window.media_tool_box
                for index in range(toolbox.count()):
                    if toolbox.widget(index) is plugin.media_item:
                        toolbox.setCurrentIndex(index)
                        break
        except Exception as error:
            self.set_status(str(error) if isinstance(error, SyncError) else tr('Cloud item import failed.'))

    @QtCore.Slot(str, str)
    def job_failed(self, job_id, message):
        job = self.jobs.get(job_id)
        if not self.closing and job and job['generation'] == self.generation:
            job['failed'] = True
            if job['kind'] in ('browse', 'connect'):
                self.connected = False
            self.set_status(message)

    @QtCore.Slot(str)
    def job_completed(self, job_id):
        job = self.jobs.pop(job_id, None)
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
                            self.set_status(tr('You cannot replace and move “{name}”: '
                                               'you cannot remove the original.').format(name=title))
                            continue
                        if not existing.can_edit or existing.folder:
                            self.set_status(tr('You cannot overwrite “{name}”: it is read only.').format(name=title))
                            continue
                        if not self.confirm_overwrite(title, tr('Cloud Library')):
                            continue
                    accepted.append((source, existing))
            if accepted and not self.closing and not (job.get('worker') and job['worker'].cancel.is_set()):
                self.run_upload(job['context'], accepted)
            else:
                job['context']['temporary'].cleanup()
        elif job and job['kind'] == 'download' and not self.closing:
            for value in job.get('downloads', []):
                self.apply_download(value, job['context'])
        elif job and job['kind'] in ('upload', 'copy') and job.get('context'):
            job['context']['temporary'].cleanup()
        if self.closing or not job:
            return
        cancelled = job.get('worker') and job['worker'].cancel.is_set()
        if job['kind'] == 'preview' and cancelled:
            self.set_status(tr('Preview closed.') if hasattr(job['context'], 'preview_window') else
                            tr('Preview cancelled.'))
        elif job['kind'] in ('connect', 'upload', 'download', 'copy', 'folder') and cancelled:
            self.set_status(tr('Cancelled. Completed copies are kept.'))
        if job['kind'] == 'connect' and not job.get('failed') and not cancelled:
            self.refresh()
        elif (job['kind'] in ('upload', 'copy', 'folder', 'rename', 'delete')
              and not job.get('failed') and not cancelled):
            self.cache.clear()
            if job['kind'] == 'delete':
                self.set_status(tr('Moved to the cloud bin.'))
            self.refresh()
        elif job['kind'] == 'disconnect' and not job.get('failed'):
            self.connected = False
            self.folder = None
            self.tree.clear()
            self.cache.clear()
            self.set_status(tr('Disconnected. Choose Connect to sign in again.'))
        self.update_actions()

    @QtCore.Slot(str, str, object, object)
    def job_progress(self, job_id, name, current, total):
        if job_id in self.jobs and not self.closing:
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
                   for job in self.jobs.values())

    def update_actions(self):
        browsing = any(job['kind'] == 'browse' for job in self.jobs.values())
        busy = self.busy()
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
        self.more_button.setEnabled(not busy and not browsing)
        self.download_action.setEnabled(bool(selected) and not busy and all(
            not item.folder and item.can_download and item_category(item) for item in selected))
        self.preview_action.setEnabled(len(selected) == 1 and not selected[0].folder and not busy and (
            selected[0].can_download or preview_url_allowed(selected[0].preview_url)))
        self.folder_action.setEnabled(bool(self.folder and self.folder.can_upload
                                           and self.folder.category in ('', self.category))
                                      and self.category not in ('songs', 'custom') and not busy and not browsing)
        self.rename_action.setEnabled(len(selected) == 1 and selected[0].can_edit and not busy)
        self.delete_action.setEnabled(bool(selected) and all(item.can_delete for item in selected) and not busy)
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
        self.refresh()

    def change_type(self, index):
        self.category = list(CATEGORIES)[index]
        self.tree = self.sections.widget(index)
        self.folder, self.history, self.page_token = None, [], ''
        self.tree.clear()
        self.search.clear()
        self.more_button.hide()
        self.footer.set_count(0)
        self.generation += 1
        self.update_breadcrumbs()
        self.browse()

    def update_breadcrumbs(self):
        crumbs = [BreadcrumbItem(self.roots.currentText(), None), BreadcrumbItem(tr(CATEGORIES[self.category]), None)]
        for position, folder in enumerate(self.history[1:] + ([self.folder] if self.history else [])):
            crumbs.append(BreadcrumbItem(folder.display_name, position + 1))
        self.breadcrumbs.setItems(crumbs)

    def activate_breadcrumb(self, index, item):
        if self.busy() or any(job['kind'] == 'browse' for job in self.jobs.values()):
            return
        depth = item.data
        folder = (self.history[depth] if depth is not None and depth < len(self.history) else
                  self.folder if depth is not None else None)
        self.history = self.history[:depth] if depth is not None else []
        self.search.clear()
        self.browse(folder)

    def browse(self, folder=None, page_token='', force=False):
        if not self.profile or self.busy() or any(job['kind'] == 'browse' for job in self.jobs.values()):
            return
        root = self.roots.currentData()
        if not root:
            return
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
        self.set_status(tr('Loading cloud folder…'))

        def operation(provider, *args):
            current = folder
            if force and not page_token and current is not None:
                current = replace(provider.folder(current.id, current.resource_key), category=current.category)
            if current is None or not current.category:
                shared = current or provider.folder(root['id'], root['resource_key'])
                current = provider.type_folder(shared, self.category, create=False) or shared
            items, token = provider.list_folder(current, page_token)
            return current, items, token
        self.start_job('browse', operation, bool(page_token))

    def refresh(self):
        self.browse(self.folder, force=True)

    def load_more(self):
        if self.page_token:
            self.browse(self.folder, self.page_token, force=True)

    def activate_item(self, row, column=0):
        item = row.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if (item.folder and self.folder and not self.busy()
                and not any(job['kind'] == 'browse' for job in self.jobs.values())):
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
            if job['kind'] == 'preview':
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
        if self.rename_action.isEnabled():
            menu.addAction(self.rename_action)
        if self.delete_action.isEnabled():
            menu.addAction(self.delete_action)
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def rename_selected(self):
        if not self.rename_action.isEnabled():
            return
        item = self.selected_items()[0]
        name, accepted = QtWidgets.QInputDialog.getText(
            self.window(), tr('Rename cloud item'), tr('Name'), text=item.display_name)
        if accepted and name.strip() != item.display_name:
            folder = self.folder
            self.start_job('rename', lambda provider, *args: provider.rename(item, folder, name))

    def delete_selected(self):
        if not self.delete_action.isEnabled():
            return
        items = self.selected_items()
        if QtWidgets.QMessageBox.question(self.window(), tr('Delete cloud items'),
                                          tr('Move {count} item(s) to the cloud bin?').format(count=len(items)),
                                          defaultButton=QtWidgets.QMessageBox.StandardButton.No) != \
                QtWidgets.QMessageBox.StandardButton.Yes:
            return

        def operation(provider, cancel, *args):
            for item in items:
                if cancel.is_set():
                    raise SyncError('Transfer cancelled.')
                provider.delete(item)
        self.start_job('delete', operation)

    def confirm_overwrite(self, title, destination):
        return QtWidgets.QMessageBox.question(
            self.window(), tr('Item already exists'),
            tr('“{name}” already exists in {destination}. Do you want to overwrite it?')
            .format(name=title, destination=destination), defaultButton=QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes

    def open_preview(self):
        selected = self.selected_items()
        if len(selected) != 1 or selected[0].folder or self.busy():
            return
        item = selected[0]
        if not item.can_download:
            if preview_url_allowed(item.preview_url):
                window = show_preview(self.window(), item, None)
                self.preview_windows.add(window)
                window.finished.connect(lambda: self.release_preview(window))
                window.show()
            return
        temporary = TemporaryDirectory(prefix='openlp-cloud-preview-')
        destination = Path(temporary.name) / (safe_name(item.display_name) + Path(item.name).suffix)
        self.set_status(tr('Loading preview: {name}').format(name=item.display_name))

        def operation(provider, cancel, progress, browser, publish):
            if item_category(item) == 'media':
                stream = MediaStream(provider, item, cancel)
                publish((item, None, stream.url))
                stream.serve()
                return None
            if item_category(item) == 'images' or (
                    item_category(item) == 'presentations' and destination.suffix.lower() != '.pdf'):
                kind, image = provider.preview(item, cancel)
                if kind == 'image':
                    thumbnail = destination.with_name('cover.png')
                    thumbnail.write_bytes(image)
                    return item, destination, thumbnail
            provider.download(item, destination, cancel, lambda current, total:
                              progress(tr('Loading preview: {name}').format(name=item.display_name), current, total))
            category = item_category(item)
            prepared = (read_xml_item(destination) if category in ('songs', 'custom') else
                        read_theme_item(destination) if category == 'themes' else None)
            return item, destination, prepared
        self.start_job('preview', operation, temporary)

    def release_preview(self, window, temporary=None):
        self.preview_windows.discard(window)
        if temporary:
            temporary.cleanup()
        window.deleteLater()

    def create_folder(self):
        if not self.folder_action.isEnabled():
            return
        name, accepted = QtWidgets.QInputDialog.getText(self.window(), tr('New cloud folder'), tr('Folder name'))
        if accepted:
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
            self.set_status(tr('Drop items into the matching Library type.'))
            return
        if any(not item_category(item) or not item.can_download or item.folder for item in items):
            self.set_status(tr('Choose downloadable Library files. Other items can use the cloud preview.'))
            return
        if any(item_category(item) != 'themes' and (
                not (plugin := PluginManager.get_plugin_by_name(item_category(item))) or not plugin.is_active())
               for item in items):
            self.set_status(tr('Enable the matching Library plugins before downloading these items.'))
            return
        accepted, overwrites, names = [], {}, set()
        try:
            for item in items:
                if name_key(item.display_name) in names:
                    raise SyncError('Choose one cloud item per name. Rename duplicates before downloading.')
                names.add(name_key(item.display_name))
                category = item_category(item)
                plugin = PluginManager.get_plugin_by_name(category) if category != 'themes' else None
                existing = local_item(category, plugin, item.display_name)
                if existing is not None:
                    if not self.confirm_overwrite(item.display_name, tr('local Library')):
                        continue
                    overwrites[item.id] = existing if category == 'themes' else existing.id
                accepted.append(item)
        except SyncError as error:
            self.set_status(str(error))
            return
        items = accepted
        if not items:
            self.set_status(tr('Download skipped.'))
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

    def can_upload(self, mime, folder=None):
        folder = folder or self.folder
        if (not folder or not folder.can_upload or self.busy()
                or any(job['kind'] == 'browse' for job in self.jobs.values())
                or folder.category not in ('', self.category)):
            return False
        if isinstance(mime, CloudDragData):
            return (mime.panel is self and bool(mime.items) and all(
                not item.folder and item.can_move and item_category(item) == self.category for item in mime.items))
        if isinstance(mime, ThemeDragData):
            return self.category == 'themes' and bool(mime.names) and all(index.isValid() for index in mime.indexes)
        return (isinstance(mime, ItemDragData) and mime.library is not None and bool(mime.indexes)
                and all(index.isValid() for index in mime.indexes) and mime.library.plugin.name == self.category)

    def upload(self, mime, folder=None):
        folder = folder or self.folder
        if not self.can_upload(mime, folder):
            return
        temporary = TemporaryDirectory(prefix='openlp-librarysync-')
        try:
            is_copy = isinstance(mime, CloudDragData)
            sources = list(mime.items) if is_copy else prepare_upload(mime, Path(temporary.name))
            titles = [source.display_name if is_copy else source[3] for source in sources]
            if len({name_key(title) for title in titles}) != len(titles):
                raise SyncError('Each item must have a unique name. Rename duplicates before uploading.')
        except Exception as error:
            temporary.cleanup()
            self.set_status(str(error) if isinstance(error, SyncError) else tr('Library item preparation failed.'))
            return
        self.cancel_previews()
        category = self.category
        context = {'folder': folder, 'temporary': temporary, 'copy': is_copy}

        def prepare(provider, *args):
            return [(source, provider.find_item(folder, category, title, exclude=source.id) if is_copy else
                     provider.find_item(folder, category, title)) for source, title in zip(sources, titles)]
        self.set_status(tr('Checking item names…'))
        self.start_job('prepare-upload', prepare, context)

    def run_upload(self, context, plan):
        temporary, folder = context['temporary'], context['folder']

        def operation(provider, cancel, progress, *args):
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
                        tr('Copying {name}').format(name=item.display_name), current, total))
                    category, contents, title = item.category, None, item.display_name
                else:
                    category, source, contents, title = source
                write_upload(source, contents)
                provider.upload(folder, category, source, cancel, lambda current, total:
                                progress(tr('Uploading {name} ({number}/{count})').format(
                                    name=title, number=position, count=len(plan)), current, total),
                                title=title, overwrite=existing)
                if context['copy']:
                    provider.delete(item)
            return len(plan)
        self.start_job('copy' if context['copy'] else 'upload', operation, context)

    def cancel_transfer(self):
        for job in self.jobs.values():
            if job['kind'] in ('connect', 'upload', 'download', 'preview', 'folder', 'copy', 'prepare-upload',
                               'rename', 'delete'):
                job['worker'].cancel.set()
        self.set_status(tr('Cancelling… completed copies are kept.'))

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
