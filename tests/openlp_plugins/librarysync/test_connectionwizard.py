"""The admin wizard validates credentials and exports only portable app configuration."""
import json
from unittest.mock import MagicMock

import pytest

from opal.core.widgets import fluent as QtWidgets
from opal.plugins.librarysync.lib.connectionwizard import ConnectionWizard
from opal.plugins.librarysync.lib.profile import read_profile


@pytest.fixture
def wizard(settings, qtbot):
    widget = ConnectionWizard()
    qtbot.addWidget(widget)
    widget.restart()
    return widget


def fill_wizard(wizard):
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('google-drive'))
    wizard.connection_name.setText('Organisation Library')
    page = wizard.provider_pages['google-drive']
    page.client_id.setText('church.apps.googleusercontent.com')
    page.client_secret.setText('desktop-client')
    page.folder_link.setText('https://drive.google.com/drive/folders/church?resourcekey=link-key')


def test_wizard_masks_secret_and_rejects_wrong_client(wizard):
    fill_wizard(wizard)
    wizard.next()
    page = wizard.provider_pages['google-drive']
    assert page.client_secret.echoMode() == QtWidgets.QLineEdit.EchoMode.Password
    page.client_id.setText('not-a-desktop-client')
    assert not wizard.validateCurrentPage()
    assert not page.error.isHidden()
    page.client_id.setText('church.apps.googleusercontent.com')
    assert wizard.validateCurrentPage()
    assert wizard.button(QtWidgets.QWizard.WizardButton.NextButton).isEnabled()
    page.folder_link.setText('https://attacker.example/drive/folders/church')
    assert not wizard.validateCurrentPage()
    assert not page.error.isHidden()


def test_wizard_exports_on_finish_and_retains_folder_key(wizard, tmp_path, monkeypatch):
    fill_wizard(wizard)
    wizard.connection_name.setText('North Campus Library')
    wizard.next()
    wizard.next()
    exported = tmp_path / 'church.opal-connection'
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.FileDialog.getSaveFileName',
                        lambda *args, **kwargs: (exported, ''))
    assert wizard.validateCurrentPage()
    assert wizard.profile['folders'][0]['resource_key'] == 'link-key'
    assert wizard.profile['name'] == 'North Campus Library'
    assert wizard.profile['folders'][0]['name'] == 'North Campus Library'
    assert read_profile(exported) == wizard.profile
    assert json.loads(exported.read_text())['data']['name'] == 'North Campus Library'
    assert 'desktop-client' not in exported.read_text()


def test_cancelled_export_keeps_wizard_open(wizard, monkeypatch):
    fill_wizard(wizard)
    wizard.next()
    wizard.next()
    dialog = MagicMock(return_value=(None, ''))
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.FileDialog.getSaveFileName', dialog)
    assert not wizard.validateCurrentPage()
    assert wizard.profile is None
    wizard.export_check.setChecked(False)
    assert wizard.validateCurrentPage()
    assert wizard.profile
    dialog.assert_called_once()


def test_wizard_can_load_google_desktop_client_json(wizard, tmp_path, monkeypatch):
    page = wizard.provider_pages['google-drive']
    client_file = tmp_path / 'google-client.json'
    client_file.write_text(json.dumps({'installed': {
        'client_id': 'church.apps.googleusercontent.com', 'client_secret': 'desktop-client',
        'token_uri': 'https://attacker.example'}}))
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.FileDialog.getOpenFileName',
                        lambda *args, **kwargs: (client_file, ''))
    page.load_google_client()
    assert page.client_id.text() == 'church.apps.googleusercontent.com'
    assert page.client_secret.text() == 'desktop-client'
    assert page.error.isHidden()


def test_provider_and_unique_name_are_required_before_next(wizard, qtbot):
    next_button = wizard.button(QtWidgets.QWizard.WizardButton.NextButton)
    assert wizard.currentId() == 0
    assert wizard.provider_combo.currentData() is None
    assert wizard.connection_name.isEnabled()
    assert not next_button.isEnabled()
    wizard.connection_name.setText('North Campus Library')
    assert not next_button.isEnabled()
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('google-drive'))
    assert wizard.connection_name.isEnabled()
    assert wizard.connection_name.text() == 'North Campus Library'
    assert next_button.isEnabled()
    wizard.connection_name.clear()
    assert not next_button.isEnabled()
    wizard.connection_name.setText('   ')
    assert not next_button.isEnabled()
    wizard.existing_names = {'north campus library'}
    wizard.connection_name.setText('  NORTH Campus Library  ')
    assert not next_button.isEnabled()
    assert not wizard.connection_error.isHidden()
    assert not wizard.validateCurrentPage()
    wizard.connection_name.setText('South Campus Library')
    assert next_button.isEnabled()
    assert wizard.connection_error.isHidden()
    wizard.next()
    assert wizard.currentPage() is wizard.provider_pages['google-drive']
    assert not next_button.isEnabled()


