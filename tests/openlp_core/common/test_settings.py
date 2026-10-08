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
Package to test the openlp.core.lib.settings package.
"""
import pytest
import shutil
import tempfile
from pathlib import Path
from unittest.mock import call, patch

from PySide6 import QtCore

from openlp.core.common import settings as modsettings
from openlp.core.common.platform import is_macosx
from openlp.core.common.settings import Settings, media_players_conv, upgrade_dark_theme_to_ui_theme, \
    check_for_variant_migration
from openlp.core.common.enum import PluginStatus
from openlp.core.ui.style import UiThemes

from tests.utils.constants import RESOURCE_PATH


def test_media_players_conv():
    """Test the media players conversion function"""
    # GIVEN: A list of media players
    media_players = 'phonon,webkit,vlc'

    # WHEN: The media converter function is called
    result = media_players_conv(media_players)

    # THEN: The list should have been converted correctly
    assert result == 'system,webkit,vlc'


def test_default_value(settings):
    """Test reading a setting that doesn't exist yet"""
    # GIVEN: A setting that doesn't exist yet

    # WHEN reading a setting for the first time
    default_value = Settings().value('core/has run wizard')

    # THEN the default value is returned
    assert default_value is False, 'The default value should be False'


def test_save_new_value(settings):
    """Test saving a new setting"""
    # GIVEN: A setting that hasn't been saved yet
    # WHEN a new value is saved into config
    Settings().setValue('core/has run wizard', True)

    # THEN the new value is returned when re-read
    assert Settings().value('core/has run wizard') is True, 'The saved value should have been returned'


def test_set_up_default_values(qapp):
    """Test that the default values are updated"""
    # GIVEN: A Settings object with defaults
    # WHEN: set_up_default_values() is called
    Settings.set_up_default_values()

    # THEN: The default values should have been added to the dictionary
    assert 'advanced/default service name' in Settings.__default_settings__


@pytest.mark.parametrize(('macos', 'families', 'expected'), [
    (True, ['Arial', 'Helvetica Neue', 'Segoe UI'], 'Helvetica Neue'),
    (False, ['Arial', 'Roboto', 'Segoe UI'], 'Segoe UI'),
    (False, ['Arial', 'Roboto'], 'Roboto'),
    (False, ['Noto Sans', 'DejaVu Sans'], 'Noto Sans'),
    (False, ['arial'], 'arial'),
])
def test_default_alert_font_uses_installed_family(macos, families, expected):
    """The default uses the first available sans-serif font, preserving its installed name."""
    with patch.object(modsettings, 'is_macosx', return_value=macos), \
            patch.object(modsettings.QtGui.QFontDatabase, 'families', return_value=families):
        assert modsettings.get_default_alert_font() == expected


def test_default_alert_font_falls_back_to_resolved_sans_serif(qapp):
    """An installation without the preferred fonts still gets a concrete font family."""
    with patch.object(modsettings.QtGui.QFontDatabase, 'families', return_value=[]):
        family = modsettings.get_default_alert_font()
    assert family
    assert family in modsettings.QtGui.QFontDatabase.families()


def test_default_alert_font_preserves_saved_choice(settings):
    """Refreshing startup defaults does not overwrite the user's saved font."""
    settings.setValue('alerts/font face', 'Custom Font')
    with patch.dict(Settings.__default_settings__), \
            patch.object(modsettings, 'get_default_alert_font', return_value='Roboto'):
        Settings.set_up_default_values()
        assert settings.get_default_value('alerts/font face') == 'Roboto'
        assert settings.value('alerts/font face') == 'Custom Font'


def test_get_default_value():
    """Test that the default value for a setting is returned"""
    # GIVEN: A Settings class with a default value
    Settings.__default_settings__['test/moo'] = 'baa'

    # WHEN: get_default_value() is called
    result = Settings().get_default_value('test/moo')

    # THEN: The correct default value should be returned
    assert result == 'baa'


def test_get_default_value_with_group():
    """Test that the default value for a setting is returned"""
    # GIVEN: A Settings class with a default value
    Settings.__default_settings__['test/moo'] = 'baa'

    # WHEN: get_default_value() is called
    settings = Settings()
    settings.beginGroup('test')
    result = settings.get_default_value('moo')

    # THEN: The correct default value should be returned
    assert result == 'baa'


def test_settings_override():
    """Test the Settings creation and its override usage"""
    # GIVEN: an override for the settings
    screen_settings = {
        'test/extend': 'very wide',
    }
    Settings().extend_default_settings(screen_settings)

    # WHEN reading a setting for the first time
    extend = Settings().value('test/extend')

    # THEN the default value is returned
    assert extend == 'very wide', 'The default value of "very wide" should be returned'


