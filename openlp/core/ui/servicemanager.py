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

from PySide6 import QtCore, QtGui
import fluentqt
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import ThemeLevel, delete_file, sha256_file_hash
from openlp.core.common.actions import ActionList, CategoryOrder
from openlp.core.common.applocation import AppLocation
from openlp.core.common.enum import LayoutStyle, ServiceItemType
from openlp.core.common.i18n import UiStrings, format_time, translate
from openlp.core.common.json import OpenLPJSONDecoder, OpenLPJSONEncoder
from openlp.core.common.mixins import LogMixin, RegistryProperties
from openlp.core.common.registry import Registry, RegistryBase
from openlp.core.display.render import remove_tags
from openlp.core.lib import build_icon, create_thumb, ItemCapabilities, validate_thumb
from openlp.core.lib.exceptions import ValidationError
from openlp.core.lib.plugin import PluginStatus
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.lib.nativefile import SERVICE_SUFFIXES, service_payload, validate_service, write_manifest
from openlp.core.lib.theme import TransitionSpeed, TransitionType
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
from openlp.core.ui.renamedialog import RenameDialog
from openlp.core.widgets.toolbar import OpenLPToolbar
from openlp.core.widgets.dnd import ItemDragData, ThemeDragData, copy_service_item, execute_drag, supports_theme_drop
from openlp.core.widgets.fluent_tree import FluentLibraryTreeDelegate
from openlp.core.ui.fluenticons import fluent_icon, service_icon


SERVICE_ITEM_INDICATORS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class ServiceItemDelegate(FluentLibraryTreeDelegate):
    """
    Render a full-width service row with indicators immediately after its label.
    """
    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        super().paint(painter, opt, index)

    def trailingIcons(self, index):
        names = index.data(SERVICE_ITEM_INDICATORS_ROLE) or []
        return [fluent_icon(f'ic_fluent_{name}_24_regular') for name in names]

    def iconBorderVisible(self, index):
        return index.parent().isValid()

    def iconSize(self, option, index):
        if index.parent().isValid():
            icon_val = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
            if isinstance(icon_val, QtGui.QIcon) and not icon_val.isNull():
                return QtCore.QSize(64, 48)
        return super().iconSize(option, index)

    def _background_rect(self, option):
        rect = super()._background_rect(option)
        rect.setRight(option.rect.right() - 2)
        return rect

    def sizeHint(self, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        if index.parent().isValid():
            icon_val = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
            if isinstance(icon_val, QtGui.QIcon) and not icon_val.isNull():
                opt.decorationSize = QtCore.QSize(64, 48)
        hint = super().sizeHint(opt, index)
        if index.parent().isValid():
            icon_val = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
            if isinstance(icon_val, QtGui.QIcon) and not icon_val.isNull():
                hint.setHeight(max(hint.height(), 48 + 8))
        return hint


class ServiceManagerList(QtWidgets.QTreeWidget):
    """
    Set up key bindings and mouse behaviour for the service list
    """
    def __init__(self, service_manager, parent=None):
        """
        Constructor
        """
        super(ServiceManagerList, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionIndicatorVisible(True)
        self.setItemDelegateForColumn(0, ServiceItemDelegate(self))
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAlternatingRowColors(use_alternate_rows())
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.setIndentation(30)
        self.setMouseTracking(True)
        self.setExpandsOnDoubleClick(False)
        self.service_manager = service_manager
        self._drag_start_pos = None
        self._last_notes_tooltip_item = None
        self._theme_drag_data = None
        self._drop_line = QtWidgets.QFrame(self.viewport())
        self._drop_line.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._drop_line.hide()
        self._drag_scroll_timer = QtCore.QTimer(self)
        self._drag_scroll_timer.setInterval(50)
        self._drag_scroll_timer.timeout.connect(self._scroll_drag)

    def _show_notes_tooltip_on_hover(self, event):
        """Show the row tooltip immediately over its inline indicators."""
        if not isinstance(event, QtGui.QMouseEvent):
            return False
        index = self.indexAt(event.pos())
        option = QtWidgets.QStyleOptionViewItem()
        option.rect = self.visualRect(index)
        option.font = self.font()
        option.direction = self.layoutDirection()
        delegate = self.itemDelegateForColumn(0)
        if index.isValid():
            delegate.initStyleOption(option, index)
        if index.isValid() and any(rect.contains(event.pos()) for rect in delegate.trailingIconRects(option, index)):
            item = self.itemFromIndex(index)
            tooltip = item.toolTip(0) if item else ''
            if tooltip:
                if self._last_notes_tooltip_item is not item:
                    QtWidgets.QToolTip.showText(self.viewport().mapToGlobal(event.pos()), tooltip, self.viewport())
                    self._last_notes_tooltip_item = item
            elif self._last_notes_tooltip_item is not None:
                self._last_notes_tooltip_item = None
                QtWidgets.QToolTip.hideText()
            return True
        self._last_notes_tooltip_item = None
        QtWidgets.QToolTip.hideText()
        return False

    def leaveEvent(self, event):
        """
        Hide any immediate tooltip when mouse leaves the list.
        """
        self._last_notes_tooltip_item = None
        QtWidgets.QToolTip.hideText()
        super(ServiceManagerList, self).leaveEvent(event)

    def can_accept_drop(self, event):
        mime = event.mimeData()
        if isinstance(mime, ThemeDragData):
            return mime.can_drop(self.theme_drop_item(event.pos()))
        if isinstance(mime, ItemDragData):
            if event.source() is self and self.service_manager.is_internal_drag_active():
                return mime.item is self.service_manager._internal_drag_item['service_item']
            return mime.can_drop('service')
        if mime.hasUrls():
            return all(url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in SERVICE_SUFFIXES
                       for url in mime.urls()) and bool(mime.urls())
        return False

    def theme_drop_item(self, pos):
        row = self.itemAt(pos)
        if row is not None:
            row = row.parent() or row
            index = get_parent_item_data(row) - 1
            if 0 <= index < len(self.service_manager.service_items):
                return self.service_manager.service_items[index]['service_item']
        return None

    def set_theme_drop_target(self, pos):
        self.set_drop_position(None)
        if self._theme_drag_data and self._theme_drag_data.can_drop(self.theme_drop_item(pos)):
            row = self.itemAt(pos)
            row = row.parent() or row
            self._drop_line.setStyleSheet(
                'background: transparent; border: 2px solid palette(highlight); border-radius: 4px;')
            rect = self.visualItemRect(row)
            if row.isExpanded() and row.childCount():
                rect = rect.united(self.visualItemRect(row.child(row.childCount() - 1)))
            self._drop_line.setGeometry(rect.intersected(self.viewport().rect()).adjusted(2, 0, -2, 0))
            self._drop_line.show()
            self._drop_line.raise_()

    def dragEnterEvent(self, event):
        if not self.can_accept_drop(event):
            event.ignore()
            return
        mime = event.mimeData()
        if isinstance(mime, ThemeDragData):
            self.service_manager.cancel_external_drag_preview()
            self._theme_drag_data = mime
            self.set_theme_drop_target(event.pos())
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
        elif isinstance(mime, ItemDragData) and event.source() is self:
            self.service_manager.update_internal_drag_preview(event.pos())
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        elif not mime.hasUrls():
            raw_title = mime.data('application/x-openlp-item-title')
            title = bytes(raw_title).decode('utf-8', errors='replace') if raw_title else None
            plugin = mime.text() if mime.hasText() else mime.item.name
            self.service_manager.cancel_external_drag_preview()
            self.service_manager.begin_external_drag_preview(plugin, item_title=title)
            self.service_manager.update_external_drag_preview(event.pos())
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
        event.accept()
        self._drag_scroll_timer.start()

    def dragLeaveEvent(self, event):
        self._drag_scroll_timer.stop()
        self._theme_drag_data = None
        self.service_manager.cancel_external_drag_preview()
        self.set_drop_position(None)
        QtWidgets.QToolTip.hideText()
        event.accept()

    def dragMoveEvent(self, event):
        if not self.can_accept_drop(event):
            self.set_drop_position(None)
            event.ignore()
            return
        if isinstance(event.mimeData(), ThemeDragData):
            self.set_theme_drop_target(event.pos())
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
        elif isinstance(event.mimeData(), ItemDragData) and event.source() is self:
            self.service_manager.update_internal_drag_preview(event.pos())
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        else:
            self.service_manager.update_external_drag_preview(event.pos())
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
        event.accept()

    def set_drop_position(self, index):
        """Draw the insertion gap independently of the row delegate."""
        if index is None:
            self._drop_line.hide()
            return
        count = self.topLevelItemCount()
        if index < count:
            y = self.visualItemRect(self.topLevelItem(index)).top()
        elif count:
            item = self.topLevelItem(count - 1)
            while item.isExpanded() and item.childCount():
                item = item.child(item.childCount() - 1)
            y = self.visualItemRect(item).bottom() + 1
        else:
            y = 4
        color = self.itemDelegateForColumn(0)._theme_host.theme_tokens().colors.accentDefault
        self._drop_line.setStyleSheet('background: {color}; border-radius: 1px;'.format(color=color.name()))
        self._drop_line.setGeometry(4, max(0, min(y - 1, self.viewport().height() - 3)),
                                    max(0, self.viewport().width() - 8), 3)
        self._drop_line.show()
        self._drop_line.raise_()

    def _scroll_drag(self):
        pos = self.viewport().mapFromGlobal(QtGui.QCursor.pos())
        if not self.viewport().rect().contains(pos):
            return
        step = -8 if pos.y() < 28 else 8 if pos.y() > self.viewport().height() - 28 else 0
        if step:
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() + step)
            if self._theme_drag_data:
                self.set_theme_drop_target(pos)
            elif self.service_manager.is_internal_drag_active():
                self.service_manager.update_internal_drag_preview(pos)
            else:
                self.service_manager.update_external_drag_preview(pos)

    def keyPressEvent(self, event):
        """
        Capture Key press and respond accordingly.
        :param event:
        """
        if isinstance(event, QtGui.QKeyEvent):
            # here accept the event and do something
            if event.modifiers() & (QtCore.Qt.KeyboardModifier.ShiftModifier |
                                    QtCore.Qt.KeyboardModifier.ControlModifier |
                                    QtCore.Qt.KeyboardModifier.MetaModifier):
                super().keyPressEvent(event)
                return
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
        if (event.buttons() & QtCore.Qt.MouseButton.LeftButton and self._drag_start_pos is not None
                and self.indexAt(self._drag_start_pos).isValid()
                and (event.pos() - self._drag_start_pos).manhattanLength()
                >= QtWidgets.QApplication.startDragDistance()):
            self._drag_start_pos = None
            self.startDrag(QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction)
            return
        if not event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self._show_notes_tooltip_on_hover(event)
        if isinstance(event, QtGui.QMouseEvent):
            super().mouseMoveEvent(event)
        else:
            event.ignore()

    def startDrag(self, actions):
        if not self.service_manager or not self.service_manager.begin_internal_drag():
            return
        mime = ItemDragData(items=[entry['service_item'] for entry in self.service_manager._internal_drag_items],
                            slide_no=self.service_manager._internal_drag_child)
        try:
            execute_drag(self, mime, QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction)
        finally:
            self._drag_scroll_timer.stop()
            self.service_manager.finish_internal_drag(False)
            self.set_drop_position(None)


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
        self.toolbar.layout().setContentsMargins(0, 0, 8, 0)
        self.toolbar.add_toolbar_action('newService', text=UiStrings().NewService, icon=UiIcons().new,
                                        tooltip=UiStrings().CreateService, triggers=self.on_new_service_clicked)
        self.open_service_action = self.toolbar.add_toolbar_action(
            'openService',
            text=UiStrings().OpenService,
            icon=UiIcons().open,
            tooltip=translate('OpenLP.ServiceManager', 'Load an existing service.'),
            triggers=self.on_load_service_clicked)
        self.save_service_action = self.toolbar.add_toolbar_action('saveService', text=UiStrings().SaveService,
                                                                   icon=UiIcons().save,
                                                                   tooltip=translate('OpenLP.ServiceManager',
                                                                                     'Save this service.'),
                                                                   triggers=self.decide_save_method)
        self.save_service_as_action = self.toolbar.add_toolbar_action(
            'saveServiceAs',
            text=translate('OpenLP.ServiceManager', 'Save As'),
            icon=UiIcons().save_plus,
            tooltip=translate('OpenLP.ServiceManager', 'Save Service As'),
            triggers=self.save_file_as)
        self.save_service_action.setEnabled(False)
        self.save_service_as_action.setEnabled(False)
        self.toolbar.add_spacer()
        self.theme_label = QtWidgets.QLabel(UiStrings().Theme, widget)
        self.theme_label.setContentsMargins(3, 3, 3, 3)
        self.theme_label.setObjectName('theme_label')
        self.toolbar.add_toolbar_widget(self.theme_label)
        self.theme_combo_box = QtWidgets.QComboBox(self.toolbar)
        self.theme_combo_box.setToolTip(translate('OpenLP.ServiceManager', 'Select a theme for the service.'))
        self.theme_combo_box.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.theme_combo_box.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.theme_combo_box.setMinimumWidth(100)
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
        self.service_manager_list.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                                QtWidgets.QSizePolicy.Policy.Expanding)
        self.layout.addWidget(self.service_manager_list, 1)
        # Add the bottom toolbar
        self.order_toolbar = OpenLPToolbar(widget, single_command_bar=True)
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
                        text=translate('OpenLP.ServiceManager', '&Delete From Service'),
                        icon=UiIcons().minus,
            tooltip=translate('OpenLP.ServiceManager', 'Delete the selected item from the service.'),
            triggers=self.on_delete_from_service)
        self.delete_action.setEnabled(False)
        self.order_toolbar.addSeparator()
        self.expand_collapse_action = self.order_toolbar.add_toolbar_action(
            'expandCollapse', can_shortcuts=True, checked=False,
            text=translate('OpenLP.ServiceManager', '&Expand all'),
                        icon=UiIcons().arrow_expand_vertical,
            tooltip=translate('OpenLP.ServiceManager', 'Expand or collapse all the service items'),
            category=UiStrings().Service, triggers=self.on_toggle_expand_all)
        self.expand_collapse_action.setEnabled(False)
        self.note_toolbar_action = self.order_toolbar.add_toolbar_action(
            'serviceNotes',
            text=translate('OpenLP.ServiceManager', '&Notes'),
            icon=UiIcons().notes,
            tooltip=translate('OpenLP.ServiceManager', 'View or edit notes for the selected item'),
            triggers=self.on_service_item_note_form)
        self.note_toolbar_action.setEnabled(False)
        self.order_toolbar.addSeparator()
        self.make_preview_action = self.order_toolbar.add_toolbar_action(
            'make_preview', pinned=True, can_shortcuts=True,
            text=translate('OpenLP.ServiceManager', 'Show &Preview'), icon=UiIcons().preview,
            tooltip=translate('OpenLP.ServiceManager', 'Send the selected item to Preview'),
            category=UiStrings().Service,
            triggers=self.make_preview)
        self.make_preview_action.setEnabled(False)
        self.make_live_action = self.order_toolbar.add_toolbar_action(
            'make_live', pinned=True, can_shortcuts=True,
            text=translate('OpenLP.ServiceManager', 'Go Live'), icon=UiIcons().live,
            tooltip=translate('OpenLP.ServiceManager', 'Send the selected item to Live.'),
            category=UiStrings().Service,
            triggers=self.on_make_live_action_triggered)
        self.make_live_action.setEnabled(False)
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
        self._update_new_service_actions()
        self._update_move_actions()
        # build the context menu
        self.menu = QtWidgets.QMenu()
        self.edit_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Edit Item'),
                                                icon=UiIcons().edit, triggers=self.remote_edit)
        self.rename_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Rename...'),
                                                  icon=UiIcons().edit,
                                                  triggers=self.on_service_item_rename)
        self.maintain_action = create_widget_action(
            self.menu, text=translate('OpenLP.ServiceManager', '&Reorder/rename items'),
            icon=UiIcons().edit, triggers=self.on_service_item_edit_form)
        self.notes_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Notes'),
                                                 icon=UiIcons().notes,
                                                 triggers=self.on_service_item_note_form)
        self.time_action = create_widget_action(self.menu, text=translate('OpenLP.ServiceManager', '&Start Time'),
                                                icon=UiIcons().time, triggers=self.on_start_time_form)
        self.auto_start_action = create_widget_action(self.menu, text='',
                                                      icon=fluent_icon('ic_fluent_play_circle_sparkle_24_regular'),
                                                      triggers=self.on_auto_start)
        # Add already existing delete action to the menu.
        self.menu.addAction(self.delete_action)
        self.transition_section_sep_before = _add_service_manager_context_menu_separator(self.menu)
        self.transition_action = create_widget_action(
            self.menu,
            text=translate('OpenLP.ServiceManager', '&Transition'),
            icon=UiIcons().transition,
            triggers=self.on_service_item_transition_form)
        self.transition_action.setCheckable(True)
        self.custom_layout_section_sep_before = _add_service_manager_context_menu_separator(self.menu)
        self.bible_layout_menu = QtWidgets.QMenu(translate('OpenLP.ServiceManager', 'Layout style'), self.menu)
        self.menu.addMenu(self.bible_layout_menu)
        self.bible_layout_action_group = QtGui.QActionGroup(self.bible_layout_menu)
        self.bible_layout_action_group.setExclusive(True)
        self.bible_layout_style_actions = {}
        _bible_layout_labels = {
            LayoutStyle.VersePerSlide: UiStrings().VersePerSlide,
            LayoutStyle.VersePerLine: UiStrings().VersePerLine,
            LayoutStyle.Continuous: UiStrings().Continuous,
            LayoutStyle.WholeVerseContinuous: UiStrings().WholeVerseContinuous,
        }
        for ls in LayoutStyle:
            act = create_widget_action(
                self.bible_layout_menu,
                name='bible_layout_{name}'.format(name=ls.name),
                text=_bible_layout_labels[ls],
                checked=False,
                triggers=self.on_bible_layout_style_action)
            act.setData(int(ls))
            self.bible_layout_action_group.addAction(act)
            self.bible_layout_style_actions[ls] = act
        self.create_custom_action = create_widget_action(self.menu,
                                                         text=translate('OpenLP.ServiceManager', 'Create New &Custom '
                                                                                                 'Slide'),
                                                         icon=UiIcons().custom,
                                                         triggers=self.create_custom)
        self.custom_layout_section_sep_after = _add_service_manager_context_menu_separator(self.menu)
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
        self.transition_section_sep_after = _add_service_manager_context_menu_separator(self.menu)
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
                                              self.expand_collapse_action, self.note_toolbar_action])


