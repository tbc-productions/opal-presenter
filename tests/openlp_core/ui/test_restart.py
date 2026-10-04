"""Restart reminders use the normal close flow and relaunch after releasing locks."""
from contextlib import nullcontext
import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

from openlp.core.app import OpenLP
from openlp.core.common.registry import Registry
from openlp.core.common.restart import show_restart_message
from openlp.core.ui.mainwindow import MainWindow
from openlp.core.widgets import fluent


@pytest.mark.parametrize('restart', [False, True])
def test_restart_reminder_has_secondary_action(qapp, registry, restart):
    application = MagicMock()
    registry.register('application', application)

    def choose_action(dialog):
        assert dialog.primaryButtonText() == 'OK'
        assert dialog.secondaryButtonText() == 'Restart OpenLP+'
        assert dialog.defaultButton() == fluent.fluentqt.ContentDialogButton.Primary
        return dialog.ResultSecondary if restart else dialog.ResultPrimary

    with patch.object(fluent.fluentqt.ContentDialog, 'exec', new=choose_action), \
            patch.object(QtCore.QTimer, 'singleShot') as timer:
        show_restart_message(None, 'Restart required', 'Restart to apply the change.')

    if restart:
        timer.assert_called_once_with(0, application.request_restart)
    else:
        timer.assert_not_called()


@pytest.mark.parametrize(('answer', 'save_succeeds', 'restarts'), [
    (fluent.QMessageBox.StandardButton.Save, True, True),
    (fluent.QMessageBox.StandardButton.Save, False, False),
    (fluent.QMessageBox.StandardButton.Discard, True, True),
    (fluent.QMessageBox.StandardButton.Cancel, True, False),
])
def test_restart_respects_unsaved_service_prompt(settings, qtbot, answer, save_succeeds, restarts):
    class Window(QtWidgets.QWidget):
        closeEvent = MainWindow.closeEvent

    window = Window()
    qtbot.addWidget(window)
    application = OpenLP()
    application.is_event_loop_active = True
    window.application = application
    window.settings = settings
    window.settings_replaced = True
    window.service_manager_contents = MagicMock()
    window.service_manager_contents.is_modified.return_value = True
    window.service_manager_contents.save_modified_service.return_value = answer
    window.service_manager_contents.decide_save_method.return_value = save_succeeds
    window._show_wait_dialog = MagicMock(return_value=nullcontext())
    window._wait_for_threads = MagicMock()
    window.clean_up = MagicMock()
    Registry().register('main_window', window)

    with patch.object(QtCore.QCoreApplication, 'quit') as quit_app:
        application.request_restart()

    window.service_manager_contents.save_modified_service.assert_called_once()
    assert application.restart_requested is restarts
    assert quit_app.called is restarts
    if restarts:
        window.clean_up.assert_called_once_with(save_settings=False)
    else:
        window.clean_up.assert_not_called()


@pytest.mark.parametrize('restart', [False, True])
def test_restart_releases_locks_before_relaunch(qapp, restart):
    application = OpenLP()
    application.restart_requested = restart
    events = []
    application.data_dir_lock = MagicMock()
    application.data_dir_lock.release.side_effect = lambda: events.append('lock released')
    application.server = MagicMock()
    application.server.close_server.side_effect = lambda: events.append('server closed')
    with patch.object(QtWidgets.QApplication, 'exec', return_value=0), \
            patch.object(application, '_restart_process', side_effect=lambda: events.append('relaunch')):
        assert application.exec() == 0
    assert events == ['lock released', 'server closed'] + (['relaunch'] if restart else [])


@pytest.mark.parametrize('frozen', [False, True])
def test_restart_relaunch_command(qapp, frozen):
    with patch('openlp.core.app.sys') as sys_mock, \
            patch('openlp.core.app.os.getcwd', return_value='/working directory'), \
            patch('openlp.core.app.QtCore.QProcess') as process_class:
        process = process_class.return_value
        process.startDetached.return_value = True
        sys_mock.frozen = frozen
        sys_mock.executable = '/path with spaces/openlp'
        sys_mock.argv = ['openlp', '--portable']
        sys_mock.orig_argv = ['python', '-m', 'openlp', '--portable']
        OpenLP()._restart_process()
    arguments = ['--portable'] if frozen else ['-m', 'openlp', '--portable']
    process.setProgram.assert_called_once_with('/path with spaces/openlp')
    process.setArguments.assert_called_once_with(arguments)
    process.setWorkingDirectory.assert_called_once_with('/working directory')
    environment = process.setProcessEnvironment.call_args.args[0]
    if frozen:
        assert environment.value('PYINSTALLER_RESET_ENVIRONMENT') == '1'
    process.startDetached.assert_called_once_with()


def test_restart_failure_shows_manual_relaunch_message(qapp):
    with patch('openlp.core.app.QtCore.QProcess') as process_class, \
            patch('openlp.core.app.QtWidgets.QMessageBox.critical') as message:
        process_class.return_value.startDetached.return_value = False
        OpenLP()._restart_process()
    message.assert_called_once_with(
        None, 'Restart failed', 'OpenLP+ could not restart automatically. Please start it again.')


def test_restart_process_with_real_qprocess(qapp, qtbot, tmp_path, monkeypatch):
    """Exercise the actual Qt return type and launch a harmless child instead of the app."""
    marker = tmp_path / 'restarted.txt'
    script = f'from pathlib import Path; Path({str(marker)!r}).write_text("restarted")'
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    monkeypatch.setattr(sys, 'orig_argv', [sys.executable, '-c', script])

    with patch('openlp.core.app.QtWidgets.QMessageBox.critical') as message:
        OpenLP()._restart_process()

    qtbot.waitUntil(marker.exists, timeout=5000)
    assert marker.read_text() == 'restarted'
    message.assert_not_called()
