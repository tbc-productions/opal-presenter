"""Expose projector control through Plugin Manager."""

from openlp.core.common.i18n import translate
from openlp.core.lib.optionalfeature import RestartRequiredFeature
from openlp.core.lib.plugin import Plugin, StringContent
from openlp.core.projectors.tab import ProjectorTab
from openlp.core.state import State
from openlp.core.ui.icons import UiIcons


class ProjectorPlugin(RestartRequiredFeature, Plugin):
    def __init__(self):
        super().__init__('projector')
        self.weight = 20
        self.icon = UiIcons().projector
        State().add_service(self.name, self.weight, is_plugin=True)
        State().update_pre_conditions(self.name, self.check_pre_conditions())

    def set_plugin_text_strings(self):
        name = translate('ProjectorPlugin', 'Projector')
        self.text_strings[StringContent.Name] = {'singular': name, 'plural': name}

    def create_settings_tab(self, parent):
        self.settings_tab = ProjectorTab(parent)
        parent.projector_tab = self.settings_tab

    @staticmethod
    def about():
        return translate('ProjectorPlugin', 'Control network projectors using PJLink. '
                         'Enable or disable this plugin, then restart Opal Presenter to apply the change. '
                         'Saved projector configuration is kept when disabled.')
