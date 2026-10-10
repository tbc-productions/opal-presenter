"""Selection and clipboard operations across the designer's editable slide rows."""
import copy
import json
import uuid

from PySide6 import QtCore, QtGui

from openlp.core.widgets import fluent as QtWidgets
from openlp.core.lib.slidelayouts import layout_for_slide


ROWS_MIME = 'application/x-openlp-slide-rows'
TEXT_MIME = 'application/x-openlp-slide-text'


def text_slice(text, start, end=None):
    return text.encode('utf-16-le')[start * 2:None if end is None else end * 2].decode('utf-16-le')


class SlideSelection:
    """Mixed text and whole-slide selection, without changing the portable source format."""
    def setup_selection(self):
        self.selected_slide_rows = set()
        self.text_range = None
        self.drag_anchor = None
        self.row_anchor = 0
        self._drag_point = None
        self._selection_scroll = QtCore.QTimer(self)
        self._selection_scroll.setInterval(40)
        self._selection_scroll.timeout.connect(self.scroll_selection)
        self.cell_editor._editor.viewport().installEventFilter(self)

    def has_grid_selection(self):
        return bool(self.selected_slide_rows or self.text_range)

    def update_selection_display(self):
        selected = self.has_grid_selection()
        if selected:
            self.cell_editor.hide()
            self.setFocus()
        else:
            self.position_editor()
        for action in self.formatting_bar.actions():
            if action not in [self.source_action, *self.designer.history_actions]:
                action.setEnabled(not selected and not self.source_action.isChecked())
        self.viewport().update()

    def clear_grid_selection(self):
        self.selected_slide_rows.clear()
        self.text_range = None
        self.update_selection_display()

    def select_slide_rows(self, rows):
        self.text_range = None
        self.selected_slide_rows = {row for row in rows if 0 <= row < len(self.rows)}
        self.update_selection_display()

    def select_text_range(self, anchor, end):
        self.selected_slide_rows.clear()
        self.text_range = (anchor, end) if anchor != end else None
        self.update_selection_display()

    def selected_text_offsets(self, row):
        from .slidegrid import qt_length
        length = qt_length(self.row_text(self.rows[row]))
        if row in self.selected_slide_rows:
            return 0, length
        if self.text_range:
            first, last = sorted(self.text_range)
            if first[0] <= row <= last[0]:
                return first[1] if row == first[0] else 0, last[1] if row == last[0] else length
        return None

    def selection_paint_context(self, row, editor, palette):
        offsets = self.selected_text_offsets(row)
        if offsets is None:
            return []
        selection = QtGui.QAbstractTextDocumentLayout.Selection()
        cursor = QtGui.QTextCursor(editor.document())
        cursor.setPosition(offsets[0])
        cursor.setPosition(offsets[1], QtGui.QTextCursor.MoveMode.KeepAnchor)
        selection.cursor = cursor
        colours = self.active_indicator.theme_tokens().colors
        selection.format.setBackground(colours.accentDefault)
        selection.format.setForeground(colours.textOnAccent)
        selection.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection,
                                     row in self.selected_slide_rows)
        return [selection]

    def point_endpoint(self, point):
        row = self.rowAt(max(0, min(point.y(), self.viewport().height() - 1)))
        if row < 0:
            row = 0 if point.y() < 0 else len(self.rows) - 1
        rect = self.visualRect(self.model().index(row, 0))
        editor = self.measure_editor(row, rect.width())
        position = editor.document().documentLayout().hitTest(
            QtCore.QPointF(point - rect.topLeft()), QtCore.Qt.HitTestAccuracy.FuzzyHit)
        return row, max(0, min(editor.document().characterCount() - 1, position))

    def selection_press(self, point, modifiers):
        endpoint = self.point_endpoint(point)
        row = endpoint[0]
        if modifiers & (QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.MetaModifier):
            selected = self.selected_slide_rows or {self.active_row}
            self.select_slide_rows(selected ^ {row})
            self.row_anchor = row
            return True
        if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
            self.select_slide_rows(range(min(self.row_anchor, row), max(self.row_anchor, row) + 1))
            return True
        self.clear_grid_selection()
        self.row_anchor = row
        self.drag_anchor = endpoint
        return False

    def selection_move(self, point):
        if self.drag_anchor is None:
            return False
        self._drag_point = point
        endpoint = self.point_endpoint(point)
        if endpoint[0] != self.drag_anchor[0] or self.text_range:
            self.select_text_range(self.drag_anchor, endpoint)
            if QtWidgets.QWidget.mouseGrabber() is not self.viewport():
                self.viewport().grabMouse()
            self._selection_scroll.start()
            return True
        return False

    def selection_release(self):
        selected = bool(self.text_range)
        self.drag_anchor = None
        self._selection_scroll.stop()
        if QtWidgets.QWidget.mouseGrabber() is self.viewport():
            self.viewport().releaseMouse()
        return selected

    def scroll_selection(self):
        if self.drag_anchor is None or self._drag_point is None:
            self._selection_scroll.stop()
            return
        y = self._drag_point.y()
        delta = -18 if y < 16 else 18 if y > self.viewport().height() - 16 else 0
        if delta:
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() + delta)
            self.select_text_range(self.drag_anchor, self.point_endpoint(self._drag_point))

    def source_endpoint(self, endpoint):
        from .slidegrid import heading_text, qt_length
        index, position = endpoint
        row = self.rows[index]
        prefix = qt_length(heading_text(row.label) + '\n') if self.kind == 'song' and row.split == 0 else 0
        if position < prefix:
            return qt_length(self.source.toPlainText()[:row.boundary])
        return qt_length(self.source.toPlainText()[:row.start]) + position - prefix

    def row_records(self):
        source = self.source.toPlainText()
        document = self.designer.document
        records = []
        keys = set(document.get('assignments', {})) | set(document.get('overrides', {}))
        keys.update(document.get('hidden_footers', []))
        for index, row in enumerate(self.rows):
            prefix = self.page_prefix(row, index)
            state = {}
            for key in keys:
                if not key.startswith(prefix):
                    continue
                page = key[len(prefix):]
                layout = layout_for_slide(document, key)
                state[page] = {'layout': layout, 'override': document.get('overrides', {}).get(key),
                               'hidden': key in document.get('hidden_footers', []),
                               'master': document.get('masters', {}).get(layout)}
            records.append({'label': row.label, 'section': row.section, 'text': source[row.start:row.end],
                            'state': copy.deepcopy(state)})
        return records

    def page_prefix(self, row, index):
        section = (f'custom-{getattr(self.form, "designer_slide_offset", 0) + index + 1}'
                   if self.kind == 'custom' else row.label.lower())
        return f'{section}:{row.split}:'

    def apply_rows(self, records, focus=0):
        """Move row-local designs and footer settings with their content in one undo step."""
        from .slidegrid import ContentCommand, qt_length, slide_rows
        from openlp.core.lib.slidedesign import normalise_design
        before, original = self.source.toPlainText(), copy.deepcopy(self.designer.document)
        after = self.serialise_rows(records)
        document = copy.deepcopy(original)
        prefixes = tuple(self.page_prefix(row, i) for i, row in enumerate(self.rows))
        for collection in ('assignments', 'overrides'):
            if collection in document:
                document[collection] = {key: value for key, value in document[collection].items()
                                        if not key.startswith(prefixes)}
        hidden = {key for key in document.get('hidden_footers', []) if not key.startswith(prefixes)}
        new_rows = slide_rows(after, self.kind, self.fallback_label())
        for i, (record, row) in enumerate(zip(records, new_rows)):
            state = record.get('state', {})
            if not isinstance(state, dict):
                continue
            for page, settings in state.items():
                if not isinstance(page, str) or not page.isdigit() or not isinstance(settings, dict):
                    continue
                key = self.page_prefix(row, i) + page
                layout, master = settings.get('layout', 'default'), settings.get('master')
                if not isinstance(layout, str):
                    continue
                if isinstance(master, dict):
                    masters = document.setdefault('masters', {})
                    if layout in masters and masters[layout] != master:
                        layout = uuid.uuid4().hex
                    masters[layout] = copy.deepcopy(master)
                if layout != layout_for_slide(document, key):
                    document.setdefault('assignments', {})[key] = layout
                if isinstance(settings.get('override'), dict):
                    document.setdefault('overrides', {})[key] = copy.deepcopy(settings['override'])
                if settings.get('hidden') is True:
                    hidden.add(key)
        if hidden:
            document['hidden_footers'] = sorted(hidden)
        else:
            document.pop('hidden_footers', None)
        if document:
            document['version'] = 1
        document = normalise_design(document)
        self.clear_grid_selection()
        if before == after and document == original:
            return
        self.record_history = True
        position = qt_length(after[:new_rows[min(focus, len(new_rows) - 1)].start])
        command = ContentCommand(self, before, after, self.source.textCursor().position(), position,
                                 original, self.current_tag(), self.current_tag())
        command.new_design = document
        self.designer.undo_stack.push(command)

    def serialise_rows(self, records):
        from .slidegrid import section_marker
        if self.kind == 'custom':
            return '\n[===]\n'.join(row['text'] for row in records)
        if self.form.has_single_verse:
            return '\n[--}{--]\n'.join(row['text'] for row in records)
        parts, previous = [], None
        for row in records:
            prefix = section_marker(row['label']) if row['section'] != previous else '[--}{--]\n'
            parts.append(prefix + row['text'])
            previous = row['section']
        return '\n'.join(parts)

    def copy_grid_selection(self):
        mime = QtCore.QMimeData()
        if self.selected_slide_rows:
            records = self.row_records()
            selected = [records[row] for row in sorted(self.selected_slide_rows)]
            mime.setData(ROWS_MIME, json.dumps({'kind': self.kind, 'rows': selected}).encode())
            mime.setText('\n\n'.join(self.row_text(self.rows[row]) for row in sorted(self.selected_slide_rows)))
        elif self.text_range:
            first, last = sorted(self.text_range)
            raw = text_slice(self.source.toPlainText(), self.source_endpoint(first), self.source_endpoint(last))
            mime.setData(TEXT_MIME, json.dumps({'kind': self.kind, 'text': raw}).encode())
            mime.setText('\n'.join(text_slice(self.row_text(self.rows[row]), *self.selected_text_offsets(row))
                                   for row in range(first[0], last[0] + 1)))
        else:
            return
        QtWidgets.QApplication.clipboard().setMimeData(mime)

    def replace_source_range(self, start, end, text):
        self.clear_grid_selection()
        self.record_history = True
        cursor = self.source.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        self.source.setTextCursor(cursor)
        self.cell_editor.setFocus()

    def delete_grid_selection(self):
        if self.selected_slide_rows:
            at = min(self.selected_slide_rows)
            records = [row for i, row in enumerate(self.row_records()) if i not in self.selected_slide_rows]
            self.apply_rows(records, focus=at)
        elif self.text_range:
            first, last = sorted(self.text_range)
            self.replace_source_range(self.source_endpoint(first), self.source_endpoint(last), '')

    def cut_grid_selection(self):
        self.copy_grid_selection()
        self.delete_grid_selection()

    def clipboard_payload(self, mime, kind):
        from openlp.plugins.songs.lib import VerseType
        try:
            value = json.loads(bytes(mime.data(kind)).decode())
            if value['kind'] == self.kind:
                if kind == TEXT_MIME and isinstance(value.get('text'), str):
                    return value['text']
                if kind == ROWS_MIME and isinstance(value.get('rows'), list):
                    rows = value['rows']
                    if rows and len(rows) <= 10000 and all(
                            isinstance(row, dict) and isinstance(row.get('text'), str)
                            and isinstance(row.get('section'), (int, str))
                            and isinstance(row.get('label'), str) and row['label']
                            and (self.kind == 'custom' or row['label'][0].lower() in VerseType.tags
                                 and row['label'][1:].isdigit() and int(row['label'][1:]) > 0)
                            for row in rows):
                        return rows
        except (ValueError, KeyError, TypeError, UnicodeError):
            pass
        return None

    def paste_grid(self, mime=None, after=False, insert=False):
        mime = mime or QtWidgets.QApplication.clipboard().mimeData()
        pasted = self.clipboard_payload(mime, ROWS_MIME)
        if pasted:
            identifier = uuid.uuid4().hex
            for row in pasted:
                row['section'] = f'{identifier}:{row["section"]}'
            records = self.row_records()
            at = ((max(self.selected_slide_rows) + 1 if after and insert else min(self.selected_slide_rows))
                  if self.selected_slide_rows else self.active_row + int(after))
            if not insert:
                records = [row for i, row in enumerate(records) if i not in self.selected_slide_rows]
            if len(records) == 1 and not records[0]['text']:
                records, at = [], 0
            records[at:at] = pasted
            self.apply_rows(records, focus=at)
            return True
        raw = self.clipboard_payload(mime, TEXT_MIME)
        if self.text_range:
            first, last = sorted(self.text_range)
            self.replace_source_range(self.source_endpoint(first), self.source_endpoint(last),
                                      raw if raw is not None else mime.text())
            return True
        if raw is not None:
            cursor = self.cell_editor.textCursor()
            start = self.source_endpoint((self.active_row, cursor.selectionStart()))
            end = self.source_endpoint((self.active_row, cursor.selectionEnd()))
            self.replace_source_range(start, end, raw)
            return True
        if self.selected_slide_rows:
            records = self.row_records()
            at = min(self.selected_slide_rows)
            records = [row for i, row in enumerate(records) if i not in self.selected_slide_rows]
            records.insert(at, {'label': self.fallback_label(), 'section': uuid.uuid4().hex, 'text': mime.text()})
            self.apply_rows(records, focus=at)
            return True
        return False

    def selection_key(self, event):
        for key, action in ((QtGui.QKeySequence.StandardKey.Copy, self.copy_grid_selection),
                            (QtGui.QKeySequence.StandardKey.Cut, self.cut_grid_selection),
                            (QtGui.QKeySequence.StandardKey.Paste, self.paste_grid),
                            (QtGui.QKeySequence.StandardKey.SelectAll,
                             lambda: self.select_slide_rows(range(len(self.rows))))):
            if event.matches(key):
                action()
                return True
        if event.key() in (QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace):
            self.delete_grid_selection()
            return True
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.clear_grid_selection()
            self.cell_editor.setFocus()
            return True
        command_modifiers = QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.MetaModifier
        if event.text() and not event.modifiers() & command_modifiers:
            mime = QtCore.QMimeData()
            mime.setText(event.text())
            self.paste_grid(mime)
            return True
        return False
