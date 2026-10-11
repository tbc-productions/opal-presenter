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

import re

from PySide6 import QtCore, QtGui
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.i18n import UiStrings
from opal.core.lib.ui import create_button_box
from opal.core.ui.icons import UiIcons
from opal.core.widgets.edits import SpellTextEdit
from opal.plugins.songs.lib import VerseType


PLAIN_VERSE_LINE_REGEX = re.compile(
    r'^[ \t]*(Verse|Chorus|Bridge|Pre[- ]?Chorus|Intro|Ending)(?:[ \t]*(\d+))?[ \t]*:?[ \t]*$', re.IGNORECASE)
SECTION_MARKER_REGEX = re.compile(r'---\[[^\n]+\]---')


class SongLyricsTextEdit(SpellTextEdit):
    """Convert section headings when lyrics are pasted into the bulk editor."""

    def __init__(self, parent):
        super().__init__(parent, visual_mode_only=True)
        self.parse_section_labels = False

    def insertFromMimeData(self, source):
        if not self.rich_text_mode or not self.parse_section_labels or not source.hasText():
            return super().insertFromMimeData(source)

        lines = []
        found_heading = False
        for line in source.text().replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            match = PLAIN_VERSE_LINE_REGEX.fullmatch(line)
            if match:
                found_heading = True
                verse_name = match.group(1).replace(' ', '-').lower()
                verse_type = (VerseType.PreChorus if verse_name == 'prechorus' else
                              VerseType.from_string(verse_name))
                lines.append('---[{tag}:{number}]---'.format(
                    tag=VerseType.names[verse_type], number=match.group(2) or '1'))
            else:
                lines.append(line)
        if not found_heading:
            return super().insertFromMimeData(source)

        pasted_text = '\n'.join(lines)
        # Replace the empty starter marker when a pasted song starts with a heading.
        if (SECTION_MARKER_REGEX.fullmatch(self.toPlainText().strip()) and
                pasted_text.lstrip('\n').startswith('---[')):
            cursor = self.textCursor()
            cursor.select(QtGui.QTextCursor.SelectionType.Document)
            self.setTextCursor(cursor)
            pasted_text = pasted_text.lstrip('\n')
        converted_source = QtCore.QMimeData()
        converted_source.setText(pasted_text)
        super().insertFromMimeData(converted_source)


