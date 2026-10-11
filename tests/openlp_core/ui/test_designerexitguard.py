"""Designer exit resumes the ordinary service-save contract without a second exit confirmation."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtGui

from opal.core.ui.mainwindow import MainWindow
from opal.core.widgets import fluent as QtWidgets


def test_clean_service_exits_immediately_after_designers_close():
    main = MagicMock()
    main.application.is_event_loop_active = True
    main.service_manager_contents.is_modified.return_value = False
    main.service_manager_contents.service_items = [object()]
    main.settings.value.return_value = True  # Normally asks for exit confirmation.
    main._closing_designers_for_exit = True
    event = QtGui.QCloseEvent()
    with patch('opal.core.ui.mainwindow.QtWidgets.QMessageBox') as confirmation:
        MainWindow.closeEvent(main, event)
    assert event.isAccepted()
    confirmation.assert_not_called()
    main.service_manager_contents.save_modified_service.assert_not_called()
    main.clean_up.assert_called_once()


@pytest.mark.parametrize('choice, save_succeeds, closes', [
    (QtWidgets.QMessageBox.StandardButton.Save, True, True),
    (QtWidgets.QMessageBox.StandardButton.Save, False, False),
    (QtWidgets.QMessageBox.StandardButton.Discard, False, True),
    (QtWidgets.QMessageBox.StandardButton.Cancel, False, False)])
def test_service_save_prompt_still_runs_after_designers_close(choice, save_succeeds, closes):
    main = MagicMock()
    main.application.is_event_loop_active = True
    main.service_manager_contents.is_modified.return_value = True
    main.service_manager_contents.save_modified_service.return_value = choice
    main.service_manager_contents.decide_save_method.return_value = save_succeeds
    main._closing_designers_for_exit = True
    event = QtGui.QCloseEvent()
    MainWindow.closeEvent(main, event)
    assert event.isAccepted() is closes
    main.service_manager_contents.save_modified_service.assert_called_once()
    assert main.clean_up.called is closes
