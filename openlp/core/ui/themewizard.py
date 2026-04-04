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
The Create/Edit theme dialog
"""
from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.display.render import ThemePreviewRenderer
from openlp.core.lib.ui import create_button_box
from openlp.core.pages.alignment import AlignmentTransitionsPage
from openlp.core.pages.areaposition import AreaPositionPage
from openlp.core.pages.background import BackgroundPage
from openlp.core.pages.fontselect import FontSelectPage
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets.layouts import AspectRatioLayout


class Ui_ThemeWizard(object):
    """
    The Create/Edit theme dialog
    """
    def setup_ui(self, theme_dialog):
        """
        Set up the UI
        """
        theme_dialog.setObjectName('OpenLP.ThemeWizard')
        theme_dialog.setWindowIcon(UiIcons().main_icon)
        theme_dialog.setModal(True)
        theme_dialog.resize(1100, 700)
        self.dialog_layout = QtWidgets.QGridLayout(theme_dialog)
        self.dialog_layout.setObjectName('dialog_layout')
        self.dialog_layout.setContentsMargins(14, 14, 14, 12)
        self.dialog_layout.setHorizontalSpacing(12)
        self.dialog_layout.setVerticalSpacing(10)

        self.page_list_widget = QtWidgets.QListWidget(theme_dialog)
        self.page_list_widget.setObjectName('page_list_widget')
        self.page_list_widget.setUniformItemSizes(True)
        self.page_list_widget.setAlternatingRowColors(True)
        self.page_list_widget.setMinimumSize(QtCore.QSize(210, 0))
        self.page_list_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_list_widget.setStyleSheet('QListWidget::item { padding: 9px 11px; }')
        self.dialog_layout.addWidget(self.page_list_widget, 0, 0, 1, 1)

        self.editor_widget = QtWidgets.QWidget(theme_dialog)
        self.editor_widget.setObjectName('editor_widget')
        self.editor_layout = QtWidgets.QVBoxLayout(self.editor_widget)
        self.editor_layout.setObjectName('editor_layout')
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(10)
        self.theme_name_layout = QtWidgets.QFormLayout()
        self.theme_name_layout.setObjectName('theme_name_layout')
        self.theme_name_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.theme_name_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.theme_name_layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.theme_name_label = QtWidgets.QLabel(self.editor_widget)
        self.theme_name_label.setObjectName('theme_name_label')
        self.theme_name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.theme_name_edit = QtWidgets.QLineEdit(self.editor_widget)
        self.theme_name_edit.setValidator(QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(r'[^/\\?*|<>\[\]":<>+%]+'), theme_dialog))
        self.theme_name_edit.setObjectName('ThemeNameEdit')
        self.theme_name_edit.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.theme_name_layout.addRow(self.theme_name_label, self.theme_name_edit)
        self.editor_layout.addLayout(self.theme_name_layout)
        self.page_stack = QtWidgets.QStackedWidget(self.editor_widget)
        self.page_stack.setObjectName('page_stack')
        self.editor_layout.addWidget(self.page_stack)
        self.dialog_layout.addWidget(self.editor_widget, 0, 1, 1, 1)

        self.preview_panel = QtWidgets.QWidget(theme_dialog)
        self.preview_panel.setObjectName('preview_panel')
        self.preview_panel.setMinimumWidth(320)
        self.preview_panel.setMaximumWidth(520)
        self.preview_panel_layout = QtWidgets.QVBoxLayout(self.preview_panel)
        self.preview_panel_layout.setObjectName('preview_panel_layout')
        self.preview_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_panel_layout.setSpacing(6)
        self.preview_label = QtWidgets.QLabel(self.preview_panel)
        self.preview_label.setObjectName('preview_label')
        self.preview_panel_layout.addWidget(self.preview_label)
        self.preview_area = QtWidgets.QWidget(self.preview_panel)
        self.preview_area.setObjectName('PreviewArea')
        self.preview_area_layout = AspectRatioLayout(self.preview_area, 0.75)  # Dummy ratio, will be updated
        self.preview_area_layout.margin = 8
        self.preview_area_layout.setSpacing(0)
        self.preview_area_layout.setObjectName('preview_web_layout')
        self.preview_box = ThemePreviewRenderer(theme_dialog, window_title='Theme Editor Preview')
        self.preview_box.setObjectName('preview_box')
        self.preview_box.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
        self.preview_area_layout.addWidget(self.preview_box)
        self.preview_area_layout.setAlignment(self.preview_box, QtCore.Qt.AlignmentFlag.AlignTop)
        self.preview_panel_layout.addWidget(self.preview_area)
        self.layout_guide_button = QtWidgets.QPushButton(self.preview_panel)
        self.layout_guide_button.setObjectName('layout_guide_button')
        self.preview_panel_layout.addWidget(self.layout_guide_button, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.preview_panel_layout.addStretch()
        self.dialog_layout.addWidget(self.preview_panel, 0, 2, 1, 1)

        self.dialog_layout.setColumnStretch(0, 0)
        self.dialog_layout.setColumnStretch(1, 1)
        self.dialog_layout.setColumnStretch(2, 1)

        # Background Page
        self.background_page = BackgroundPage()
        self.background_page.setObjectName('background_page')
        self.page_stack.addWidget(self.background_page)
        # Main Area Page
        self.main_area_page = FontSelectPage()
        self.main_area_page.setObjectName('main_area_page')
        self.main_area_page.disable_features(FontSelectPage.Wrap)
        self.page_stack.addWidget(self.main_area_page)
        # Footer Area Page
        self.footer_area_page = FontSelectPage()
        self.footer_area_page.setObjectName('footer_area_page')
        self.footer_area_page.disable_features(FontSelectPage.Outline, FontSelectPage.Shadow)
        self.page_stack.addWidget(self.footer_area_page)
        # Alignment Page
        self.alignment_page = AlignmentTransitionsPage()
        self.alignment_page.setObjectName('alignment_page')
        self.page_stack.addWidget(self.alignment_page)
        # Area Position Page
        self.area_position_page = AreaPositionPage()
        self.area_position_page.setObjectName('area_position_page')
        self.page_stack.addWidget(self.area_position_page)

        self.page_list_widget.addItems(['', '', '', '', ''])
        self.page_list_widget.setCurrentRow(0)

        self.button_box = create_button_box(theme_dialog, 'button_box', ['cancel', 'save', 'help'])
        self.dialog_layout.addWidget(self.button_box, 1, 0, 1, 3, QtCore.Qt.AlignmentFlag.AlignRight)
        self.retranslate_ui(theme_dialog)

    def retranslate_ui(self, theme_dialog):
        """
        Translate the UI on the fly
        """
        theme_dialog.setWindowTitle(translate('OpenLP.ThemeWizard', 'Theme Editor'))
        self.page_list_widget.item(0).setText(translate('OpenLP.ThemeWizard', 'Background'))
        self.page_list_widget.item(1).setText(translate('OpenLP.ThemeWizard', 'Main Text'))
        self.page_list_widget.item(2).setText(translate('OpenLP.ThemeWizard', 'Footer Text'))
        self.page_list_widget.item(3).setText(translate('OpenLP.ThemeWizard', 'Formatting'))
        self.page_list_widget.item(4).setText(translate('OpenLP.ThemeWizard', 'Positions'))
        self.preview_label.setText(translate('OpenLP.ThemeWizard', 'Preview'))
        self.layout_guide_button.setText(translate('OpenLP.ThemeWizard', 'Show layout guide'))
        self.theme_name_label.setText(translate('OpenLP.ThemeWizard', 'Theme name:'))
