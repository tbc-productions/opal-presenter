"""Provider-specific setup with Fluent controls and a portable, token-free export."""
import os
from pathlib import Path

from PySide6 import QtCore

from opal.core.common.i18n import translate
from opal.core.widgets import fluent as QtWidgets
from opal.core.widgets.dialogs import FileDialog
from opal.core.widgets.wizard import WIZARD_FIXED_WIDTH
from opal.plugins.librarysync.lib.profile import PROFILE_VALIDATORS, validate_profile, write_profile
from opal.plugins.librarysync.lib.provider import SyncError
from opal.plugins.librarysync.lib.worker import PROVIDERS


def tr(text):
    return translate('LibrarySync', text)


def label(text, parent, role=QtWidgets.fluentqt.FontRole.Body, secondary=False):
    widget = QtWidgets.QLabel(text, parent)
    widget.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    widget.setFluentTypography(role)
    widget.setWordWrap(True)
    if secondary:
        widget.setTextColorRole(QtWidgets.fluentqt.Label.TextColorRole.Secondary)
    return widget


def add_field(form, text, widget):
    widget.setAccessibleName(text)
    widget.setMinimumHeight(32)
    caption = label(text, widget.parentWidget())
    caption.setBuddy(widget)
    form.addRow(caption, widget)


class ConnectionPage(QtWidgets.QWizardPage):
    def isComplete(self):
        wizard = self.wizard()
        return wizard.provider_combo.currentData() in wizard.provider_pages and not wizard.name_error()


class LocalStoragePage(QtWidgets.QWizardPage):
    display_name = 'Local Cloud Storage'
    description = 'Choose a local or synced folder.'

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)
        self.folder_path = QtWidgets.QLineEdit(self)
        self.folder_path.setMaxLength(4096)
        self.folder_path.setMinimumHeight(32)
        self.folder_path.setAccessibleName(tr('Storage folder'))
        caption = label(tr('Storage folder'), self, QtWidgets.fluentqt.FontRole.BodyStrong)
        caption.setBuddy(self.folder_path)
        layout.addWidget(caption)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.folder_path, 1)
        browse = QtWidgets.QPushButton(tr('Browse…'), self)
        browse.clicked.connect(self.choose_folder)
        row.addWidget(browse)
        layout.addLayout(row)
        layout.addWidget(label(tr('Your storage app handles syncing and sharing.'), self, secondary=True))
        self.error = ConnectionWizard.add_error(self, layout)
        layout.addStretch()
        self.folder_path.textChanged.connect(self.completeChanged)
        self.folder_path.textChanged.connect(self.error.hide)

    def choose_folder(self):
        directory = Path(self.folder_path.text()) if self.folder_path.text() else Path.home()
        path = FileDialog.getExistingDirectory(self, tr('Choose Cloud Library storage folder'),
                                               directory)
        if path:
            self.folder_path.setText(str(path))

    def isComplete(self):
        return bool(self.folder_path.text().strip())

    def connection_profile(self, name):
        return validate_profile({'version': 1, 'provider': 'local-cloud', 'name': name,
                                 'path': self.folder_path.text().strip()})

    def validatePage(self):
        self.error.hide()
        try:
            profile = self.connection_profile(self.wizard().connection_name.text().strip())
            path = Path(profile['path'])
            if not path.is_dir() or not os.access(path, os.R_OK | os.X_OK):
                raise SyncError(tr('Choose an existing folder that you can read.'))
            return True
        except (OSError, SyncError) as error:
            self.error.setMessage(str(error) if isinstance(error, SyncError) else tr('Could not access this folder.'))
            self.error.show()
            return False


PROVIDER_PAGES = {'local-cloud': LocalStoragePage}