def test_save_existing_setting():
    """Test that saving an existing setting returns the new value"""
    # GIVEN: An existing setting
    Settings().extend_default_settings({'test/existing value': None})
    Settings().setValue('test/existing value', 'old value')

    # WHEN a new value is saved into config
    Settings().setValue('test/existing value', 'new value')

    # THEN the new value is returned when re-read
    assert Settings().value('test/existing value') == 'new value', 'The saved value should be returned'


def test_settings_override_with_group():
    """Test the Settings creation and its override usage - with groups"""
    # GIVEN: an override for the settings
    screen_settings = {
        'test/extend': 'very wide',
    }
    Settings.extend_default_settings(screen_settings)

    # WHEN reading a setting for the first time
    settings = Settings()
    extend = settings.value('test/extend')

    # THEN the default value is returned
    assert 'very wide' == extend, 'The default value defined should be returned'

    # WHEN a new value is saved into config
    Settings().setValue('test/extend', 'very short')

    # THEN the new value is returned when re-read
    assert 'very short' == Settings().value('test/extend'), 'The saved value should be returned'


def test_settings_nonexisting():
    """Test the Settings on query for non-existing value"""
    # GIVEN: A new Settings setup
    with pytest.raises(KeyError) as cm:
        # WHEN reading a setting that doesn't exist
        Settings().value('core/does not exists')

    # THEN: An exception with the non-existing key should be thrown
    assert str(cm.value) != KeyError("'core/does not exists'", 'We should get an exception')


def test_extend_default_settings():
    """Test that the extend_default_settings method extends the default settings"""
    # GIVEN: A patched __default_settings__ dictionary
    with patch.dict(Settings.__default_settings__,
                    {'test/setting 1': 1, 'test/setting 2': 2, 'test/setting 3': 3}, True):

        # WHEN: Calling extend_default_settings
        Settings.extend_default_settings({'test/setting 3': 4, 'test/extended 1': 1, 'test/extended 2': 2})

        # THEN: The _default_settings__ dictionary_ should have the new keys
        assert Settings.__default_settings__ == {'test/setting 1': 1, 'test/setting 2': 2, 'test/setting 3': 4,
                                                 'test/extended 1': 1, 'test/extended 2': 2}


@patch('openlp.core.common.settings.QtCore.QSettings.contains')
@patch('openlp.core.common.settings.QtCore.QSettings.value')
@patch('openlp.core.common.settings.QtCore.QSettings.setValue')
@patch('openlp.core.common.settings.QtCore.QSettings.remove')
def test_upgrade_single_setting(mocked_remove, mocked_setValue, mocked_value, mocked_contains):
    """Test that the upgrade mechanism for settings works correctly for single value upgrades"""
    # GIVEN: A settings object with an upgrade step to take (99, so that we don't interfere with real ones)
    local_settings = Settings()
    local_settings.__setting_upgrade_99__ = [
        ('single/value', 'single/new value', [(str, '')])
    ]
    modsettings.__version__ = 99
    mocked_value.side_effect = [98, 10]
    mocked_contains.return_value = True

    # WHEN: upgrade_settings() is called
    local_settings.upgrade_settings()

    # THEN: The correct calls should have been made with the correct values
    assert mocked_value.call_count == 2, 'Settings().value() should have been called twice'
    assert mocked_value.call_args_list == [call('settings/version', 0), call('single/value')]
    assert mocked_setValue.call_count == 2, 'Settings().setValue() should have been called twice'
    assert mocked_setValue.call_args_list == [call('single/new value', '10'), call('settings/version', 99)]
    mocked_contains.assert_called_once_with('single/value')
    mocked_remove.assert_called_once_with('single/value')


@patch('openlp.core.common.settings.QtCore.QSettings.contains')
@patch('openlp.core.common.settings.QtCore.QSettings.value')
@patch('openlp.core.common.settings.QtCore.QSettings.setValue')
@patch('openlp.core.common.settings.QtCore.QSettings.remove')
def test_upgrade_setting_value(mocked_remove, mocked_setValue, mocked_value, mocked_contains):
    """Test that the upgrade mechanism for settings correctly uses the new value when it's not a function"""
    # GIVEN: A settings object with an upgrade step to take (99, so that we don't interfere with real ones)
    local_settings = Settings()
    local_settings.__setting_upgrade_99__ = [
        ('values/old value', 'values/new value', [(True, 1)])
    ]
    modsettings.__version__ = 99
    mocked_value.side_effect = [98, 1]
    mocked_contains.return_value = True

    # WHEN: upgrade_settings() is called
    local_settings.upgrade_settings()

    # THEN: The correct calls should have been made with the correct values
    assert mocked_value.call_count == 2, 'Settings().value() should have been called twice'
    assert mocked_value.call_args_list == [call('settings/version', 0), call('values/old value')]
    assert mocked_setValue.call_count == 2, 'Settings().setValue() should have been called twice'
    assert mocked_setValue.call_args_list == [call('values/new value', True), call('settings/version', 99)]
    mocked_contains.assert_called_once_with('values/old value')
    mocked_remove.assert_called_once_with('values/old value')


