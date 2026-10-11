# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
Package to test the openlp.core.ui.shortcutform package.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.ui.shortcutlistform import ShortcutListForm, _qobject_is_alive


@pytest.fixture()
def form(mock_settings, qtbot):
    frm = ShortcutListForm()
    qtbot.addWidget(frm)
    return frm


def test_adjust_button(form):
    """
    Test the _adjust_button() method
    """
    # GIVEN: A button.
    button = QtWidgets.QPushButton()
    checked = True
    enabled = True
    text = 'new!'

    # WHEN: Call the method.
    with patch('openlp.core.widgets.fluent.QPushButton.setChecked') as mocked_check_method:
        form._adjust_button(button, checked, enabled, text)

        # THEN: The button should be changed.
        assert button.text() == text, 'The text should match.'
        mocked_check_method.assert_called_once_with(True)
        assert button.isEnabled() == enabled, 'The button should be disabled.'


def test_space_key_press_event(form):
    """
    Test the keyPressEvent when the spacebar was pressed
    """
    # GIVEN: A key event that is a space
    mocked_event = MagicMock()
    mocked_event.key.return_value = QtCore.Qt.Key.Key_Space

    # WHEN: The event is handled
    with patch.object(form, '_capture_key') as mocked_key_release_event:
        form.keyPressEvent(mocked_event)

        # THEN: The key should be released
        mocked_key_release_event.assert_called_with(mocked_event)
        assert 0 == mocked_event.accept.call_count


def test_primary_push_button_checked_key_press_event(form):
    """
    Test the keyPressEvent when the primary push button is checked
    """
    # GIVEN: The primary push button is checked
    with patch.object(form, '_capture_key') as mocked_key_release_event, \
            patch.object(form.primary_push_button, 'isChecked') as mocked_is_checked:
        mocked_is_checked.return_value = True
        mocked_event = MagicMock()

        # WHEN: The event is handled
        form.keyPressEvent(mocked_event)

        # THEN: The key should be released
        mocked_key_release_event.assert_called_with(mocked_event)
        assert 0 == mocked_event.accept.call_count


def test_alternate_push_button_checked_key_press_event(form):
    """
    Test the keyPressEvent when the alternate push button is checked
    """
    # GIVEN: The primary push button is checked
    with patch.object(form, '_capture_key') as mocked_key_release_event, \
            patch.object(form.alternate_push_button, 'isChecked') as mocked_is_checked:
        mocked_is_checked.return_value = True
        mocked_event = MagicMock()

        # WHEN: The event is handled
        form.keyPressEvent(mocked_event)

        # THEN: The key should be released
        mocked_key_release_event.assert_called_with(mocked_event)
        assert 0 == mocked_event.accept.call_count


def test_escape_key_press_event(form):
    """
    Test the keyPressEvent when the escape key was pressed
    """
    # GIVEN: A key event that is an escape
    mocked_event = MagicMock()
    mocked_event.key.return_value = QtCore.Qt.Key.Key_Escape

    # WHEN: The event is handled
    with patch.object(form, 'close') as mocked_close:
        form.keyPressEvent(mocked_event)

        # THEN: The key should be released
        mocked_event.accept.assert_called_with()
        mocked_close.assert_called_with()


def test_action_shortcuts_returns_empty_when_shortcuts_raises_runtime_error(form):
    """
    A destroyed QAction must not crash _action_shortcuts (regression: shiboken deleted object).
    """
    action = MagicMock()
    action.shortcuts.side_effect = RuntimeError('Internal C++ object already deleted.')
    with patch('openlp.core.ui.shortcutlistform._qobject_is_alive', return_value=True):
        assert form._action_shortcuts(action) == []


def test_qobject_is_alive_none():
    assert _qobject_is_alive(None) is False


@pytest.fixture()
def shortcut_form(settings, qtbot, monkeypatch):
    """Exercise native controls with real actions while isolating the global action registry."""
    window = ShortcutListForm()
    qtbot.addWidget(window)
    actions = []
    for name, caption, default in [('test_new', 'New Service', 'Ctrl+N'),
                                   ('test_open', 'Open Service', 'Ctrl+O')]:
        action = QtGui.QAction(caption, window)
        action.setObjectName(name)
        action.default_shortcuts = [QtGui.QKeySequence(default)]
        action.setShortcuts(action.default_shortcuts)
        actions.append(action)
    window.action_list = SimpleNamespace(categories=[SimpleNamespace(name='File', actions=actions)],
                                         update_shortcut_map=MagicMock())
    window.warning_mock = MagicMock(return_value=QtWidgets.QMessageBox.StandardButton.Ok)
    monkeypatch.setattr('openlp.core.ui.shortcutlistform.QtWidgets.QMessageBox.warning', window.warning_mock)
    window.reload_shortcut_list()
    return window


