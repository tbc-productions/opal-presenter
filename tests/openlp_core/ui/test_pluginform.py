"""Plugin Manager ordering, metadata and interaction contracts."""
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

from opal.core.lib.plugin import PluginStatus
from opal.core.ui.pluginform import PluginForm
from opal.plugins.projector.projectorplugin import ProjectorPlugin
from opal.plugins.projector import projectorplugin


def make_plugin(name, status=PluginStatus.Inactive, **metadata):
    plugin = SimpleNamespace(name_strings={'singular': name}, status=status, icon=None,
                             version='1.2.3', developer='', licence='', website='', can_be_disabled=True,
                             about=lambda: '<p>A plugin description.</p>', app_startup=MagicMock())
    plugin.__dict__.update(metadata)
    plugin.toggle_status = MagicMock(side_effect=lambda status: setattr(plugin, 'status', status))
    return plugin


@pytest.fixture
def plugin_form(mock_settings, qtbot):
    plugins = []
    with patch('opal.core.ui.pluginform.State') as state:
        state.return_value.list_plugins.return_value = plugins
        form = PluginForm()
        qtbot.addWidget(form)
        yield form, plugins


def listed_plugins(form):
    return [form.plugin_list_widget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)
            for row in range(form.plugin_list_widget.count())]


def test_active_plugins_first_then_alphabetical(plugin_form):
    form, plugins = plugin_form
    inactive = make_plugin('Alpha', str(PluginStatus.Inactive.value))
    active_z = make_plugin('Zulu', PluginStatus.Active)
    active_a = make_plugin('alpha', str(PluginStatus.Active.value))
    disabled = make_plugin('Bravo', PluginStatus.Disabled)
    plugins.extend([inactive, active_z, None, disabled, active_a])
    form.load()

    assert listed_plugins(form) == [active_a, active_z, inactive, disabled]
    assert plugins == [inactive, active_z, None, disabled, active_a]
    assert form.active_plugin is active_a
    assert form.status_checkbox.isChecked()
    assert all(not plugin.toggle_status.called for plugin in plugins if plugin)


def test_toggling_reorders_and_preserves_selected_plugin(plugin_form):
    form, plugins = plugin_form
    other = make_plugin('Beta', PluginStatus.Active)
    selected = make_plugin('Alpha (Community)')
    duplicate = make_plugin('Alpha (Community)')
    plugins.extend([other, duplicate, selected])
    form.load(selected_plugin=selected)

    form.status_checkbox.setChecked(True)
    assert listed_plugins(form) == [selected, other, duplicate]
    assert form.active_plugin is selected
    assert form.plugin_list_widget.currentRow() == 0
    selected.toggle_status.assert_called_once_with(PluginStatus.Active)
    selected.app_startup.assert_called_once_with()

    form.status_checkbox.setChecked(False)
    assert listed_plugins(form) == [other, duplicate, selected]
    assert form.active_plugin is selected
    assert form.plugin_list_widget.currentRow() == 2
    assert not form.status_checkbox.isChecked()
    assert selected.toggle_status.call_count == 2
    duplicate.toggle_status.assert_not_called()


def test_bundled_metadata_is_hidden_without_explicit_values(settings, state, qtbot):
    plugin = ProjectorPlugin()
    form = PluginForm()
    qtbot.addWidget(form)
    text = form.about_text_browser.toPlainText()
    assert plugin.version
    assert not plugin.version_is_explicit
    for field in ['Version', 'Developer', 'Licence', 'Website', 'Updates']:
        assert field + ':' not in text
    assert 'About' in text
    assert '<hr' not in form.about_text_browser.toHtml()
    assert form.plugin_folder == Path(projectorplugin.__file__).resolve().parent
    assert form.open_folder_button.isEnabled()
    assert not form.open_folder_button.icon().isNull()
    assert form.open_folder_button.text() == 'Open Plugin Folder'