@patch('openlp.core.common.settings.QtCore.QSettings.contains')
@patch('openlp.core.common.settings.QtCore.QSettings.value')
@patch('openlp.core.common.settings.QtCore.QSettings.setValue')
@patch('openlp.core.common.settings.QtCore.QSettings.remove')
def test_upgrade_multiple_one_invalid(mocked_remove, mocked_setValue, mocked_value, mocked_contains):
    """Test that the upgrade mechanism for settings works correctly for multiple values where one is invalid"""
    # GIVEN: A settings object with an upgrade step to take
    local_settings = Settings()
    local_settings.__setting_upgrade_99__ = [
        (['multiple/value 1', 'multiple/value 2'], 'single/new value', [])
    ]
    modsettings.__version__ = 99
    mocked_value.side_effect = [98, 10]
    mocked_contains.side_effect = [True, False]

    # WHEN: upgrade_settings() is called
    local_settings.upgrade_settings()

    # THEN: The correct calls should have been made with the correct values
    mocked_value.assert_called_once_with('settings/version', 0)
    mocked_setValue.assert_called_once_with('settings/version', 99)
    assert mocked_contains.call_args_list == [call('multiple/value 1'), call('multiple/value 2')]


def test_from_future(settings):
    """Test the Settings.from_future() method"""
    # GIVEN: A Settings object
    settings.setValue('settings/version', 100)

    # WHEN: from_future() is called
    result = settings.from_future()

    # THEN: The result should be true
    assert result is True, 'The settings should be detected as a newer version'


def test_version_mismatched():
    """Test the Settings.version_mismatched() method"""
    # GIVEN: A Settings object
    local_settings = Settings()

    # WHEN: version_mismatched() is run
    result = local_settings.version_mismatched()

    # THEN: The result should be True
    assert result is True, 'The settings should be upgradeable'


def test_convert_value_setting_none_str():
    """Test the Settings._convert_value() method when a setting is None and the default value is a string"""
    # GIVEN: A settings object
    # WHEN: _convert_value() is run
    result = Settings()._convert_value(None, 'string')

    # THEN: The result should be an empty string
    assert result == '', 'The result should be an empty string'


def test_convert_value_setting_none_list():
    """Test the Settings._convert_value() method when a setting is None and the default value is a list"""
    # GIVEN: A settings object
    # WHEN: _convert_value() is run
    result = Settings()._convert_value(None, [None])

    # THEN: The result should be an empty list
    assert result == [], 'The result should be an empty list'


def test_convert_value_setting_utf8_json():
    """Test the Settings._convert_value() method when a setting is utf8-encoded JSON"""
    # GIVEN: A settings object
    # WHEN: _convert_value() is run
    result = Settings()._convert_value('{"key": "value"}'.encode('utf8'), None)

    # THEN: The result should be a Path object
    assert isinstance(result, dict), 'The result should be a dictionary'


def test_convert_value_setting_json_Path():
    """Test the Settings._convert_value() method when a setting is JSON and represents a Path object"""
    # GIVEN: A settings object
    # WHEN: _convert_value() is run
    result = Settings()._convert_value(
        '{"parts": ["openlp", "core"], "json_meta": {"class": "Path", "version": 1}}', None)

    # THEN: The result should be a Path object
    assert isinstance(result, Path), 'The result should be a Path object'


def test_convert_value_setting_bool_str():
    """Test the Settings._convert_value() method when a setting is supposed to be a boolean"""
    # GIVEN: A settings object
    # WHEN: _convert_value() is run
    result = Settings()._convert_value('false', True)

    # THEN: The result should be False
    assert result is False, 'The result should be False'


