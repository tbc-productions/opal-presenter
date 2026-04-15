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
Package to test the openlp.core.ui.advancedtab package.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6 import QtWidgets

from openlp.core.ui.advancedtab import AdvancedTab
from openlp.core.ui.settingsform import SettingsForm


def test_creation(settings):
    """
    Test that Advanced Tab is created.
    """
    # GIVEN: A new Advanced Tab
    settings_form = SettingsForm(None)

    # WHEN: I create an advanced tab
    advanced_tab = AdvancedTab(settings_form)

    # THEN:
    assert "Advanced" == advanced_tab.tab_title, 'The tab title should be Advanced'


@patch('openlp.core.ui.advancedtab.QtWidgets.QProgressDialog')
@patch('openlp.core.ui.advancedtab.QtWidgets.QMessageBox.information')
@patch('openlp.core.ui.advancedtab.QtWidgets.QMessageBox.question')
@patch('openlp.core.ui.advancedtab.copy2')
@patch('openlp.core.ui.advancedtab.create_paths')
@patch('openlp.core.ui.advancedtab.sha256_file_hash')
@patch('openlp.core.ui.advancedtab.AppLocation.get_section_data_path')
def test_migrate_library_files_button_copies_files(mocked_get_section_data_path: MagicMock,
                                                   mocked_sha256_file_hash: MagicMock,
                                                   mocked_create_paths: MagicMock,
                                                   mocked_copy2: MagicMock,
                                                   mocked_question: MagicMock,
                                                   mocked_information: MagicMock,
                                                   mocked_progress_dialog: MagicMock,
                                                   settings, tmp_path):
    """
    Test that clicking migrate copies files and updates library item paths.
    """
    settings_form = SettingsForm(None)
    advanced_tab = AdvancedTab(settings_form)
    source_file = tmp_path / 'movie.mp4'
    source_file.write_bytes(b'media')
    managed_root = tmp_path / 'managed'
    mocked_get_section_data_path.return_value = managed_root
    mocked_sha256_file_hash.return_value = 'abc123'
    mocked_question.return_value = QtWidgets.QMessageBox.StandardButton.Yes
    progress = MagicMock()
    progress.wasCanceled.side_effect = [False, False]
    mocked_progress_dialog.return_value = progress
    manager = MagicMock()
    item = MagicMock(file_path=str(source_file), file_hash=None)
    advanced_tab._collect_library_migration_candidates = MagicMock(
        return_value=[('media', manager, item, Path(source_file))]
    )

    advanced_tab.on_migrate_library_files_button_clicked()

    expected_path = managed_root / 'library' / 'abc123.mp4'
    mocked_create_paths.assert_called_once_with(managed_root / 'library')
    mocked_copy2.assert_called_once_with(source_file, expected_path)
    assert item.file_path == str(expected_path)
    assert item.file_hash == 'abc123'
    manager.save_object.assert_called_once_with(item)
    assert mocked_information.call_count == 1
