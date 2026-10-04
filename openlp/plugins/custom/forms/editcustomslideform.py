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

from PySide6 import QtCore, QtGui
from openlp.core.widgets.fluent_dialogs import TextEditorDialog
from openlp.core.widgets.slidedesigner import SlideDesignerDialogMixin, designer_dialog_parent

from .editcustomslidedialog import Ui_CustomSlideEditDialog


log = logging.getLogger(__name__)


class EditCustomSlideForm(SlideDesignerDialogMixin, TextEditorDialog, Ui_CustomSlideEditDialog):
    """
    Class documentation goes here.
    """
    log.info('Custom Verse Editor loaded')

    def __init__(self, parent=None):
        """
        Constructor
        """
        super(EditCustomSlideForm, self).__init__(designer_dialog_parent(parent),
                                                  QtCore.Qt.WindowType.WindowSystemMenuHint |
                                                  QtCore.Qt.WindowType.WindowTitleHint |
                                                  QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setup_ui(self)
        self._text_editor = self.slide_text_edit
        # Connecting signals and slots
        self.insert_button.clicked.connect(self.on_insert_button_clicked)
        self.split_button.clicked.connect(self.on_split_button_clicked)
        self.setup_slide_designer(parent, self.slide_text_edit, 'custom')

    def set_text(self, text):
        """
        Set the text for slide_text_edit.

        :param text: The text (unicode).
        """
        self.slide_text_edit.clear()
        if text:
            self.slide_text_edit.setPlainText(text)
        self.slide_text_edit.reset_undo_redo_history()
        self.slide_text_edit.moveCursor(QtGui.QTextCursor.MoveOperation.Start)
        self.slide_text_edit.verticalScrollBar().setValue(0)
        self.slide_text_edit.setFocus()

    def get_text(self):
        """
        Returns a list with all slides.
        """
        return self.slide_text_edit.toPlainText().split('\n[===]\n')

    def on_insert_button_clicked(self):
        """
        Adds a slide split at the cursor.
        """
        self.insert_single_line_text_at_cursor('[===]')
        self.slide_text_edit.setFocus()

    def on_split_button_clicked(self):
        """
        Adds an optional split at cursor.
        """
        self.insert_single_line_text_at_cursor('[---]')
        self.slide_text_edit.setFocus()

    def insert_single_line_text_at_cursor(self, text):
        """
        Adds a single line at the cursor position.

        :param text: The text to be inserted
        """
        full_text = self.slide_text_edit.toPlainText()
        position = self.slide_text_edit.textCursor().position()
        if position and full_text[position - 1] != '\n':
            text = '\n' + text
        if position == len(full_text) or full_text[position] != '\n':
            text += '\n'
        self.slide_text_edit.insertPlainText(text)
