"""Choose the optional visual editor without loading it when the plugin is disabled."""
from openlp.core.common.enum import PluginStatus
from openlp.core.common.registry import Registry


def get_slide_editor(owner, kind, current=None):
    registry = Registry()
    if registry.has('slide_designer_plugin'):
        enabled = registry.get('slide_designer_plugin').is_active()
    else:
        enabled = registry.get('settings').value('slide_designer/status') == PluginStatus.Active
    if current is not None and getattr(current, 'uses_slide_designer', False) == enabled:
        return current
    if enabled:
        from openlp.plugins.slide_designer.forms import SongSlideDesigner, CustomSlideDesigner
        editor_class = SongSlideDesigner if kind == 'song' else CustomSlideDesigner
    elif kind == 'song':
        from openlp.plugins.songs.forms.editverseform import EditVerseForm
        editor_class = EditVerseForm
    else:
        from openlp.plugins.custom.forms.editcustomslideform import EditCustomSlideForm
        editor_class = EditCustomSlideForm
    editor = editor_class(owner)
    if current is not None:
        current.deleteLater()
    return editor
