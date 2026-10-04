"""Expose the remote interface through Plugin Manager."""

from openlp.core.api.tab import ApiTab
from openlp.core.common.i18n import translate
from openlp.core.lib.optionalfeature import RestartRequiredFeature
from openlp.core.lib.plugin import Plugin, StringContent
from openlp.core.state import State
from openlp.core.ui.icons import UiIcons


class RemoteInterfacePlugin(RestartRequiredFeature, Plugin):
    def __init__(self):
        super().__init__('remote_interface')
        self.weight = 21
        self.icon = UiIcons().remote
        State().add_service(self.name, self.weight, is_plugin=True)
        State().update_pre_conditions(self.name, self.check_pre_conditions())

    def set_plugin_text_strings(self):
        name = translate('RemoteInterfacePlugin', 'Remote Interface')
        self.text_strings[StringContent.Name] = {'singular': name, 'plural': name}

    def create_settings_tab(self, parent):
        self.settings_tab = ApiTab(parent)
        parent.api_tab = self.settings_tab

    @staticmethod
    def about():
        return translate('RemoteInterfacePlugin', 'Provide remote control, stage, live and chords views '
                         'through the HTTP and WebSocket servers. Enable or disable this plugin, then '
                         'restart OpenLP+ to apply the change. Saved remote configuration is kept when disabled.')
