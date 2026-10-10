"""Editable slide rows over the existing portable lyrics source."""
import copy
import re
import time
from dataclasses import dataclass

import fluentqt
from PySide6 import QtCore, QtGui

from openlp.core.common.i18n import translate
from openlp.core.ui.fluenticons import fluent_icon
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.edits import FormattingTagDelegate
from openlp.plugins.songs.forms.editversedialog import SongLyricsTextEdit
from openlp.plugins.songs.lib import VerseType
from openlp.plugins.songs.lib.sectioncolors import (
    DEFAULT_SECTION_COLORS, color_from_settings, opacity_from_verse_number, section_key_from_verse_tag)
from openlp.core.common.registry import Registry
from .selection import SlideSelection


def tr(text):
    return translate('SlideDesigner.SlideGrid', text)


def qt_length(text):
    return len(text.encode('utf-16-le')) // 2


def heading_identity(text):
    """Recognise a complete section heading without mistaking lyrics for metadata."""
    for index, names in enumerate(zip(VerseType.names, VerseType.translated_names)):
        for name in names:
            match = re.fullmatch(re.escape(name).replace(r'\-', '[- ]?') + r'\s+(\d+)\s*:?', text.strip(), re.I)
            if match and int(match.group(1)) > 0:
                return VerseType.tags[index].upper() + match.group(1)
    return None


def heading_text(label):
    return f'{VerseType.translated_name(label[0].lower())} {label[1:]}'


def section_marker(label):
    return f'---[{VerseType.translated_name(label[0].lower())}:{label[1:]}]---\n'


def section_colour(label):
    try:
        return color_from_settings(Registry().get('settings'), label[0], label[1:])
    except KeyError:
        # Editors can be constructed before the songs plugin installs its settings.
        colour = QtGui.QColor(DEFAULT_SECTION_COLORS[section_key_from_verse_tag(label[0])])
        colour.setAlphaF(opacity_from_verse_number(label[1:]))
        return colour


@dataclass
class SlideRow:
    label: str
    start: int
    end: int
    boundary: int
    section: int
    split: int


def slide_rows(text, kind, fallback='V1'):
    """Keep source offsets, including empty slides and repeated section labels."""
    pattern = (r'(?m)^[ \t]*(?:---\[([^\n]+)\]---|\[--}\{--\])[ \t]*(?:\n|$)'
               if kind == 'song' else r'(?m)^[ \t]*\[===\][ \t]*(?:\n|$)')
    rows = []
    start = boundary = section = split = 0
    label = fallback if kind == 'song' else '1'
    for match in re.finditer(pattern, text):
        is_section = kind == 'song' and match.group(1) is not None
        if match.start() > 0 or not is_section:
            end = match.start() - (1 if text[:match.start()].endswith('\n') else 0)
            rows.append(SlideRow(label, start, max(start, end), boundary, section, split))
            if is_section or kind == 'custom':
                section += 1
                split = 0
            else:
                split += 1
        if is_section:
            name, _, number = match.group(1).rpartition(':')
            verse_type = VerseType.from_loose_input(name or match.group(1))
            label = VerseType.tags[verse_type].upper() + (number.strip() or '1')
        elif kind == 'custom':
            label = str(len(rows) + 1)
        boundary = match.start()
        start = match.end()
    rows.append(SlideRow(label, start, len(text), boundary, section, split))
    return rows


class ContentCommand(QtGui.QUndoCommand):
    """Content and design edits share the window's chronological undo history."""
    def __init__(self, grid, old_text, new_text, old_position, new_position, old_design, old_tag, new_tag):
        super().__init__(tr('Edit slide content'))
        self.grid = grid
        self.old_text, self.new_text = old_text, new_text
        self.old_position, self.new_position = old_position, new_position
        self.old_design = old_design
        self.new_design = None
        self.old_tag, self.new_tag = old_tag, new_tag
        self.edit_key = (grid.active_row, len(grid.rows)) if grid._cell_edit else None
        self.timestamp = time.monotonic()

    def id(self):
        return 201

    def mergeWith(self, other):
        if (not isinstance(other, ContentCommand) or self.grid is not other.grid or self.edit_key is None
                or self.edit_key != other.edit_key or other.timestamp - self.timestamp > 1
                or self.new_text != other.old_text):
            return False
        self.new_text, self.new_position = other.new_text, other.new_position
        self.new_design, self.new_tag = other.new_design, other.new_tag
        self.timestamp = other.timestamp
        return True

    def undo(self):
        self.grid.restore(self.old_text, self.old_position, self.old_design, self.old_tag)

    def redo(self):
        if self.new_design is None:
            self.grid.form.designer_cursor_changed()
            self.new_design = copy.deepcopy(self.grid.designer.document)
        else:
            self.grid.restore(self.new_text, self.new_position, self.new_design, self.new_tag)


