"""The slide grid edits portable lyrics and shares the designer undo stack."""
from unittest.mock import MagicMock

import pytest
from PySide6 import QtCore, QtGui

from openlp.core.common.registry import Registry
from openlp.plugins.songs.forms.editsongform import EditSongForm
from openlp.plugins.slide_designer.forms.slidegrid import slide_rows


@pytest.fixture
def form(settings):
    from openlp.plugins.songs.lib.sectioncolors import DEFAULT_SECTION_COLORS
    settings.extend_default_settings({'songs/section color ' + key: colour
                                      for key, colour in DEFAULT_SECTION_COLORS.items()})
    settings.extend_default_settings({'songs/section background opacity minimum': 10,
                                      'songs/section background opacity maximum': 60})
    manager = MagicMock()
    manager.global_theme = 'Default'
    manager.get_theme_names.return_value = ['Default']
    Registry().register('theme_manager', manager)
    owner = EditSongForm(MagicMock(), None, MagicMock())
    editor = owner.verse_form
    editor.set_verse('---[Verse:1]---\nFirst line\nSecond line\n---[Chorus:1]---\nChorus')
    editor.slide_grid.record_history = True
    yield editor
    editor.slide_designer.refresh_timer.stop()
    editor.deleteLater()
    owner.deleteLater()


def test_rows_preserve_sections_splits_empty_rows_and_optional_markers():
    text = '---[Verse:1]---\nFirst\n[---]\nOptional\n[--}{--]\nSecond\n---[Chorus:2]---\n'
    rows = slide_rows(text, 'song')
    assert [row.label for row in rows] == ['V1', 'V1', 'C2']
    assert [text[row.start:row.end] for row in rows] == ['First\n[---]\nOptional', 'Second', '']
    assert [(row.section, row.split) for row in rows] == [(0, 0), (0, 1), (1, 0)]
    text = '\n[===]\nSecond\n[===]\n'
    assert [text[row.start:row.end] for row in slide_rows(text, 'custom')] == ['', 'Second', '']


def test_cell_edit_updates_source_and_undo(form):
    grid = form.slide_grid
    grid.cell_editor.moveCursor(QtGui.QTextCursor.MoveOperation.End)
    grid.cell_editor.insertPlainText('!')
    assert form.get_all_verses().startswith('---[Verse:1]---\nFirst line\nSecond line!\n')
    form.slide_designer.undo_stack.undo()
    assert grid.cell_editor.toPlainText() == 'Verse 1\nFirst line\nSecond line'
    form.slide_designer.undo_stack.redo()
    assert grid.cell_editor.toPlainText() == 'Verse 1\nFirst line\nSecond line!'


def test_split_creates_row_and_backspace_merges_with_undo(form, qtbot):
    grid = form.slide_grid
    cursor = grid.cell_editor.textCursor()
    cursor.setPosition(len('Verse 1\nFirst line\n'))
    grid.cell_editor.setTextCursor(cursor)
    form.on_forced_split_button_clicked()
    assert [row.label for row in grid.rows] == ['V1', 'V1', 'C1']
    assert grid.active_row == 1
    assert grid.cell_editor.toPlainText() == 'Second line'
    assert form.slide_designer.footer_key() == 'v1:1:0'
    grid.cell_editor.moveCursor(QtGui.QTextCursor.MoveOperation.Start)
    qtbot.keyClick(grid.cell_editor._editor, QtCore.Qt.Key.Key_Backspace)
    assert len(grid.rows) == 2
    assert grid.cell_editor.toPlainText() == 'Verse 1\nFirst line\nSecond line'
    form.slide_designer.undo_stack.undo()
    assert len(grid.rows) == 3
    form.slide_designer.undo_stack.redo()
    assert len(grid.rows) == 2


