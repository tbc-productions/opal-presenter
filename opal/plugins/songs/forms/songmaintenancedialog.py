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
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.i18n import UiStrings
from opal.core.lib.ui import create_button_box
from opal.core.ui.icons import UiIcons
from opal.plugins.songs.lib.ui import SongStrings


class Ui_SongMaintenanceDialog(object):
    """
    The user interface for the song maintenance dialog
    """
    def setup_ui(self, song_maintenance_dialog):
        """
        Set up the user interface for the song maintenance dialog
        """
        song_maintenance_dialog.setObjectName('song_maintenance_dialog')
        song_maintenance_dialog.setWindowIcon(UiIcons().main_icon)
        song_maintenance_dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        song_maintenance_dialog.resize(760, 600)
        self.dialog_layout = QtWidgets.QGridLayout(song_maintenance_dialog)
        self.dialog_layout.setObjectName('dialog_layout')
        self.type_list_widget = QtWidgets.QListWidget(song_maintenance_dialog)
        self.type_list_widget.setIconSize(QtCore.QSize(32, 32))
        self.type_list_widget.setUniformItemSizes(True)
        self.type_list_widget.setObjectName('type_list_widget')
        self.authors_list_item = QtWidgets.QListWidgetItem(self.type_list_widget)
        self.authors_list_item.setIcon(UiIcons().usermo)
        self.topics_list_item = QtWidgets.QListWidgetItem(self.type_list_widget)
        self.topics_list_item.setIcon(UiIcons().light_bulb)
        self.books_list_item = QtWidgets.QListWidgetItem(self.type_list_widget)
        self.books_list_item.setIcon(UiIcons().book)
        self.dialog_layout.addWidget(self.type_list_widget, 0, 0)
        self.stacked_layout = QtWidgets.QStackedLayout()
        self.stacked_layout.setObjectName('stacked_layout')
        # Each section has a command bar above its list, flush with the navigation.
        for section, item, list_name in (('authors', 'author', 'authors_list_widget'),
                                         ('topics', 'topic', 'topics_list_widget'),
                                         ('books', 'book', 'song_books_list_widget')):
            page = QtWidgets.QWidget(song_maintenance_dialog)
            page.setObjectName(f'{section}_page')
            setattr(self, f'{section}_page', page)
            layout = QtWidgets.QVBoxLayout(page)
            layout.setObjectName(f'{section}_layout')
            layout.setContentsMargins(0, 0, 0, 0)
            setattr(self, f'{section}_layout', layout)
            command_bar = fluentqt.CommandBar(page)
            command_bar.setObjectName(f'{section}_command_bar')
            command_bar.setLabelPosition(fluentqt.CommandBar.LabelPosition.Right)
            command_bar.setBackgroundVisible(False)
            command_bar.setDynamicOverflowEnabled(True)
            setattr(self, f'{section}_command_bar', command_bar)
            for command, icon, caption in (('add', UiIcons().add, UiStrings().Add),
                                           ('edit', UiIcons().edit, UiStrings().Edit),
                                           ('delete', UiIcons().delete, UiStrings().Delete)):
                action = QtGui.QAction(icon, caption, command_bar)
                action.setObjectName(f'{command}_{item}_action')
                setattr(self, f'{command}_{item}_action', action)
                command_bar.addPrimaryAction(action)
            layout.addWidget(command_bar)
            list_widget = QtWidgets.QListWidget(page)
            list_widget.setObjectName(list_name)
            setattr(self, list_name, list_widget)
            layout.addWidget(list_widget, 1)
            self.stacked_layout.addWidget(page)
        #
        self.dialog_layout.addLayout(self.stacked_layout, 0, 1)
        self.dialog_layout.setColumnStretch(1, 1)
        self.button_box = create_button_box(song_maintenance_dialog, 'button_box', ['close'])
        self.dialog_layout.addWidget(self.button_box, 1, 0, 1, 2)
        self.retranslate_ui(song_maintenance_dialog)
        self.stacked_layout.setCurrentIndex(0)
        self.type_list_widget.currentRowChanged.connect(self.stacked_layout.setCurrentIndex)

    def retranslate_ui(self, song_maintenance_dialog):
        """
        Translate the UI on the fly.
        """
        song_maintenance_dialog.setWindowTitle(SongStrings().SongMaintenance)
        self.authors_list_item.setText(SongStrings().Authors)
        self.topics_list_item.setText(SongStrings().Topics)
        self.books_list_item.setText(SongStrings().SongBooks)
        self.add_author_action.setText(UiStrings().Add)
        self.edit_author_action.setText(UiStrings().Edit)
        self.delete_author_action.setText(UiStrings().Delete)
        self.add_topic_action.setText(UiStrings().Add)
        self.edit_topic_action.setText(UiStrings().Edit)
        self.delete_topic_action.setText(UiStrings().Delete)
        self.add_book_action.setText(UiStrings().Add)
        self.edit_book_action.setText(UiStrings().Edit)
        self.delete_book_action.setText(UiStrings().Delete)
        # Ask the view's delegate to include the actual font, icon and Fluent cell padding.
        self.type_list_widget.setFixedWidth(max(180, self.type_list_widget.sizeHintForColumn(0) +
                                               2 * self.type_list_widget.frameWidth() + 16))