def test_upgrade_dark_theme_to_ui_theme_true():
    """Test that the upgrade_dark_theme_to_ui_theme function returns UiTheme.QDarkStyle for True"""
    # GIVEN: The upgrade_dark_theme_to_ui_theme function
    # WHEN: upgrade_dark_theme_to_ui_theme is called with True
    result = upgrade_dark_theme_to_ui_theme(True)

    # THEN: UiTheme.QDarkStyle should be returned
    assert result == UiThemes.QDarkStyle


def test_upgrade_dark_theme_to_ui_theme_false():
    """Test that the upgrade_dark_theme_to_ui_theme function returns UiTheme.Automatic for False"""
    # GIVEN: The upgrade_dark_theme_to_ui_theme function
    # WHEN: upgrade_dark_theme_to_ui_theme is called with False
    result = upgrade_dark_theme_to_ui_theme(False)

    # THEN: UiTheme.QDarkStyle should be returned
    assert result == UiThemes.Automatic


def test_settings_pyqt5_pyside6_migration_ini():
    """Test that an ini file created by PyQt5 can be read by PySide6"""
    # WHEN: The system is using ini configuration
    # GIVEN: an ini file created by PyQt5 loaded by PySide6 (which is used now)
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_ini_file_path = tmpdirname + '/OpenLP-3-1-3.ini'
        shutil.copyfile(str(RESOURCE_PATH / 'settings' / 'OpenLP-3-1-3.ini'), tmp_ini_file_path)

        settings = Settings(tmp_ini_file_path, QtCore.QSettings.IniFormat)
        settings = check_for_variant_migration(settings)

        # THEN: The migration of Variant based entries should be converted correctly (mostly enums)
        value = settings.value('custom/status')
        assert value == PluginStatus.Active


@pytest.mark.skipif(not is_macosx(), reason='This test only works on macOs')
def test_settings_pyqt5_pyside6_migration_plist():
    """Test that an plist file created by PyQt5 can be read by PySide6"""
    # WHEN: The system is mac and therefore using plist format as the native format
    # GIVEN: an plist file created by PyQt5 loaded by PySide6 (which is used now)
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_plist_file_path = tmpdirname + '/org.openlp.OpenLP-3-1-3.plist'
        shutil.copyfile(str(RESOURCE_PATH / 'settings' / 'org.openlp.OpenLP-3-1-3.plist'), tmp_plist_file_path)

        settings = Settings(tmp_plist_file_path, QtCore.QSettings.NativeFormat)
        settings = check_for_variant_migration(settings)

        # THEN: The migration of Variant based entries should be converted correctly (mostly enums)
        value = settings.value('custom/status')
        assert value == PluginStatus.Active


def test_settings_pyqt5_pyside6_migration_ini_missing():
    """Test that the ini migration can handle that there is no existing file"""
    # WHEN: The system is using ini configuration but no ini file already exists
    # GIVEN: an settings instance
    tmp_ini_file_path = str(RESOURCE_PATH / 'settings' / 'files-does-not-exists.ini')
    settings = Settings(tmp_ini_file_path, QtCore.QSettings.IniFormat)
    ret_settings = check_for_variant_migration(settings)

    # THEN: The returned settings object should be the same as the original
    assert settings == ret_settings


def test_settings_zip_export_import(settings, monkeypatch):
    """Test exporting and importing settings using ZIP format"""
    from openlp.core.common import settings as modsettings
    from openlp.core.common.applocation import AppLocation
    original_version = modsettings.__version__
    modsettings.__version__ = 4
    try:
        # GIVEN: A Settings object with custom values
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            monkeypatch.setattr(AppLocation, 'get_data_path', lambda: tmp_dir_path / 'data')
            zip_path = tmp_dir_path / 'backup.zip'
            logo_path = tmp_dir_path / 'my_logo.png'
            # Create a dummy logo file
            logo_path.write_text("dummy image content")

            # Set some custom settings
            settings.setValue('core/ccli number', '12345')
            settings.setValue('core/logo file', logo_path)
            settings.setValue('SettingsImport/type', 'OpenLP_settings_export')
            settings.sync()

            # WHEN: Exporting to ZIP
            settings.export_zip(zip_path)

            # THEN: The ZIP file should exist and contain openlp.conf and the logo
            assert zip_path.exists()
            import zipfile
            with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
                namelist = zip_ref.namelist()
                assert 'openlp.conf' in namelist
                assert 'my_logo.png' in namelist

            # GIVEN: Clear current settings and import from ZIP
            settings.setValue('core/ccli number', '0')
            settings.setValue('core/logo file', Path(':/graphics/openlp-logo-background.svg'))
            settings.sync()

            # WHEN: Importing settings from the ZIP
            success = settings.import_settings(zip_path)

            # THEN: Import should be successful, settings restored, and logo file path updated
            assert success is True
            assert settings.value('core/ccli number') == '12345'
            restored_logo_path = settings.value('core/logo file')
            assert restored_logo_path.name == 'my_logo.png'
            assert restored_logo_path.exists()
    finally:
        modsettings.__version__ = original_version


