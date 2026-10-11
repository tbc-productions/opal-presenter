"""Shared ContentDialog for service titles and local slide labels."""
import fluentqt
from PySide6 import QtCore

from opal.core.common.i18n import translate
from opal.core.widgets import fluent as QtWidgets


class RenameDialog(QtWidgets.ContentDialog):
    def __init__(self, parent, title, label, text):
        super().__init__(parent)
        self.setObjectName('rename_dialog')
        self.setTitle(title)
        self.graphicsEffect().setEnabled(False)
        self.setSmokeEnabled(True)
        self.setDragEnabled(False)
        self.setMinimumWidth(420)
        self.setMaximumWidth(560)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.name_edit = QtWidgets.QLineEdit(content)
        self.name_edit.setObjectName('rename_edit')
        self.name_edit.setAccessibleName(label.rstrip(':'))
        self.name_edit.setText(text)
        self.name_edit.selectAll()
        layout.addWidget(self.name_edit)
        self.setContent(content)
        rename = translate('OpenLP.RenameDialog', 'Rename')
        self.setPrimaryButtonText(rename)
        self.setCloseButtonText(translate('OpenLP.RenameDialog', 'Cancel'))
        self.setDefaultButton(fluentqt.ContentDialogButton.Primary)
        self.rename_button = next(button for button in self.findChildren(fluentqt.Button) if button.text() == rename)
        self.name_edit.textChanged.connect(lambda value: self.rename_button.setEnabled(bool(value.strip())))
        self.rename_button.setEnabled(bool(text.strip()))
        QtCore.QTimer.singleShot(0, self.name_edit, self.name_edit.setFocus)

    @classmethod
    def get_text(cls, parent, title, label, text):
        dialog = cls(parent, title, label, text)
        try:
            accepted = dialog.exec() == dialog.ResultPrimary
            return dialog.name_edit.text().strip(), accepted
        finally:
            dialog.deleteLater()
