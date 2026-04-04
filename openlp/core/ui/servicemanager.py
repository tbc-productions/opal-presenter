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
The service manager sets up, loads, saves and manages services.
"""
import html
import json
import shutil
import os
import zipfile
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common import ThemeLevel, delete_file, sha256_file_hash
from openlp.core.common.actions import ActionList, CategoryOrder
from openlp.core.common.applocation import AppLocation
from openlp.core.common.enum import ServiceItemType
from openlp.core.common.i18n import UiStrings, format_time, translate
from openlp.core.common.json import OpenLPJSONDecoder, OpenLPJSONEncoder
from openlp.core.common.mixins import LogMixin, RegistryProperties
from openlp.core.common.registry import Registry, RegistryBase
from openlp.core.lib import build_icon, ItemCapabilities
from openlp.core.lib.exceptions import ValidationError
from openlp.core.lib.plugin import PluginStatus
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.lib.ui import create_widget_action, critical_error_message_box, find_and_set_in_combo_box
from openlp.core.state import State
from openlp.core.threading import ThreadWorker, run_thread
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.media import get_supported_media_suffix
from openlp.core.ui.serviceitemeditform import ServiceItemEditForm
from openlp.core.ui.servicenoteform import ServiceNoteForm
from openlp.core.ui.starttimeform import StartTimeForm
from openlp.core.ui.style import use_alternate_rows
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.toolbar import OpenLPToolbar


class ServiceManagerList(QtWidgets.QTreeWidget):
    """
    Set up key bindings and mouse behaviour for the service list
    """
    def __init__(self, service_manager, parent=None):
        """
        Constructor
        """
        super(ServiceManagerList, self).__init__(parent)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setAlternatingRowColors(use_alternate_rows())
        self.setHeaderHidden(True)
        self.setExpandsOnDoubleClick(False)
        self.service_manager = service_manager
        self._drag_start_pos = None
        self._is_internal_dragging = False
        self._drag_tooltip_label = None
        self.setStyleSheet('QTreeWidget::item { padding: 4px 2px; }')

    def dragEnterEvent(self, event):
        """
        React to a drag enter event from an external source (e.g. Songs or Media library).
        Start a live preview of where the dragged item will land.
        """
        if event.mimeData().hasUrls():
            event.accept()
        elif event.mimeData().hasText():
            plugin_name = event.mimeData().text()
            raw_title = event.mimeData().data('application/x-openlp-item-title')
            item_title = bytes(raw_title).decode('utf-8') if raw_title and not raw_title.isEmpty() else None
            if self.service_manager:
                self.service_manager.cancel_external_drag_preview()
                title = self.service_manager.begin_external_drag_preview(plugin_name, item_title=item_title)
                self.service_manager.update_external_drag_preview(event.pos())
                self._show_drag_tooltip(title)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """
        React to the drag leaving the service list — cancel the external preview and tooltip.
        """
        if self.service_manager:
            self.service_manager.cancel_external_drag_preview()
        self._hide_drag_tooltip()
        event.accept()

    def dragMoveEvent(self, event):
        """
        React to a drag move event from an external source — update the live preview position.
        """
        if event.mimeData().hasUrls():
            event.accept()
        elif event.mimeData().hasText():
            if self.service_manager:
                self.service_manager.update_external_drag_preview(event.pos())
            self._update_drag_tooltip_pos()
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        """
        Capture Key press and respond accordingly.
        :param event:
        """
        if isinstance(event, QtGui.QKeyEvent):
            if self._is_internal_dragging and event.key() == QtCore.Qt.Key.Key_Escape:
                self._cancel_internal_drag()
                event.accept()
                return
            # here accept the event and do something
            if event.key() == QtCore.Qt.Key.Key_Up:
                self.service_manager.on_move_selection_up()
                event.accept()
            elif event.key() == QtCore.Qt.Key.Key_Down:
                self.service_manager.on_move_selection_down()
                event.accept()
            elif event.key() == QtCore.Qt.Key.Key_Right:
                self.service_manager.on_expand_selection()
                event.accept()
            elif event.key() == QtCore.Qt.Key.Key_Left:
                self.service_manager.on_collapse_selection()
                event.accept()
            elif event.key() == QtCore.Qt.Key.Key_Delete:
                self.service_manager.on_delete_from_service()
                event.accept()
            event.ignore()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Handle internal service item reordering via pure mouse events (no QDrag).
        This gives full cursor control and avoids macOS native-drag cursor override.
        """
        left_held = bool(event.buttons() & QtCore.Qt.MouseButton.LeftButton)
        if not left_held:
            if self._is_internal_dragging:
                self._cancel_internal_drag()
            event.ignore()
            return

        if self._is_internal_dragging:
            if self.service_manager:
                self.service_manager.update_internal_drag_preview(event.pos())
            self._update_drag_tooltip_pos()
            event.accept()
            return

        # Check drag-start conditions
        if not self.itemAt(self.mapFromGlobal(QtGui.QCursor.pos())):
            event.ignore()
            return
        if self._drag_start_pos is None or \
                (event.pos() - self._drag_start_pos).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            event.ignore()
            return
        if self.itemAt(event.pos()) is None:
            event.ignore()
            return

        # Begin drag
        if self.service_manager and not self.service_manager.begin_internal_drag():
            event.ignore()
            return
        self._is_internal_dragging = True
        self._show_drag_tooltip(
            self.service_manager.get_internal_drag_title() if self.service_manager else '')
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        if self.service_manager:
            self.service_manager.update_internal_drag_preview(event.pos())
        event.accept()

    def mouseReleaseEvent(self, event):
        """
        Commit the internal drag when the left mouse button is released.
        """
        if self._is_internal_dragging and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._finish_internal_drag(True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _finish_internal_drag(self, commit):
        """Finish the internal drag, committing or cancelling the reorder."""
        if not self._is_internal_dragging:
            return
        self._is_internal_dragging = False
        self._hide_drag_tooltip()
        QtWidgets.QApplication.restoreOverrideCursor()
        if self.service_manager:
            self.service_manager.finish_internal_drag(commit)

    def _cancel_internal_drag(self):
        """Cancel the internal drag and restore original order."""
        self._finish_internal_drag(False)

    def _show_drag_tooltip(self, text):
        """Show or update the floating drag tooltip near the cursor."""
        if self._drag_tooltip_label is None:
            self._drag_tooltip_label = QtWidgets.QLabel(
                text, None, QtCore.Qt.WindowType.ToolTip)
            self._drag_tooltip_label.setAttribute(
                QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        else:
            self._drag_tooltip_label.setText(text)
        self._drag_tooltip_label.adjustSize()
        self._update_drag_tooltip_pos()
        self._drag_tooltip_label.show()

    def _update_drag_tooltip_pos(self):
        """Reposition the drag tooltip to follow the cursor."""
        if self._drag_tooltip_label is not None:
            self._drag_tooltip_label.move(QtGui.QCursor.pos() + QtCore.QPoint(16, 8))

    def _hide_drag_tooltip(self):
        """Hide and destroy the drag tooltip."""
        if self._drag_tooltip_label is not None:
            self._drag_tooltip_label.hide()
            self._drag_tooltip_label.deleteLater()
            self._drag_tooltip_label = None


class Ui_ServiceManager(object):
    """
    UI part of the Service Manager
    """
    def setup_ui(self, widget):
        """
        Define the UI
        :param widget:
        """
        # start with the layout
        self.layout = QtWidgets.QVBoxLayout(widget)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        # Create the top toolbar
        self.toolbar = OpenLPToolbar(self)
        self.toolbar.add_toolbar_action('newService', text=UiStrings().NewService, icon=UiIcons().new,
                                        tooltip=UiStrings().CreateService, triggers=self.on_new_service_clicked)
        self.toolbar.add_toolbar_action('openService', text=UiStrings().OpenService,
                                        icon=UiIcons().open,
                                        tooltip=translate('OpenLP.ServiceManager', 'Load an existing service.'),
                                        triggers=self.on_load_service_clicked)
        self.toolbar.add_toolbar_action('saveService', text=UiStrings().SaveService,
                                        icon=UiIcons().save,
                                        tooltip=translate('OpenLP.ServiceManager', 'Save this service.'),
                                        triggers=self.decide_save_method)
        self.toolbar.add_toolbar_action('saveServiceAs',
                        text=translate('OpenLP.ServiceManager', 'Save As'),
                        icon=UiIcons().save_plus,
                        tooltip=translate('OpenLP.ServiceManager', 'Save Service As'),
                        triggers=self.save_file_as)
        self.toolbar.addSeparator()
        self.theme_label = QtWidgets.QLabel('{theme}:'.format(theme=UiStrings().Theme), widget)
        self.theme_label.setContentsMargins(3, 3, 3, 3)
        self.theme_label.setObjectName('theme_label')
        self.toolbar.add_toolbar_widget(self.theme_label)
        self.theme_combo_box = QtWidgets.QComboBox(self.toolbar)
        self.theme_combo_box.setToolTip(translate('OpenLP.ServiceManager', 'Select a theme for the service.'))
        self.theme_combo_box.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.theme_combo_box.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.theme_combo_box.setMinimumWidth(80)
        self.theme_combo_box.setObjectName('theme_combo_box')
        self.toolbar.add_toolbar_widget(self.theme_combo_box)
        self.unsaved_changes_container = QtWidgets.QWidget(self.toolbar)
        self.unsaved_changes_container.setObjectName('unsaved_changes_container')
        self.unsaved_changes_container.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                                     QtWidgets.QSizePolicy.Policy.Fixed)
        self.unsaved_changes_layout = QtWidgets.QHBoxLayout(self.unsaved_changes_container)
        self.unsaved_changes_layout.setContentsMargins(0, 0, 0, 0)
        self.unsaved_changes_layout.addStretch()
        self.unsaved_changes_label = QtWidgets.QLabel(
            translate('OpenLP.ServiceManager', 'Unsaved changes'), self.unsaved_changes_container)
        self.unsaved_changes_label.setObjectName('unsaved_changes_label')
        unsaved_changes_font = self.unsaved_changes_label.font()
        unsaved_changes_font.setItalic(True)
        self.unsaved_changes_label.setFont(unsaved_changes_font)
        self.unsaved_changes_label.setContentsMargins(0, 0, 4, 0)
        self.unsaved_changes_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight |
                                                QtCore.Qt.AlignmentFlag.AlignVCenter)
        unsaved_changes_opacity = QtWidgets.QGraphicsOpacityEffect(self.unsaved_changes_label)
        unsaved_changes_opacity.setOpacity(0.5)
        self.unsaved_changes_label.setGraphicsEffect(unsaved_changes_opacity)
        self.unsaved_changes_layout.addWidget(self.unsaved_changes_label)
        self.toolbar.add_toolbar_widget(self.unsaved_changes_container)
        self.toolbar.setObjectName('toolbar')
        self.layout.addWidget(self.toolbar)
        # Create the service manager list
        self.service_manager_list = ServiceManagerList(widget)
        self.service_manager_list.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.CurrentChanged |
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked |
            QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed)
        self.service_manager_list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.service_manager_list.customContextMenuRequested.connect(self.context_menu)
        self.service_manager_list.setObjectName('service_manager_list')
        # enable drop
        self.service_manager_list.dropEvent = self.drop_event
        self.layout.addWidget(self.service_manager_list)
        # Add the bottom toolbar
        self.order_toolbar = OpenLPToolbar(widget)
        action_list = ActionList.get_instance()
        action_list.add_category(UiStrings().Service, CategoryOrder.standard_toolbar)
        self.move_top_action = self.order_toolbar.add_toolbar_action(
            'moveTop',
            text=translate('OpenLP.ServiceManager', 'Move to &top'), icon=UiIcons().move_start,
            tooltip=translate('OpenLP.ServiceManager', 'Move item to the top of the service.'),
            can_shortcuts=True, category=UiStrings().Service, triggers=self.on_service_top)
        self.move_top_action.setEnabled(False)
        self.move_up_action = self.order_toolbar.add_toolbar_action(
            'moveUp',
            text=translate('OpenLP.ServiceManager', 'Move &up'), icon=UiIcons().move_up,
            tooltip=translate('OpenLP.ServiceManager', 'Move item up one position in the service.'),
            can_shortcuts=True, category=UiStrings().Service, triggers=self.on_service_up)
        self.move_up_action.setEnabled(False)
        self.move_down_action = self.order_toolbar.add_toolbar_action(
            'moveDown',
            text=translate('OpenLP.ServiceManager', 'Move &down'), icon=UiIcons().move_down,
            tooltip=translate('OpenLP.ServiceManager', 'Move item down one position in the service.'),
            can_shortcuts=True, category=UiStrings().Service, triggers=self.on_service_down)
        self.move_down_action.setEnabled(False)
        self.move_bottom_action = self.order_toolbar.add_toolbar_action(
            'moveBottom',
            text=translate('OpenLP.ServiceManager', 'Move to &bottom'), icon=UiIcons().move_end,
            tooltip=translate('OpenLP.ServiceManager', 'Move item to the end of the service.'),
            can_shortcuts=True, category=UiStrings().Service, triggers=self.on_service_end)
        self.move_bottom_action.setEnabled(False)
        self.order_toolbar.addSeparator()
        self.delete_action = self.order_toolbar.add_toolbar_action(
            'delete', can_shortcuts=True,
              text=translate('OpenLP.ServiceManager', '&Delete From Service'), icon=UiIcons().minus,
            tooltip=translate('OpenLP.ServiceManager', 'Delete the selected item from the service.'),
            triggers=self.on_delete_from_service)
        self.order_toolbar.addSeparator()
        self.expand_collapse_action = self.order_toolbar.add_toolbar_action(
            'expandCollapse', can_shortcuts=True, checked=False,
            text=translate('OpenLP.ServiceManager', '&Expand all'),
              icon=UiIcons().arrow_expand_vertical,
            tooltip=translate('OpenLP.ServiceManager', 'Expand or collapse all the service items.'),
            category=UiStrings().Service, triggers=self.on_toggle_expand_all)
        self.order_toolbar.addSeparator()
        self.make_preview_action = self.order_toolbar.add_toolbar_action(
            'make_preview', can_shortcuts=True,
            text=translate('OpenLP.ServiceManager', 'Show &Preview'), icon=UiIcons().preview,
            tooltip=translate('OpenLP.ServiceManager', 'Send the selected item to Preview.'),
            category=UiStrings().Service,
            triggers=self.make_preview)
        self.make_live_action = self.order_toolbar.add_toolbar_action(
            'make_live', can_shortcuts=True,
            text=translate('OpenLP.ServiceManager', 'Go Live'), icon=UiIcons().live,
            tooltip=translate('OpenLP.ServiceManager', 'Send the selected item to Live.'),
            category=UiStrings().Service,
            triggers=self.on_make_live_action_triggered)
        self.layout.addWidget(self.order_toolbar)
        # Connect up our signals and slots
        self.theme_combo_box.activated.connect(self.on_theme_combo_box_selected)
        self.service_manager_list.doubleClicked.connect(self.on_double_click_live)
        self.service_manager_list.clicked.connect(self.on_single_click_preview)
        self.service_manager_list.itemCollapsed.connect(self.collapsed)
        self.service_manager_list.itemExpanded.connect(self.expanded)
        self.service_manager_list.itemSelectionChanged.connect(self.on_selection_changed)
        # Last little bits of setting up
        self.service_theme = self.settings.value('servicemanager/service theme')
        self.service_path = AppLocation.get_section_data_path('servicemanager')
        self._update_unsaved_changes_indicator()
        # build the drag and drop context menu
        self.dnd_menu = QtWidgets.QMenu()
        self.new_action = self.dnd_menu.addAction(translate('OpenLP.ServiceManager', '&Add New Item'))
        self.new_action.setIcon(UiIcons().edit)
        self.add_to_action = self.dnd_menu.addAction(translate('OpenLP.ServiceManager', '&Add to Selected Item'))
        self.add_to_action.setIcon(UiIcons().edit)
        # build the context menu
        self.menu = QtWidgets.QMenu()
        self.edit_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Edit Item'),
                                                icon=UiIcons().edit, triggers=self.remote_edit)
        self.rename_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Rename...'),
                                                  icon=UiIcons().edit,
                                                  triggers=self.on_service_item_rename)
        self.maintain_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Reorder Item'),
                                                    icon=UiIcons().edit,
                                                    triggers=self.on_service_item_edit_form)
        self.notes_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Notes'),
                                                 icon=UiIcons().notes,
                                                 triggers=self.on_service_item_note_form)
        self.time_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Start Time'),
                                                icon=UiIcons().time, triggers=self.on_start_time_form)
        self.auto_start_action = create_widget_action(self.menu, text='',
                                                      icon=UiIcons().active,
                                                      triggers=self.on_auto_start)
        # Add already existing delete action to the menu.
        self.menu.addAction(self.delete_action)
        self.create_custom_action = create_widget_action(self.menu,
                                                         text=translate('OpenLP.ServiceManager', 'Create New &Custom '
                                                                                                 'Slide'),
                                                         icon=UiIcons().custom,
                                                         triggers=self.create_custom)
        self.menu.addSeparator()
        # Add AutoPlay menu actions
        self.auto_play_slides_menu = QtWidgets.QMenu(translate('OpenLP.ServiceManager', '&Auto play slides'))
        self.menu.addMenu(self.auto_play_slides_menu)
        auto_play_slides_group = QtGui.QActionGroup(self.auto_play_slides_menu)
        auto_play_slides_group.setExclusive(True)
        self.auto_play_slides_loop = create_widget_action(self.auto_play_slides_menu,
                                                          text=translate('OpenLP.ServiceManager', 'Auto play slides '
                                                                                                  '&Loop'),
                                                          checked=False, triggers=self.toggle_auto_play_slides_loop)
        auto_play_slides_group.addAction(self.auto_play_slides_loop)
        self.auto_play_slides_once = create_widget_action(self.auto_play_slides_menu,
                                                          text=translate('OpenLP.ServiceManager', 'Auto play slides '
                                                                                                  '&Once'),
                                                          checked=False, triggers=self.toggle_auto_play_slides_once)
        auto_play_slides_group.addAction(self.auto_play_slides_once)
        self.auto_play_slides_menu.addSeparator()
        self.timed_slide_interval = create_widget_action(self.auto_play_slides_menu,
                                                         text=translate('OpenLP.ServiceManager', '&Delay between '
                                                                                                 'slides'),
                                                         triggers=self.on_timed_slide_interval)
        self.menu.addSeparator()
        self.preview_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', 'Show &Preview'),
                                                   icon=UiIcons().preview, triggers=self.make_preview)
        # Add already existing make live action to the menu.
        self.menu.addAction(self.make_live_action)
        self.menu.addSeparator()
        self.theme_menu = QtWidgets.QMenu(translate('OpenLP.ServiceManager', '&Change Item Theme'))
        self.menu.addMenu(self.theme_menu)
        self.service_manager_list.addActions([self.move_down_action, self.move_up_action, self.make_live_action,
                                              self.move_top_action, self.move_bottom_action,
                                              self.expand_collapse_action])


