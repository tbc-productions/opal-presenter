"""Admin setup using Fluent wizard controls and a portable, token-free export."""
import json
from pathlib import Path

from PySide6 import QtCore

from openlp.core.common.i18n import translate
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.wizard import WIZARD_FIXED_HEIGHT, WIZARD_FIXED_WIDTH
from openlp.plugins.librarysync.lib.profile import MAX_PROFILE, folder_reference, validate_profile, write_profile
from openlp.plugins.librarysync.lib.provider import SyncError


def tr(text):
    return translate('LibrarySync', text)


class ConnectionWizard(QtWidgets.QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile = None
        self.setWindowTitle(tr('Set up Google Drive'))
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ModernStyle)
        self.setFixedSize(WIZARD_FIXED_WIDTH, WIZARD_FIXED_HEIGHT)
        self.setOption(QtWidgets.QWizard.WizardOption.NoBackButtonOnStartPage)

        credentials, layout = self.add_page(tr('Google app credentials'), tr(
            'Enable the Google Drive API and create a Desktop app OAuth client for your organisation.'))
        instructions = QtWidgets.fluentqt.HyperlinkButton(
            tr('Google setup instructions'),
            QtCore.QUrl('https://developers.google.com/identity/protocols/oauth2/native-app'), credentials)
        layout.addWidget(instructions)
        form = QtWidgets.QFormLayout()
        self.client_id = QtWidgets.QLineEdit(credentials)
        self.client_id.setMaxLength(250)
        self.client_secret = QtWidgets.QLineEdit(credentials)
        self.client_secret.setMaxLength(250)
        self.client_secret.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        form.addRow(tr('Client ID:'), self.client_id)
        form.addRow(tr('Client secret:'), self.client_secret)
        layout.addLayout(form)
        credentials.registerField('client_id*', self.client_id, 'text', QtCore.SIGNAL('textChanged(QString)'))
        load = QtWidgets.QPushButton(tr('Load Google client JSON…'), credentials)
        load.clicked.connect(self.load_google_client)
        layout.addWidget(load, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.credentials_error = self.add_error(credentials, layout)
        layout.addStretch()

        folder, layout = self.add_page(tr('Shared organisation folder'), tr(
            'Each team member signs in with their own Google account. The folder’s permissions control uploads.'))
        form = QtWidgets.QFormLayout()
        self.connection_name = QtWidgets.QLineEdit(folder)
        self.connection_name.setText(tr('Organisation Library'))
        self.connection_name.setMaxLength(200)
        self.folder_link = QtWidgets.QLineEdit(folder)
        self.folder_link.setPlaceholderText(tr('Paste a Google Drive folder link'))
        self.folder_link.setMaxLength(2048)
        form.addRow(tr('Connection name:'), self.connection_name)
        form.addRow(tr('Shared folder:'), self.folder_link)
        layout.addLayout(form)
        folder.registerField('folder_link*', self.folder_link, 'text', QtCore.SIGNAL('textChanged(QString)'))
        self.folder_error = self.add_error(folder, layout)
        layout.addStretch()

        share, layout = self.add_page(tr('Save and share'), tr(
            'Save this connection, then choose Connect in Cloud Library to sign in and check folder access.'))
        message = QtWidgets.QLabel(tr(
            'The shared file conceals the app credentials from casual reading. It is reversible, '
            'so it is not secret encryption. Personal sign-in tokens and passwords are never included.'), share)
        message.setWordWrap(True)
        layout.addWidget(message)
        self.export_check = QtWidgets.QCheckBox(share)
        self.export_check.setText(tr('Export a connection file for the team'))
        self.export_check.setChecked(True)
        layout.addWidget(self.export_check)
        self.share_error = self.add_error(share, layout)
        layout.addStretch()
        self.setButtonText(QtWidgets.QWizard.WizardButton.FinishButton, tr('Save connection'))

    def add_page(self, title, subtitle):
        page = QtWidgets.QWizardPage(self)
        page.setTitle(title)
        page.setSubTitle(subtitle)
        layout = QtWidgets.QVBoxLayout(page)
        self.addPage(page)
        return page, layout

    def add_error(self, page, layout):
        error = QtWidgets.fluentqt.InfoBar(page)
        policy = error.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Policy.Expanding)
        error.setSizePolicy(policy)
        error.setSeverity(QtWidgets.fluentqt.InfoBar.InfoBarSeverity.Error)
        error.setIsClosable(False)
        error.hide()
        layout.addWidget(error)
        return error

    def client(self):
        return {'client_id': self.client_id.text().strip(), 'client_secret': self.client_secret.text().strip()}

    def connection_profile(self):
        folder_id, key = folder_reference(self.folder_link.text())
        return validate_profile({'version': 1, 'provider': 'google-drive', 'installed': self.client(),
                                 'name': self.connection_name.text(),
                                 'folders': [{'id': folder_id, 'name': self.connection_name.text(),
                                              'resource_key': key}]})

    def load_google_client(self):
        path, _ = FileDialog.getOpenFileName(
            self, tr('Choose Google Desktop app OAuth client JSON'), filter=tr('Google client configuration (*.json)'))
        if not path:
            return
        try:
            if path.stat().st_size > MAX_PROFILE:
                raise SyncError('The Google configuration file is too large.')
            value = json.loads(path.read_text(encoding='utf-8'))
            client = value.get('installed') if isinstance(value, dict) else None
            if not client:
                raise SyncError('Choose a Desktop app OAuth client, rather than a web client or service account.')
            clean = validate_profile({'version': 1, 'provider': 'google-drive', 'installed': client,
                                      'folders': [{'id': 'pending', 'name': 'Pending'}]})['installed']
            self.client_id.setText(clean['client_id'])
            self.client_secret.setText(clean['client_secret'])
            self.credentials_error.hide()
        except (OSError, ValueError, UnicodeError, SyncError) as error:
            message = (str(error) if isinstance(error, SyncError) else
                       tr('Could not read the Google client file. Choose a valid Desktop client.'))
            self.credentials_error.setMessage(message)
            self.credentials_error.show()

    def validateCurrentPage(self):
        error_info = (self.credentials_error, self.folder_error, self.share_error)[self.currentId()]
        error_info.hide()
        try:
            if self.currentId() == 0:
                validate_profile({'version': 1, 'provider': 'google-drive', 'installed': self.client(),
                                  'folders': [{'id': 'pending', 'name': 'Pending'}]})
            elif self.currentId() == 1:
                self.connection_profile()
            else:
                profile = self.connection_profile()
                if self.export_check.isChecked():
                    path, _ = FileDialog.getSaveFileName(
                        self, tr('Export Library Sync connection'), Path('organisation-library.librarysync.json'),
                        tr('Connection file (*.json)'))
                    if not path:
                        return False
                    write_profile(path, profile)
                self.profile = profile
            return True
        except (OSError, SyncError) as error:
            error_info.setMessage(str(error) if isinstance(error, SyncError) else
                                  tr('Could not save the connection file. Choose another location and retry.'))
            error_info.show()
            return False