def test_optional_split_stays_inside_row(form):
    grid = form.slide_grid
    grid.cell_editor.moveCursor(QtGui.QTextCursor.MoveOperation.End)
    form.on_overflow_split_button_clicked()
    assert len(grid.rows) == 2
    assert '[---]' in grid.cell_editor.toPlainText()
    assert grid.cell_editor.split_marker_style_for_text('[---]') == QtCore.Qt.PenStyle.DotLine


def test_forced_split_continuation_edits_without_repeating_section_heading(form):
    source = '---[Verse:4]---\nFirst half\n[--}{--]\nSecond half\n---[Verse:5]---\nNext verse'
    form.set_verse(source)
    grid = form.slide_grid
    assert [grid.row_text(row) for row in grid.rows] == [
        'Verse 4\nFirst half', 'Second half', 'Verse 5\nNext verse']
    grid.activate_row(1)
    grid.cell_editor.moveCursor(QtGui.QTextCursor.MoveOperation.End)
    grid.cell_editor.insertPlainText('!')
    assert form.get_all_verses() == source.replace('Second half', 'Second half!')
    grid.activate_row(2)
    grid.activate_row(1)
    assert grid.cell_editor.toPlainText() == 'Second half!'
    assert grid.cell_editor.textCursor().position() == 0
    assert grid.active_indicator.geometry().topLeft() == grid.visualRect(grid.model().index(1, 0)).topLeft()
    form.slide_designer.undo_stack.undo()
    assert form.get_all_verses() == source


def test_formatting_command_bar_targets_active_cell(form):
    grid = form.slide_grid
    grid.activate_row(1)
    grid.cell_editor.selectAll()
    grid.cell_editor._tag_actions['st'].trigger()
    assert '{st}Chorus{/st}' in form.get_all_verses()
    assert grid.formatting_bar.parentWidget() is form
    assert form.command_rows.indexOf(grid.formatting_bar) == 1
    assert form.command_rows.spacing() == 0
    assert not grid.cell_editor._custom_formatting_combo.isHidden()
    actions = grid.formatting_bar.actions()
    styles = next(action for action in actions
                  if grid.formatting_bar.widgetForAction(action) is grid.cell_editor._custom_formatting_combo)
    assert actions.index(styles) < next(i for i, action in enumerate(actions) if action.text() == 'Clear formatting')
    assert actions[-2:] == form.slide_designer.history_actions
    assert actions[-3].isSeparator()
    import fluentqt
    divider = grid.formatting_bar.widgetForAction(actions[-3])
    assert isinstance(divider, fluentqt.Divider)
    assert divider.width() == 1
    assert divider.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
    assert grid.cell_editor._toolbar is None
    assert grid.cell_editor._mode_switch is None
    assert grid.cell_editor._undo_action not in grid.formatting_bar.actions()
    assert grid.cell_editor._redo_action not in grid.formatting_bar.actions()


def test_text_and_design_undo_in_order(form):
    grid = form.slide_grid
    grid.cell_editor.insertPlainText('A')
    form.slide_designer.add_element('rectangle')
    grid.cell_editor.insertPlainText('B')
    stack = form.slide_designer.undo_stack
    stack.undo()
    assert grid.cell_editor.toPlainText().startswith('Verse 1\nAFirst')
    assert len(form.slide_designer.design['elements']) == 1
    stack.undo()
    assert not form.slide_designer.design.get('elements')
    stack.undo()
    assert grid.cell_editor.toPlainText().startswith('Verse 1\nFirst')


def test_unicode_cursor_and_row_switch(form):
    grid = form.slide_grid
    grid.cell_editor.insertPlainText('🙏 ')
    grid.activate_row(1)
    grid.cell_editor.insertPlainText('New ')
    assert '🙏 First' in form.get_all_verses()
    assert form.get_all_verses().endswith('New Chorus')


def test_pasted_song_headings_create_rows(form):
    grid = form.slide_grid
    form.set_verse('')
    mime = QtCore.QMimeData()
    mime.setText('Verse 1\nFirst verse\nChorus 1\nThe chorus')
    grid.cell_editor.insertFromMimeData(mime)
    assert [row.label for row in grid.rows] == ['V1', 'C1']
    assert '---[Chorus:1]---' in form.get_all_verses()