def test_explicit_version_is_shown_even_when_equal_to_application_version(settings, state, qtbot):
    plugin = ProjectorPlugin()
    plugin._setup(plugin.version)
    form = PluginForm()
    qtbot.addWidget(form)
    assert plugin.version_is_explicit
    assert f'Version: {plugin.version}' in form.about_text_browser.toPlainText()


def test_community_metadata_is_escaped_and_linked(plugin_form):
    form, plugins = plugin_form
    plugin = make_plugin('Community', developer='A <Developer> & Team', licence='MIT',
                         website='https://example.org/plugin?a=1&b=2')
    plugins.append(plugin)
    form.load()
    text = form.about_text_browser.toPlainText()
    assert 'Developer: A <Developer> & Team' in text
    assert 'Licence: MIT' in text
    assert 'Version: 1.2.3' in text
    assert 'Updates:' not in text
    assert 'href="https://example.org/plugin?a=1&amp;b=2"' in form.about_text_browser.toHtml()
    assert form.about_text_browser.openExternalLinks()


@pytest.mark.parametrize('website', ['', 'file:///tmp/plugin', 'https://[invalid'])
def test_missing_community_metadata_and_invalid_website(plugin_form, website):
    form, plugins = plugin_form
    plugins.append(make_plugin('Community', website=website))
    form.load()
    text = form.about_text_browser.toPlainText()
    assert 'Developer:' not in text
    assert 'Licence:' not in text
    assert 'Updates:' not in text
    assert 'href=' not in form.about_text_browser.toHtml()
    if website:
        assert 'Website: ' + website in text
    else:
        assert 'Website:' not in text


@pytest.mark.parametrize('empty_value', [None, '', '   '])
def test_empty_metadata_hidden_and_selection_clears_previous_values(plugin_form, empty_value):
    form, plugins = plugin_form
    supplied = make_plugin('Supplied', updates='Download <new> versions from the developer.')
    empty = make_plugin('Empty', version=empty_value, developer=empty_value, licence=empty_value,
                        website=empty_value, updates=empty_value)
    plugins.extend([supplied, empty])
    form.load(supplied)
    assert 'Updates: Download <new> versions from the developer.' in form.about_text_browser.toPlainText()
    form.plugin_list_widget.setCurrentRow(0)
    assert form.active_plugin is empty
    text = form.about_text_browser.toPlainText()
    for field in ['Version', 'Developer', 'Licence', 'Website', 'Updates']:
        assert field + ':' not in text
    assert '<hr' not in form.about_text_browser.toHtml()


@pytest.mark.parametrize('status,can_be_disabled,checked', [
    (PluginStatus.Disabled, True, False), (PluginStatus.Active, False, True),
])
def test_unavailable_and_required_plugins_cannot_be_toggled(plugin_form, status, can_be_disabled, checked):
    form, plugins = plugin_form
    plugins.append(make_plugin('Protected', status, can_be_disabled=can_be_disabled))
    form.load()
    assert not form.status_checkbox.isEnabled()
    assert form.status_checkbox.isChecked() is checked
    plugins[0].toggle_status.assert_not_called()


def test_empty_list_clears_selection_and_details(plugin_form):
    form, plugins = plugin_form
    plugins.append(make_plugin('Alpha', PluginStatus.Active))
    form.load()
    plugins.clear()
    form.load()
    assert form.active_plugin is None
    assert not form.status_checkbox.isEnabled()
    assert not form.status_checkbox.isChecked()
    assert not form.about_text_browser.toPlainText()
    assert not form.programmatic_change
    assert not form.open_folder_button.isEnabled()
    assert form.plugin_folder is None


@pytest.mark.parametrize('dismiss', ['mouse', 'enter', 'escape'])
def test_close_with_mouse_and_keyboard(plugin_form, qtbot, dismiss):
    form, plugins = plugin_form
    form.show()
    close = form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
    close.setFocus()
    if dismiss == 'mouse':
        qtbot.mouseClick(close, QtCore.Qt.MouseButton.LeftButton)
    else:
        qtbot.keyClick(close, QtCore.Qt.Key.Key_Return if dismiss == 'enter' else QtCore.Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not form.isVisible())


