"""Renaming uses Fluent ContentDialog acceptance and cancellation."""
import fluentqt
import pytest
from PySide6 import QtCore, QtWidgets

from openlp.core.ui.renamedialog import RenameDialog


@pytest.mark.parametrize('accept', [True, False])
def test_rename_content_dialog_returns_only_confirmed_changes(qapp, accept):
    parent = QtWidgets.QWidget()
    parent.resize(900, 600)
    parent.show()
    observed = []

    def finish():
        dialog = parent.findChild(RenameDialog)
        observed.append((isinstance(dialog, fluentqt.ContentDialog), dialog.isSmokeEnabled(),
                         dialog.name_edit.text()))
        dialog.name_edit.setText(' New label ')
        if accept:
            dialog.rename_button.click()
        else:
            next(button for button in dialog.findChildren(fluentqt.Button) if button.text() == 'Cancel').click()

    QtCore.QTimer.singleShot(30, finish)
    value, accepted = RenameDialog.get_text(parent, 'Rename slide label', 'Label:', 'Original')
    assert observed == [(True, True, 'Original')]
    assert value == 'New label'
    assert accepted is accept
    parent.close()


def test_blank_name_cannot_be_confirmed(qapp):
    parent = QtWidgets.QWidget()
    dialog = RenameDialog(parent, 'Rename item title', 'Title:', 'Original')
    assert dialog.name_edit.accessibleName() == 'Title'
    assert not any(label.text() == 'Title:' for label in dialog.findChildren(fluentqt.Label))
    dialog.name_edit.setText('  ')
    assert not dialog.rename_button.isEnabled()
    dialog.name_edit.setText('New title')
    assert dialog.rename_button.isEnabled()
    dialog.deleteLater()
    parent.close()
