"""The storage wizard validates local folders and saves connection settings."""
from unittest.mock import MagicMock

import pytest
from PySide6 import QtCore

from opal.core.widgets import fluent as QtWidgets
from opal.plugins.librarysync.lib.connectionwizard import ConnectionWizard


@pytest.fixture
def wizard(settings, qtbot):
    widget = ConnectionWizard()
    qtbot.addWidget(widget)
    widget.restart()
    return widget


def fill_wizard(wizard, path):
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('local-cloud'))
    wizard.connection_name.setText('Organisation Library')
    wizard.provider_pages['local-cloud'].folder_path.setText(str(path))


def test_local_storage_disables_export_and_saves_without_file_prompt(wizard, tmp_path, monkeypatch):
    fill_wizard(wizard, tmp_path)
    wizard.next()
    wizard.next()
    assert not wizard.export_check.isEnabled()
    assert not wizard.export_check.isChecked()
    wizard.export_check.setChecked(True)
    dialog = MagicMock()
    write = MagicMock()
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.FileDialog.getSaveFileName', dialog)
    monkeypatch.setattr('opal.plugins.librarysync.lib.connectionwizard.write_profile', write)
    assert wizard.validateCurrentPage()
    assert wizard.profile['path'] == str(tmp_path)
    assert 'installed' not in wizard.profile
    dialog.assert_not_called()
    write.assert_not_called()


def test_provider_and_unique_name_are_required_before_next(wizard, qtbot):
    next_button = wizard.button(QtWidgets.QWizard.WizardButton.NextButton)
    assert wizard.currentId() == 0
    assert wizard.provider_combo.currentData() is None
    assert wizard.connection_name.isEnabled()
    assert wizard.connection_name.accessibleName() == 'Library name'
    assert wizard.buttonText(QtWidgets.QWizard.WizardButton.FinishButton) == 'Save library'
    assert not next_button.isEnabled()
    wizard.connection_name.setText('North Campus Library')
    assert not next_button.isEnabled()
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('local-cloud'))
    assert wizard.connection_name.isEnabled()
    assert wizard.connection_name.text() == 'North Campus Library'
    assert next_button.isEnabled()
    wizard.connection_name.clear()
    assert not next_button.isEnabled()
    assert wizard.name_error() == 'Enter a library name.'
    wizard.connection_name.setText('   ')
    assert not next_button.isEnabled()
    wizard.existing_names = {'north campus library'}
    wizard.connection_name.setText('  NORTH Campus Library  ')
    assert not next_button.isEnabled()
    assert not wizard.connection_error.isHidden()
    assert wizard.name_error() == 'This library name is already in use.'
    assert not wizard.validateCurrentPage()
    wizard.connection_name.setText('South Campus Library')
    assert next_button.isEnabled()
    assert wizard.connection_error.isHidden()
    wizard.next()
    assert wizard.currentPage() is wizard.provider_pages['local-cloud']
    assert not next_button.isEnabled()


def test_back_preserves_provider_details_and_updates_review(wizard, tmp_path):
    fill_wizard(wizard, tmp_path)
    wizard.next()
    wizard.next()
    wizard.back()
    wizard.back()
    wizard.connection_name.setText('South Campus Library')
    wizard.next()
    assert wizard.provider_pages['local-cloud'].folder_path.text() == str(tmp_path)
    wizard.next()
    assert 'South Campus Library' in wizard.summary.text()
    assert 'Local Cloud Storage' in wizard.summary.text()
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
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData('local-cloud'))
    widget.next()
    assert widget.currentPage() is widget.provider_pages['local-cloud']


def test_setup_provider_needs_runtime_and_profile_support(settings, qtbot, monkeypatch):
    from opal.plugins.librarysync.lib import connectionwizard
    monkeypatch.setitem(connectionwizard.PROVIDER_PAGES, 'unavailable', connectionwizard.LocalStoragePage)
    widget = ConnectionWizard()
    qtbot.addWidget(widget)
    assert widget.provider_combo.count() == 2
    assert widget.provider_combo.findData('google-drive') == -1


def test_local_setup_validates_before_keyboard_and_mouse_submission(wizard, tmp_path, qtbot):
    fill_wizard(wizard, tmp_path)
    wizard.connection_name.setText('Organisation Library ' * 9)
    wizard.resize(460, 380)
    wizard.show()
    next_button = wizard.button(QtWidgets.QWizard.WizardButton.NextButton)
    next_button.setFocus()
    qtbot.keyClick(next_button, QtCore.Qt.Key.Key_Return)
    page = wizard.provider_pages['local-cloud']
    assert wizard.currentPage() is page
    page.folder_path.setText(str(tmp_path / 'missing'))
    next_button.setFocus()
    qtbot.keyClick(next_button, QtCore.Qt.Key.Key_Return)
    assert wizard.currentPage() is page and not page.error.isHidden()
    page.folder_path.setText(str(tmp_path))
    qtbot.mouseClick(next_button, QtCore.Qt.MouseButton.LeftButton)
    assert wizard.currentPage() is wizard.share_page
    assert not wizard.export_check.isChecked()
    finish = wizard.button(QtWidgets.QWizard.WizardButton.FinishButton)
    finish.setFocus()
    qtbot.keyClick(finish, QtCore.Qt.Key.Key_Return)
    assert wizard.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert wizard.profile['path'] == str(tmp_path)


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
    wizard.provider_combo.setCurrentIndex(wizard.provider_combo.findData('local-cloud'))
    wizard.next()
    assert wizard.currentPage() is wizard.provider_pages['local-cloud']
    assert not wizard.export_check.isChecked()


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