def test_backspace_at_start_of_first_row_keeps_content(form, qtbot):
    grid = form.slide_grid
    before = form.get_all_verses()
    grid.cell_editor.moveCursor(QtGui.QTextCursor.MoveOperation.Start)
    qtbot.keyClick(grid.cell_editor._editor, QtCore.Qt.Key.Key_Backspace)
    assert form.get_all_verses() == before


def test_custom_slide_split_merge_and_design_undo(form, qtbot):
    from openlp.plugins.custom.forms.editcustomform import EditCustomForm
    owner = EditCustomForm(MagicMock(), None, MagicMock())
    editor = owner.edit_slide_form
    editor.set_text('First\nSecond\n[===]\nLast')
    grid = editor.slide_grid
    grid.record_history = True
    cursor = grid.cell_editor.textCursor()
    cursor.setPosition(len('First\n'))
    grid.cell_editor.setTextCursor(cursor)
    editor.on_insert_button_clicked()
    assert editor.get_text() == ['First', 'Second', 'Last']
    assert grid.active_row == 1
    grid.cell_editor.moveCursor(QtGui.QTextCursor.MoveOperation.Start)
    qtbot.keyClick(grid.cell_editor._editor, QtCore.Qt.Key.Key_Backspace)
    assert editor.get_text() == ['First\nSecond', 'Last']
    editor.slide_designer.undo_stack.undo()
    assert editor.get_text() == ['First', 'Second', 'Last']
    editor.slide_designer.refresh_timer.stop()
    editor.deleteLater()
    owner.deleteLater()


def test_keyboard_undo_uses_shared_history(form, qtbot):
    grid = form.slide_grid
    grid.cell_editor.insertPlainText('A')
    form.slide_designer.add_element('rectangle')
    # QKeySequence's platform binding is used by the native editor as well.
    sequence = QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Undo)[0]
    event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, sequence.key(), sequence.keyboardModifiers())
    QtCore.QCoreApplication.sendEvent(grid.cell_editor._editor, event)
    assert not form.slide_designer.design.get('elements')
    assert grid.cell_editor.toPlainText().startswith('Verse 1\nAFirst')


def test_typing_section_heading_updates_label_and_keeps_colour(form, qtbot):
    grid = form.slide_grid
    cursor = grid.cell_editor.textCursor()
    cursor.setPosition(0)
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock, QtGui.QTextCursor.MoveMode.KeepAnchor)
    grid.cell_editor.setTextCursor(cursor)
    qtbot.keyClicks(grid.cell_editor._editor, 'Chorus 2')
    assert grid.rows[0].label == 'C2'
    assert grid.cell_editor.toPlainText().startswith('Chorus 2\nFirst line')
    assert form.get_all_verses().startswith('---[Chorus:2]---\nFirst line')
    assert grid.cell_editor.document().firstBlock().blockFormat().background().color().alpha() > 0
    form.slide_designer.undo_stack.undo()
    assert grid.rows[0].label == 'V1'
    assert grid.cell_editor.toPlainText().startswith('Verse 1\nFirst line')


def test_single_verse_heading_edits_metadata_without_putting_it_in_lyrics(form):
    form.set_verse('Lyrics', single=True, tag='v1')
    form.slide_designer.undo_stack.clear()
    grid = form.slide_grid
    cursor = grid.cell_editor.textCursor()
    cursor.setPosition(0)
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock, QtGui.QTextCursor.MoveMode.KeepAnchor)
    grid.cell_editor.setTextCursor(cursor)
    grid.cell_editor.insertPlainText('Chorus 2')
    assert form.get_verse() == ('Lyrics', 'c', '2')
    form.slide_designer.undo_stack.undo()
    assert form.get_verse() == ('Lyrics', 'v', '1')


