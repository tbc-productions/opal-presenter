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
"""Fluent style browser and editor for inline text formatting."""
from PySide6 import QtCore, QtGui
from fluentqt import CommandBar, FontIcon, FontRole, InfoBadge, TextEdit
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.i18n import UiStrings, translate
from opal.core.lib.ui import create_button_box
from opal.core.ui.icons import UiIcons


class StyleTabs(QtWidgets.QTabWidget):
    """Native Fluent tabs with result badges positioned inside each tab's trailing space."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.match_badges = []
        self._badge_timer = QtCore.QTimer(self)
        self._badge_timer.setSingleShot(True)
        self._badge_timer.timeout.connect(self._position_badges)
        self._tabs.installEventFilter(self)
        self._tabs.tabsChanged.connect(self._schedule_badges)

    def addTab(self, page, label):
        index = super().addTab(page, label)
        badge = InfoBadge(self._tabs)
        badge.setDisplayMode(InfoBadge.InfoBadgeDisplayMode.Value)
        badge.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.match_badges.append(badge)
        return index

    def set_match_counts(self, counts, searching):
        for index, (badge, count) in enumerate(zip(self.match_badges, counts)):
            label = self.tabText(index)
            badge.setValue(count)
            badge.show()
            space_width = max(1, self._tabs.fontMetrics().horizontalAdvance(' '))
            padding = ' ' * ((badge.sizeHint().width() + 8 + space_width - 1) // space_width)
            self._tabs.setTabText(index, label + padding)
            count_label = (translate('OpenLP.FormattingTagDialog', '{tab}: {count} matches') if searching
                           else translate('OpenLP.FormattingTagDialog', '{tab}: {count} styles'))
            accessible_name = count_label.format(tab=label, count=count)
            self._tabs.setTabAccessibleName(index, accessible_name)
        self._schedule_badges()

    def _schedule_badges(self):
        self._badge_timer.start(0)

    def _position_badges(self):
        for index, badge in enumerate(self.match_badges):
            if badge.isHidden():
                continue
            rect = self._tabs.tabGeometry(index)
            badge.resize(badge.sizeHint())
            if self.layoutDirection() == QtCore.Qt.LayoutDirection.RightToLeft:
                x = rect.left() + 8
            else:
                x = rect.right() - badge.width() - 8
            badge.move(x, rect.center().y() - badge.height() // 2)
            badge.raise_()

    def eventFilter(self, watched, event):
        if watched is self._tabs and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show,
                                                      QtCore.QEvent.Type.LayoutDirectionChange):
            self._schedule_badges()
        return super().eventFilter(watched, event)


class Ui_FormattingTagDialog(object):
    """Build the formatting styles dialog."""

    def setup_ui(self, formatting_tag_dialog):
        formatting_tag_dialog.setObjectName('formatting_tag_dialog')
        formatting_tag_dialog.setWindowIcon(UiIcons().main_icon)
        formatting_tag_dialog.setMinimumSize(860, 640)
        self.content_widget = QtWidgets.QWidget()
        formatting_tag_dialog.setContentWidget(self.content_widget)
        self.list_data_grid_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.list_data_grid_layout.setContentsMargins(24, 20, 24, 20)
        self.list_data_grid_layout.setSpacing(16)
        self.window_title_label = QtWidgets.QLabel()
        self.window_title_label.setContentsMargins(12, 0, 12, 0)
        self.window_title_label.setFluentTypography(FontRole.BodyStrong)
        formatting_tag_dialog.titleBar().setContentWidget(self.window_title_label)

        self.content_splitter = QtWidgets.QSplitter(formatting_tag_dialog)
        self.content_splitter.setChildrenCollapsible(False)
        self.list_data_grid_layout.addWidget(self.content_splitter, 1)
        browser = QtWidgets.QWidget(self.content_splitter)
        browser.setMinimumWidth(340)
        browser_layout = QtWidgets.QVBoxLayout(browser)
        browser_layout.setContentsMargins(0, 0, 12, 0)
        browser_layout.setSpacing(12)
        self.search_edit = QtWidgets.QLineEdit(browser)
        self.search_edit.setClearButtonEnabled(True)
        browser_layout.addWidget(self.search_edit)
        collection = QtWidgets.QWidget(browser)
        collection_layout = QtWidgets.QVBoxLayout(collection)
        collection_layout.setContentsMargins(0, 0, 0, 0)
        collection_layout.setSpacing(0)
        self.style_tabs = StyleTabs(collection)
        self.tag_table_widget = self._create_style_table('tag_table_widget', 6)
        self.tag_table_widget_read = self._create_style_table('tag_table_widget_read', 5)
        for table in (self.tag_table_widget_read, self.tag_table_widget):
            page = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(page)
            layout.setContentsMargins(0, 12, 0, 0)
            layout.setSpacing(8)
            layout.addWidget(table, 1)
            self.style_tabs.addTab(page, '')
        self.style_command_bar = self._create_command_bar(collection, 'style_command_bar')
        self.new_button = self._create_command(
            self.style_command_bar, 'new_button', UiIcons().new,
            UiStrings().New)
        self.copy_button = self._create_command(
            self.style_command_bar, 'copy_button', UiIcons().copy, translate('OpenLP.FormattingTagDialog', 'Copy'))
        self.delete_button = self._create_command(
            self.style_command_bar, 'delete_button', UiIcons().delete, UiStrings().Delete)
        self.import_button = self._create_command(
            self.style_command_bar, 'import_button', UiIcons().download, UiStrings().Import)
        self.export_button = self._create_command(
            self.style_command_bar, 'export_button', UiIcons().upload, UiStrings().Export)
        collection_layout.addWidget(self.style_command_bar)
        collection_layout.addWidget(self.style_tabs, 1)
        browser_layout.addWidget(collection, 1)

        editor_scroll = QtWidgets.QScrollArea(self.content_splitter)
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        editor_scroll.setMinimumWidth(420)
        self.editor_card = QtWidgets.Card()
        editor_scroll.setWidget(self.editor_card)
        editor_layout = QtWidgets.QVBoxLayout(self.editor_card)
        editor_layout.setContentsMargins(20, 16, 20, 16)
        editor_layout.setSpacing(8)
        self.editor_heading = QtWidgets.QLabel(self.editor_card)
        self.editor_heading.setFluentTypography(FontRole.Subtitle)
        editor_header = QtWidgets.QHBoxLayout()
        editor_header.addWidget(self.editor_heading, 1)
        self.read_only_icon = FontIcon('ic_fluent_lock_closed_24_regular', self.editor_card)
        self.read_only_icon.setObjectName('read_only_icon')
        self.read_only_icon.setIconSize(20)
        editor_header.addWidget(self.read_only_icon)
        editor_layout.addLayout(editor_header)
        self.preview_heading = QtWidgets.QLabel(self.editor_card)
        self.preview_heading.setFluentTypography(FontRole.BodyStrong)
        editor_layout.addWidget(self.preview_heading)
        self.preview_card = QtWidgets.Card(self.editor_card)
        self.preview_card.setMinimumHeight(80)
        preview_layout = QtWidgets.QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(16, 12, 16, 12)
        self.preview_label = QtWidgets.QLabel(self.preview_card)
        self.preview_label.setFluentTypography(FontRole.Subtitle)
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)
        editor_layout.addWidget(self.preview_card)
        self.editor_fields = QtWidgets.QWidget(self.editor_card)
        editor_layout.addWidget(self.editor_fields)
        fields_layout = QtWidgets.QVBoxLayout(self.editor_fields)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(8)
        self.name_edit = QtWidgets.QLineEdit(self.editor_fields)
        self.tag_edit = QtWidgets.QLineEdit(self.editor_fields)
        self.start_html_edit = TextEdit(self.editor_fields)
        self.end_html_edit = TextEdit(self.editor_fields)
        for edit in (self.start_html_edit, self.end_html_edit):
            edit.setMinVisibleLines(2)
            edit.setMaxVisibleLines(3)
            edit.setTabChangesFocus(True)
        self.field_labels = []
        identity_layout = QtWidgets.QGridLayout()
        identity_layout.setColumnStretch(0, 2)
        identity_layout.setColumnStretch(1, 1)
        identity_layout.setHorizontalSpacing(12)
        fields_layout.addLayout(identity_layout)
        for index, edit in enumerate((self.name_edit, self.tag_edit, self.start_html_edit, self.end_html_edit)):
            label = QtWidgets.QLabel(self.editor_fields)
            label.setFluentTypography(FontRole.BodyStrong)
            label.setBuddy(edit)
            self.field_labels.append(label)
            if index < 2:
                identity_layout.addWidget(label, 0, index)
                identity_layout.addWidget(edit, 1, index)
            else:
                fields_layout.addWidget(label)
                fields_layout.addWidget(edit)
        self.hidden_checkbox = QtWidgets.QCheckBox(self.editor_fields)
        fields_layout.addWidget(self.hidden_checkbox)
        editor_layout.addStretch()
        self.content_splitter.setSizes([640, 480])

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        self.button_box = create_button_box(formatting_tag_dialog, 'button_box', ['cancel', 'save'])
        self.save_button = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        self.save_button.setObjectName('save_button')
        self.save_button.setIcon(UiIcons().get_icon_variant('save', color='white'))
        self.save_button.setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Accent)
        footer.addWidget(self.button_box)
        self.list_data_grid_layout.addLayout(footer)
        self.retranslate_ui(formatting_tag_dialog)
        formatting_tag_dialog.resize(1160, 780)

    def _create_command_bar(self, parent, name):
        bar = CommandBar(parent)
        bar.setObjectName(name)
        bar.setLabelPosition(CommandBar.LabelPosition.Right)
        bar.setDynamicOverflowEnabled(True)
        bar.setBackgroundVisible(True)
        bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        return bar

    def _create_command(self, bar, name, icon, text):
        action = QtGui.QAction(icon, text, bar)
        action.setObjectName(name)
        bar.addPrimaryAction(action)
        return action

    def _create_style_table(self, name, columns):
        """Show readable style information; HTML lives in the detail editor."""
        table = QtWidgets.QTableWidget()
        table.setObjectName(name)
        table.setColumnCount(columns)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setCornerButtonEnabled(False)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 70)
        table.setColumnWidth(4, 115)
        for column in range(columns):
            table.setHorizontalHeaderItem(column, QtWidgets.QTableWidgetItem())
        for column in (2, 3, 5):
            if column < columns:
                table.setColumnHidden(column, True)
        return table

    def retranslate_ui(self, formatting_tag_dialog):
        formatting_tag_dialog.setWindowTitle(translate('OpenLP.FormattingTagDialog', 'Formatting styles'))
        self.window_title_label.setText(formatting_tag_dialog.windowTitle())
        self.search_edit.setPlaceholderText(translate('OpenLP.FormattingTagDialog', 'Search styles by name or tag'))
        self.search_edit.setAccessibleName(translate('OpenLP.FormattingTagDialog', 'Search styles'))
        self.style_tabs.setTabText(0, translate('OpenLP.FormattingTagDialog', 'Built-in'))
        self.style_tabs.setTabText(1, translate('OpenLP.FormattingTagDialog', 'Custom'))
        self.new_button.setText(UiStrings().New)
        self.copy_button.setText(translate('OpenLP.FormattingTagDialog', 'Copy'))
        self.delete_button.setText(UiStrings().Delete)
        self.save_button.setText(translate('OpenLP.FormattingTagDialog', 'Save changes'))
        self.import_button.setText(UiStrings().Import)
        self.export_button.setText(UiStrings().Export)
        self.import_button.setToolTip(translate('OpenLP.FormattingTagDialog', 'Import custom styles from a JSON file.'))
        self.export_button.setToolTip(translate('OpenLP.FormattingTagDialog', 'Export custom styles to a JSON file.'))
        self.copy_button.setToolTip(translate('OpenLP.FormattingTagDialog', 'Create an editable copy of this style.'))
        read_only = translate('OpenLP.FormattingTagDialog', 'Read-only')
        self.read_only_icon.setToolTip(read_only)
        self.read_only_icon.setAccessibleName(read_only)
        column_labels = ((0, translate('OpenLP.FormattingTagDialog', 'Name')),
                         (1, translate('OpenLP.FormattingTagDialog', 'Tag')),
                         (4, translate('OpenLP.FormattingTagDialog', 'Preview')))
        for table in (self.tag_table_widget, self.tag_table_widget_read):
            for column, text in column_labels:
                table.horizontalHeaderItem(column).setText(text)
        field_labels = (translate('OpenLP.FormattingTagDialog', 'Name'),
                        translate('OpenLP.FormattingTagDialog', 'Tag'),
                        translate('OpenLP.FormattingTagDialog', 'Opening HTML'),
                        translate('OpenLP.FormattingTagDialog', 'Closing HTML'))
        for label, edit, text in zip(self.field_labels,
                                     (self.name_edit, self.tag_edit, self.start_html_edit, self.end_html_edit),
                                     field_labels):
            label.setText(text)
            edit.setAccessibleName(text)
        self.name_edit.setPlaceholderText(translate('OpenLP.FormattingTagDialog', 'e.g. Emphasis'))
        self.tag_edit.setPlaceholderText(translate('OpenLP.FormattingTagDialog', 'e.g. emphasis'))
        self.tag_edit.setToolTip(translate('OpenLP.FormattingTagDialog', 'Enter the tag without braces or spaces.'))
        self.start_html_edit.setPlaceholderText('<span style="font-weight: bold;">')
        self.start_html_edit.setToolTip(
            translate('OpenLP.FormattingTagDialog', 'Closing HTML is suggested automatically as you type.'))
        self.end_html_edit.setPlaceholderText('</span>')
        self.hidden_checkbox.setText(translate(
            'OpenLP.FormattingTagDialog', 'Hide tagged text in slide lists and printouts'))
        self.hidden_checkbox.setToolTip(translate(
            'OpenLP.FormattingTagDialog',
            'Text enclosed by this style is omitted from the Preview and Live slide lists and printed service sheets. '
            'It remains in the lyrics/custom slide editor and on projected slides.'))
        self.preview_heading.setText(translate('OpenLP.FormattingTagDialog', 'Preview'))
