"""Canvas/inspector behaviour without needing a native browser process."""
import copy
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore
from openlp.core.common import ThemeLevel
from openlp.core.common.registry import Registry
from openlp.core.lib.theme import Theme
from openlp.plugins.songs.forms.editsongform import EditSongForm


@pytest.fixture
def designer(settings):
    manager = MagicMock()
    manager.global_theme = 'Global'
    manager.get_theme_names.return_value = ['Global', 'Song', 'Service']
    Registry().register('theme_manager', manager)
    form = EditSongForm(MagicMock(), None, MagicMock())
    with patch('openlp.core.widgets.slidedesigner.ScreenList') as screens:
        screens.return_value.current.display_geometry.size.return_value = QtCore.QSize(1920, 1080)
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
    designer.load_design(original)
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
    assert designer.serialised_design()['elements'][0]['text'] == 'Final unsaved keystrokes'
    designer.text.setPlainText('Discard this draft')
    designer.load_design(None)
    designer.commit_text()
    assert designer.design == {}
    assert designer.undo_stack.count() == 0


def test_switch_layer_preserves_pending_text_and_selection(designer):
    designer.add_element('text')
    designer.text.setPlainText('New caption')
    designer.layers.setCurrentIndex(0)
    assert designer.selected == 'lyrics'
    assert designer.design['elements'][0]['text'] == 'New caption'


def test_preview_theme_sources_follow_output_level(designer, settings):
    form = designer.source_form
    form.theme_combo_box.addItems(['Song'])
    form.theme_combo_box.setCurrentText('Song')
    designer.theme_source.setCurrentIndex(0)
    settings.setValue('themes/theme level', ThemeLevel.Global)
    designer.resolve_theme()
    designer.theme_manager.get_theme_data.assert_called_with('Global')
    settings.setValue('themes/theme level', ThemeLevel.Song)
    designer.resolve_theme()
    designer.theme_manager.get_theme_data.assert_called_with('Song')
    designer.theme_source.setCurrentIndex(1)
    designer.resolve_theme()
    designer.theme_manager.get_theme_data.assert_called_with('Global')
    settings.setValue('servicemanager/service theme', 'Service')
    designer.theme_source.setCurrentIndex(3)
    designer.resolve_theme()
    designer.theme_manager.get_theme_data.assert_called_with('Service')


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
    designer.load_design({'version': 1, 'lyrics': {'x': 25}, 'elements': []})
    designer.refresh()
    assert designer.display.set_theme.call_args.args[0].font_main_x == 480
    designer.display.load_verses.assert_called_with(
        [{'verse': 'designer', 'text': 'New lyrics', 'footer': 'Draft footer'}])
    form.design_owner.manager.save_object.assert_not_called()


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
    from openlp.core.widgets.fluent_dialogs import TextEditorDialog
    owner = designer.source_form.design_owner
    owner.slide_design = {'version': 1, 'lyrics': {'x': 10}, 'elements': []}
    original = copy.deepcopy(owner.slide_design)

    def edit_and_finish(dialog):
        assert dialog.slide_designer.design['lyrics']['x'] == 10
        dialog.slide_designer.set_property('x', 35)
        return int(accepted)

    with patch.object(TextEditorDialog, 'exec', new=edit_and_finish):
        designer.source_form.exec()
    assert owner.slide_design['lyrics']['x'] == (35 if accepted else 10)
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
    designer.load_design({'version': 1, 'lyrics': {'x': 15}, 'theme': {
        'background_type': 'solid', 'background_color': '#123456'}})
    designer.source_form.theme_combo_box.addItem('Song')
    assert 'theme' not in designer.design
    assert designer.design['lyrics']['x'] == 15
    assert designer.theme_source.currentIndex() == 2
