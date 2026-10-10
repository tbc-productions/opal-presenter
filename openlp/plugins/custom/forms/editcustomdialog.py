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
from PySide6 import QtCore, QtGui
import fluentqt
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import UiStrings, translate
from openlp.core.lib.ui import create_button_box
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.style import use_alternate_rows
from openlp.core.widgets.edits import FormattingTagDelegate


class CustomSlideListWidget(QtWidgets.QListWidget):
    """One numbered, fully selectable row per custom slide, including optional splits."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setItemDelegate(FormattingTagDelegate(self))
        header = self.verticalHeader()
        header.show()
        header.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignHCenter)
        header.setMinimumWidth(32)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for signal in (self.model().rowsInserted, self.model().rowsRemoved, self.model().dataChanged,
                       self.model().modelReset):
            signal.connect(self._resize_slide_rows)

    def _resize_slide_rows(self, *args):
        self.resizeRowsToContents()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resizeRowsToContents()


class Ui_CustomEditDialog(object):
    def setup_ui(self, custom_edit_dialog):
        """
        Build the Edit Dialog UI
        :param custom_edit_dialog: The Dialog
        """
        custom_edit_dialog.setObjectName('custom_edit_dialog')
        custom_edit_dialog.setWindowIcon(UiIcons().main_icon)
        custom_edit_dialog.resize(900, 600)
        self.dialog_layout = QtWidgets.QVBoxLayout(custom_edit_dialog)
        self.dialog_layout.setObjectName('dialog_layout')
        self.title_layout = QtWidgets.QHBoxLayout()
        self.title_layout.setObjectName('title_layout')
        self.title_label = QtWidgets.QLabel(custom_edit_dialog)
        self.title_label.setObjectName('title_label')
        self.title_layout.addWidget(self.title_label)
        self.title_edit = QtWidgets.QLineEdit(custom_edit_dialog)
        self.title_label.setBuddy(self.title_edit)
        self.title_edit.setObjectName('title_edit')
        self.title_layout.addWidget(self.title_edit)
        self.dialog_layout.addLayout(self.title_layout)
        self.slide_command_bar = fluentqt.CommandBar(custom_edit_dialog)
        self.slide_command_bar.setObjectName('slide_command_bar')
        self.slide_command_bar.setLabelPosition(fluentqt.CommandBar.LabelPosition.Right)
        self.slide_command_bar.setBackgroundVisible(True)
        self.slide_command_bar.setDynamicOverflowEnabled(True)
        for name, icon, caption in (('add_action', UiIcons().add, UiStrings().Add),
                                    ('edit_action', UiIcons().edit, UiStrings().Edit),
                                    ('edit_all_action', UiIcons().edit,
                                     translate('CustomPlugin.EditCustomForm', 'Ed&it All')),
                                    ('delete_action', UiIcons().delete, UiStrings().Delete),
                                    ('up_action', UiIcons().arrow_up, UiStrings().Up),
                                    ('down_action', UiIcons().arrow_down, UiStrings().Down)):
            action = QtGui.QAction(icon, caption, self.slide_command_bar)
            action.setObjectName(name)
            setattr(self, name, action)
            self.slide_command_bar.addPrimaryAction(action)
        for action in (self.edit_action, self.delete_action, self.up_action, self.down_action):
            action.setEnabled(False)
        self.dialog_layout.addWidget(self.slide_command_bar)
        self.slide_list_view = CustomSlideListWidget(custom_edit_dialog)
        self.slide_list_view.setAlternatingRowColors(use_alternate_rows())
        self.slide_list_view.setObjectName('slide_list_view')
        self.dialog_layout.addWidget(self.slide_list_view, 1)
        self.bottom_form_layout = QtWidgets.QFormLayout()
        self.bottom_form_layout.setObjectName('bottom_form_layout')
        self.theme_label = QtWidgets.QLabel(custom_edit_dialog)
        self.theme_label.setObjectName('theme_label')
        self.theme_combo_box = QtWidgets.QComboBox(custom_edit_dialog)
        self.theme_combo_box.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.theme_combo_box.setObjectName('theme_combo_box')
        self.theme_label.setBuddy(self.theme_combo_box)
        self.bottom_form_layout.addRow(self.theme_label, self.theme_combo_box)
        self.credit_label = QtWidgets.QLabel(custom_edit_dialog)
        self.credit_label.setObjectName('credit_label')
        self.credit_edit = QtWidgets.QLineEdit(custom_edit_dialog)
        self.credit_edit.setObjectName('credit_edit')
        self.credit_label.setBuddy(self.credit_edit)
        self.bottom_form_layout.addRow(self.credit_label, self.credit_edit)
        self.dialog_layout.addLayout(self.bottom_form_layout)
        self.preview_button = QtWidgets.QPushButton()
        self.button_box = create_button_box(custom_edit_dialog, 'button_box', ['cancel', 'save'],
                                            [self.preview_button])
        self.save_button = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        self.dialog_layout.addWidget(self.button_box)
        self.retranslate_ui(custom_edit_dialog)

    def retranslate_ui(self, custom_edit_dialog):
        custom_edit_dialog.setWindowTitle(translate('CustomPlugin.EditCustomForm', 'Edit Custom Slides'))
        self.title_label.setText(translate('CustomPlugin.EditCustomForm', '&Title'))
        self.add_action.setText(UiStrings().Add)
        self.add_action.setToolTip(translate('CustomPlugin.EditCustomForm', 'Add a new slide at bottom.'))
        self.edit_action.setText(UiStrings().Edit)
        self.edit_action.setToolTip(translate('CustomPlugin.EditCustomForm', 'Edit the selected slide.'))
        self.edit_all_action.setText(translate('CustomPlugin.EditCustomForm', 'Ed&it All'))
        self.edit_all_action.setToolTip(translate('CustomPlugin.EditCustomForm', 'Edit all the slides at once.'))
        self.delete_action.setText(UiStrings().Delete)
        self.delete_action.setToolTip(translate('OpenLP.Ui', 'Delete the selected item.'))
        self.up_action.setText(UiStrings().Up)
        self.up_action.setToolTip(translate('OpenLP.Ui', 'Move selection up one position.'))
        self.down_action.setText(UiStrings().Down)
        self.down_action.setToolTip(translate('OpenLP.Ui', 'Move selection down one position.'))
        self.theme_label.setText(translate('CustomPlugin.EditCustomForm', 'The&me'))
        self.credit_label.setText(translate('CustomPlugin.EditCustomForm', '&Credits'))
        self.preview_button.setText(UiStrings().SaveAndPreview)
        self.save_button.setText(UiStrings().SaveAndClose)
