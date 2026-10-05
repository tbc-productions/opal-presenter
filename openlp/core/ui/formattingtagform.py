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
"""Browse built-in formatting styles and edit custom styles stored as JSON in settings."""
import html
import json
import re

from PySide6 import QtCore, QtGui
from fluentqt import Window as FluentWindow
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.lib.formattingtags import FormattingTags
from openlp.core.ui.formattingtagcontroller import FormattingTagController
from openlp.core.ui.formattingtagdialog import Ui_FormattingTagDialog
from openlp.core.ui.icons import UiIcons
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


class FormattingTagForm(FluentWindow, Ui_FormattingTagDialog, FormattingTagController):
    """Manage a draft of custom styles while keeping built-in styles read-only."""
    accepted = QtCore.Signal()
    rejected = QtCore.Signal()
    finished = QtCore.Signal(int)

    BuiltInTab = 0
    CustomTab = 1

    def __init__(self, parent):
        """
        Constructor
        """
        super().__init__(parent)
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._event_loop = None
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        self.reloading = False
        self._loading_editor = False
        self.setup_ui(self)
        self.escape_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape), self)
        self.escape_shortcut.activated.connect(self.reject)
        self._setup()

    def _setup(self):
        """
        Set up the class. This method is mocked out by the tests.
        """
        self.services = FormattingTagController()
        self.tag_table_widget.itemSelectionChanged.connect(self.on_row_selected)
        self.tag_table_widget_read.itemSelectionChanged.connect(self.on_row_selected)
        self.style_tabs.currentChanged.connect(self.on_row_selected)
        self.search_edit.textChanged.connect(self._filter_styles)
        self.copy_button.triggered.connect(self.on_copy_clicked)
        self.name_edit.textEdited.connect(lambda text: self._on_editor_changed(EditColumn.Description, text))
        self.tag_edit.textEdited.connect(lambda text: self._on_editor_changed(EditColumn.Tag, text))
        self.start_html_edit.textChanged.connect(
            lambda: self._on_editor_changed(EditColumn.StartHtml, self.start_html_edit.toPlainText()))
        self.end_html_edit.textChanged.connect(
            lambda: self._on_editor_changed(EditColumn.EndHtml, self.end_html_edit.toPlainText()))
        self.hidden_checkbox.toggled.connect(self._on_hidden_changed)
        self.new_button.triggered.connect(self.on_new_clicked)
        self.delete_button.triggered.connect(self.on_delete_clicked)
        self.import_button.triggered.connect(self.on_import_clicked)
        self.export_button.triggered.connect(self.on_export_clicked)
        # Forces reloading of tags from openlp configuration.
        FormattingTags.load_tags()
        self.on_row_selected()

    def exec(self):
        """Open the Fluent window with the existing modal save/cancel contract."""
        self.style_tabs.setCurrentIndex(self.BuiltInTab)
        self._reloadTable()
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        loop = QtCore.QEventLoop(self)
        self._event_loop = loop
        try:
            # Apply the opening geometry after content and native window setup.
            self.ensurePolished()
            self.layout().activate()
            self.resize(1160, 780)
            self.show()
            self.raise_()
            self.activateWindow()
            loop.exec()
        finally:
            self._event_loop = None
            loop.deleteLater()
        return self._result

    def result(self):
        return self._result

    def done(self, result):
        """Close the native window and release callers waiting for a result."""
        self._result = result
        self.hide()
        if self._event_loop is not None:
            self._event_loop.quit()
        if result == QtWidgets.QDialog.DialogCode.Accepted:
            self.accepted.emit()
        else:
            self.rejected.emit()
        self.finished.emit(result)

    def reject(self):
        self.done(QtWidgets.QDialog.DialogCode.Rejected)

    def closeEvent(self, event):
        self.reject()
        event.accept()

    def _active_table(self):
        return self.tag_table_widget if self.style_tabs.currentIndex() == self.CustomTab else self.tag_table_widget_read

    def on_row_selected(self):
        """Show the selected style in the detail editor, including read-only built-ins."""
        if self.reloading:
            return
        table = self._active_table()
        row = table.currentRow()
        selected = row >= 0 and not table.isRowHidden(row)
        custom = table is self.tag_table_widget
        self.delete_button.setEnabled(selected and custom)
        self.copy_button.setEnabled(selected)
        self.editor_fields.setEnabled(selected)
        self.editor_fields.setVisible(selected)
        self.preview_card.setVisible(selected)
        self.preview_heading.setVisible(selected)
        self.read_only_icon.setVisible(selected and not custom)
        self._loading_editor = True
        try:
            values = [table.item(row, column).text() if selected else '' for column in range(4)]
            self.name_edit.setText(values[0])
            self.tag_edit.setText(values[1])
            self.start_html_edit.setPlainText(values[2])
            self.end_html_edit.setPlainText(values[3])
            for edit in (self.name_edit, self.tag_edit, self.start_html_edit, self.end_html_edit):
                edit.setReadOnly(not custom)
            hidden = table.cellWidget(row, EditColumn.Hidden) if selected and custom else None
            self.hidden_checkbox.setChecked(hidden.isChecked() if hidden else False)
            self.hidden_checkbox.setEnabled(custom)
            self._auto_end_html = not values[3] or values[3] == self.services.start_html_to_end_html(values[2])
        finally:
            self._loading_editor = False
        if not selected:
            self.editor_heading.setText(translate('OpenLP.FormattingTagForm', 'No style selected'))
        else:
            self.editor_heading.setText(translate('OpenLP.FormattingTagForm', 'Style'))
            self._update_detail_preview()
        self._update_style_counts()

    def _update_style_counts(self):
        tables = (self.tag_table_widget_read, self.tag_table_widget)
        counts = [sum(not table.isRowHidden(row) for row in range(table.rowCount())) for table in tables]
        self.style_tabs.set_match_counts(counts, bool(self.search_edit.text().strip()))

    def _filter_styles(self):
        """Filter both lists without losing edits stored in hidden rows."""
        query = self.search_edit.text().strip().casefold()
        for table in (self.tag_table_widget, self.tag_table_widget_read):
            previous_state = table.blockSignals(True)
            try:
                for row in range(table.rowCount()):
                    matches = any(query in table.item(row, column).text().casefold() for column in (0, 1))
                    table.setRowHidden(row, not matches)
                if table.currentRow() < 0 or table.isRowHidden(table.currentRow()):
                    table.clearSelection()
                    table.setCurrentIndex(QtCore.QModelIndex())
                    for row in range(table.rowCount()):
                        if not table.isRowHidden(row):
                            table.selectRow(row)
                            break
            finally:
                table.blockSignals(previous_state)
        self.on_row_selected()

    def _on_editor_changed(self, column, text):
        """Store edits immediately so changing the selection never discards text."""
        if self._loading_editor or self.reloading or self.style_tabs.currentIndex() != self.CustomTab:
            return
        row = self.tag_table_widget.currentRow()
        if row < 0:
            return
        previous_state = self.tag_table_widget.blockSignals(True)
        try:
            self.tag_table_widget.item(row, column).setText(text)
            if column == EditColumn.EndHtml:
                self._auto_end_html = not text
            if column == EditColumn.StartHtml and self._auto_end_html:
                end = self.services.start_html_to_end_html(text)
                if end is not None:
                    self.tag_table_widget.item(row, EditColumn.EndHtml).setText(end)
                    self._loading_editor = True
                    try:
                        self.end_html_edit.setPlainText(end)
                    finally:
                        self._loading_editor = False
        finally:
            self.tag_table_widget.blockSignals(previous_state)
        if column in (EditColumn.StartHtml, EditColumn.EndHtml):
            self._update_preview_cell(row)
        self._update_detail_preview()

    def _on_hidden_changed(self, checked):
        if self._loading_editor or self.style_tabs.currentIndex() != self.CustomTab:
            return
        row = self.tag_table_widget.currentRow()
        if row >= 0:
            self.tag_table_widget.cellWidget(row, EditColumn.Hidden).setChecked(checked)

    def _update_detail_preview(self):
        start = self._normalize_preview_html(self.start_html_edit.toPlainText(), self.preview_label)
        sample = translate('OpenLP.FormattingTagForm', 'Amazing grace, how sweet the sound')
        self.preview_label.setText('{start}{sample}{end}'.format(
            start=start, sample=html.escape(sample), end=self.end_html_edit.toPlainText()))

    def _append_style(self, desc, tag, start_html, end_html, hidden=False):
        table = self.tag_table_widget
        previous_state = table.blockSignals(True)
        try:
            row = table.rowCount()
            table.insertRow(row)
            for column, value in enumerate((desc, tag, start_html, end_html)):
                table.setItem(row, column, QtWidgets.QTableWidgetItem(value))
            table.setCellWidget(row, EditColumn.Preview, self._build_preview_widget(start_html, end_html))
            checkbox = QtWidgets.QCheckBox(table)
            checkbox.setChecked(hidden)
            table.setCellWidget(row, EditColumn.Hidden, checkbox)
        finally:
            table.blockSignals(previous_state)
        table.resizeRowsToContents()
        return row

    def _unique_new_style(self):
        """Allocate a name and tag that do not collide with any existing style."""
        names, tags = set(), set()
        for table in (self.tag_table_widget, self.tag_table_widget_read):
            for row in range(table.rowCount()):
                names.add(table.item(row, EditColumn.Description).text().casefold())
                tags.add(table.item(row, EditColumn.Tag).text().casefold())
        number = 1
        while True:
            name = translate('OpenLP.FormattingTagForm', 'New style {number}').format(number=number)
            tag = 'style{number}'.format(number=number)
            if name.casefold() not in names and tag.casefold() not in tags:
                return name, tag
            number += 1

    def _select_new_style(self, row):
        self.search_edit.clear()
        self.style_tabs.setCurrentIndex(self.CustomTab)
        self.tag_table_widget.selectRow(row)
        self.tag_table_widget.scrollToItem(self.tag_table_widget.item(row, 0))
        self.on_row_selected()
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def on_new_clicked(self):
        """Create a usable style with valid HTML, ready to name and customise."""
        name, tag = self._unique_new_style()
        self._select_new_style(self._append_style(name, tag, '<span>', '</span>'))

    def on_copy_clicked(self):
        """Copy either a built-in or custom style into an editable custom style."""
        table = self._active_table()
        row = table.currentRow()
        if row < 0 or table.isRowHidden(row):
            return
        original_name = table.item(row, EditColumn.Description).text()
        names = {grid.item(index, EditColumn.Description).text().casefold()
                 for grid in (self.tag_table_widget, self.tag_table_widget_read) for index in range(grid.rowCount())}
        number = 1
        while True:
            name = translate('OpenLP.FormattingTagForm', '{name} (copy {number})').format(
                name=original_name, number=number)
            if name.casefold() not in names:
                break
            number += 1
        _, tag = self._unique_new_style()
        hidden = table.cellWidget(row, EditColumn.Hidden) if table is self.tag_table_widget else None
        new_row = self._append_style(
            name, tag, table.item(row, EditColumn.StartHtml).text(),
            table.item(row, EditColumn.EndHtml).text(), hidden.isChecked() if hidden else False)
        self._select_new_style(new_row)

    def _build_preview_widget(self, start_html, end_html):
        """
        Create a preview label that renders sample text with the provided HTML wrapper.
        """
        preview_widget = QtWidgets.QLabel()
        preview_widget.setWordWrap(True)
        preview_widget.setTextFormat(QtCore.Qt.TextFormat.RichText)
        preview_widget.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        normalized_start_html = self._normalize_preview_html(start_html or '', preview_widget)
        preview_widget.setText('{start}{text}{end}'.format(
            start=normalized_start_html,
            text=html.escape(translate('OpenLP.FormattingTagForm', 'Preview text')),
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
        """Delete the selected custom style; built-in styles remain protected."""
        if self.style_tabs.currentIndex() != self.CustomTab:
            return
        selected = self.tag_table_widget.currentRow()
        if selected != -1:
            self.tag_table_widget.removeRow(selected)
            self._filter_styles()

    def accept(self):
        """
        Update Custom Tag details if not duplicate and save the data.
        """
        if not self._validate_tags_for_save():
            return
        self.services.save_tags()
        self.done(QtWidgets.QDialog.DialogCode.Accepted)

    def _validate_tags_for_save(self):
        """
        Validate the current custom tags in the table and build ``self.services.custom_tags``.
        """
        self.services.pre_save()
        for count in range(self.tag_table_widget.rowCount()):
            desc, tag, start, end = [self.tag_table_widget.item(count, column).text() for column in range(4)]
            if not desc.strip():
                error = translate('OpenLP.FormattingTagForm', 'Enter a name for this style.')
            elif not tag or re.search(r'[{}\s/]', tag):
                error = translate('OpenLP.FormattingTagForm',
                                  'Enter a tag without spaces, braces or slashes, such as emphasis.')
            else:
                error = self.services.validate_for_save(
                    desc, tag, start, end, self.tag_table_widget.cellWidget(count, EditColumn.Hidden).isChecked())
            if error:
                QtWidgets.QMessageBox.warning(self, translate('OpenLP.FormattingTagForm', 'Validation Error'), error)
                self.search_edit.clear()
                self.style_tabs.setCurrentIndex(self.CustomTab)
                self.tag_table_widget.selectRow(count)
                self.on_row_selected()
                return False
        return True

    def on_export_clicked(self):
        """
        Export custom formatting tags to a JSON file.
        """
        if not self.isVisible():
            self._reloadTable()
        if not self._validate_tags_for_save():
            return
        settings = Registry().get('settings')
        try:
            last_export_directory = settings.value('formattingTags/last directory export')
        except KeyError:
            last_export_directory = None
        export_file_path, filter_used = FileDialog.getSaveFileName(
            self,
            translate('OpenLP.FormattingTagForm', 'Export formatting styles'),
            last_export_directory,
            translate('OpenLP.FormattingTagForm', 'OpenLP+ Formatting Styles (*.json)'))
        if not export_file_path:
            return
        export_file_path = export_file_path.with_suffix('.json')
        try:
            with export_file_path.open('w', encoding='utf-8') as exported_tags_file:
                json.dump(self.services.custom_tags, exported_tags_file, indent=2)
        except OSError as ose:
            QtWidgets.QMessageBox.critical(
                self,
                translate('OpenLP.FormattingTagForm', 'Formatting style export error'),
                translate('OpenLP.FormattingTagForm',
                          'An error occurred while exporting formatting styles: {err}').format(err=ose.strerror))
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
            translate('OpenLP.FormattingTagForm', 'Import formatting styles'),
            last_import_directory,
            translate('OpenLP.FormattingTagForm', 'OpenLP+ Formatting Styles (*.json)'))
        if import_file_path is None:
            return
        try:
            with import_file_path.open('r', encoding='utf-8') as imported_tags_file:
                imported_tags = json.load(imported_tags_file)
        except (OSError, ValueError, TypeError):
            QtWidgets.QMessageBox.critical(
                self,
                translate('OpenLP.FormattingTagForm', 'Formatting style import error'),
                translate('OpenLP.FormattingTagForm',
                          'The selected formatting style file is invalid and could not be imported.'))
            return
        if not isinstance(imported_tags, list):
            QtWidgets.QMessageBox.critical(
                self,
                translate('OpenLP.FormattingTagForm', 'Formatting style import error'),
                translate('OpenLP.FormattingTagForm',
                          'The selected formatting style file is invalid and could not be imported.'))
            return
        # Within the editor, imports join the current draft and respect Save/Cancel.
        # The main-window Import action keeps its existing immediate-save behaviour.
        editing = self.isVisible()
        if editing:
            if not self._validate_tags_for_save():
                return
            existing_custom_tags = [tag.copy() for tag in self.services.custom_tags]
        else:
            existing_custom_tags = [tag.copy() for tag in FormattingTags.get_html_tags() if not tag.get('protected')]
        self.services.pre_save()
        self.services.custom_tags = existing_custom_tags
        for tag in imported_tags:
            if not isinstance(tag, dict):
                QtWidgets.QMessageBox.critical(
                    self,
                    translate('OpenLP.FormattingTagForm', 'Formatting style import error'),
                    translate('OpenLP.FormattingTagForm',
                              'The selected formatting style file is invalid and could not be imported.'))
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
                    translate('OpenLP.FormattingTagForm', 'Formatting style exists'),
                    translate('OpenLP.FormattingTagForm',
                              'Do you want to overwrite the existing {tag} style?'
                              '\n\nChoose No to skip importing this style.').format(tag=tag_name),
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
        if editing:
            protected = [tag for tag in FormattingTags.get_html_tags() if tag.get('protected')]
            self._reloadTable(protected + self.services.custom_tags)
        else:
            self.services.save_tags()
            self._reloadTable()
        settings.setValue('formattingTags/last directory import', import_file_path.parent)

    def _reloadTable(self, tags=None):
        """Load the style lists and restore a useful initial selection."""
        self.reloading = True
        try:
            self.tag_table_widget_read.clearContents()
            self.tag_table_widget_read.setRowCount(0)
            self.tag_table_widget.clearContents()
            self.tag_table_widget.setRowCount(0)
            for tag in FormattingTags.get_html_tags() if tags is None else tags:
                if tag['protected']:
                    table = self.tag_table_widget_read
                    row = table.rowCount()
                    table.insertRow(row)
                    for column, value in enumerate((tag['desc'], self._strip(tag['start tag']),
                                                    tag['start html'], tag['end html'])):
                        table.setItem(row, column, QtWidgets.QTableWidgetItem(value))
                    name_item = table.item(row, EditColumn.Description)
                    name_item.setIcon(UiIcons().lock)
                    name_item.setToolTip(translate('OpenLP.FormattingTagDialog', 'Read-only'))
                    table.setCellWidget(row, EditColumn.Preview,
                                        self._build_preview_widget(tag['start html'], tag['end html']))
                else:
                    self._append_style(tag['desc'], self._strip(tag['start tag']), tag['start html'], tag['end html'],
                                       tag.get('hidden', False))
            self.tag_table_widget_read.resizeRowsToContents()
        finally:
            self.reloading = False
        self._filter_styles()
