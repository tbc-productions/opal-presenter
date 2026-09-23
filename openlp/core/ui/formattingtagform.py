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
The :mod:`formattingtagform` provides an Tag Edit facility. The Base set are protected and included each time loaded.
Custom tags can be defined and saved. The Custom Tag arrays are saved in a json string so QSettings works on them.
Base Tags cannot be changed.
"""
import json
import re

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.lib.formattingtags import FormattingTags
from openlp.core.ui.formattingtagcontroller import FormattingTagController
from openlp.core.ui.formattingtagdialog import Ui_FormattingTagDialog
from openlp.core.widgets.dialogs import FileDialog


class EditColumn(object):
    """
    Hides the magic numbers for the table columns
    """
    Description = 0
    Tag = 1
    StartHtml = 2
    EndHtml = 3
    Preview = 4
    Hidden = 5


class FormattingTagForm(QtWidgets.QDialog, Ui_FormattingTagDialog, FormattingTagController):
    """
    The :class:`FormattingTagForm` manages the settings tab .
    """
    def __init__(self, parent):
        """
        Constructor
        """
        super(FormattingTagForm, self).__init__(parent,
                                                QtCore.Qt.WindowType.WindowSystemMenuHint |
                                                QtCore.Qt.WindowType.WindowTitleHint |
                                                QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setup_ui(self)
        self._setup()

    def _setup(self):
        """
        Set up the class. This method is mocked out by the tests.
        """
        self.services = FormattingTagController()
        self.tag_table_widget.itemSelectionChanged.connect(self.on_row_selected)
        self.new_button.clicked.connect(self.on_new_clicked)
        self.delete_button.clicked.connect(self.on_delete_clicked)
        self.import_button.clicked.connect(self.on_import_clicked)
        self.export_button.clicked.connect(self.on_export_clicked)
        self.tag_table_widget.itemChanged.connect(self.on_table_item_changed)
        self.button_box.rejected.connect(self.close)
        # Forces reloading of tags from openlp configuration.
        FormattingTags.load_tags()
        self.is_deleting = False
        self.reloading = False

    def exec(self):
        """
        Load Display and set field state.
        """
        # Create initial copy from master
        self._reloadTable()
        return QtWidgets.QDialog.exec(self)

    def on_row_selected(self):
        """
        Table Row selected so display items and set field state.
        """
        self.delete_button.setEnabled(True)

    def on_new_clicked(self):
        """
        Add a new tag to edit list and select it for editing.
        """
        previous_state = self.tag_table_widget.blockSignals(True)
        new_row = self.tag_table_widget.rowCount()
        self.tag_table_widget.insertRow(new_row)
        self.tag_table_widget.setItem(new_row, 0,
                                      QtWidgets.QTableWidgetItem(translate('OpenLP.FormattingTagForm',
                                                                           'New Tag {row:d}').format(row=new_row)))
        self.tag_table_widget.setItem(new_row, 1, QtWidgets.QTableWidgetItem('n{row:d}'.format(row=new_row)))
        self.tag_table_widget.setItem(new_row, 2,
                                      QtWidgets.QTableWidgetItem(translate('OpenLP.FormattingTagForm', '<HTML here>')))
        self.tag_table_widget.setItem(new_row, 3, QtWidgets.QTableWidgetItem(''))
        self.tag_table_widget.setCellWidget(new_row, EditColumn.Preview,
                                            self._build_preview_widget('', ''))
        hiddenwidget = QtWidgets.QWidget()
        hiddencheckbox = QtWidgets.QCheckBox()
        hiddenlayout = QtWidgets.QHBoxLayout()
        hiddenlayout.addWidget(hiddencheckbox)
        hiddenlayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hiddenlayout.setContentsMargins(0, 0, 0, 0)
        hiddenwidget.setLayout(hiddenlayout)
        hiddencheckbox.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.tag_table_widget.setCellWidget(new_row, EditColumn.Hidden, hiddenwidget)
        self.tag_table_widget.blockSignals(previous_state)
        self.tag_table_widget.resizeRowsToContents()
        self.tag_table_widget.scrollToBottom()
        self.tag_table_widget.selectRow(new_row)

    def _build_preview_widget(self, start_html, end_html):
        """
        Create a preview label that renders sample text with the provided HTML wrapper.
        """
        preview_widget = QtWidgets.QLabel()
        preview_widget.setWordWrap(True)
        preview_widget.setTextFormat(QtCore.Qt.TextFormat.RichText)
        preview_widget.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        normalized_start_html = self._normalize_preview_html(start_html or '', preview_widget)
        preview_widget.setText('{start}{text}{end}'.format(start=normalized_start_html,
                                   text=translate('OpenLP.FormattingTagForm', 'Preview text'),
                                   end=end_html or ''))
        return preview_widget

    def _normalize_preview_html(self, start_html, preview_widget):
        """
        Convert CSS that QLabel rich text does not handle well into a more compatible form for preview only.
        """
        normalized = start_html.replace('-webkit-text-fill-color', 'color')
        style_match = re.search(r'style\s*=\s*"([^"]*)"', normalized, flags=re.IGNORECASE)
        if not style_match:
            return normalized
        style = style_match.group(1)
        # QLabel rich text is inconsistent with numeric font weights.
        style = re.sub(r'font-weight\s*:\s*(\d{3})',
                       lambda match: 'font-weight: {weight}'.format(
                           weight='bold' if int(match.group(1)) >= 600 else 'normal'),
                       style,
                       flags=re.IGNORECASE)
        # Convert percentages to a concrete point size for consistent rendering.
        base_point_size = preview_widget.font().pointSizeF()
        if base_point_size <= 0:
            base_point_size = 12.0

        def _percent_to_point_size(match):
            percentage = float(match.group(1)) / 100.0
            return 'font-size: {size:.1f}pt'.format(size=base_point_size * percentage)

        style = re.sub(r'font-size\s*:\s*([0-9]*\.?[0-9]+)\s*%', _percent_to_point_size,
                       style, flags=re.IGNORECASE)
        # Emulate opacity by applying alpha to color in preview styles.
        opacity_match = re.search(r'opacity\s*:\s*([0-9]*\.?[0-9]+)', style, flags=re.IGNORECASE)
        if opacity_match:
            opacity = max(0.0, min(1.0, float(opacity_match.group(1))))
            style = re.sub(r'opacity\s*:\s*[0-9]*\.?[0-9]+\s*;?', '', style, flags=re.IGNORECASE)
            color_match = re.search(r'color\s*:\s*([^;]+)', style, flags=re.IGNORECASE)
            if color_match:
                base_color = QtGui.QColor(color_match.group(1).strip())
            else:
                base_color = preview_widget.palette().color(QtGui.QPalette.ColorRole.WindowText)
            if base_color.isValid():
                base_color.setAlphaF(opacity)
                rgba_color = 'rgba({red}, {green}, {blue}, {alpha:.3f})'.format(
                    red=base_color.red(), green=base_color.green(), blue=base_color.blue(), alpha=opacity)
                if color_match:
                    style = re.sub(r'color\s*:\s*[^;]+', 'color: {color}'.format(color=rgba_color), style,
                                   count=1, flags=re.IGNORECASE)
                else:
                    style = 'color: {color}; {style}'.format(color=rgba_color, style=style).strip()
        style = re.sub(r'\s{2,}', ' ', style).strip()
        return normalized[:style_match.start(1)] + style + normalized[style_match.end(1):]

    def _update_preview_cell(self, row):
        """
        Refresh a row preview label in the custom formatting table.
        """
        start_item = self.tag_table_widget.item(row, EditColumn.StartHtml)
        end_item = self.tag_table_widget.item(row, EditColumn.EndHtml)
        if not start_item or not end_item:
            return
        self.tag_table_widget.setCellWidget(row, EditColumn.Preview,
                                            self._build_preview_widget(start_item.text(), end_item.text()))
        self.tag_table_widget.resizeRowsToContents()

    def on_delete_clicked(self):
        """
        Delete selected custom row.
        """
        selected = self.tag_table_widget.currentRow()
        if selected != -1:
            self.is_deleting = True
            self.tag_table_widget.removeRow(selected)

    def accept(self):
        """
        Update Custom Tag details if not duplicate and save the data.
        """
        if not self._validate_tags_for_save():
            return
        self.services.save_tags()
        QtWidgets.QDialog.accept(self)

    def _validate_tags_for_save(self):
        """
        Validate the current custom tags in the table and build ``self.services.custom_tags``.
        """
        count = 0
        self.services.pre_save()
        while count < self.tag_table_widget.rowCount():
            error = self.services.validate_for_save(self.tag_table_widget.item(count, 0).text(),
                                                    self.tag_table_widget.item(count, 1).text(),
                                                    self.tag_table_widget.item(count, 2).text(),
                                                    self.tag_table_widget.item(count, 3).text(),
                                                    self.tag_table_widget.cellWidget(count, EditColumn.Hidden).
                                                    children()[1].isChecked()
                                                    )
            if error:
                QtWidgets.QMessageBox.warning(self, translate('OpenLP.FormattingTagForm', 'Validation Error'), error)
                self.tag_table_widget.selectRow(count)
                return False
            count += 1
        return True

    def on_export_clicked(self):
        """
        Export custom formatting tags to a JSON file.
        """
        if not self._validate_tags_for_save():
            return
        settings = Registry().get('settings')
        try:
            last_export_directory = settings.value('formattingTags/last directory export')
        except KeyError:
            last_export_directory = None
        export_file_path, filter_used = FileDialog.getSaveFileName(
            self,
            translate('OpenLP.FormattingTagForm', 'Export Formatting Tags'),
            last_export_directory,
            translate('OpenLP.FormattingTagForm', 'OpenLP+ Formatting Tags (*.json)'))
        if not export_file_path:
            return
        export_file_path = export_file_path.with_suffix('.json')
        try:
            with export_file_path.open('w', encoding='utf-8') as exported_tags_file:
                json.dump(self.services.custom_tags, exported_tags_file, indent=2)
        except OSError as ose:
            QtWidgets.QMessageBox.critical(
                self,
                translate('OpenLP.FormattingTagForm', 'Formatting Tag Export Error'),
                translate('OpenLP.FormattingTagForm',
                          'An error occurred while exporting formatting tags: {err}').format(err=ose.strerror))
            return
        settings.setValue('formattingTags/last directory export', export_file_path.parent)

    def on_import_clicked(self):
        """
        Import custom formatting tags from a JSON file.
        """
        settings = Registry().get('settings')
        try:
            last_import_directory = settings.value('formattingTags/last directory import')
        except KeyError:
            last_import_directory = None
        import_file_path, filter_used = FileDialog.getOpenFileName(
            self,
            translate('OpenLP.FormattingTagForm', 'Import Formatting Tags'),
            last_import_directory,
            translate('OpenLP.FormattingTagForm', 'OpenLP+ Formatting Tags (*.json)'))
        if import_file_path is None:
            return
        try:
            with import_file_path.open('r', encoding='utf-8') as imported_tags_file:
                imported_tags = json.load(imported_tags_file)
        except (OSError, ValueError, TypeError):
            QtWidgets.QMessageBox.critical(
                self,
                translate('OpenLP.FormattingTagForm', 'Formatting Tag Import Error'),
                translate('OpenLP.FormattingTagForm',
                          'The selected formatting tag file is invalid and could not be imported.'))
            return
        if not isinstance(imported_tags, list):
            QtWidgets.QMessageBox.critical(
                self,
                translate('OpenLP.FormattingTagForm', 'Formatting Tag Import Error'),
                translate('OpenLP.FormattingTagForm',
                          'The selected formatting tag file is invalid and could not be imported.'))
            return
        existing_custom_tags = [tag.copy() for tag in FormattingTags.get_html_tags() if not tag.get('protected')]
        self.services.pre_save()
        self.services.custom_tags = existing_custom_tags
        for tag in imported_tags:
            if not isinstance(tag, dict):
                QtWidgets.QMessageBox.critical(
                    self,
                    translate('OpenLP.FormattingTagForm', 'Formatting Tag Import Error'),
                    translate('OpenLP.FormattingTagForm',
                              'The selected formatting tag file is invalid and could not be imported.'))
                return
            if tag.get('protected'):
                continue
            tag_name = tag.get('tag') or self._strip(tag.get('start tag', ''))
            existing_tag_index = -1
            for tag_index, existing_tag in enumerate(self.services.custom_tags):
                existing_tag_name = self._strip(existing_tag.get('start tag', ''))
                if existing_tag_name.casefold() == tag_name.casefold():
                    existing_tag_index = tag_index
                    break
            if existing_tag_index != -1:
                answer = QtWidgets.QMessageBox.question(
                    self,
                    translate('OpenLP.FormattingTagForm', 'Formatting Tag Exists'),
                    translate('OpenLP.FormattingTagForm',
                              'Do you want to overwrite the existing {tag} tag?'
                              '\n\nChoose No to skip importing this tag.').format(tag=tag_name),
                    QtWidgets.QMessageBox.StandardButton(
                        QtWidgets.QMessageBox.StandardButton.Yes |
                        QtWidgets.QMessageBox.StandardButton.No),
                    QtWidgets.QMessageBox.StandardButton.No)
                if answer == QtWidgets.QMessageBox.StandardButton.No:
                    continue
                self.services.custom_tags.pop(existing_tag_index)
            error = self.services.validate_for_save(tag.get('desc', ''),
                                                    tag_name,
                                                    tag.get('start html', ''),
                                                    tag.get('end html', ''),
                                                    bool(tag.get('hidden', False)))
            if error:
                QtWidgets.QMessageBox.warning(self,
                                              translate('OpenLP.FormattingTagForm', 'Validation Error'),
                                              error)
                return
        self.services.save_tags()
        self._reloadTable()
        settings.setValue('formattingTags/last directory import', import_file_path.parent)

    def _reloadTable(self):
        """
        Reset List for loading.
        """
        self.reloading = True
        self.tag_table_widget_read.clearContents()
        self.tag_table_widget_read.setRowCount(0)
        self.tag_table_widget.clearContents()
        self.tag_table_widget.setRowCount(0)
        self.new_button.setEnabled(True)
        self.delete_button.setEnabled(False)
        for line_number, html in enumerate(FormattingTags.get_html_tags()):
            if html['protected']:
                line = self.tag_table_widget_read.rowCount()
                self.tag_table_widget_read.setRowCount(line + 1)
                self.tag_table_widget_read.setItem(line, 0, QtWidgets.QTableWidgetItem(html['desc']))
                self.tag_table_widget_read.setItem(line, 1, QtWidgets.QTableWidgetItem(self._strip(html['start tag'])))
                self.tag_table_widget_read.setItem(line, 2, QtWidgets.QTableWidgetItem(html['start html']))
                self.tag_table_widget_read.setItem(line, 3, QtWidgets.QTableWidgetItem(html['end html']))
                self.tag_table_widget_read.setCellWidget(line, EditColumn.Preview,
                                                         self._build_preview_widget(html['start html'],
                                                                                    html['end html']))
                self.tag_table_widget_read.resizeRowsToContents()
            else:
                line = self.tag_table_widget.rowCount()
                self.tag_table_widget.setRowCount(line + 1)
                self.tag_table_widget.setItem(line, 0, QtWidgets.QTableWidgetItem(html['desc']))
                self.tag_table_widget.setItem(line, 1, QtWidgets.QTableWidgetItem(self._strip(html['start tag'])))
                self.tag_table_widget.setItem(line, 2, QtWidgets.QTableWidgetItem(html['start html']))
                self.tag_table_widget.setItem(line, 3, QtWidgets.QTableWidgetItem(html['end html']))
                self.tag_table_widget.setCellWidget(line, EditColumn.Preview,
                                                    self._build_preview_widget(html['start html'], html['end html']))
                hiddenwidget = QtWidgets.QWidget()
                hiddencheckbox = QtWidgets.QCheckBox()
                hiddenlayout = QtWidgets.QHBoxLayout()
                hiddenlayout.addWidget(hiddencheckbox)
                hiddenlayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                hiddenlayout.setContentsMargins(0, 0, 0, 0)
                hiddenwidget.setLayout(hiddenlayout)
                hiddencheckbox.setCheckState(QtCore.Qt.CheckState.Checked if html['hidden']
                                             else QtCore.Qt.CheckState.Unchecked)
                self.tag_table_widget.setCellWidget(line, EditColumn.Hidden, hiddenwidget)
                self.tag_table_widget.resizeRowsToContents()
                # Permanent (persistent) tags do not have this key
                html['temporary'] = False
        self.reloading = False

    def on_table_item_changed(self, item):
        """
        Process table edits immediately when item content changes.
        """
        if self.reloading:
            return
        if not item:
            return
        row = item.row()
        col = item.column()
        if not self.tag_table_widget.item(row, EditColumn.Description):
            return
        if col not in (EditColumn.Description, EditColumn.Tag, EditColumn.StartHtml, EditColumn.EndHtml):
            return
        text = item.text()
        errors = None
        if col is EditColumn.Description:
            if not text:
                errors = translate('OpenLP.FormattingTagForm', 'Description is missing')
        elif col is EditColumn.Tag:
            if not text:
                errors = translate('OpenLP.FormattingTagForm', 'Tag is missing')
        elif col is EditColumn.StartHtml:
            end_item = self.tag_table_widget.item(row, EditColumn.EndHtml)
            end_html = end_item.text() if end_item else ''
            errors, tag = self.services.start_tag_changed(text, end_html)
            if tag:
                previous_state = self.tag_table_widget.blockSignals(True)
                self.tag_table_widget.setItem(row, EditColumn.EndHtml, QtWidgets.QTableWidgetItem(tag))
                self.tag_table_widget.blockSignals(previous_state)
        elif col is EditColumn.EndHtml:
            start_item = self.tag_table_widget.item(row, EditColumn.StartHtml)
            start_html = start_item.text() if start_item else ''
            errors, tag = self.services.end_tag_changed(start_html, text)
            if tag:
                previous_state = self.tag_table_widget.blockSignals(True)
                self.tag_table_widget.setItem(row, EditColumn.EndHtml, QtWidgets.QTableWidgetItem(tag))
                self.tag_table_widget.blockSignals(previous_state)
        if col is EditColumn.StartHtml or col is EditColumn.EndHtml:
            self._update_preview_cell(row)
        if errors:
            QtWidgets.QMessageBox.warning(self, translate('OpenLP.FormattingTagForm', 'Validation Error'), errors)
        self.tag_table_widget.resizeRowsToContents()
