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
The :mod:`ui` module provides the core user interface for OpenLP
"""
from opal.core.widgets import fluent as QtWidgets
from PySide6.QtCore import Qt


class HideMode(object):
    """
    This is an enumeration class which specifies the different modes of hiding the display.

    ``Blank``
        This mode is used to hide all output, specifically by covering the display with a black screen.

    ``Theme``
        This mode is used to hide all output, but covers the display with the current theme background, as opposed to
        black.

    ``Logo``
        This mode is used to hide all output, but covers the display with the configured logo background image.

    ``Desktop``
        This mode hides all output by minimising the display, leaving the user's desktop showing.
    """
    Blank = 1
    Theme = 2
    Screen = 3
    Logo = 4


class DisplayControllerType(object):
    """
    This is an enumeration class which says where a display controller originated from.
    """
    Live = 0
    Preview = 1


class SingleColumnTableWidget(QtWidgets.QTableWidget):
    """
    Class to for a single column table widget to use for the verse table widget.
    """

    def __init__(self, parent):
        """
        Constructor
        """
        super(SingleColumnTableWidget, self).__init__(parent)
        self.horizontalHeader().setVisible(False)
        self.setColumnCount(1)
        vertical_header = self.verticalHeader()
        vertical_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        vertical_header.setStyleSheet('QHeaderView::section { padding-left: 2px; padding-right: 2px; }')
        vertical_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        # Keep verse tags readable while avoiding an oversized row header.
        target_width = int((self.fontMetrics().horizontalAdvance('W99') + 16) * 0.6)
        vertical_header.setMinimumWidth(max(20, target_width))

    def resizeEvent(self, event):
        """
        Resize the first column together with the widget.
        """
        QtWidgets.QTableWidget.resizeEvent(self, event)
        if self.columnCount():
            self.setColumnWidth(0, self.viewport().width())
            self.resizeRowsToContents()


__all__ = ['DisplayControllerType', 'HideMode', 'SingleColumnTableWidget']
