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

from PySide6 import QtCore, QtWidgets

from openlp.core.common.i18n import UiStrings, translate
from openlp.core.common.registry import Registry
from openlp.core.lib import ServiceItemContext, build_icon, create_thumb, validate_thumb
from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem
from openlp.core.lib.theme import TransitionSpeed, TransitionType
from openlp.core.lib.ui import create_horizontal_adjusting_combo_box, create_widget_action, critical_error_message_box
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.library import FolderLibraryItem
from openlp.core.widgets.views import FileTreeWidgetItem

from openlp.plugins.presentations.lib.db import Folder, Item
from openlp.plugins.presentations.lib.messagelistener import MessageListener
from openlp.plugins.presentations.lib.pdfcontroller import PDF_CONTROLLER_FILETYPES


log = logging.getLogger(__name__)


def _format_file_size(size: int) -> str:
    """Return a human-readable file size string."""
    for unit, threshold in (('GB', 1 << 30), ('MB', 1 << 20), ('KB', 1 << 10)):
        if size >= threshold:
            return f'{size / threshold:.1f} {unit}'
    return f'{size} B'


class PresentationMediaItem(FolderLibraryItem):
    """
    This is the Presentation media manager item for Presentation Items. It can present files using Openoffice and
    Powerpoint
    """
    presentations_go_live = QtCore.Signal(list)
    presentations_add_to_service = QtCore.Signal(list)
    log.info('Presentations Media Item loaded')

    def __init__(self, parent, plugin, controllers):
        """
        Constructor. Setup defaults
        """
        self.icon_path = 'presentations/presentation'
        self.controllers = controllers
        super(PresentationMediaItem, self).__init__(parent, plugin, Folder, Item)

    def retranslate_ui(self):
        """
        The name of the plugin media displayed in UI
        """
        super().retranslate_ui()
        self.on_new_prompt = translate('PresentationPlugin.MediaItem', 'Select Presentation(s)')
        self.automatic = translate('PresentationPlugin.MediaItem', 'Automatic')
        self.display_type_label.setText(translate('PresentationPlugin.MediaItem', 'Present using:'))

    def setup_item(self):
        """
        Do some additional setup.
        """
        self.presentations_go_live.connect(self.go_live_remote)
        self.presentations_add_to_service.connect(self.add_to_service_remote)
        self.message_listener = MessageListener(self)
        self.has_search = True
        self.single_service_item = False
        Registry().register_function('mediaitem_presentation_rebuild', self.populate_display_types)
        Registry().register_function('mediaitem_suffixes', self.build_file_mask_string)
        Registry().register_function('presentations_pdf_transition_settings_changed',
                                     self.apply_pdf_transition_settings_to_active_items)
        # Allow DnD from the desktop
        self.list_view.activateDnD()
        self.list_view.setup_columns([translate('PresentationPlugin.MediaItem', 'Name'),
                                      translate('PresentationPlugin.MediaItem', 'Date')])

    @staticmethod
    def apply_pdf_transition_settings_to_active_items():
        for controller_key in ('preview_controller', 'live_controller'):
            controller = Registry().get(controller_key)
            if controller and hasattr(controller, 'apply_pdf_transition_settings'):
                controller.apply_pdf_transition_settings()

    def required_icons(self):
        """
        Set which icons the media manager tab should show.
        """
        super().required_icons()
        self.has_file_icon = True
        self.has_new_icon = False
        self.has_edit_icon = False

    def initialise(self):
        """
        Populate the media manager tab
        """
        self.list_view.clear()
        self.list_view.setIndentation(self.list_view.default_indentation)
        self.list_view.allow_internal_dnd = True
        self.list_view.setIconSize(QtCore.QSize(88, 50))
        self.load_list(self.manager.get_all_objects(Item, order_by_ref=Item.file_path), is_initial_load=True)
        self.populate_display_types()

    def add_custom_context_actions(self):
        """
        Add custom actions to the context menu.
        """
        super().add_custom_context_actions()

    def add_middle_header_bar(self):
        """
        Display custom media manager items for presentations.
        """
        super().add_middle_header_bar()
        self.presentation_widget = QtWidgets.QWidget(self)
        self.presentation_widget.setObjectName('presentation_widget')
        self.display_layout = QtWidgets.QFormLayout(self.presentation_widget)
        self.display_layout.setContentsMargins(self.display_layout.spacing(), self.display_layout.spacing(),
                                               self.display_layout.spacing(), self.display_layout.spacing())
        self.display_layout.setObjectName('display_layout')
        self.display_type_label = QtWidgets.QLabel(self.presentation_widget)
        self.display_type_label.setObjectName('display_type_label')
        self.display_type_combo_box = create_horizontal_adjusting_combo_box(self.presentation_widget,
                                                                            'display_type_combo_box')
        self.display_type_label.setBuddy(self.display_type_combo_box)
        self.display_layout.addRow(self.display_type_label, self.display_type_combo_box)
        # Add the Presentation widget to the page layout.
        self.panel_layout.addWidget(self.presentation_widget)

    def build_file_mask_string(self):
        """
        Build the list of file extensions to be used in the Open file dialog.
        """
        file_type_string = ''
        for controller in self.controllers:
            if self.controllers[controller].enabled():
                file_types = self.controllers[controller].supports + self.controllers[controller].also_supports
                for file_type in file_types:
                    if file_type not in file_type_string:
                        file_type_string += '*.{text} '.format(text=file_type)
        file_type_string = file_type_string.strip()
        self.service_manager.supported_suffixes(file_type_string.split(' '))
        self.on_new_file_masks = translate('PresentationPlugin.MediaItem',
                                           'Presentations ({text})').format(text=file_type_string)

    def populate_display_types(self):
        """
        Load the combobox with the enabled presentation controllers, allowing user to select a specific app if settings
        allow.
        """
        self.display_type_combo_box.clear()
        for item in self.controllers:
            # For PDF reload backend, since it can have changed
            if self.controllers[item].name == 'Pdf':
                self.controllers[item].check_available()
            # load the drop down selection
            if self.controllers[item].enabled():
                self.display_type_combo_box.addItem(item)
        if self.display_type_combo_box.count() > 1:
            self.display_type_combo_box.insertItem(0, self.automatic, userData='automatic')
            self.display_type_combo_box.setCurrentIndex(0)
        if self.settings.value('presentations/override app') == QtCore.Qt.CheckState.Checked:
            self.presentation_widget.show()
        else:
            self.presentation_widget.hide()

    def load_item(self, item, is_initial_load=False):
        """
        Given an item object, return a QTreeWidgetItem
        """
        tree_item = None
        file_path = Path(item.file_path)
        file_name = item.name or file_path.name
        display_name = Path(file_name).stem
        if not file_path.exists() or not os.access(file_path, os.R_OK):
            tree_item = FileTreeWidgetItem([display_name])
            tree_item.setIcon(0, UiIcons().delete)
            tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
            tree_item.setToolTip(0, str(file_path))
        else:
            controller_name = self.find_controller_by_type(file_path)
            if controller_name:
                controller = self.controllers[controller_name]
                doc = controller.add_document(file_path)
                thumbnail_path = doc.get_thumbnail_folder() / 'icon.png'
                preview_path = doc.get_thumbnail_path(1, True)
                if not preview_path and not is_initial_load:
                    preview_path = self._ensure_first_thumbnail(doc)
                doc.close_presentation()
                if not (preview_path and preview_path.exists()):
                    icon = UiIcons().delete
                else:
                    if validate_thumb(preview_path, thumbnail_path):
                        icon = build_icon(thumbnail_path)
                    else:
                        icon = create_thumb(preview_path, thumbnail_path)
            else:
                if is_initial_load:
                    icon = UiIcons().delete
                else:
                    critical_error_message_box(UiStrings().UnsupportedFile,
                                               translate('PresentationPlugin.MediaItem',
                                                         'This type of presentation is not supported.'))
                    return None
            tree_item = FileTreeWidgetItem([display_name])
            tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
            tree_item.setIcon(0, icon)
            file_type = file_path.suffix.lstrip('.').upper()
            tree_item.setToolTip(0, f'{file_type} · {size_str}')
            try:
                stat = file_path.stat()
                size_str = _format_file_size(stat.st_size)
                mtime = stat.st_mtime
                tree_item.setText(1, datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M'))
                tree_item.set_sort_data(1, mtime)
            except OSError:
                pass
        return tree_item

    def delete_item(self, item):
        """
        Remove a presentation item from the list.
        """
        file_path = Path(item.file_path)
        if file_path.exists():
            self.clean_up_thumbnails(file_path)

    def clean_up_thumbnails(self, file_path, clean_for_update=False):
        """
        Clean up the files created such as thumbnails

        :param pathlib.Path file_path: File path of the presentation to clean up after
        :param bool clean_for_update: Only clean thumbnails if update is needed
        :rtype: None
        """
        for cidx in self.controllers:
            if not self.controllers[cidx].enabled():
                # skip presentation controllers that are not enabled
                continue
            file_ext = file_path.suffix[1:]
            if file_ext in self.controllers[cidx].supports or file_ext in self.controllers[cidx].also_supports:
                doc = self.controllers[cidx].add_document(file_path)
                if clean_for_update:
                    thumb_path = doc.get_thumbnail_path(1, True)
                    if not thumb_path or not file_path.exists() or \
                            thumb_path.stat().st_mtime < file_path.stat().st_mtime:
                        doc.presentation_deleted()
                else:
                    doc.presentation_deleted()
                doc.close_presentation()

    def generate_slide_data(self, service_item, *, item=None, remote=False, context=ServiceItemContext.Service,
                            file_path=None, **kwargs):
        """
        Generate the slide data. Needs to be implemented by the plugin.

        :param service_item: The service item to be built on
        :param item: The Song item to be used
        :param remote: Triggered from remote
        :param context: Why is it being generated
        :param file_path: Path for the file to be processes
        :param kwargs: Consume other unused args specified by the base implementation, but not use by this one.
        """
        if item:
            items = [item]
        else:
            items = self.list_view.selectedItems()
            if len(items) > 1:
                return False
        items = [self.list_view.itemFromIndex(item) if isinstance(item, QtCore.QModelIndex) else item
                 for item in items]
        # If this is a folder, show an error message and return
        is_folder = (items and not isinstance(items[0], ServiceItem) and
                     isinstance(items[0].data(0, QtCore.Qt.ItemDataRole.UserRole), Folder))
        if is_folder:
            return False
        if items and not isinstance(items[0], ServiceItem):
            source_data = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
        else:
            source_data = None
        if file_path is None:
            file_path = Path(source_data.file_path)
        source_name = (source_data.name if source_data is not None else None) or file_path.name
        display_name = Path(source_name).stem
        file_type = file_path.suffix.lower()[1:]
        if not self.display_type_combo_box.currentText():
            return False
        service_item.add_capability(ItemCapabilities.CanEditTitle)
        if file_type in PDF_CONTROLLER_FILETYPES:
            service_item.add_capability(ItemCapabilities.CanMaintain)
            service_item.add_capability(ItemCapabilities.CanPreview)
            service_item.add_capability(ItemCapabilities.CanLoop)
            service_item.add_capability(ItemCapabilities.CanAppend)
            service_item.add_capability(ItemCapabilities.ProvidesOwnTheme)
            resolved_transition_settings = self._get_custom_transition_settings(service_item)
            if (not resolved_transition_settings) and items and isinstance(items[0], ServiceItem):
                resolved_transition_settings = self._get_custom_transition_settings(items[0])
            if resolved_transition_settings:
                transition_enabled = bool(resolved_transition_settings.get('enabled', False))
                transition_type = resolved_transition_settings.get('type', TransitionType.Fade)
                transition_speed = resolved_transition_settings.get('speed', TransitionSpeed.Normal)
                speed_seconds_lookup = {
                    TransitionSpeed.Fast: 0.4,
                    TransitionSpeed.Normal: 0.8,
                    TransitionSpeed.Slow: 1.2
                }
                speed_seconds = speed_seconds_lookup.get(transition_speed, 0.8)
                base_pdf_transition_settings = self._get_pdf_transition_settings()
                service_item.slide_transition_settings = {
                    'enabled': transition_enabled,
                    'type': transition_type,
                    'speed': transition_speed
                }
                service_item.pdf_transition_settings = {
                    'enabled': transition_enabled,
                    'effect': transition_type,
                    'speed': transition_speed,
                    'speed_seconds': speed_seconds,
                    'easing': base_pdf_transition_settings.get('easing', 'balanced'),
                    'type': transition_type
                }
            else:
                service_item.pdf_transition_settings = self._get_pdf_transition_settings()
                service_item.slide_transition_settings = {
                    'enabled': bool(service_item.pdf_transition_settings.get('enabled', False)),
                    'type': service_item.pdf_transition_settings.get('effect', TransitionType.Fade),
                    'speed': service_item.pdf_transition_settings.get('speed', TransitionSpeed.Normal)
                }
            # Keep name as 'presentations' so the service icon survives save/reload;
            # image-style rendering is driven by ServiceItemType.Image, not the name.
            # force a nonexistent theme
            service_item.theme = -1
            for bitem in items:
                if file_path is None:
                    file_path = Path(bitem.data(0, QtCore.Qt.ItemDataRole.UserRole).file_path)
                path = file_path.parent
                service_item.title = display_name
                if file_path.exists():
                    if not os.access(file_path, os.R_OK):
                        # File is inaccessible
                        if not remote:
                            critical_error_message_box(
                                    translate('PresentationPlugin.MediaItem', 'Missing Presentation'),
                                    translate(
                                        'PresentationPlugin.MediaItem',
                                        'The presentation {name} is inaccessible.'
                                    ).format(name=file_path)
                            )
                        return False

                    processor = self.find_controller_by_type(file_path)
                    if not processor:
                        return False
                    controller = self.controllers[processor]
                    service_item.processor = None
                    doc = controller.add_document(file_path)
                    if doc.get_thumbnail_path(1, True) is None or \
                            not (doc.get_temp_folder() / 'mainslide001.png').is_file():
                        doc.load_presentation()
                    i = 1
                    image_path = doc.get_temp_folder() / 'mainslide{number:0>3d}.png'.format(number=i)
                    thumbnail_path = doc.get_thumbnail_folder() / 'slide{number:d}.png'.format(number=i)
                    while image_path.is_file():
                        service_item.add_from_image(image_path, display_name, thumbnail=thumbnail_path)
                        # Hint the display layer to use Reveal background images so fade transitions cross-fade natively.
                        service_item.slides[-1]['use_background_image'] = True
                        service_item.slides[-1]['pdf_transition_enabled'] = bool(
                            service_item.pdf_transition_settings.get('enabled', False)
                        )
                        service_item.slides[-1]['pdf_transition_effect'] = service_item.pdf_transition_settings.get(
                            'effect', TransitionType.Fade
                        )
                        service_item.slides[-1]['pdf_transition_speed_seconds'] = \
                            service_item.pdf_transition_settings.get('speed_seconds', 0.8)
                        service_item.slides[-1]['pdf_transition_easing'] = service_item.pdf_transition_settings.get(
                            'easing', 'balanced'
                        )
                        i += 1
                        image_path = doc.get_temp_folder() / 'mainslide{number:0>3d}.png'.format(number=i)
                        thumbnail_path = doc.get_thumbnail_folder() / 'slide{number:d}.png'.format(number=i)
                    service_item.add_capability(ItemCapabilities.HasThumbnails)
                    doc.close_presentation()
                    service_item.validate_item()
                    return True
                else:
                    # File is no longer present
                    if not remote:
                        critical_error_message_box(translate('PresentationPlugin.MediaItem', 'Missing Presentation'),
                                                   translate('PresentationPlugin.MediaItem',
                                                             'The presentation {name} no longer exists.'
                                                             ).format(name=file_path))
                    return False
        else:
            service_item.processor = self.display_type_combo_box.currentText()
            service_item.add_capability(ItemCapabilities.ProvidesOwnDisplay)
            for bitem in items:
                file_path = Path(bitem.data(0, QtCore.Qt.ItemDataRole.UserRole).file_path)
                source_file_name = bitem.data(0, QtCore.Qt.ItemDataRole.UserRole).name or file_path.name
                display_file_name = Path(source_file_name).stem
                path = file_path.parent
                service_item.title = display_file_name
                if file_path.exists():
                    if os.access(file_path, os.R_OK):
                        if (self.display_type_combo_box.itemData(self.display_type_combo_box.currentIndex())
                                == 'automatic'):
                            service_item.processor = self.find_controller_by_type(file_path)
                            if not service_item.processor:
                                return False
                        controller = self.controllers[service_item.processor]
                        doc = controller.add_document(file_path)
                        thumbnail_path = self._ensure_first_thumbnail(doc)
                        i = 1
                        if thumbnail_path:
                            # Get titles and notes
                            titles, notes = doc.get_titles_and_notes()
                            service_item.add_capability(ItemCapabilities.HasDisplayTitle)
                            if notes.count('') != len(notes):
                                service_item.add_capability(ItemCapabilities.HasNotes)
                            service_item.add_capability(ItemCapabilities.HasThumbnails)
                            while thumbnail_path:
                                # Use title and note if available
                                title = ''
                                if titles and len(titles) >= i:
                                    title = titles[i - 1]
                                note = ''
                                if notes and len(notes) >= i:
                                    note = notes[i - 1]
                                service_item.add_from_command(str(path), source_file_name, thumbnail_path, title, note,
                                                              doc.get_sha256_file_hash())
                                i += 1
                                thumbnail_path = doc.get_thumbnail_path(i, True)
                            doc.close_presentation()
                            service_item.validate_item()
                            return True
                        else:
                            # File is no longer present
                            if not remote:
                                critical_error_message_box(translate('PresentationPlugin.MediaItem',
                                                                     'Missing Presentation'),
                                                           translate('PresentationPlugin.MediaItem',
                                                                     'The presentation {name} is incomplete, '
                                                                     'please reload.').format(name=file_path))
                            return False
                    else:
                        # File is inaccessible
                        if not remote:
                            critical_error_message_box(
                                    translate('PresentationPlugin.MediaItem', 'Missing Presentation'),
                                    translate(
                                        'PresentationPlugin.MediaItem',
                                        'The presentation {name} is inaccessible.'
                                    ).format(name=file_path))
                        return False
                else:
                    # File is no longer present
                    if not remote:
                        critical_error_message_box(translate('PresentationPlugin.MediaItem', 'Missing Presentation'),
                                                   translate('PresentationPlugin.MediaItem',
                                                             'The presentation {name} no longer exists.'
                                                             ).format(name=file_path))
                    return False

    def _get_pdf_transition_settings(self):
        speed_value = self.settings.value('presentations/pdf transition speed')
        speed_lookup = {
            TransitionSpeed.Fast: 0.4,
            TransitionSpeed.Normal: 0.8,
            TransitionSpeed.Slow: 1.2,
            'fast': 0.4,
            'normal': 0.8,
            'slow': 1.2
        }
        if isinstance(speed_value, bool):
            speed_seconds = 0.8
        elif speed_value in speed_lookup:
            speed_seconds = speed_lookup[speed_value]
        elif isinstance(speed_value, str) and speed_value.strip().lower() in speed_lookup:
            speed_seconds = speed_lookup[speed_value.strip().lower()]
        else:
            try:
                speed_seconds = float(speed_value)
            except (TypeError, ValueError):
                speed_seconds = 0.8
        speed_seconds = max(0.1, speed_seconds)

        effect = self._get_transition_type_value(self.settings.value('presentations/pdf transition type'))
        return {
            'enabled': bool(self.settings.value('presentations/pdf transitions')),
            'effect': effect,
            'speed_seconds': speed_seconds,
            'easing': 'balanced',
            # Backward-compatible aliases for existing consumers/tests.
            'type': effect,
            'speed': self._get_transition_speed_value(self.settings.value('presentations/pdf transition speed'))
        }

    @staticmethod
    def _ensure_first_thumbnail(doc):
        thumbnail_path = doc.get_thumbnail_path(1, True)
        if thumbnail_path:
            return thumbnail_path
        doc.load_presentation()
        thumbnail_path = doc.get_thumbnail_path(1, True)
        if thumbnail_path:
            return thumbnail_path
        # Recover from stale/incomplete cache where metadata files exist but slide thumbnails do not.
        doc.presentation_deleted()
        doc.load_presentation()
        return doc.get_thumbnail_path(1, True)

    @staticmethod
    def _get_transition_type_value(value):
        if isinstance(value, str):
            converted = TransitionType.from_string(value)
            return converted if converted is not None else TransitionType.Fade
        if value in (TransitionType.Fade, TransitionType.Slide, TransitionType.Convex,
                     TransitionType.Concave, TransitionType.Zoom):
            return value
        return TransitionType.Fade

    @staticmethod
    def _get_transition_speed_value(value):
        if isinstance(value, str):
            converted = TransitionSpeed.from_string(value)
            return converted if converted is not None else TransitionSpeed.Normal
        if value in (TransitionSpeed.Normal, TransitionSpeed.Fast, TransitionSpeed.Slow):
            return value
        return TransitionSpeed.Normal

    @classmethod
    def _is_default_transition_settings(cls, settings):
        if not isinstance(settings, dict):
            return False
        transition_type = cls._get_transition_type_value(settings.get('type', TransitionType.Fade))
        transition_speed = cls._get_transition_speed_value(settings.get('speed', TransitionSpeed.Normal))
        transition_enabled = bool(settings.get('enabled', False))
        return (not transition_enabled) and transition_type == TransitionType.Fade and \
            transition_speed == TransitionSpeed.Normal

    @classmethod
    def _normalise_transition_settings(cls, settings):
        if not isinstance(settings, dict):
            return None
        return {
            'enabled': bool(settings.get('enabled', False)),
            'type': cls._get_transition_type_value(settings.get('type', TransitionType.Fade)),
            'speed': cls._get_transition_speed_value(settings.get('speed', TransitionSpeed.Normal))
        }

    @classmethod
    def _get_custom_transition_settings(cls, service_item):
        slide_settings = cls._normalise_transition_settings(getattr(service_item, 'slide_transition_settings', None))
        if slide_settings and not cls._is_default_transition_settings(slide_settings):
            return slide_settings
        pdf_settings = getattr(service_item, 'pdf_transition_settings', None)
        if isinstance(pdf_settings, dict):
            legacy_settings = cls._normalise_transition_settings({
                'enabled': bool(pdf_settings.get('enabled', False)),
                'type': pdf_settings.get('effect', pdf_settings.get('type', TransitionType.Fade)),
                'speed': pdf_settings.get('speed', TransitionSpeed.Normal)
            })
            if legacy_settings and not cls._is_default_transition_settings(legacy_settings):
                return legacy_settings
        return None

    def find_controller_by_type(self, file_path):
        """
        Determine the default application controller to use for the selected file type. This is used if "Automatic" is
        set as the preferred controller. Find the first (alphabetic) enabled controller which "supports" the extension.
        If none found, then look for a controller which "also supports" it instead.

        :param pathlib.Path file_path: The file path
        :return: The default application controller for this file type, or None if not supported
        :rtype: PresentationController
        """
        file_type = file_path.suffix[1:]
        if not file_type:
            return None
        for controller in self.controllers:
            if self.controllers[controller].enabled():
                if file_type in self.controllers[controller].supports:
                    return controller
        for controller in self.controllers:
            if self.controllers[controller].enabled():
                if file_type in self.controllers[controller].also_supports:
                    return controller
        return None
