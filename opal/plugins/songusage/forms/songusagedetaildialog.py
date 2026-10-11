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
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.i18n import translate
from opal.core.lib.ui import create_button_box
from opal.core.ui.icons import UiIcons
from opal.core.widgets.edits import PathEdit
from opal.core.widgets.enums import PathEditType


class Ui_SongUsageDetailDialog(object):
    """
    The Song Usage report details
    """
    def setup_ui(self, song_usage_detail_dialog):
        """
        Set up the UI

        :param song_usage_detail_dialog:
        """
        song_usage_detail_dialog.setObjectName('song_usage_detail_dialog')
        song_usage_detail_dialog.setWindowIcon(UiIcons().main_icon)
        self.vertical_layout = QtWidgets.QVBoxLayout(song_usage_detail_dialog.content_widget)
        self.vertical_layout.setObjectName('vertical_layout')
        self.form_layout = QtWidgets.QFormLayout()
        self.form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.from_label = QtWidgets.QLabel(song_usage_detail_dialog)
        self.from_date_picker = QtWidgets.CalendarDatePicker(song_usage_detail_dialog)
        self.from_date_picker.setObjectName('from_date_picker')
        self.from_label.setBuddy(self.from_date_picker)
        self.form_layout.addRow(self.from_label, self.from_date_picker)
        self.to_label = QtWidgets.QLabel(song_usage_detail_dialog)
        self.to_date_picker = QtWidgets.CalendarDatePicker(song_usage_detail_dialog)
        self.to_date_picker.setObjectName('to_date_picker')
        self.to_label.setBuddy(self.to_date_picker)
        self.form_layout.addRow(self.to_label, self.to_date_picker)
        for picker in (self.from_date_picker, self.to_date_picker):
            picker.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.report_path_label = QtWidgets.QLabel(song_usage_detail_dialog)
        self.report_path_edit = PathEdit(song_usage_detail_dialog, path_type=PathEditType.Directories,
                                         show_revert=False)
        self.report_path_label.setBuddy(self.report_path_edit.line_edit)
        self.form_layout.addRow(self.report_path_label, self.report_path_edit)
        self.vertical_layout.addLayout(self.form_layout)
        self.button_box = create_button_box(song_usage_detail_dialog, 'button_box', ['cancel', 'ok'])
        self.vertical_layout.addWidget(self.button_box)
        self.retranslate_ui(song_usage_detail_dialog)
        self.report_path_edit.pathChanged.connect(song_usage_detail_dialog.on_report_path_edit_path_changed)

    def retranslate_ui(self, song_usage_detail_dialog):
        """
        Retranslate the UI

        :param song_usage_detail_dialog:
        """
        song_usage_detail_dialog.setWindowTitle(
            translate('SongUsagePlugin.SongUsageDetailForm', 'Song Usage Extraction'))
        self.from_label.setText(translate('SongUsagePlugin.SongUsageDetailForm', 'From'))
        self.to_label.setText(translate('SongUsagePlugin.SongUsageDetailForm', 'To'))
        self.from_date_picker.setAccessibleName(translate('SongUsagePlugin.SongUsageDetailForm', 'From date'))
        self.to_date_picker.setAccessibleName(translate('SongUsagePlugin.SongUsageDetailForm', 'To date'))
        self.report_path_label.setText(translate('SongUsagePlugin.SongUsageDetailForm', 'Report Location'))
        self.report_path_edit.line_edit.setAccessibleName(self.report_path_label.text())
        self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(
            translate('SongUsagePlugin.SongUsageDetailForm', 'Export'))