class SlideContentDelegate(FormattingTagDelegate):
    def paint(self, painter, option, index):
        if index.row() == self.parent().active_row and not self.parent().has_grid_selection():
            # The Fluent editor is translucent: do not paint a second copy underneath.
            self.initStyleOption(option, index)
            option.text = ''
            option.widget.style().drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem,
                                              option, painter, option.widget)
            self._paint_separator(painter, option, index)
        else:
            self.initStyleOption(option, index)
            option.text = ''
            if self.parent().has_grid_selection():
                option.state &= ~QtWidgets.QStyle.StateFlag.State_Selected
            option.widget.style().drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem,
                                              option, painter, option.widget)
            if index.row() in self.parent().selected_slide_rows:
                tint = QtGui.QColor(self.parent().active_indicator.theme_tokens().colors.accentDefault)
                tint.setAlphaF(0.18)
                painter.fillRect(option.rect, tint)
            editor = self.parent().measure_editor(index.row(), option.rect.width())
            painter.save()
            painter.setClipRect(option.rect)
            painter.translate(option.rect.topLeft())
            editor.paint_heading_backgrounds(painter, editor._editor.viewport().width())
            context = QtGui.QAbstractTextDocumentLayout.PaintContext()
            context.palette = option.palette
            context.selections = self.parent().selection_paint_context(index.row(), editor, option.palette)
            editor.document().documentLayout().draw(painter, context)
            block = editor.document().begin()
            while block.isValid():
                if editor.split_marker_style_for_text(block.text()):
                    rect = editor.document().documentLayout().blockBoundingRect(block)
                    self._paint_marker(painter, block.text(), rect.top(),
                                       QtCore.QRect(6, 0, editor._editor.viewport().width() - 12, 0),
                                       option.palette.color(QtGui.QPalette.ColorRole.Text))
                block = block.next()
            painter.restore()
            self._paint_separator(painter, option, index)

    def sizeHint(self, option, index):
        grid = self.parent()
        width = option.rect.width() or grid.columnWidth(0)
        editor = grid.measure_editor(index.row(), width)
        return QtCore.QSize(width, max(64, round(editor.document().size().height()) + 12))


