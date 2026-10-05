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
Package to test the openlp.core.ui.thememanager package.
"""
import pytest
import os
import shutil
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import ANY, Mock, MagicMock, patch, call, sentinel

from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.core.lib.theme import Theme
from openlp.core.ui.thememanager import ThemeManager
from openlp.core.widgets.themeviews import ThemeViews
from tests.utils.constants import RESOURCE_PATH


@pytest.fixture()
def theme_manager(registry: Registry, settings: Settings) -> ThemeManager:
    registry.register('main_window', None)
    thm = ThemeManager()
    return thm


@patch('openlp.core.ui.thememanager.zipfile.ZipFile.__init__')
@patch('openlp.core.ui.thememanager.zipfile.ZipFile.write')
def test_export_theme(mocked_zipfile_write: MagicMock, mocked_zipfile_init: MagicMock, theme_manager: ThemeManager):
    """
    Test exporting a theme .
    """
    # GIVEN: A new ThemeManager instance.
    theme_manager.theme_path = RESOURCE_PATH / 'themes'
    mocked_zipfile_init.return_value = None

    # WHEN: The theme is exported
    theme_manager._export_theme(Path('some', 'path', 'Default.otz'), 'Default')

    # THEN: The zipfile should be created at the given path
    mocked_zipfile_init.assert_called_with(Path('some', 'path', 'Default.otz'), 'w')
    mocked_zipfile_write.assert_called_with(RESOURCE_PATH / 'themes' / 'Default' / 'Default.xml',
                                            Path('Default', 'Default.xml'))


def test_initial_theme_manager(theme_manager: ThemeManager):
    """
    Test the instantiation of theme manager.
    """
    # GIVEN: A new service manager instance.
    # WHEN: the default theme manager is built.
    # THEN: The the controller should be registered in the registry.
    assert Registry().get('theme_manager') is not None, 'The base theme manager should be registered'


def test_screen_changed_updates_thumbnails_and_preview(theme_manager: ThemeManager):
    """
    Test that screen changes refresh theme thumbnails and the open edit preview.
    """
    # GIVEN: A theme manager with cached themes and mock refresh hooks
    theme_one = MagicMock()
    theme_two = MagicMock()
    theme_manager._theme_list = {'theme1': theme_one, 'theme2': theme_two}
    theme_manager._thumbnail_dimensions = MagicMock()
    theme_manager._get_current_screen = MagicMock(return_value=None)
    theme_manager._get_screen_dimensions = MagicMock(return_value='different-size')
    theme_manager._thumbnail_refresh_worker = None
    theme_manager.update_preview_images = MagicMock()
    theme_manager.get_theme_names = MagicMock(return_value=['theme1', 'theme2'])
    theme_manager.theme_form = MagicMock()

    # WHEN: The screen changes
    theme_manager.screen_changed()

    # THEN: Cached theme defaults should be recalculated and previews refreshed
    theme_one.set_default_header_footer.assert_called_once_with()
    theme_two.set_default_header_footer.assert_called_once_with()
    theme_manager.update_preview_images.assert_called_once_with(['theme1', 'theme2'], show_status=False)
    theme_manager.theme_form.refresh_preview.assert_called_once_with()


def test_screen_changed_skips_thumbnail_refresh_when_dimensions_match(theme_manager: ThemeManager):
    """
    Test that screen changes do not refresh thumbnails when the screen dimensions are unchanged.
    """
    # GIVEN: A theme manager with cached themes and matching dimensions
    theme_one = MagicMock()
    theme_manager._theme_list = {'theme1': theme_one}
    theme_manager._thumbnail_dimensions = 'same-size'
    theme_manager._get_current_screen = MagicMock(return_value=None)
    theme_manager._get_screen_dimensions = MagicMock(return_value='same-size')
    theme_manager._regenerate_previews_with_progress_dialog = MagicMock()
    theme_manager.theme_form = MagicMock()

    # WHEN: The screen changes
    theme_manager.screen_changed()

    # THEN: The theme defaults should still be updated, but thumbnails should not be rebuilt
    theme_one.set_default_header_footer.assert_called_once_with()
    theme_manager._regenerate_previews_with_progress_dialog.assert_not_called()
    theme_manager.theme_form.refresh_preview.assert_called_once_with()


@patch('openlp.core.ui.thememanager.Theme')
def test_get_global_theme(mocked_theme: MagicMock, theme_manager: ThemeManager):
    """
    Test the global theme method returns the theme data for the global theme
    """
    # GIVEN: A service manager instance and the global theme
    theme_manager.global_theme = 'global theme name'
    theme_manager._theme_list = {'global theme name': sentinel.global_theme}

    # WHEN: Calling get_global_theme
    result = theme_manager.get_global_theme()

    # THEN: Returned global theme
    assert result == sentinel.global_theme


@patch('openlp.core.ui.thememanager.Theme')
def test_get_theme_data(mocked_theme: MagicMock, theme_manager: ThemeManager):
    """
    Test that the get theme data method returns the requested theme data
    """
    # GIVEN: A service manager instance and themes
    theme_manager._theme_list = {'theme1': sentinel.theme1, 'theme2': sentinel.theme2}

    # WHEN: Get theme data is called with 'theme2'
    result = theme_manager.get_theme_data('theme2')

    # THEN: Should return theme2's data
    assert result == sentinel.theme2


@patch('openlp.core.ui.thememanager.Theme')
def test_get_theme_data_missing(mocked_theme: MagicMock, theme_manager: ThemeManager):
    """
    Test that the get theme data method returns the default theme when theme name not found
    """
    # GIVEN: A service manager instance and themes
    theme_manager._theme_list = {'theme1': sentinel.theme1, 'theme2': sentinel.theme2}
    mocked_theme.return_value = sentinel.default_theme

    # WHEN: Get theme data is called with None
    result = theme_manager.get_theme_data(None)

    # THEN: Should return default theme's data
    assert result == sentinel.default_theme


@patch('openlp.core.ui.thememanager.shutil')
@patch('openlp.core.ui.thememanager.create_paths')
def test_save_theme_same_image(mocked_create_paths: MagicMock, mocked_shutil: MagicMock, theme_manager: ThemeManager):
    """
    Test that we don't try to overwrite a theme background image with itself
    """
    # GIVEN: A new theme manager instance, with mocked builtins.open, copyfile,
    #        theme, create_paths, thememanager-attributes and background
    #       .filename path is the same as the source path.
    theme_manager.old_background_image_path = None
    theme_manager.update_preview_images = MagicMock()
    theme_manager.theme_path = MagicMock()
    mocked_theme = MagicMock()
    mocked_theme.theme_name = 'themename'
    mocked_theme.extract_formatted_xml = MagicMock()
    mocked_theme.extract_formatted_xml.return_value = 'fake_theme_xml'.encode()
    file_path_1 = RESOURCE_PATH / 'church.jpg'
    mocked_theme.background_filename = file_path_1
    mocked_theme.background_source = file_path_1

    # WHEN: Calling save_theme with both background paths to the same image
    theme_manager.save_theme(mocked_theme)

    # THEN: The mocked_copyfile should not have been called
    assert mocked_shutil.copyfile.called is False, 'copyfile should not be called'


@patch('openlp.core.ui.thememanager.shutil')
@patch('openlp.core.ui.thememanager.create_paths')
def test_save_theme_diff_images(mocked_create_paths, mocked_shutil, theme_manager: ThemeManager):
    """
    Test that we do overwrite a theme background image when a new is submitted
    """
    # GIVEN: A new theme manager instance, with mocked builtins.open, copyfile,
    #        theme, create_paths, thememanager-attributes and background
    #       .filename path is the same as the source path.
    theme_manager.old_background_image_path = None
    theme_manager.update_preview_images = MagicMock()
    theme_manager.theme_path = MagicMock()
    mocked_theme = MagicMock()
    mocked_theme.theme_name = 'themename'
    mocked_theme.background_filename = RESOURCE_PATH / 'church.jpg'
    mocked_theme.background_source = RESOURCE_PATH / 'church2.jpg'

    # WHEN: Calling save_theme with both background paths to different images
    theme_manager.save_theme(mocked_theme)

    # THEN: The mocked_copyfile should have been called
    assert mocked_shutil.copyfile.called is True, 'copyfile should be called'


@patch('openlp.core.ui.thememanager.shutil')
@patch('openlp.core.ui.thememanager.delete_file')
@patch('openlp.core.ui.thememanager.create_paths')
def test_save_theme_delete_old_image(mocked_create_paths, mocked_del_file, mocked_shutil, theme_manager: ThemeManager):
    """
    Test that we do delete a old theme background image when a new is submitted
    """
    # GIVEN: A new theme manager instance, with mocked builtins.open,
    #        theme, create_paths, thememanager-attributes and background
    #       .filename path is the same as the source path.
    theme_manager.old_background_image_path = RESOURCE_PATH / 'old_church.png'
    theme_manager.update_preview_images = MagicMock()
    theme_manager.theme_path = MagicMock()
    mocked_theme = MagicMock()
    mocked_theme.theme_name = 'themename'
    mocked_theme.background_filename = RESOURCE_PATH / 'church.jpg'
    mocked_theme.background_source = RESOURCE_PATH / 'church2.jpg'

    # WHEN: Calling save_theme with both background paths to different images
    theme_manager.save_theme(mocked_theme)

    # THEN: The mocked_delete_file should have been called to delete the old cached background
    assert mocked_del_file.called is True, 'delete_file should be called'


@patch.object(ThemeManager, 'log_exception')
@patch('openlp.core.ui.thememanager.delete_file')
@patch('openlp.core.ui.thememanager.create_paths')
def test_save_theme_missing_original(mocked_paths, mocked_delete, mocked_log_exception, theme_manager: ThemeManager):
    """
    Test that we revert to the old theme background image if the source is missing
    when changing the theme. (User doesn't change background but the original is
    missing)
    """
    # GIVEN: A new theme manager instance, with invalid files. Setup as if the user
    # has left the background the same, or reselected the same path.
    # Not using resource dir because I could potentially copy a file
    folder_path = Path(mkdtemp())
    theme_manager.old_background_image_path = folder_path / 'old.png'
    theme_manager.update_preview_images = MagicMock()
    theme_manager.theme_path = MagicMock()
    mocked_theme = MagicMock()
    mocked_theme.theme_name = 'themename'
    mocked_theme.background_filename = folder_path / 'old.png'
    mocked_theme.background_source = folder_path / 'non_existent_original.png'

    # WHEN: Calling save_theme with a invalid background_filename
    # Although all filenames are considered invalid in this test,
    # it is important it reverts to the old background path as this in reality is always
    # valid unless someone has messed with the cache.
    theme_manager.save_theme(mocked_theme)

    # THEN: The old background should not have bee deleted
    #       AND the filename should have been replaced with the old cached background
    #       AND there is no exception
    assert mocked_delete.called is False, 'delete_file should not be called'
    assert mocked_theme.background_filename == theme_manager.old_background_image_path, \
        'Background path should be reverted'
    assert mocked_log_exception.called is False, \
        'Should not have been an exception as the file wasn\'t changed'


@patch.object(ThemeManager, 'log_warning')
@patch('openlp.core.ui.thememanager.delete_file')
@patch('openlp.core.ui.thememanager.create_paths')
def test_save_theme_missing_new(mocked_paths, mocked_delete, mocked_log_warning, theme_manager: ThemeManager):
    """
    Test that we log a warning if the new background is missing
    """
    # GIVEN: A new theme manager instance, with invalid files. Setup as if the user
    # has changed the background to a invalid path.
    # Not using resource dir because I could potentially copy a file
    folder_path = Path(mkdtemp())
    theme_manager.old_background_image_path = folder_path / 'old.png'
    theme_manager.update_preview_images = MagicMock()
    theme_manager.theme_path = MagicMock()
    mocked_theme = MagicMock()
    mocked_theme.theme_name = 'themename'
    mocked_theme.background_filename = folder_path / 'new_cached.png'
    mocked_theme.background_source = folder_path / 'new_original.png'

    # WHEN: Calling save_theme with a invalid background_filename
    theme_manager.save_theme(mocked_theme)

    # THEN: A warning should have happened due to attempting to copy a missing file
    mocked_log_warning.assert_called_once_with('Background source does not exist, retaining cached background')


@patch('openlp.core.ui.thememanager.shutil')
@patch('openlp.core.ui.thememanager.delete_file')
@patch('openlp.core.ui.thememanager.create_paths')
def test_save_theme_background_override(mocked_paths, mocked_delete, mocked_shutil, theme_manager: ThemeManager):
    """
    Test that we log a warning if the new background is missing
    """
    # GIVEN: A new theme manager instance, with invalid files. Setup as if the user
    # has changed the background to a invalid path.
    # Not using resource dir because I could potentially copy a file
    folder_path = Path(mkdtemp())
    theme_manager.old_background_image_path = folder_path / 'old.png'
    theme_manager.update_preview_images = MagicMock()
    theme_manager.theme_path = MagicMock()
    mocked_theme = MagicMock()
    mocked_theme.theme_name = 'themename'
    mocked_theme.background_filename = folder_path / 'new_cached.png'
    # mocked_theme.background_source.exists() will return True
    mocked_theme.background_source = MagicMock()
    # override_background.exists() will return True
    override_background = MagicMock()

    # WHEN: Calling save_theme with a background override
    theme_manager.save_theme(mocked_theme, background_file=override_background)

    # THEN: The override_background should have been copied rather than the background_source
    mocked_shutil.copyfile.assert_called_once_with(override_background, mocked_theme.background_filename)


def test_save_theme_special_char_name(registry, temp_folder, theme_manager: ThemeManager):
    """
    Test that we can save themes with special characters in the name
    """
    # GIVEN: A new theme manager instance, with mocked theme and thememanager-attributes.
    theme_manager.old_background_image_path = None
    theme_manager.update_preview_images = MagicMock()
    theme_manager.theme_path = Path(temp_folder)
    mocked_theme = MagicMock()
    mocked_theme.theme_name = 'theme 愛 name'
    mocked_theme.export_theme.return_value = "{}"

    # WHEN: Calling save_theme with a theme with a name with special characters in it
    theme_manager.save_theme(mocked_theme)

    # THEN: It should have been created
    assert os.path.exists(os.path.join(temp_folder, 'theme 愛 name', 'theme 愛 name.json')) is True, \
        'Theme with special characters should have been created!'


@patch('openlp.core.ui.thememanager.QtWidgets.QMessageBox.question',
       return_value=QtWidgets.QMessageBox.StandardButton.Yes)
@patch('openlp.core.ui.thememanager.translate')
def test_over_write_message_box_yes(mocked_translate, mocked_qmessagebox_question, theme_manager: ThemeManager):
    """
    Test that theme_manager.over_write_message_box returns True when the user clicks yes.
    """
    # GIVEN: A patched QMessageBox.question and an instance of ThemeManager
    mocked_translate.side_effect = lambda context, text: text

    # WHEN: Calling over_write_message_box with 'Theme Name'
    result = theme_manager.over_write_message_box('Theme Name')

    # THEN: over_write_message_box should return True and the message box should contain the theme name
    assert result is True
    mocked_qmessagebox_question.assert_called_once_with(
        theme_manager, 'Theme Already Exists', 'Theme Theme Name already exists. Do you want to replace it?',
        defaultButton=ANY)


@patch('openlp.core.ui.thememanager.QtWidgets.QMessageBox.question',
       return_value=QtWidgets.QMessageBox.StandardButton.No)
@patch('openlp.core.ui.thememanager.translate')
def test_over_write_message_box_no(mocked_translate, mocked_qmessagebox_question, theme_manager: ThemeManager):
    """
    Test that theme_manager.over_write_message_box returns False when the user clicks no.
    """
    # GIVEN: A patched QMessageBox.question and an instance of ThemeManager
    mocked_translate.side_effect = lambda context, text: text

    # WHEN: Calling over_write_message_box with 'Theme Name'
    result = theme_manager.over_write_message_box('Theme Name')

    # THEN: over_write_message_box should return False and the message box should contain the theme name
    assert result is False
    mocked_qmessagebox_question.assert_called_once_with(
        theme_manager, 'Theme Already Exists', 'Theme Theme Name already exists. Do you want to replace it?',
        defaultButton=ANY)


@patch('openlp.core.lib.theme.Theme.set_default_header_footer')
def test_unzip_theme(mocked_theme_set_defaults, theme_manager: ThemeManager):
    """
    Test that unzipping of themes works
    """
    # GIVEN: A theme file, a output folder and some mocked out internal functions
    with patch('openlp.core.ui.thememanager.critical_error_message_box') \
            as mocked_critical_error_message_box:
        theme_manager.update_preview_images = MagicMock()
        theme_manager.theme_path = Path(mkdtemp())
        theme_file_path = RESOURCE_PATH / 'themes' / 'Moss_on_tree.otz'

        # WHEN: We try to unzip it
        ret_theme_name = theme_manager.unzip_theme(theme_file_path)

        # THEN: Files should be unpacked AND xml file should be upgraded to json
        assert (theme_manager.theme_path / 'Moss on tree' / 'Moss on tree.xml').exists() is False
        assert (theme_manager.theme_path / 'Moss on tree' / 'Moss on tree.json').exists() is True
        assert mocked_critical_error_message_box.call_count == 0, 'No errors should have happened'
        assert ret_theme_name == "Moss on tree", "The theme name should have been returned"
        shutil.rmtree(theme_manager.theme_path)


def test_unzip_theme_invalid_version(theme_manager: ThemeManager):
    """
    Test that themes with invalid (< 2.0) or with no version attributes are rejected
    """
    # GIVEN: An instance of ThemeManager whilst mocking a theme that returns a theme with no version attribute
    with patch('openlp.core.ui.thememanager.zipfile.ZipFile') as mocked_zip_file, \
            patch('openlp.core.ui.thememanager.ElementTree.getroot') as mocked_getroot, \
            patch('openlp.core.ui.thememanager.XML'), \
            patch('openlp.core.ui.thememanager.critical_error_message_box') as mocked_critical_error_message_box:

        mocked_zip_file.return_value = MagicMock(**{'namelist.return_value': [os.path.join('theme', 'theme.xml')]})
        mocked_getroot.return_value = MagicMock(**{'get.return_value': None})
        theme_manager.theme_path = Path('folder')

        # WHEN: unzip_theme is called
        ret_theme_name = theme_manager.unzip_theme(Path('theme.file'))

        # THEN: The critical_error_message_box should have been called
        assert mocked_critical_error_message_box.call_count == 1, 'Should have been called once'
        assert ret_theme_name is None, 'No theme name should have been returned'


def test_update_preview_images(theme_manager: ThemeManager):
    """
    Test that the update_preview_images() method starts the thumbnail worker.
    """
    # GIVEN: A ThemeManager and a fake worker
    theme_manager.get_theme_names = MagicMock(return_value=['Default', 'Test'])
    worker = MagicMock()
    worker.thumbnail_requested = MagicMock()
    worker.thumbnail_requested.connect = MagicMock()
    worker.status_changed = MagicMock()
    worker.status_changed.connect = MagicMock()
    worker.finished = MagicMock()
    worker.finished.connect = MagicMock()
    worker.quit = MagicMock()
    worker.quit.emit = MagicMock()

    with patch('openlp.core.ui.thememanager.ThemeThumbnailRefreshWorker', return_value=worker) as mocked_worker, \
            patch('openlp.core.ui.thememanager.run_thread') as mocked_run_thread:

        # WHEN: ThemeManager.update_preview_images() is called
        theme_manager.update_preview_images()

    # THEN: The worker should be started and connected correctly
    mocked_worker.assert_called_once_with(['Default', 'Test'])
    worker.finished.connect.assert_called_once_with(worker.quit.emit)
    mocked_run_thread.assert_called_once_with(worker, 'theme_thumbnail_refresh', queued_connections=[
        (worker.thumbnail_requested, theme_manager._refresh_thumbnail_for_theme),
        (worker.status_changed, theme_manager._set_thumbnail_status)
    ], on_finished=theme_manager._thumbnail_refresh_finished)


def test_thumbnail_refresh_waits_for_thread_cleanup(theme_manager, qtbot):
    """A screen change during thumbnail rendering queues a refresh after the old thread is removed."""
    from PySide6 import QtCore

    theme_manager._theme_list = {'Default': MagicMock()}
    theme_manager.get_theme_names = MagicMock(return_value=['Default'])
    theme_manager.load_themes = MagicMock()
    render_threads = []

    def render(_theme, _force):
        render_threads.append(QtCore.QThread.currentThread())
        if len(render_threads) == 1:
            theme_manager.update_preview_images()
            theme_manager.update_preview_images()

    theme_manager._get_theme_data = MagicMock()
    theme_manager.generate_image = render
    theme_manager.update_preview_images()
    qtbot.waitUntil(lambda: theme_manager._thumbnail_refresh_worker is None, timeout=5000)

    assert len(render_threads) == 2
    assert all(thread == theme_manager.thread() for thread in render_threads)
    assert 'theme_thumbnail_refresh' not in Registry().get('application').worker_threads
    theme_manager.load_themes.assert_called_once_with()


def test_theme_manager_initialise(theme_manager):
    """
    Test the thememanager initialise - basic test
    """
    # GIVEN: A new a call to initialise
    theme_manager.setup_ui = MagicMock()
    theme_manager.build_theme_path = MagicMock()
    Settings().setValue('themes/global theme', 'my_theme')

    # WHEN: the initialisation is run
    theme_manager.bootstrap_initialise()

    # THEN:
    theme_manager.setup_ui.assert_called_once_with(theme_manager)
    assert theme_manager.global_theme == 'my_theme'
    theme_manager.build_theme_path.assert_called_once_with()


@patch('openlp.core.ui.thememanager.create_paths')
@patch('openlp.core.ui.thememanager.AppLocation.get_section_data_path')
def test_build_theme_path(mocked_get_section_data_path, mocked_create_paths, theme_manager):
    """
    Test the thememanager build_theme_path
    """
    # GIVEN: A mocked out AppLocation.get_directory() and mocked create_paths
    mocked_get_section_data_path.return_value = Path('tests/my_theme')

    # WHEN: the build_theme_path is run
    theme_manager.build_theme_path()

    #  THEN: The theme path and the thumb path should be correct
    assert theme_manager.theme_path == Path('tests/my_theme')
    assert theme_manager.thumb_path == Path('tests/my_theme/thumbnails')
    mocked_create_paths.assert_called_once_with(Path('tests/my_theme'), Path('tests/my_theme/thumbnails'))


def test_click_on_new_theme(theme_manager):
    """
    Test the on_add_theme event handler is called by the UI
    """
    # GIVEN: An initial form
    Settings().setValue('themes/global theme', 'my_theme')
    mocked_event = MagicMock()
    theme_manager.on_add_theme = mocked_event
    theme_manager.setup_ui(theme_manager)

    # WHEN displaying the UI and pressing cancel
    new_theme = theme_manager.toolbar.actions_map['newTheme']
    new_theme.trigger()

    assert mocked_event.call_count == 1, 'The on_add_theme method should have been called once'


@patch('openlp.core.ui.themeform.ThemeForm._setup')
@patch('openlp.core.ui.filerenameform.FileRenameForm._setup')
def test_bootstrap_post(mocked_rename_form, mocked_theme_form, theme_manager):
    """
    Test the functions of bootstrap_post_setup are called.
    """
    # GIVEN:
    theme_manager.toolbar = MagicMock()
    theme_manager.theme_path = MagicMock()
    theme_manager.load_themes = MagicMock()
    theme_manager.upgrade_themes = MagicMock()
    theme_manager._get_screen_dimensions = MagicMock(return_value='screen-size')
    theme_manager._get_current_screen = MagicMock(return_value=None)
    theme_manager._get_themes_requiring_preview_refresh = MagicMock(return_value=[])
    theme_manager._regenerate_previews_with_progress_dialog = MagicMock()

    # WHEN:
    theme_manager.bootstrap_post_set_up()

    # THEN:
    assert theme_manager.theme_form is not None
    assert theme_manager.file_rename_form is not None
    assert theme_manager._thumbnail_dimensions == 'screen-size'
    theme_manager.upgrade_themes.assert_called_once()
    theme_manager.load_themes.assert_called_once()
    theme_manager._regenerate_previews_with_progress_dialog.assert_not_called()


@patch('openlp.core.lib.theme.Theme.set_default_header')
@patch('openlp.core.lib.theme.Theme.set_default_footer')
def test_clone_theme_data(mock_set_default_header, mock_set_default_footer, theme_manager):
    """Test that cloning the theme data works correctly"""
    # GIVEN: A theme manager, a theme (without a background source) and a new theme name
    existing_theme = Theme()
    existing_theme.theme_name = 'Existing Theme'
    existing_theme.background_type = 'image'
    existing_theme.background_filename = Path('Existing Theme', 'background.jpg')

    theme_manager.theme_path = Path('openlp', 'themes')
    theme_manager.save_theme = MagicMock()
    theme_manager.update_preview_images = MagicMock()
    theme_manager.load_themes = MagicMock()

    # WHEN: The theme is cloned
    theme_manager.clone_theme_data(existing_theme, 'New Theme')

    # THEN: The theme data should have been updated
    assert existing_theme.theme_name == 'New Theme'
    theme_manager.save_theme.assert_called_once_with(existing_theme, background_file=Path('Existing Theme',
                                                                                          'background.jpg'))
    theme_manager.update_preview_images.assert_called_once_with(['New Theme'])
    theme_manager.load_themes.assert_called_once_with()


@pytest.mark.parametrize('view_mode', [QtWidgets.QListView.ViewMode.ListMode, QtWidgets.QListView.ViewMode.IconMode])
@patch('openlp.core.lib.theme.Theme.set_default_header_footer')
def test_copy_theme_during_thumbnail_refresh_has_no_duplicates(mock_defaults, theme_manager, tmp_path, view_mode):
    """Finishing a thumbnail refresh during copying must not overlap theme-list reloads."""
    from PySide6 import QtCore, QtGui

    theme_manager.theme_path = tmp_path
    theme_manager.thumb_path = tmp_path / 'thumbnails'
    theme_manager.global_theme = 'Original'
    theme_manager.theme_list_widget = ThemeViews(theme_manager)
    theme_manager.theme_list_widget.setViewMode(view_mode)
    theme_manager.update_preview_images = MagicMock()
    theme_manager.save_preview = MagicMock()
    theme_manager._push_themes = MagicMock()
    theme_manager.file_rename_form = MagicMock()
    theme_manager.file_rename_form.file_name_edit.text.return_value = 'Copy of Original'
    theme = Theme()
    theme.theme_name = 'Original'
    theme_manager.save_theme(theme)
    refresh_finished = True

    def generate_preview(*args):
        nonlocal refresh_finished
        refresh_finished = True
        # Preview rendering processes UI events, including worker completion.
        theme_manager._thumbnail_refresh_finished()
        return QtGui.QPixmap(10, 10)

    def find_theme_files(*args):
        return [path.relative_to(tmp_path) for path in tmp_path.glob('*/*.json')]

    theme_manager.generate_image = MagicMock(side_effect=generate_preview)
    with patch('openlp.core.ui.thememanager.AppLocation.get_files',
               side_effect=find_theme_files) as get_files, \
            patch('openlp.core.ui.thememanager.validate_thumb', side_effect=lambda *args: refresh_finished), \
            patch('openlp.core.ui.thememanager.build_icon', return_value=QtGui.QIcon()):
        theme_manager.load_themes()
        theme_manager.theme_list_widget.setCurrentRow(0)
        refresh_finished = False

        theme_manager.on_copy_theme()

    # The worker's reload request is handled after the active reload finishes.
    assert get_files.call_count == 3
    view = theme_manager.theme_list_widget
    assert [view.item(row).data(QtCore.Qt.ItemDataRole.UserRole) for row in range(view.count())] == [
        'Copy of Original', 'Original'
    ]
    assert view.list_view.model().rowCount() == view.grid_view.model().rowCount() == 2
    assert theme_manager.get_theme_names() == ['Copy of Original', 'Original']
    assert (tmp_path / 'Original' / 'Original.json').exists()
    assert (tmp_path / 'Copy of Original' / 'Copy of Original.json').exists()


def test_load_themes_can_retry_after_error(theme_manager, tmp_path):
    """A failed theme load must not prevent later refreshes."""
    from PySide6 import QtGui

    (tmp_path / 'Original.json').write_text('{}')
    theme_manager.theme_path = tmp_path
    theme_manager.thumb_path = tmp_path
    theme_manager.global_theme = 'Original'
    theme_manager.theme_list_widget = ThemeViews(theme_manager)
    theme_manager._get_theme_data = MagicMock(side_effect=[ValueError('Invalid theme'), sentinel.original_theme])
    theme_manager._push_themes = MagicMock()
    with patch('openlp.core.ui.thememanager.AppLocation.get_files', return_value=[Path('Original.json')]), \
            patch('openlp.core.ui.thememanager.validate_thumb', return_value=True), \
            patch('openlp.core.ui.thememanager.build_icon', return_value=QtGui.QIcon()):
        with pytest.raises(ValueError, match='Invalid theme'):
            theme_manager.load_themes()
        theme_manager.load_themes()

    assert theme_manager.theme_list_widget.count() == 1
    assert theme_manager.get_theme_names() == ['Original']
    theme_manager._push_themes.assert_called_once_with()


@patch('openlp.core.ui.thememanager.State')
@patch('openlp.core.ui.thememanager.QtWidgets.QMessageBox.question',
       return_value=QtWidgets.QMessageBox.StandardButton.Yes)
def test_on_delete_theme_deletes_selected_themes(mocked_question: MagicMock, mocked_state: MagicMock,
                                                 theme_manager: ThemeManager):
    """
    Test that deleting themes removes all selected themes.
    """
    # GIVEN: Multiple selected theme items
    mocked_state.return_value.list_plugins.return_value = []
    item_1 = MagicMock()
    item_1.text.return_value = 'Theme 1'
    item_1.data.return_value = 'Theme 1'
    item_2 = MagicMock()
    item_2.text.return_value = 'Theme 2'
    item_2.data.return_value = 'Theme 2'
    theme_manager.theme_list_widget = MagicMock()
    theme_manager.theme_list_widget.selectedItems.return_value = [item_1, item_2]
    theme_manager.theme_list_widget.row.side_effect = lambda item: {item_1: 1, item_2: 3}[item]
    theme_manager.delete_theme = MagicMock()
    theme_manager._push_themes = MagicMock()

    # WHEN: The delete action is triggered
    theme_manager.on_delete_theme()

    # THEN: All selected items should be deleted
    mocked_question.assert_called_once()
    assert mocked_question.call_args.args[2] == 'Delete 2 selected themes?'
    assert theme_manager.theme_list_widget.takeItem.call_args_list == [call(3), call(1)]
    assert theme_manager.delete_theme.call_args_list == [call('Theme 2'), call('Theme 1')]
    theme_manager._push_themes.assert_called_once_with()


@patch('openlp.core.ui.thememanager.critical_error_message_box')
def test_on_delete_theme_blocks_default_theme(mocked_critical: MagicMock, theme_manager: ThemeManager):
    """
    Test that deleting the default theme is blocked.
    """
    # GIVEN: The selected item is the default theme
    item = MagicMock()
    item.text.return_value = 'Theme 1 (default)'
    item.data.return_value = 'Theme 1'
    theme_manager.theme_list_widget = MagicMock()
    theme_manager.theme_list_widget.selectedItems.return_value = [item]
    theme_manager.delete_theme = MagicMock()
    theme_manager._push_themes = MagicMock()

    # WHEN: The delete action is triggered
    theme_manager.on_delete_theme()

    # THEN: Deletion should be blocked
    mocked_critical.assert_called_once_with(message='You are unable to delete the default theme.')
    theme_manager.delete_theme.assert_not_called()
    theme_manager._push_themes.assert_not_called()


def test_load_themes_progress_counts_existing_files(theme_manager, tmp_path):
    """Theme progress advances after loading, excludes missing files and then resets."""
    from PySide6 import QtGui

    for name in ('a.json', 'b.json'):
        (tmp_path / name).write_text('{}')
    theme_manager.theme_path = tmp_path
    theme_manager.thumb_path = tmp_path
    theme_manager.global_theme = 'a'
    theme_manager.theme_list_widget = MagicMock()
    theme_manager._get_theme_data = MagicMock()
    theme_manager._push_themes = MagicMock()
    updates = []

    def report(*args, **kwargs):
        assert kwargs == ({'progress_range': (75, 90)} if len(args) > 1 else {})
        updates.append((args, list(theme_manager._theme_list)))

    Registry().register_function('startup_progress', report)
    with patch('openlp.core.ui.thememanager.AppLocation.get_files',
               return_value=[Path('b.json'), Path('missing.json'), Path('a.json')]), \
            patch('openlp.core.ui.thememanager.validate_thumb', return_value=True), \
            patch('openlp.core.ui.thememanager.build_icon', return_value=QtGui.QIcon()):
        theme_manager.load_themes()

    assert updates == [
        (('Loading themes', 0, 2), []),
        (('Loading themes', 1, 2), ['a']),
        (('Loading themes', 2, 2), ['a', 'b']),
        (('Loading library and themes',), ['a', 'b'])
    ]
    theme_manager._push_themes.assert_called_once_with()