class ConnectionWizard(QtWidgets.QWizard):
    def __init__(self, parent=None, existing_names=()):
        super().__init__(parent)
        self.profile = None
        self.existing_names = {name.strip().casefold() for name in existing_names}
        self.setWindowTitle(tr('Set up Library Sync'))
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ModernStyle)
        self.resize(WIZARD_FIXED_WIDTH, 540)
        self.setOption(QtWidgets.QWizard.WizardOption.NoBackButtonOnStartPage)
        # Keep typed provider details when users go back to rename the connection.
        self.setOption(QtWidgets.QWizard.WizardOption.IndependentPages)
        for button in (self.WizardButton.NextButton, self.WizardButton.FinishButton):
            self.button(button).setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Accent)
        for button in (self.WizardButton.HelpButton, self.WizardButton.CustomButton1,
                       self.WizardButton.CustomButton2, self.WizardButton.CustomButton3):
            self.button(button).hide()
        self.setButtonText(self.WizardButton.NextButton, tr('Next'))
        self.setButtonText(self.WizardButton.BackButton, tr('Back'))
        self.setButtonText(self.WizardButton.FinishButton, tr('Save connection'))

        connection = ConnectionPage(self)
        layout = self.add_page(connection, tr('Choose your cloud provider'), tr(
            'Choose a provider and enter a unique connection name.'), 1)
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(16)
        self.provider_combo = QtWidgets.QComboBox(connection)
        self.provider_combo.addItem(tr('Choose a cloud provider'), None)
        self.connection_name = QtWidgets.QLineEdit(connection)
        self.connection_name.setMaxLength(200)
        add_field(form, tr('Cloud provider'), self.provider_combo)
        add_field(form, tr('Connection name'), self.connection_name)
        layout.addLayout(form)
        self.connection_error = self.add_error(connection, layout)
        layout.addStretch()

        self.provider_pages = {}
        for provider, page_class in PROVIDER_PAGES.items():
            if provider not in PROVIDERS or provider not in PROFILE_VALIDATORS:
                continue
            page = page_class(self)
            self.add_page(page, tr('Configure {provider}').format(provider=tr(page_class.display_name)),
                          tr(page_class.description), 2)
            self.provider_pages[provider] = page
            self.provider_combo.addItem(tr(page_class.display_name), provider)
        self.provider_combo.setCurrentIndex(0)

        share = QtWidgets.QWizardPage(self)
        layout = self.add_page(share, tr('Review and save'), tr(
            'Save to open this folder in Cloud Library.'), 3)
        self.summary = label('', share, QtWidgets.fluentqt.FontRole.BodyStrong)
        layout.addWidget(self.summary)
        self.export_check = QtWidgets.QCheckBox(tr('Export a connection file for the team'), share)
        self.export_check.setChecked(False)
        layout.addWidget(self.export_check)
        self.share_hint = label(tr(
            'Each computer selects its own folder.'), share, secondary=True)
        layout.addWidget(self.share_hint)
        self.share_error = self.add_error(share, layout)
        layout.addStretch()
        self.share_page = share
        self.provider_combo.currentIndexChanged.connect(self.connection_changed)
        self.connection_name.textChanged.connect(self.connection_changed)
        self.currentIdChanged.connect(self.page_changed)

    def add_page(self, page, title, subtitle, step):
        layout = page.layout() or QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        for index, widget in enumerate((
                label(tr('Step {step} of 3').format(step=step), page,
                      QtWidgets.fluentqt.FontRole.Caption, secondary=True),
                label(title, page, QtWidgets.fluentqt.FontRole.Title),
                label(subtitle, page, secondary=True))):
            layout.insertWidget(index, widget)
        self.addPage(page)
        return layout

    @staticmethod
    def add_error(page, layout):
        error = QtWidgets.fluentqt.InfoBar(page)
        policy = error.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Policy.Expanding)
        error.setSizePolicy(policy)
        error.setSeverity(QtWidgets.fluentqt.InfoBar.InfoBarSeverity.Error)
        error.setIsClosable(False)
        error.hide()
        layout.addWidget(error)
        return error

    def name_error(self):
        name = self.connection_name.text().strip()
        if not name:
            return tr('Enter a connection name.')
        if name.casefold() in self.existing_names:
            return tr('This connection name is already in use. Choose a different name.')
        return ''

    def connection_changed(self):
        if self.sender() is self.provider_combo:
            exportable = bool(self.provider_combo.currentData()) and self.provider_combo.currentData() != 'local-cloud'
            self.export_check.setEnabled(exportable)
            self.export_check.setChecked(exportable)
        error = self.name_error()
        self.connection_error.setMessage(error)
        self.connection_error.setVisible(bool(self.connection_name.text() and error))
        self.page(0).completeChanged.emit()

    def nextId(self):
        if self.currentId() == 0:
            page = self.provider_pages.get(self.provider_combo.currentData())
            return self.pageIds()[list(self.provider_pages.values()).index(page) + 1] if page else self.pageIds()[1]
        if self.currentPage() is self.share_page:
            return -1
        return self.pageIds()[-1]

    def page_changed(self):
        if self.currentPage() is self.share_page:
            profile = self.connection_profile()
            location = profile.get('path', '')
            self.summary.setText('\n'.join(part for part in (
                self.connection_name.text().strip(), self.provider_combo.currentText(), location) if part))
            if location:
                self.share_hint.setText(tr('Each computer selects its own folder.'))
            else:
                self.share_hint.setText(tr('Connection files contain provider settings.'))

    def connection_profile(self):
        page = self.provider_pages[self.provider_combo.currentData()]
        return page.connection_profile(self.connection_name.text().strip())

    def validateCurrentPage(self):
        if self.currentId() == 0:
            if self.page(0).isComplete():
                return True
            self.connection_error.setMessage(self.name_error() if self.provider_combo.currentData()
                                             else tr('Choose a cloud provider.'))
            self.connection_error.show()
            return False
        if self.currentPage() is not self.share_page:
            return self.currentPage().validatePage()
        self.share_error.hide()
        try:
            profile = self.connection_profile()
            if self.export_check.isEnabled() and self.export_check.isChecked():
                path, _ = FileDialog.getSaveFileName(
                    self, tr('Export Library Sync connection'), Path('organisation-library.opal-connection'),
                    tr('Connection file (*.opal-connection)'))
                if not path:
                    return False
                write_profile(path, profile)
            self.profile = profile
            return True
        except (OSError, SyncError) as error:
            self.share_error.setMessage(str(error) if isinstance(error, SyncError) else
                                        tr('Could not save the connection file. Choose another location and retry.'))
            self.share_error.show()
            return False