class ServiceLoadWorker(ThreadWorker):
    """Background worker that parses and extracts a service file."""
    progress_max = QtCore.Signal(int)
    progress_increment = QtCore.Signal(int)
    status = QtCore.Signal(str)
    loaded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, file_path: Path, service_path: Path):
        super().__init__()
        self.file_path = file_path
        self.service_path = service_path

    def start(self):
        try:
            with zipfile.ZipFile(str(self.file_path)) as zip_file:
                zip_infos = zip_file.infolist()
                compressed_size = sum(zip_info.compress_size for zip_info in zip_infos)
                self.progress_max.emit(compressed_size // 1024)
                self.status.emit(
                    translate('OpenLP.ServiceManager', 'Reading service metadata...'))
                service_data = None
                for zip_info in zip_infos:
                    if zip_info.filename == 'service_data.osj' or zip_info.filename.endswith('osj'):
                        with zip_file.open(zip_info, 'r') as json_file:
                            service_data = json_file.read()
                        break
                if not service_data:
                    raise ValidationError(msg='No service data found')
                items = json.loads(service_data, cls=OpenLPJSONDecoder)
                servicefile_version = 2
                for item in items:
                    if 'openlp_core' in item:
                        item = item['openlp_core']
                        servicefile_version = item.get('openlp-servicefile-version', 2)
                        break
                is_broken_file = False
                for zip_info in zip_infos:
                    self.status.emit(
                        translate('OpenLP.ServiceManager', 'Importing file: {file_name}')
                        .format(file_name=Path(zip_info.filename).name))
                    if zip_info.filename == 'service_data.osj' or zip_info.filename.endswith('osj'):
                        self.progress_increment.emit(zip_info.compress_size // 1024)
                        continue
                    if servicefile_version < 3:
                        zip_info.filename = os.path.basename(zip_info.filename.replace('/', os.path.sep))
                    else:
                        fname, ext = os.path.splitext(zip_info.filename)
                        if not ext and os.path.basename(fname).startswith('.'):
                            zip_info.filename = fname.replace('/', '')
                            is_broken_file = True
                    zip_file.extract(zip_info, str(self.service_path))
                    self.progress_increment.emit(zip_info.compress_size // 1024)
                self.loaded.emit({
                    'items': items,
                    'servicefile_version': servicefile_version,
                    'is_broken_file': is_broken_file
                })
        except (NameError, OSError, ValidationError, zipfile.BadZipFile):
            self.failed.emit(str(self.file_path))
        finally:
            self.quit.emit()


class ServiceManager(QtWidgets.QWidget, RegistryBase, Ui_ServiceManager, LogMixin, RegistryProperties):
    """
    Manages the services. This involves taking text strings from plugins and adding them to the service. This service
    can then be zipped up with all the resources used into one OSZ or OSZL file for use on any OpenLP installation.
    Also handles the UI tasks of moving things up and down etc.
    """
    servicemanager_set_item = QtCore.Signal(int)
    servicemanager_set_item_by_uuid = QtCore.Signal(str)
    servicemanager_next_item = QtCore.Signal()
    servicemanager_previous_item = QtCore.Signal()
    servicemanager_delete_item = QtCore.Signal()
    servicemanager_new_file = QtCore.Signal()
    servicemanager_changed = QtCore.Signal()
    theme_update_service = QtCore.Signal()
    SERVICE_ICON_THEME_SETTINGS = {
        'songs': 'servicemanager/theme color song',
        'bibles': 'servicemanager/theme color bible',
        'presentations': 'servicemanager/theme color presentation',
        'images': 'servicemanager/theme color image',
        'media': 'servicemanager/theme color media',
        'custom': 'servicemanager/theme color custom slide',
    }

    def __init__(self, parent=None):
        """
        Sets up the service manager, toolbars, list view, et al.
        """
        super().__init__(parent)
        self._save_lite = False
        self.service_items = []
        self.suffixes = set()
        self.add_media_suffixes()
        self.drop_position = -1
        self.service_id = 0
        # is a new service and has not been saved
        self._modified = False
        self._service_path = None
        self.service_has_all_original_files = True
        self.list_double_clicked = False
        self.servicefile_version = None
        self.tree_widget_items = []
        self._internal_drag_item = None
        self._internal_drag_original_index = None
        self._internal_drag_child = -1
        self._external_drag_item = None
        self._external_drag_plugin_name = None
        self._load_service_file_path = None
        self._pending_loading_status_message = ''
        self._loading_status_timer = QtCore.QTimer(self)
        self._loading_status_timer.setSingleShot(True)
        self._loading_status_timer.setInterval(100)
        self._loading_status_timer.timeout.connect(self._flush_loading_status)
        # repaint_service_list debouncer
        self.repaint_service_list_timer = QtCore.QTimer(self)
        self.repaint_service_list_timer.setInterval(100)
        self.repaint_service_list_timer.timeout.connect(self._try_run_repaint_service_list)
        self.is_running_repaint = False
        self.repaint_select_indexes = (None, None)

    def bootstrap_initialise(self):
        """
        To be called as part of initialisation
        """
        self.setup_ui(self)
        self.set_theme_visibility()
        # Need to use event as called across threads and UI is updated
        self.servicemanager_set_item.connect(self.on_set_item)
        self.servicemanager_set_item_by_uuid.connect(self.set_item_by_uuid)
        self.servicemanager_next_item.connect(self.next_item)
        self.servicemanager_previous_item.connect(self.previous_item)
        self.servicemanager_delete_item.connect(self.delete_item)
        self.servicemanager_new_file.connect(self.new_file)
        # This signal is used to update the theme on the ui thread from the web api thread
        self.theme_update_service.connect(self.on_service_theme_change)
        Registry().register_function('theme_update_list', self.update_theme_list)
        Registry().register_function('theme_level_changed', self.on_theme_level_changed)
        Registry().register_function('config_screen_changed', self.regenerate_service_items)
        Registry().register_function('theme_change_global', self.regenerate_service_items)
        Registry().register_function('theme_change_service', self.regenerate_changed_service_items)
        Registry().register_function('mediaitem_suffix_reset', self.reset_supported_suffixes)
        Registry().register_function('service_manager_repaint_list_icons', self.repaint_list_icons)

    def bootstrap_post_set_up(self):
        """
        Can be set up as a late setup
        """
        self.service_note_form = ServiceNoteForm()
        self.service_item_edit_form = ServiceItemEditForm()
        self.start_time_form = StartTimeForm()

    def _delete_confirmation_dialog(self):
        msg_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question,
                                        translate('OpenLP.ServiceManager', 'Delete item from service'),
                                        translate('OpenLP.ServiceManager', 'Are you sure you want to delete '
                                                  'this item from the service?'),
                                        QtWidgets.QMessageBox.StandardButton(
                                            QtWidgets.QMessageBox.StandardButton.Close |
                                            QtWidgets.QMessageBox.StandardButton.Cancel), self)
        del_button = msg_box.button(QtWidgets.QMessageBox.StandardButton.Close)
        del_button.setText(translate('OpenLP.ServiceManager', '&Delete item'))
        msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Close)
        return msg_box.exec()

    def add_media_suffixes(self):
        """
        Add the suffixes supported by :mod:`openlp.core.ui.media.*player`
        """
        audio, video = get_supported_media_suffix()
        self.suffixes.update(audio)
        self.suffixes.update(video)

    def set_modified(self, modified=True):
        """
        Setter for property "modified". Sets whether or not the current service has been modified.

        :param modified: Indicates if the service has new or removed items.  Used to trigger a remote update.
        """
        if modified:
            self.service_id += 1
        self._modified = modified
        if self._service_path:
            service_file = self._service_path.name
        else:
            service_file = translate('OpenLP.ServiceManager', 'Untitled Service')
        self.main_window.set_service_modified(modified, service_file)
        self._update_unsaved_changes_indicator()
        self.servicemanager_changed.emit()

    def _update_unsaved_changes_indicator(self):
        """
        Show the toolbar indicator using the same modified-state logic as the main window title bar.
        """
        if not hasattr(self, 'unsaved_changes_container'):
            return
        should_show = self._modified
        self.unsaved_changes_container.setVisible(should_show)
        if 'unsaved_changes_container' in self.toolbar.actions_map:
            self.toolbar.actions_map['unsaved_changes_container'].setVisible(should_show)

    def repaint_list_icons(self):
        """
        Repaint the service list after icon color settings are changed.
        """
        self.repaint_service_list(-1, -1)

    @staticmethod
    def _normalise_theme_color(color_text, default):
        """
        Normalize a color to #RRGGBB and use default when invalid.
        """
        color = QtGui.QColor(str(color_text).strip())
        if not color.isValid():
            color = QtGui.QColor(default)
        return color

    def _resolve_service_item_icon_color(self, service_item):
        """
        Resolve the configured icon color for the service item's plugin type.
        """
        plugin_name = str(getattr(service_item, 'name', '')).lower()
        setting_key = self.SERVICE_ICON_THEME_SETTINGS.get(plugin_name)
        if not setting_key:
            return None
        default_color = self.settings.get_default_value(setting_key)
        color_text = self.settings.value(setting_key)
        return self._normalise_theme_color(color_text, default_color)

    def _create_colored_service_icon(self, icon, service_item):
        """
        Create a colored icon for a service item type while preserving the original alpha mask.
        """
        color = self._resolve_service_item_icon_color(service_item)
        if color is None:
            return icon
        base_pixmap = icon.pixmap(80, 80)
        if base_pixmap.isNull():
            return icon
        tinted_pixmap = QtGui.QPixmap(base_pixmap.size())
        tinted_pixmap.setDevicePixelRatio(base_pixmap.devicePixelRatio())
        tinted_pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(tinted_pixmap)
        painter.drawPixmap(0, 0, base_pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted_pixmap.rect(), color)
        painter.end()
        return QtGui.QIcon(tinted_pixmap)

    def is_modified(self):
        """
        Getter for boolean property "modified".
        """
        return self._modified

    def set_file_name(self, file_path):
        """
        Setter for service file.

        :param Path file_path: The service file name
        :rtype: None
        """
        self._service_path = file_path
        self.set_modified(self.is_modified())
        self.settings.setValue('servicemanager/last file', file_path)
        if file_path and file_path.suffix == '.oszl':
            self._save_lite = True
        else:
            self._save_lite = False

    def file_name(self):
        """
        Return the current file name including path.

        :rtype: Path
        """
        return self._service_path

    def short_file_name(self):
        """
        Return the current file name, excluding the path.
        """
        if self._service_path:
            return self._service_path.name

    def reset_supported_suffixes(self):
        """
        Resets the Suffixes list.
        """
        self.suffixes.clear()

    def supported_suffixes(self, suffix_list):
        """
        Adds Suffixes supported to the master list. Called from Plugins.

        :param list[str] | str suffix_list: New suffix(s) to be supported
        """
        if isinstance(suffix_list, str):
            self.suffixes.add(suffix_list)
        else:
            self.suffixes.update(suffix_list)

    def set_theme_visibility(self):
        """Set the visibility of the theme items"""
        visible = self.settings.value('themes/theme level') != ThemeLevel.Global
        self.toolbar.actions_map['theme_combo_box'].setVisible(visible)
        self.toolbar.actions_map['theme_label'].setVisible(visible)

    def on_new_service_clicked(self):
        """
        Create a new service.
        """
        if self.is_modified():
            result = self.save_modified_service()
            if result == QtWidgets.QMessageBox.StandardButton.Cancel:
                return False
            elif result == QtWidgets.QMessageBox.StandardButton.Save:
                if not self.decide_save_method():
                    return False
        if not self.service_items and self.settings.value('advanced/new service message'):
            do_not_show_again = QtWidgets.QCheckBox(translate('OpenLP.Ui', 'Do not show this message again'), None)
            message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Information,
                                                translate('OpenLP.Ui', 'Create a new service.'),
                                                translate('OpenLP.Ui', 'You already have a blank new service.\n'
                                                                       'Add some items to it then press Save'),
                                                QtWidgets.QMessageBox.StandardButton.Ok,
                                                self)
            message_box.setCheckBox(do_not_show_again)
            message_box.exec()
            if message_box.checkBox().isChecked():
                self.settings.setValue('advanced/new service message', False)
        self.new_file()

    def on_load_service_clicked(self, checked):
        """
        Handle the `fileOpenItem` action

        :param bool checked: Not used.
        :rtype: None
        """
        self.load_service()

    def load_service(self, file_path=None):
        """
        Loads the service file and saves the existing one it there is one unchanged.

        :param Path | None file_path: The service file to the loaded.
        """
        if self.is_modified():
            result = self.save_modified_service()
            if result == QtWidgets.QMessageBox.StandardButton.Cancel:
                return False
            elif result == QtWidgets.QMessageBox.StandardButton.Save:
                self.decide_save_method()
        if not file_path:
            file_path, filter_used = FileDialog.getOpenFileName(
                self.main_window,
                translate('OpenLP.ServiceManager', 'Open File'),
                self.settings.value('servicemanager/last directory'),
                translate('OpenLP.ServiceManager', 'OpenLP Service Files (*.osz *.oszl)'))
            if not file_path:
                return False
        self.settings.setValue('servicemanager/last directory', file_path.parent)
        self.load_file_in_thread(file_path)

    def save_modified_service(self):
        """
        Check to see if a service needs to be saved.
        """
        return QtWidgets.QMessageBox.question(self.main_window,
                                              translate('OpenLP.ServiceManager', 'Modified Service'),
                                              translate('OpenLP.ServiceManager',
                                                        'The current service has been modified. Would you like to save '
                                                        'this service?'),
                                              QtWidgets.QMessageBox.StandardButton.Save |
                                              QtWidgets.QMessageBox.StandardButton.Discard |
                                              QtWidgets.QMessageBox.StandardButton.Cancel,
                                              QtWidgets.QMessageBox.StandardButton.Save)

    def on_recent_service_clicked(self, checked):
        """
        Load a recent file as the service triggered by mainwindow recent service list.

        :param bool checked: Not used
        """
        if self.is_modified():
            result = self.save_modified_service()
            if result == QtWidgets.QMessageBox.StandardButton.Cancel:
                return False
            elif result == QtWidgets.QMessageBox.StandardButton.Save:
                self.decide_save_method()
        sender = self.sender()
        self.load_file_in_thread(Path(sender.data()))

    def load_file_in_thread(self, file_path):
        """
        Load an existing service file in a background worker so the UI remains responsive.

        :param Path | str file_path: The service file to load.
        """
        file_path = Path(file_path)
        try:
            if not file_path.exists():
                return False
        except OSError:
            return False
        self._load_service_file_path = file_path
        self.application.set_busy_cursor()
        self._show_loading_status(
            translate('OpenLP.ServiceManager', 'Loading service: {file_name}').format(file_name=file_path.name))
        worker = ServiceLoadWorker(file_path, self.service_path)
        worker.progress_max.connect(self.main_window.display_progress_bar)
        worker.progress_increment.connect(self.main_window.increment_progress_bar)
        worker.status.connect(self._show_loading_status)
        worker.loaded.connect(self._on_load_file_worker_loaded)
        worker.failed.connect(self._on_load_file_worker_failed)
        thread_name = f'service-load-{datetime.now().timestamp()}'
        run_thread(worker, thread_name, can_start=True)
        return True

    def _on_load_file_worker_loaded(self, payload):
        """
        Handle the completed load payload on the UI thread.

        :param dict payload: Parsed service content and metadata from the worker.
        """
        file_path = self._load_service_file_path
        self._loading_status_timer.stop()
        self._pending_loading_status_message = ''
        try:
            self.servicefile_version = payload.get('servicefile_version', 2)
            self.new_file()
            self.process_service_items(payload.get('items', []))
            self.set_file_name(file_path)
            self.main_window.add_recent_file(file_path)
            self.set_modified(False)
            if payload.get('is_broken_file', False):
                self.save_file()
            self.settings.setValue('servicemanager/last file', file_path)
            self._loading_status_timer.stop()
            self._pending_loading_status_message = ''
            self.main_window.show_status_message(
                translate('OpenLP.ServiceManager', 'Loaded service: {file_name}').format(file_name=file_path.name),
                5000)
        except Exception:
            self.log_exception('Problem loading service file {name}'.format(name=file_path))
            critical_error_message_box(
                message=translate('OpenLP.ServiceManager',
                                  'The service file {file_path} could not be loaded because it is either corrupt, '
                                  'inaccessible, or not a valid OpenLP 2 or OpenLP 3 service file.'
                                  ).format(file_path=file_path))
            self.main_window.show_status_message('')
        finally:
            self.main_window.finished_progress_bar()
            self.application.set_normal_cursor()
            self.repaint_service_list(-1, -1)
            self._load_service_file_path = None

    def _on_load_file_worker_failed(self, file_path):
        """
        Handle worker load failures on the UI thread.

        :param str file_path: The file path that failed to load.
        """
        self._loading_status_timer.stop()
        self._pending_loading_status_message = ''
        self.log_exception('Problem loading service file {name}'.format(name=file_path))
        critical_error_message_box(
            message=translate('OpenLP.ServiceManager',
                              'The service file {file_path} could not be loaded because it is either corrupt, '
                              'inaccessible, or not a valid OpenLP 2 or OpenLP 3 service file.'
                              ).format(file_path=file_path))
        self.main_window.finished_progress_bar()
        self.application.set_normal_cursor()
        self.main_window.show_status_message('')
        self.repaint_service_list(-1, -1)
        self._load_service_file_path = None

    def new_file(self):
        """
        Create a blank new service file.
        """
        self.service_manager_list.clear()
        self.service_items = []
        self.set_file_name(None)
        self.service_id += 1
        self.set_modified(False)
        self.settings.setValue('servicemanager/last file', None)
        self.plugin_manager.new_service_created()
        self.live_controller.slide_count = 0
        self.servicemanager_changed.emit()

    def create_basic_service(self):
        """
        Create the initial service array with the base items to be saved.

        :return: service array
        """
        service = []
        # Regarding openlp-servicefile-version:
        #  1: OpenLP 1? Not used.
        #  2: OpenLP 2 (default when loading a service file without openlp-servicefile-version)
        #  3: The new format introduced in OpenLP 3.0.
        # Note that the servicefile-version numbering is not expected to follow the OpenLP version numbering.
        core = {
            'lite-service': self._save_lite,
            'service-theme': self.service_theme,
            'openlp-servicefile-version': 3
        }
        service.append({'openlp_core': core})
        return service

    def get_write_file_list(self):
        """
        Get a list of files used in the service and files that are missing.

        :return: A list of tuples with files used in the service that exist and their sha256-based name in the
                 servicefile, and a list of files that doesn't exists.
        :rtype: (list[(Path,str)], list[str])
        """
        write_list = []
        missing_list = []
        # Run through all items
        for item in self.service_items:
            # If the item has files, see if they exists
            if item['service_item'].uses_file():
                for frame in item['service_item'].get_frames():
                    frame_path = item['service_item'].get_frame_path(frame=frame)
                    if not frame_path.exists():
                        if 'thumbnail' not in frame_path.parts:
                            missing_list.append(str(frame_path))
                        continue
                    if item['service_item'].stored_filename:
                        sha256_file_name = Path(item['service_item'].stored_filename)
                    else:
                        sha256_file_name = Path(sha256_file_hash(frame_path) + frame_path.suffix)
                    bundle = (frame_path, sha256_file_name)
                    if bundle in write_list or str(frame_path) in missing_list:
                        continue
                    write_list.append(bundle)
                # For items that has thumbnails, add them to the list
                if item['service_item'].is_capable(ItemCapabilities.HasThumbnails):
                    thumbnail_path = item['service_item'].get_thumbnail_path()
                    if not thumbnail_path or not Path(thumbnail_path).exists():
                        continue
                    thumbnail_path_parent = Path(thumbnail_path).parent
                    if item['service_item'].is_command():
                        # Run through everything in the thumbnail folder and add pictures
                        for filename in os.listdir(thumbnail_path):
                            # Skip non-pictures
                            if os.path.splitext(filename)[1] not in ['.png', '.jpg', '.jpeg']:
                                continue
                            filename_path = Path(thumbnail_path) / Path(filename)
                            if not filename_path.exists():
                                continue
                            # Create a thumbnail path in the zip/service file
                            service_path = filename_path.relative_to(thumbnail_path_parent)
                            write_list.append((filename_path, service_path))
                    elif item['service_item'].is_image():
                        # Find all image thumbnails and store them
                        # All image thumbnails will be put in a folder named 'thumbnails'
                        for frame in item['service_item'].get_frames():
                            if 'thumbnail' in frame:
                                filename_path = Path(thumbnail_path) / frame['thumbnail']
                                if not filename_path.exists():
                                    continue
                                # Create a thumbnail path in the zip/service file
                                service_path = filename_path.relative_to(thumbnail_path_parent)
                                path_from_tuple = (filename_path, service_path)
                                if path_from_tuple in write_list:
                                    continue
                                write_list.append(path_from_tuple)
            for (audio_path, audio_file_hash) in item['service_item'].background_audio:
                if not audio_file_hash:
                    audio_file_hash = sha256_file_hash(audio_path)
                service_path = audio_file_hash + audio_path.suffix
                audio_path_tuple = (audio_path, service_path)
                if audio_path_tuple in write_list:
                    continue
                write_list.append(audio_path_tuple)
        return write_list, missing_list

    def save_file(self):
        """
        Save the current service file.

        A temporary file is created so that we don't overwrite the existing one and leave a mangled service file should
        there be an error when saving. Audio files are also copied into the service manager directory, and then packaged
        into the zip file.
        """
        file_path = self.file_name()
        self.log_debug('ServiceManager.save_file - {name}'.format(name=file_path))
        self.application.set_busy_cursor()

        service = self.create_basic_service()

        write_list = []
        missing_list = []

        if not self._save_lite:
            try:
                write_list, missing_list = self.get_write_file_list()
            except PermissionError as pe:
                self.main_window.error_message(UiStrings.PermissionError,
                                               UiStrings.UnableToRead + '\n\n' + pe.filename)
                return False
            if missing_list:
                self.application.set_normal_cursor()
                title = translate('OpenLP.ServiceManager', 'Service File(s) Missing')
                message = translate('OpenLP.ServiceManager',
                                    'The following file(s) in the service are missing: {name}\n\n'
                                    'These files will be removed if you continue to save.'
                                    ).format(name='\n\t'.join(missing_list))
                answer = QtWidgets.QMessageBox.critical(self, title, message,
                                                        QtWidgets.QMessageBox.StandardButton(
                                                            QtWidgets.QMessageBox.StandardButton.Ok |
                                                            QtWidgets.QMessageBox.StandardButton.Cancel))
                if answer == QtWidgets.QMessageBox.StandardButton.Cancel:
                    return False
        # Check if item contains a missing file.
        for item in list(self.service_items):
            if not self._save_lite:
                item['service_item'].remove_invalid_frames(missing_list)
                if item['service_item'].missing_frames():
                    self.service_items.remove(item)
                    continue
            service_item = item['service_item'].get_service_repr(self._save_lite)
            # Add the service item to the service.
            service.append({'serviceitem': service_item})
        self.repaint_service_list(-1, -1)
        service_content = json.dumps(service, cls=OpenLPJSONEncoder)
        service_content_size = len(bytes(service_content, encoding='utf-8'))
        total_size = service_content_size
        for local_file_item, zip_file_item in write_list:
            try:
                total_size += local_file_item.stat().st_size
            except FileNotFoundError:
                self.log_exception(f'Local file {local_file_item} not found')
        self.log_debug('ServiceManager.save_file - ZIP contents size is %i bytes' % total_size)
        self.main_window.display_progress_bar(1000)
        try:
            tmp_file_path = str(file_path) + ".saving"
            with zipfile.ZipFile(tmp_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # First we add service contents..
                zip_file.writestr('service_data.osj', service_content)
                self.main_window.increment_progress_bar(service_content_size / total_size * 1000)
                # Finally add all the listed media files.
                for local_file_item, zip_file_item in write_list:
                    zip_file.write(str(local_file_item), str(zip_file_item))
                    self.main_window.increment_progress_bar(local_file_item.stat().st_size / total_size * 1000)
                with suppress(FileNotFoundError):
                    file_path.unlink()
            # Move rather than copy to prevent writing another file if possible
            shutil.move(tmp_file_path, file_path)
            self.settings.setValue('servicemanager/last directory', file_path.parent)
        except (PermissionError, OSError) as error:
            self.log_exception('Failed to save service to disk: {name}'.format(name=file_path))
            self.main_window.error_message(
                translate('OpenLP.ServiceManager', 'Error Saving File'),
                translate('OpenLP.ServiceManager',
                          'There was an error saving your file.\n\n{error}').format(error=error))
            return self.save_file_as()
        self.main_window.finished_progress_bar()
        self.application.set_normal_cursor()
        self.main_window.add_recent_file(file_path)
        self.set_modified(False)
        return True

    def save_file_as(self):
        """
        Get a file name and then call :func:`ServiceManager.save_file` to save the file.
        """
        default_service_enabled = self.settings.value('advanced/default service enabled')
        if default_service_enabled:
            service_day = self.settings.value('advanced/default service day')
            if service_day == 7:
                local_time = datetime.now()
            else:
                service_hour = self.settings.value('advanced/default service hour')
                service_minute = self.settings.value('advanced/default service minute')
                now = datetime.now()
                day_delta = service_day - now.weekday()
                if day_delta < 0:
                    day_delta += 7
                time = now + timedelta(days=day_delta)
                local_time = time.replace(hour=service_hour, minute=service_minute)
            default_pattern = self.settings.value('advanced/default service name')
            default_file_name = format_time(default_pattern, local_time)
        else:
            default_file_name = ''
        default_file_path = Path(default_file_name)
        directory_path = self.settings.value('servicemanager/last directory')
        if directory_path:
            default_file_path = directory_path / default_file_path
        lite_filter = translate('OpenLP.ServiceManager', 'OpenLP Service Files - lite (*.oszl)')
        packaged_filter = translate('OpenLP.ServiceManager', 'OpenLP Service Files (*.osz)')
        if self._service_path and self._service_path.suffix == '.oszl':
            default_filter = lite_filter
        else:
            default_filter = packaged_filter
        # SaveAs from osz to oszl is not valid as the files will be deleted on exit which is not sensible or usable in
        # the long term.
        if self._service_path and self._service_path.suffix == '.oszl' or self.service_has_all_original_files:
            file_path, filter_used = FileDialog.getSaveFileName(
                self.main_window, UiStrings().SaveService, default_file_path,
                '{packaged};; {lite}'.format(packaged=packaged_filter, lite=lite_filter),
                default_filter)
        else:
            file_path, filter_used = FileDialog.getSaveFileName(
                self.main_window, UiStrings().SaveService, default_file_path,
                '{packaged};;'.format(packaged=packaged_filter))
        if not file_path:
            return False
        if filter_used == lite_filter:
            file_path = file_path.with_suffix('.oszl')
        else:
            file_path = file_path.with_suffix('.osz')
        self.set_file_name(file_path)
        self.decide_save_method()

    def decide_save_method(self):
        """
        Determine which type of save method to use.
        """
        if not self.file_name():
            return self.save_file_as()
        return self.save_file()

    def load_file(self, file_path):
        """
        Load an existing service file.

        :param Path file_path: The service file to load.
        """
        # If the file_path is a string, this method will fail. Typecase to Path
        file_path = Path(file_path)
        try:
            if not file_path.exists():
                return False
        except OSError:
            # if the filename, directory name, or volume label syntax is incorrect it can cause an exception
            return False
        service_data = None
        is_broken_file = False
        is_loaded = False
        self.application.set_busy_cursor()
        self._show_loading_status(
            translate('OpenLP.ServiceManager', 'Loading service: {file_name}').format(file_name=file_path.name))
        try:
            # TODO: figure out a way to use the presentation thumbnails from the service file
            with zipfile.ZipFile(str(file_path)) as zip_file:
                compressed_size = 0
                for zip_info in zip_file.infolist():
                    compressed_size += zip_info.compress_size
                self.main_window.display_progress_bar(compressed_size // 1024)
                self._show_loading_status(translate('OpenLP.ServiceManager', 'Reading service metadata...'))
                # First find the osj-file to find out how to handle the file
                for zip_info in zip_file.infolist():
                    # The json file has been called 'service_data.osj' since OpenLP 3.0
                    if zip_info.filename == 'service_data.osj' or zip_info.filename.endswith('osj'):
                        with zip_file.open(zip_info, 'r') as json_file:
                            service_data = json_file.read()
                        break
                if service_data:
                    items = json.loads(service_data, cls=OpenLPJSONDecoder)
                else:
                    raise ValidationError(msg='No service data found')
                # Extract the service file version
                for item in items:
                    if 'openlp_core' in item:
                        item = item['openlp_core']
                        self.servicefile_version = item.get('openlp-servicefile-version', 2)
                        break
                self.log_debug('Service format version: %{ver}'.format(ver=self.servicefile_version))
                for zip_info in zip_file.infolist():
                    self.log_debug('Extract file: {name}'.format(name=zip_info.filename))
                    self._show_loading_status(
                        translate('OpenLP.ServiceManager', 'Importing file: {file_name}')
                        .format(file_name=Path(zip_info.filename).name))
                    # The json file has been called 'service_data.osj' since OpenLP 3.0
                    if zip_info.filename == 'service_data.osj' or zip_info.filename.endswith('osj'):
                        with zip_file.open(zip_info, 'r') as json_file:
                            service_data = json_file.read()
                    else:
                        # Service files from earlier versions than 3 expects that all files are extracted
                        # into the root of the service folder.
                        if self.servicefile_version and self.servicefile_version < 3:
                            zip_info.filename = os.path.basename(zip_info.filename.replace('/', os.path.sep))
                        else:
                            # Fix an issue with service files created in 2.9.x
                            fname, ext = os.path.splitext(zip_info.filename)
                            if not ext and os.path.basename(fname).startswith('.'):
                                zip_info.filename = fname.replace('/', '')
                                is_broken_file = True
                                self.log_debug(f'Fixing file {fname} => {zip_info.filename}')
                        zip_file.extract(zip_info, str(self.service_path))
                    self.main_window.increment_progress_bar(zip_info.compress_size // 1024)
                # Handle the content
                self.new_file()
                self.process_service_items(items)
                self.set_file_name(file_path)
                self.main_window.add_recent_file(file_path)
                self.set_modified(False)
                # If this file was broken due to a bug in 2.9.x, save the file to fix it.
                if is_broken_file:
                    self.save_file()
                self.settings.setValue('servicemanager/last file', file_path)
                is_loaded = True
        except (NameError, OSError, ValidationError, zipfile.BadZipFile):
            self.application.set_normal_cursor()
            self.log_exception('Problem loading service file {name}'.format(name=file_path))
            critical_error_message_box(
                message=translate('OpenLP.ServiceManager',
                                  'The service file {file_path} could not be loaded because it is either corrupt, '
                                  'inaccessible, or not a valid OpenLP 2 or OpenLP 3 service file.'
                                  ).format(file_path=file_path))
        self._loading_status_timer.stop()
        self._pending_loading_status_message = ''
        self.main_window.finished_progress_bar()
        if is_loaded:
            self.main_window.show_status_message(
                translate('OpenLP.ServiceManager', 'Loaded service: {file_name}').format(file_name=file_path.name),
                5000)
        else:
            self.main_window.show_status_message('')
        self.application.set_normal_cursor()
        self.repaint_service_list(-1, -1)

    def process_service_items(self, service_items):
        """
        Process all the array of service items loaded from the saved service

        :param service_items: list of service_items
        """
        for item in service_items:
            self.main_window.increment_progress_bar()
            if 'serviceitem' in item:
                header = item['serviceitem'].get('header', {})
                item_title = header.get('title') or header.get('name') or translate('OpenLP.ServiceManager',
                                                                                      'Service item')
                self._show_loading_status(
                    translate('OpenLP.ServiceManager', 'Importing item: {item_title}')
                    .format(item_title=item_title))
            service_item = ServiceItem()
            if 'openlp_core' in item:
                item = item['openlp_core']
                self._save_lite = item.get('lite-service', False)
                if theme := item.get('service-theme', None):
                    find_and_set_in_combo_box(self.theme_combo_box, theme, set_missing=False)
                    if theme == self.theme_combo_box.currentText():
                        self.service_theme = theme
                        self.settings.setValue('servicemanager/service theme', theme)
                        Registry().execute('theme_change_service')
            else:
                if self._save_lite:
                    service_item.set_from_service(item, version=self.servicefile_version)
                else:
                    service_item.set_from_service(item, self.service_path, self.servicefile_version)
                service_item.validate_item()
                if service_item.is_capable(ItemCapabilities.OnLoadUpdate):
                    new_item = Registry().get(service_item.name).service_load(service_item)
                    if new_item:
                        service_item = new_item
                self.add_service_item(service_item, repaint=False)

    def _show_loading_status(self, message):
        """
        Queue a status message during service loading and only display it after a short delay.

        :param message: The status message to display.
        """
        self._pending_loading_status_message = message
        self._loading_status_timer.start()

    def _flush_loading_status(self):
        """Display the latest queued loading status message."""
        with suppress(Exception):
            self.main_window.show_status_message(self._pending_loading_status_message)

    def load_last_file(self):
        """
        Load the last service item from the service manager when the service was last closed. Can be blank if there was
        no service present.
        """
        file_path = self.settings.value('servicemanager/last file')
        if file_path:
            self.load_file_in_thread(file_path)

    def context_menu(self, point):
        """
        The Right click context menu from the Service item list

        :param point: The location of the cursor.
        """
        item = self.service_manager_list.itemAt(point)
        if item is None:
            return
        if item.parent():
            pos = item.parent().data(0, QtCore.Qt.ItemDataRole.UserRole)
        else:
            pos = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        service_item = self.service_items[pos - 1]
        self.edit_action.setVisible(False)
        self.rename_action.setVisible(False)
        self.create_custom_action.setVisible(False)
        self.maintain_action.setVisible(False)
        self.notes_action.setVisible(False)
        self.time_action.setVisible(False)
        self.auto_start_action.setVisible(False)
        if service_item['service_item'].is_capable(ItemCapabilities.CanEdit) and service_item['service_item'].edit_id:
            self.edit_action.setVisible(True)
        if service_item['service_item'].is_capable(ItemCapabilities.CanEditTitle):
            self.rename_action.setVisible(True)
        if service_item['service_item'].is_capable(ItemCapabilities.CanMaintain):
            self.maintain_action.setVisible(True)
        if item.parent() is None:
            self.notes_action.setVisible(True)
        if service_item['service_item'].is_capable(ItemCapabilities.CanLoop) and  \
                len(service_item['service_item'].get_frames()) > 1:
            self.auto_play_slides_menu.menuAction().setVisible(True)
            self.auto_play_slides_once.setChecked(service_item['service_item'].auto_play_slides_once)
            self.auto_play_slides_loop.setChecked(service_item['service_item'].auto_play_slides_loop)
            self.timed_slide_interval.setChecked(service_item['service_item'].timed_slide_interval > 0)
            if service_item['service_item'].timed_slide_interval > 0:
                delay_suffix = ' {text} s'.format(text=str(service_item['service_item'].timed_slide_interval))
            else:
                delay_suffix = ' ...'
            self.timed_slide_interval.setText(
                translate('OpenLP.ServiceManager', '&Delay between slides') + delay_suffix)
            # TODO for future: make group explains itself more visually
        else:
            self.auto_play_slides_menu.menuAction().setVisible(False)
        if service_item['service_item'].is_capable(ItemCapabilities.HasVariableStartTime) and \
                not service_item['service_item'].is_capable(ItemCapabilities.IsOptical):
            self.time_action.setVisible(True)
        if service_item['service_item'].is_capable(ItemCapabilities.CanAutoStartForLive):
            self.auto_start_action.setVisible(True)
            if service_item['service_item'].will_auto_start:
                self.auto_start_action.setText(translate('OpenLP.ServiceManager', '&Auto Start - active'))
                self.auto_start_action.setIcon(UiIcons().active)
            else:
                self.auto_start_action.setIcon(UiIcons().inactive)
                self.auto_start_action.setText(translate('OpenLP.ServiceManager', '&Auto Start - inactive'))
        if service_item['service_item'].is_text():
            for plugin in State().list_plugins():
                if plugin.name == 'custom' and plugin.status == PluginStatus.Active:
                    self.create_custom_action.setVisible(True)
                    break
        self.theme_menu.menuAction().setVisible(False)
        # Set up the theme menu.
        if service_item['service_item'].is_text() and self.renderer.theme_level == ThemeLevel.Song:
            self.theme_menu.menuAction().setVisible(True)
            # The service item does not have a theme, check the "Default".
            if service_item['service_item'].theme is None:
                theme_action = self.theme_menu.defaultAction()
            else:
                theme_action = self.theme_menu.findChild(QtGui.QAction, service_item['service_item'].theme)
            if theme_action is not None:
                theme_action.setChecked(True)
        self.menu.exec(self.service_manager_list.mapToGlobal(point))

    def on_service_item_note_form(self):
        """
        Allow the service note to be edited
        """
        item = self.find_service_item()[0]
        self.service_note_form.text_edit.setPlainText(self.service_items[item]['service_item'].notes)
        if self.service_note_form.exec():
            self.service_items[item]['service_item'].notes = self.service_note_form.text_edit.toPlainText()
            self.repaint_service_list(item, -1)
            self.set_modified()

    def on_start_time_form(self):
        """
        Opens a dialog to type in service item notes.
        """
        item = self.find_service_item()[0]
        self.start_time_form.item = self.service_items[item]
        if self.start_time_form.exec():
            self.repaint_service_list(item, -1)

    def toggle_auto_play_slides_once(self):
        """
        Toggle Auto play slide once. Inverts auto play once option for the item
        """
        item = self.find_service_item()[0]
        service_item = self.service_items[item]['service_item']
        service_item.auto_play_slides_once = not service_item.auto_play_slides_once
        if service_item.auto_play_slides_once:
            service_item.auto_play_slides_loop = False
            self.auto_play_slides_loop.setChecked(False)
        if service_item.auto_play_slides_once and service_item.timed_slide_interval == 0:
            service_item.timed_slide_interval = self.settings.value('core/loop delay')
        self.set_modified()

    def toggle_auto_play_slides_loop(self):
        """
        Toggle Auto play slide loop.
        """
        item = self.find_service_item()[0]
        service_item = self.service_items[item]['service_item']
        service_item.auto_play_slides_loop = not service_item.auto_play_slides_loop
        if service_item.auto_play_slides_loop:
            service_item.auto_play_slides_once = False
            self.auto_play_slides_once.setChecked(False)
        if service_item.auto_play_slides_loop and service_item.timed_slide_interval == 0:
            service_item.timed_slide_interval = self.settings.value('core/loop delay')
        self.set_modified()

    def on_timed_slide_interval(self):
        """
        Shows input dialog for enter interval in seconds for delay
        """
        item = self.find_service_item()[0]
        service_item = self.service_items[item]['service_item']
        if service_item.timed_slide_interval == 0:
            timed_slide_interval = self.settings.value('core/loop delay')
        else:
            timed_slide_interval = service_item.timed_slide_interval
        timed_slide_interval, ok = QtWidgets.QInputDialog.getInt(self, translate('OpenLP.ServiceManager',
                                                                 'Input delay'),
                                                                 translate('OpenLP.ServiceManager',
                                                                           'Delay between slides in seconds.'),
                                                                 timed_slide_interval, 0, 180, 1)
        if ok:
            service_item.timed_slide_interval = timed_slide_interval
        if service_item.timed_slide_interval != 0 and not service_item.auto_play_slides_loop \
                and not service_item.auto_play_slides_once:
            service_item.auto_play_slides_loop = True
        elif service_item.timed_slide_interval == 0:
            service_item.auto_play_slides_loop = False
            service_item.auto_play_slides_once = False
        self.set_modified()

    def on_auto_start(self):
        """
        Toggles to Auto Start Setting.
        """
        item = self.find_service_item()[0]
        self.service_items[item]['service_item'].will_auto_start = \
            not self.service_items[item]['service_item'].will_auto_start

    def on_service_item_edit_form(self):
        """
        Opens a dialog to edit the service item and update the service display if changes are saved.
        """
        item = self.find_service_item()[0]
        self.service_item_edit_form.set_service_item(self.service_items[item]['service_item'])
        if self.service_item_edit_form.exec():
            self.add_service_item(self.service_item_edit_form.get_service_item(),
                                  replace=item, expand=self.service_items[item]['expanded'])

    def preview_live(self, unique_identifier, row):
        """
        Called by the SlideController to request a preview item be made live and allows the next preview to be updated
        if relevant.

        :param unique_identifier: Reference to the service_item
        :param row: individual row number
        """
        for sitem in self.service_items:
            if sitem['service_item'].unique_identifier == unique_identifier:
                item = self.service_manager_list.topLevelItem(sitem['order'] - 1)
                self.service_manager_list.setCurrentItem(item)
                self.make_live(int(row))
                return

    def next_item(self):
        """
        Called by the SlideController to select the next service item.
        """
        if not self.service_manager_list.selectedItems():
            return
        selected = self.service_manager_list.selectedItems()[0]
        look_for = 0
        service_iterator = QtWidgets.QTreeWidgetItemIterator(self.service_manager_list)
        while service_iterator.value():
            if look_for == 1 and service_iterator.value().parent() is None:
                self.service_manager_list.setCurrentItem(service_iterator.value())
                self.make_live()
                return
            if service_iterator.value() == selected:
                look_for = 1
            service_iterator += 1

    def previous_item(self, last_slide=False):
        """
        Called by the SlideController to select the previous service item.

        :param last_slide: Is this the last slide in the service_item.
        """
        if not self.service_manager_list.selectedItems():
            return
        selected = self.service_manager_list.selectedItems()[0]
        prev_item = None
        prev_item_last_slide = None
        service_iterator = QtWidgets.QTreeWidgetItemIterator(self.service_manager_list)
        while service_iterator.value():
            # Found the selected/current service item
            if service_iterator.value() == selected:
                if last_slide and prev_item_last_slide:
                    # Go to the last slide of the previous service item
                    pos = prev_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                    check_expanded = self.service_items[pos - 1]['expanded']
                    self.service_manager_list.setCurrentItem(prev_item_last_slide)
                    if not check_expanded:
                        self.service_manager_list.collapseItem(prev_item)
                    self.make_live()
                    self.service_manager_list.setCurrentItem(prev_item)
                elif prev_item:
                    # Go to the first slide of the previous service item
                    self.service_manager_list.setCurrentItem(prev_item)
                    self.make_live()
                return
            # Found the previous service item root
            if service_iterator.value().parent() is None:
                prev_item = service_iterator.value()
            # Found the last slide of the previous item
            if service_iterator.value().parent() is prev_item:
                prev_item_last_slide = service_iterator.value()
            # Go to next item in the tree
            service_iterator += 1

    def on_set_item(self, message):
        """
        Called by a signal to select a specific item and make it live usually from remote.
        :param message: The data passed in from a remove message
        """
        self.log_debug(message)
        self.set_item(int(message))

    def set_item(self, index):
        """
        Makes a specific item in the service live.

        :param index: The index of the service item list to be actioned.
        """
        if 0 <= index < self.service_manager_list.topLevelItemCount():
            item = self.service_manager_list.topLevelItem(index)
            self.service_manager_list.setCurrentItem(item)
            self.make_live()

    def set_item_by_uuid(self, unique_identifier):
        """
        Makes a specific item in the service live.  Called directly by the API layer

        :param unique_identifier: Unique Identifier for the item.
        """
        for sitem in self.service_items:
            if sitem['service_item'].unique_identifier == unique_identifier:
                item = self.service_manager_list.topLevelItem(sitem['order'] - 1)
                self.service_manager_list.setCurrentItem(item)
                self.make_live()
                return

    def on_move_selection_up(self):
        """
        Moves the cursor selection up the window. Called by the up arrow.
        """
        item = self.service_manager_list.currentItem()
        item_before = self.service_manager_list.itemAbove(item)
        if item_before is None:
            return
        self.service_manager_list.setCurrentItem(item_before)

    def on_move_selection_down(self):
        """
        Moves the cursor selection down the window. Called by the down arrow.
        """
        item = self.service_manager_list.currentItem()
        item_after = self.service_manager_list.itemBelow(item)
        if item_after is None:
            return
        self.service_manager_list.setCurrentItem(item_after)

    def on_expand_selection(self):
        """
        Expands cursor selection on the window. Called by the right arrow
        """
        item = self.service_manager_list.currentItem()
        # Since we only have 2 levels we find them by checking for children
        if item and item.childCount():
            if not self.service_manager_list.isExpanded(self.service_manager_list.currentIndex()):
                self.service_manager_list.expandItem(item)
                self.service_manager.expanded(item)
                # If not expanded, Expand it
            self.service_manager_list.setCurrentItem(self.service_manager_list.itemBelow(item))
            # Then move selection down to child whether it needed to be expanded or not

    def on_collapse_selection(self):
        """
        Collapses cursor selection on the window Called by the left arrow
        """
        item = self.service_manager_list.currentItem()
        if item is not None:
            # Since we only have 2 levels we find them by checking for children
            if item.childCount():
                if self.service_manager_list.isExpanded(self.service_manager_list.currentIndex()):
                    self.service_manager_list.collapseItem(item)
                    self.service_manager.collapsed(item)
            else:  # If selection is lower level
                self.service_manager_list.collapseItem(item.parent())
                self.service_manager.collapsed(item.parent())
                self.service_manager_list.setCurrentItem(item.parent())

    def on_toggle_expand_all(self, checked):
        """
        Expand or collapse all service items depending on the toggle state.

        :param checked: True to expand all, False to collapse all.
        """
        if checked:
            self.expand_collapse_action.setText(translate('OpenLP.ServiceManager', '&Collapse all'))
            self.expand_collapse_action.setIcon(UiIcons().arrow_collapse_vertical)
            for item in self.service_items:
                item['expanded'] = True
            self.service_manager_list.expandAll()
        else:
            self.expand_collapse_action.setText(translate('OpenLP.ServiceManager', '&Expand all'))
            self.expand_collapse_action.setIcon(UiIcons().arrow_expand_vertical)
            for item in self.service_items:
                item['expanded'] = False
            self.service_manager_list.collapseAll()

    def collapsed(self, item):
        """
        Record if an item is collapsed. Used when repainting the list to get the correct state.

        :param item: The service item to be checked
        """
        pos = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        # Only set root items as collapsed, and since we only have 2 levels we find them by checking for children
        if item.childCount():
            self.service_items[pos - 1]['expanded'] = False



    def expanded(self, item):
        """
        Record if an item is collapsed. Used when repainting the list to get the correct state.

        :param item: The service item to be checked
        """
        pos = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        # Only set root items as expanded, and since we only have 2 levels we find them by checking for children
        if item.childCount():
            self.service_items[pos - 1]['expanded'] = True

    def on_service_top(self):
        """
        Move the current ServiceItem to the top of the list.
        """
        item, child = self.find_service_item()
        if item < len(self.service_items) and item != -1:
            temp = self.service_items[item]
            self.service_items.remove(self.service_items[item])
            self.service_items.insert(0, temp)
            self.repaint_service_list(0, child)
            self.set_modified()

    def on_service_up(self):
        """
        Move the current ServiceItem one position up in the list.
        """
        item, child = self.find_service_item()
        if item > 0:
            temp = self.service_items[item]
            self.service_items.remove(self.service_items[item])
            self.service_items.insert(item - 1, temp)
            self.repaint_service_list(item - 1, child)
            self.set_modified()

    def on_service_down(self):
        """
        Move the current ServiceItem one position down in the list.
        """
        item, child = self.find_service_item()
        if item < len(self.service_items) and item != -1:
            temp = self.service_items[item]
            self.service_items.remove(self.service_items[item])
            self.service_items.insert(item + 1, temp)
            self.repaint_service_list(item + 1, child)
            self.set_modified()

    def on_service_end(self):
        """
        Move the current ServiceItem to the bottom of the list.
        """
        item, child = self.find_service_item()
        if item < len(self.service_items) and item != -1:
            temp = self.service_items[item]
            self.service_items.remove(self.service_items[item])
            self.service_items.insert(len(self.service_items), temp)
            self.repaint_service_list(len(self.service_items) - 1, child)
            self.set_modified()

    def on_delete_from_service(self):
        """
        Remove the current ServiceItem from the list.
        """
        need_confirmation: bool = self.settings.value('advanced/delete service item confirmation')
        if (
            not need_confirmation or
            self._delete_confirmation_dialog() == QtWidgets.QMessageBox.Close
        ):
            self.delete_item()

    def repaint_service_list(self, service_item: int, service_item_child: int):
        """
        Clear the existing service list and prepaint all the items. This is used when moving items as the move takes
        place in a supporting list, and when regenerating all the items due to theme changes.

        :param service_item: The item which changed. (int)
        :param service_item_child: The child of the ``service_item``, which will be selected. (int)
        """
        self.repaint_select_indexes = (service_item, service_item_child)
        self._try_run_repaint_service_list()

    def _try_run_repaint_service_list(self):
        if not self.is_running_repaint:
            self.repaint_service_list_timer.stop()
            self._repaint_service_list()
            if self.repaint_select_indexes[0] is not None and not self.is_internal_drag_active():
                self._select_item_after_repaint(self.repaint_select_indexes[0], self.repaint_select_indexes[1])
                self.repaint_select_indexes = (None, None)
            elif self.is_internal_drag_active():
                self.repaint_select_indexes = (None, None)
        else:
            # Trying again later
            self.repaint_service_list_timer.stop()
            self.repaint_service_list_timer.start()

    def _select_item_after_repaint(self, service_item: int, service_item_child: int):
        """
        Selects the list active item after repaint.

        :param service_item: The item which changed. (int)
        :param service_item_child: The child of the ``service_item``, which will be selected. (int)
        """
        for item_index, item in enumerate(self.service_items):
            service_item_from_item = item['service_item']
            for slide_index, slide in enumerate(service_item_from_item.get_frames()):
                if service_item == item_index:
                    try:
                        if item['expanded'] and service_item_child == slide_index:
                            self.service_manager_list.setCurrentIndex(
                                self.service_manager_list.model().index(service_item, 0).child(service_item_child, 0)
                            )
                        elif service_item_child == -1:
                            self.service_manager_list.setCurrentIndex(
                                self.service_manager_list.model().index(service_item, 0)
                            )
                    except RuntimeError:
                        pass

    def _repaint_service_list(self) -> bool:
        """
        Clear the existing service list and prepaint all the items. This is used when moving items as the move takes
        place in a supporting list, and when regenerating all the items due to theme changes.

        :returns: Whether the call should be scheduled to be run again due to fail.
        """
        # Correct order of items in array
        self.is_running_repaint = True
        count = 1
        self.service_has_all_original_files = True
        for item in self.service_items:
            item['order'] = count
            count += 1
            if not item['service_item'].has_original_file_path:
                self.service_has_all_original_files = False
        # Repaint the screen
        self.tree_widget_items = []
        self.service_manager_list.clearSelection()
        self.service_manager_list.clear()
        for _, item in enumerate(self.service_items):
            service_item_from_item = item['service_item']
            tree_widget_item = QtWidgets.QTreeWidgetItem(self.service_manager_list)
            self.tree_widget_items.append(tree_widget_item)
            is_dragged_item = item is self._internal_drag_item or item is self._external_drag_item
            if service_item_from_item.is_valid:
                themed_icon = self._create_colored_service_icon(service_item_from_item.icon, service_item_from_item)
                icon = themed_icon.pixmap(80, 80).toImage()
                icon = icon.scaled(80, 80, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                   QtCore.Qt.TransformationMode.SmoothTransformation)
                if service_item_from_item.notes:
                    overlay = UiIcons().notes.pixmap(40, 40).toImage()
                    overlay = overlay.scaled(40, 40, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                             QtCore.Qt.TransformationMode.SmoothTransformation)
                    painter = QtGui.QPainter(icon)
                    painter.drawImage(0, 0, overlay)
                    painter.end()
                    tree_widget_item.setIcon(0, build_icon(icon))
                elif service_item_from_item.temporary_edit:
                    overlay = QtGui.QImage(UiIcons().upload)
                    overlay = overlay.scaled(40, 40, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                             QtCore.Qt.TransformationMode.SmoothTransformation)
                    painter = QtGui.QPainter(icon)
                    painter.drawImage(40, 0, overlay)
                    painter.end()
                    tree_widget_item.setIcon(0, build_icon(icon))
                else:
                    tree_widget_item.setIcon(0, themed_icon)
            else:
                tree_widget_item.setIcon(0, UiIcons().delete)
            tree_widget_item.setText(0, service_item_from_item.get_display_title())
            tips = []
            if service_item_from_item.temporary_edit:
                text1 = translate('OpenLP.ServiceManager', 'Edit')
                text2 = translate('OpenLP.ServiceManager', 'Service copy only')
                tips.append('<strong>{text1}:</strong> <em>{text2}</em>'.format(text1=text1, text2=text2))
            if service_item_from_item.theme and service_item_from_item.theme != -1:
                text = translate('OpenLP.ServiceManager', 'Slide theme')
                tips.append('<strong>{text1}:</strong> <em>{text2}</em>'.format(text1=text,
                                                                                text2=service_item_from_item.theme))
            if service_item_from_item.notes:
                text1 = translate('OpenLP.ServiceManager', 'Notes')
                text2 = html.escape(service_item_from_item.notes)
                tips.append('<strong>{text1}: </strong> {text2}'.format(text1=text1, text2=text2))
            if item['service_item'].is_capable(ItemCapabilities.HasVariableStartTime):
                tips.append(item['service_item'].get_media_time())
            if item['service_item'].is_capable(ItemCapabilities.HasMetaData):
                for meta in item['service_item'].metadata:
                    tips.append(meta)
            tree_widget_item.setToolTip(0, '<br>'.join(tips))
            tree_widget_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item['order'])
            tree_widget_item.setSelected(item['selected'] and not is_dragged_item)
            if is_dragged_item:
                dragged_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
                dragged_text_color.setAlpha(140)
                tree_widget_item.setForeground(0, QtGui.QBrush(dragged_text_color))
            # Add the children to their parent tree_widget_item.
            for slide_index, slide in enumerate(service_item_from_item.get_frames()):
                try:
                    child = QtWidgets.QTreeWidgetItem(tree_widget_item)
                    # prefer to use a display_title
                    if service_item_from_item.is_capable(ItemCapabilities.HasDisplayTitle) or \
                            service_item_from_item.service_item_type is not ServiceItemType.Text:
                        text = slide['title'].replace('\n', ' ')
                    else:
                        text = service_item_from_item.get_rendered_frame(slide_index, clean=True)
                    child.setText(0, text[:40])
                    child.setData(0, QtCore.Qt.ItemDataRole.UserRole, slide_index)
                    if is_dragged_item:
                        child_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
                        child_text_color.setAlpha(140)
                        child.setForeground(0, QtGui.QBrush(child_text_color))
                except RuntimeError:
                    # it's probably a "wrapped C/C++ object of type QTreeWidgetItem has been deleted" due to
                    # consecutive/parallel repaint_service_list execution. We've added some mitigation to avoid this
                    # to happen, but it for any reason it happens again, we'll silent it and try to repaint the list
                    # again (to avoid a broken list presented to the user).
                    self.is_running_repaint = False
                    return True
            tree_widget_item.setExpanded(item['expanded'])
        self.is_running_repaint = False
        self._update_move_actions()
        return False

    def clean_up(self):
        """
        Empties the service_path of temporary files on system exit.
        """
        if not hasattr(self, 'service_path'):
            return
        for file_name in os.listdir(self.service_path):
            file_path = Path(self.service_path, file_name)
            if os.path.isdir(file_path):
                shutil.rmtree(file_path, True)
            else:
                delete_file(file_path)

    def on_theme_combo_box_selected(self, current_index):
        """
        Set the theme for the current service.

        :param current_index: The combo box index for the selected item
        """
        self.service_theme = self.theme_combo_box.currentText()
        self.settings.setValue('servicemanager/service theme', self.service_theme)
        Registry().execute('theme_change_service')

    def on_theme_level_changed(self):
        """
        The theme may have changed in the settings dialog so make sure the theme combo box is in the correct state.
        """
        self.set_theme_visibility()
        self.regenerate_service_items()

    def on_service_theme_change(self):
        """
        Set the theme for the current service from the settings
        """
        self.service_theme = self.settings.value('servicemanager/service theme')
        find_and_set_in_combo_box(self.theme_combo_box, self.service_theme)
        Registry().execute('theme_change_service')

    def regenerate_changed_service_items(self):
        """
        Regenerate the changed service items, marking the service as unsaved.
        """
        self.regenerate_service_items(changed=True)

    def regenerate_service_items(self, changed=False):
        """
        Rebuild the service list as things have changed and a repaint is the easiest way to do this.

        :param changed: True if the list has changed for new / removed items. False for a theme change.
        """
        self.application.set_busy_cursor()
        was_modified = self.is_modified()
        # force reset of renderer as theme data has changed
        self.service_has_all_original_files = True
        if self.service_items:
            for item in self.service_items:
                item['selected'] = False
            service_iterator = QtWidgets.QTreeWidgetItemIterator(self.service_manager_list)
            selected_item = None
            while service_iterator.value():
                if service_iterator.value().isSelected():
                    selected_item = service_iterator.value()
                service_iterator += 1
            if selected_item is not None:
                if selected_item.parent() is None:
                    pos = selected_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                else:
                    pos = selected_item.parent().data(0, QtCore.Qt.ItemDataRole.UserRole)
                self.service_items[pos - 1]['selected'] = True
            temp_service_items = self.service_items
            self.service_manager_list.clear()
            self.service_items = []
            self.is_new = True
            for item in temp_service_items:
                self.add_service_item(item['service_item'], False, expand=item['expanded'], repaint=False,
                                      selected=item['selected'])
            # Set to False as items may have changed rendering does not impact the saved song so True may also be valid
            self.set_modified(changed or was_modified)
            # Repaint it once only at the end
            self.repaint_service_list(-1, -1)
        self.application.set_normal_cursor()

    def replace_service_item(self, new_item):
        """
        Using the service item passed replace the one with the same edit id if found.

        :param new_item: a new service item to up date an existing one.
        """
        for item_count, item in enumerate(self.service_items):
            if item['service_item'].edit_id == new_item.edit_id and item['service_item'].name == new_item.name:
                new_item.merge(item['service_item'])
                item['service_item'] = new_item
                self.repaint_service_list(item_count + 1, 0)
                self.live_controller.replace_service_manager_item(new_item)
                self.set_modified()

    def add_service_item(self, item, rebuild=False, expand=None, replace=-1, repaint=True, selected=False,
                         position=-1):
        """
        Add a Service item to the list

        :param item: Service Item to be added
        :param rebuild: Do we need to rebuild the live display (Default False)
        :param expand: Override the default expand settings. (Tristate)
        :param replace: The service item to be replaced
        :param repaint: Do we need to repaint the service item list (Default True)
        :param selected: Has the item been selected (Default False)
        :param position: The position where the item is dropped (Default -1)
        """
        # if not passed set to config value
        if expand is None:
            expand = self.settings.value('advanced/expand service item')
        item.from_service = True
        if position != -1:
            self.drop_position = position
        if replace > -1:
            item.merge(self.service_items[replace]['service_item'])
            self.service_items[replace]['service_item'] = item
            self.repaint_service_list(replace, -1)
            self.live_controller.replace_service_manager_item(item)
        else:
            item.render_text_items()
            # nothing selected for dnd
            if self.drop_position == -1:
                if isinstance(item, list):
                    for ind_item in item:
                        self.service_items.append({'service_item': ind_item,
                                                   'order': len(self.service_items) + 1,
                                                   'expanded': expand, 'selected': selected})
                else:
                    self.service_items.append({'service_item': item,
                                               'order': len(self.service_items) + 1,
                                               'expanded': expand, 'selected': selected})
                if repaint:
                    self.repaint_service_list(len(self.service_items) - 1, -1)
            else:
                self.service_items.insert(self.drop_position,
                                          {'service_item': item, 'order': self.drop_position,
                                           'expanded': expand, 'selected': selected})
                self.repaint_service_list(self.drop_position, -1)
            # if rebuilding list make sure live is fixed.
            if rebuild:
                self.live_controller.replace_service_manager_item(item)
        self.drop_position = -1
        self.set_modified()

    def delete_item(self):
        """
        Remove the current item from the service.
        """
        item = self.find_service_item()[0]
        if item != -1:
            self.service_items.remove(self.service_items[item])
            self.repaint_service_list(item - 1, -1)
            self.set_modified()
            self.servicemanager_changed.emit()

    def make_preview(self):
        """
        Send the current item to the Preview slide controller
        """
        self.application.set_busy_cursor()
        try:
            item, child = self.find_service_item()
            if item < 0 or item >= len(self.service_items):
                return
            if self.service_items[item]['service_item'].is_valid:
                self.preview_controller.add_service_manager_item(self.service_items[item]['service_item'], child)
            else:
                critical_error_message_box(translate('OpenLP.ServiceManager', 'Missing Display Handler'),
                                           translate('OpenLP.ServiceManager',
                                                     'Your item cannot be displayed as there is no handler to display '
                                                     'it'))
        finally:
            self.application.set_normal_cursor()

    def get_service_item(self):
        """
        Send the current item to the Preview slide controller
        """
        item = self.find_service_item()[0]
        if item == -1:
            return False
        else:
            return self.service_items[item]['service_item']

    def on_double_click_live(self):
        """
        Send the current item to the Live slide controller but triggered by a tablewidget click event.
        """
        self.list_double_clicked = True
        self.make_live()

    def on_single_click_preview(self):
        """
        If single click previewing is enabled, and triggered by a tablewidget click event,
        start a timeout to verify a double-click hasn't triggered.
        """
        if self.settings.value('advanced/single click service preview'):
            if not self.list_double_clicked:
                # If a double click has not registered start a timer, otherwise wait for the existing timer to finish.
                QtCore.QTimer.singleShot(QtWidgets.QApplication.instance().doubleClickInterval(),
                                         self.on_single_click_preview_timeout)

    def on_single_click_preview_timeout(self):
        """
        If a single click ok, but double click not triggered, send the current item to the Preview slide controller.
        """
        if self.list_double_clicked:
            # If a double click has registered, clear it.
            self.list_double_clicked = False
        else:
            # Otherwise preview the item.
            self.make_preview()

    def make_live(self, row=-1):
        """
        Send the current item to the Live slide controller

        :param row: Row number to be displayed if from preview. -1 is passed if the value is not set
        """
        item, child = self.find_service_item()
        # No items in service
        if item == -1 or item >= len(self.service_items):
            return
        if row != -1:
            child = row
        self.application.set_busy_cursor()
        if self.service_items[item]['service_item'].is_valid:
            self.servicemanager_changed.emit()
            self.live_controller.add_service_manager_item(self.service_items[item]['service_item'], child)
            if self.settings.value('core/auto preview'):
                item += 1
                if self.service_items and item < len(self.service_items) and \
                        self.service_items[item]['service_item'].is_capable(ItemCapabilities.CanPreview):
                    self.preview_controller.add_service_manager_item(self.service_items[item]['service_item'], 0)
                    self.live_controller.preview_widget.setFocus()
        else:
            critical_error_message_box(translate('OpenLP.ServiceManager', 'Missing Display Handler'),
                                       translate('OpenLP.ServiceManager',
                                                 'Your item cannot be displayed as the plugin required to display it '
                                                 'is missing or inactive'))
        self.application.set_normal_cursor()

    def remote_edit(self):
        """
        Triggers a remote edit to a plugin to allow item to be edited.
        """
        item = self.find_service_item()[0]
        if self.service_items[item]['service_item'].is_capable(ItemCapabilities.CanEdit):
            new_item = Registry().get(self.service_items[item]['service_item'].name). \
                on_remote_edit(self.service_items[item]['service_item'].edit_id)
            if new_item:
                self.add_service_item(new_item, replace=item)

    def on_service_item_rename(self):
        """
        Opens a dialog to rename the service item.
        """
        item = self.find_service_item()[0]
        if not self.service_items[item]['service_item'].is_capable(ItemCapabilities.CanEditTitle):
            return
        title = self.service_items[item]['service_item'].title
        title, ok = QtWidgets.QInputDialog.getText(self, translate('OpenLP.ServiceManager', 'Rename item title'),
                                                   translate('OpenLP.ServiceManager', 'Title:'),
                                                   QtWidgets.QLineEdit.EchoMode.Normal, self.tr(title))
        if ok:
            self.service_items[item]['service_item'].title = title
            self.repaint_service_list(item, -1)
            self.set_modified()

    def create_custom(self):
        """
        Saves the current text item as a custom slide and opens the custom tab (if is not open)
        """
        item = self.find_service_item()[0]
        Registry().execute('custom_create_from_service', self.service_items[item]['service_item'])
        for pos in range(1, self.main_window.media_tool_box.count()):
            if self.main_window.media_tool_box.itemText(pos) == Registry().execute('custom_visible_name')[0]:
                self.main_window.media_tool_box.setItemEnabled(pos, True)
                self.main_window.media_tool_box.setCurrentIndex(pos)

    def find_service_item(self):
        """
        Finds the first selected ServiceItem in the list and returns the position of the service_item_from_item and its
        selected child item. For example, if the third child item (in the Slidecontroller known as slide) in the
        second service item is selected this will return::

            (1, 2)
        """
        items = self.service_manager_list.selectedItems()
        service_item = -1
        service_item_child = -1
        for item in items:
            parent_item = item.parent()
            if parent_item is None:
                service_item = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            else:
                service_item = parent_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                service_item_child = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if service_item is None:
                break
            # Adjust for zero based arrays.
            service_item -= 1
            # Only process the first item on the list for this method.
            break
        return service_item, service_item_child

    def on_selection_changed(self):
        """
        Called whenever the selection in the service manager list changes. Updates the enabled state of the
        move toolbar buttons.
        """
        self._update_move_actions()

    def _update_move_actions(self):
        """
        Enable or disable the four move toolbar buttons based on whether a top-level service item is selected
        and whether movement in each direction is possible.
        """
        if not hasattr(self, 'move_top_action'):
            return
        item, _ = self.find_service_item()
        count = len(self.service_items)
        has_selection = item != -1
        at_top = item == 0
        at_bottom = item == count - 1
        self.move_top_action.setEnabled(has_selection and not at_top)
        self.move_up_action.setEnabled(has_selection and not at_top)
        self.move_down_action.setEnabled(has_selection and not at_bottom)
        self.move_bottom_action.setEnabled(has_selection and not at_bottom)

    def is_internal_drag_active(self):
        return self._internal_drag_item is not None

    def is_external_drag_active(self):
        return self._external_drag_item is not None

    def get_internal_drag_title(self):
        """Return the display title of the item currently being dragged internally."""
        if not self.is_internal_drag_active():
            return ''
        try:
            return self._internal_drag_item['service_item'].get_display_title()
        except Exception:
            return ''

    # External drag preview constants (plugin name → friendly display title)
    _PLUGIN_DISPLAY_NAMES = {
        'songs': 'Song',
        'bibles': 'Bible Verse',
        'presentations': 'Presentation',
        'images': 'Image',
        'media': 'Media',
        'custom': 'Custom Slide',
        'alerts': 'Alert',
    }

    def begin_external_drag_preview(self, plugin_name, item_title=None):
        """
        Create a placeholder service item for an incoming external drag and insert it at the end
        of the service list to provide a live drop-position preview.

        :param plugin_name: The plugin name from the drag MIME data (e.g. 'songs', 'images').
        :param item_title: The actual title of the item being dragged, if available.
        :returns: The display title of the placeholder (for the drag tooltip).
        """
        from openlp.core.lib.serviceitem import ServiceItem
        placeholder = ServiceItem()
        placeholder.name = plugin_name
        placeholder.add_icon()
        placeholder.add_capability(ItemCapabilities.CanEditTitle)
        placeholder.title = item_title or self._PLUGIN_DISPLAY_NAMES.get(plugin_name, plugin_name.title())
        insert_idx = len(self.service_items)
        self._external_drag_item = {
            'service_item': placeholder,
            'order': insert_idx + 1,
            'expanded': False,
            'selected': False,
        }
        self._external_drag_plugin_name = plugin_name
        self.service_items.append(self._external_drag_item)
        self.repaint_service_list(insert_idx, -1)
        return placeholder.get_display_title()

    def update_external_drag_preview(self, pos):
        """Move the external drag placeholder to the position under the cursor."""
        if not self.is_external_drag_active():
            return
        target_index = self._get_internal_drag_target_index(pos)
        self._move_external_drag_preview(target_index)

    def _move_external_drag_preview(self, target_index):
        current_index = self._get_external_drag_item_index()
        if current_index == -1:
            return
        insert_index = max(0, min(target_index, len(self.service_items)))
        if insert_index > current_index:
            insert_index -= 1
        if insert_index == current_index:
            return
        dragged_item = self.service_items.pop(current_index)
        self.service_items.insert(insert_index, dragged_item)
        self.repaint_service_list(insert_index, -1)

    def _get_external_drag_item_index(self):
        if not self.is_external_drag_active():
            return -1
        for index, item in enumerate(self.service_items):
            if item is self._external_drag_item:
                return index
        return -1

    def cancel_external_drag_preview(self):
        """Remove the external drag placeholder without committing."""
        if not self.is_external_drag_active():
            return
        idx = self._get_external_drag_item_index()
        self._external_drag_item = None
        self._external_drag_plugin_name = None
        if idx != -1:
            self.service_items.pop(idx)
        self.repaint_service_list(-1, -1)

    def finish_external_drag_preview(self):
        """
        Commit the external drag: record the placeholder's position as drop_position, then remove
        the placeholder so the real item can be inserted at that index by add_service_item.
        """
        if not self.is_external_drag_active():
            return
        idx = self._get_external_drag_item_index()
        self._external_drag_item = None
        self._external_drag_plugin_name = None
        if idx != -1:
            self.service_items.pop(idx)
            self.drop_position = idx

    def begin_internal_drag(self):
        start_pos, child = self.find_service_item()
        if start_pos == -1 or start_pos >= len(self.service_items):
            return False
        self._internal_drag_item = self.service_items[start_pos]
        self._internal_drag_original_index = start_pos
        self._internal_drag_child = child
        self.repaint_service_list(start_pos, child)
        return True

    def update_internal_drag_preview(self, pos):
        if not self.is_internal_drag_active():
            return
        target_index = self._get_internal_drag_target_index(pos)
        self._move_internal_drag_preview(target_index)

    def cancel_internal_drag_preview(self):
        if self.is_internal_drag_active():
            self.finish_internal_drag(False)

    def finish_internal_drag(self, is_drop_complete):
        if not self.is_internal_drag_active():
            return
        current_index = self._get_internal_drag_item_index()
        original_index = self._internal_drag_original_index
        child = self._internal_drag_child
        if current_index == -1:
            current_index = original_index
        if not is_drop_complete and current_index != original_index:
            dragged_item = self.service_items.pop(current_index)
            self.service_items.insert(original_index, dragged_item)
            current_index = original_index
        has_moved = current_index != original_index
        self._internal_drag_item = None
        self._internal_drag_original_index = None
        self._internal_drag_child = -1
        self.repaint_service_list(current_index, child)
        if is_drop_complete and has_moved:
            self.set_modified()

    def _get_internal_drag_item_index(self):
        if not self.is_internal_drag_active():
            return -1
        for index, item in enumerate(self.service_items):
            if item is self._internal_drag_item:
                return index
        return -1

    def _get_internal_drag_target_index(self, pos):
        target_item = self.service_manager_list.itemAt(pos)
        if target_item is None:
            return len(self.service_items)
        target_item = target_item if target_item.parent() is None else target_item.parent()
        target_index = get_parent_item_data(target_item) - 1
        if pos.y() > self.service_manager_list.visualItemRect(target_item).center().y():
            target_index += 1
        return target_index

    def _move_internal_drag_preview(self, target_index):
        current_index = self._get_internal_drag_item_index()
        if current_index == -1:
            return
        insert_index = max(0, min(target_index, len(self.service_items)))
        if insert_index > current_index:
            insert_index -= 1
        if insert_index == current_index:
            return
        dragged_item = self.service_items.pop(current_index)
        self.service_items.insert(insert_index, dragged_item)
        self.repaint_service_list(insert_index, self._internal_drag_child)

    def drop_event(self, event):
        """
        Receive drop event and trigger an internal event to get the plugins to build and push the correct service item.
        The drag event payload carries the plugin name

        :param event: Handle of the event passed
        """
        link = event.mimeData()
        if link.hasUrls():
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            for url in link.urls():
                file_path = Path(url.toLocalFile())
                if file_path.suffix == '.osz':
                    self.load_service(file_path)
                elif file_path.suffix == '.oszl':
                    # todo correct
                    self.load_service(file_path)
        elif link.hasText():
            plugin = link.text()
            self.service_manager_list._hide_drag_tooltip()
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            replace = False
            if self.is_external_drag_active():
                # Preview was active — use the placeholder's position as drop target
                self.finish_external_drag_preview()
            else:
                # Fallback: no preview was active, determine position from cursor
                item = self.service_manager_list.itemAt(event.pos())
                if item is None:
                    self.drop_position = len(self.service_items)
                else:
                    # we are over something so lets investigate
                    pos = get_parent_item_data(item) - 1
                    service_item = self.service_items[pos]
                    if (plugin == service_item['service_item'].name and
                            service_item['service_item'].is_capable(ItemCapabilities.CanAppend)):
                        action = self.dnd_menu.exec(QtGui.QCursor.pos())
                        # New action required
                        if action == self.new_action:
                            self.drop_position = get_parent_item_data(item)
                        # Append to existing action
                        if action == self.add_to_action:
                            self.drop_position = get_parent_item_data(item)
                            item.setSelected(True)
                            replace = True
                    else:
                        self.drop_position = get_parent_item_data(item) - 1
            Registry().execute('{plugin}_add_service_item'.format(plugin=plugin), replace)
        else:
            self.log_warning('Unrecognised item')

    def update_theme_list(self, theme_list):
        """
        Called from ThemeManager when the Themes have changed

        :param theme_list: A list of current themes to be displayed
        """
        self.theme_combo_box.clear()
        self.theme_menu.clear()
        self.theme_combo_box.addItem('')
        theme_group = QtGui.QActionGroup(self.theme_menu)
        theme_group.setExclusive(True)
        theme_group.setObjectName('theme_group')
        # Create a "Default" theme, which allows the user to reset the item's theme to the service theme or global
        # theme.
        default_theme = create_widget_action(self.theme_menu, text=UiStrings().Default, checked=False,
                                             triggers=self.on_theme_change_action)
        self.theme_menu.setDefaultAction(default_theme)
        theme_group.addAction(default_theme)
        self.theme_menu.addSeparator()
        for theme in theme_list:
            self.theme_combo_box.addItem(theme)
            theme_group.addAction(create_widget_action(self.theme_menu, theme, text=theme, checked=False,
                                  triggers=self.on_theme_change_action))
        find_and_set_in_combo_box(self.theme_combo_box, self.service_theme)

    def on_theme_change_action(self, field=None):
        """
        Handles theme change events
        """
        theme = self.sender().objectName()
        # No object name means that the "Default" theme is supposed to be used.
        if not theme:
            theme = None
        item = self.find_service_item()[0]
        service_item = self.service_items[item]['service_item']
        # Needs to be checked before updating theme on service, as it generates a new identifier
        is_selected_item_live = self.live_controller.service_item and \
            service_item.unique_identifier == self.live_controller.service_item.unique_identifier
        service_item.update_theme(theme)
        # self.regenerate_service_items(True)
        if self.settings.value('themes/hot reload') and is_selected_item_live:
            self.live_controller.refresh_service_item(service_item)

    def on_make_live_action_triggered(self, checked):
        """
        Handle `make_live_action` when the action is triggered.

        :param bool checked: Not Used.
        :rtype: None
        """
        self.make_live()

    def get_drop_position(self):
        """
        Getter for drop_position. Used in: MediaManagerItem
        """
        return self.drop_position


def get_parent_item_data(item):
    """
    Finds and returns the parent item for any item

    :param item: The service item list item to be checked.
    """
    parent_item = item.parent()
    if parent_item is None:
        return item.data(0, QtCore.Qt.ItemDataRole.UserRole)
    else:
        return parent_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