def test_back_preserves_provider_details_and_updates_review(wizard):
    fill_wizard(wizard)
    wizard.next()
    wizard.next()
    wizard.back()
    wizard.back()
    wizard.connection_name.setText('South Campus Library')
    wizard.next()
    assert wizard.provider_pages['google-drive'].client_id.text() == 'church.apps.googleusercontent.com'
    wizard.next()
    assert 'South Campus Library' in wizard.summary.text()
    assert 'Google Drive' in wizard.summary.text()
    wizard.export_check.setChecked(False)
    assert wizard.validateCurrentPage()
    assert wizard.profile['name'] == 'South Campus Library'


def test_wizard_routes_to_selected_provider_and_skips_other_pages(settings, qtbot, monkeypatch):
    from opal.plugins.librarysync.lib import connectionwizard
    from opal.plugins.librarysync.lib.profile import PROFILE_VALIDATORS, serialize_profile

    class OtherProviderPage(QtWidgets.QWizardPage):
        display_name = 'Other cloud'
        description = 'Configure another provider.'

        def connection_profile(self, name):
            return {'version': 1, 'provider': 'other-cloud', 'name': name, 'folders': []}

    monkeypatch.setitem(connectionwizard.PROVIDER_PAGES, 'other-cloud', OtherProviderPage)
    monkeypatch.setitem(connectionwizard.PROVIDERS, 'other-cloud', MagicMock())
    monkeypatch.setitem(PROFILE_VALIDATORS, 'other-cloud', lambda value: {
        key: value[key] for key in ('version', 'provider', 'name', 'folders')})
    widget = ConnectionWizard(existing_names=['Existing Library'])
    qtbot.addWidget(widget)
    widget.restart()
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData('other-cloud'))
    widget.connection_name.setText('Other Library')
    widget.next()
    assert widget.currentPage() is widget.provider_pages['other-cloud']
    widget.next()
    assert widget.currentPage() is widget.share_page
    widget.export_check.setChecked(False)
    assert widget.validateCurrentPage()
    assert widget.profile['provider'] == 'other-cloud'
    assert 'other-cloud' in connectionwizard.PROVIDERS
    assert serialize_profile(widget.profile)
    widget.back()
    assert widget.currentPage() is widget.provider_pages['other-cloud']
    widget.back()
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData('google-drive'))
    widget.next()
    assert widget.currentPage() is widget.provider_pages['google-drive']


def test_setup_provider_needs_runtime_and_profile_support(settings, qtbot, monkeypatch):
    from opal.plugins.librarysync.lib import connectionwizard
    monkeypatch.setitem(connectionwizard.PROVIDER_PAGES, 'unavailable', connectionwizard.GoogleDrivePage)
    widget = ConnectionWizard()
    qtbot.addWidget(widget)
    assert widget.provider_combo.count() == 3


def test_export_failure_keeps_profile_unset(wizard, tmp_path, monkeypatch):
    fill_wizard(wizard)
    wizard.next()
    wizard.next()
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.FileDialog.getSaveFileName',
                        lambda *args, **kwargs: (tmp_path / 'connection.json', ''))
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.write_profile',
                        MagicMock(side_effect=OSError('disk error')))
    assert not wizard.validateCurrentPage()
    assert wizard.profile is None
    assert not wizard.share_error.isHidden()


def test_local_storage_page_chooses_folder_and_saves_without_credentials(wizard, tmp_path, monkeypatch):
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('local-cloud'))
    wizard.connection_name.setText('Desktop Library')
    wizard.next()
    page = wizard.provider_pages['local-cloud']
    assert wizard.currentPage() is page
    assert not wizard.export_check.isChecked()
    assert not wizard.button(QtWidgets.QWizard.WizardButton.NextButton).isEnabled()
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.FileDialog.getExistingDirectory',
                        lambda *args, **kwargs: tmp_path)
    page.choose_folder()
    assert page.folder_path.text() == str(tmp_path)
    assert wizard.validateCurrentPage()
    wizard.next()
    assert wizard.currentPage() is wizard.share_page
    assert str(tmp_path) in wizard.summary.text()
    assert wizard.validateCurrentPage()
    assert wizard.profile['provider'] == 'local-cloud'
    assert wizard.profile['path'] == str(tmp_path)
    assert 'installed' not in wizard.profile
    wizard.back()
    wizard.back()
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('google-drive'))
    wizard.next()
    assert wizard.currentPage() is wizard.provider_pages['google-drive']
    assert wizard.export_check.isChecked()


def test_local_storage_rejects_missing_folder_or_file(wizard, tmp_path):
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('local-cloud'))
    wizard.connection_name.setText('Desktop Library')
    wizard.next()
    page = wizard.provider_pages['local-cloud']
    for path in (tmp_path / 'missing', tmp_path / 'file.txt'):
        if path.suffix:
            path.write_text('not a folder')
        page.folder_path.setText(str(path))
        assert not wizard.validateCurrentPage()
        assert not page.error.isHidden()
    page.folder_path.setText(str(tmp_path))
    assert wizard.validateCurrentPage()


def test_cancelled_local_folder_picker_retains_selection(wizard, tmp_path, monkeypatch):
    page = wizard.provider_pages['local-cloud']
    page.folder_path.setText(str(tmp_path))
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.FileDialog.getExistingDirectory',
                        lambda *args, **kwargs: None)
    page.choose_folder()
    assert page.folder_path.text() == str(tmp_path)
