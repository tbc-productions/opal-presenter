"""Optional features are discoverable, reversible plugins."""
from unittest.mock import patch

import pytest

from openlp.core.common.enum import PluginStatus
from openlp.core.lib.plugin import Plugin
from openlp.core.state import State
from openlp.core.ui.pluginform import PluginForm
from openlp.core.ui.settingsform import SettingsForm
from openlp.plugins.projector.projectorplugin import ProjectorPlugin
from openlp.plugins.remote_interface.remoteinterfaceplugin import RemoteInterfacePlugin


@pytest.mark.parametrize('plugin_class,alias,configuration', [
    (ProjectorPlugin, 'projector_tab', 'projector/connect on start'),
    (RemoteInterfacePlugin, 'api_tab', 'api/ip address'),
])
def test_optional_plugin_activation(settings, state, registry, plugin_class, alias, configuration):
    """Activation changes persist and retain existing configuration."""
    plugin = plugin_class()
    assert plugin_class in Plugin.__subclasses__()
    assert plugin in State().list_plugins()
    assert plugin.can_be_disabled
    assert not plugin.is_active()
    original_configuration = settings.value(configuration)
    with patch.object(plugin, 'initialise') as start, patch.object(plugin, 'finalise') as stop:
        plugin.toggle_status(PluginStatus.Active)
        assert plugin.is_active()
        assert settings.value(f'{plugin.name}/status') == PluginStatus.Active
        plugin.toggle_status(PluginStatus.Inactive)
        assert not plugin.is_active()
        assert settings.value(f'{plugin.name}/status') == PluginStatus.Inactive
        start.assert_not_called()
        stop.assert_not_called()
    assert settings.value(configuration) == original_configuration
    registry.set_flag('no_web_server', True)
    form = SettingsForm(None)
    plugin.create_settings_tab(form)
    assert getattr(form, alias) is plugin.settings_tab
    plugin.settings_tab.close()
    form.close()


def test_plugin_manager_lists_features_and_explains_restart(settings, state, registry):
    """Plugin Manager exposes both features and explains when changes take effect."""
    projector = ProjectorPlugin()
    remote = RemoteInterfacePlugin()
    form = PluginForm(None)
    form.load()
    assert form.plugin_list_widget.count() == 2
    assert form.status_checkbox.isEnabled()
    with patch('openlp.core.ui.pluginform.show_restart_message') as message:
        form.status_checkbox.setChecked(True)
        assert projector.is_active()
        message.assert_called_once()
        message.reset_mock()
        form.status_checkbox.setChecked(False)
        assert not projector.is_active()
        message.assert_called_once()
    assert not remote.is_active()
    form.close()
