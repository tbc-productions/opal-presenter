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

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.plugins.songusage.forms.songusagedeletedialog import Ui_SongUsageDeleteDialog
from openlp.plugins.songusage.lib.db import SongUsageItem


class SongUsageDeleteForm(QtWidgets.FormDialog, Ui_SongUsageDeleteDialog, RegistryProperties):
    """
    Class documentation goes here.
    """
    def __init__(self, manager, parent):
        """
        Constructor
        """
        self.manager = manager
        super(SongUsageDeleteForm, self).__init__(parent,
                                                  QtCore.Qt.WindowType.WindowSystemMenuHint |
                                                  QtCore.Qt.WindowType.WindowTitleHint |
                                                  QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setup_ui(self)

    def accept(self):
        """Keep the date selection open until deletion is explicitly confirmed."""
        delete_date = self.delete_calendar.selectedDate().toPyDate()
        dialog = QtWidgets.ContentDialog(self)
        dialog.setTitle(translate('SongUsagePlugin.SongUsageDeleteForm', 'Delete Song Usage Data?'))
        date_text = self.delete_calendar.selectedDate().toString(QtCore.Qt.DateFormat.ISODate)
        message = translate('SongUsagePlugin.SongUsageDeleteForm',
                            'Permanently delete all song usage data on or before {date}?').format(date=date_text)
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        dialog.setContent(label)
        dialog.setPrimaryButtonText(translate('OpenLP.Ui', 'Delete'))
        dialog.setCloseButtonText(translate('OpenLP.Ui', 'Cancel'))
        dialog.setDefaultButton(QtWidgets.fluentqt.ContentDialogButton.Close)
        try:
            confirmed = dialog.exec() == dialog.ResultPrimary
        finally:
            dialog.deleteLater()
        if not confirmed:
            return
        self.manager.delete_all_objects(SongUsageItem, SongUsageItem.usagedate <= delete_date)
        self.main_window.information_message(
            translate('SongUsagePlugin.SongUsageDeleteForm', 'Deletion Successful'),
            translate('SongUsagePlugin.SongUsageDeleteForm', 'All requested data has been deleted successfully.'))
        super().accept()
