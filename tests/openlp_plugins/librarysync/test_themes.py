"""Themes retain their native format, selection and safe, portable backgrounds."""
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6 import QtCore

from openlp.core.common.registry import Registry
from openlp.core.display.screens import ScreenList
from openlp.core.lib.theme import Theme
from openlp.core.ui.thememanager import ThemeManager
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.dnd import ThemeDragData
from openlp.core.widgets.themeviews import ThemeViews
from openlp.plugins.librarysync.lib.panel import CloudDragData, CloudLibrary
from openlp.plugins.librarysync.lib.preview import text_service_item
from openlp.plugins.librarysync.lib.provider import CloudItem, SyncError
from openlp.plugins.librarysync.lib.transfer import import_item, prepare_upload, read_theme_item, write_upload


@pytest.fixture
def theme(settings):
    ScreenList.create(QtWidgets.QApplication.instance())
    result = Theme()
    result.theme_name = 'Organisation welcome'
    result.background_type = 'solid'
    result.background_color = '#345678'
    result.font_main_name = 'Arial'
    result.font_main_size = 48
    return result


def test_theme_round_trip_preserves_appearance_and_overwrite_is_explicit(theme, settings, tmp_path, qtbot):
    view = ThemeViews()
    qtbot.addWidget(view)
    row = QtWidgets.QListWidgetItem(theme.theme_name, view.list_view)
    row.setData(QtCore.Qt.ItemDataRole.UserRole, theme.theme_name)
    row.setSelected(True)
    manager = SimpleNamespace(theme_path=tmp_path / 'themes', get_theme_data=lambda name: theme,
                              get_theme_names=lambda: [], update_preview_images=MagicMock())
    Registry().register('theme_manager', manager)
    mime = ThemeDragData(manager, view.selectedIndexes())
    [(category, path, contents, title)] = prepare_upload(mime, tmp_path / 'export')
    assert category == 'themes' and title == theme.theme_name
    write_upload(path, contents)
    restored = read_theme_item(path)
    assert restored.background_color == theme.background_color
    assert restored.font_main_name == theme.font_main_name and restored.font_main_size == 48
    item = CloudItem('theme', path.name, category='themes')
    service, metadata = text_service_item(item, restored)
    assert service.get_theme_data() is restored
    assert len(service.slides) == 2 and metadata['Theme'] == theme.theme_name
    import_item(item, path, None, prepared=restored)
    descriptor = manager.theme_path / theme.theme_name / (theme.theme_name + '.json')
    assert descriptor.is_file()
    before = descriptor.read_text()
    with pytest.raises(SyncError, match='Confirm overwrite'):
        import_item(item, path, None, prepared=restored)
    assert descriptor.read_text() == before
    manager.get_theme_names = lambda: [theme.theme_name]
    restored.background_color = '#123456'
    with pytest.raises(SyncError, match='Confirm overwrite'):
        import_item(item, path, None, prepared=restored)
    assert descriptor.read_text() == before
    import_item(item, path, None, prepared=restored, overwrite=theme.theme_name)
    assert json.loads(descriptor.read_text())['background_color'] == '#123456'
    assert not list(descriptor.parent.glob('tmp*'))


@pytest.mark.parametrize('background', ['/etc/passwd', 'https://example.com/file.png', '../outside.png'])
def test_remote_theme_cannot_reference_local_paths_or_arbitrary_urls(theme, background, tmp_path):
    data = json.loads(theme.export_theme())
    data['background_filename'] = background
    path = tmp_path / 'unsafe.otz'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('theme/theme.json', json.dumps(data))
        archive.writestr('../../outside.txt', 'must never be extracted')
    with pytest.raises(SyncError, match='portable background'):
        read_theme_item(path)
    assert not (tmp_path.parent / 'outside.txt').exists()


def test_local_themes_footer_and_cloud_drop_targets(theme, settings, qtbot, monkeypatch):
    manager = ThemeManager()
    qtbot.addWidget(manager)
    manager.setup_ui(manager)
    manager.resize(650, 450)
    manager.show()
    for name in ('First', 'Second'):
        row = QtWidgets.QListWidgetItem(name, manager.theme_list_widget.list_view)
        row.setData(QtCore.Qt.ItemDataRole.UserRole, name)
    assert manager.footer_status_bar.count_label.text() == '2 items'
    assert 'gridView' not in manager.toolbar.actions_map and 'listView' not in manager.toolbar.actions_map
    manager.view_buttons.button(1).click()
    manager.thumbnail_slider.setValue(150)
    assert manager.theme_list_widget.grid_view.iconSize() == QtCore.QSize(264, 150)
    assert settings.value('user interface/theme thumbnail size') == 150
    manager.theme_list_widget.takeItem(0)
    assert manager.footer_status_bar.count_label.text() == '1 item'
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.PluginManager.get_plugin_by_name', lambda name: None)
    panel = CloudLibrary(SimpleNamespace(settings=settings), None)
    qtbot.addWidget(panel)
    panel.install_drop_targets()
    assert manager.theme_list_widget.list_view.viewport() in panel.drop_views
    assert manager.theme_list_widget.grid_view.viewport() in panel.drop_views
    assert CloudDragData(panel, [CloudItem('t', 'Welcome.otz', category='themes')]).can_import(manager)
    assert not CloudDragData(panel, [CloudItem('s', 'Welcome.xml', category='songs')]).can_import(manager)
    panel.shutdown()


def test_cloud_theme_preview_works_without_song_plugin_settings(theme, settings, qtbot, monkeypatch):
    from openlp.plugins.librarysync.lib.preview import CloudSlidePreview
    display = QtWidgets.QWidget()
    display.set_theme = MagicMock()
    display.set_scale = MagicMock()
    display.load_verses = MagicMock()
    display.go_to_slide = MagicMock()
    display.deregister_display = MagicMock()
    monkeypatch.setattr('openlp.core.display.window.DisplayWindow', lambda *args, **kwargs: display)
    warning = MagicMock()
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', warning)
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    window = CloudSlidePreview(parent, CloudItem('theme', 'Organisation.otz', category='themes'), theme)
    service = window.service_item
    service._rendered_slides = [{'text': 'First sample', 'verse': 0}, {'text': 'Second sample', 'verse': 1}]
    service._display_slides = [{'text': 'First sample', 'title': 'First sample', 'verse': 'V1'},
                               {'text': 'Second sample', 'title': 'Second sample', 'verse': 'V2'}]
    window.render()
    warning.assert_not_called()
    assert window.slide_list.rowCount() == 2
    display.set_theme.assert_called_once_with(theme, service_item_type=service.service_item_type)
    window.reject()