def test_long_details_scroll_in_narrow_host(mock_settings, qtbot):
    host = QtWidgets.QWidget()
    qtbot.addWidget(host)
    host.resize(680, 500)
    plugin = make_plugin('A plugin with a long name', developer='An organisation and its contributors ' * 5,
                         about=lambda: '<p>' + 'A long description. ' * 200 + '</p>')
    with patch('opal.core.ui.pluginform.State') as state:
        state.return_value.list_plugins.return_value = [plugin]
        form = PluginForm(host)
        qtbot.addWidget(form)
        form.setAnimationEnabled(False)
        host.show()
        form.open()
        qtbot.waitUntil(lambda: form.about_text_browser.verticalScrollBar().maximum() > 0)
        assert form.width() <= host.width()
        assert form.height() <= host.height()
        assert form.about_text_browser.horizontalScrollBar().maximum() == 0
        assert form.button_box.geometry().bottom() < form.height()
        assert form.plugin_list_widget.currentItem().toolTip() == 'A plugin with a long name (Inactive)'
        qtbot.mouseClick(form.status_checkbox, QtCore.Qt.MouseButton.LeftButton,
                         pos=QtCore.QPoint(10, form.status_checkbox.height() // 2))
        plugin.toggle_status.assert_called_once_with(PluginStatus.Active)


@pytest.fixture
def community_folder(tmp_path, monkeypatch):
    folder = tmp_path / 'Community plugin #1'
    folder.mkdir()
    module = ModuleType('contrib.plugins.example.exampleplugin')
    module.__file__ = str(folder / 'exampleplugin.py')
    monkeypatch.setitem(sys.modules, module.__name__, module)
    plugin_class = type('CommunityPlugin', (SimpleNamespace,), {'__module__': module.__name__})
    return plugin_class(**make_plugin('Community').__dict__), folder, module


@pytest.mark.parametrize('interaction', ['mouse', 'enter'])
def test_open_community_folder_keeps_manager_open(plugin_form, community_folder, qtbot, interaction):
    form, plugins = plugin_form
    plugin, folder, module = community_folder
    plugins.append(plugin)
    form.load()
    form.setAnimationEnabled(False)
    form.show()
    assert form.open_folder_button.toolTip() == str(folder)
    with patch('opal.core.ui.pluginform.QtGui.QDesktopServices.openUrl', return_value=True) as open_url:
        if interaction == 'mouse':
            qtbot.mouseClick(form.open_folder_button, QtCore.Qt.MouseButton.LeftButton)
        else:
            form.open_folder_button.setFocus()
            qtbot.keyClick(form.open_folder_button, QtCore.Qt.Key.Key_Return)
        open_url.assert_called_once_with(QtCore.QUrl.fromLocalFile(str(folder)))
        assert form.isVisible()
        assert form.active_plugin is plugin


@pytest.mark.parametrize('module_file', [None, '/missing/plugin/folder/plugin.py'])
def test_unavailable_plugin_folder_disables_button(plugin_form, community_folder, module_file):
    form, plugins = plugin_form
    plugin, folder, module = community_folder
    module.__file__ = module_file
    plugins.append(plugin)
    form.load()
    assert not form.open_folder_button.isEnabled()
    assert 'not available on disk' in form.open_folder_button.toolTip()


@pytest.mark.parametrize('deleted_folder', [False, True])
def test_open_plugin_folder_failure_is_reported(plugin_form, community_folder, deleted_folder):
    form, plugins = plugin_form
    plugin, folder, module = community_folder
    plugins.append(plugin)
    form.load()
    if deleted_folder:
        folder.rmdir()
    with patch('opal.core.ui.pluginform.QtGui.QDesktopServices.openUrl', return_value=False) as open_url, \
            patch('opal.core.ui.pluginform.QtWidgets.QMessageBox.warning') as warning:
        form.on_open_folder_clicked()
        assert open_url.call_count == (0 if deleted_folder else 1)
        warning.assert_called_once()
        assert form.active_plugin is plugin
