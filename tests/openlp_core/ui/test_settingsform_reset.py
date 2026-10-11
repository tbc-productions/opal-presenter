"""Tests for resetting preferences from the settings dialog."""
from unittest.mock import MagicMock, patch

from opal.core.widgets import fluent as QtWidgets

from opal.core.common.registry import Registry
from opal.core.ui.settingsform import SettingsForm


def test_reset_to_defaults_cancel_keeps_saved_settings(settings):
    form = SettingsForm()
    settings.setValue('core/ccli number', '12345')

    with patch.object(QtWidgets.QMessageBox, 'warning',
                      return_value=QtWidgets.QMessageBox.StandardButton.Cancel):
        form.reset_defaults_button.click()

    assert settings.value('core/ccli number') == '12345'
    assert settings.contains('core/ccli number')


def test_reset_to_defaults_keeps_library_location_and_setup_state(settings, tmp_path):
    form = SettingsForm()
    main_window = MagicMock()
    Registry().register('main_window', main_window)
    library_path = tmp_path / 'library'
    settings.setValue('advanced/data path', library_path)
    settings.setValue('advanced/is portable', True)
    settings.setValue('core/has run wizard', True)
    settings.setValue('settings/version', 4)
    settings.setValue('core/application version', '3.2.8')
    settings.setValue('songs/status', 1)
    settings.setValue('bibles/status', 1)
    settings.setValue('librarysync/status', 0)
    settings.setValue('removedplugin/status', 0)
    settings.setValue('core/ccli number', '12345')
    settings.setValue('songs/update service on edit', False)
    settings.setValue('custom/plugin preference', 'saved')
    form.register_post_process('theme_update_list')

    with patch.object(QtWidgets.QMessageBox, 'warning',
                      return_value=QtWidgets.QMessageBox.StandardButton.Reset), \
            patch('opal.core.ui.settingsform.show_restart_message') as information:
        form.reset_defaults_button.click()

    assert settings.value('advanced/data path') == library_path
    assert settings.value('advanced/is portable') is True
    assert settings.value('core/has run wizard') is True
    assert settings.value('settings/version') == 4
    assert settings.value('core/application version') == '3.2.8'
    assert settings.value('songs/status') == 1
    assert settings.value('bibles/status') == 1
    assert settings.value('librarysync/status') == 0
    assert not settings.contains('removedplugin/status')
    assert settings.value('core/ccli number') == ''
    assert settings.value('songs/update service on edit') is True
    assert not settings.contains('custom/plugin preference')
    assert not form.processes
    assert main_window.settings_replaced is True
    information.assert_called_once()
