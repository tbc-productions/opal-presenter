"""Expose the optional visual editor in Plugin Manager."""
from openlp.core.common.i18n import translate
from openlp.core.lib.plugin import Plugin, StringContent
from openlp.core.state import State
from openlp.core.ui.icons import UiIcons


class SlideDesignerPlugin(Plugin):
    def __init__(self):
        super().__init__('slide_designer')
        self.weight = 9
        self.icon = UiIcons().edit
        State().add_service(self.name, self.weight, is_plugin=True)
        State().update_pre_conditions(self.name, self.check_pre_conditions())

    def set_plugin_text_strings(self):
        name = translate('SlideDesignerPlugin', 'Slide Designer')
        self.text_strings[StringContent.Name] = {'singular': name, 'plural': name}
        self.text_strings[StringContent.VisibleName] = {'title': name}

    @staticmethod
    def about():
        return translate('SlideDesignerPlugin',
                         'Edit songs and custom slides in one window with metadata, backgrounds, '
                         'images, shapes, text boxes and layers. When disabled, the original editing dialogs are used. '
                         'Saved designs remain available. Changes take effect the next time an editor is opened.')
