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

from PySide6 import QtGui
from opal.core.widgets import fluent as QtWidgets

from opal.core.ui.icons import UiIcons
from opal.core.common.i18n import translate


class Ui_ConfirmationDialog():
    """
    The UI for the Confirmation dialog.
    """

    def setup_ui(self, confirmation_dialog, title, items, message, width=400, height=None):
        """
        Set up the UI for the confirmation dialog.

        :param confirmation_dialog: The QDialog object to set up.
        :param items:               A list (or other iterable) containing the items
        :param message:             The confirmation message to display
        :param width:               Width of the dialog window
        :param height:              Height of the dialog window (None to auto-size to contents)

        :return:                    None
        """
        # overall aspects for confirmation dialog
        confirmation_dialog.setObjectName('confirmation_dialog')
        confirmation_dialog.setWindowIcon(UiIcons().main_icon)
        if height is not None:
            confirmation_dialog.resize(width, height)
        else:
            confirmation_dialog.resize(width, 200)
        confirmation_dialog.setWindowTitle(title)

        self.confirmation_layout = QtWidgets.QVBoxLayout(confirmation_dialog.content_widget)
        self.confirmation_layout.setObjectName('confirmation_layout')

        # confirmation message
        self.message_label = QtWidgets.QLabel(message)
        self.message_label.setObjectName('message')
        self.message_label.setWordWrap(True)
        self.message_label.setFluentTypography(QtWidgets.fluentqt.FontRole.Body)
        self.confirmation_layout.addWidget(self.message_label)

        # listview to display the items
        self.listview = QtWidgets.QListView(confirmation_dialog)
        self.listview.setObjectName("confirmation listview")
        # make the entries read-only
        self.listview.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.confirmation_layout.addWidget(self.listview)

        # add the items to the listview model
        model = QtGui.QStandardItemModel()
        self.listview.setModel(model)
        for item in items:
            model.appendRow(QtGui.QStandardItem(item))
        row_count = model.rowCount()
        row_height = self.listview.sizeHintForRow(0)
        if row_height <= 0:
            row_height = self.listview.fontMetrics().height() + 8
        visible_rows = max(row_count, 1)
        frame_height = self.listview.frameWidth() * 2
        list_height = (row_height * visible_rows) + frame_height + 4
        self.listview.setMinimumHeight(list_height)
        self.listview.setMaximumHeight(list_height)

        # Yes/No buttons
        button_types = QtWidgets.QDialogButtonBox.StandardButton.Yes | QtWidgets.QDialogButtonBox.StandardButton.No
        self.buttonBox = QtWidgets.QDialogButtonBox(button_types)
        self.buttonBox.setObjectName('buttons')
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Yes).setText(
            translate('OpenLP.ConfirmationDialog', 'Delete'))
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.No).setText(
            translate('OpenLP.Ui', 'Cancel'))
        self.confirmation_layout.addWidget(self.buttonBox)

        # slot connections
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        confirmation_dialog.setButtonBox(self.buttonBox)
        confirmation_dialog.setDefaultButton(QtWidgets.fluentqt.ContentDialogButton.Close)

        # Avoid adjustSize() here as it can crash in some Qt/PySide test environments.
        # Activate the layout so child geometry is computed for tests and callers.
        self.confirmation_layout.activate()
