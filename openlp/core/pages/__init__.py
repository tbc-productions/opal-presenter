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
The :mod:`~openlp.core.pages` module contains wizard pages used in OpenLP
"""
from PySide6 import QtCore, QtWidgets


class GridLayoutPage(QtWidgets.QWizardPage):
    """
    A class that has a QGridLayout for its layout which automatically ensure all columns are equal width
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._column_width = 0
        self.layout = QtWidgets.QGridLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setup_ui()
        self.retranslate_ui()
        self.resize_columns()

    def resizeEvent(self, event):
        """
        Override inherited resize method
        """
        super().resizeEvent(event)
        self.resize_columns()

    def resize_columns(self):
        """
        Keep all columns at equal relative width.

        Using dynamic minimum widths here causes parent dialogs to grow over time
        when pages are hosted in resizable containers (for example, a QStackedWidget
        inside a QDialog). Stretch factors provide equal-width columns without
        feeding a minimum-size growth loop back into the parent layout.
        """
        column_count = self.layout.columnCount()
        if column_count <= 0:
            return
        self._column_width = self.layout.contentsRect().width() // column_count
        for column_number in range(column_count):
            self.layout.setColumnStretch(column_number, 1)

    def setup_ui(self):
        raise NotImplementedError('Descendant pages need to implement setup_ui')

    def retranslate_ui(self):
        raise NotImplementedError('Descendant pages need to implement retranslate_ui')
