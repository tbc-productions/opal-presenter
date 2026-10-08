"""The admin wizard validates credentials and exports only portable app configuration."""
import json
from unittest.mock import MagicMock

import pytest

from openlp.core.widgets import fluent as QtWidgets
from openlp.plugins.librarysync.lib.connectionwizard import ConnectionWizard
from openlp.plugins.librarysync.lib.profile import read_profile


@pytest.fixture
def wizard(settings, qtbot):
    widget = ConnectionWizard()
    qtbot.addWidget(widget)
    widget.restart()
    return widget


def fill_wizard(wizard):
    wizard.client_id.setText('church.apps.googleusercontent.com')
    wizard.client_secret.setText('desktop-client')
    wizard.folder_link.setText('https://drive.google.com/drive/folders/church?resourcekey=link-key')


def test_wizard_masks_secret_and_rejects_wrong_client(wizard):
    assert wizard.connection_name.text() == 'Organisation Library'
    assert wizard.client_secret.echoMode() == QtWidgets.QLineEdit.EchoMode.Password
    wizard.client_id.setText('not-a-desktop-client')
    assert not wizard.validateCurrentPage()
    assert not wizard.credentials_error.isHidden()
    fill_wizard(wizard)
    assert wizard.validateCurrentPage()
    wizard.next()
    assert wizard.button(QtWidgets.QWizard.WizardButton.NextButton).isEnabled()
    wizard.folder_link.setText('https://attacker.example/drive/folders/church')
    assert not wizard.validateCurrentPage()
    assert not wizard.folder_error.isHidden()


def test_wizard_exports_on_finish_and_retains_folder_key(wizard, tmp_path, monkeypatch):
    fill_wizard(wizard)
    wizard.connection_name.setText('North Campus Library')
    wizard.next()
    wizard.next()
    exported = tmp_path / 'church.librarysync.json'
    monkeypatch.setattr('openlp.plugins.librarysync.lib.connectionwizard.FileDialog.getSaveFileName',
                        lambda *args, **kwargs: (exported, ''))
    assert wizard.validateCurrentPage()
    assert wizard.profile['folders'][0]['resource_key'] == 'link-key'
    assert wizard.profile['name'] == 'North Campus Library'
    assert wizard.profile['folders'][0]['name'] == 'North Campus Library'
    assert read_profile(exported) == wizard.profile
    assert json.loads(exported.read_text())['name'] == 'North Campus Library'
    assert 'desktop-client' not in exported.read_text()


def test_cancelled_export_keeps_wizard_open(wizard, monkeypatch):
    fill_wizard(wizard)
    wizard.next()
    wizard.next()
    dialog = MagicMock(return_value=(None, ''))
    monkeypatch.setattr('openlp.plugins.librarysync.lib.connectionwizard.FileDialog.getSaveFileName', dialog)
    assert not wizard.validateCurrentPage()
    assert wizard.profile is None
    wizard.export_check.setChecked(False)
    assert wizard.validateCurrentPage()
    assert wizard.profile
    dialog.assert_called_once()


def test_wizard_can_load_google_desktop_client_json(wizard, tmp_path, monkeypatch):
    client_file = tmp_path / 'google-client.json'
    client_file.write_text(json.dumps({'installed': {
        'client_id': 'church.apps.googleusercontent.com', 'client_secret': 'desktop-client',
        'token_uri': 'https://attacker.example'}}))
    monkeypatch.setattr('openlp.plugins.librarysync.lib.connectionwizard.FileDialog.getOpenFileName',
                        lambda *args, **kwargs: (client_file, ''))
    wizard.load_google_client()
    assert wizard.client_id.text() == 'church.apps.googleusercontent.com'
    assert wizard.client_secret.text() == 'desktop-client'
    assert wizard.credentials_error.isHidden()