def _add_service_manager_context_menu_separator(menu):
    """Add a separator and return its QAction (supports setVisible for dynamic show/hide)."""
    action = menu.addSeparator()
    action.setObjectName('openlp_service_manager_context_menu_sep')
    return action


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
                payload_name = service_payload(
                    zip_file, required=self.file_path.suffix.lower().startswith('.opal-'),
                    file_type='service-lite' if self.file_path.suffix.lower() == '.opal-service-lite' else 'service')
                zip_infos = zip_file.infolist()
                compressed_size = sum(zip_info.compress_size for zip_info in zip_infos)
                self.progress_max.emit(compressed_size // 1024)
                self.status.emit(
                    translate('OpenLP.ServiceManager', 'Reading service metadata...'))
                service_data = None
                for zip_info in zip_infos:
                    if zip_info.filename == payload_name:
                        with zip_file.open(zip_info, 'r') as json_file:
                            service_data = json_file.read()
                        break
                if not service_data:
                    raise ValidationError(msg='No service data found')
                items = json.loads(service_data, cls=OpenLPJSONDecoder)
                validate_service(items)
                servicefile_version = 2
                for item in items:
                    if 'openlp_core' in item:
                        item = item['openlp_core']
                        servicefile_version = item.get('openlp-servicefile-version', 2)
                        break
                is_broken_file = False
                for zip_info in zip_infos:
                    if zip_info.filename == 'manifest.json':
                        continue
                    self.status.emit(
                        translate('OpenLP.ServiceManager', 'Importing file: {file_name}')
                        .format(file_name=Path(zip_info.filename).name))
                    if zip_info.filename == payload_name:
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
        except (NameError, OSError, ValueError, ValidationError, zipfile.BadZipFile):
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
        self.servicefile_version = None
        self.tree_widget_items = []
        self._internal_drag_item = None
        self._internal_drag_items = []
        self._internal_drag_target_index = None
        self._internal_drag_child = -1
        self._internal_drag_visual_item_index = -1
        self._external_drag_item = None
        self._external_drag_plugin_name = None
        self._external_drag_target_index = -1
        self._external_drag_highlight_index = -1
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

    def bootstrap_post_set_up(self):
        """
        Can be set up as a late setup
        """
        self.service_note_form = ServiceNoteForm()
        self.service_item_edit_form = ServiceItemEditForm()
        self.start_time_form = StartTimeForm()
        self._update_new_service_actions()

    def on_export_presentation(self, suffix):
        """Export the current service, with the configured logo between items."""
        from openlp.core.lib.presentationexport import export_items_dialog

        export_items_dialog(self.main_window,
                            [entry['service_item'] for entry in self.service_items],
                            suffix, self.suggested_presentation_file_path(suffix), insert_logo=True)

    def suggested_presentation_file_path(self, suffix):
        """Use the current service filename or the configured Save As name pattern."""
        if self.file_name():
            return Path(self.file_name()).with_suffix(suffix)
        if not self.settings.value('advanced/default service enabled') or \
                not self.settings.value('advanced/default service name'):
            directory = self.settings.value('servicemanager/last directory') or Path('.')
            return Path(directory) / f"{translate('OpenLP.ServiceManager', 'Service')}{suffix}"
        default_path = self._default_service_file_path()
        return default_path.parent / f'{default_path.name}{suffix}'

    def _delete_confirmation_dialog(self):
        multiple = len(self.selected_service_indexes()) > 1
        message = (translate('OpenLP.ServiceManager', 'Are you sure you want to delete these items from the service?')
                   if multiple else translate('OpenLP.ServiceManager',
                                              'Are you sure you want to delete this item from the service?'))
        msg_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question,
                                        translate('OpenLP.ServiceManager', 'Delete item from service'),
                                        message,
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
        self._update_new_service_actions()
        self.servicemanager_changed.emit()

    def _can_create_new_service(self):
        """An untouched empty service already provides a blank canvas."""
        return bool(self.service_items or self.is_modified())

    def _update_new_service_actions(self):
        """Keep the toolbar and File menu New actions in sync."""
        enabled = self._can_create_new_service()
        toolbar = getattr(self, 'toolbar', None)
        if toolbar is not None:
            toolbar.actions_map['newService'].setEnabled(enabled)
        action = getattr(self.main_window, 'file_new_item', None)
        if action is not None:
            action.setEnabled(enabled)

    def _update_unsaved_changes_indicator(self):
        """
        Show unsaved state in the Service dock title and hide the legacy toolbar indicator.
        """
        self._update_service_manager_dock_title()
        if not hasattr(self, 'unsaved_changes_container'):
            return
        self.unsaved_changes_container.setVisible(False)
        if 'unsaved_changes_container' in self.toolbar.actions_map:
            self.toolbar.actions_map['unsaved_changes_container'].setVisible(False)

    def _update_service_manager_dock_title(self):
        """
        Update the Service pane title, appending unsaved state when required.
        """
        dock_widget = self.parentWidget()
        if not isinstance(dock_widget, QtWidgets.QDockWidget):
            return
        service_title = translate('OpenLP.MainWindow', 'Service')
        if self._modified:
            unsaved_text = translate('OpenLP.ServiceManager', 'unsaved changes')
            service_title = '{title} ({unsaved})'.format(title=service_title, unsaved=unsaved_text)
        dock_widget.setWindowTitle(service_title)

    def _create_colored_service_icon(self, icon, service_item):
        """Use the Fluent colour for this service item's plugin type."""
        return service_icon(icon, str(getattr(service_item, 'name', '')).lower())

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
        if file_path and file_path.suffix.lower() in ('.opal-service-lite', '.oszl'):
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
        if not self._can_create_new_service():
            return False
        if self.is_modified():
            result = self.save_modified_service()
            if result == QtWidgets.QMessageBox.StandardButton.Cancel:
                return False
            elif result == QtWidgets.QMessageBox.StandardButton.Save:
                if not self.decide_save_method():
                    return False
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
                translate('OpenLP.ServiceManager', 'Opal Presenter and OpenLP Services (*.opal-service *.opal-service-lite *.osz *.oszl)'))
            if not file_path:
                return False
        self.settings.setValue('servicemanager/last directory', file_path.parent)
        self.load_file_in_thread(file_path)

    def save_modified_service(self):
        """
        Check to see if a service needs to be saved.
        """
        dialog = QtWidgets.ContentDialog(self.main_window)
        dialog.graphicsEffect().setEnabled(False)
        dialog.setSmokeEnabled(True)
        dialog.setDragEnabled(False)
        dialog.setMinimumWidth(420)
        dialog.setMaximumWidth(560)
        dialog.setTitle(translate('OpenLP.ServiceManager', 'Modified Service'))
        content = fluentqt.Label(
            translate('OpenLP.ServiceManager',
                      'The current service has been modified. Would you like to save this service?'))
        content.setWordWrap(True)
        dialog.setContent(content)
        dialog.setPrimaryButtonText(translate('OpenLP.ServiceManager', 'Save'))
        dialog.setSecondaryButtonText(translate('OpenLP.ServiceManager', 'Discard'))
        dialog.setCloseButtonText(translate('OpenLP.ServiceManager', 'Cancel'))
        dialog.setDefaultButton(fluentqt.ContentDialogButton.Primary)
        result = dialog.exec()
        dialog.deleteLater()
        return {dialog.ResultPrimary: QtWidgets.QMessageBox.StandardButton.Save,
                dialog.ResultSecondary: QtWidgets.QMessageBox.StandardButton.Discard}.get(
                    result, QtWidgets.QMessageBox.StandardButton.Cancel)

    def on_recent_service_clicked(self, checked, file_path=None):
        """
        Load a recent file as the service triggered by mainwindow recent service list.

        :param bool checked: Not used
        :param Path | str | None file_path: Optional path for callers that are not QAction senders.
        """
        if self.is_modified():
            result = self.save_modified_service()
            if result == QtWidgets.QMessageBox.StandardButton.Cancel:
                return False
            elif result == QtWidgets.QMessageBox.StandardButton.Save:
                self.decide_save_method()
        if file_path is None:
            sender = self.sender()
            if not sender:
                return False
            file_path = sender.data()
        if not file_path:
            return False
        self.load_file_in_thread(Path(file_path))

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
                self.set_modified(True)
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
                        file_hash = sha256_file_hash(frame_path)
                        if file_hash is None:
                            missing_list.append(str(frame_path))
                            continue
                        sha256_file_name = Path(file_hash + frame_path.suffix)
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
                if audio_file_hash is None:
                    missing_list.append(str(audio_path))
                    continue
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
        if file_path and file_path.suffix.lower() not in ('.opal-service', '.opal-service-lite'):
            return self.save_file_as()
        self.log_debug('ServiceManager.save_file - {name}'.format(name=file_path))
        self.application.set_busy_cursor()
        try:
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
                    self.application.set_busy_cursor()
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
                    write_manifest(zip_file, 'service-lite' if self._save_lite else 'service', 'service.json')
                    zip_file.writestr('service.json', service_content)
                    if not self._save_lite:
                        from openlp.core.lib.designmedia import write_media
                        write_media(zip_file, service)
                    self.main_window.increment_progress_bar(service_content_size / total_size * 1000)
                    # Finally add all the listed media files.
                    for local_file_item, zip_file_item in write_list:
                        zip_file.write(str(local_file_item), str(zip_file_item))
                        self.main_window.increment_progress_bar(local_file_item.stat().st_size / total_size * 1000)
                Path(tmp_file_path).replace(file_path)
                self.settings.setValue('servicemanager/last directory', file_path.parent)
            except (PermissionError, OSError) as error:
                self.log_exception('Failed to save service to disk: {name}'.format(name=file_path))
                self.application.set_normal_cursor()
                self.main_window.error_message(
                    translate('OpenLP.ServiceManager', 'Error Saving File'),
                    translate('OpenLP.ServiceManager',
                              'There was an error saving your file.\n\n{error}').format(error=error))
                return self.save_file_as()
            self.main_window.finished_progress_bar()
            self.main_window.add_recent_file(file_path)
            self.set_modified(False)
            return True
        finally:
            self.application.set_normal_cursor()

    def _default_service_file_path(self):
        """Build the default service path from the configured date and name pattern."""
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
        return default_file_path

    def save_file_as(self):
        """
        Get a file name and then call :func:`ServiceManager.save_file` to save the file.
        """
        default_file_path = self._default_service_file_path()
        lite_filter = translate('OpenLP.ServiceManager', 'Opal Presenter Service - external files (*.opal-service-lite)')
        packaged_filter = translate('OpenLP.ServiceManager', 'Opal Presenter Service (*.opal-service)')
        if self._service_path and self._service_path.suffix.lower() in ('.opal-service-lite', '.oszl'):
            default_filter = lite_filter
        else:
            default_filter = packaged_filter
        # SaveAs from osz to oszl is not valid as the files will be deleted on exit which is not sensible or usable in
        # the long term.
        if self._service_path and self._service_path.suffix.lower() in ('.opal-service-lite', '.oszl') or self.service_has_all_original_files:
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
            file_path = file_path.with_suffix('.opal-service-lite')
        else:
            file_path = file_path.with_suffix('.opal-service')
        self.set_file_name(file_path)
        return self.decide_save_method()

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
                payload_name = service_payload(
                    zip_file, required=file_path.suffix.lower().startswith('.opal-'),
                    file_type='service-lite' if file_path.suffix.lower() == '.opal-service-lite' else 'service')
                compressed_size = 0
                for zip_info in zip_file.infolist():
                    compressed_size += zip_info.compress_size
                self.main_window.display_progress_bar(compressed_size // 1024)
                self._show_loading_status(translate('OpenLP.ServiceManager', 'Reading service metadata...'))
                # First find the osj-file to find out how to handle the file
                for zip_info in zip_file.infolist():
                    # The json file has been called 'service_data.osj' since OpenLP 3.0
                    if zip_info.filename == payload_name:
                        with zip_file.open(zip_info, 'r') as json_file:
                            service_data = json_file.read()
                        break
                if service_data:
                    items = json.loads(service_data, cls=OpenLPJSONDecoder)
                    validate_service(items)
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
                    if zip_info.filename == 'manifest.json':
                        continue
                    self.log_debug('Extract file: {name}'.format(name=zip_info.filename))
                    self._show_loading_status(
                        translate('OpenLP.ServiceManager', 'Importing file: {file_name}')
                        .format(file_name=Path(zip_info.filename).name))
                    # The json file has been called 'service_data.osj' since OpenLP 3.0
                    if zip_info.filename == payload_name:
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
                    self.set_modified(True)
                self.settings.setValue('servicemanager/last file', file_path)
                is_loaded = True
        except (NameError, OSError, ValueError, ValidationError, zipfile.BadZipFile):
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
                if service_item.uses_file() and not service_item.is_valid:
                    if not self._resolve_missing_service_item_files(service_item):
                        continue
                self._regenerate_missing_thumbnails(service_item)
                if service_item.is_capable(ItemCapabilities.OnLoadUpdate):
                    new_item = Registry().get(service_item.name).service_load(service_item)
                    if new_item:
                        service_item = new_item
                self.add_service_item(service_item, repaint=False)

    # Filters used when prompting the user to locate a replacement for a missing file.
    _RELOCATE_FILE_FILTERS = {
        'images': 'Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp);;All Files (*)',
        'presentations': ('Presentation Files (*.ppt *.pptx *.pps *.ppsx *.odp *.pdf);;'
                          'All Files (*)'),
        'media': ('Media Files (*.mp3 *.mp4 *.mov *.avi *.mkv *.wav *.ogg *.m4a *.webm);;'
                  'All Files (*)'),
    }

    def _resolve_missing_service_item_files(self, service_item):
        """
        When a loaded service item references source files that no longer exist, prompt
        the user to locate the replacement file(s) or remove the item from the service.
        Missing thumbnails are never surfaced here — they are regenerated automatically.

        :param service_item: The ``ServiceItem`` with missing source-file references.
        :return: ``True`` if the item should still be added to the service (user
                 relocated the file(s) or chose to keep the item anyway), ``False`` if
                 the user chose to remove the item.
        """
        missing_frames = [frame for frame in service_item.get_frames()
                          if not service_item.get_frame_path(frame=frame).exists()]
        if not missing_frames:
            return True
        # Presentations/media typically have many frames all pointing at a single source
        # file, so deduplicate the list we show and act on.
        seen = set()
        unique_missing = []
        for frame in missing_frames:
            path = service_item.get_frame_path(frame=frame)
            if path in seen:
                continue
            seen.add(path)
            unique_missing.append(path)
        title = service_item.title or service_item.name or ''
        if service_item.is_image() and len(unique_missing) > 1:
            message = translate(
                'OpenLP.ServiceManager',
                '"{title}" references image files that could not be found:\n{files}'
            ).format(title=title, files='\n'.join(str(p) for p in unique_missing))
        else:
            # One source file per item (presentation/media) or a single missing image.
            message = translate(
                'OpenLP.ServiceManager',
                'The source file for "{title}" could not be found:\n{file}'
            ).format(title=title, file=str(unique_missing[0]))
        box = QtWidgets.QMessageBox(self.main_window)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle(translate('OpenLP.ServiceManager', 'Missing File'))
        box.setText(message)
        locate_button = box.addButton(translate('OpenLP.ServiceManager', 'Locate…'),
                                      QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        remove_button = box.addButton(translate('OpenLP.ServiceManager', 'Remove Item'),
                                      QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(locate_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is remove_button:
            return False
        if service_item.is_image():
            for frame in missing_frames:
                new_path = self._prompt_for_replacement_file(
                    service_item, service_item.get_frame_path(frame=frame))
                if new_path:
                    self._update_image_frame_path(frame, new_path)
        else:
            new_path = self._prompt_for_replacement_file(service_item, unique_missing[0])
            if new_path:
                self._update_command_item_path(service_item, new_path)
        service_item.validate_item()
        return True

    def _prompt_for_replacement_file(self, service_item, missing_path):
        """Show a file-picker dialog scoped to the plugin's supported file types."""
        file_filter = translate('OpenLP.ServiceManager',
                                self._RELOCATE_FILE_FILTERS.get(service_item.name, ''))
        caption = translate('OpenLP.ServiceManager',
                            'Locate replacement for "{name}"').format(name=missing_path.name)
        start_dir = missing_path.parent if missing_path.parent.exists() else Path.home()
        new_path, _ = FileDialog.getOpenFileName(self.main_window, caption, start_dir, file_filter)
        return new_path if new_path else None

    @staticmethod
    def _update_image_frame_path(frame, new_path):
        """Rewrite an image slide to point at the replacement file."""
        frame['path'] = new_path
        frame['title'] = new_path.stem
        try:
            frame['file_hash'] = sha256_file_hash(new_path)
        except OSError:
            frame['file_hash'] = None
        # Drop the cached thumbnail so it will be regenerated from the new source.
        frame.pop('thumbnail', None)

    @staticmethod
    def _update_command_item_path(service_item, new_path):
        """Rewrite a command-style (presentation/media) item to point at the replacement file."""
        service_item.has_original_file_path = True
        try:
            service_item.sha256_file_hash = sha256_file_hash(new_path)
        except OSError:
            service_item.sha256_file_hash = None
        service_item.stored_filename = new_path.name
        for frame in service_item.get_frames():
            frame['path'] = new_path.parent
            frame['title'] = new_path.name
            # Clear any stale bundled-thumbnail path; the regen pass will refresh it.
            frame['image'] = None
            frame['thumbnail'] = None

    def _regenerate_missing_thumbnails(self, service_item):
        """
        Regenerate any missing or stale thumbnails referenced by a loaded service item.
        Items whose source files are still missing are silently skipped.
        """
        if not service_item.is_capable(ItemCapabilities.HasThumbnails):
            return
        try:
            if service_item.is_image():
                self._regenerate_image_thumbnails(service_item)
            elif service_item.is_command():
                if service_item.name == 'media':
                    self._regenerate_media_thumbnails(service_item)
                elif service_item.name == 'presentations':
                    self._regenerate_presentation_thumbnails(service_item)
        except Exception:
            self.log_exception('Failed to regenerate thumbnails for service item "{title}"'
                               .format(title=service_item.title))

    @staticmethod
    def _regenerate_image_thumbnails(service_item):
        thumb_dir = AppLocation.get_section_data_path(service_item.name) / 'thumbnails'
        thumb_dir.mkdir(parents=True, exist_ok=True)
        for frame in service_item.get_frames():
            source_path = Path(frame['path'])
            if not source_path.exists():
                continue
            file_hash = frame.get('file_hash')
            if not file_hash:
                try:
                    file_hash = sha256_file_hash(source_path)
                    frame['file_hash'] = file_hash
                except OSError:
                    continue
            thumb_path = thumb_dir / '{hash}{ext}'.format(hash=file_hash,
                                                          ext=source_path.suffix.lower())
            existing = frame.get('thumbnail')
            if existing and Path(existing).exists() and validate_thumb(source_path, Path(existing)):
                continue
            create_thumb(source_path, thumb_path, return_icon=False)
            if thumb_path.exists():
                frame['thumbnail'] = thumb_path

    def _regenerate_media_thumbnails(self, service_item):
        from openlp.core.ui.media import media_info
        thumb_dir = AppLocation.get_section_data_path(service_item.name) / 'thumbnails'
        thumb_dir.mkdir(parents=True, exist_ok=True)
        for frame in service_item.get_frames():
            source_path = service_item.get_frame_path(frame=frame)
            if not source_path.exists():
                continue
            existing = frame.get('thumbnail') or frame.get('image')
            if existing and Path(existing).exists() and validate_thumb(source_path, Path(existing)):
                continue
            file_hash = service_item.sha256_file_hash
            if not file_hash:
                try:
                    file_hash = sha256_file_hash(source_path)
                    service_item.sha256_file_hash = file_hash
                except OSError:
                    continue
            thumb_path = thumb_dir / '{hash}.png'.format(hash=file_hash)
            if media_info().create_media_thumbnail(str(source_path), str(thumb_path)):
                frame['thumbnail'] = thumb_path
                frame['image'] = thumb_path

    def _regenerate_presentation_thumbnails(self, service_item):
        plugin = Registry().get(service_item.name) if Registry().has(service_item.name) else None
        media_item = getattr(plugin, 'media_item', None) if plugin else None
        if media_item is None or not getattr(media_item, 'controllers', None):
            return
        # All frames in a presentation service item share one source file, so resolve it once.
        source_path = None
        for frame in service_item.get_frames():
            candidate = service_item.get_frame_path(frame=frame)
            if candidate.exists():
                source_path = candidate
                break
        if source_path is None:
            return
        needs_regen = any(
            not (frame.get('image') and Path(frame['image']).exists())
            for frame in service_item.get_frames()
        )
        if not needs_regen:
            return
        controller_name = media_item.find_controller_by_type(source_path)
        if not controller_name:
            return
        controller = media_item.controllers[controller_name]
        doc = controller.add_document(source_path)
        try:
            thumb_path = doc.get_thumbnail_path(1, True)
            if thumb_path is None:
                doc.load_presentation()
            for index, frame in enumerate(service_item.get_frames(), start=1):
                regenerated = doc.get_thumbnail_path(index, True)
                if regenerated and regenerated.exists():
                    frame['image'] = regenerated
                    frame['thumbnail'] = regenerated
        finally:
            doc.close_presentation()

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
        if hasattr(self, 'transition_action'):
            self.transition_action.setVisible(False)
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
            else:
                self.auto_start_action.setText(translate('OpenLP.ServiceManager', '&Auto Start - inactive'))
        if hasattr(self, 'transition_action') and self._service_item_supports_transition(service_item['service_item']):
            transition_settings = self._get_service_item_transition_settings(service_item['service_item'])
            self.transition_action.setVisible(True)
            self.transition_action.setChecked(bool(transition_settings.get('enabled', False)))
        state = State()
        try:
            plugins = state.list_plugins()
        except AttributeError:
            plugins = []
        if service_item['service_item'].is_text() and not service_item['service_item'].is_slide_set:
            for plugin in plugins:
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
        bible_layout_menu = getattr(self, 'bible_layout_menu', None)
        if bible_layout_menu is not None:
            bible_layout_menu.menuAction().setVisible(False)
        si = service_item['service_item']
        bible_media_item = None
        for plugin in plugins:
            if plugin.name == 'bibles' and plugin.is_active() and plugin.media_item:
                bible_media_item = plugin.media_item
                break
        if (getattr(si, 'name', None) == 'bibles' and isinstance(si.data_string, dict)
                and si.data_string.get('verse_source') and bible_media_item is not None):
            if bible_layout_menu is not None:
                bible_layout_menu.menuAction().setVisible(True)
            current_layout = self.settings.value('bibles/verse layout style')
            for ls, act in self.bible_layout_style_actions.items():
                act.setChecked(int(ls) == int(current_layout))
        has_create_custom = self.create_custom_action.isVisible()
        has_bible_layout = bible_layout_menu.menuAction().isVisible() if bible_layout_menu is not None else False
        custom_layout_section_visible = has_create_custom or has_bible_layout
        if hasattr(self, 'custom_layout_section_sep_before'):
            self.custom_layout_section_sep_before.setVisible(custom_layout_section_visible)
        if hasattr(self, 'custom_layout_section_sep_after'):
            self.custom_layout_section_sep_after.setVisible(custom_layout_section_visible)
        transition_visible = getattr(self, 'transition_action', None)
        transition_section_visible = (transition_visible.isVisible() if transition_visible is not None else False) or \
            self.auto_play_slides_menu.menuAction().isVisible()
        if hasattr(self, 'transition_section_sep_before'):
            self.transition_section_sep_before.setVisible(transition_section_visible)
        if hasattr(self, 'transition_section_sep_after'):
            self.transition_section_sep_after.setVisible(transition_section_visible)
        multiple = len(self.service_manager_list.selectedItems()) > 1
        for action in (self.edit_action, self.rename_action, self.maintain_action, self.create_custom_action,
                       self.time_action, self.auto_start_action, getattr(self, 'transition_action', None),
                       self.auto_play_slides_menu.menuAction(), self.theme_menu.menuAction(),
                       bible_layout_menu.menuAction() if bible_layout_menu is not None else None):
            if action is not None:
                action.setEnabled(not multiple)
        self._update_move_actions()
        self.menu.exec(self.service_manager_list.mapToGlobal(point))

    @staticmethod
    def _service_item_supports_transition(service_item):
        """
        Return True when item-level slide transitions are configurable for this service item.
        """
        is_pdf_presentation = (
            getattr(service_item, 'name', None) == 'presentations'
            and getattr(service_item, 'service_item_type', None) == ServiceItemType.Command
            and str(getattr(service_item, 'title', '')).lower().endswith('.pdf')
        )
        supports = (service_item.is_image() or getattr(service_item, 'is_slide_set', False) is True
                    or is_pdf_presentation)
        return supports

    @staticmethod
    def _get_service_item_transition_settings(service_item):
        """
        Return normalised transition settings for a service item.
        """
        settings = getattr(service_item, 'slide_transition_settings', None)
        if not isinstance(settings, dict):
            settings = {}
        transition_type = settings.get('type', TransitionType.Fade)
        if isinstance(transition_type, str):
            transition_type = TransitionType.from_string(transition_type) or TransitionType.Fade
        transition_speed = settings.get('speed', TransitionSpeed.Normal)
        if isinstance(transition_speed, str):
            transition_speed = TransitionSpeed.from_string(transition_speed) or TransitionSpeed.Normal
        return {
            'enabled': bool(settings.get('enabled', False)),
            'type': transition_type,
            'speed': transition_speed
        }

    def on_service_item_transition_form(self):
        """
        Configure slide transitions for the selected image, mixed Collection or PDF item.
        """
        item_index = self.find_service_item()[0]
        if item_index < 0:
            return
        service_item = self.service_items[item_index]['service_item']
        if not self._service_item_supports_transition(service_item):
            return
        settings = self._get_service_item_transition_settings(service_item)
        transition_types = [
            (translate('OpenLP.ServiceManager', 'Fade'), TransitionType.Fade),
            (translate('OpenLP.ServiceManager', 'Slide'), TransitionType.Slide),
            (translate('OpenLP.ServiceManager', 'Convex'), TransitionType.Convex),
            (translate('OpenLP.ServiceManager', 'Concave'), TransitionType.Concave),
            (translate('OpenLP.ServiceManager', 'Zoom'), TransitionType.Zoom)
        ]
        transition_speeds = [
            (translate('OpenLP.ServiceManager', 'Fast'), TransitionSpeed.Fast),
            (translate('OpenLP.ServiceManager', 'Normal'), TransitionSpeed.Normal),
            (translate('OpenLP.ServiceManager', 'Slow'), TransitionSpeed.Slow)
        ]
        dialog = QtWidgets.FormDialog(self)
        dialog.setWindowTitle(translate('OpenLP.ServiceManager', 'Transition'))
        dialog_layout = QtWidgets.QFormLayout(dialog.content_widget)
        transition_combo = QtWidgets.QComboBox(dialog)
        transition_combo.addItem(translate('OpenLP.ServiceManager', 'Disabled'), None)
        for label, value in transition_types:
            transition_combo.addItem(label, value)
        speed_combo = QtWidgets.QComboBox(dialog)
        for label, value in transition_speeds:
            speed_combo.addItem(label, value)
        dialog_layout.addRow(translate('OpenLP.ServiceManager', 'Type'), transition_combo)
        dialog_layout.addRow(translate('OpenLP.ServiceManager', 'Speed'), speed_combo)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=dialog
        )
        dialog_layout.addRow(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.setButtonBox(button_box)
        button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(
            translate('OpenLP.ServiceManager', 'Apply'))
        if settings['enabled']:
            type_index = transition_combo.findData(settings['type'])
            transition_combo.setCurrentIndex(max(0, type_index))
            speed_index = speed_combo.findData(settings['speed'])
            speed_combo.setCurrentIndex(max(0, speed_index))
        else:
            transition_combo.setCurrentIndex(0)
        transition_combo.currentIndexChanged.connect(lambda: speed_combo.setEnabled(transition_combo.currentData() is not None))
        speed_combo.setEnabled(transition_combo.currentData() is not None)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            dialog.deleteLater()
            return
        selected_type = transition_combo.currentData()
        service_item.slide_transition_settings = {
            'enabled': selected_type is not None,
            'type': selected_type if selected_type is not None else TransitionType.Fade,
            'speed': speed_combo.currentData() if speed_combo.currentData() is not None else TransitionSpeed.Normal
        }
        dialog.deleteLater()
        self._sync_pdf_service_item_transition_settings(service_item)
        if service_item.is_slide_set:
            service_item._clear_slides_cache()
        self.repaint_service_list(item_index, -1)
        self.preview_controller.replace_service_manager_item(service_item, item_index)
        self.live_controller.replace_service_manager_item(service_item, item_index)
        self.set_modified()

    @staticmethod
    def _transition_speed_to_seconds(transition_speed):
        speed_seconds_lookup = {
            TransitionSpeed.Fast: 0.4,
            TransitionSpeed.Normal: 0.8,
            TransitionSpeed.Slow: 1.2
        }
        return speed_seconds_lookup.get(transition_speed, 0.8)

    def _sync_pdf_service_item_transition_settings(self, service_item):
        """
        Apply service-item transition settings to PDF slide metadata used by the display layer.
        """
        if not isinstance(getattr(service_item, 'slides', None), list):
            return
        has_pdf_slides = any(isinstance(slide, dict) and slide.get('use_background_image') for slide in service_item.slides)
        if not has_pdf_slides:
            return
        settings = self._get_service_item_transition_settings(service_item)
        speed_seconds = self._transition_speed_to_seconds(settings['speed'])
        service_item.pdf_transition_settings = {
            'enabled': settings['enabled'],
            'effect': settings['type'],
            'speed': settings['speed'],
            'speed_seconds': speed_seconds,
            'easing': 'balanced',
            'type': settings['type']
        }
        for slide in service_item.slides:
            if isinstance(slide, dict) and slide.get('use_background_image'):
                slide['pdf_transition_enabled'] = settings['enabled']
                slide['pdf_transition_effect'] = settings['type']
                slide['pdf_transition_speed_seconds'] = speed_seconds
                slide['pdf_transition_easing'] = 'balanced'

    def on_bible_layout_style_action(self, checked=False):
        """
        Apply a Bible verse layout style to the selected service item and global Bible settings.
        """
        if not checked:
            return
        act = self.sender()
        if act is None:
            return
        layout_style = act.data()
        if layout_style is None:
            return
        layout_style = int(layout_style)
        item_idx, _ = self.find_service_item()
        if item_idx < 0 or item_idx >= len(self.service_items):
            return
        service_item = self.service_items[item_idx]['service_item']
        bible_media_item = None
        for plugin in State().list_plugins():
            if plugin.name == 'bibles' and plugin.is_active() and plugin.media_item:
                bible_media_item = plugin.media_item
                break
        if bible_media_item is None:
            return
        if not bible_media_item.apply_bible_layout_style_to_service_item(service_item, layout_style):
            critical_error_message_box(
                translate('OpenLP.ServiceManager', 'Bible layout'),
                translate(
                    'OpenLP.ServiceManager',
                    'This Bible item was saved before layout switching was available. '
                    'Remove it from the service and add the passage again, or change layout in the Bible Options tab.'),
                parent=self)
            return
        self.repaint_service_list(item_idx, -1)
        self.preview_controller.replace_service_manager_item(service_item, item_idx)
        self.live_controller.replace_service_manager_item(service_item, item_idx)
        self.set_modified()

    def on_service_item_note_form(self):
        """
        Allow the service note to be edited
        """
        indexes = self.selected_service_indexes()
        if not indexes:
            return
        notes = [self.service_items[index]['service_item'].notes for index in indexes]
        self.service_note_form.text_edit.setPlainText(notes[0] if all(note == notes[0] for note in notes) else '')
        if self.service_note_form.exec():
            for index in indexes:
                self.service_items[index]['service_item'].notes = self.service_note_form.text_edit.toPlainText()
                self._render_service_item_row(self.service_items[index], self.tree_widget_items[index],
                                              update_slides=False)
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
        self.repaint_service_list(item, -1)
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
        self.repaint_service_list(item, -1)
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
        self.repaint_service_list(item, -1)
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
        indexes = self.selected_service_indexes()
        if len(indexes) > 1:
            self._move_service_entries([self.service_items[index] for index in indexes], 0)
            return
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
        indexes = self.selected_service_indexes()
        if len(indexes) > 1:
            self._move_service_entries([self.service_items[index] for index in indexes], indexes[0] - 1)
            return
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
        indexes = self.selected_service_indexes()
        if len(indexes) > 1:
            self._move_service_entries([self.service_items[index] for index in indexes], indexes[-1] + 2)
            return
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
        indexes = self.selected_service_indexes()
        if len(indexes) > 1:
            self._move_service_entries([self.service_items[index] for index in indexes], len(self.service_items))
            return
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
            self._delete_confirmation_dialog() == QtWidgets.QMessageBox.StandardButton.Close
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
        if service_item >= 0 and service_item < len(self.tree_widget_items):
            tree_item = self.tree_widget_items[service_item]
            try:
                if tree_item.childCount() > 0 and self.service_items[service_item]['expanded'] and service_item_child >= 0:
                    self.service_manager_list.setCurrentIndex(
                        self.service_manager_list.model().index(service_item, 0).child(service_item_child, 0)
                    )
                else:
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
        self.service_manager_list.setUpdatesEnabled(False)
        self.service_manager_list.clearSelection()
        self.service_manager_list.clear()
        for _, item in enumerate(self.service_items):
            service_item_from_item = item['service_item']
            autoplay_loop_enabled = bool(service_item_from_item.auto_play_slides_loop)
            tree_widget_item = QtWidgets.QTreeWidgetItem(self.service_manager_list)
            self.tree_widget_items.append(tree_widget_item)
            is_dragged_item = item is self._internal_drag_item or item is self._external_drag_item
            if service_item_from_item.is_valid:
                themed_icon = self._create_colored_service_icon(service_item_from_item.icon, service_item_from_item)
                icon = themed_icon.pixmap(80, 80).toImage()
                icon = icon.scaled(80, 80, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                   QtCore.Qt.TransformationMode.SmoothTransformation)
                if service_item_from_item.notes:
                    painter = QtGui.QPainter(icon)
                    if autoplay_loop_enabled:
                        sync_pixmap = UiIcons().sync.pixmap(30, 30)
                        sync_overlay = sync_pixmap.toImage()
                        sync_overlay = sync_overlay.scaled(
                            30, 30, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation
                        )
                        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                        painter.setBrush(QtGui.QColor(0, 0, 0, 180))
                        painter.setPen(QtCore.Qt.PenStyle.NoPen)
                        painter.drawEllipse(QtCore.QRectF(16, 46, 38, 38))
                        painter.drawImage(20, 50, sync_overlay)
                    painter.end()
                    tree_widget_item.setIcon(0, build_icon(icon))
                elif service_item_from_item.temporary_edit:
                    overlay = QtGui.QImage(UiIcons().upload)
                    overlay = overlay.scaled(40, 40, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                             QtCore.Qt.TransformationMode.SmoothTransformation)
                    painter = QtGui.QPainter(icon)
                    painter.drawImage(40, 0, overlay)
                    if autoplay_loop_enabled:
                        sync_pixmap = UiIcons().sync.pixmap(30, 30)
                        sync_overlay = sync_pixmap.toImage()
                        sync_overlay = sync_overlay.scaled(
                            30, 30, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation
                        )
                        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                        painter.setBrush(QtGui.QColor(0, 0, 0, 180))
                        painter.setPen(QtCore.Qt.PenStyle.NoPen)
                        painter.drawEllipse(QtCore.QRectF(16, 46, 38, 38))
                        painter.drawImage(20, 50, sync_overlay)
                    painter.end()
                    tree_widget_item.setIcon(0, build_icon(icon))
                elif autoplay_loop_enabled:
                    painter = QtGui.QPainter(icon)
                    if autoplay_loop_enabled:
                        sync_pixmap = UiIcons().sync.pixmap(30, 30)
                        sync_overlay = sync_pixmap.toImage()
                        sync_overlay = sync_overlay.scaled(
                            30, 30, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation
                        )
                        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                        painter.setBrush(QtGui.QColor(0, 0, 0, 180))
                        painter.setPen(QtCore.Qt.PenStyle.NoPen)
                        painter.drawEllipse(QtCore.QRectF(16, 46, 38, 38))
                        painter.drawImage(20, 50, sync_overlay)
                    painter.end()
                    composed_icon = build_icon(icon)
                    tree_widget_item.setIcon(0, composed_icon)
                else:
                    tree_widget_item.setIcon(0, themed_icon)
            else:
                tree_widget_item.setIcon(0, UiIcons().delete)
            title = service_item_from_item.get_display_title()
            tree_widget_item.setText(0, title)

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
            self._update_item_indicators(tree_widget_item, service_item_from_item, tips)
            tree_widget_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item['order'])
            tree_widget_item.setSelected(item['selected'] and not is_dragged_item)
            if is_dragged_item:
                dragged_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
                dragged_text_color.setAlpha(140)
                tree_widget_item.setForeground(0, QtGui.QBrush(dragged_text_color))
            # Add the children to their parent tree_widget_item.
            frames = service_item_from_item.get_frames()
            # Don't add children for Media/Image/Presentation items with only a single sub-item
            if not (service_item_from_item.name in ['images', 'media', 'presentations'] and len(frames) == 1):
                for slide_index, slide in enumerate(frames):
                    try:
                        child = QtWidgets.QTreeWidgetItem(tree_widget_item)
                        # prefer to use a display_title
                        if service_item_from_item.is_capable(ItemCapabilities.HasDisplayTitle) or \
                                service_item_from_item.service_item_type is not ServiceItemType.Text:
                            text = slide['title'].replace('\n', ' ')
                        else:
                            text = service_item_from_item.get_rendered_frame(slide_index, clean=True)
                        # For presentations, use "Slide N" instead of repeating the title
                        if service_item_from_item.name == 'presentations':
                            text = f"Slide {slide_index + 1}"
                        # For songs, add the section label
                        if service_item_from_item.name == 'songs':
                            text = slide['verse'] + ': ' + text
                        # Hide formatting tags from preview
                        text = remove_tags(text)
                        # Flatten to a single preview line and remove excess spacing
                        text = ' '.join(line.strip() for line in text.splitlines() if line.strip())
                        text = ' '.join(text.split())
                        # For songs, use HTML to dim the label (but since HTML not supported, use plain)
                        child.setText(0, text)
                        child.setData(0, QtCore.Qt.ItemDataRole.UserRole, slide_index)
                        self._set_child_thumbnail(child, service_item_from_item, slide)
                        if is_dragged_item:
                            child_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
                            child_text_color.setAlpha(140)
                            child.setForeground(0, QtGui.QBrush(child_text_color))
                    except RuntimeError:
                        # QTreeWidgetItem was deleted by a concurrent repaint.
                        self.service_manager_list.setUpdatesEnabled(True)
                        self.is_running_repaint = False
                        return True
            tree_widget_item.setExpanded(item['expanded'])
        self.service_manager_list.setUpdatesEnabled(True)
        self.is_running_repaint = False
        self._update_move_actions()
        return False

    def _render_service_item_row(self, item_data, tree_widget_item, update_slides=True):
        """Render one top-level service row and its children into an existing QTreeWidgetItem."""
        service_item_from_item = item_data['service_item']
        autoplay_loop_enabled = bool(service_item_from_item.auto_play_slides_loop)
        is_dragged_item = item_data is self._internal_drag_item or item_data is self._external_drag_item
        if service_item_from_item.is_valid:
            themed_icon = self._create_colored_service_icon(service_item_from_item.icon, service_item_from_item)
            icon = themed_icon.pixmap(80, 80).toImage()
            icon = icon.scaled(80, 80, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                               QtCore.Qt.TransformationMode.SmoothTransformation)
            if service_item_from_item.notes:
                painter = QtGui.QPainter(icon)
                if autoplay_loop_enabled:
                    sync_overlay = UiIcons().sync.pixmap(30, 30).toImage().scaled(
                        30, 30, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation
                    )
                    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                    painter.setBrush(QtGui.QColor(0, 0, 0, 180))
                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                    painter.drawEllipse(QtCore.QRectF(16, 46, 38, 38))
                    painter.drawImage(20, 50, sync_overlay)
                painter.end()
                tree_widget_item.setIcon(0, build_icon(icon))
            elif service_item_from_item.temporary_edit:
                overlay = QtGui.QImage(UiIcons().upload)
                overlay = overlay.scaled(40, 40, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                         QtCore.Qt.TransformationMode.SmoothTransformation)
                painter = QtGui.QPainter(icon)
                painter.drawImage(40, 0, overlay)
                if autoplay_loop_enabled:
                    sync_overlay = UiIcons().sync.pixmap(30, 30).toImage().scaled(
                        30, 30, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation
                    )
                    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                    painter.setBrush(QtGui.QColor(0, 0, 0, 180))
                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                    painter.drawEllipse(QtCore.QRectF(16, 46, 38, 38))
                    painter.drawImage(20, 50, sync_overlay)
                painter.end()
                tree_widget_item.setIcon(0, build_icon(icon))
            elif autoplay_loop_enabled:
                painter = QtGui.QPainter(icon)
                sync_overlay = UiIcons().sync.pixmap(30, 30).toImage().scaled(
                    30, 30, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                )
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                painter.setBrush(QtGui.QColor(0, 0, 0, 180))
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.drawEllipse(QtCore.QRectF(16, 46, 38, 38))
                painter.drawImage(20, 50, sync_overlay)
                painter.end()
                tree_widget_item.setIcon(0, build_icon(icon))
            else:
                tree_widget_item.setIcon(0, themed_icon)
        else:
            tree_widget_item.setIcon(0, UiIcons().delete)
        title = service_item_from_item.get_display_title()
        tree_widget_item.setText(0, title)

        tips = []
        if service_item_from_item.temporary_edit:
            text1 = translate('OpenLP.ServiceManager', 'Edit')
            text2 = translate('OpenLP.ServiceManager', 'Service copy only')
            tips.append('<strong>{text1}:</strong> <em>{text2}</em>'.format(text1=text1, text2=text2))
        if service_item_from_item.theme and service_item_from_item.theme != -1:
            text = translate('OpenLP.ServiceManager', 'Slide theme')
            tips.append('<strong>{text1}:</strong> <em>{text2}</em>'.format(text1=text, text2=service_item_from_item.theme))
        if service_item_from_item.notes:
            text1 = translate('OpenLP.ServiceManager', 'Notes')
            text2 = html.escape(service_item_from_item.notes)
            tips.append('<strong>{text1}: </strong> {text2}'.format(text1=text1, text2=text2))
        if item_data['service_item'].is_capable(ItemCapabilities.HasVariableStartTime):
            tips.append(item_data['service_item'].get_media_time())
        if item_data['service_item'].is_capable(ItemCapabilities.HasMetaData):
            for meta in item_data['service_item'].metadata:
                tips.append(meta)
        tree_widget_item.setToolTip(0, '<br>'.join(tips))
        self._update_item_indicators(tree_widget_item, service_item_from_item, tips)
        if not update_slides:
            return
        tree_widget_item.setSelected(item_data['selected'] and not is_dragged_item)
        if is_dragged_item:
            dragged_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
            dragged_text_color.setAlpha(140)
            tree_widget_item.setForeground(0, QtGui.QBrush(dragged_text_color))
        frames = service_item_from_item.get_frames()
        if not (service_item_from_item.name in ['images', 'media', 'presentations'] and len(frames) == 1):
            for slide_index, slide in enumerate(frames):
                try:
                    child = QtWidgets.QTreeWidgetItem(tree_widget_item)
                    if service_item_from_item.is_capable(ItemCapabilities.HasDisplayTitle) or \
                            service_item_from_item.service_item_type is not ServiceItemType.Text:
                        text = slide['title'].replace('\n', ' ')
                    else:
                        text = service_item_from_item.get_rendered_frame(slide_index, clean=True)
                    if service_item_from_item.name == 'presentations':
                        text = f"Slide {slide_index + 1}"
                    if service_item_from_item.name == 'songs':
                        text = slide['verse'] + ': ' + text
                    text = remove_tags(text)
                    text = ' '.join(line.strip() for line in text.splitlines() if line.strip())
                    text = ' '.join(text.split())
                    child.setText(0, text)
                    child.setData(0, QtCore.Qt.ItemDataRole.UserRole, slide_index)
                    self._set_child_thumbnail(child, service_item_from_item, slide)
                    if is_dragged_item:
                        child_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
                        child_text_color.setAlpha(140)
                        child.setForeground(0, QtGui.QBrush(child_text_color))
                except RuntimeError:
                    # QTreeWidgetItem was deleted by a concurrent repaint.
                    return
        tree_widget_item.setExpanded(item_data['expanded'])

    def _set_child_thumbnail(self, child, service_item, slide):
        if service_item.name == 'images':
            image_path = slide.get('thumbnail') or slide.get('path')
            icon_pixmap = QtGui.QPixmap(64, 48)
            icon_pixmap.fill(QtCore.Qt.GlobalColor.transparent)
            if service_item.is_slide_set is True:
                from openlp.core.lib.slideset import set_thumbnail
                img_pixmap = set_thumbnail(service_item, int(slide['verse']) - 1)
            else:
                img_pixmap = QtGui.QPixmap(str(image_path)) if image_path else QtGui.QPixmap()
            if not img_pixmap.isNull():
                scaled_img = img_pixmap.scaled(64, 48, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                               QtCore.Qt.TransformationMode.SmoothTransformation)
                painter = QtGui.QPainter(icon_pixmap)
                x = (64 - scaled_img.width()) // 2
                y = (48 - scaled_img.height()) // 2
                painter.drawPixmap(x, y, scaled_img)
                # Draw a subtle 1px border around the scaled image
                pen = QtGui.QPen(QtGui.QColor(128, 128, 128, 180))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawRect(x, y, scaled_img.width() - 1, scaled_img.height() - 1)
                painter.end()
            child.setIcon(0, QtGui.QIcon(icon_pixmap))

    def _update_item_indicators(self, tree_widget_item, service_item, tips):
        transition_settings = self._get_service_item_transition_settings(service_item)
        transition_enabled = self._service_item_supports_transition(service_item) and \
            transition_settings.get('enabled', False)
        indicators = []
        if transition_enabled:
            indicators.append('shape_subtract')
        if service_item.notes:
            indicators.append('note')
        tree_widget_item.setData(0, SERVICE_ITEM_INDICATORS_ROLE, indicators)

    def _refresh_tree_rows_from_service_items(self, start_index=0):
        """Update top-level order metadata and row styling after in-place list changes."""
        for index, item_data in enumerate(self.service_items):
            item_data['order'] = index + 1
            if index >= len(self.tree_widget_items):
                continue
            tree_item = self.tree_widget_items[index]
            tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item_data['order'])
            if item_data is self._internal_drag_item:
                dragged_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
                dragged_text_color.setAlpha(140)
                drag_brush = QtGui.QBrush(dragged_text_color)
                tree_item.setForeground(0, drag_brush)
                for child_index in range(tree_item.childCount()):
                    tree_item.child(child_index).setForeground(0, drag_brush)

        for controller in (self.preview_controller, self.live_controller):
            if controller and isinstance(controller.service_item, ServiceItem):
                controller._service_manager_item_index = next(
                    (i for i, entry in enumerate(self.service_items)
                     if entry['service_item'].unique_identifier == controller.service_item.unique_identifier), None)

    def _insert_service_item_row(self, index):
        """Insert a single rendered row at index without rebuilding the full list."""
        tree_item = QtWidgets.QTreeWidgetItem()
        self._render_service_item_row(self.service_items[index], tree_item)
        self.service_manager_list.insertTopLevelItem(index, tree_item)
        self.tree_widget_items.insert(index, tree_item)
        self._refresh_tree_rows_from_service_items(max(0, index))

    def _move_service_item_row(self, from_index, to_index):
        """Move one service row and matching data model entry without full repaint."""
        if from_index == to_index:
            return
        dragged_item = self.service_items.pop(from_index)
        self.service_items.insert(to_index, dragged_item)
        if from_index >= self.service_manager_list.topLevelItemCount() or to_index > self.service_manager_list.topLevelItemCount():
            self._refresh_tree_rows_from_service_items(min(from_index, to_index))
            return
        if from_index >= len(self.tree_widget_items):
            self._refresh_tree_rows_from_service_items(min(from_index, to_index))
            return
        expanded = self.tree_widget_items[from_index].isExpanded()
        with QtCore.QSignalBlocker(self.service_manager_list):
            moved_tree_item = self.service_manager_list.takeTopLevelItem(from_index)
            self.service_manager_list.insertTopLevelItem(to_index, moved_tree_item)
            moved_tree_widget_item = self.tree_widget_items.pop(from_index)
            self.tree_widget_items.insert(to_index, moved_tree_widget_item)
            self._refresh_tree_rows_from_service_items(min(from_index, to_index))
            moved_tree_item.setExpanded(expanded)

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
            if replace < len(self.tree_widget_items):
                tree_item = self.tree_widget_items[replace]
                tree_item.takeChildren()
                self._render_service_item_row(self.service_items[replace], tree_item)
                self._refresh_tree_rows_from_service_items(replace)
            elif repaint:
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
                        if repaint:
                            self._insert_service_item_row(len(self.service_items) - 1)
                else:
                    self.service_items.append({'service_item': item,
                                               'order': len(self.service_items) + 1,
                                               'expanded': expand, 'selected': selected})
                    if repaint:
                        self._insert_service_item_row(len(self.service_items) - 1)
            else:
                self.service_items.insert(self.drop_position,
                                          {'service_item': item, 'order': self.drop_position,
                                           'expanded': expand, 'selected': selected})
                if repaint:
                    self._insert_service_item_row(self.drop_position)
            # if rebuilding list make sure live is fixed.
            if rebuild:
                self.live_controller.replace_service_manager_item(item)
            if repaint and self.drop_position != -1 and self.drop_position < len(self.tree_widget_items):
                self.service_manager_list.setCurrentItem(self.tree_widget_items[self.drop_position])
            elif repaint and self.service_items and self.drop_position == -1:
                self.service_manager_list.setCurrentItem(self.tree_widget_items[len(self.service_items) - 1])
        self.drop_position = -1
        self._update_move_actions()
        self.set_modified()

    def delete_item(self):
        """
        Remove the current item from the service.
        """
        indexes = self.selected_service_indexes()
        if indexes:
            for index in reversed(indexes):
                self.service_items.pop(index)
            self.repaint_service_list(indexes[0] - 1, -1)
            self.set_modified()
            self.servicemanager_changed.emit()

    def make_preview(self):
        """
        Send the current item to the Preview slide controller
        """
        if len(self.service_manager_list.selectedItems()) > 1:
            return
        self.application.set_busy_cursor()
        try:
            item, child = self.find_service_item()
            if item < 0 or item >= len(self.service_items):
                return
            if self.service_items[item]['service_item'].is_valid:
                self.preview_controller.add_service_manager_item(
                    self.service_items[item]['service_item'], child, service_list_index=item)
            else:
                critical_error_message_box(translate('OpenLP.ServiceManager', 'Unavailable Service Item'),
                                           translate('OpenLP.ServiceManager',
                                                     'This item cannot be displayed because its source file is missing '
                                                     'or its display handler is unavailable.'))
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
        self.make_live()

    def on_single_click_preview(self):
        """
        Preview the clicked item immediately when single-click previewing is enabled.

        The tree emits clicked for the first click and doubleClicked for the second,
        so a double-click can still send the item Live without delaying Preview.
        """
        if self.settings.value('advanced/single click service preview'):
            self.make_preview()

    def make_live(self, row=-1):
        """
        Send the current item to the Live slide controller

        :param row: Row number to be displayed if from preview. -1 is passed if the value is not set
        """
        if len(self.service_manager_list.selectedItems()) > 1:
            return
        item, child = self.find_service_item()
        # No items in service
        if item == -1 or item >= len(self.service_items):
            return
        if row != -1:
            child = row
        self.application.set_busy_cursor()
        if self.service_items[item]['service_item'].is_valid:
            self.servicemanager_changed.emit()
            self.live_controller.add_service_manager_item(
                self.service_items[item]['service_item'], child, service_list_index=item)
            if self.settings.value('core/auto preview'):
                item += 1
                if self.service_items and item < len(self.service_items) and \
                        self.service_items[item]['service_item'].is_capable(ItemCapabilities.CanPreview):
                    self.preview_controller.add_service_manager_item(
                        self.service_items[item]['service_item'], 0, service_list_index=item)
                    self.live_controller.preview_widget.setFocus()
        else:
            critical_error_message_box(translate('OpenLP.ServiceManager', 'Unavailable Service Item'),
                                       translate('OpenLP.ServiceManager',
                                                 'This item cannot be displayed because its source file is missing '
                                                 'or its display handler is unavailable.'))
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
        item, child = self.find_service_item()
        if item < 0:
            return
        service_item = self.service_items[item]['service_item']
        if not service_item.is_capable(ItemCapabilities.CanEditTitle):
            return
        slide_index = None
        if child >= 0 and (service_item.is_image() or service_item.is_slide_set):
            slide_index = service_item.get_frames()[child].get('raw_index', child)
        title = service_item.title if slide_index is None else service_item.slides[slide_index]['title']
        dialog_title = translate('OpenLP.ServiceManager', 'Rename item title') if slide_index is None else \
            translate('OpenLP.ServiceManager', 'Rename slide label')
        field_label = translate('OpenLP.ServiceManager', 'Title') if slide_index is None else \
            translate('OpenLP.ServiceManager', 'Label')
        title, ok = RenameDialog.get_text(self.main_window, dialog_title,
                                         field_label, title)
        if ok and title.strip():
            if slide_index is None:
                service_item.title = title.strip()
            else:
                service_item.slides[slide_index]['title'] = title.strip()
                service_item._clear_slides_cache()
            self.repaint_service_list(item, -1)
            if slide_index is not None:
                self.preview_controller.replace_service_manager_item(service_item, item)
                self.live_controller.replace_service_manager_item(service_item, item)
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

    def selected_service_indexes(self):
        """Return selected service positions once each, in service order."""
        rows = {get_parent_item_data(item) for item in self.service_manager_list.selectedItems()}
        return sorted(row - 1 for row in rows if row is not None and 0 < row <= len(self.service_items))

    def on_selection_changed(self):
        """
        Called whenever the selection in the service manager list changes. Updates the enabled state of the
        move toolbar buttons, and clears any Library selection so the Preview panel is not polluted by a
        previously-highlighted library item.
        """
        self._update_move_actions()
        if self.service_manager_list.selectedItems():
            self._clear_library_selections()

    def _clear_library_selections(self):
        """
        Deselect all items in every Library panel so that switching service items does not trigger a
        library single-click preview in the Preview controller.
        """
        try:
            media_tool_box = self.main_window.media_tool_box
            for i in range(media_tool_box.count()):
                widget = media_tool_box.widget(i)
                if widget is not None and hasattr(widget, 'list_view'):
                    widget.list_view.clearSelection()
        except Exception:
            pass

    def _update_move_actions(self):
        """
        Enable or disable selection-based toolbar actions based on whether a top-level service item is selected.
        Move actions are also constrained by top/bottom boundaries.
        """
        if not hasattr(self, 'move_top_action'):
            return
        item, _ = self.find_service_item()
        if item == -1 and hasattr(self, 'service_manager_list'):
            current_item = self.service_manager_list.currentItem()
            if current_item is not None:
                parent_item = current_item.parent()
                top_item = parent_item if parent_item is not None else current_item
                row = top_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if row is not None:
                    item = row - 1
        count = len(self.service_items)
        has_items = count > 0
        has_selection = item != -1 or any(service_item.get('selected', False) for service_item in self.service_items)
        indexes = self.selected_service_indexes()
        at_top = (indexes[0] if indexes else item) == 0
        at_bottom = (indexes[-1] if indexes else item) == count - 1
        if hasattr(self, 'delete_action'):
            self.delete_action.setEnabled(has_items)
        if hasattr(self, 'expand_collapse_action'):
            self.expand_collapse_action.setEnabled(has_items)
        if hasattr(self, 'save_service_action'):
            self.save_service_action.setEnabled(has_items)
        if hasattr(self, 'save_service_as_action'):
            self.save_service_as_action.setEnabled(has_items)
        single_selection = has_selection and len(self.service_manager_list.selectedItems()) <= 1
        if hasattr(self, 'make_preview_action'):
            self.make_preview_action.setEnabled(single_selection)
        if hasattr(self, 'make_live_action'):
            self.make_live_action.setEnabled(single_selection)
        if hasattr(self, 'preview_action'):
            self.preview_action.setEnabled(single_selection)
        if hasattr(self, 'note_toolbar_action'):
            self.note_toolbar_action.setEnabled(has_selection)
        self.move_top_action.setEnabled(has_selection and not at_top)
        self.move_up_action.setEnabled(has_selection and not at_top)
        self.move_down_action.setEnabled(has_selection and not at_bottom)
        self.move_bottom_action.setEnabled(has_selection and not at_bottom)

    def is_internal_drag_active(self):
        return self._internal_drag_item is not None

    def is_external_drag_active(self):
        return self._external_drag_plugin_name is not None

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
        Start external drag preview state and track a lightweight insertion target without
        mutating the service item list.

        :param plugin_name: The plugin name from the drag MIME data (e.g. 'songs', 'images').
        :param item_title: The actual title of the item being dragged, if available.
        :returns: The display title used by the drag tooltip.
        """
        display_title = item_title or self._PLUGIN_DISPLAY_NAMES.get(plugin_name, plugin_name.title())
        self._external_drag_item = object()
        self._external_drag_plugin_name = plugin_name
        self._external_drag_target_index = len(self.service_items)
        self._set_external_drag_highlight(self._external_drag_target_index)
        return display_title

    def update_external_drag_preview(self, pos):
        """Move the external drag placeholder to the position under the cursor."""
        if not self.is_external_drag_active():
            return
        target_index = self._get_internal_drag_target_index(pos)
        self._move_external_drag_preview(target_index)

    def _move_external_drag_preview(self, target_index):
        insert_index = max(0, min(target_index, len(self.service_items)))
        if insert_index == self._external_drag_target_index:
            return
        self._external_drag_target_index = insert_index
        self._set_external_drag_highlight(insert_index)

    def _get_external_drag_item_index(self):
        if not self.is_external_drag_active():
            return -1
        return self._external_drag_target_index

    def _set_external_drag_highlight(self, insert_index):
        self.service_manager_list.set_drop_position(insert_index)

    def _clear_external_drag_highlight(self):
        self.service_manager_list.set_drop_position(None)

    def cancel_external_drag_preview(self):
        """Remove the external drag placeholder without committing."""
        if not self.is_external_drag_active():
            return
        self._clear_external_drag_highlight()
        self._external_drag_item = None
        self._external_drag_plugin_name = None
        self._external_drag_target_index = -1

    def finish_external_drag_preview(self):
        """
        Commit the external drag: record the tracked insertion target as drop_position.
        """
        if not self.is_external_drag_active():
            return
        idx = self._get_external_drag_item_index()
        self._clear_external_drag_highlight()
        self._external_drag_item = None
        self._external_drag_plugin_name = None
        self._external_drag_target_index = -1
        if idx != -1:
            self.drop_position = idx

    def begin_internal_drag(self):
        start_pos, child = self.find_service_item()
        if start_pos == -1 or start_pos >= len(self.service_items):
            return False
        self._internal_drag_items = [self.service_items[index] for index in self.selected_service_indexes()]
        self._internal_drag_item = self.service_items[start_pos]
        self._internal_drag_target_index = start_pos
        self._internal_drag_child = child
        self._apply_internal_drag_grab_visual(start_pos)
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
        entries = self._internal_drag_items
        target_index = self._internal_drag_target_index
        child = self._internal_drag_child
        self._clear_internal_drag_grab_visual()
        self._internal_drag_item = None
        self._internal_drag_items = []
        self._internal_drag_target_index = None
        self._internal_drag_child = -1
        self.service_manager_list.set_drop_position(None)
        if is_drop_complete:
            self._move_service_entries(entries, target_index, child)
        self._update_move_actions()

    def _move_service_entries(self, entries, boundary, child=-1):
        """Move the captured selection as a block, preserving order and tree rows."""
        positions = [index for index, entry in enumerate(self.service_items)
                     if any(entry is selected for selected in entries)]
        if len(positions) != len(entries) or not positions:
            return
        boundary = max(0, min(boundary, len(self.service_items)))
        insert_index = boundary - sum(index < boundary for index in positions)
        remaining = [entry for index, entry in enumerate(self.service_items) if index not in positions]
        order = remaining[:insert_index] + entries + remaining[insert_index:]
        changed = any(old is not new for old, new in zip(self.service_items, order))
        with QtCore.QSignalBlocker(self.service_manager_list):
            for index, entry in enumerate(order):
                current = next(pos for pos, value in enumerate(self.service_items) if value is entry)
                self._move_service_item_row(current, index)
            self.service_manager_list.clearSelection()
            for offset in range(len(entries)):
                row = self.tree_widget_items[insert_index + offset]
                if len(entries) == 1 and 0 <= child < row.childCount():
                    row = row.child(child)
                if offset == 0:
                    self.service_manager_list.setCurrentItem(row)
                row.setSelected(True)
        if changed:
            self.set_modified()
            self.servicemanager_changed.emit()
        self._update_move_actions()

    def _apply_internal_drag_grab_visual(self, item_index):
        """Dim the grabbed item in-place so drag start does not trigger a full list repaint."""
        self._clear_internal_drag_grab_visual()
        if item_index < 0 or item_index >= len(self.tree_widget_items):
            return
        root_item = self.tree_widget_items[item_index]
        dragged_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
        dragged_text_color.setAlpha(140)
        drag_brush = QtGui.QBrush(dragged_text_color)
        root_item.setForeground(0, drag_brush)
        for child_index in range(root_item.childCount()):
            root_item.child(child_index).setForeground(0, drag_brush)
        self._internal_drag_visual_item_index = item_index

    def _clear_internal_drag_grab_visual(self):
        if self._internal_drag_visual_item_index == -1:
            return
        if self._internal_drag_visual_item_index < len(self.tree_widget_items):
            root_item = self.tree_widget_items[self._internal_drag_visual_item_index]
            root_item.setForeground(0, QtGui.QBrush())
            for child_index in range(root_item.childCount()):
                root_item.child(child_index).setForeground(0, QtGui.QBrush())
        self._internal_drag_visual_item_index = -1

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
            if (self.tree_widget_items
                    and pos.y() < self.service_manager_list.visualItemRect(self.tree_widget_items[0]).top()):
                return 0
            return len(self.service_items)
        target_item = target_item if target_item.parent() is None else target_item.parent()
        target_index = get_parent_item_data(target_item) - 1
        if pos.y() > self.service_manager_list.visualItemRect(target_item).center().y():
            target_index += 1
        return target_index

    def _move_internal_drag_preview(self, target_index):
        self._internal_drag_target_index = max(0, min(target_index, len(self.service_items)))
        self.service_manager_list.set_drop_position(self._internal_drag_target_index)

    def drop_event(self, event):
        """
        Receive drop event and trigger an internal event to get the plugins to build and push the correct service item.
        The drag event payload carries the plugin name

        :param event: Handle of the event passed
        """
        link = event.mimeData()
        self.service_manager_list._drag_scroll_timer.stop()
        self.service_manager_list._theme_drag_data = None
        self.service_manager_list.set_drop_position(None)
        if not self.service_manager_list.can_accept_drop(event):
            self.cancel_external_drag_preview()
            event.ignore()
            return
        if isinstance(link, ThemeDragData):
            self.cancel_external_drag_preview()
            if self.apply_theme_to_item(self.service_manager_list.theme_drop_item(event.pos()), link.title):
                event.setDropAction(QtCore.Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
            return
        if isinstance(link, ItemDragData):
            self.cancel_external_drag_preview()
            if event.source() is self.service_manager_list:
                if not self.is_internal_drag_active() or self._get_internal_drag_item_index() == -1:
                    event.ignore()
                    return
                self.update_internal_drag_preview(event.pos())
                self.finish_internal_drag(True)
                event.setDropAction(QtCore.Qt.DropAction.MoveAction)
            else:
                position = self._get_internal_drag_target_index(event.pos())
                items = link.service_items()
                if not items:
                    event.ignore()
                    return
                for offset, item in enumerate(items):
                    if link.library is None:
                        item = copy_service_item(item)
                    item.from_plugin = False
                    self.add_service_item(item, position=position + offset)
                event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            return
        if link.hasUrls():
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            for url in link.urls():
                file_path = Path(url.toLocalFile())
                if file_path.suffix.lower() in SERVICE_SUFFIXES:
                    self.load_service(file_path)
        else:
            event.ignore()

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

    def apply_theme_to_item(self, service_item, theme):
        """Apply an explicit theme drop and refresh every pane showing this item."""
        if not supports_theme_drop(service_item):
            return False
        identifier = service_item.unique_identifier
        controllers = [controller for controller in (self.preview_controller, self.live_controller)
                       if controller.service_item and controller.service_item.unique_identifier == identifier]
        index = next((i for i, entry in enumerate(self.service_items)
                      if entry['service_item'].unique_identifier == identifier), None)
        if index is None and service_item.from_service:
            index = next((controller._service_manager_item_index for controller in controllers
                          if isinstance(controller._service_manager_item_index, int)
                          and 0 <= controller._service_manager_item_index < len(self.service_items)
                          and self.service_items[controller._service_manager_item_index]['service_item'].name
                          == service_item.name), None)
        if index is not None:
            service_item = self.service_items[index]['service_item']
        if not supports_theme_drop(service_item):
            return False
        controllers = [controller for controller in (self.preview_controller, self.live_controller)
                       if controller in controllers or (controller.service_item and
                       controller.service_item.unique_identifier == service_item.unique_identifier)]
        changed = service_item.get_theme_data().theme_name != theme
        if changed:
            service_item.update_theme(theme)
            # A deliberate item override must also work at Global and Service theme levels.
            service_item.add_capability(ItemCapabilities.ProvidesOwnTheme)
            service_item.render_text_items()
            if index is not None:
                self.repaint_service_list(*self.find_service_item())
                self.set_modified()
        for controller in controllers:
            if (changed or controller.service_item.unique_identifier != service_item.unique_identifier
                    or controller.service_item.get_theme_data().theme_name != theme):
                controller._service_manager_item_index = index
                controller.refresh_service_item(service_item)
        return True

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