class Ui_EditVerseDialog(object):
    def setup_ui(self, edit_verse_dialog):
        edit_verse_dialog.setObjectName('edit_verse_dialog')
        edit_verse_dialog.setWindowIcon(UiIcons().main_icon)
        edit_verse_dialog.resize(1000, 680)
        edit_verse_dialog.setSizeGripEnabled(True)
        edit_verse_dialog.setModal(True)
        self.dialog_layout = QtWidgets.QVBoxLayout(edit_verse_dialog)
        self.dialog_layout.setObjectName('dialog_layout')
        self.verse_text_edit = SongLyricsTextEdit(edit_verse_dialog)
        self.verse_text_edit.setObjectName('verse_text_edit')
        self.dialog_layout.addWidget(self.verse_text_edit)
        self.verse_type_layout = QtWidgets.QHBoxLayout()
        self.verse_type_layout.setObjectName('verse_type_layout')
        self.forced_split_button = QtWidgets.QPushButton(edit_verse_dialog)
        self.forced_split_button.setIcon(UiIcons().add)
        self.forced_split_button.setObjectName('forced_split_button')
        self.verse_type_layout.addWidget(self.forced_split_button)
        self.overflow_split_button = QtWidgets.QPushButton(edit_verse_dialog)
        self.overflow_split_button.setIcon(UiIcons().add_starburst)
        self.overflow_split_button.setObjectName('overflow_split_button')
        self.verse_type_layout.addWidget(self.overflow_split_button)
        self.verse_type_layout.addSpacing(20)
        self.verse_type_layout.addStretch(1)
        self.verse_type_label = QtWidgets.QLabel(edit_verse_dialog)
        self.verse_type_label.setObjectName('verse_type_label')
        self.verse_type_layout.addWidget(self.verse_type_label)
        self.verse_type_combo_box = QtWidgets.QComboBox(edit_verse_dialog)
        self.verse_type_combo_box.addItems(['', '', '', '', '', '', ''])
        self.verse_type_combo_box.setObjectName('verse_type_combo_box')
        self.verse_type_label.setBuddy(self.verse_type_combo_box)
        self.verse_type_layout.addWidget(self.verse_type_combo_box)
        self.verse_number_box = QtWidgets.QSpinBox(edit_verse_dialog)
        self.verse_number_box.setMinimum(1)
        self.verse_number_box.setCompactWidth(2)
        self.verse_number_box.setObjectName('verse_number_box')
        self.verse_type_layout.addWidget(self.verse_number_box)
        self.insert_button = QtWidgets.QPushButton(edit_verse_dialog)
        self.insert_button.setIcon(UiIcons().add)
        self.insert_button.setObjectName('insert_button')
        self.verse_type_layout.addWidget(self.insert_button)
        self.dialog_layout.addLayout(self.verse_type_layout)
        self.transpose_widget = QtWidgets.QWidget()
        self.transpose_layout = QtWidgets.QHBoxLayout(self.transpose_widget)
        self.transpose_layout.setObjectName('transpose_layout')
        self.transpose_label = QtWidgets.QLabel(edit_verse_dialog)
        self.transpose_label.setObjectName('transpose_label')
        self.transpose_layout.addWidget(self.transpose_label)
        self.transpose_up_button = QtWidgets.QPushButton(edit_verse_dialog)
        self.transpose_up_button.setIcon(UiIcons().arrow_up)
        self.transpose_up_button.setObjectName('transpose_up')
        self.transpose_layout.addWidget(self.transpose_up_button)
        self.transpose_down_button = QtWidgets.QPushButton(edit_verse_dialog)
        self.transpose_down_button.setIcon(UiIcons().arrow_down)
        self.transpose_down_button.setObjectName('transpose_down')
        self.transpose_layout.addWidget(self.transpose_down_button)
        self.dialog_layout.addWidget(self.transpose_widget)
        self.button_box = create_button_box(edit_verse_dialog, 'button_box', ['cancel', 'ok'])
        self.dialog_layout.addWidget(self.button_box)
        self.retranslate_ui(edit_verse_dialog)

    def retranslate_ui(self, edit_verse_dialog):
        VerseType.translated_names = [
            UiStrings().Verse,
            UiStrings().Chorus,
            UiStrings().Bridge,
            UiStrings().PreChorus,
            UiStrings().Intro,
            UiStrings().Ending,
            UiStrings().Other
        ]
        VerseType.translated_tags = [name[0].lower() for name in VerseType.translated_names]
        edit_verse_dialog.setWindowTitle(UiStrings().EditVerse)
        self.verse_type_label.setText(UiStrings().VerseType)
        self.verse_type_combo_box.setItemText(VerseType.Verse, VerseType.translated_names[VerseType.Verse])
        self.verse_type_combo_box.setItemText(VerseType.Chorus, VerseType.translated_names[VerseType.Chorus])
        self.verse_type_combo_box.setItemText(VerseType.Bridge, VerseType.translated_names[VerseType.Bridge])
        self.verse_type_combo_box.setItemText(VerseType.PreChorus, VerseType.translated_names[VerseType.PreChorus])
        self.verse_type_combo_box.setItemText(VerseType.Intro, VerseType.translated_names[VerseType.Intro])
        self.verse_type_combo_box.setItemText(VerseType.Ending, VerseType.translated_names[VerseType.Ending])
        self.verse_type_combo_box.setItemText(VerseType.Other, VerseType.translated_names[VerseType.Other])
        self.overflow_split_button.setText(UiStrings().Split)
        self.overflow_split_button.setToolTip(UiStrings().SplitToolTip)
        self.forced_split_button.setText(UiStrings().ForcedSplit)
        self.forced_split_button.setToolTip(UiStrings().ForcedSplitToolTip)
        self.insert_button.setText(UiStrings().Insert)
        self.insert_button.setToolTip(UiStrings().InsertToolTip)
        self.transpose_label.setText(UiStrings().Transpose)
        self.transpose_up_button.setText(UiStrings().Up)
        self.transpose_down_button.setText(UiStrings().Down)
