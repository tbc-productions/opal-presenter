"""The optional editor must fall back to the original dialogs without discarding designs."""
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest

from openlp.core.common.enum import PluginStatus
from openlp.core.common.registry import Registry
from openlp.core.lib.plugin import StringContent
from openlp.core.widgets.slideeditor import get_slide_editor
from openlp.plugins.slide_designer.slide_designer_plugin import SlideDesignerPlugin
from openlp.plugins.songs.forms.editsongform import EditSongForm
from openlp.plugins.songs.forms.editverseform import EditVerseForm
from openlp.plugins.custom.forms.editcustomform import EditCustomForm
from openlp.plugins.custom.forms.editcustomslideform import EditCustomSlideForm


@pytest.mark.parametrize('kind', ['song', 'custom'])
def test_checking_another_item_does_not_reuse_an_open_designer_draft(kind):
    from openlp.plugins.songs.lib.mediaitem import SongMediaItem
    from openlp.plugins.custom.lib.mediaitem import CustomMediaItem

    attribute = 'edit_song_form' if kind == 'song' else 'edit_custom_form'
    module = 'songs' if kind == 'song' else 'custom'
    form_class = 'EditSongForm' if kind == 'song' else 'EditCustomForm'
    media_class = SongMediaItem if kind == 'song' else CustomMediaItem
    draft = MagicMock(_designer_open=True)
    item = SimpleNamespace(**{attribute: draft}, main_window=MagicMock(), plugin=MagicMock())
    with patch(f'openlp.plugins.{module}.lib.mediaitem.{form_class}') as new_form:
        media_class.ensure_available_editor(item)
        assert getattr(item, attribute) is new_form.return_value
        draft.load_song.assert_not_called()
        draft.load_custom.assert_not_called()


@pytest.mark.parametrize('kind', ['song', 'custom'])
def test_plugin_toggle_switches_the_next_editor_and_preserves_designs(settings, state, kind):
    Registry().register('theme_manager', MagicMock())
    plugin = SlideDesignerPlugin()
    assert plugin.text_strings[StringContent.Name]['singular'] == 'Slide Designer'
    assert plugin.is_active()
    owner_class = EditSongForm if kind == 'song' else EditCustomForm
    owner = owner_class(MagicMock(), None, MagicMock())
    attribute = 'verse_form' if kind == 'song' else 'edit_slide_form'
    original = getattr(owner, attribute)
    assert hasattr(original, 'slide_designer')
    owner.slide_design = {'version': 1, 'background': {'type': 'solid', 'colour': '#123456'}}
    plugin.toggle_status(PluginStatus.Inactive)
    basic_class = EditVerseForm if kind == 'song' else EditCustomSlideForm
    with patch.object(basic_class, 'exec', return_value=0):
        if kind == 'song':
            owner.on_verse_add_button_clicked()
        else:
            owner.on_add_button_clicked()
    basic = getattr(owner, attribute)
    assert type(basic) is basic_class
    assert basic.parentWidget() is owner
    assert not hasattr(basic, 'slide_designer')
    assert not hasattr(basic, 'editor_splitter')
    assert owner.slide_design['background']['colour'] == '#123456'
    assert settings.value('slide_designer/status') == PluginStatus.Inactive
    plugin.toggle_status(PluginStatus.Active)
    restored = get_slide_editor(owner, kind, basic)
    assert restored.uses_slide_designer
    assert restored.design_owner is owner
    assert owner.slide_design['background']['colour'] == '#123456'
    restored.deleteLater()
    owner.deleteLater()


@pytest.mark.parametrize('kind', ['song', 'custom'])
def test_starting_disabled_constructs_only_the_basic_editor(settings, state, kind):
    Registry().register('theme_manager', MagicMock())
    settings.setValue('slide_designer/status', PluginStatus.Inactive)
    plugin = SlideDesignerPlugin()
    assert not plugin.is_active()
    owner_class = EditSongForm if kind == 'song' else EditCustomForm
    owner = owner_class(MagicMock(), None, MagicMock())
    editor = owner.verse_form if kind == 'song' else owner.edit_slide_form
    assert type(editor) is (EditVerseForm if kind == 'song' else EditCustomSlideForm)
    assert not hasattr(editor, 'slide_designer')
    owner.deleteLater()
