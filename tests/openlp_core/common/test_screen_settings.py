"""Screen-change reminders navigate safely to the Screens preferences page."""
from unittest.mock import MagicMock, patch

import pytest

from opal.core.common.screen_settings import request_screen_configuration, show_screen_setup_message
from opal.core.widgets import fluent


@pytest.mark.parametrize('configure', [False, True])
def test_screen_setup_dialog_secondary_action(qapp, configure):
    def choose_action(dialog):
        assert dialog.primaryButtonText() == 'OK'
        assert dialog.secondaryButtonText() == 'Configure screens'
        assert dialog.defaultButton() == fluent.fluentqt.ContentDialogButton.Primary
        return dialog.ResultSecondary if configure else dialog.ResultPrimary

    with patch.object(fluent.fluentqt.ContentDialog, 'exec', new=choose_action):
        assert show_screen_setup_message(None, 'Screens changed', 'Screen setup has changed.') is configure


def test_screen_configuration_opens_screens_after_current_event(qapp, registry):
    settings_form = MagicMock()
    registry.register('settings_form', settings_form)
    with patch('opal.core.common.screen_settings.QtCore.QTimer.singleShot') as timer:
        request_screen_configuration()
    settings_form.exec.assert_not_called()
    delay, callback = timer.call_args.args
    assert delay == 0
    callback()
    settings_form.exec.assert_called_once_with('Screens')


def test_startup_screen_configuration_waits_for_settings_form(qapp, registry):
    later_startup_listener = MagicMock()
    with patch('opal.core.common.screen_settings.QtCore.QTimer.singleShot') as timer:
        request_screen_configuration()
        request_screen_configuration()
        timer.assert_not_called()
        registry.register_function('bootstrap_completion', later_startup_listener)
        settings_form = MagicMock()
        registry.register('settings_form', settings_form)
        registry.execute('bootstrap_completion')
        later_startup_listener.assert_called_once()
        timer.assert_called_once()
        settings_form.exec.assert_not_called()
        timer.call_args.args[1]()
    settings_form.exec.assert_called_once_with('Screens')
    assert registry.functions_list['bootstrap_completion'] == [later_startup_listener]
