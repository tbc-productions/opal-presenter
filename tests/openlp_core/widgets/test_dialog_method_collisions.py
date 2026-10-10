"""Dialogs retain Qt methods while preparing and opening their content."""
from unittest.mock import MagicMock

import pytest
from PySide6 import QtCore, QtWidgets

from openlp.core.projectors.editform import ProjectorEditForm
from openlp.core.projectors.sourceselectform import SourceSelectSingle, SourceSelectTabs
from openlp.core.widgets.dialogs import DownloadProgressDialog
from openlp.core.widgets.widgets import ProxyDialog


@pytest.mark.parametrize('kind', ['proxy', 'source_single', 'source_single_edit',
                                 'source_tabs', 'source_tabs_edit', 'projector', 'download'])
def test_dialog_exec_retains_qt_methods(settings, kind):
    parent = QtWidgets.QWidget()
    parent.resize(1200, 900)
    parent.show()
    manager = MagicMock()
    manager.get_source_list.return_value = {'11': 'RGB 1'}
    manager.get_source_by_code.return_value = None
    projector = MagicMock(source_available=['11'], source='11')
    args = ()
    if kind.startswith('proxy'):
        dialog = ProxyDialog(parent)
    elif kind.startswith('source'):
        factory = SourceSelectTabs if 'tabs' in kind else SourceSelectSingle
        dialog = factory(parent, manager, edit=kind.endswith('_edit'))
        args = (projector,)
    elif kind == 'projector':
        dialog = ProjectorEditForm(parent, manager)
    else:
        dialog = DownloadProgressDialog(parent, MagicMock())
    dialog.setAnimationEnabled(False)
    observed = []

    def dismiss():
        observed.append((dialog.isVisible(), dialog.isOpen(), dialog.parent() is parent,
                         isinstance(dialog.layout(), QtWidgets.QLayout)))
        dialog.reject()

    QtCore.QTimer.singleShot(0, dismiss)
    try:
        assert dialog.exec(*args) == QtWidgets.QDialog.DialogCode.Rejected
        assert observed == [(True, True, True, True)]
    finally:
        parent.close()


def test_projector_details_has_one_close_command(settings, qtbot):
    from openlp.core.projectors.db import Projector
    from openlp.core.widgets import fluent
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.resize(1200, 900)
    parent.show()
    dialog = ProjectorEditForm(parent, MagicMock())
    dialog.setAnimationEnabled(False)
    observed = []

    def dismiss():
        observed.append(([button.text() for button in dialog._native_commands.values() if button.isVisible()],
                         dialog.defaultButton(), dialog.name_text.isReadOnly()))
        dialog._native_commands['close'].click()

    QtCore.QTimer.singleShot(0, dismiss)
    projector = Projector(name='Projector', ip='192.168.1.2', port=4352, pin='', location='', notes='')
    dialog.exec(projector, edit=False)
    assert observed == [(['Close'], fluent.fluentqt.ContentDialogButton.Close, True)]
