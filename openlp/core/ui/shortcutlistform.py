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
The :mod:`~openlp.core.ui.shortcutlistform` module contains the form class
"""
import logging
import re

from PySide6 import QtCore, QtGui
from fluentqt import Window as FluentWindow
from openlp.core.widgets import fluent as QtWidgets
from shiboken6 import isValid as qobject_cpp_is_valid

from openlp.core.common.actions import ActionList
from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.ui.shortcutlistdialog import Ui_ShortcutListDialog


REMOVE_AMPERSAND = re.compile(r'&')

log = logging.getLogger(__name__)


def _qobject_is_alive(obj):
    """
    Return True if ``obj`` is a Qt wrapper whose underlying C++ object still exists.

    After a ``QAction`` is destroyed, Python may still hold references (e.g. in tree item
    ``UserRole`` data); calling methods raises ``RuntimeError``.
    """
    if obj is None:
        return False
    try:
        return qobject_cpp_is_valid(obj)
    except (TypeError, AttributeError):
        return False


class ShortcutListForm(FluentWindow, Ui_ShortcutListDialog, RegistryProperties):
    """Edit a shortcut draft in a native Fluent window; Save applies it to actions."""
    accepted = QtCore.Signal()
    rejected = QtCore.Signal()
    finished = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._event_loop = None
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        self.setup_ui(self)
        self.changed_actions = {}
        self.action_list = ActionList.get_instance()
        self.primary_push_button.toggled.connect(self.on_primary_push_button_clicked)
        self.alternate_push_button.toggled.connect(self.on_alternate_push_button_clicked)
        self.shortcut_grid.currentItemChanged.connect(self.on_current_item_changed)
        self.shortcut_grid.itemDoubleClicked.connect(lambda item: self.on_item_double_clicked(item, item.column()))
        self.search_edit.textChanged.connect(self._filter_shortcuts)
        self.clear_primary_button.clicked.connect(lambda: self._clear_shortcut(0))
        self.clear_alternate_button.clicked.connect(lambda: self._clear_shortcut(1))
        self.restore_action.triggered.connect(self.on_restore_action_clicked)
        self.restore_all_action.triggered.connect(self.on_restore_defaults_clicked)
        self.on_current_item_changed()

    def exec(self):
        self.changed_actions = {}
        self.search_edit.clear()
        self.reload_shortcut_list()
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        loop = QtCore.QEventLoop(self)
        self._event_loop = loop
        try:
            self.ensurePolished()
            self.layout().activate()
            self.resize(1100, 760)
            self.show()
            self.raise_()
            self.activateWindow()
            loop.exec()
        finally:
            self._event_loop = None
            loop.deleteLater()
        return self._result

    def result(self):
        return self._result

    def done(self, result):
        self._result = result
        self._stop_capture()
        self.hide()
        if self._event_loop is not None:
            self._event_loop.quit()
        if result == QtWidgets.QDialog.DialogCode.Accepted:
            self.accepted.emit()
        else:
            self.rejected.emit()
        self.finished.emit(result)

    def accept(self):
        self.done(QtWidgets.QDialog.DialogCode.Accepted)

    def reject(self):
        self.changed_actions = {}
        self.done(QtWidgets.QDialog.DialogCode.Rejected)

    def closeEvent(self, event):
        self.reject()
        event.accept()

    def _is_capturing(self):
        return self.primary_push_button.isChecked() or self.alternate_push_button.isChecked()

    def event(self, event):
        # Reserve application shortcuts such as Ctrl+S while recording their keys.
        if (event.type() == QtCore.QEvent.Type.ShortcutOverride and hasattr(self, 'primary_push_button')
                and self._is_capturing()):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Space or self._is_capturing():
            self._capture_key(event)
        elif event.key() == QtCore.Qt.Key.Key_Escape:
            event.accept()
            self.close()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self._is_capturing():
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def _capture_key(self, event):
        if not self._is_capturing():
            return
        event.accept()
        if event.isAutoRepeat():
            return
        if event.key() in (QtCore.Qt.Key.Key_Shift, QtCore.Qt.Key.Key_Control,
                           QtCore.Qt.Key.Key_Meta, QtCore.Qt.Key.Key_Alt):
            return
        action = self._current_item_action()
        if action is None:
            return
        key_sequence = QtGui.QKeySequence(event.keyCombination())
        if not self._validiate_shortcut(action, key_sequence):
            return
        shortcuts = self._action_shortcuts(action)
        if self.primary_push_button.isChecked():
            new_shortcuts = [key_sequence] + shortcuts[1:2]
        else:
            new_shortcuts = shortcuts[:1] + [key_sequence]
        self.changed_actions[action] = new_shortcuts
        self._stop_capture()
        self.refresh_shortcut_list()
        event.accept()

    def _stop_capture(self):
        for button in (self.primary_push_button, self.alternate_push_button):
            blocked = button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(blocked)

    def _toggle_capture(self, button, other, toggled):
        if toggled:
            blocked = other.blockSignals(True)
            other.setChecked(False)
            other.blockSignals(blocked)
            self.on_current_item_changed()
            button.setFocus()
        else:
            self.on_current_item_changed()

    def on_primary_push_button_clicked(self, toggled):
        self._toggle_capture(self.primary_push_button, self.alternate_push_button, toggled)

    def on_alternate_push_button_clicked(self, toggled):
        self._toggle_capture(self.alternate_push_button, self.primary_push_button, toggled)

    def on_item_double_clicked(self, item, column):
        if self._current_item_action(item) is not None:
            button = self.alternate_push_button if column == 2 else self.primary_push_button
            button.setChecked(True)
            button.setFocus()

    def reload_shortcut_list(self):
        self._stop_capture()
        self.shortcut_grid.setRowCount(0)
        for category in self.action_list.categories:
            if category.name is None:
                continue
            for action in category.actions:
                if not _qobject_is_alive(action):
                    continue
                row = self.shortcut_grid.rowCount()
                self.shortcut_grid.insertRow(row)
                action_text = REMOVE_AMPERSAND.sub('', action.text())
                for column, text in enumerate((action_text, '', '', category.name)):
                    self.shortcut_grid.setItem(row, column, QtWidgets.QTableWidgetItem(text))
                item = self.shortcut_grid.item(row, 0)
                item.setIcon(action.icon())
                item.setData(QtCore.Qt.ItemDataRole.UserRole, action)
                if action.toolTip() != action_text:
                    for column in range(4):
                        self.shortcut_grid.item(row, column).setToolTip(action.toolTip())
        self.shortcut_grid.resizeRowsToContents()
        self.refresh_shortcut_list()

    def refresh_shortcut_list(self):
        for row in range(self.shortcut_grid.rowCount()):
            action = self._current_item_action(self.shortcut_grid.item(row, 0))
            if action is None:
                continue
            shortcuts = self._action_shortcuts(action)
            for index in range(2):
                self.shortcut_grid.item(row, index + 1).setText(
                    self.get_shortcut_string(shortcuts[index], for_display=True) if index < len(shortcuts) else '')
        self._filter_shortcuts()

    def _filter_shortcuts(self):
        query = self.search_edit.text().strip().casefold()
        first_match = None
        for row in range(self.shortcut_grid.rowCount()):
            action = self._current_item_action(self.shortcut_grid.item(row, 0))
            texts = [self.shortcut_grid.item(row, column).text() for column in range(4)]
            texts.extend(self.get_shortcut_string(sequence) for sequence in self._action_shortcuts(action))
            matches = any(query in text.casefold() for text in texts)
            self.shortcut_grid.setRowHidden(row, not matches)
            if matches and first_match is None:
                first_match = row
        current = self.shortcut_grid.currentRow()
        if current < 0 or self.shortcut_grid.isRowHidden(current):
            self._stop_capture()
            self.shortcut_grid.clearSelection()
            self.shortcut_grid.setCurrentIndex(QtCore.QModelIndex())
            if first_match is not None:
                self.shortcut_grid.selectRow(first_match)
        self.on_current_item_changed()

    def on_current_item_changed(self, item=None, previousItem=None):
        if item is not None:
            self._stop_capture()
        action = self._current_item_action(item)
        if action is None:
            self._stop_capture()
        self.editor_controls.setVisible(action is not None)
        self.restore_action.setEnabled(action is not None)
        self.primary_push_button.setEnabled(action is not None)
        self.alternate_push_button.setEnabled(action is not None)
        self.action_label.setText(REMOVE_AMPERSAND.sub('', action.text()) if action is not None
                                  else translate('OpenLP.ShortcutListDialog', 'No action selected'))
        shortcuts = self._action_shortcuts(action)
        for index, (button, clear) in enumerate(((self.primary_push_button, self.clear_primary_button),
                                                (self.alternate_push_button, self.clear_alternate_button))):
            button.setText(self.get_shortcut_string(shortcuts[index], for_display=True)
                           if index < len(shortcuts) else '')
            clear.setEnabled(index < len(shortcuts))

    def _clear_shortcut(self, index):
        action = self._current_item_action()
        if action is None:
            return
        self._stop_capture()
        shortcuts = self._action_shortcuts(action)
        self.changed_actions[action] = shortcuts[:index] + shortcuts[index + 1:]
        self.refresh_shortcut_list()

    def on_restore_action_clicked(self):
        action = self._current_item_action()
        if action is None:
            return
        self._stop_capture()
        # Check defaults against pending edits of other actions before restoring.
        previous = self.changed_actions.get(action)
        self.changed_actions[action] = []
        if all(self._validiate_shortcut(action, sequence) for sequence in action.default_shortcuts):
            self.changed_actions[action] = list(action.default_shortcuts)
        elif previous is None:
            del self.changed_actions[action]
        else:
            self.changed_actions[action] = previous
        self.refresh_shortcut_list()

    def on_restore_defaults_clicked(self):
        if QtWidgets.QMessageBox.question(
                self, translate('OpenLP.ShortcutListDialog', 'Restore all defaults'),
                translate('OpenLP.ShortcutListDialog', 'Restore all shortcuts to their defaults?')) != \
                QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._stop_capture()
        for category in self.action_list.categories:
            if category.name is None:
                continue
            for action in category.actions:
                if _qobject_is_alive(action):
                    self.changed_actions[action] = list(action.default_shortcuts)
        self.refresh_shortcut_list()

    def save(self):
        """
        Save the shortcuts. **Note**, that we do not have to load the shortcuts, as they are loaded in
        :class:`~openlp.core.utils.ActionList`.
        """
        self._prune_stale_changed_actions()
        for category in self.action_list.categories:
            # Check if the category is for internal use only.
            if category.name is None:
                continue
            for action in category.actions:
                if not _qobject_is_alive(action):
                    continue
                if action in self.changed_actions:
                    try:
                        old_shortcuts = list(map(self.get_shortcut_string, action.shortcuts()))
                    except RuntimeError:
                        old_shortcuts = []
                    action.setShortcuts(self.changed_actions[action])
                    self.action_list.update_shortcut_map(action, old_shortcuts)
                try:
                    self.settings.setValue('shortcuts/' + action.objectName(), action.shortcuts())
                except RuntimeError:
                    log.warning('Could not save shortcuts for a QAction that was destroyed.')

    def _validiate_shortcut(self, changing_action, key_sequence):
        """
        Checks if the given ``changing_action `` can use the given ``key_sequence``. Returns ``True`` if the
        ``key_sequence`` can be used by the action, otherwise displays a dialog and returns ``False``.

        :param changing_action: The action which wants to use the ``key_sequence``.
        :param key_sequence: The key sequence which the action want so use.
        """
        if changing_action is None or not _qobject_is_alive(changing_action):
            return False
        if not key_sequence:
            return False
        is_valid = True
        try:
            changing_parent = changing_action.parent()
            changing_context = changing_action.shortcutContext()
        except RuntimeError:
            return False
        for category in self.action_list.categories:
            for action in category.actions:
                if not _qobject_is_alive(action):
                    continue
                shortcuts = self._action_shortcuts(action)
                if key_sequence not in shortcuts:
                    continue
                if action is changing_action:
                    if self.primary_push_button.isChecked() and shortcuts.index(key_sequence) == 0:
                        continue
                    if self.alternate_push_button.isChecked() and shortcuts.index(key_sequence) == 1:
                        continue
                try:
                    action_parent = action.parent()
                    action_context = action.shortcutContext()
                except RuntimeError:
                    continue
                # Have the same parent, thus they cannot have the same shortcut.
                if action_parent is changing_parent:
                    is_valid = False
                # The new shortcut is already assigned, but if both shortcuts are only valid in a different widget the
                # new shortcut is valid, because they will not interfere.
                if action_context in [QtCore.Qt.ShortcutContext.WindowShortcut,
                                      QtCore.Qt.ShortcutContext.ApplicationShortcut]:
                    is_valid = False
                if changing_context in [QtCore.Qt.ShortcutContext.WindowShortcut,
                                        QtCore.Qt.ShortcutContext.ApplicationShortcut]:
                    is_valid = False
        if not is_valid:
            text = translate('OpenLP.ShortcutListDialog',
                             'The shortcut "{key}" is already assigned to another action. '
                             'Please use a different shortcut.'
                             ).format(key=self.get_shortcut_string(key_sequence))
            QtWidgets.QMessageBox.warning(self, translate('OpenLP.ShortcutListDialog', 'Duplicate shortcut'), text)
        return is_valid

    def _action_shortcuts(self, action):
        """
        This returns the shortcuts for the given ``action``, which also includes those shortcuts which are not saved
        yet but already assigned (as changes are applied when closing the dialog).
        """
        if action is None or not _qobject_is_alive(action):
            return []
        if action in self.changed_actions:
            return self.changed_actions[action]
        try:
            return action.shortcuts()
        except RuntimeError:
            log.debug('QAction.shortcuts() failed (object likely destroyed).')
            return []

    def _prune_stale_changed_actions(self):
        """Remove pending edits whose QAction has been destroyed."""
        for dead in [a for a in list(self.changed_actions.keys()) if not _qobject_is_alive(a)]:
            del self.changed_actions[dead]

    def _current_item_action(self, item=None):
        """
        Returns the action of the given ``item``. If no item is given, we return the action of the current item of
        the shortcut grid.
        """
        if item is None:
            item = self.shortcut_grid.currentItem()
            if item is None:
                return None
        item = self.shortcut_grid.item(item.row(), 0)
        action = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if action is None:
            return None
        if not _qobject_is_alive(action):
            item.setData(QtCore.Qt.ItemDataRole.UserRole, None)
            return None
        return action

    def _adjust_button(self, button, checked=None, enabled=None, text=None):
        """
        Can be called to adjust more properties of the given ``button`` at once.
        """
        # Set the text before checking the button, because this emits a signal.
        if text is not None:
            button.setText(text)
        if checked is not None:
            button.setChecked(checked)
        if enabled is not None:
            button.setEnabled(enabled)

    @staticmethod
    def get_shortcut_string(shortcut, for_display=False):
        if for_display:
            if any(modifier in shortcut.toString() for modifier in ['Ctrl', 'Alt', 'Meta', 'Shift']):
                sequence_format = QtGui.QKeySequence.SequenceFormat.NativeText
            else:
                sequence_format = QtGui.QKeySequence.SequenceFormat.PortableText
        else:
            sequence_format = QtGui.QKeySequence.SequenceFormat.PortableText
        return shortcut.toString(sequence_format)
