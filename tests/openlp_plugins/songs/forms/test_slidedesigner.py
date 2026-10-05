"""Canvas/inspector behaviour without needing a native browser process."""
import copy
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui
from openlp.core.common import ThemeLevel
from openlp.core.common.registry import Registry
from openlp.core.lib.theme import Theme
from openlp.core.lib.slidelayouts import slide_design, visual_design
from openlp.plugins.songs.forms.editsongform import EditSongForm


def load_editable_design(designer, value):
    """Canvas-editing tests explicitly select a user-created layout."""
    document = copy.deepcopy(value) or {'version': 1}
    if designer.footer_key() not in document.get('assignments', {}):
        document.setdefault('masters', {})['editing'] = {'name': 'Editing', 'design': visual_design(document)}
        document.setdefault('assignments', {})[designer.footer_key()] = 'editing'
    designer.load_design(document)


@pytest.fixture
def designer(settings):
    manager = MagicMock()
    manager.global_theme = 'Global'
    manager.get_theme_names.return_value = ['Global', 'Song', 'Service']
    Registry().register('theme_manager', manager)
    form = EditSongForm(MagicMock(), None, MagicMock())
    with patch('openlp.plugins.slide_designer.forms.designer.ScreenList') as screens:
        screens.return_value.current.display_geometry.size.return_value = QtCore.QSize(1920, 1080)
        load_editable_design(form.verse_form.slide_designer, {})
        form.verse_form.slide_designer.select_object('lyrics')
        yield form.verse_form.slide_designer
    form.verse_form.slide_designer.refresh_timer.stop()
    form.verse_form.deleteLater()
    form.deleteLater()


def test_add_edit_undo_redo_and_reset(designer):
    designer.add_element('rectangle')
    identifier = designer.selected
    designer.set_property('x', 37)
    assert designer.design['elements'][0]['x'] == 37
    designer.undo_stack.undo()
    assert designer.design['elements'][0]['x'] == 10
    designer.undo_stack.undo()
    assert designer.design == {}
    designer.undo_stack.redo()
    assert designer.design['elements'][0]['id'] == identifier
    designer.commit({}, 'Reset')
    assert designer.design == {}
    designer.undo_stack.undo()
    assert len(designer.design['elements']) == 1


def test_drag_gesture_is_one_undo_and_does_not_change_input(designer):
    original = {'version': 1, 'lyrics': {'width': 80}, 'elements': []}
    before = copy.deepcopy(original)
    load_editable_design(designer, original)
    designer.canvas_changed({'id': 'lyrics', 'changed': True,
                             'geometry': {'x': 5, 'y': 15, 'width': 80, 'height': 60}})
    assert designer.design['lyrics']['y'] == 15
    assert designer.undo_stack.count() == 1
    assert original == before
    designer.undo_stack.undo()
    assert designer.design['lyrics'] == {'width': 80}


def test_save_flushes_pending_text_and_song_switch_clears_it(designer):
    designer.add_element('text')
    designer.text.setPlainText('Final unsaved keystrokes')
    saved = slide_design(designer.serialised_design(), designer.footer_key())
    assert saved['elements'][0]['text'] == 'Final unsaved keystrokes'
    designer.text.setPlainText('Discard this draft')
    load_editable_design(designer, None)
    designer.commit_text()
    assert designer.design == {}
    assert designer.undo_stack.count() == 0


