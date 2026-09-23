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

import logging
import os
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from sqlalchemy.sql.expression import or_

from openlp.core.common import delete_file, sha256_file_hash
from openlp.core.common.applocation import AppLocation
from openlp.core.common.i18n import UiStrings, translate
from openlp.core.common.path import create_paths
from openlp.core.common.registry import Registry
from openlp.core.lib import build_icon, validate_thumb
from openlp.core.lib import ServiceItemContext
from openlp.core.lib.serviceitem import ItemCapabilities
from openlp.core.lib.ui import create_widget_action, critical_error_message_box
from openlp.core.state import State
from openlp.core.threading import ThreadWorker, run_thread
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.library import FolderLibraryItem
from openlp.core.ui.media import get_supported_media_suffix, parse_stream_path, MediaType
from openlp.core.ui.media.mediainfo import media_info
from openlp.core.widgets.views import FileTreeWidgetItem

from openlp.plugins.media.lib.db import Folder, Item

from openlp.plugins.media.forms.streamselectorform import StreamSelectorForm
from openlp.plugins.media.forms.networkstreamselectorform import NetworkStreamSelectorForm


log = logging.getLogger(__name__)


def _format_file_size(size: int) -> str:
    """Return a human-readable file size string."""
    for unit, threshold in (('GB', 1 << 30), ('MB', 1 << 20), ('KB', 1 << 10)):
        if size >= threshold:
            return f'{size / threshold:.1f} {unit}'
    return f'{size} B'


class ThumbnailGeneratorWorker(ThreadWorker):
    """
    Worker thread for generating media thumbnails in background without blocking UI.
    """
    # Signal emitted when a thumbnail is generated: (file_path, thumbnail_path)
    thumbnail_generated = QtCore.Signal(str, str)

    def __init__(self, items_with_paths):
        """
        Initialize the worker with a list of (file_path, thumbnail_path, media_item) tuples.
        
        :param items_with_paths: List of tuples (file_path, thumbnail_path, media_item)
        """
        super().__init__()
        self.items_with_paths = items_with_paths

    def start(self):
        """
        Generate thumbnails for all pending items in background.
        """
        for file_path, thumbnail_path, media_item in self.items_with_paths:
            try:
                # Skip if file doesn't exist
                if not Path(file_path).exists():
                    continue
                # Skip if thumbnail already exists
                if validate_thumb(Path(file_path), Path(thumbnail_path)):
                    self.thumbnail_generated.emit(file_path, thumbnail_path)
                    continue
                # Generate thumbnail
                if media_info().create_media_thumbnail(file_path, thumbnail_path):
                    self.thumbnail_generated.emit(file_path, thumbnail_path)
            except Exception as e:
                log.exception(f'Failed to generate thumbnail for {file_path}: {e}')
        self.quit.emit()


class MediaLengthWorker(ThreadWorker):
    """
    Worker thread for obtaining media duration without blocking the UI thread.
    """
    media_length_ready = QtCore.Signal(int)

    def __init__(self, media_path: str):
        super().__init__()
        self.media_path = media_path

    def start(self):
        try:
            media_length = media_info().get_media_duration(self.media_path)
            self.media_length_ready.emit(media_length)
        except Exception as e:
            log.exception(f'Failed to read media length for {self.media_path}: {e}')
            self.media_length_ready.emit(0)
        finally:
            self.quit.emit()