class SlideCellEditor(SongLyricsTextEdit):
    def __init__(self, parent, song_headings=False):
        self.song_headings = song_headings
        super().__init__(parent)

    def frameWidth(self):
        # The grid owns the cell border; headings fill the entire cell width.
        return 0

    def insertFromMimeData(self, source):
        if hasattr(self, 'slide_grid') and self.slide_grid.paste_grid(source):
            return
        if self.song_headings and heading_identity(source.text().split('\n')[0]):
            existing = self.toPlainText().partition('\n')
            if heading_identity(existing[0]) and not existing[2].strip():
                self.selectAll()
        super().insertFromMimeData(source)

    def _selection_section_ranges(self, text, selection_start, selection_end):
        if not self.song_headings:
            return super()._selection_section_ranges(text, selection_start, selection_end)
        ranges = []
        start = selection_start
        for match in re.finditer(r'(?m)^.*(?:\n|$)', text):
            if heading_identity(match.group().strip()) and match.end() > start and match.start() < selection_end:
                ranges.extend(super()._selection_section_ranges(text, start, min(selection_end, match.start())))
                start = match.end()
        ranges.extend(super()._selection_section_ranges(text, start, selection_end))
        return ranges

    def _is_section_boundary_line(self, text):
        return bool(self.song_headings and heading_identity(text)) or super()._is_section_boundary_line(text)

    def _refresh_block_formats(self):
        if self._updating_block_formats:
            return
        if not self.song_headings:
            return super()._refresh_block_formats()
        # A base formatting pass would temporarily move every heading before this pass restores it.
        self._updating_block_formats = True
        cursor = QtGui.QTextCursor(self.document())
        cursor.joinPreviousEditBlock()
        try:
            block = self.document().begin()
            while block.isValid():
                label = heading_identity(block.text())
                desired = QtGui.QTextBlockFormat(block.blockFormat())
                desired.setBackground(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
                desired.setTopMargin(0)
                desired.setBottomMargin(0)
                desired.setLeftMargin(self.TEXT_INSET)
                desired.setRightMargin(self.TEXT_INSET)
                desired.setTextIndent(0)
                desired.setNonBreakableLines(bool(label))
                desired.setLineHeight(
                    self._editor.fontMetrics().lineSpacing() + 2 * self.LABEL_PADDING if label else 100,
                    (QtGui.QTextBlockFormat.LineHeightTypes.FixedHeight if label else
                     QtGui.QTextBlockFormat.LineHeightTypes.ProportionalHeight).value)
                if desired != block.blockFormat():
                    cursor.setPosition(block.position())
                    cursor.setBlockFormat(desired)
                block = block.next()
        finally:
            cursor.endEditBlock()
            self._updating_block_formats = False

    def paint_heading_backgrounds(self, painter, width):
        if not self.song_headings:
            return
        block = self.document().begin()
        while block.isValid():
            label = heading_identity(block.text())
            if label:
                rect = self.blockBoundingRect(block)
                rect.setLeft(0)
                rect.setWidth(width)
                painter.fillRect(rect, section_colour(label))
            block = block.next()

    def eventFilter(self, watched, event):
        if watched is self._viewport and event.type() == QtCore.QEvent.Type.Paint:
            painter = QtGui.QPainter(watched)
            painter.translate(0, -self._editor.verticalScrollBar().value())
            self.paint_heading_backgrounds(painter, watched.width())
            painter.end()
        return super().eventFilter(watched, event)

    def createStandardContextMenu(self):
        menu = self.slide_grid.history_menu(super().createStandardContextMenu())
        if hasattr(self, 'slide_grid'):
            menu.addSeparator()
            menu.addAction(tr('Select slide'), lambda: self.slide_grid.select_slide_rows({self.slide_grid.active_row}))
            menu.addAction(tr('Select all slides'),
                           lambda: self.slide_grid.select_slide_rows(range(len(self.slide_grid.rows))))
        return menu


class ActiveSlideIndicator(fluentqt.FluentWidget):
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self.theme_tokens().colors.accentDefault)


