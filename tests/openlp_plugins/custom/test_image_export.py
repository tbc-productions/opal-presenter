"""Saving custom slides to the Image library respects folder choice and cancellation."""
from unittest.mock import MagicMock, patch

import pytest

from openlp.plugins.custom.lib.mediaitem import CustomMediaItem


@pytest.fixture
def media_item(mock_settings):
    with patch('openlp.core.lib.mediamanageritem.MediaManagerItem._setup'), \
            patch.object(CustomMediaItem, 'setup_item'):
        yield CustomMediaItem(None, MagicMock())


def test_cancel_does_not_render(media_item):
    media_item.list_view = MagicMock()
    media_item.list_view.selectedItems.return_value = [object()]
    with patch('openlp.core.lib.pluginmanager.PluginManager.get_plugin_by_name'), \
            patch('openlp.core.ui.folders.ChooseFolderForm') as chooser, \
            patch('openlp.core.lib.slideimageexport.render_slide_images') as render:
        chooser.return_value.exec.return_value = 0
        media_item.on_save_to_image_library()
    render.assert_not_called()
    chooser.return_value.deleteLater.assert_called_once()


def test_passes_folder_and_cleans_temporary_files(media_item):
    media_item.list_view = MagicMock()
    selected = object()
    media_item.list_view.selectedItems.return_value = [selected]
    service_item = object()
    media_item.build_service_item = MagicMock(return_value=service_item)
    paths = []

    def render(items, directory, progress):
        assert items == [service_item]
        path = directory / 'Welcome.png'
        path.write_bytes(b'image')
        paths.append(path)
        return [(path, 'Welcome.png')]

    with patch('openlp.core.lib.pluginmanager.PluginManager.get_plugin_by_name') as get_plugin, \
            patch('openlp.core.ui.folders.ChooseFolderForm') as chooser, \
            patch('openlp.core.ui.presentationexportdialog.ExportProgressDialog') as progress, \
            patch('openlp.core.lib.slideimageexport.render_slide_images', side_effect=render):
        chooser.return_value.exec.return_value = 1
        folder = chooser.return_value.folder
        media_item.on_save_to_image_library()
        get_plugin.return_value.media_item.add_generated_images.assert_called_once_with(
            [(paths[0], 'Welcome.png')], folder)
        progress.return_value.finish.assert_called_once()
    assert not paths[0].exists()


def test_requires_enabled_images_plugin(media_item):
    media_item.list_view = MagicMock()
    media_item.list_view.selectedItems.return_value = [object()]
    with patch('openlp.core.lib.pluginmanager.PluginManager.get_plugin_by_name', return_value=None), \
            patch('openlp.core.ui.folders.ChooseFolderForm') as chooser, \
            patch('openlp.plugins.custom.lib.mediaitem.QtWidgets.QMessageBox.information') as message:
        media_item.on_save_to_image_library()
    chooser.assert_not_called()
    message.assert_called_once()