def test_convert_value_with_enum(settings):
    """Test that _convert_value handles QListView.ViewMode enums correctly"""
    from PySide6.QtWidgets import QListView
    # GIVEN: A settings object and a QListView.ViewMode enum
    # WHEN: Calling _convert_value with int default_value
    val = settings._convert_value(QListView.ViewMode.IconMode, 0)
    # THEN: It should convert correctly to the enum's integer value (1)
    assert val == 1


@pytest.mark.parametrize('plugin', ['Bibles', 'Custom', 'Images', 'Media', 'Presentations', 'Songs'])
def test_upgrade_saved_live_shortcuts(settings, monkeypatch, plugin):
    """Existing broken defaults are repaired when settings are upgraded."""
    from PySide6 import QtGui
    monkeypatch.setattr(modsettings, '__version__', 5)
    key = f'shortcuts/listView{plugin}LiveItem'
    old = [QtGui.QKeySequence(int(QtCore.Qt.Key.Key_Shift) + int(value))
           for value in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)]
    settings.setValue('settings/version', 4)
    settings.setValue(key, old)
    settings.upgrade_settings()
    assert settings.value(key) == [QtGui.QKeySequence('Shift+Return'), QtGui.QKeySequence('Shift+Enter')]


def test_upgrade_preserves_custom_live_shortcut(settings, monkeypatch):
    """Changing defaults does not replace a user's chosen shortcut."""
    from PySide6 import QtGui
    monkeypatch.setattr(modsettings, '__version__', 5)
    custom = [QtGui.QKeySequence('Ctrl+L')]
    settings.setValue('settings/version', 4)
    settings.setValue('shortcuts/listViewImagesLiveItem', custom)
    settings.upgrade_settings()
    assert settings.value('shortcuts/listViewImagesLiveItem') == custom


def test_retired_settings_upgrade(settings, monkeypatch):
    """Cleanup removes retired keys while retaining the recent-file preference."""
    monkeypatch.setattr(modsettings, '__version__', 6)
    settings.setValue('settings/version', 5)
    for key, _, _ in Settings.__setting_upgrade_6__:
        settings.setValue(key, True)
    settings.setValue('advanced/recent file count', 7)
    settings.setValue('core/update check', False)
    settings.setValue('api/update check', True)

    settings.upgrade_settings()

    assert settings.value('settings/version') == 6
    assert all(not settings.contains(key) for key, _, _ in Settings.__setting_upgrade_6__)
    assert settings.value('advanced/recent file count') == 7
    assert settings.value('core/update check') is False
    assert settings.value('api/update check') is True


def test_presentation_and_display_override_upgrade(settings, monkeypatch):
    """Retired overrides are removed without changing enabled controllers or output settings."""
    monkeypatch.setattr(modsettings, '__version__', 7)
    settings.setValue('settings/version', 6)
    for key, _, _ in Settings.__setting_upgrade_7__:
        settings.setValue(key, True)
    settings.setValue('presentations/Powerpoint', QtCore.Qt.CheckState.Checked)
    settings.setValue('advanced/x11 bypass wm', False)

    settings.upgrade_settings()

    assert settings.value('settings/version') == 7
    assert all(not settings.contains(key) for key, _, _ in Settings.__setting_upgrade_7__)
    assert settings.value('presentations/Powerpoint') == QtCore.Qt.CheckState.Checked
    assert settings.value('advanced/x11 bypass wm') is False


def test_service_colours_upgrade(settings, monkeypatch):
    """Remove all retired colour overrides while preserving service settings."""
    monkeypatch.setattr(modsettings, '__version__', 8)
    settings.setValue('settings/version', 7)
    for key, _, _ in Settings.__setting_upgrade_8__:
        settings.setValue(key, '#123456')
    settings.setValue('servicemanager/service theme', 'Sunday')
    settings.setValue('advanced/delete service item confirmation', False)

    settings.upgrade_settings()

    assert settings.value('settings/version') == 8
    assert all(not settings.contains(key) for key, _, _ in Settings.__setting_upgrade_8__)
    assert all(key not in Settings.__default_settings__ for key, _, _ in Settings.__setting_upgrade_8__)
    assert settings.value('servicemanager/service theme') == 'Sunday'
    assert settings.value('advanced/delete service item confirmation') is False
