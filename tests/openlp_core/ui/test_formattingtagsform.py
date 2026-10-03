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
Package to test the openlp.core.ui.formattingtagsform package.
"""
from pathlib import Path

import pytest
from openlp.core.widgets import fluent as QtWidgets
from unittest.mock import MagicMock, call, patch

from openlp.core.ui.formattingtagform import FormattingTagForm


@pytest.fixture()
def tagform_env(registry):
    setup_patcher = patch('openlp.core.ui.formattingtagform.FormattingTagForm._setup')
    mocked_setup_patcher = setup_patcher.start()
    yield mocked_setup_patcher
    setup_patcher.stop()


def test_on_row_selected(tagform_env, mock_settings):
    """
    Test that the appropriate actions are preformed when on_row_selected is called
    """
    # GIVEN: An instance of the Formatting Tag Form and a mocked delete_button
    form = FormattingTagForm(None)
    form.delete_button = MagicMock()

    # WHEN: on_row_selected is called
    form.on_row_selected()

    # THEN: setEnabled and should have been called on delete_button
    form.delete_button.setEnabled.assert_called_with(True)


def test_on_new_clicked(tagform_env, mock_settings):
    """
    Test that clicking the Add a new tag button does the right thing
    """

    # GIVEN: A formatting tag form and a mocked out tag table widget
    form = FormattingTagForm(None)
    form.tag_table_widget = MagicMock()
    row_count = 5
    form.tag_table_widget.rowCount.return_value = row_count

    # WHEN: on_new_clicked is run (i.e. the Add new button was clicked)
    with patch('openlp.core.ui.formattingtagform.QtWidgets.QTableWidgetItem') as MockedQTableWidgetItem:
        mockedwidget = patch('openlp.core.ui.formattingtagform.QtWidgets.QWidget')
        mocked_table_widget = MagicMock()
        mocked_widget = MagicMock()
        MockedQTableWidgetItem.return_value = mocked_table_widget
        mockedwidget.return_value = mocked_widget
        form.on_new_clicked()

        # THEN: A new row should be added to the table
        form.tag_table_widget.rowCount.assert_called_with()
        form.tag_table_widget.insertRow.assert_called_with(row_count)
        expected_set_item_calls = [
            call(row_count, 0, mocked_table_widget),
            call(row_count, 1, mocked_table_widget),
            call(row_count, 2, mocked_table_widget),
            call(row_count, 3, mocked_table_widget)
        ]
        assert expected_set_item_calls == form.tag_table_widget.setItem.call_args_list, \
            'setItem should have been called correctly'
        form.tag_table_widget.resizeRowsToContents.assert_called_with()
        form.tag_table_widget.scrollToBottom.assert_called_with()
        form.tag_table_widget.selectRow.assert_called_with(row_count)


@patch('openlp.core.ui.formattingtagform.FileDialog.getSaveFileName')
@patch('openlp.core.ui.formattingtagform.json.dump')
def test_on_export_clicked_exports_tags(mock_json_dump, mock_get_save_file_name, tagform_env, mock_settings):
    """
    Test that clicking export writes custom tags to a JSON file.
    """
    # GIVEN: A formatting tag form with valid custom tags
    form = FormattingTagForm(None)
    form.services = MagicMock()
    form.services.custom_tags = [{'desc': 'My Tag'}]
    form._validate_tags_for_save = MagicMock(return_value=True)
    export_file_path = Path('/tmp/formatting-tags')
    mock_get_save_file_name.return_value = export_file_path, ''

    # WHEN: on_export_clicked is called
    with patch.object(Path, 'open') as mocked_path_open:
        form.on_export_clicked()

    # THEN: The selected path should be used with a .json suffix and tag data should be written
    mocked_path_open.assert_called_once_with('w', encoding='utf-8')
    mock_json_dump.assert_called_once_with(form.services.custom_tags, mocked_path_open().__enter__(), indent=2)
    mock_settings.setValue.assert_called_with('formattingTags/last directory export', Path('/tmp'))


@patch('openlp.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('openlp.core.ui.formattingtagform.FormattingTags.get_html_tags')
@patch('openlp.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('openlp.core.ui.formattingtagform.json.load')
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


@patch('openlp.core.ui.formattingtagform.QtWidgets.QMessageBox.question')
@patch('openlp.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('openlp.core.ui.formattingtagform.FormattingTags.get_html_tags')
@patch('openlp.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('openlp.core.ui.formattingtagform.json.load')
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


@patch('openlp.core.ui.formattingtagform.QtWidgets.QMessageBox.question')
@patch('openlp.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('openlp.core.ui.formattingtagform.FormattingTags.get_html_tags')
@patch('openlp.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('openlp.core.ui.formattingtagform.json.load')
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


@patch('openlp.core.ui.formattingtagform.QtWidgets.QMessageBox.critical')
@patch('openlp.core.ui.formattingtagform.FileDialog.getOpenFileName')
@patch('openlp.core.ui.formattingtagform.json.load')
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