class SlideGrid(SlideSelection, fluentqt.DataGrid):
    """One reusable rich editor sits in the active content cell; other rows remain readable."""
    def __init__(self, form, source, kind):
        super().__init__(form)
        self.form, self.source, self.kind = form, source, kind
        self.designer = form.slide_designer
        self.rows = []
        self.active_row = 0
        self._syncing = False
        self._cell_edit = False
        self._replaying = False
        self.record_history = False
        self._last_text = source.toPlainText()
        self._last_position = source.textCursor().position()
        self._last_tag = self.current_tag()
        self._model = QtGui.QStandardItemModel(0, 1, self)
        self._model.setHorizontalHeaderLabels([tr('Content')])
        self.setModel(self._model)
        self.setAccessibleName(tr('Slide content'))
        self.setSelectionMode(fluentqt.SelectionMode.Single)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(True)
        self.verticalHeader().hide()
        self.verticalHeader().setMinimumSectionSize(64)
        self.horizontalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.setItemDelegateForColumn(0, SlideContentDelegate(self))
        self.cell_editor = SlideCellEditor(self.viewport(), kind == 'song')
        self.cell_editor.slide_grid = self
        self.active_indicator = ActiveSlideIndicator(self.viewport())
        self.active_indicator.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.active_indicator.setAccessibleName(tr('Active slide'))
        self.paint_editor = SlideCellEditor(self, kind == 'song')
        self.paint_editor._toolbar.hide()
        self.paint_editor._toolbar = None
        self.paint_editor.hide()
        self._paint_key = None
        self.cell_editor.setAccessibleName(tr('Slide text'))
        self.cell_editor.parse_section_labels = kind == 'song'
        self.formatting_bar = self.cell_editor._toolbar
        self.cell_editor._toolbar = None
        self.formatting_bar.setParent(form)
        self.formatting_bar.removeAction(self.cell_editor._undo_action)
        self.formatting_bar.removeAction(self.cell_editor._redo_action)
        switch = self.cell_editor._mode_switch
        container = switch.parentWidget()
        for action in self.formatting_bar.actions():
            if self.formatting_bar.widgetForAction(action) is container:
                self.formatting_bar.removeAction(action)
                break
        container.hide()
        self.cell_editor._mode_switch = None
        container.deleteLater()
        # Inputs divide native command groups, retaining overflow within each group.
        actions = self.formatting_bar.actions()
        styles = next(action for action in actions
                      if self.formatting_bar.widgetForAction(action) is self.cell_editor._custom_formatting_combo)
        inline = set(self.cell_editor._tag_actions.values())
        trailing = [action for action in actions if action not in inline and action is not styles
                    and not action.isSeparator()]
        self.formatting_bar.clear()
        self.formatting_bar.layout().setContentsMargins(8, 2, 8, 4)
        for action in self.cell_editor._tag_actions.values():
            self.formatting_bar.addAction(action)
        self.formatting_bar.addAction(styles)
        for action in trailing:
            self.formatting_bar.addAction(action)
        self.source_action = QtGui.QAction(fluent_icon('ic_fluent_code_24_regular'), tr('Source'), self)
        self.source_action.setCheckable(True)
        self.source_action.setToolTip(tr('Edit source'))
        self.source_action.toggled.connect(self.set_source_mode)
        self.formatting_bar.addAction(self.source_action)
        self.formatting_bar.addSeparator(standalone=True)
        for action in self.designer.history_actions:
            action.setParent(self.formatting_bar)
            self.formatting_bar.addAction(action)
        self.cell_editor._editor.installEventFilter(self)
        source._editor.installEventFilter(self)
        source._editor.viewport().installEventFilter(self)
        self.cell_editor.textChanged.connect(self.cell_changed)
        self.cell_editor.cursorPositionChanged.connect(self.sync_source_cursor)
        source.textChanged.connect(self.source_changed)
        source.cursorPositionChanged.connect(self.source_cursor_changed)
        self.clicked.connect(lambda index: self.activate_row(index.row(), focus=True))
        self.selectionModel().currentChanged.connect(lambda index, previous: self.activate_row(index.row()))
        self.verticalScrollBar().valueChanged.connect(self.position_editor)
        self.horizontalHeader().sectionResized.connect(self.resize_rows)
        self.setup_selection()
        self.reload()

    def active_text_editor(self):
        return self.source if self.source_action.isChecked() else self.cell_editor

    def set_source_mode(self, enabled):
        self.designer.commit_text()
        self.clear_grid_selection()
        self.form.text_editor_stack.setCurrentWidget(self.source if enabled else self)
        self.active_text_editor().setFocus()

    def history_menu(self, menu):
        stack = self.designer.undo_stack
        for action in menu.actions():
            if action.objectName() in ('edit-undo', 'edit-redo'):
                undo = action.objectName() == 'edit-undo'
                action.triggered.disconnect()
                action.triggered.connect(stack.undo if undo else stack.redo)
                action.setEnabled(stack.canUndo() if undo else stack.canRedo())
        return menu

    def fallback_label(self):
        if self.kind == 'song':
            return (VerseType.tags[self.form.verse_type_combo_box.currentIndex()].upper()
                    + str(self.form.verse_number_box.value()))
        return '1'

    def current_tag(self):
        return self.fallback_label() if self.kind == 'song' and self.form.has_single_verse else None

    def row_text(self, row):
        text = self.source.toPlainText()[row.start:row.end]
        return heading_text(row.label) + '\n' + text if self.kind == 'song' and row.split == 0 else text

    def cell_prefix(self):
        first, separator, rest = self.cell_editor.toPlainText().partition('\n')
        return first + separator if self.kind == 'song' and heading_identity(first) else ''

    def measure_editor(self, row, width):
        text = self.row_text(self.rows[row])
        key = (text, width, self.font().toString(), self.palette().cacheKey())
        if key != self._paint_key:
            self.paint_editor._editor.setFont(self.font())
            self.paint_editor.setPlainText(text)
            self.paint_editor.resize(max(1, width), 10000)
            self.paint_editor._position_formatting_toolbar()
            self.paint_editor.document().setTextWidth(self.paint_editor._editor.viewport().width())
            self._paint_key = key
        return self.paint_editor

    def reload(self):
        self._syncing = True
        try:
            text = self.source.toPlainText()
            self.cell_editor.parse_section_labels = False
            self.rows = slide_rows(text, self.kind, self.fallback_label())
            self._model.setRowCount(len(self.rows))
            for index, row in enumerate(self.rows):
                item = self._model.item(index, 0)
                if item is None:
                    item = QtGui.QStandardItem()
                    item.setEditable(False)
                    self._model.setItem(index, 0, item)
                item.setText(self.row_text(row))
            position = self.source.textCursor().position()
            if not self._cell_edit:
                self.active_row = max((i for i, row in enumerate(self.rows)
                                       if qt_length(text[:row.boundary]) <= position), default=0)
            self.active_row = min(self.active_row, len(self.rows) - 1)
            self.setCurrentIndex(self._model.index(self.active_row, 0))
            self.viewport().update()
            row = self.rows[self.active_row]
            value = self.row_text(row)
            if not self._cell_edit and self.cell_editor.toPlainText() != value:
                self.cell_editor.setPlainText(value)
            if not self._cell_edit:
                self.copy_source_cursor()
            self.resize_rows()
        finally:
            self._syncing = False

    def resize_rows(self, *args):
        if not self.rows:
            return
        self.resizeRowsToContents()
        self.position_editor()

    def position_editor(self, *args):
        if not self.rows:
            return
        rect = self.visualRect(self._model.index(self.active_row, 0))
        self.cell_editor._editor.setFont(self.font())
        self.cell_editor.setGeometry(rect)
        self.cell_editor._position_formatting_toolbar()
        self.cell_editor.document().setTextWidth(self.cell_editor._editor.viewport().width())
        self.cell_editor.setVisible(not self.has_grid_selection())
        if not self.has_grid_selection():
            self.cell_editor.raise_()
        self.active_indicator.setGeometry(rect.x(), rect.y(), 3, rect.height())
        self.active_indicator.show()
        self.active_indicator.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'cell_editor'):
            self.resize_rows()

    def activate_row(self, index, focus=False):
        if self._syncing or not 0 <= index < len(self.rows):
            return
        if not self.has_grid_selection():
            self.row_anchor = index
        if index != self.active_row:
            cursor = self.source.textCursor()
            cursor.setPosition(qt_length(self.source.toPlainText()[:self.rows[index].start]))
            self.source.setTextCursor(cursor)
        if focus:
            self.cell_editor.setFocus()

    def copy_source_cursor(self):
        row = self.rows[self.active_row]
        offset = qt_length(self.source.toPlainText()[:row.start])
        offset -= qt_length(self.cell_prefix())
        source_cursor = self.source.textCursor()
        cursor = self.cell_editor.textCursor()
        end = self.cell_editor.document().characterCount() - 1
        cursor.setPosition(max(0, min(end, source_cursor.anchor() - offset)))
        cursor.setPosition(max(0, min(end, source_cursor.position() - offset)), QtGui.QTextCursor.MoveMode.KeepAnchor)
        self.cell_editor.setTextCursor(cursor)

    def sync_source_cursor(self):
        if self._syncing or self._cell_edit or not self.rows:
            return
        row = self.rows[self.active_row]
        prefix = self.cell_prefix()
        if self.cell_editor.toPlainText()[len(prefix):] != self.source.toPlainText()[row.start:row.end]:
            # QTextEdit can move the caret before delivering textChanged.
            return
        self._syncing = True
        try:
            offset = qt_length(self.source.toPlainText()[:self.rows[self.active_row].start])
            cursor = self.source.textCursor()
            cell_cursor = self.cell_editor.textCursor()
            cursor.setPosition(offset + max(0, cell_cursor.anchor() - qt_length(prefix)))
            cursor.setPosition(offset + max(0, cell_cursor.position() - qt_length(prefix)),
                               QtGui.QTextCursor.MoveMode.KeepAnchor)
            self.source.setTextCursor(cursor)
            self._last_position = cursor.position()
        finally:
            self._syncing = False

    def source_cursor_changed(self):
        if not self._syncing and not self._cell_edit:
            self.reload()
        if not self._cell_edit and self.source.toPlainText() == self._last_text:
            self._last_position = self.source.textCursor().position()

    def cell_changed(self):
        if self._syncing:
            return
        self.record_history = True
        self._cell_edit = True
        try:
            row = self.rows[self.active_row]
            count = len(self.rows)
            text = self.source.toPlainText()
            value = self.cell_editor.toPlainText()
            cell_cursor = self.cell_editor.textCursor()
            prefix = self.cell_prefix()
            label = heading_identity(prefix.strip()) if prefix else row.label
            body = value[len(prefix):]
            position = max(0, cell_cursor.position() - qt_length(prefix))
            anchor = max(0, cell_cursor.anchor() - qt_length(prefix))
            first, separator, remaining = body.partition('\n')
            promoted_heading = self.kind == 'song' and separator and heading_identity(first)
            if promoted_heading:
                label = promoted_heading
                body = remaining
                position = max(0, position - qt_length(first + separator))
                anchor = max(0, anchor - qt_length(first + separator))
            start = row.start
            raw_prefix = ''
            if self.kind == 'song':
                if self.form.has_single_verse:
                    with QtCore.QSignalBlocker(self.form.verse_type_combo_box), \
                            QtCore.QSignalBlocker(self.form.verse_number_box):
                        self.form.verse_type_combo_box.setCurrentIndex(VerseType.from_tag(label[0].lower()))
                        self.form.verse_number_box.setValue(int(label[1:]))
                else:
                    start = row.boundary
                    raw_prefix = text[row.boundary:row.start]
                    if label != row.label or raw_prefix.lstrip().startswith('---[') or not raw_prefix:
                        raw_prefix = section_marker(label)
                    # New headings become sections when their line is completed.

                    def encode(value):
                        return ''.join(section_marker(identity) if line.endswith('\n')
                                       and (identity := heading_identity(line.strip())) else line
                                       for line in value.splitlines(keepends=True))
                    position = qt_length(encode(body.encode('utf-16-le')[:position * 2].decode('utf-16-le')))
                    anchor = qt_length(encode(body.encode('utf-16-le')[:anchor * 2].decode('utf-16-le')))
                    body = encode(body)
            cursor = self.source.textCursor()
            cursor.setPosition(qt_length(text[:start]))
            cursor.setPosition(qt_length(text[:row.end]), QtGui.QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(raw_prefix + body)
            offset = qt_length(text[:start] + raw_prefix)
            cursor.setPosition(offset + anchor)
            cursor.setPosition(offset + position, QtGui.QTextCursor.MoveMode.KeepAnchor)
            self.source.setTextCursor(cursor)
            self.source_changed()
        finally:
            self._cell_edit = False
        if len(self.rows) != count or promoted_heading:
            self.reload()
        else:
            # Keep a heading editable while it is being typed, including partial words.
            self._cell_edit = True
            self.reload()
            self._cell_edit = False
        self.form.designer_cursor_changed()

    def source_changed(self):
        text = self.source.toPlainText()
        tag = self.current_tag()
        if text == self._last_text and tag == self._last_tag:
            return
        old_text, old_position = self._last_text, self._last_position
        if self.has_grid_selection():
            self.clear_grid_selection()
        old_tag, self._last_tag = self._last_tag, tag
        old_design = copy.deepcopy(self.designer.document)
        self._last_text = text
        self.reload()
        if self.record_history and not self._replaying:
            self.designer.undo_stack.push(ContentCommand(
                self, old_text, text, old_position, self.source.textCursor().position(), old_design, old_tag, tag))

    def restore(self, text, position, design, tag=None):
        self._replaying = True
        try:
            if tag:
                with QtCore.QSignalBlocker(self.form.verse_type_combo_box), \
                        QtCore.QSignalBlocker(self.form.verse_number_box):
                    self.form.verse_type_combo_box.setCurrentIndex(VerseType.from_tag(tag[0].lower()))
                    self.form.verse_number_box.setValue(int(tag[1:]))
            self.source.setPlainText(text)
            cursor = self.source.textCursor()
            cursor.setPosition(min(position, self.source.document().characterCount() - 1))
            self.source.setTextCursor(cursor)
            self.designer.restore(design)
            self.reload()
            self.active_text_editor().setFocus()
        finally:
            self._replaying = False

    def merge_previous(self):
        if self.active_row == 0:
            return
        row, previous = self.rows[self.active_row], self.rows[self.active_row - 1]
        text = self.source.toPlainText()
        cursor = self.source.textCursor()
        cursor.setPosition(qt_length(text[:previous.end]))
        cursor.setPosition(qt_length(text[:row.start]), QtGui.QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText('\n')
        self.source.setTextCursor(cursor)
        self.cell_editor.setFocus()

    def eventFilter(self, watched, event):
        if watched is self.source._viewport and event.type() == QtCore.QEvent.Type.ContextMenu:
            menu = self.history_menu(self.source.createStandardContextMenu())
            menu.exec(event.globalPos())
            menu.deleteLater()
            return True
        if hasattr(self, 'cell_editor') and watched is self.cell_editor._viewport:
            point = (watched.mapTo(self.viewport(), event.position().toPoint())
                     if isinstance(event, QtGui.QMouseEvent) else None)
            if (event.type() == QtCore.QEvent.Type.MouseButtonPress
                    and event.button() == QtCore.Qt.MouseButton.LeftButton):
                if self.selection_press(point, event.modifiers()):
                    return True
            elif event.type() == QtCore.QEvent.Type.MouseMove and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
                if self.selection_move(point):
                    return True
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                if self.selection_release():
                    return True
        if (hasattr(self, 'cell_editor') and watched in (self.cell_editor._editor, self.source._editor)
                and event.type() == QtCore.QEvent.Type.KeyPress):
            for key, action in ((QtGui.QKeySequence.StandardKey.Undo, self.designer.undo_stack.undo),
                                (QtGui.QKeySequence.StandardKey.Redo, self.designer.undo_stack.redo)):
                if event.matches(key):
                    action()
                    return True
            if watched is self.source._editor:
                return super().eventFilter(watched, event)
            cursor = self.cell_editor.textCursor()
            if (event.key() == QtCore.Qt.Key.Key_Backspace and not cursor.hasSelection()
                    and cursor.position() in (0, qt_length(self.cell_prefix()))):
                self.merge_previous()
                return True
            if event.key() in (QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Backtab):
                self.activate_row(self.active_row + (-1 if event.key() == QtCore.Qt.Key.Key_Backtab else 1), True)
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        point = event.position().toPoint()
        endpoint = self.point_endpoint(point)
        if not self.selection_press(point, event.modifiers()):
            self.activate_row(endpoint[0], focus=True)
            cursor = self.cell_editor.textCursor()
            cursor.setPosition(endpoint[1])
            self.cell_editor.setTextCursor(cursor)
            self.viewport().grabMouse()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_anchor is not None:
            if not self.selection_move(event.position().toPoint()):
                endpoint = self.point_endpoint(event.position().toPoint())
                cursor = self.cell_editor.textCursor()
                cursor.setPosition(self.drag_anchor[1])
                cursor.setPosition(endpoint[1], QtGui.QTextCursor.MoveMode.KeepAnchor)
                self.cell_editor.setTextCursor(cursor)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_anchor is not None:
            self.selection_release()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        for key, action in ((QtGui.QKeySequence.StandardKey.Undo, self.designer.undo_stack.undo),
                            (QtGui.QKeySequence.StandardKey.Redo, self.designer.undo_stack.redo)):
            if event.matches(key):
                action()
                return
        if self.has_grid_selection() and self.selection_key(event):
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        if not self.has_grid_selection():
            self.select_slide_rows({self.point_endpoint(event.pos())[0]})
        menu = QtWidgets.QMenu(self)
        for caption, callback in ((tr('Cut'), self.cut_grid_selection), (tr('Copy'), self.copy_grid_selection),
                                  (tr('Delete'), self.delete_grid_selection)):
            menu.addAction(caption, callback)
        menu.addSeparator()
        menu.addAction(tr('Paste slides before'), lambda: self.paste_grid(insert=True))
        menu.addAction(tr('Paste slides after'), lambda: self.paste_grid(after=True, insert=True))
        menu.addSeparator()
        menu.addAction(tr('Select all slides'), lambda: self.select_slide_rows(range(len(self.rows))))
        menu.exec(event.globalPos())
