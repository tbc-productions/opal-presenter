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
import html

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.lib.ui import critical_error_message_box, find_and_set_in_combo_box
from openlp.plugins.custom.forms.editcustomdialog import Ui_CustomEditDialog
from openlp.core.widgets.slideeditor import get_slide_editor, exec_item_editor
from openlp.plugins.custom.lib.customxmlhandler import CustomXML
from openlp.plugins.custom.lib.db import CustomSlide

log = logging.getLogger(__name__)


class EditCustomForm(QtWidgets.QDialog, Ui_CustomEditDialog):
    """
    Class documentation goes here.
    """
    log.info('Custom Editor loaded')

    def __init__(self, media_item, parent, manager):
        """
        Constructor
        """
        super(EditCustomForm, self).__init__(parent,
                                             QtCore.Qt.WindowType.WindowSystemMenuHint |
                                             QtCore.Qt.WindowType.WindowTitleHint |
                                             QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.manager = manager
        self.media_item = media_item
        self.slide_design = {}
        self.setup_ui(self)
        # Create other objects and forms.
        self.edit_slide_form = get_slide_editor(self, 'custom')
        # Connecting signals and slots
        self.preview_button.clicked.connect(self.on_preview_button_clicked)
        self.add_action.triggered.connect(self.on_add_button_clicked)
        self.edit_action.triggered.connect(self.on_edit_button_clicked)
        self.edit_all_action.triggered.connect(self.on_edit_all_button_clicked)
        self.delete_action.triggered.connect(self.on_delete_button_clicked)
        self.up_action.triggered.connect(self.on_up_button_clicked)
        self.down_action.triggered.connect(self.on_down_button_clicked)
        self.slide_list_view.currentRowChanged.connect(self.on_current_row_changed)
        self.slide_list_view.doubleClicked.connect(self.on_edit_button_clicked)
        self.theme_combo_box.activated.connect(lambda: self.slide_design.pop('theme', None))
        Registry().register_function('theme_update_list', self.load_themes)

    def exec(self):
        result = exec_item_editor(self, 'custom')
        return super().exec() if result is None else result

    def designer_footer(self):
        settings = Registry().get('settings')
        if settings.value('custom/display footer') or self.credit_edit.text():
            return html.escape(' '.join([self.title_edit.text(), self.credit_edit.text()]))
        return ''

    def load_themes(self, theme_list=None):
        """
        Load a list of themes into the themes combo box.

        :param theme_list: The list of themes to load.
        """
        if theme_list is None:
            theme_manager = Registry().get('theme_manager')
            theme_list = theme_manager.get_theme_names() if theme_manager else []
        self.theme_combo_box.clear()
        self.theme_combo_box.addItem('')
        self.theme_combo_box.addItems(theme_list)

    def load_custom(self, id, preview=False):
        """
        Called when editing or creating a new custom.

        :param id: The custom's id. If zero, then a new custom is created.
        :param preview: States whether the custom is edited while being previewed in the preview panel.
        """
        self.slide_list_view.clear()
        self.slide_design = {}
        if id == 0:
            self.custom_slide = CustomSlide()
            self.title_edit.setText('')
            self.credit_edit.setText('')
            self.theme_combo_box.setCurrentIndex(0)
        else:
            self.custom_slide = self.manager.get_object(CustomSlide, id)
            self.title_edit.setText(self.custom_slide.title)
            self.credit_edit.setText(self.custom_slide.credits)
            custom_xml = CustomXML(self.custom_slide.text)
            self.slide_design = custom_xml.get_design()
            slide_list = custom_xml.get_verses()
            self.slide_list_view.addItems([slide[1] for slide in slide_list])
            theme = self.custom_slide.theme_name
            find_and_set_in_combo_box(self.theme_combo_box, theme)
        self.title_edit.setFocus()
        # If not preview hide the preview button.
        self.preview_button.setVisible(preview)

    def accept(self):
        """
        Override the QDialog method to check if the custom slide has been saved before closing the dialog.
        """
        log.debug('accept')
        if self.save_custom():
            QtWidgets.QDialog.accept(self)

    def save_custom(self):
        """
        Saves the custom.
        """
        if not self._validate():
            return False
        sxml = CustomXML()
        for count in range(self.slide_list_view.count()):
            sxml.add_verse_to_lyrics('custom', str(count + 1), self.slide_list_view.item(count).text())
        sxml.set_design(self.slide_design)
        self.custom_slide.title = self.title_edit.text()
        self.custom_slide.text = str(sxml.extract_xml(), 'utf-8')
        self.custom_slide.credits = self.credit_edit.text()
        self.custom_slide.theme_name = self.theme_combo_box.currentText()
        success = self.manager.save_object(self.custom_slide)
        self.media_item.auto_select_id = self.custom_slide.id
        Registry().execute('custom_changed', self.custom_slide.id)
        return success

    def on_up_button_clicked(self):
        """
        Move a slide up in the list when the "Up" button is clicked.
        """
        selected_row = self.slide_list_view.currentRow()
        if selected_row != 0:
            self.remap_footer_sections({selected_row: selected_row - 1, selected_row - 1: selected_row})
            qw = self.slide_list_view.takeItem(selected_row)
            self.slide_list_view.insertItem(selected_row - 1, qw)
            self.slide_list_view.setCurrentRow(selected_row - 1)

    def on_down_button_clicked(self):
        """
        Move a slide down in the list when the "Down" button is clicked.
        """
        selected_row = self.slide_list_view.currentRow()
        # zero base arrays
        if selected_row != self.slide_list_view.count() - 1:
            self.remap_footer_sections({selected_row: selected_row + 1, selected_row + 1: selected_row})
            qw = self.slide_list_view.takeItem(selected_row)
            self.slide_list_view.insertItem(selected_row + 1, qw)
            self.slide_list_view.setCurrentRow(selected_row + 1)

    def on_add_button_clicked(self):
        """
        Add a new blank slide.
        """
        self.edit_slide_form = get_slide_editor(self, 'custom', self.edit_slide_form)
        self.edit_slide_form.designer_slide_offset = self.slide_list_view.count()
        self.edit_slide_form.set_text('')
        if self.edit_slide_form.exec():
            self.slide_list_view.addItems(self.edit_slide_form.get_text())

    def on_edit_button_clicked(self):
        """
        Edit the currently selected slide.
        """
        self.edit_slide_form = get_slide_editor(self, 'custom', self.edit_slide_form)
        self.edit_slide_form.designer_slide_offset = self.slide_list_view.currentRow()
        self.edit_slide_form.set_text(self.slide_list_view.currentItem().text())
        if self.edit_slide_form.exec():
            self.update_slide_list(self.edit_slide_form.get_text())

    def on_edit_all_button_clicked(self):
        """
        Edits all slides.
        """
        self.edit_slide_form = get_slide_editor(self, 'custom', self.edit_slide_form)
        slide_text = ''
        for row in range(self.slide_list_view.count()):
            item = self.slide_list_view.item(row)
            slide_text += item.text()
            if row != self.slide_list_view.count() - 1:
                slide_text += '\n[===]\n'
        self.edit_slide_form.designer_slide_offset = 0
        self.edit_slide_form.set_text(slide_text)
        if self.edit_slide_form.exec():
            self.update_slide_list(self.edit_slide_form.get_text(), True)

    def on_preview_button_clicked(self):
        """
        Save the custom item and preview it.
        """
        log.debug('onPreview')
        if self.save_custom():
            Registry().execute('custom_preview')
            return True
        return False

    def update_slide_list(self, slides, edit_all=False):
        """
        Updates the slide list after editing slides.

        :param slides: A list of all slides which have been edited.
        :param edit_all:  Indicates if all slides or only one slide has been edited.
        """
        if not getattr(self.edit_slide_form, 'uses_slide_designer', False):
            from openlp.core.lib.slidedesign import remap_custom_footers
            before = ([self.slide_list_view.item(row).text() for row in range(self.slide_list_view.count())]
                      if edit_all else [self.slide_list_view.currentItem().text()])
            self.slide_design = remap_custom_footers(
                self.slide_design, before, slides, 0 if edit_all else self.slide_list_view.currentRow())
        if edit_all:
            self.slide_list_view.clear()
            self.slide_list_view.addItems(slides)
        else:
            old_row = self.slide_list_view.currentRow()
            # Create a list with all (old/unedited) slides.
            old_slides = [self.slide_list_view.item(row).text() for row in range(self.slide_list_view.count())]
            self.slide_list_view.clear()
            old_slides.pop(old_row)
            # Insert all slides to make the old_slides list complete.
            for slide in slides:
                old_slides.insert(old_row, slide)
                old_row += 1
            self.slide_list_view.addItems(old_slides)
        self.slide_list_view.repaint()

    def on_delete_button_clicked(self):
        """
        Removes the current row from the list.
        """
        row = self.slide_list_view.currentRow()
        self.remap_footer_sections({i: (None if i == row else i - 1)
                                    for i in range(row, self.slide_list_view.count())})
        self.slide_list_view.takeItem(row)
        self.on_current_row_changed(self.slide_list_view.currentRow())

    def remap_footer_sections(self, mapping):
        def remap(key):
            section, split, page = key.split(':')
            if section.startswith('custom-'):
                index = int(section[7:]) - 1
                destination = mapping.get(index, index)
                if destination is None:
                    return None
                section = f'custom-{destination + 1}'
            return f'{section}:{split}:{page}'
        if 'hidden_footers' in self.slide_design:
            self.slide_design['hidden_footers'] = [target for key in self.slide_design['hidden_footers']
                                                   if (target := remap(key)) is not None]
        for collection in ('assignments', 'overrides'):
            if collection in self.slide_design:
                self.slide_design[collection] = {target: value for key, value in self.slide_design[collection].items()
                                                 if (target := remap(key)) is not None}

    def on_current_row_changed(self, row):
        """
        Called when the *slide_list_view*'s current row has been changed. This
        enables or disables buttons which require an slide to act on.

        :param row: The row (int). If there is no current row, the value is -1.
        """
        if row == -1:
            self.delete_action.setEnabled(False)
            self.edit_action.setEnabled(False)
            self.up_action.setEnabled(False)
            self.down_action.setEnabled(False)
        else:
            self.delete_action.setEnabled(True)
            self.edit_action.setEnabled(True)
            # Decide if the up/down buttons should be enabled or not.
            self.down_action.setEnabled(self.slide_list_view.count() - 1 != row)
            self.up_action.setEnabled(row != 0)

    def _validate(self):
        """
        Checks whether a custom is valid or not.
        """
        # We must have a title.
        if not self.title_edit.displayText():
            self.title_edit.setFocus()
            critical_error_message_box(
                parent=self,
                message=translate('CustomPlugin.EditCustomForm', 'You need to type in a title.'))
            return False
        # We must have at least one slide.
        if self.slide_list_view.count() == 0:
            critical_error_message_box(
                parent=self,
                message=translate('CustomPlugin.EditCustomForm',
                                  'You need to add at least one slide.'))
            return False
        return True
