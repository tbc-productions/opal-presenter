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
Package to test the opal.core.ui.formattingtagsform package.
"""
import json
from pathlib import Path

import pytest
from PySide6 import QtCore
from opal.core.widgets import fluent as QtWidgets
from unittest.mock import MagicMock, patch

from opal.core.lib.formattingtags import FormattingTags
from opal.core.ui.formattingtagform import EditColumn, FormattingTagForm


@pytest.fixture()
def tagform_env(registry):
    setup_patcher = patch('opal.core.ui.formattingtagform.FormattingTagForm._setup')
    mocked_setup_patcher = setup_patcher.start()
    yield mocked_setup_patcher
    setup_patcher.stop()


@pytest.fixture()
def style_form(settings, qtbot):
    """Use real Fluent controls, signals, models and settings for editor interactions."""
    previous_tags = FormattingTags.html_expands
    form = FormattingTagForm(None)
    qtbot.addWidget(form)
    form._reloadTable()
    yield form
    FormattingTags.html_expands = previous_tags


def test_on_row_selected(tagform_env, mock_settings):
    """An empty selection disables actions and hides the read-only indicator."""
    form = FormattingTagForm(None)
    form.on_row_selected()
    assert not form.delete_button.isEnabled()
    assert not form.copy_button.isEnabled()
    assert not form.editor_fields.isEnabled()
    assert form.editor_heading.text() == 'No style selected'
    assert form.read_only_icon.isHidden()


def test_on_new_clicked(style_form):
    """New styles have unique tags and valid HTML and focus the name field."""
    style_form.on_new_clicked()
    style_form.on_new_clicked()
    table = style_form.tag_table_widget
    assert table.rowCount() == 2
    assert table.currentRow() == 1
    assert table.item(0, EditColumn.Tag).text() != table.item(1, EditColumn.Tag).text()
    assert style_form.start_html_edit.toPlainText() == '<span>'
    assert style_form.end_html_edit.toPlainText() == '</span>'
    assert style_form._validate_tags_for_save()


@patch('opal.core.ui.formattingtagform.FileDialog.getSaveFileName')
def test_on_export_clicked_exports_tags(mock_get_save_file_name, tagform_env, mock_settings, tmp_path):
    form = FormattingTagForm(None)
    form.services = MagicMock()
    form.services.custom_tags = [{'desc': 'My Tag'}]
    form._validate_tags_for_save = MagicMock(return_value=True)
    form._reloadTable = MagicMock()
    export_file_path = tmp_path / 'styles.opal-styles'
    mock_get_save_file_name.return_value = export_file_path, ''
    form.on_export_clicked()
    value = json.loads(export_file_path.read_text())
    assert value['format'] == 'opal-presenter'
    assert value['type'] == 'styles'
    assert value['data'] == [{'desc': 'My Tag'}]


@patch('opal.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('opal.core.ui.formattingtagform.FormattingTags.get_html_tags')
@patch('opal.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('opal.core.ui.formattingtagform.json.load')
def test_on_import_clicked_imports_tags(mock_json_load, mock_get_open_file_name, mock_get_html_tags, mock_critical,
                                        tagform_env, mock_settings):
    """
    Test that clicking import reads and saves imported custom tags.
    """
    # GIVEN: A formatting tag form and an import file containing one custom tag
    form = FormattingTagForm(None)
    form.services = MagicMock()
    form.services.validate_for_save.return_value = None
    form._reloadTable = MagicMock()
    mock_get_html_tags.return_value = []
    import_file_path = Path('/tmp/formatting-tags.json')
    mock_get_open_file_name.return_value = import_file_path, ''
    mock_json_load.return_value = [{
        'desc': 'Imported Tag',
        'start tag': '{it}',
        'start html': '<em>',
        'end html': '</em>',
        'hidden': True
    }]

    # WHEN: on_import_clicked is called
    with patch.object(Path, 'open') as mocked_path_open:
        form.on_import_clicked()

    # THEN: The imported tags should be validated and saved
    mocked_path_open.assert_called_once_with('r', encoding='utf-8')
    form.services.pre_save.assert_called_once_with()
    form.services.validate_for_save.assert_called_once_with('Imported Tag', 'it', '<em>', '</em>', True)
    form.services.save_tags.assert_called_once_with()
    form._reloadTable.assert_called_once_with()
    mock_settings.setValue.assert_called_with('formattingTags/last directory import', Path('/tmp'))
    mock_critical.assert_not_called()


@patch('opal.core.ui.formattingtagform.QtWidgets.QMessageBox.question')
@patch('opal.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('opal.core.ui.formattingtagform.FormattingTags.get_html_tags')
@patch('opal.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('opal.core.ui.formattingtagform.json.load')
def test_on_import_clicked_overwrites_existing_tag(mock_json_load, mock_get_open_file_name, mock_get_html_tags,
                                                   mock_critical, mock_question, tagform_env, mock_settings):
    """
    Test that an existing tag with the same name (case-insensitive) can be overwritten.
    """
    # GIVEN: A formatting tag form with an existing custom tag and an imported duplicate by tag name
    form = FormattingTagForm(None)
    form.services = MagicMock()
    form.services.validate_for_save.return_value = None
    form._reloadTable = MagicMock()
    mock_get_html_tags.return_value = [{
        'desc': 'Existing Tag',
        'start tag': '{IT}',
        'start html': '<b>',
        'end tag': '{/IT}',
        'end html': '</b>',
        'protected': False,
        'temporary': False,
        'hidden': False
    }]
    import_file_path = Path('/tmp/formatting-tags.json')
    mock_get_open_file_name.return_value = import_file_path, ''
    mock_json_load.return_value = [{
        'desc': 'Imported Tag',
        'start tag': '{it}',
        'start html': '<em>',
        'end html': '</em>',
        'hidden': True
    }]
    mock_question.return_value = QtWidgets.QMessageBox.StandardButton.Yes

    # WHEN: on_import_clicked is called
    with patch.object(Path, 'open'):
        form.on_import_clicked()

    # THEN: User is prompted and imported tag is validated/saved
    mock_question.assert_called_once()
    form.services.validate_for_save.assert_called_once_with('Imported Tag', 'it', '<em>', '</em>', True)
    form.services.save_tags.assert_called_once_with()
    form._reloadTable.assert_called_once_with()
    mock_critical.assert_not_called()


@patch('opal.core.ui.formattingtagform.QtWidgets.QMessageBox.question')
@patch('opal.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('opal.core.ui.formattingtagform.FormattingTags.get_html_tags')
@patch('opal.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('opal.core.ui.formattingtagform.json.load')
def test_on_import_clicked_skips_existing_tag(mock_json_load, mock_get_open_file_name, mock_get_html_tags,
                                              mock_critical, mock_question, tagform_env, mock_settings):
    """
    Test that choosing skip for a duplicate tag leaves existing tags untouched.
    """
    # GIVEN: A formatting tag form with an existing custom tag and an imported duplicate by tag name
    form = FormattingTagForm(None)
    form.services = MagicMock()
    form.services.validate_for_save.return_value = None
    form._reloadTable = MagicMock()
    mock_get_html_tags.return_value = [{
        'desc': 'Existing Tag',
        'start tag': '{IT}',
        'start html': '<b>',
        'end tag': '{/IT}',
        'end html': '</b>',
        'protected': False,
        'temporary': False,
        'hidden': False
    }]
    import_file_path = Path('/tmp/formatting-tags.json')
    mock_get_open_file_name.return_value = import_file_path, ''
    mock_json_load.return_value = [{
        'desc': 'Imported Tag',
        'start tag': '{it}',
        'start html': '<em>',
        'end html': '</em>',
        'hidden': True
    }]
    mock_question.return_value = QtWidgets.QMessageBox.StandardButton.No

    # WHEN: on_import_clicked is called
    with patch.object(Path, 'open'):
        form.on_import_clicked()

    # THEN: Duplicate tag import is skipped, but existing tags are still saved
    mock_question.assert_called_once()
    form.services.validate_for_save.assert_not_called()
    form.services.save_tags.assert_called_once_with()
    form._reloadTable.assert_called_once_with()
    mock_critical.assert_not_called()


@patch('opal.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('opal.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('opal.core.ui.formattingtagform.json.load')
def test_on_import_clicked_shows_error_on_invalid_file(mock_json_load, mock_get_open_file_name, mock_critical,
                                                       tagform_env, mock_settings):
    """
    Test that an invalid import file structure shows an import error.
    """
    # GIVEN: A formatting tag form and an import file containing invalid data
    form = FormattingTagForm(None)
    form.services = MagicMock()
    import_file_path = Path('/tmp/formatting-tags.json')
    mock_get_open_file_name.return_value = import_file_path, ''
    mock_json_load.return_value = {'invalid': 'structure'}

    # WHEN: on_import_clicked is called
    with patch.object(Path, 'open'):
        form.on_import_clicked()

    # THEN: A critical error should be shown and no save should occur
    mock_critical.assert_called_once()
    form.services.save_tags.assert_not_called()


def test_normalize_preview_html_converts_webkit_color(tagform_env, mock_settings):
    """
    Test that preview normalization converts webkit text fill color to CSS color.
    """
    form = FormattingTagForm(None)
    preview_widget = MagicMock()
    preview_widget.font.return_value.pointSizeF.return_value = 12.0
    html = '<span style="-webkit-text-fill-color:red;">'

    normalized = form._normalize_preview_html(html, preview_widget)

    assert '-webkit-text-fill-color' not in normalized
    assert 'color:red' in normalized


def test_normalize_preview_html_converts_weight_size_and_opacity(tagform_env, mock_settings):
    """
    Test that preview normalization converts unsupported style patterns.
    """
    form = FormattingTagForm(None)
    preview_widget = MagicMock()
    preview_widget.font.return_value.pointSizeF.return_value = 10.0
    color = MagicMock()
    color.isValid.return_value = True
    color.red.return_value = 1
    color.green.return_value = 2
    color.blue.return_value = 3
    preview_widget.palette.return_value.color.return_value = color
    html = '<span style="font-weight:700; font-size:80%; opacity:0.6;">'

    normalized = form._normalize_preview_html(html, preview_widget)

    assert 'font-weight: bold' in normalized
    assert 'font-size: 8.0pt' in normalized
    assert 'opacity:' not in normalized
    assert 'rgba(' in normalized


def test_dialog_uses_fluent_editor_components(style_form):
    """The style browser and text fields are native Fluent controls."""
    import fluentqt
    assert isinstance(style_form, fluentqt.Window)
    assert style_form.windowTitle() == 'Formatting styles'
    assert style_form.titleBar().contentWidget().text() == 'Formatting styles'
    assert [style_form.style_tabs.tabText(index) for index in range(2)] == ['Built-in', 'Custom']
    assert style_form.save_button.text() == 'Save changes'
    assert isinstance(style_form.editor_card, fluentqt.Card)
    assert isinstance(style_form.tag_table_widget, fluentqt.DataGrid)
    assert isinstance(style_form.start_html_edit, fluentqt.TextEdit)
    assert isinstance(style_form.name_edit, fluentqt.LineEdit)
    assert isinstance(style_form.style_tabs._tabs, fluentqt.TabView)
    bar = style_form.style_command_bar
    assert isinstance(bar, fluentqt.CommandBar)
    assert bar.primaryActions() == [style_form.new_button, style_form.copy_button, style_form.delete_button,
                                    style_form.import_button, style_form.export_button]
    assert bar.labelPosition() == fluentqt.CommandBar.LabelPosition.Right
    assert bar.isBackgroundVisible()
    assert bar.isDynamicOverflowEnabled()
    assert style_form.new_button.text() == 'New'
    assert all(action.text() and not action.icon().isNull() for action in bar.primaryActions())
    assert style_form.tag_table_widget.isColumnHidden(EditColumn.StartHtml)
    assert style_form.tag_table_widget.isColumnHidden(EditColumn.EndHtml)


def test_search_badges_count_both_collections(style_form):
    """Badges always show counts, filter both collections and restore totals when cleared."""
    from fluentqt import InfoBadge
    badges = style_form.style_tabs.match_badges
    total_builtins = style_form.tag_table_widget_read.rowCount()
    assert all(isinstance(badge, InfoBadge) and not badge.isHidden() for badge in badges)
    assert [badge.value() for badge in badges] == [total_builtins, 0]
    style_form.search_edit.setText('bold')
    assert [badge.value() for badge in badges] == [1, 0]
    assert all(not badge.isHidden() for badge in badges)
    assert all(badge.displayMode() == InfoBadge.InfoBadgeDisplayMode.Value for badge in badges)
    style_form.on_copy_clicked()
    style_form.search_edit.setText('BOLD')
    assert [badge.value() for badge in badges] == [1, 1]
    style_form.search_edit.setText('no matching style')
    assert [badge.value() for badge in badges] == [0, 0]
    for query in ('', '   '):
        style_form.search_edit.setText(query)
        assert all(not badge.isHidden() for badge in badges)
        assert [badge.value() for badge in badges] == [total_builtins, 1]


def test_fluent_window_opens_with_default_size(settings, qtbot):
    """Constructing before the parent is shown still opens a correctly sized native window."""
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    form = FormattingTagForm(parent)
    qtbot.addWidget(form)
    parent.resize(1280, 900)
    parent.show()
    form.resize(form.minimumSize())
    sizes = []

    def measure_and_close():
        try:
            sizes.append((form.size(), form.windowHandle().size()))
        finally:
            form.reject()

    QtCore.QTimer.singleShot(50, measure_and_close)
    form.exec()
    assert sizes == [(QtCore.QSize(1160, 780), QtCore.QSize(1160, 780))]
    assert form.content_splitter.sizes()[0] > form.content_splitter.sizes()[1]


@pytest.mark.parametrize('action', ['accept', 'reject', 'close', 'escape'])
def test_fluent_window_modal_result_and_default_tab(style_form, settings, qtbot, action):
    """Native window exits preserve modal results and reopen on Built-in with saved data only."""
    opened = []
    finished = []
    closed = []
    style_form.finished.connect(finished.append)
    style_form.style_tabs.setCurrentIndex(style_form.CustomTab)

    def edit_and_finish():
        try:
            opened.append((style_form.isVisible(), style_form.style_tabs.currentIndex()))
            style_form.on_new_clicked()
            if action == 'escape':
                qtbot.keyClick(style_form, QtCore.Qt.Key.Key_Escape)
            else:
                getattr(style_form, action)()
            closed.append(not style_form.isVisible())
        finally:
            if style_form.isVisible():
                style_form.reject()

    QtCore.QTimer.singleShot(50, edit_and_finish)
    result = style_form.exec()
    expected = (QtWidgets.QDialog.DialogCode.Accepted if action == 'accept'
                else QtWidgets.QDialog.DialogCode.Rejected)
    assert result == style_form.result() == expected
    assert finished == [expected]
    assert opened == [(True, style_form.BuiltInTab)]
    assert closed == [True]
    assert not style_form.isVisible()
    assert bool(settings.value('formattingTags/html_tags')) == (action == 'accept')

    QtCore.QTimer.singleShot(50, style_form.reject)
    assert style_form.exec() == QtWidgets.QDialog.DialogCode.Rejected
    assert style_form.style_tabs.currentIndex() == style_form.BuiltInTab
    assert style_form.tag_table_widget.rowCount() == (1 if action == 'accept' else 0)


def test_invalid_save_keeps_fluent_window_open(style_form):
    """An invalid Save leaves the modal window active until the user cancels."""
    stayed_open = []

    def invalid_save_and_cancel():
        try:
            style_form.accept()
            stayed_open.append(style_form.isVisible())
        finally:
            style_form.reject()

    with (patch.object(style_form, '_validate_tags_for_save', return_value=False),
          patch.object(style_form.services, 'save_tags') as save_tags):
        QtCore.QTimer.singleShot(0, invalid_save_and_cancel)
        assert style_form.exec() == QtWidgets.QDialog.DialogCode.Rejected
    assert stayed_open == [True]
    save_tags.assert_not_called()


def test_builtin_styles_are_read_only_and_copyable(style_form):
    """Built-ins cannot be changed or deleted, but copying makes an independent custom style."""
    style_form.style_tabs.setCurrentIndex(style_form.BuiltInTab)
    style_form.search_edit.setText('bold')
    assert style_form.name_edit.text() == 'Bold'
    assert style_form.name_edit.isReadOnly()
    assert style_form.start_html_edit.isReadOnly()
    assert not style_form.delete_button.isEnabled()
    assert style_form.copy_button.isEnabled()
    assert not style_form.read_only_icon.isHidden()
    assert style_form.read_only_icon.toolTip() == 'Read-only'
    row = style_form.tag_table_widget_read.currentRow()
    name_item = style_form.tag_table_widget_read.item(row, EditColumn.Description)
    assert not name_item.icon().isNull()
    assert name_item.toolTip() == 'Read-only'
    built_in_count = style_form.tag_table_widget_read.rowCount()
    style_form.on_delete_clicked()
    assert style_form.tag_table_widget_read.rowCount() == built_in_count
    style_form.on_copy_clicked()
    assert style_form.style_tabs.currentIndex() == style_form.CustomTab
    assert style_form.search_edit.text() == ''
    assert not style_form.name_edit.isReadOnly()
    assert style_form.read_only_icon.isHidden()
    assert style_form.start_html_edit.toPlainText() == '<strong>'
    assert style_form.end_html_edit.toPlainText() == '</strong>'
    assert style_form.tag_edit.text() != 'st'
    assert style_form._validate_tags_for_save()


def test_command_bar_actions_are_connected(style_form, qtbot):
    """Clicking native CommandBar presenters performs the style actions."""
    from PySide6 import QtCore
    style_form.show()

    def presenter(action):
        return next(widget for widget in style_form.style_command_bar.findChildren(QtWidgets.QWidget)
                    if widget.property('commandAction') is action and widget.isVisible())

    qtbot.mouseClick(presenter(style_form.new_button), QtCore.Qt.MouseButton.LeftButton)
    assert style_form.tag_table_widget.rowCount() == 1
    qtbot.mouseClick(presenter(style_form.copy_button), QtCore.Qt.MouseButton.LeftButton)
    assert style_form.tag_table_widget.rowCount() == 2
    qtbot.mouseClick(presenter(style_form.delete_button), QtCore.Qt.MouseButton.LeftButton)
    assert style_form.tag_table_widget.rowCount() == 1


def test_command_bar_overflow_keeps_import_export_accessible_on_one_row(style_form, qtbot):
    """Narrow command bars overflow transfer actions without adding a second row."""
    from PySide6 import QtCore
    style_form.show()
    bar = style_form.style_command_bar
    row_height = bar.height()
    bar.setFixedWidth(260)
    transfer_actions = (style_form.import_button, style_form.export_button)
    qtbot.waitUntil(lambda: all(bar.isPrimaryActionOverflowed(action) for action in transfer_actions))
    assert bar.height() == row_height
    presenters = [widget for widget in bar.findChildren(QtWidgets.QWidget)
                  if widget.parentWidget() is bar and widget.isVisible() and widget.property('commandAction')]
    assert len({widget.y() for widget in presenters}) == 1
    with (
        patch('opal.core.ui.formattingtagform.FileDialog.getOpenFileName', return_value=(None, '')) as import_file,
        patch('opal.core.ui.formattingtagform.FileDialog.getSaveFileName', return_value=(None, '')) as export_file
    ):
        for action, picker in ((style_form.import_button, import_file), (style_form.export_button, export_file)):
            bar.setOverflowOpen(True)
            popup = style_form.window().findChild(QtWidgets.QWidget, 'FluentCommandBar.OverflowPopup')
            assert popup.isVisible()
            command = next(widget for widget in popup.findChildren(QtWidgets.QWidget)
                           if widget.objectName() == 'FluentCommandBar.OverflowRow'
                           and widget.property('commandAction') is action)
            qtbot.mouseClick(command, QtCore.Qt.MouseButton.LeftButton)
            picker.assert_called_once()
            qtbot.waitUntil(lambda: not bar.isOverflowOpen())


def test_editor_changes_survive_selection_and_filtering(style_form, qtbot):
    """Typing edits the draft immediately; searching and selecting do not discard it."""
    style_form.on_new_clicked()
    qtbot.keyClicks(style_form.name_edit, 'Emphasis')
    style_form.start_html_edit.setPlainText('<em>')
    assert style_form.end_html_edit.toPlainText() == '</em>'
    assert '<em>' in style_form.preview_label.text()
    style_form.hidden_checkbox.setChecked(True)
    style_form.on_new_clicked()
    style_form.search_edit.setText('EMPHASIS')
    assert style_form.tag_table_widget.isRowHidden(1)
    assert style_form.name_edit.text() == 'Emphasis'
    assert style_form.start_html_edit.toPlainText() == '<em>'
    assert style_form.hidden_checkbox.isChecked()
    assert style_form._validate_tags_for_save()
    assert len(style_form.services.custom_tags) == 2
    assert style_form.services.custom_tags[0]['hidden'] is True


def test_custom_closing_html_is_preserved(style_form):
    """Automatic closing HTML must not overwrite a deliberate custom ending."""
    style_form.on_new_clicked()
    style_form.end_html_edit.setPlainText('</span> footer')
    style_form.start_html_edit.setPlainText('<span style="color: red;">')
    assert style_form.end_html_edit.toPlainText() == '</span> footer'
    assert style_form.tag_table_widget.item(0, EditColumn.EndHtml).text() == '</span> footer'


def test_no_search_results_disable_actions_and_can_recover(style_form):
    """A filtered-out selection is not editable or copyable; clearing search restores it."""
    style_form.on_new_clicked()
    style_form.search_edit.setText('no such style')
    assert not style_form.editor_fields.isEnabled()
    assert not style_form.delete_button.isEnabled()
    assert not style_form.copy_button.isEnabled()
    assert style_form.tag_table_widget.currentRow() == -1
    assert style_form.style_tabs.match_badges[style_form.CustomTab].value() == 0
    style_form.search_edit.clear()
    assert style_form.tag_table_widget.currentRow() == 0
    assert style_form.delete_button.isEnabled()
    style_form.on_delete_clicked()
    assert style_form.tag_table_widget.rowCount() == 0
    assert not style_form.delete_button.isEnabled()


def test_save_reveals_invalid_filtered_style(style_form):
    """Validation includes filtered styles and brings the failing row back into view."""
    style_form.on_new_clicked()
    style_form.tag_table_widget.item(0, EditColumn.Tag).setText('bad tag')
    style_form.search_edit.setText('not found')
    with patch('opal.core.ui.formattingtagform.QtWidgets.QMessageBox.warning') as warning:
        assert not style_form._validate_tags_for_save()
    warning.assert_called_once()
    assert style_form.search_edit.text() == ''
    assert style_form.tag_table_widget.currentRow() == 0
    assert style_form.tag_edit.text() == 'bad tag'


def test_cancel_discards_draft_and_save_persists_it(style_form, settings):
    """Only Save writes drafts, and reopening always reloads the saved styles."""
    style_form.on_new_clicked()
    style_form.reject()
    assert settings.value('formattingTags/html_tags') == ''
    style_form._reloadTable()
    assert style_form.tag_table_widget.rowCount() == 0
    style_form.on_new_clicked()
    style_form.hidden_checkbox.setChecked(True)
    style_form.accept()
    saved = json.loads(settings.value('formattingTags/html_tags'))
    assert len(saved) == 1
    assert saved[0]['start tag'] == '{style1}'
    assert saved[0]['hidden'] is True


def test_import_in_dialog_preserves_draft_and_respects_cancel(style_form, settings, tmp_path, qtbot):
    """Imports merge into unsaved edits, and Cancel leaves stored styles untouched."""
    imported = tmp_path / 'styles.json'
    imported.write_text(json.dumps([{
        'desc': 'Imported', 'start tag': '{imp}', 'start html': '<em>', 'end html': '</em>', 'hidden': False
    }]))
    style_form.on_new_clicked()
    qtbot.keyClicks(style_form.name_edit, 'Unsaved')
    style_form.show()
    with patch('opal.core.ui.formattingtagform.FileDialog.getOpenFileName', return_value=(imported, '')):
        style_form.on_import_clicked()
    assert style_form.tag_table_widget.rowCount() == 2
    assert style_form.tag_table_widget.item(0, EditColumn.Description).text() == 'Unsaved'
    assert style_form.tag_table_widget.item(1, EditColumn.Description).text() == 'Imported'
    assert settings.value('formattingTags/html_tags') == ''
    style_form.reject()
    style_form._reloadTable()
    assert style_form.tag_table_widget.rowCount() == 0


def test_main_window_export_uses_saved_styles_not_stale_draft(style_form, settings, tmp_path):
    """Export invoked outside the dialog reloads saved styles before exporting."""
    style_form.on_new_clicked()
    style_form.accept()
    style_form.on_new_clicked()
    exported = tmp_path / 'styles.opal-styles'
    with patch('opal.core.ui.formattingtagform.FileDialog.getSaveFileName', return_value=(exported, '')):
        style_form.on_export_clicked()
    assert len(json.loads(exported.read_text())['data']) == 1
    assert len(json.loads(settings.value('formattingTags/html_tags'))) == 1