def test_typing_heading_into_empty_content_assigns_current_row(form, qtbot):
    form.set_verse('')
    grid = form.slide_grid
    qtbot.keyClicks(grid.cell_editor._editor, 'Chorus 2')
    qtbot.keyClick(grid.cell_editor._editor, QtCore.Qt.Key.Key_Return)
    assert [row.label for row in grid.rows] == ['C2']
    assert form.get_all_verses() == '---[Chorus:2]---\n'
    assert grid.cell_editor.toPlainText() == 'Chorus 2\n'


def test_row_text_geometry_stays_the_same_when_selected(form):
    grid = form.slide_grid
    grid.resize(360, 480)
    grid.resize_rows()
    heights = [grid.rowHeight(i) for i in range(len(grid.rows))]
    for row in range(len(grid.rows)):
        measured = grid.measure_editor(row, grid.columnWidth(0))
        expected = measured.document().documentLayout().blockBoundingRect(measured.document().lastBlock())
        grid.activate_row(row)
        actual = grid.cell_editor.document().documentLayout().blockBoundingRect(grid.cell_editor.document().lastBlock())
        assert actual == expected
        assert [grid.rowHeight(i) for i in range(len(grid.rows))] == heights
        heading = grid.cell_editor.document().firstBlock()
        rect = grid.cell_editor.document().documentLayout().blockBoundingRect(heading)
        assert rect.left() == 0
        assert heading.blockFormat().rightMargin() == 0
        assert grid.cell_editor.geometry() == grid.visualRect(grid.model().index(row, 0))
        assert heading.blockFormat().textIndent() == grid.cell_editor.TEXT_INSET


def test_properties_is_the_only_sidebar_toggle_and_drawers_stay_present(form):
    designer = form.slide_designer
    assert not designer.inspector_button.isChecked()
    assert designer.sidebar.isHidden()
    assert not hasattr(designer, 'layers_button')
    drawers = [designer.properties_accordion.itemAt(i) for i in range(designer.properties_accordion.count())]
    drawers.append(designer.layers_panel)
    for selection in ([], ['lyrics']):
        designer.select_objects(selection)
        assert all(not drawer.isHidden() for drawer in drawers)
    designer.inspector_button.setChecked(False)
    assert designer.sidebar.isHidden()
    designer.inspector_button.setChecked(True)
    assert not designer.sidebar.isHidden()
    assert all(not drawer.isHidden() for drawer in drawers)


def test_whole_slide_cut_paste_preserves_sections_and_forced_splits(form):
    source = '---[Verse:1]---\nOne\n[--}{--]\nTwo\n---[Chorus:1]---\nThree'
    form.set_verse(source)
    grid = form.slide_grid
    grid.select_slide_rows({0, 1})
    grid.cut_grid_selection()
    assert form.get_all_verses() == '---[Chorus:1]---\nThree'
    grid.paste_grid(after=True)
    assert form.get_all_verses() == '---[Chorus:1]---\nThree\n---[Verse:1]---\nOne\n[--}{--]\nTwo'
    form.slide_designer.undo_stack.undo()
    assert form.get_all_verses() == '---[Chorus:1]---\nThree'
    form.slide_designer.undo_stack.undo()
    assert form.get_all_verses() == source


def test_deleting_first_slide_keeps_heading_on_its_continuation(form):
    form.set_verse('---[Verse:4]---\nOne\n[--}{--]\nTwo\n---[Verse:5]---\nThree')
    grid = form.slide_grid
    grid.select_slide_rows({0, 2})
    grid.delete_grid_selection()
    assert form.get_all_verses() == '---[Verse:4]---\nTwo'
    assert grid.row_text(grid.rows[0]) == 'Verse 4\nTwo'


