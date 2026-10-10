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
The UI widgets of the settings dialog.
"""
from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.lib.ui import create_button_box
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.style import use_alternate_rows


class SettingsContentWidget(QtWidgets.QWidget):
    """
    Container widget for the settings pages inside the scroll area.

    The size hint is based on the currently visible stacked page so the scroll area only shows
    scrollbars when the active page actually exceeds the available space.
    """

    def sizeHint(self):
        layout = self.layout()
        if isinstance(layout, QtWidgets.QStackedLayout):
            current_widget = layout.currentWidget()
            if current_widget is not None:
                return current_widget.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        layout = self.layout()
        if isinstance(layout, QtWidgets.QStackedLayout):
            current_widget = layout.currentWidget()
            if current_widget is not None:
                return current_widget.minimumSizeHint()
        return super().minimumSizeHint()


class Ui_SettingsDialog(object):
    """
    The UI widgets of the settings dialog.
    """
    def setup_ui(self, settings_dialog):
        """
        Set up the UI
        """
        settings_dialog.setObjectName('settings_dialog')
        settings_dialog.setWindowIcon(UiIcons().main_icon)
        settings_dialog.resize(900, 500)
        self.dialog_layout = QtWidgets.QGridLayout(settings_dialog)
        self.dialog_layout.setObjectName('dialog_layout')
        self.dialog_layout.setContentsMargins(14, 14, 14, 12)
        self.dialog_layout.setHorizontalSpacing(12)
        self.dialog_layout.setVerticalSpacing(10)
        self.setting_list_widget = QtWidgets.QListWidget(settings_dialog)
        self.setting_list_widget.setUniformItemSizes(True)
        self.setting_list_widget.setMinimumSize(QtCore.QSize(210, 0))
        self.setting_list_widget.setIconSize(QtCore.QSize(22, 22))
        sidebar_font = self.setting_list_widget.font()
        if sidebar_font.pointSizeF() > 0:
            sidebar_font.setPointSizeF(sidebar_font.pointSizeF() + 0.5)
            self.setting_list_widget.setFont(sidebar_font)
        self.setting_list_widget.setSpacing(2)
        self.setting_list_widget.setAlternatingRowColors(use_alternate_rows())
        self.setting_list_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setting_list_widget.setStyleSheet('QListWidget::item { padding: 9px 11px; }')
        self.setting_list_widget.setObjectName('setting_list_widget')
        self.dialog_layout.addWidget(self.setting_list_widget, 0, 0, 1, 1)
        self.dialog_layout.setColumnStretch(0, 0)
        self.dialog_layout.setColumnStretch(1, 1)
        self.content_widget = SettingsContentWidget(settings_dialog)
        self.content_widget.setObjectName('content_widget')
        self.content_tabs_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_tabs_layout.setObjectName('content_tabs_layout')
        self.content_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.content_tabs_layout.setSpacing(0)
        self.scroll_area = QtWidgets.QScrollArea(settings_dialog)
        self.scroll_area.setObjectName('scroll_area')
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll_area.setWidget(self.content_widget)
        self.dialog_layout.addWidget(self.scroll_area, 0, 1, 1, 1)
        self.button_box = create_button_box(settings_dialog, 'button_box', ['cancel', 'ok', 'defaults'])
        self.reset_defaults_button = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults)
        self.reset_defaults_button.setObjectName('reset_defaults_button')
        self.dialog_layout.addWidget(self.button_box, 1, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignRight)
        self.retranslate_ui(settings_dialog)

    def retranslate_ui(self, settings_dialog):
        """
        Translate the UI on the fly
        """
        settings_dialog.setWindowTitle(translate('OpenLP.SettingsForm', 'Configure Opal Presenter'))
        self.reset_defaults_button.setText(translate('OpenLP.SettingsForm', 'Reset to defaults'))