def test_switch_layer_preserves_pending_text_and_selection(designer):
    designer.add_element('text')
    designer.text.setPlainText('New caption')
    designer.layers.selectionModel().setCurrentIndex(
        designer.layers.model().index(designer.layers.identifiers().index('lyrics'), 0),
        QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
    assert designer.selected == 'lyrics'
    assert designer.design['elements'][0]['text'] == 'New caption'


def test_preview_uses_assigned_theme_with_global_fallback(designer, settings):
    form = designer.source_form
    form.theme_combo_box.addItems(['Song', 'Missing theme'])
    form.theme_combo_box.setCurrentText('Song')
    settings.setValue('themes/theme level', ThemeLevel.Global)
    designer.resolve_theme()
    designer.theme_manager.get_theme_data.assert_called_with('Song')
    form.theme_combo_box.setCurrentText('Missing theme')
    designer.resolve_theme()
    designer.theme_manager.get_theme_data.assert_called_with('Global')
    assert not hasattr(designer, 'theme_source')
    assert designer.canvas_combo.parentWidget() is designer.preview_footer.preview_group


def test_preview_uses_unsaved_verse_and_design(designer):
    designer.display = MagicMock()
    designer.display._is_initialised = True
    designer.display.format_slide.return_value = ['New lyrics']
    designer.isVisible = lambda: True
    with patch('openlp.core.lib.theme.ScreenList') as screens:
        screens.return_value.current.display_geometry = QtCore.QRect(0, 0, 1920, 1080)
        theme = Theme()
    designer.theme_manager.get_theme_data.return_value = theme
    form = designer.source_form
    form.designer_footer = lambda: 'Draft footer'
    form.verse_text_edit.setPlainText('New lyrics')
    load_editable_design(designer, {'version': 1, 'lyrics': {'x': 25}, 'elements': []})
    designer.refresh()
    assert designer.display.set_theme.call_args.args[0].font_main_x == 480
    designer.display.load_verses.assert_called_with(
        [{'verse': 'designer', 'text': 'New lyrics', 'footer': 'Draft footer'}])
    form.design_owner.manager.save_object.assert_not_called()


def test_preview_creation_survives_reentrant_show_event(designer):
    renderer = MagicMock()

    def create_renderer(*args, **kwargs):
        designer.showEvent(QtGui.QShowEvent())
        return renderer

    with patch.object(designer, 'resolve_theme', return_value=MagicMock(spec=Theme)), \
            patch('openlp.plugins.slide_designer.forms.designer.ThemePreviewRenderer',
                  side_effect=create_renderer) as create:
        designer.showEvent(QtGui.QShowEvent())
        designer.showEvent(QtGui.QShowEvent())

    create.assert_called_once()
    assert designer.display is renderer
    assert not designer._creating_display
    renderer.show.assert_called_once()
    assert renderer.display_watcher.register_event_listener.call_count == 2


def test_preview_creation_can_retry_after_failure(designer):
    with patch.object(designer, 'resolve_theme', return_value=MagicMock(spec=Theme)), \
            patch('openlp.plugins.slide_designer.forms.designer.ThemePreviewRenderer',
                  side_effect=[RuntimeError('Startup failed'), MagicMock()]) as create:
        with pytest.raises(RuntimeError, match='Startup failed'):
            designer.showEvent(QtGui.QShowEvent())
        assert not designer._creating_display
        assert designer.display is None
        designer.showEvent(QtGui.QShowEvent())

    assert create.call_count == 2
    assert designer.display is not None


def test_aspect_preview_stays_frozen_until_latest_render_is_ready(designer):
    designer.display = MagicMock()
    designer.display._is_initialised = True
    designer.display.format_slide.return_value = ['Lyrics']
    designer.isVisible = lambda: True
    with patch('openlp.core.lib.theme.ScreenList') as screens:
        screens.return_value.current.display_geometry = QtCore.QRect(0, 0, 1920, 1080)
        designer.theme_manager.get_theme_data.return_value = Theme()
    designer.fit_canvas()
    with patch.object(designer.viewport, 'grab', wraps=designer.viewport.grab) as grab:
        designer.canvas_combo.setCurrentIndex(2)
        assert not designer.preview_cover.isHidden()
        designer.refresh()
        first_revision = designer._preview_revision
        designer.display.run_in_display.assert_called_with(
            'waitForDesignPreview', first_revision, return_event_name='designPreviewReady')
        designer.canvas_combo.setCurrentIndex(3)
        designer.refresh()
        designer.preview_ready(first_revision)
        assert not designer.preview_cover.isHidden()
        grab.assert_called_once()
        designer.preview_ready(designer._preview_revision)
        assert designer.preview_cover.isHidden()
        assert not designer.preview_timeout.isActive()
        designer.undo_stack.undo()
        assert not designer.preview_cover.isHidden()
        assert grab.call_count == 2
        designer.clear_preview_cover()


def test_failed_preview_render_releases_frozen_image(designer):
    designer.display = MagicMock()
    designer.display._is_initialised = True
    designer.isVisible = lambda: True
    designer.freeze_preview()
    designer.resolve_theme = MagicMock(side_effect=RuntimeError('Renderer unavailable'))
    with pytest.raises(RuntimeError, match='Renderer unavailable'):
        designer.refresh()
    assert designer.preview_cover.isHidden()
    assert not designer._refreshing


def test_designer_only_belongs_to_inner_edit_dialog(designer):
    from openlp.plugins.custom.forms.editcustomform import EditCustomForm
    owner = designer.source_form.design_owner
    assert not hasattr(owner, 'slide_designer')
    assert owner.verse_form.slide_designer is designer
    custom = EditCustomForm(MagicMock(), None, MagicMock())
    assert not hasattr(custom, 'slide_designer')
    assert custom.edit_slide_form.slide_designer.design == {}
    custom.edit_slide_form.deleteLater()
    custom.deleteLater()


@pytest.mark.parametrize('accepted', [False, True])
def test_inner_dialog_commits_only_on_accept(designer, accepted):
    owner = designer.source_form.design_owner
    owner.slide_design = {'version': 1, 'lyrics': {'x': 10}, 'elements': []}
    original = copy.deepcopy(owner.slide_design)

    def edit_and_finish(dialog):
        assert dialog.slide_designer.design['lyrics']['x'] == 10
        with patch.object(dialog.slide_designer, 'prompt_layout_name', return_value=('Welcome', True)):
            dialog.slide_designer.new_layout()
        dialog.slide_designer.select_object('lyrics')
        dialog.slide_designer.set_property('x', 35)
        return int(accepted)

    with patch('openlp.plugins.slide_designer.forms.window.exec_designer_window', new=edit_and_finish):
        designer.source_form.exec()
    assert slide_design(owner.slide_design, designer.footer_key())['lyrics']['x'] == (35 if accepted else 10)
    if not accepted:
        assert owner.slide_design == original
    owner.manager.save_object.assert_not_called()


def test_bulk_preview_follows_section_selection(designer, settings):
    from openlp.plugins.songs.lib.sectioncolors import DEFAULT_SECTION_COLORS
    settings.extend_default_settings({'songs/section color ' + key: colour
                                      for key, colour in DEFAULT_SECTION_COLORS.items()})
    settings.extend_default_settings({'songs/section background opacity minimum': 10,
                                      'songs/section background opacity maximum': 60})
    dialog = designer.source_form
    dialog.set_verse('---[Verse:1]---\nFirst verse\n---[Chorus:1]---\nThe chorus')
    assert dialog.section_combo_box.count() == 2
    assert dialog.designer_text() == 'First verse'
    dialog.section_combo_box.setCurrentIndex(1)
    assert dialog.designer_text() == 'The chorus'


def test_assigning_theme_releases_imported_snapshot(designer):
    load_editable_design(designer, {'version': 1, 'lyrics': {'x': 15}, 'theme': {
        'background_type': 'solid', 'background_color': '#123456'}})
    designer.source_form.theme_combo_box.addItem('Song')
    assert 'theme' not in designer.design
    assert designer.design['lyrics']['x'] == 15
    designer.resolve_theme()
    designer.theme_manager.get_theme_data.assert_called_with('Song')


def test_fluent_inspector_edits_keep_precision_and_undo(designer):
    import fluentqt
    numeric_fields = [field for field in designer.fields.values() if isinstance(field, fluentqt.NumberBox)]
    numeric_fields.append(designer.background_image_opacity)
    assert all(field.displayPrecision() == 0 for field in numeric_fields)
    designer.fields['x'].setValue(12.5)
    designer.fields['bold'].click()
    assert designer.design['lyrics']['x'] == pytest.approx(12.5 / 1920 * 100)
    assert designer.design['lyrics']['bold'] is True
    designer.undo_stack.undo()
    assert not designer.fields['bold'].isChecked()
    assert designer.fields['x'].value() == pytest.approx(12.5)
    designer.undo_stack.undo()
    assert designer.design == {}


def test_inspector_follows_selected_object(designer):
    designer.add_element('rectangle')
    assert not designer.text_section.isEnabled()
    assert not designer.field_rows['fill'].isHidden()
    assert designer.back_button.isEnabled()
    designer.layers.selectionModel().setCurrentIndex(
        designer.layers.model().index(designer.layers.identifiers().index('lyrics'), 0),
        QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
    assert not designer.text_section.isHidden()
    assert not designer.field_rows['fill'].isEnabled()
    assert designer.front_button.isEnabled()
    designer.add_element('text')
    assert not designer.text.isHidden()
    assert not designer.field_rows['fill'].isEnabled()


def test_unavailable_drawers_disable_and_reenable_with_selection(designer):
    object_drawers = [designer.position_section, designer.text_section, designer.appearance_section,
                      *designer.effect_sections]
    designer.clear_selection()
    assert all(not drawer.isEnabled() for drawer in object_drawers)
    assert all(drawer.disabled_opacity.isEnabled() for drawer in object_drawers)
    assert all(drawer.disabled_opacity.opacity() == 0.65 for drawer in object_drawers)
    assert all(not drawer.isHidden() for drawer in object_drawers)
    assert designer.slide_section.isEnabled()
    assert designer.background_section.isEnabled()
    designer.add_element('rectangle')
    assert designer.position_section.isEnabled()
    assert designer.appearance_section.isEnabled()
    assert all(drawer.isEnabled() for drawer in designer.effect_sections)
    assert not designer.text_section.isEnabled()
    designer.select_object('lyrics')
    assert all(drawer.isEnabled() for drawer in object_drawers)
    assert all(not drawer.disabled_opacity.isEnabled() for drawer in object_drawers)


def test_properties_header_stays_fixed_and_pane_can_resize(designer, qtbot):
    designer.inspector_button.setChecked(True)
    designer.setParent(None)
    qtbot.addWidget(designer)
    designer.display = MagicMock()
    designer.display._is_initialised = False
    designer.resize(1050, 550)
    designer.show()
    for drawer, _ in designer.reset_sections.values():
        drawer.setExpanded(True)
    scroll = designer.sidebar_scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: scroll.maximum() > 0)
    heading_position = designer.properties_heading.mapTo(designer, QtCore.QPoint())
    scroll.setValue(scroll.maximum())
    assert designer.properties_heading.mapTo(designer, QtCore.QPoint()) == heading_position
    assert designer.properties_heading.parentWidget() is designer.sidebar
    assert not any(button.accessibleName() == 'Close properties'
                   for button in designer.sidebar.findChildren(type(designer.inspector_button)))
    before = designer.sidebar.width()
    handle = designer.splitter.handle(1)
    designer.splitter.moveSplitter(handle.x() - 80, 1)
    assert designer.sidebar.width() > before
    designer.hide()


def test_custom_sidebar_commands_still_insert_slides(designer):
    from openlp.plugins.custom.forms.editcustomform import EditCustomForm
    owner = EditCustomForm(MagicMock(), None, MagicMock())
    dialog = owner.edit_slide_form
    dialog.set_text('First')
    cursor = dialog.slide_text_edit.textCursor()
    cursor.setPosition(2)
    dialog.slide_text_edit.setTextCursor(cursor)
    dialog.insert_button.click()
    assert dialog.get_text() == ['Fi', 'rst']
    assert dialog.button_box.buttonRole(dialog.insert_button) == dialog.button_box.ButtonRole.InvalidRole
    dialog.deleteLater()
    owner.deleteLater()


def test_default_theme_has_a_label_without_changing_inheritance(designer):
    owner = designer.source_form.design_owner
    owner.theme_combo_box.clear()
    owner.theme_combo_box.addItems(['', 'Song'])

    def accept(dialog):
        assert dialog.theme_combo_box.currentText() == 'Default theme'
        assert dialog.designer_theme_name() == ''
        return 1

    with patch('openlp.plugins.slide_designer.forms.window.exec_designer_window', new=accept):
        designer.source_form.exec()
    assert owner.theme_combo_box.currentText() == ''


def test_layers_include_slide_text_and_new_objects_start_at_front(designer):
    from openlp.core.lib.slidedesign import layer_order
    designer.add_element('rectangle')
    shape = designer.selected
    assert layer_order(designer.design) == ['lyrics', shape]
    assert designer.layers.identifiers() == [shape, 'lyrics']
    designer.arrange('back')
    assert layer_order(designer.design) == [shape, 'lyrics']
    designer.layers.selectionModel().setCurrentIndex(
        designer.layers.model().index(0, 0), QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
    assert designer.selected == 'lyrics'
    designer.arrange('backward')
    assert layer_order(designer.design) == ['lyrics', shape]
    designer.undo_stack.undo()
    assert layer_order(designer.design) == [shape, 'lyrics']
    designer.undo_stack.redo()
    assert layer_order(designer.design) == ['lyrics', shape]


def test_dragging_layer_rows_is_one_undoable_change_and_preserves_selection(designer):
    designer.add_element('rectangle')
    shape = designer.selected
    designer.add_element('text')
    caption = designer.selected
    designer.text.setPlainText('Saved caption')
    designer.commit_text()
    before = designer.undo_stack.count()
    designer.layers.move_row(0, 3)
    assert designer.layers.identifiers() == [shape, 'lyrics', caption]
    assert designer.selected == caption
    assert designer.undo_stack.count() == before + 1
    assert designer.design['elements'][1]['text'] == 'Saved caption'
    designer.undo_stack.undo()
    assert designer.layers.identifiers() == [caption, shape, 'lyrics']
    designer.layers.move_row(0, 1)
    assert designer.layers.identifiers() == [caption, shape, 'lyrics']
    designer.delete_element()
    assert caption not in slide_design(designer.serialised_design(), designer.footer_key())['order']


def test_layer_drop_uses_row_boundary(designer):
    designer.add_element('rectangle')
    shape = designer.selected
    index = designer.layers.model().index(1, 0)
    event = MagicMock()
    event.source.return_value = designer.layers
    event.position.return_value = QtCore.QPointF(10, 40)
    with patch.object(designer.layers, 'indexAt', return_value=index), \
            patch.object(designer.layers, 'visualRect', return_value=QtCore.QRect(0, 30, 200, 30)):
        designer.layers.dropEvent(event)
    assert designer.layers.identifiers() == [shape, 'lyrics']
    event.position.return_value = QtCore.QPointF(10, 58)
    with patch.object(designer.layers, 'indexAt', return_value=index), \
            patch.object(designer.layers, 'visualRect', return_value=QtCore.QRect(0, 30, 200, 30)):
        designer.layers.dropEvent(event)
    assert designer.layers.identifiers() == ['lyrics', shape]
    event.accept.assert_called()


def test_empty_selection_shows_slide_properties_and_keeps_editor_interactive(designer):
    designer.display = MagicMock()
    designer.clear_selection()
    assert designer.selected is None
    assert not designer.background_section.isHidden()
    assert not designer.position_section.isEnabled()
    assert not designer.field_rows['opacity'].isEnabled()
    assert not designer.delete_button.isEnabled()
    designer.display.run_in_display.assert_called_with('setDesignEditor', '')
    designer.canvas_changed({'id': 'lyrics', 'changed': False})
    assert not designer.background_section.isHidden()
    assert not designer.position_section.isHidden()
    designer.canvas_changed({'id': None, 'changed': False})
    assert designer.selected_label.text() == 'Slide'


def test_slide_fill_and_image_opacity_are_independent_and_undoable(designer):
    designer.clear_selection()
    designer.set_background_property('type', 'gradient')
    designer.set_background_property('colour', '#123456')
    designer.set_background_property('image', 'data:image/png;base64,AAAA')
    designer.background_image_opacity.setValue(37.5)
    assert designer.design['background']['image_opacity'] == 37.5
    assert designer.design['background']['colour'] == '#123456'
    designer.set_background_property('type', 'solid')
    assert designer.design['background']['image'] == 'data:image/png;base64,AAAA'
    assert designer.design['background']['image_opacity'] == 37.5
    designer.remove_background_image.click()
    assert 'image' not in designer.design['background']
    assert designer.design['background']['colour'] == '#123456'
    designer.undo_stack.undo()
    assert designer.design['background']['image'] == 'data:image/png;base64,AAAA'
    designer.background_type.setCurrentIndex(designer.background_type.findData('theme'))
    assert 'background' not in designer.design


@pytest.mark.parametrize('kind', ['image', 'rectangle', 'ellipse', 'text'])
def test_object_opacity_is_editable_without_changing_background(designer, kind):
    load_editable_design(designer, {'version': 1, 'background': {'type': 'solid', 'colour': '#123456'},
                                    'elements': [{'id': 'object', 'kind': kind, 'src': 'data:image/png;base64,AAAA'}]})
    designer.select_object('object')
    assert not designer.field_rows['opacity'].isHidden()
    designer.fields['opacity'].setValue(0)
    assert slide_design(designer.serialised_design(), designer.footer_key())['elements'][0]['opacity'] == 0
    assert designer.design['background']['colour'] == '#123456'
    designer.undo_stack.undo()
    assert designer.fields['opacity'].value() == 100


def test_reset_slide_text_restores_theme_without_touching_other_layers(designer):
    load_editable_design(designer, {'version': 1, 'lyrics': {
        'x': 40, 'width': 20, 'font': 'Courier', 'font_size': 18, 'shadow': False, 'flip_vertical': True},
                                    'background': {'type': 'solid', 'colour': '#123456'},
                                    'elements': [{'id': 'shape', 'kind': 'rectangle'}], 'order': ['lyrics', 'shape']})
    designer.select_object('lyrics')
    original = copy.deepcopy(designer.design)
    assert not designer.text_section.reset_button.isHidden()
    designer.text_section.reset_button.click()
    assert designer.design['lyrics']['x'] == 40
    assert 'font' not in designer.design['lyrics']
    designer.position_section.reset_button.click()
    designer.effect_sections[1].reset_button.click()
    assert designer.design['lyrics'] == {}
    for key in ('background', 'elements', 'order'):
        assert designer.design[key] == original[key]
    assert designer.selection == ['lyrics']
    assert designer.text_section.reset_button.isHidden()
    designer.undo_stack.undo()
    designer.undo_stack.undo()
    designer.undo_stack.undo()
    assert designer.design == original


def test_section_reset_edits_multiple_objects_and_only_its_fields(designer):
    load_editable_design(designer, {'version': 1, 'elements': [
        {'id': 'a', 'kind': 'text', 'font_size': 60, 'x': 20, 'opacity': 35},
        {'id': 'b', 'kind': 'text', 'font_size': 80, 'x': 60, 'opacity': 75}]})
    designer.select_objects(['a', 'b'])
    original = copy.deepcopy(designer.design)
    assert not designer.text_section.reset_button.isHidden()
    expanded = designer.text_section.isExpanded()
    designer.text_section.reset_button.click()
    assert designer.text_section.isExpanded() == expanded
    assert designer.text_section.reset_button.isHidden()
    assert [e['font_size'] for e in designer.design['elements']] == [40, 40]
    assert [e['x'] for e in designer.design['elements']] == [20, 60]
    assert [e['opacity'] for e in designer.design['elements']] == [35, 75]
    designer.undo_stack.undo()
    assert designer.design == original
    assert not designer.text_section.reset_button.isHidden()


def test_background_reset_restores_fill_and_image_properties_together(designer):
    designer.set_background_property('colour', '#123456')
    designer.set_background_property('image_opacity', 35)
    original = copy.deepcopy(designer.design)
    assert not designer.background_section.reset_button.isHidden()
    assert not hasattr(designer, 'background_image_section')
    assert designer.background_section.isAncestorOf(designer.background_image_opacity)
    designer.background_section.reset_button.click()
    assert designer.background_section.reset_button.isHidden()
    assert 'background' not in designer.design
    designer.undo_stack.undo()
    assert designer.design == original


def test_section_reset_tracks_actual_theme_values(designer):
    designer.select_object('lyrics')
    defaults = designer.property_defaults('lyrics')
    designer.set_property('font_size', defaults['font_size'])
    assert designer.text_section.reset_button.isHidden()
    designer.set_property('font_size', defaults['font_size'] + 10)
    assert not designer.text_section.reset_button.isHidden()
    designer.text_section.reset_button.click()
    assert designer.selected_properties('lyrics')['font_size'] == defaults['font_size']
    assert designer.text_section.reset_button.isHidden()


def select_three_objects(designer):
    load_editable_design(designer, {'version': 1, 'elements': [
        {'id': 'a', 'kind': 'rectangle', 'x': 10, 'y': 15, 'width': 10, 'height': 10},
        {'id': 'b', 'kind': 'text', 'x': 35, 'y': 30, 'width': 20, 'height': 20},
        {'id': 'c', 'kind': 'ellipse', 'x': 75, 'y': 70, 'width': 15, 'height': 15}],
        'order': ['lyrics', 'a', 'b', 'c']})
    designer.select_objects(['a', 'b', 'c'])


def test_multiple_properties_show_mixed_values_and_edit_applicable_objects_together(designer):
    load_editable_design(designer, {'version': 1, 'lyrics': {'font_size': 40}, 'elements': [
        {'id': 'a', 'kind': 'text', 'font_size': 24, 'opacity': 50, 'text': 'First', 'outline': True},
        {'id': 'b', 'kind': 'text', 'font_size': 48, 'text': 'Second', 'outline': False},
        {'id': 'shape', 'kind': 'rectangle'}]})
    designer.select_objects(['a', 'b', 'shape', 'lyrics'])
    original = copy.deepcopy(designer.document)
    assert not designer.position_section.isHidden()
    assert not designer.text_section.isHidden()
    assert designer.fields['font_size'].text() == ''
    assert designer.fields['opacity'].text() == ''
    assert designer.fields['outline'].checkState() == QtCore.Qt.CheckState.PartiallyChecked
    assert designer.text.toPlainText() == ''
    designer.fields['font_size'].setValue(64)
    assert designer.design['lyrics']['font_size'] == 64
    assert [element.get('font_size') for element in designer.design['elements']] == [64, 64, None]
    designer.undo_stack.undo()
    assert designer.document == original
    designer.fields['outline'].click()
    assert all(element['outline'] for element in designer.design['elements'])
    assert designer.design['lyrics']['outline']
    designer.fields['opacity'].setValue(75)
    assert all(element['opacity'] == 75 for element in designer.design['elements'])
    assert designer.design['lyrics']['opacity'] == 75
    designer.text.setPlainText('Shared caption')
    designer.commit_text()
    assert [element['text'] for element in designer.design['elements'][:2]] == ['Shared caption'] * 2
    assert designer.design['elements'][2]['text'] == ''
    designer.select_objects(['a', 'b'])
    original = copy.deepcopy(designer.document)
    designer.fields['font_size'].setValue(float('nan'))
    assert designer.document == original


def test_slide_edits_do_not_change_master_or_other_slides_and_reset_stays_local(designer):
    from openlp.core.lib.slidelayouts import slide_design
    designer.add_element('text')
    identifier = designer.selected
    with patch.object(designer, 'prompt_layout_name', return_value=('Welcome', True)):
        designer.new_layout()
    master = designer.active_layout()
    page = designer.footer_key()
    master_before = copy.deepcopy(designer.document['masters'][master]['design'])
    designer.document.setdefault('assignments', {})['v2:0:0'] = master
    designer.set_property('font_size', 36)
    designer.set_property('colour', '#123456')
    assert page in designer.document['overrides']
    designer.set_property('font_size', 72)
    assert designer.selected_properties(identifier)['font_size'] == 72
    assert designer.selected_properties(identifier)['colour'] == '#123456'
    assert designer.document['masters'][master]['design'] == master_before
    assert slide_design(designer.document, 'v2:0:0') == master_before
    original = copy.deepcopy(designer.document)
    with patch('openlp.plugins.slide_designer.forms.designer.fluentqt.ContentDialog') as dialog:
        dialog.return_value.ResultPrimary = 1
        dialog.return_value.exec.return_value = 0
        designer.reset_design()
        assert designer.document == original
        dialog.return_value.exec.return_value = 1
        designer.reset_design()
    assert page not in designer.document.get('overrides', {})
    assert designer.document['assignments'][page] == master
    assert slide_design(designer.document, page)['elements'][0]['colour'] == '#ffffff'
    designer.undo_stack.undo()
    assert designer.document == original


def test_reset_all_assigns_theme_keeps_saved_layouts_and_supports_undo(designer):
    from openlp.core.lib.slidelayouts import set_slide_design, layout_for_slide
    load_editable_design(designer, {'version': 1, 'lyrics': {'font_size': 40}, 'elements': []})
    document = set_slide_design(designer.document, 'v1:0:0', {'version': 1, 'lyrics': {'font_size': 60}})
    document = set_slide_design(document, 'v2:0:0', {'version': 1, 'lyrics': {'font_size': 80}})
    load_editable_design(designer, document)
    designer.clear_selection()
    # Reset must remain available when another slide has customisations.
    with patch.object(designer, 'footer_key', return_value='v3:0:0'):
        designer.document.setdefault('assignments', {})['v3:0:0'] = 'theme'
        designer.switch_design_context()
        assert designer.reset_button.isEnabled()
    document = copy.deepcopy(designer.document)
    with patch('openlp.plugins.slide_designer.forms.designer.fluentqt.ContentDialog') as dialog:
        dialog.return_value.ResultPrimary = 1
        dialog.return_value.exec.return_value = 0
        designer.reset_button.click()
        assert designer.document == document
        dialog.return_value.exec.return_value = 1
        designer.reset_button.click()
    assert 'overrides' not in designer.document
    assert 'assignments' not in designer.document
    assert designer.document['masters'] == document['masters']
    for page in ('v1:0:0', 'v2:0:0', 'v3:0:0', 'v4:0:0'):
        assert layout_for_slide(designer.document, page) == 'theme'
        assert not slide_design(designer.document, page)
    assert designer.layout_combo.currentText() == 'Theme'
    assert not designer.reset_button.isEnabled()
    designer.undo_stack.undo()
    assert designer.document == document
    designer.undo_stack.redo()
    saved = designer.serialised_design()
    designer.load_design(saved)
    assert designer.layout_combo.currentText() == 'Theme'


def test_deleting_a_master_keeps_all_assigned_slides_appearance(designer):
    from openlp.core.lib.slidelayouts import slide_design
    load_editable_design(designer, {'version': 1, 'masters': {'welcome': {'name': 'Welcome', 'design': {
        'version': 1, 'lyrics': {'font_size': 72}, 'elements': []}}},
        'assignments': {'v1:0:0': 'welcome', 'v2:0:0': 'welcome'}})
    before = {key: slide_design(designer.document, key) for key in ('v1:0:0', 'v2:0:0')}
    designer.delete_layout()
    assert not designer.document.get('masters')
    for key, design in before.items():
        assert slide_design(designer.document, key) == design


@pytest.mark.parametrize('kind,title,expected', [
    ('song', 'Amazing Grace', 'Amazing Grace - OpenLP+'), ('song', '', 'New Song - OpenLP+'),
    ('custom', 'Welcome', 'Welcome - OpenLP+'), ('custom', '  ', 'New Custom Slide - OpenLP+')])
def test_designer_uses_independent_nonmodal_fluent_window_and_restores_editor_layout(designer, kind, title, expected):
    from openlp.plugins.slide_designer.forms.window import exec_designer_window, DesignerWindow
    from openlp.core.widgets import fluent as QtWidgets
    editor = designer.source_form
    editor.design_kind = kind
    editor.design_owner.title_edit.setText(title)
    observations = []

    def inspect_and_close():
        window = editor.designer_window
        observations.append((isinstance(window, DesignerWindow), window.isVisible(),
                             window.windowModality(), QtWidgets.QApplication.activeModalWidget(),
                             editor.design_owner._designer_open, window.windowTitle()))
        editor.done(0)

    QtCore.QTimer.singleShot(0, inspect_and_close)
    assert exec_designer_window(editor) == 0
    assert observations == [(True, True, QtCore.Qt.WindowModality.NonModal, None, True, expected)]
    assert not editor.design_owner._designer_open
    assert editor.layout() is editor.dialog_layout


@pytest.mark.parametrize('operation,axis,expected', [
    ('left', 'x', [10, 10, 10]), ('center', 'x', [45, 40, 42.5]), ('right', 'x', [80, 70, 75]),
    ('top', 'y', [15, 15, 15]), ('middle', 'y', [45, 40, 42.5]), ('bottom', 'y', [75, 65, 70]),
    ('horizontal', 'x', [10, 37.5, 75]), ('vertical', 'y', [15, 37.5, 70])])
def test_align_and_distribute_selection_are_one_undo_step(designer, operation, axis, expected):
    select_three_objects(designer)
    original = copy.deepcopy(designer.design)
    designer.alignment_actions[operation].trigger()
    assert [element[axis] for element in designer.design['elements']] == expected
    assert designer.undo_stack.count() == 1
    assert designer.selection == ['a', 'b', 'c']
    designer.undo_stack.undo()
    assert designer.design == original


@pytest.mark.parametrize('operation,axis,expected', [
    ('left', 'x', 0), ('center', 'x', 45), ('right', 'x', 90),
    ('top', 'y', 0), ('middle', 'y', 45), ('bottom', 'y', 90)])
def test_align_single_object_uses_slide(designer, operation, axis, expected):
    select_three_objects(designer)
    designer.select_object('a')
    designer.alignment_actions[operation].trigger()
    assert designer.design['elements'][0][axis] == expected


def test_align_pair_uses_selection_and_cannot_distribute(designer):
    select_three_objects(designer)
    designer.select_objects(['a', 'b'])
    designer.alignment_actions['right'].trigger()
    assert [element['x'] for element in designer.design['elements']] == [45, 35, 75]
    assert not designer.alignment_actions['horizontal'].isEnabled()
    assert not designer.alignment_actions['vertical'].isEnabled()
    original = copy.deepcopy(designer.design)
    designer.align_objects('horizontal')
    designer.align_objects('vertical')
    assert designer.design == original


def test_native_layers_multiselection_updates_properties_without_rebuilding_model(designer):
    select_three_objects(designer)
    designer.clear_selection()
    model = designer.layers.model()
    index = model.index(0, 0)
    selection = designer.layers.selectionModel()
    selection.select(index, QtCore.QItemSelectionModel.SelectionFlag.Select)
    selection.select(model.index(1, 0), QtCore.QItemSelectionModel.SelectionFlag.Select)
    assert set(designer.selection) == {'b', 'c'}
    assert designer.selected_label.text() == '2 objects'
    assert not designer.position_section.isHidden()
    assert index.isValid()
    assert len(selection.selectedRows()) == 2
    designer.select_objects(['lyrics', 'a'])
    assert len(selection.selectedRows()) == 2
    assert not hasattr(designer, 'reset_text_button')


def test_multi_drag_flip_and_layer_order_preserve_selection_and_undo(designer):
    select_three_objects(designer)
    designer.select_objects(['lyrics', 'b'])
    designer.arrange('front')
    assert designer.design['order'] == ['a', 'c', 'lyrics', 'b']
    designer.arrange('backward')
    assert designer.design['order'] == ['a', 'lyrics', 'b', 'c']
    before = copy.deepcopy(designer.design)
    designer.flip_objects('horizontal')
    assert designer.design['lyrics']['flip_horizontal'] is True
    assert designer.design['elements'][1]['flip_horizontal'] is True
    designer.undo_stack.undo()
    assert designer.design == before
    count = designer.undo_stack.index()
    designer.canvas_changed({'id': 'lyrics', 'ids': ['lyrics', 'b'], 'changed': True,
                             'geometries': {'lyrics': {'x': 5, 'y': 10}, 'b': {'x': 40, 'y': 35}}})
    assert designer.design['lyrics']['x'] == 5
    assert designer.design['elements'][1]['x'] == 40
    assert designer.undo_stack.index() == count + 1
    designer.undo_stack.undo()
    assert designer.design == before


@pytest.mark.parametrize('kind', ['text', 'rectangle', 'ellipse', 'image'])
def test_outline_shadow_and_flip_controls_persist_and_undo(designer, kind):
    load_editable_design(designer, {'version': 1, 'elements': [{'id': 'object', 'kind': kind,
                                                               'src': 'data:image/png;base64,AAAA'}]})
    designer.select_object('object')
    assert not designer.effect_sections[0].isHidden()
    assert not designer.fields['outline_width'].isEnabled()
    designer.fields['outline'].setChecked(True)
    designer.fields['outline_width'].setValue(3.5)
    designer.set_property('outline_colour', '#123456')
    designer.fields['shadow'].setChecked(True)
    designer.fields['shadow_x'].setValue(-8)
    designer.fields['shadow_blur'].setValue(12)
    designer.flip_objects('vertical')
    element = slide_design(designer.serialised_design(), designer.footer_key())['elements'][0]
    assert element['outline_width'] == 3.5
    assert element['outline_colour'] == '#123456'
    assert element['shadow'] is True
    assert element['shadow_x'] == -8
    assert element['shadow_blur'] == 12
    assert element['flip_vertical'] is True
    designer.undo_stack.undo()
    assert 'flip_vertical' not in designer.design['elements'][0]


def test_multi_row_drop_keeps_relative_order(designer):
    select_three_objects(designer)
    designer.select_objects(['b', 'c'])
    designer.layers.move_row(0, 4)
    assert designer.layers.identifiers() == ['a', 'lyrics', 'c', 'b']
    assert set(designer.selection) == {'b', 'c'}
    designer.delete_element()
    assert [element['id'] for element in designer.design['elements']] == ['a']


def test_pixel_coordinates_and_canvas_change_preserve_shape_proportions(designer):
    designer.add_element('rectangle')
    designer.fields['x'].setValue(192)
    designer.fields['y'].setValue(108)
    designer.fields['width'].setValue(384)
    designer.fields['height'].setValue(216)
    assert designer.design['canvas_width'] == 1920
    assert designer.fields['width'].value() == 384
    original = copy.deepcopy(designer.design)
    designer.canvas_combo.setCurrentIndex(3)  # 4:3
    assert designer.canvas_size() == QtCore.QSize(1440, 1080)
    element = designer.design['elements'][0]
    assert element['width'] * 1440 / 100 == pytest.approx(288)
    assert element['height'] * 1080 / 100 == pytest.approx(162)
    assert (element['x'] + element['width'] / 2) == pytest.approx(20)
    assert (element['y'] + element['height'] / 2) == pytest.approx(27.5)
    designer.undo_stack.undo()
    assert designer.canvas_size() == QtCore.QSize(1920, 1080)
    assert designer.design == original
    assert designer.fields['width'].value() == 384


@pytest.mark.parametrize('alignment', ['left', 'center', 'right', 'top', 'middle', 'bottom',
                                       'horizontal', 'vertical'])
def test_aspect_changes_preserve_aligned_layout_with_different_box_sizes(designer, alignment):
    load_editable_design(designer, {'version': 1, 'canvas_width': 1920, 'canvas_height': 1080,
                                    'lyrics': {'x': 50, 'y': 65, 'width': 45, 'height': 20, 'font_size': 48},
                                    'elements': [
                                        {'id': 'date', 'kind': 'text', 'x': 45, 'y': 15, 'width': 40, 'height': 12},
                                        {'id': 'title', 'kind': 'text', 'x': 55, 'y': 35, 'width': 30, 'height': 18}]})
    designer.select_objects(['date', 'title', 'lyrics'])
    designer.alignment_actions[alignment].trigger()
    original = copy.deepcopy(designer.design)
    for preset, width, height in ((2, 2560, 1080), (3, 1440, 1080), (1, 1920, 1200), (0, 1920, 1080)):
        designer.canvas_combo.setCurrentIndex(preset)
        scale = min(width / 1920, height / 1080)
        before = [original['lyrics']] + original['elements']
        after = [designer.design['lyrics']] + designer.design['elements']
        for first, second in zip(before, after):
            # A single affine transform preserves aligned edges and even gaps regardless of box size.
            for axis, extent, initial, current in (('x', 'width', 1920, width), ('y', 'height', 1080, height)):
                expected_position = (first[axis] / 100 * initial - initial / 2) * scale + current / 2
                assert second[axis] / 100 * current == pytest.approx(expected_position)
                assert second[extent] / 100 * current == pytest.approx(first[extent] / 100 * initial * scale)
    designer.undo_stack.undo()
    assert designer.canvas_size() == QtCore.QSize(1920, 1200)
    designer.undo_stack.redo()
    assert designer.design['lyrics']['x'] == pytest.approx(original['lyrics']['x'])


def test_footer_visibility_is_per_verse_split_and_page_with_undo(designer):
    dialog = designer.source_form
    dialog.set_verse('---[Verse:1]---\nFirst\n---[Chorus:1]---\nChorus')
    dialog.section_combo_box.setCurrentIndex(0)
    designer.page_keys = [(0, 0), (0, 1), (1, 0)]
    designer.clear_selection()
    designer.show_footer.setChecked(False)
    assert designer.design['hidden_footers'] == ['v1:0:0']
    designer.page_index = 1
    designer.populate_inspector()
    assert designer.show_footer.isChecked()
    designer.show_footer.setChecked(False)
    assert designer.design['hidden_footers'] == ['v1:0:0', 'v1:0:1']
    designer.undo_stack.undo()
    assert designer.show_footer.isChecked()
    dialog.section_combo_box.setCurrentIndex(1)
    designer.populate_inspector()
    assert designer.footer_key() == 'c1:0:0'
    assert designer.show_footer.isChecked()


def test_custom_footer_uses_outer_slide_number_and_survives_reorder_delete(designer):
    from openlp.plugins.custom.forms.editcustomform import EditCustomForm
    owner = EditCustomForm(MagicMock(), None, MagicMock())
    owner.slide_list_view.addItems(['First', 'Second', 'Third'])
    owner.slide_design = {'version': 1, 'hidden_footers': ['custom-2:0:0']}
    dialog = owner.edit_slide_form
    dialog.designer_slide_offset = 1
    dialog.set_text('Second')
    dialog.slide_designer.load_design(owner.slide_design)
    assert dialog.slide_designer.footer_key() == 'custom-2:0:0'
    assert not dialog.slide_designer.show_footer.isChecked()
    owner.slide_list_view.setCurrentRow(1)
    owner.on_up_button_clicked()
    assert owner.slide_design['hidden_footers'] == ['custom-1:0:0']
    owner.on_delete_button_clicked()
    assert owner.slide_design['hidden_footers'] == []
    dialog.deleteLater()
    owner.deleteLater()


def test_repeated_aspect_switches_return_to_original_geometry(designer):
    designer.add_element('rectangle')
    designer.fields['x'].setValue(250)
    designer.fields['y'].setValue(120)
    designer.fields['width'].setValue(384)
    designer.fields['height'].setValue(216)
    designer.add_element('text')
    designer.fields['font_size'].setValue(48)
    original = copy.deepcopy(designer.design['elements'])
    layouts = {}
    for _ in range(6):
        for preset in (1, 3, 2, 0):
            designer.canvas_combo.setCurrentIndex(preset)
            actual = designer.design['elements']
            if preset in layouts:
                for first, second in zip(layouts[preset], actual):
                    for key in ('x', 'y', 'width', 'height', 'font_size'):
                        assert second[key] == pytest.approx(first[key])
            else:
                layouts[preset] = copy.deepcopy(actual)
    for first, second in zip(original, designer.design['elements']):
        for key in ('x', 'y', 'width', 'height', 'font_size'):
            assert second[key] == pytest.approx(first[key])
    # The reference survives closing/reopening the editor on a different aspect ratio.
    designer.canvas_combo.setCurrentIndex(3)
    saved = designer.serialised_design()
    load_editable_design(designer, saved)
    designer.canvas_combo.setCurrentIndex(0)
    for first, second in zip(original, designer.design['elements']):
        for key in ('x', 'y', 'width', 'height', 'font_size'):
            assert second[key] == pytest.approx(first[key])


@pytest.mark.parametrize('accepted', [True, False])
def test_layout_name_content_dialog_has_header_and_rejects_blank_names(designer, accepted):
    import fluentqt
    from openlp.core.widgets import fluent as QtWidgets

    def inspect(dialog):
        assert dialog.title() == 'New layout'
        assert dialog.primaryButtonText() == 'Create'
        assert dialog.closeButtonText() == 'Cancel'
        field = dialog.findChild(QtWidgets.QLineEdit, 'layout_name_edit')
        primary = next(button for button in dialog.findChildren(fluentqt.Button) if button.text() == 'Create')
        assert not primary.isEnabled()
        field.setText('   ')
        assert not primary.isEnabled()
        field.setText('  Welcome  ')
        assert primary.isEnabled()
        return dialog.ResultPrimary if accepted else dialog.ResultNone

    before = copy.deepcopy(designer.document)
    with patch.object(fluentqt.ContentDialog, 'exec', inspect):
        designer.new_layout()
    if accepted:
        assert designer.document['masters'][designer.active_layout()]['name'] == 'Welcome'
    else:
        assert designer.document == before


def test_rename_layout_content_dialog_has_header_and_existing_name(designer):
    import fluentqt
    from openlp.core.widgets import fluent as QtWidgets

    def inspect(dialog):
        assert dialog.title() == 'Rename layout'
        assert dialog.primaryButtonText() == 'Rename'
        field = dialog.findChild(QtWidgets.QLineEdit, 'layout_name_edit')
        assert field.text() == 'Welcome'
        assert field.selectedText() == 'Welcome'
        field.setText('Closing')
        return dialog.ResultPrimary

    with patch.object(fluentqt.ContentDialog, 'exec', inspect):
        assert designer.prompt_layout_name('Rename layout', 'Welcome') == ('Closing', True)


def test_new_slide_uses_theme_and_locks_all_design_changes(designer):
    designer.load_design({})
    assert designer.active_layout() == 'theme'
    assert designer.layout_combo.currentText() == 'Theme'
    assert designer.layout_combo.findData('default') == -1
    before = copy.deepcopy(designer.document)
    designer.add_element('text')
    designer.select_object('lyrics')
    designer.set_property('x', 20)
    designer.set_background_property('colour', '#123456')
    designer.set_filter('blur', 5)
    designer.canvas_changed({'id': 'lyrics', 'changed': True, 'geometry': {'x': 50}})
    assert designer.document == before
    for key, (drawer, _) in designer.reset_sections.items():
        assert drawer.isEnabled() == (key == 'slide')
    designer.set_footer_visible(False)
    assert designer.footer_key() in designer.document['hidden_footers']
    designer.reset_section('slide')
    assert not designer.document.get('hidden_footers')
    designer.canvas_combo.setCurrentIndex(2)
    assert designer.canvas_size() == QtCore.QSize(2560, 1080)
    assert not designer.document.get('overrides')
    with patch.object(designer, 'prompt_layout_name', return_value=('Welcome', True)):
        designer.new_layout()
    assert designer.design_editable()
    designer.add_element('text')
    assert len(designer.design['elements']) == 1
    designer.layout_combo.setCurrentIndex(designer.layout_combo.findData('theme'))
    assert not designer.design.get('elements')
    assert not designer.design_editable()


def test_song_does_not_invent_a_custom_layout_for_saved_formatting(designer):
    source = {'version': 1, 'lyrics': {'font_size': 60}, 'custom_layout_name': 'Previous design'}
    designer.load_design(source)
    assert designer.layout_combo.count() == 1
    assert designer.layout_combo.currentText() == 'Theme'
    assert not designer.rename_layout_button.isEnabled()
    assert designer.design['lyrics']['font_size'] == 60
    assert not designer.design_editable()


def test_custom_layout_can_be_renamed_saved_and_undone(designer):
    designer.source_form.design_kind = 'custom'
    designer.load_design({'version': 1, 'lyrics': {'font_size': 60}})
    original = copy.deepcopy(designer.design)
    assert designer.layout_combo.currentText() == 'Custom'
    assert designer.rename_layout_button.isEnabled()
    assert not designer.delete_layout_button.isEnabled()
    with patch.object(designer, 'prompt_layout_name', return_value=('Welcome', True)) as prompt:
        designer.rename_layout()
    prompt.assert_called_once_with('Rename layout', 'Custom')
    assert designer.layout_combo.currentText() == 'Welcome'
    assert designer.active_layout() == 'default'
    assert designer.design == original
    designer.undo_stack.undo()
    assert designer.layout_combo.currentText() == 'Custom'
    designer.undo_stack.redo()
    designer.load_design(designer.serialised_design())
    assert designer.layout_combo.currentText() == 'Welcome'
    assert designer.design == original
    designer.layout_combo.setCurrentIndex(designer.layout_combo.findData('theme'))
    assert not designer.rename_layout_button.isEnabled()


def test_effects_target_background_and_images_with_mixed_selection_and_undo(designer):
    load_editable_design(designer, {'version': 1, 'elements': [
        {'id': 'a', 'kind': 'image', 'src': 'data:image/png;base64,AAAA', 'filters': {'blur': 5}},
        {'id': 'b', 'kind': 'image', 'src': 'data:image/png;base64,AAAA'},
        {'id': 'text', 'kind': 'text'}]})
    designer.select_objects(['a', 'b', 'text'])
    assert designer.filters_section.isEnabled()
    import math
    assert math.isnan(designer.filter_fields['blur'].value())
    designer.filter_fields['contrast'].setValue(125)
    assert [element.get('filters', {}).get('contrast') for element in designer.design['elements']] == [125, 125, None]
    assert designer.design['elements'][0]['filters']['blur'] == 5
    designer.select_object('text')
    assert not designer.filters_section.isEnabled()
    designer.clear_selection()
    assert designer.filters_section.isEnabled()
    designer.filter_fields['sepia'].setValue(50)
    designer.filter_fields['brightness'].setValue(80)
    assert designer.design['background_filters'] == {'brightness': 80, 'sepia': 50}
    assert designer.section_modified('effects')
    designer.reset_section('effects')
    assert 'background_filters' not in designer.design
    assert not designer.section_modified('effects')
    designer.undo_stack.undo()
    saved = designer.serialised_design()
    load_editable_design(designer, saved)
    assert designer.design['background_filters'] == {'brightness': 80, 'sepia': 50}
    assert designer.design['elements'][0]['filters'] == {'blur': 5, 'contrast': 125}
    for drawer, _ in designer.reset_sections.values():
        assert drawer.reset_button.text() == ''
        assert not drawer.reset_button.icon().isNull()