def test_cross_slide_text_selection_cuts_partial_lines_and_undo(form):
    from openlp.core.widgets import fluent as QtWidgets
    from openlp.plugins.slide_designer.forms.slidegrid import qt_length
    source = '---[Verse:1]---\nHello 🙏 world\n[--}{--]\nSecond line'
    form.set_verse(source)
    grid = form.slide_grid
    grid.select_text_range((0, qt_length('Verse 1\nHello 🙏 ')), (1, len('Second')))
    grid.copy_grid_selection()
    assert QtWidgets.QApplication.clipboard().text() == 'world\nSecond'
    grid.cut_grid_selection()
    assert form.get_all_verses() == '---[Verse:1]---\nHello 🙏  line'
    assert not grid.has_grid_selection()
    grid.paste_grid()
    assert form.get_all_verses() == source
    form.slide_designer.undo_stack.undo()
    assert form.get_all_verses() == '---[Verse:1]---\nHello 🙏  line'
    form.slide_designer.undo_stack.undo()
    assert form.get_all_verses() == source


def test_select_all_slides_delete_and_undo(form, qtbot):
    before = form.get_all_verses()
    grid = form.slide_grid
    grid.select_slide_rows(range(len(grid.rows)))
    qtbot.keyClick(grid, QtCore.Qt.Key.Key_Delete)
    assert grid.source.toPlainText() == ''
    assert len(grid.rows) == 1
    form.slide_designer.undo_stack.undo()
    assert form.get_all_verses() == before


def test_shift_click_and_drag_across_rows(form, qtbot):
    grid = form.slide_grid
    grid.setParent(None)
    qtbot.addWidget(grid)
    grid.resize(400, 500)
    grid.show()
    qtbot.waitUntil(lambda: grid.isVisible())
    second = grid.visualRect(grid.model().index(1, 0))
    qtbot.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier, second.center())
    assert grid.selected_slide_rows == {0, 1}
    grid.clear_grid_selection()
    viewport = grid.cell_editor._editor.viewport()
    cursor = grid.cell_editor.textCursor()
    cursor.setPosition(len('Verse 1\nFirst'))
    start = grid.cell_editor._editor.cursorRect(cursor).center()
    qtbot.mousePress(viewport, QtCore.Qt.MouseButton.LeftButton, pos=start)
    end = viewport.mapFrom(grid.viewport(), second.center())
    move = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove, QtCore.QPointF(end), QtCore.QPointF(viewport.mapToGlobal(end)),
        QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtCore.QCoreApplication.sendEvent(viewport, move)
    assert grid.text_range is not None
    assert grid.text_range[0][0] == 0
    assert grid.text_range[1][0] == 1
    qtbot.mouseRelease(grid.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=second.center())
    assert grid.drag_anchor is None
    assert grid.cell_editor.isHidden()
    grid.hide()


def test_custom_slide_cut_move_keeps_local_design_and_footer(form):
    from openlp.plugins.custom.forms.editcustomform import EditCustomForm
    owner = EditCustomForm(MagicMock(), None, MagicMock())
    editor = owner.edit_slide_form
    editor.set_text('First\n[===]\nSecond\n[===]\nThird')
    grid, designer = editor.slide_grid, editor.slide_designer
    designer.load_design({'version': 1, 'canvas_width': 1920, 'hidden_footers': ['custom-1:0:0'],
                          'overrides': {'custom-1:0:0': {'base': {}, 'design': {
                              'version': 1, 'lyrics': {'x': 25, 'font_size': 60}}}}})
    original = designer.serialised_design()
    grid.select_slide_rows({0})
    grid.cut_grid_selection()
    assert editor.get_text() == ['Second', 'Third']
    assert not designer.document.get('hidden_footers')
    grid.activate_row(1)
    grid.paste_grid(after=True)
    assert editor.get_text() == ['Second', 'Third', 'First']
    assert designer.document['hidden_footers'] == ['custom-3:0:0']
    assert designer.document['overrides']['custom-3:0:0']['design']['lyrics']['font_size'] == 60
    designer.undo_stack.undo()
    designer.undo_stack.undo()
    assert editor.get_text() == ['First', 'Second', 'Third']
    assert designer.serialised_design() == original
    designer.refresh_timer.stop()
    editor.deleteLater()
    owner.deleteLater()
