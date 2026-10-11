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
The list of shortcuts within a dialog.
"""
from PySide6 import QtGui
from fluentqt import CommandBar, FontRole
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.lib.ui import create_button_box
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.style import use_alternate_rows


class CaptureShortcutButton(QtWidgets.QPushButton):
    """Show the current keys or an explicit prompt while capturing a shortcut."""
    def __init__(self, *args):
        super().__init__(*args)
        self._shortcut_text = ''
        self.setCheckable(True)
        self.toggled.connect(self._refresh_caption)
        self._refresh_caption()

    def setText(self, text):
        self._shortcut_text = text
        self._refresh_caption()

    def shortcutText(self):
        return self._shortcut_text

    def _refresh_caption(self):
        caption = (translate('OpenLP.ShortcutListDialog', 'Press shortcut…') if self.isChecked()
                   else self._shortcut_text or translate('OpenLP.ShortcutListDialog', 'Set shortcut'))
        super().setText(caption)
        self.setIcon(UiIcons().get_icon_variant('keyboard', color='white') if self.isChecked() else UiIcons().keyboard)

    def keyPressEvent(self, event):
        # Bubble captured keys to the window, including Space and Return.
        if self.isChecked():
            event.ignore()
        else:
            super().keyPressEvent(event)


class ShortcutDataGrid(QtWidgets.QTableWidget):
    def keyboardSearch(self, search):
        """Single letters are available as shortcuts rather than type-to-select."""
        pass


class Ui_ShortcutListDialog:
    """Searchable action browser beside clearly labelled shortcut controls."""
    def setup_ui(self, window):
        window.setObjectName('shortcutListDialog')
        window.setWindowIcon(UiIcons().main_icon)
        window.setMinimumSize(900, 600)
        self.window_title_label = QtWidgets.QLabel()
        self.window_title_label.setContentsMargins(12, 0, 12, 0)
        self.window_title_label.setFluentTypography(FontRole.BodyStrong)
        window.titleBar().setContentWidget(self.window_title_label)
        self.content_widget = QtWidgets.QWidget()
        window.setContentWidget(self.content_widget)
        self.shortcut_list_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.shortcut_list_layout.setContentsMargins(24, 20, 24, 20)
        self.shortcut_list_layout.setSpacing(16)
        self.content_splitter = QtWidgets.QSplitter()
        self.content_splitter.setChildrenCollapsible(False)
        self.shortcut_list_layout.addWidget(self.content_splitter, 1)

        browser = QtWidgets.QWidget()
        self.content_splitter.addWidget(browser)
        browser.setMinimumWidth(460)
        browser_layout = QtWidgets.QVBoxLayout(browser)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(12)
        self.search_edit = QtWidgets.QLineEdit(browser)
        self.search_edit.setClearButtonEnabled(True)
        browser_layout.addWidget(self.search_edit)
        self.list_command_bar = self._command_bar(browser)
        self.restore_all_action = QtGui.QAction(
            UiIcons().undo, translate('OpenLP.ShortcutListDialog', 'Restore all defaults'), self.list_command_bar)
        self.list_command_bar.addPrimaryAction(self.restore_all_action)
        self.shortcut_grid = ShortcutDataGrid(browser)
        self.shortcut_grid.setObjectName('shortcut_grid')
        self.shortcut_grid.setAlternatingRowColors(use_alternate_rows())
        self.shortcut_grid.setColumnCount(4)
        self.shortcut_grid.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.shortcut_grid.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.shortcut_grid.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.shortcut_grid.verticalHeader().hide()
        self.shortcut_grid.setCornerButtonEnabled(False)
        self.shortcut_grid.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.shortcut_grid.setColumnWidth(column, 100)
        browser_layout.addWidget(self.shortcut_grid, 1)
        browser_layout.addWidget(self.list_command_bar)

        self.editor_card = QtWidgets.Card()
        self.editor_card.setMinimumWidth(330)
        self.content_splitter.addWidget(self.editor_card)
        editor_layout = QtWidgets.QVBoxLayout(self.editor_card)
        editor_layout.setContentsMargins(20, 16, 20, 16)
        editor_layout.setSpacing(16)
        self.action_label = QtWidgets.QLabel(self.editor_card)
        self.action_label.setFluentTypography(FontRole.Subtitle)
        self.action_label.setWordWrap(True)
        editor_layout.addWidget(self.action_label)
        self.editor_controls = QtWidgets.QWidget(self.editor_card)
        editor_layout.addWidget(self.editor_controls)
        controls_layout = QtWidgets.QVBoxLayout(self.editor_controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(16)
        self.primary_label = QtWidgets.QLabel(self.editor_controls)
        self.alternate_label = QtWidgets.QLabel(self.editor_controls)
        self.primary_push_button = CaptureShortcutButton(self.editor_controls)
        self.alternate_push_button = CaptureShortcutButton(self.editor_controls)
        self.clear_primary_button = QtWidgets.QPushButton(self.editor_controls)
        self.clear_alternate_button = QtWidgets.QPushButton(self.editor_controls)
        for label, capture, clear in ((self.primary_label, self.primary_push_button, self.clear_primary_button),
                                      (self.alternate_label, self.alternate_push_button, self.clear_alternate_button)):
            label.setFluentTypography(FontRole.BodyStrong)
            label.setBuddy(capture)
            controls_layout.addWidget(label)
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(8)
            capture.setIcon(UiIcons().keyboard)
            capture.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            clear.setIcon(UiIcons().delete)
            row.addWidget(capture, 1)
            row.addWidget(clear)
            controls_layout.addLayout(row)
        self.editor_command_bar = self._command_bar(self.editor_controls)
        self.restore_action = QtGui.QAction(
            UiIcons().undo, translate('OpenLP.ShortcutListDialog', 'Restore defaults'), self.editor_command_bar)
        self.editor_command_bar.addPrimaryAction(self.restore_action)
        controls_layout.addWidget(self.editor_command_bar)
        editor_layout.addStretch()
        self.content_splitter.setSizes([650, 380])

        self.button_box = create_button_box(window, 'button_box', ['cancel', 'save'])
        self.save_button = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        self.save_button.setIcon(UiIcons().get_icon_variant('save', color='white'))
        self.save_button.setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Accent)
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.button_box)
        self.shortcut_list_layout.addLayout(footer)
        self.retranslate_ui(window)
        window.resize(1100, 760)

    def _command_bar(self, parent):
        bar = CommandBar(parent)
        bar.setLabelPosition(CommandBar.LabelPosition.Right)
        bar.setBackgroundVisible(True)
        bar.setDynamicOverflowEnabled(True)
        bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        return bar

    def retranslate_ui(self, window):
        window.setWindowTitle(translate('OpenLP.ShortcutListDialog', 'Shortcuts'))
        self.window_title_label.setText(window.windowTitle())
        self.search_edit.setPlaceholderText(translate('OpenLP.ShortcutListDialog', 'Search actions or shortcuts'))
        self.search_edit.setAccessibleName(translate('OpenLP.ShortcutListDialog', 'Search shortcuts'))
        self.shortcut_grid.setHorizontalHeaderLabels([
            translate('OpenLP.ShortcutListDialog', 'Action'),
            translate('OpenLP.ShortcutListDialog', 'Primary'),
            translate('OpenLP.ShortcutListDialog', 'Alternate'),
            translate('OpenLP.ShortcutListDialog', 'Category')])
        self.primary_label.setText(translate('OpenLP.ShortcutListDialog', 'Primary'))
        self.alternate_label.setText(translate('OpenLP.ShortcutListDialog', 'Alternate'))
        self.primary_push_button.setAccessibleName(translate('OpenLP.ShortcutListDialog', 'Primary shortcut'))
        self.alternate_push_button.setAccessibleName(translate('OpenLP.ShortcutListDialog', 'Alternate shortcut'))
        for capture in (self.primary_push_button, self.alternate_push_button):
            capture.setToolTip(translate(
                'OpenLP.ShortcutListDialog', 'Click, then press the shortcut. Click again to cancel.'))
        self.clear_primary_button.setText(translate('OpenLP.ShortcutListDialog', 'Clear'))
        self.clear_primary_button.setToolTip(translate('OpenLP.ShortcutListDialog', 'Remove the primary shortcut'))
        self.clear_alternate_button.setText(translate('OpenLP.ShortcutListDialog', 'Clear'))
        self.clear_alternate_button.setToolTip(translate('OpenLP.ShortcutListDialog', 'Remove the alternate shortcut'))
        self.restore_action.setText(translate('OpenLP.ShortcutListDialog', 'Restore defaults'))
        self.restore_all_action.setText(translate('OpenLP.ShortcutListDialog', 'Restore all defaults'))
        self.save_button.setText(translate('OpenLP.ShortcutListDialog', 'Save changes'))