def test_native_window_and_labelled_shortcut_controls(shortcut_form):
    import fluentqt
    assert isinstance(shortcut_form, fluentqt.Window)
    assert isinstance(shortcut_form.shortcut_grid, fluentqt.DataGrid)
    assert shortcut_form.windowTitle() == 'Shortcuts'
    assert shortcut_form.titleBar().contentWidget().text() == 'Shortcuts'
    assert shortcut_form.primary_label.text() == 'Primary'
    assert shortcut_form.alternate_label.text() == 'Alternate'
    assert shortcut_form.alternate_push_button.text() == 'Set shortcut'
    assert shortcut_form.clear_primary_button.text() == 'Clear'
    assert shortcut_form.clear_alternate_button.text() == 'Clear'
    assert shortcut_form.editor_command_bar.primaryActions() == [shortcut_form.restore_action]
    assert shortcut_form.list_command_bar.primaryActions() == [shortcut_form.restore_all_action]
    assert not hasattr(shortcut_form, 'default_radio_button')
    assert shortcut_form.save_button.text() == 'Save changes'


def test_capture_primary_and_alternate_are_drafts(shortcut_form, qtbot):
    shortcut_form.show()
    action = shortcut_form._current_item_action()
    triggered = MagicMock()
    action.triggered.connect(triggered)
    shortcut_form.addAction(action)
    button = shortcut_form.primary_push_button
    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    assert button.text() == 'Press shortcut…'
    qtbot.keyClick(button, QtCore.Qt.Key.Key_N, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert shortcut_form._action_shortcuts(action) == [QtGui.QKeySequence('Ctrl+N')]
    triggered.assert_not_called()
    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(button, QtCore.Qt.Key.Key_K, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert not button.isChecked()
    button = shortcut_form.alternate_push_button
    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(button, QtCore.Qt.Key.Key_J, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert shortcut_form._action_shortcuts(action) == [QtGui.QKeySequence('Ctrl+K'), QtGui.QKeySequence('Ctrl+J')]
    assert action.shortcuts() == [QtGui.QKeySequence('Ctrl+N')]
    item = shortcut_form.shortcut_grid.currentItem()
    assert shortcut_form.shortcut_grid.item(item.row(), 1).text() == shortcut_form.primary_push_button.text()
    assert shortcut_form.shortcut_grid.item(item.row(), 2).text() == shortcut_form.alternate_push_button.text()


@pytest.mark.parametrize('key', [QtCore.Qt.Key.Key_Space, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Escape])
def test_capture_special_keys(shortcut_form, qtbot, key):
    shortcut_form.show()
    button = shortcut_form.primary_push_button
    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(button, key)
    assert shortcut_form._action_shortcuts(shortcut_form._current_item_action()) == [QtGui.QKeySequence(key)]
    assert not button.isChecked()
    assert shortcut_form.isVisible()


def test_cancel_capture_and_change_selection_do_not_edit(shortcut_form, qtbot):
    shortcut_form.show()
    primary = shortcut_form.primary_push_button
    alternate = shortcut_form.alternate_push_button
    qtbot.mouseClick(primary, QtCore.Qt.MouseButton.LeftButton)
    qtbot.mouseClick(primary, QtCore.Qt.MouseButton.LeftButton)
    assert shortcut_form.changed_actions == {}
    qtbot.mouseClick(primary, QtCore.Qt.MouseButton.LeftButton)
    qtbot.mouseClick(alternate, QtCore.Qt.MouseButton.LeftButton)
    assert not primary.isChecked()
    assert primary.text() != 'Press shortcut…'
    shortcut_form.shortcut_grid.setCurrentItem(shortcut_form.shortcut_grid.item(1, 0))
    assert not alternate.isChecked()
    assert shortcut_form.changed_actions == {}


def test_conflicting_shortcut_keeps_capture_active(shortcut_form, qtbot):
    shortcut_form.show()
    button = shortcut_form.primary_push_button
    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(button, QtCore.Qt.Key.Key_O, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert button.isChecked()
    assert shortcut_form.changed_actions == {}
    shortcut_form.warning_mock.assert_called_once()
    assert shortcut_form.warning_mock.call_args.args[0] is shortcut_form


def test_datagrid_alternate_cell_starts_capture_for_correct_action(shortcut_form, qtbot):
    """Double-clicking a key cell selects its action and captures the corresponding shortcut."""
    shortcut_form.show()
    grid = shortcut_form.shortcut_grid
    cell = grid.item(1, 2)
    qtbot.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=grid.visualItemRect(cell).center())
    qtbot.mouseDClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=grid.visualItemRect(cell).center())
    assert shortcut_form.action_label.text() == 'Open Service'
    assert shortcut_form.alternate_push_button.isChecked()
    qtbot.keyClick(shortcut_form.alternate_push_button, QtCore.Qt.Key.Key_K,
                   QtCore.Qt.KeyboardModifier.ControlModifier)
    action = shortcut_form.action_list.categories[0].actions[1]
    assert shortcut_form._action_shortcuts(action) == [QtGui.QKeySequence('Ctrl+O'), QtGui.QKeySequence('Ctrl+K')]


def test_search_preserves_drafts_and_filters_keys_categories(shortcut_form):
    action = shortcut_form._current_item_action()
    shortcut_form.changed_actions[action] = [QtGui.QKeySequence('Ctrl+K')]
    shortcut_form.refresh_shortcut_list()
    grid = shortcut_form.shortcut_grid
    shortcut_form.search_edit.setText('open')
    assert grid.isRowHidden(0) and not grid.isRowHidden(1)
    assert shortcut_form.action_label.text() == 'Open Service'
    shortcut_form.search_edit.setText('Ctrl+K')
    assert not grid.isRowHidden(0) and grid.isRowHidden(1)
    shortcut_form.search_edit.setText('no such action')
    assert shortcut_form.shortcut_grid.currentItem() is None
    assert shortcut_form.editor_controls.isHidden()
    shortcut_form.search_edit.setText('FILE')
    assert not grid.isRowHidden(0) and not grid.isRowHidden(1)
    assert shortcut_form._action_shortcuts(action) == [QtGui.QKeySequence('Ctrl+K')]


def test_clear_and_restore_selected_action(shortcut_form, qtbot):
    shortcut_form.show()
    action = shortcut_form._current_item_action()
    other = shortcut_form.action_list.categories[0].actions[1]
    shortcut_form.changed_actions[action] = [QtGui.QKeySequence('Ctrl+K'), QtGui.QKeySequence('Ctrl+J')]
    shortcut_form.changed_actions[other] = [QtGui.QKeySequence('Ctrl+L')]
    shortcut_form.refresh_shortcut_list()
    qtbot.mouseClick(shortcut_form.clear_primary_button, QtCore.Qt.MouseButton.LeftButton)
    assert shortcut_form._action_shortcuts(action) == [QtGui.QKeySequence('Ctrl+J')]
    assert shortcut_form.alternate_push_button.text() == 'Set shortcut'
    qtbot.mouseClick(shortcut_form.clear_primary_button, QtCore.Qt.MouseButton.LeftButton)
    assert shortcut_form._action_shortcuts(action) == []
    assert shortcut_form.primary_push_button.text() == 'Set shortcut'
    shortcut_form.restore_action.trigger()
    assert shortcut_form._action_shortcuts(action) == action.default_shortcuts
    assert shortcut_form._action_shortcuts(other) == [QtGui.QKeySequence('Ctrl+L')]
    assert action.shortcuts() == action.default_shortcuts


def test_restore_defaults_rejects_conflicting_pending_edits(shortcut_form):
    action, other = shortcut_form.action_list.categories[0].actions
    shortcut_form.changed_actions[action] = [QtGui.QKeySequence('Ctrl+K')]
    shortcut_form.changed_actions[other] = action.default_shortcuts
    shortcut_form.restore_action.trigger()
    assert shortcut_form._action_shortcuts(action) == [QtGui.QKeySequence('Ctrl+K')]
    shortcut_form.warning_mock.assert_called_once()


def test_restore_all_defaults_stays_in_draft_and_respects_confirmation(shortcut_form):
    action = shortcut_form._current_item_action()
    shortcut_form.changed_actions[action] = [QtGui.QKeySequence('Ctrl+K')]
    with patch('openlp.core.ui.shortcutlistform.QtWidgets.QMessageBox.question',
               return_value=QtWidgets.QMessageBox.StandardButton.No):
        shortcut_form.restore_all_action.trigger()
    assert shortcut_form._action_shortcuts(action) == [QtGui.QKeySequence('Ctrl+K')]
    with patch('openlp.core.ui.shortcutlistform.QtWidgets.QMessageBox.question',
               return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        shortcut_form.restore_all_action.trigger()
    assert shortcut_form._action_shortcuts(action) == action.default_shortcuts
    shortcut_form.reject()
    assert shortcut_form.changed_actions == {}


@pytest.mark.parametrize('exit_method', ['accept', 'reject', 'close', 'escape'])
def test_modal_save_cancel_and_opening_size(shortcut_form, settings, qtbot, exit_method):
    action = shortcut_form.action_list.categories[0].actions[0]
    opening_sizes = []

    def edit_and_finish():
        try:
            opening_sizes.append((shortcut_form.size(), shortcut_form.windowHandle().size()))
            shortcut_form.changed_actions[action] = [QtGui.QKeySequence('Ctrl+K')]
            if exit_method == 'escape':
                qtbot.keyClick(shortcut_form.search_edit, QtCore.Qt.Key.Key_Escape)
            else:
                getattr(shortcut_form, exit_method)()
            assert not shortcut_form.isVisible()
        finally:
            if shortcut_form.isVisible():
                shortcut_form.reject()

    QtCore.QTimer.singleShot(50, edit_and_finish)
    result = shortcut_form.exec()
    assert opening_sizes == [(QtCore.QSize(1100, 760), QtCore.QSize(1100, 760))]
    assert result == (QtWidgets.QDialog.DialogCode.Accepted if exit_method == 'accept'
                      else QtWidgets.QDialog.DialogCode.Rejected)
    # Preserve the main window's existing exec-then-save contract.
    if result:
        shortcut_form.save()
    assert action.shortcuts() == [QtGui.QKeySequence('Ctrl+K' if result else 'Ctrl+N')]
    assert settings.contains('shortcuts/test_new') == bool(result)
    QtCore.QTimer.singleShot(50, shortcut_form.reject)
    shortcut_form.exec()
    assert shortcut_form.changed_actions == {}