class MediaMediaItem(FolderLibraryItem):
    """
    This is the custom media manager item for Media Slides.
    """
    media_go_live = QtCore.Signal(list)
    media_add_to_service = QtCore.Signal(list)
    pending_thumbnail_role = QtCore.Qt.ItemDataRole.UserRole + 1
    thumbnail_updated = QtCore.Signal(str)  # Emitted with file_path when thumbnail is generated
    log.info('{name} MediaMediaItem loaded'.format(name=__name__))

    def __init__(self, parent, plugin):
        self.setup()
        super(MediaMediaItem, self).__init__(parent, plugin, Folder, Item)
        self.thumbnail_generator_worker = None
        self.thumbnail_generator_thread_name = None

    def retranslate_ui(self):
        """
        This method is called automatically to provide OpenLP with the opportunity to translate the ``MediaManagerItem``
        to another language.
        """
        super().retranslate_ui()
        self.on_new_prompt = translate('MediaPlugin.MediaItem', 'Select Media')

    def setup_item(self):
        """
        Do some additional setup.
        """
        self.media_go_live.connect(self.go_live_remote)
        self.media_add_to_service.connect(self.add_to_service_remote)
        self.single_service_item = False
        self.has_search = True
        self.media_object = None
        Registry().register_function('mediaitem_media_rebuild', self.rebuild_players)
        # Allow DnD from the desktop
        self.list_view.activateDnD()
        self.list_view.setup_columns([translate('MediaPlugin.MediaItem', 'Name'),
                                      translate('MediaPlugin.MediaItem', 'Date')])

    def setup(self):
        """
        Allow early setup to be mocked.
        """
        self.icon_path = 'images/image'
        self.background = False
        self.automatic = ''
        self.error_icon = UiIcons().delete
        self.clapperboard = UiIcons().clapperboard

    @staticmethod
    def _fixed_canvas_icon(icon, canvas_width=88, canvas_height=50, icon_size=30):
        """
        Draw an icon centered on a fixed-size canvas, so media rows do not stagger.
        """
        canvas = QtGui.QPixmap(canvas_width, canvas_height)
        canvas.fill(QtCore.Qt.GlobalColor.black)
        source = icon.pixmap(QtCore.QSize(icon_size, icon_size))
        x = (canvas_width - source.width()) // 2
        y = (canvas_height - source.height()) // 2
        painter = QtGui.QPainter(canvas)
        painter.drawPixmap(x, y, source)
        painter.end()
        return QtGui.QIcon(canvas)

    def required_icons(self):
        """
        Set which icons the media manager tab should show
        """
        super().required_icons()
        self.has_file_icon = True
        self.has_new_icon = False
        self.has_edit_icon = False
        if not State().check_preconditions('media'):
            self.can_preview = False
            self.can_make_live = False
            self.can_add_to_service = False
        if State().check_preconditions('media_live'):
            self.can_make_live = True
        else:
            self.can_preview = False
            self.can_make_live = False
            self.can_add_to_service = False

    def initialise(self):
        """
        Initialize media item.
        """
        self.log_debug('Initialise')
        self.list_view.clear()
        self.list_view.setIconSize(QtCore.QSize(88, 50))
        self.list_view.setIndentation(self.list_view.default_indentation)
        self.list_view.allow_internal_dnd = True
        self.service_path = AppLocation.get_section_data_path(self.settings_section) / 'thumbnails'
        create_paths(self.service_path)
        # Load images from the database
        self.load_list(self.manager.get_all_objects(Item, order_by_ref=Item.file_path), is_initial_load=True)
        self.service_path = AppLocation.get_section_data_path('media') / 'thumbnails'
        self.rebuild_players()

    def add_middle_header_bar(self):
        super().add_middle_header_bar()
        self.toolbar.addSeparator()
        network_stream_button_text = translate('MediaPlugin.MediaItem', 'Open network stream')
        network_stream_button_tooltip = translate('MediaPlugin.MediaItem', 'Open network stream')
        self.toolbar.add_toolbar_action('networkstream_action', text=network_stream_button_text,
                                        icon=UiIcons().network_stream, tooltip=network_stream_button_tooltip,
                                        triggers=self.on_open_network_stream)
        device_stream_button_text = translate('MediaPlugin.MediaItem', 'Open device stream')
        device_stream_button_tooltip = translate('MediaPlugin.MediaItem', 'Open device stream')
        self.toolbar.add_toolbar_action('devicestream_action', text=device_stream_button_text,
                                        icon=UiIcons().device_stream, tooltip=device_stream_button_tooltip,
                                        triggers=self.on_open_device_stream)

    def add_custom_context_actions(self):
        """
        Add custom actions to the context menu.
        """
        super().add_custom_context_actions()

    def generate_slide_data(self, service_item, *, item=None, remote=False, context=ServiceItemContext.Service,
                            **kwargs):
        """
        Generate the slide data. Needs to be implemented by the plugin.

        :param service_item: The service item to be built on
        :param item: The Song item to be used
        :param remote: Triggered from remote
        :param context: Why is it being generated
        :param kwargs: Consume other unused args specified by the base implementation, but not use by this one.
        """
        if item is None:
            item = self.list_view.currentItem()
            if item is None:
                return False
        if isinstance(item, QtCore.QModelIndex):
            item = self.list_view.itemFromIndex(item)
        media_item = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not isinstance(media_item, Item):
            return False
        filename = media_item.file_path
        if filename.startswith('devicestream:') or filename.startswith('networkstream:'):
            # Special handling if the filename is a devicestream
            (_, name, _, _) = parse_stream_path(filename)
            service_item.processor = 'qt6'
            service_item.add_capability(ItemCapabilities.CanStream)
            service_item.add_from_command(filename, name, self.clapperboard)
            service_item.title = name
        else:
            if not os.path.exists(filename):
                recovered_path = self._recover_managed_media(media_item)
                if recovered_path:
                    filename = str(recovered_path)
            if not os.path.exists(filename):
                if not remote:
                    # File is no longer present
                    critical_error_message_box(
                        translate('MediaPlugin.MediaItem', 'Missing Media File'),
                        translate('MediaPlugin.MediaItem', 'The file {name} no longer exists.').format(name=filename))
                return False
            supported, error_text = self.media_controller.is_media_supported(filename)
            if not supported:
                if not remote:
                    details = error_text or translate(
                        'MediaPlugin.MediaItem',
                        'The current platform media backend cannot decode this file.')
                    critical_error_message_box(
                        translate('MediaPlugin.MediaItem', 'Unsupported Media on This Platform'),
                        translate('MediaPlugin.MediaItem',
                                  'Unable to play media file:\n{name}\n\n{details}').format(name=filename,
                                                                                            details=details))
                return False
            (path, name) = os.path.split(filename)
            display_name = media_item.name or name
            service_item.title = Path(display_name).stem
            service_item.processor = 'qt6'
            managed_library_dir = (AppLocation.get_section_data_path('media') / 'library').resolve()
            media_path = Path(filename).resolve()
            is_managed_file = False
            try:
                media_path.relative_to(managed_library_dir)
                is_managed_file = True
            except ValueError:
                is_managed_file = False
            if is_managed_file and media_item.file_hash and Path(name).stem == media_item.file_hash:
                # Older managed imports use hash-named files and a separate display name.
                service_item.has_original_file_path = False
                service_item.add_from_command(path, display_name, self.clapperboard, file_hash=media_item.file_hash)
            else:
                # The frame title is also used to locate the source file.
                service_item.add_from_command(path, name, self.clapperboard, file_hash=media_item.file_hash)
            # Only get start and end times if going to a service
            if context == ServiceItemContext.Service:
                self._queue_media_length_probe(service_item, filename)
        service_item.add_capability(ItemCapabilities.CanAutoStartForLive)
        service_item.add_capability(ItemCapabilities.CanEditTitle)
        service_item.add_capability(ItemCapabilities.RequiresMedia)
        # force a non-existent theme
        service_item.theme = -1
        # validate the item after all capabilities has been added
        service_item.validate_item()
        return True

    def _recover_managed_media(self, media_item):
        """Find a renamed managed file by its recorded hash and repair the database path."""
        if not media_item.file_hash:
            return None
        library_dir = (AppLocation.get_section_data_path('media') / 'library').resolve()
        missing_path = Path(media_item.file_path)
        try:
            missing_path.resolve().relative_to(library_dir)
        except ValueError:
            return None
        if not library_dir.is_dir():
            return None
        for candidate in library_dir.iterdir():
            if candidate.is_file() and candidate.suffix.lower() == missing_path.suffix.lower() and \
                    sha256_file_hash(candidate) == media_item.file_hash:
                media_item.file_path = str(candidate)
                if not media_item.name or media_item.name == missing_path.name:
                    media_item.name = candidate.name
                self.manager.save_object(media_item)
                return candidate
        return None

    def _queue_media_length_probe(self, service_item, filename):
        """
        Read media length in a worker thread and update the existing service item when finished.
        """
        thread_name = f'media_length_{service_item.unique_identifier}_{QtCore.QDateTime.currentMSecsSinceEpoch()}'
        worker = MediaLengthWorker(filename)
        worker.media_length_ready.connect(
            lambda media_length, unique_id=service_item.unique_identifier, media_path=filename:
            self._apply_media_length_probe_result(unique_id, media_length, media_path)
        )
        run_thread(worker, thread_name, can_start=True)

    def _apply_media_length_probe_result(self, service_item_id, media_length, media_path=None):
        """
        Apply async media-length result to the matching item currently in the service.
        """
        if media_length <= 0 and media_path:
            # Some Windows backends can report LoadedMedia before durationChanged in threaded probes.
            # Retry once on the main thread for a reliable duration before updating the service item.
            media_length = self.media_controller.media_length(media_path)
        for index, service_entry in enumerate(self.service_manager.service_items):
            service_item = service_entry.get('service_item')
            if service_item and service_item.unique_identifier == service_item_id:
                service_item.set_media_length(media_length)
                self.service_manager.repaint_service_list(index, -1)
                break

    def rebuild_players(self):
        """
        Rebuild the tab in the media manager when changes are made in the settings.
        """
        # self.populate_display_types()
        audio, video = get_supported_media_suffix()
        self.on_new_file_masks = translate('MediaPlugin.MediaItem',
                                           'Videos ({video});;Audio ({audio});;{files} '
                                           '(*)').format(video=' '.join(video),
                                                         audio=' '.join(audio),
                                                         files=UiStrings().AllFiles)

    def file_to_item(self, filename):
        """
        Override the inherited file_to_item() method to handle various tracks
        """
        if isinstance(filename, Path):
            name = filename.name
            filename = str(filename)
        elif filename.startswith('devicestream:') or filename.startswith('networkstream:'):
            _, name, _, _ = parse_stream_path(filename)
        else:
            name = os.path.basename(filename)
        item = self.item_class(name=name, file_path=filename)
        self.manager.save_object(item)
        return item

    def load_item(self, item, is_initial_load=False, force_generate=False):
        """
        Given an item object, return a QTreeWidgetItem
        
        :param item: The item to load
        :param is_initial_load: If True, defer thumbnail generation (startup)
        :param force_generate: If True, generate thumbnail immediately (used for testing)
        """
        track_str = str(item.file_path)
        track_info = QtCore.QFileInfo(track_str)
        tree_item = None
        if track_str.startswith('devicestream:') or track_str.startswith('networkstream:'):
            (stream_type, name, mrl, _) = parse_stream_path(track_str)
            tree_item = FileTreeWidgetItem([name])
            tree_item.setText(0, name)
            if stream_type == MediaType.DeviceStream:
                tree_item.setIcon(0, UiIcons().device_stream)
            else:
                tree_item.setIcon(0, UiIcons().network_stream)
            tree_item.setToolTip(0, mrl)
        elif not Path(item.file_path).exists():
            # File doesn't exist, mark as error.
            file_name = item.name or Path(item.file_path).name
            display_name = Path(file_name).stem
            tree_item = FileTreeWidgetItem([display_name])
            tree_item.setText(0, display_name)
            tree_item.setIcon(0, UiIcons().error)
            tree_item.setToolTip(0, track_str)
        elif track_info.isFile():
            # Normal media file handling.
            file_path_obj = Path(item.file_path)
            file_name = item.name or file_path_obj.name
            display_name = Path(file_name).stem
            file_type = file_path_obj.suffix.lstrip('.').upper()
            tree_item = FileTreeWidgetItem([display_name])
            tree_item.setText(0, display_name)
            search = "*." + file_name.split('.')[-1].lower()
            a_suffixes, v_suffixes = get_supported_media_suffix()
            if search in a_suffixes:
                tree_item.setIcon(0, UiIcons().audio)
            else:
                # During imports (not initial load), defer thumbnail to prevent UI freeze
                # During startup (initial load), also defer for performance
                defer_on_import = not is_initial_load and not force_generate
                self._set_video_icon(tree_item, item, is_initial_load=is_initial_load,
                                   defer_on_import=defer_on_import, force_generate=force_generate)
            tree_item.setToolTip(0, track_str)
            try:
                stat = file_path_obj.stat()
                size_str = _format_file_size(stat.st_size)
                mtime = stat.st_mtime
                tree_item.setText(1, datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M'))
                tree_item.set_sort_data(1, mtime)
                tree_item.setToolTip(0, f'{track_str}\n{file_type} · {size_str}')
            except OSError:
                pass
        if tree_item:
            tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
        return tree_item

    def _set_video_icon(self, tree_item: QtWidgets.QTreeWidgetItem, item: Item, is_initial_load: bool = False,
                        defer_on_import: bool = False, force_generate: bool = False):
        """
        Set the icon for a video item, optionally deferring thumbnail generation during startup load or import.
        
        :param tree_item: The tree widget item to update with the icon
        :param item: The media item database object
        :param is_initial_load: If True, defer thumbnail generation (startup initial load)
        :param defer_on_import: If True, defer thumbnail generation (during import to prevent UI freeze)
        :param force_generate: If True, always generate immediately (overrides other settings, used for on_focus)
        """
        file_path = Path(item.file_path)
        thumbnail_path = self.generate_thumbnail_path(item)
        if validate_thumb(file_path, thumbnail_path):
            tree_item.setIcon(0, build_icon(thumbnail_path))
            tree_item.setData(0, self.pending_thumbnail_role, False)
            return
        # Defer thumbnail generation for startup and import (non-blocking)
        if not force_generate and (is_initial_load or defer_on_import):
            tree_item.setIcon(0, self._fixed_canvas_icon(UiIcons().video))
            tree_item.setData(0, self.pending_thumbnail_role, True)
            return
        # For other cases (like on_focus), generate immediately
        if media_info().create_media_thumbnail(str(file_path), str(thumbnail_path)):
            tree_item.setIcon(0, build_icon(thumbnail_path))
        else:
            tree_item.setIcon(0, self._fixed_canvas_icon(UiIcons().video))
        tree_item.setData(0, self.pending_thumbnail_role, False)

    def _iter_tree_items(self, parent: QtWidgets.QTreeWidgetItem):
        """
        Yield all child tree items recursively.
        """
        for index in range(parent.childCount()):
            child = parent.child(index)
            yield child
            yield from self._iter_tree_items(child)

    def on_focus(self):
        """
        Lazily generate deferred video thumbnails when the media tab gains focus.
        """
        super().on_focus()
        root = self.list_view.invisibleRootItem()
        for tree_item in self._iter_tree_items(root):
            if not tree_item.data(0, self.pending_thumbnail_role):
                continue
            media_item = tree_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if not isinstance(media_item, Item):
                tree_item.setData(0, self.pending_thumbnail_role, False)
                continue
            if not Path(media_item.file_path).exists():
                tree_item.setData(0, self.pending_thumbnail_role, False)
                continue
            # Force immediate generation when user focuses on Media tab (not deferred)
            self._set_video_icon(tree_item, media_item, is_initial_load=False, force_generate=True)

    def _collect_pending_thumbnails(self):
        """
        Collect all pending thumbnails from the tree that need to be generated.
        
        :return: List of (file_path, thumbnail_path, media_item) tuples
        """
        items_list = []
        # Safety check: list_view may not be available in tests or early initialization
        if not hasattr(self, 'list_view') or not self.list_view:
            return items_list
        root = self.list_view.invisibleRootItem()
        for tree_item in self._iter_tree_items(root):
            if not tree_item.data(0, self.pending_thumbnail_role):
                continue
            media_item = tree_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if not isinstance(media_item, Item):
                continue
            if not Path(media_item.file_path).exists():
                continue
            thumbnail_path = self.generate_thumbnail_path(media_item)
            items_list.append((media_item.file_path, str(thumbnail_path), media_item))
        return items_list

    def _queue_thumbnail_generation(self):
        """
        Queue pending thumbnails for background generation.
        """
        pending_items = self._collect_pending_thumbnails()
        if not pending_items:
            return
        
        # Stop any existing worker
        if self.thumbnail_generator_thread_name:
            app = Registry().get('application')
            if self.thumbnail_generator_thread_name in app.worker_threads:
                try:
                    worker_info = app.worker_threads[self.thumbnail_generator_thread_name]
                    worker_info['worker'].quit.emit()
                except Exception as e:
                    log.warning(f'Failed to stop existing thumbnail worker: {e}')
        
        # Create and start new worker
        thread_name = f'media_thumbnail_generator_{id(self)}'
        self.thumbnail_generator_worker = ThumbnailGeneratorWorker(pending_items)
        self.thumbnail_generator_worker.thumbnail_generated.connect(self._on_thumbnail_generated)
        self.thumbnail_generator_thread_name = thread_name
        run_thread(self.thumbnail_generator_worker, thread_name, can_start=True)

    def _on_thumbnail_generated(self, file_path, thumbnail_path):
        """
        Update tree item when a thumbnail has been generated in background.
        
        :param file_path: The path to the media file
        :param thumbnail_path: The path to the generated thumbnail
        """
        root = self.list_view.invisibleRootItem()
        for tree_item in self._iter_tree_items(root):
            media_item = tree_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(media_item, Item) and media_item.file_path == file_path:
                # Update icon with the generated thumbnail
                if Path(thumbnail_path).exists():
                    tree_item.setIcon(0, build_icon(thumbnail_path))
                tree_item.setData(0, self.pending_thumbnail_role, False)
                break


    def generate_thumbnail_path(self, item: Item) -> Path:
        """
        Generate a stable path to the media thumbnail.
        """
        file_path = Path(item.file_path)
        thumb_name = item.file_hash or file_path.stem
        return self.service_path / f'{thumb_name}.png'

    def delete_item(self, item):
        """
        Delete any and all thumbnails and things associated with this media item
        """
        delete_file(self.generate_thumbnail_path(item))

    def format_search_result(self, item):
        """
        Format an item for the search results

        :param Item item: An Item to be formatted
        :return list[str, str]: A list of two items containing the full path and a pretty name
        """
        if Path(item.file_path).exists():
            return [item.file_path, Path(item.file_path).name]
        elif item.file_path.startswith('device') or item.file_path.startswith('network'):
            (_, name, _, _) = parse_stream_path(item.file_path)
            return [item.file_path, name]
        else:
            return super().format_search_result(item)

    def get_list(self, media_type=MediaType.Audio):
        """
        Get the list of media, optional select media type.

        :param media_type: Type to get, defaults to audio.
        :return: The media list
        """
        if media_type == MediaType.Audio:
            extensions, _ = get_supported_media_suffix()
        else:
            _, extensions = get_supported_media_suffix()
        clauses = []
        for extension in extensions:
            # Drop the initial * and add to the list of clauses
            clauses.append(Item.file_path.endswith(extension[1:]))
        items = self.manager.get_all_objects(Item, or_(*clauses))
        return [Path(item.file_path) for item in items]

    def on_open_device_stream(self):
        """
        When the open device stream button is clicked, open the stream selector window.
        """
        stream_selector_form = StreamSelectorForm(self.main_window, self.add_device_stream)
        stream_selector_form.exec()
        del stream_selector_form

    def add_device_stream(self, stream):
        """
        Add a device stream based clip to the mediamanager, called from stream_selector_form.

        :param stream: The clip to add.
        """
        self.validate_and_load([str(stream)])

    def on_open_network_stream(self):
        """
        When the open network stream button is clicked, open the stream selector window.
        """
        # if media_add_to_service:
        stream_selector_form = NetworkStreamSelectorForm(self.main_window, self.add_network_stream)
        stream_selector_form.exec()
        del stream_selector_form

    def add_network_stream(self, stream):
        """
        Add a network stream based clip to the mediamanager, called from stream_selector_form.

        :param stream: The clip to add.
        """
        self.validate_and_load([str(stream)])

    def validate_and_load(self, file_paths, target_folder=None):
        """
        Validate media support before importing files into the media library.
        """
        valid_file_paths = []
        unsupported_media = []
        for file_path in file_paths:
            file_path_str = str(file_path)
            # Streams are validated at playback time by the backend.
            if file_path_str.startswith('devicestream:') or file_path_str.startswith('networkstream:'):
                valid_file_paths.append(file_path)
                continue
            path_obj = Path(file_path_str)
            if path_obj.exists():
                supported, error_text = self.media_controller.is_media_supported(path_obj)
                if not supported:
                    unsupported_media.append((file_path_str, error_text))
                    continue
            valid_file_paths.append(file_path)

        if unsupported_media:
            names = '\n'.join([item[0] for item in unsupported_media[:3]])
            error_text = unsupported_media[0][1] or translate(
                'MediaPlugin.MediaItem',
                'The current platform media backend cannot decode the selected media.')
            critical_error_message_box(
                translate('MediaPlugin.MediaItem', 'Unsupported Media on This Platform'),
                translate('MediaPlugin.MediaItem',
                          'These files could not be imported:\n{names}\n\n{details}').format(names=names,
                                                                                               details=error_text)
            )

        if valid_file_paths:
            super().validate_and_load(valid_file_paths, target_folder)
            # Queue newly imported items for background thumbnail generation to avoid UI freeze
            self._queue_thumbnail_generation()
