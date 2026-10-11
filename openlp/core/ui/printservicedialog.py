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
The UI widgets of the print service dialog.
"""
from PySide6 import QtCore, QtGui, QtPrintSupport
from fluentqt import CommandBar
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import UiStrings, translate
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets.edits import SpellTextEdit


class ZoomSize(object):
    """
    Type enumeration for Combo Box sizes
    """
    Page = 0
    Width = 1
    OneHundred = 2
    SeventyFive = 3
    Fifty = 4
    TwentyFive = 5


class Ui_PrintServiceDialog(object):
    """
    The UI of the print service dialog
    """
    def setup_ui(self, print_service_dialog):
        """
        Set up the UI
        """
        print_service_dialog.setObjectName('print_service_dialog')
        print_service_dialog.setWindowIcon(UiIcons().main_icon)
        print_service_dialog.resize(1100, 700)
        self.content_widget = QtWidgets.QWidget(print_service_dialog)
        print_service_dialog.setContentWidget(self.content_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setObjectName('main_layout')
        self.toolbar = CommandBar(self.content_widget)
        self.toolbar.setObjectName('print_command_bar')
        self.toolbar.setLabelPosition(CommandBar.LabelPosition.Right)
        self.toolbar.setDynamicOverflowEnabled(True)
        self.toolbar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.print_button = self._add_command('print_button', UiIcons().print, 'Print')
        self.plain_copy = self._add_command('plain_copy', UiIcons().clone, 'Copy as Text')
        self.html_copy = self._add_command('html_copy', UiIcons().clone, 'Copy as HTML')
        self.zoom_out_button = self._add_command('zoom_out_button', UiIcons().search_minus, 'Zoom Out')
        self.zoom_in_button = self._add_command('zoom_in_button', UiIcons().search_plus, 'Zoom In')
        self.zoom_original_button = self._add_command('zoom_original_button', UiIcons().search, 'Zoom Original')
        self.close_button = self._add_command('close_button', UiIcons().close, 'Close')
        self.close_button.triggered.connect(print_service_dialog.close)
        self.main_layout.addWidget(self.toolbar)
        self.content_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self.content_widget)
        self.content_splitter.setChildrenCollapsible(False)
        self.main_layout.addWidget(self.content_splitter, 1)
        self.options_scroll_area = QtWidgets.QScrollArea(self.content_splitter)
        self.options_scroll_area.setWidgetResizable(True)
        self.options_scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.options_scroll_area.setMinimumWidth(340)
        self.options_widget = QtWidgets.QWidget()
        self.options_widget.setObjectName('print_options_pane')
        self.options_scroll_area.setWidget(self.options_widget)
        self.options_layout = QtWidgets.QVBoxLayout(self.options_widget)
        self.options_layout.setContentsMargins(16, 16, 16, 16)
        self.options_layout.setSpacing(12)
        self.title_label = QtWidgets.QLabel(self.options_widget)
        self.title_label.setObjectName('title_label')
        self.options_layout.addWidget(self.title_label)
        self.title_line_edit = QtWidgets.QLineEdit(self.options_widget)
        self.title_line_edit.setObjectName('title_line_edit')
        self.options_layout.addWidget(self.title_line_edit)
        self.footer_label = QtWidgets.QLabel(self.options_widget)
        self.footer_label.setObjectName('footer_label')
        self.options_layout.addWidget(self.footer_label)
        self.footer_text_edit = SpellTextEdit(self.options_widget, False)
        self.footer_text_edit.setObjectName('footer_text_edit')
        self.footer_text_edit.setMinimumHeight(96)
        self.footer_text_edit.setMaximumHeight(160)
        self.options_layout.addWidget(self.footer_text_edit)
        self.options_group_box = QtWidgets.QGroupBox()
        self.group_layout = QtWidgets.QVBoxLayout()
        self.group_layout.setContentsMargins(12, 12, 12, 12)
        self.slide_text_check_box = QtWidgets.QCheckBox()
        self.group_layout.addWidget(self.slide_text_check_box)
        self.page_break_after_text = QtWidgets.QCheckBox()
        self.group_layout.addWidget(self.page_break_after_text)
        self.notes_check_box = QtWidgets.QCheckBox()
        self.group_layout.addWidget(self.notes_check_box)
        self.meta_data_check_box = QtWidgets.QCheckBox()
        self.group_layout.addWidget(self.meta_data_check_box)
        self.show_chords_check_box = QtWidgets.QCheckBox()
        self.group_layout.addWidget(self.show_chords_check_box)
        self.show_icons_check_box = QtWidgets.QCheckBox()
        self.group_layout.addWidget(self.show_icons_check_box)
        self.options_group_box.setLayout(self.group_layout)
        self.options_layout.addWidget(self.options_group_box)
        self.zoom_layout = QtWidgets.QHBoxLayout()
        self.zoom_label = QtWidgets.QLabel(self.options_widget)
        self.zoom_combo_box = QtWidgets.QComboBox(self.options_widget)
        self.zoom_combo_box.setObjectName('zoom_combo_box')
        self.zoom_label.setBuddy(self.zoom_combo_box)
        self.zoom_layout.addWidget(self.zoom_label)
        self.zoom_layout.addWidget(self.zoom_combo_box, 1)
        self.options_layout.addLayout(self.zoom_layout)
        self.options_layout.addStretch(1)
        self.preview_widget = QtPrintSupport.QPrintPreviewWidget(self.content_splitter)
        self.content_splitter.addWidget(self.options_scroll_area)
        self.content_splitter.addWidget(self.preview_widget)
        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([340, 760])

        self.retranslate_ui(print_service_dialog)

    def _add_command(self, name, icon, text):
        """Keep all print actions in the same native CommandBar."""
        action = QtGui.QAction(icon, translate('OpenLP.PrintServiceForm', text), self.toolbar)
        action.setObjectName(name)
        self.toolbar.addPrimaryAction(action)
        return action

    def retranslate_ui(self, print_service_dialog):
        """
        Translate the UI on the fly
        """
        print_service_dialog.setWindowTitle(UiStrings().PrintService)
        self.zoom_out_button.setToolTip(translate('OpenLP.PrintServiceForm', 'Zoom Out'))
        self.zoom_original_button.setToolTip(translate('OpenLP.PrintServiceForm', 'Zoom Original'))
        self.zoom_in_button.setToolTip(translate('OpenLP.PrintServiceForm', 'Zoom In'))
        self.options_group_box.setTitle(translate('OpenLP.PrintServiceForm', 'Options'))
        self.title_label.setText(translate('OpenLP.PrintServiceForm', 'Title:'))
        self.footer_label.setText(translate('OpenLP.PrintServiceForm', 'Service Note Text:'))
        self.slide_text_check_box.setText(translate('OpenLP.PrintServiceForm', 'Include slide text'))
        self.page_break_after_text.setText(translate('OpenLP.PrintServiceForm', 'Page break before each text item'))
        self.notes_check_box.setText(translate('OpenLP.PrintServiceForm', 'Include service item notes'))
        self.meta_data_check_box.setText(translate('OpenLP.PrintServiceForm', 'Include media play length'))
        self.show_chords_check_box.setText(translate('OpenLP.PrintServiceForm', 'Show chords'))
        self.show_icons_check_box.setText(translate('OpenLP.PrintServiceForm', 'Show icons'))
        self.title_line_edit.setText(translate('OpenLP.PrintServiceForm', 'Service Sheet'))
        self.zoom_label.setText(translate('OpenLP.PrintServiceForm', 'Zoom:'))
        # Do not change the order.
        self.zoom_combo_box.addItems([
            translate('OpenLP.PrintServiceDialog', 'Fit Page'),
            translate('OpenLP.PrintServiceDialog', 'Fit Width'),
            '100%',
            '75%',
            '50%',
            '25%'
        ])
