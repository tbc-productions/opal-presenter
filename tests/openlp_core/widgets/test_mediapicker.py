"""Shared picker behaviour using a small library and native Fluent controls."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.widgets.mediapicker import MediaPicker, MediaLibraryPathEdit
from openlp.plugins.images.lib.db import Folder, Item
from openlp.core.app import OpenLP
from openlp.core.lib.designmedia import cache_media, resolve_media, media_label
from openlp.core.widgets.mediapreview import MediaPreview, reveal_media


@pytest.fixture(scope='session')
def native_application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def qapp(native_application):
    # The application's test fixture depends on qtbot; Qt's fixture depends on qapp.
    # Create the native application first to avoid that dependency cycle here.
    return OpenLP()


@pytest.fixture
def library(tmp_path, settings):
    entries = []
    groups = [Folder(id=1, name='Backgrounds')]
    for index, name in enumerate(('Beach', 'Forest')):
        path = tmp_path / f'{name}.png'
        image = QtGui.QImage(160, 90, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtGui.QColor('#315efb' if index else '#df8133'))
        assert image.save(str(path))
        entries.append(Item(id=index + 1, name=path.name, file_path=str(path), folder_id=1 if index else None))
    manager = MagicMock()
    manager.get_all_objects.side_effect = lambda model: groups if model == Folder else entries

    def save(item):
        entries.append(item)
        return True

    manager.save_object.side_effect = save
    media_item = SimpleNamespace(manager=manager, item_class=Item, folder_class=Folder, _insert_saved_items=MagicMock())
    plugin = SimpleNamespace(media_item=media_item, is_active=lambda: True)
    with patch('openlp.core.widgets.mediapicker.PluginManager.get_plugin_by_name',
               side_effect=lambda name: plugin if name == 'images' else None), \
            patch('openlp.core.lib.designmedia.asset_root', return_value=tmp_path / 'managed'):
        yield media_item


def test_picker_filters_and_selection_enable_insert(qtbot, library):
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    assert len(picker.tiles) == 2
    assert not picker.insert_button.isEnabled()
    picker.tiles[0].click()
    assert picker.selected_path.name == 'Beach.png'
    assert picker.insert_button.isEnabled()
    picker.search.setText('Forest')
    assert len(picker.tiles) == 1
    assert picker.selected_path is None
    picker.search.clear()
    picker.folder_combo.setCurrentIndex(1)
    assert len(picker.tiles) == 1
    assert picker.tiles[0].accessibleName() == 'Forest'


def test_picker_adds_managed_file_to_library_and_keeps_original_name(qtbot, library, tmp_path):
    path = tmp_path / 'New image.jpg'
    image = QtGui.QImage(100, 50, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('#238031'))
    assert image.save(str(path))
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    with patch('openlp.core.widgets.mediapicker.FileDialog.getOpenFileNames', return_value=([path], None)):
        picker.add_files()
    added = library.manager.save_object.call_args.args[0]
    assert added.name == 'New image.jpg'
    assert Path(added.file_path).is_file()
    path.unlink()
    assert picker.selected_path == Path(added.file_path)
    assert picker.insert_button.isEnabled()
    library._insert_saved_items.assert_called_once()


def test_theme_path_picker_preserves_path_changed_contract(qtbot, library):
    field = MediaLibraryPathEdit(kind='image', show_revert=False)
    qtbot.addWidget(field)
    path = Path(library.manager.get_all_objects(Item)[0].file_path)
    with patch.object(MediaPicker, 'choose', return_value=path), qtbot.waitSignal(field.pathChanged) as signal:
        field.on_browse_button_clicked()
    assert signal.args == [path]
    assert field.path == path
    assert field.line_edit.isReadOnly()
    assert field.line_edit.text() == path.name


def test_selected_field_keeps_friendly_label_after_library_record_and_source_are_removed(qtbot, library):
    original = Path(library.manager.get_all_objects(Item)[0].file_path)
    retained = resolve_media(cache_media(original))
    library.manager.get_all_objects(Item).clear()
    original.unlink()
    field = MediaLibraryPathEdit(kind='image', show_revert=False)
    qtbot.addWidget(field)
    field.path = retained
    assert field.line_edit.text() == 'Beach.png'
    field.setProperty('path', retained)
    assert field.line_edit.text() == 'Beach.png'
    # Qt field registration must not replace a friendly label with the underlying path.
    field.line_edit.setText(str(retained))
    assert field.line_edit.text() == 'Beach.png'
    assert field.line_edit.toolTip() == 'Beach.png'


def test_insert_retains_independent_media_before_returning_to_designer(qtbot, library):
    original = Path(library.manager.get_all_objects(Item)[0].file_path)
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    picker.select_path(original)
    picker.accept()
    assert picker.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert picker.selected_path != original
    original.unlink()
    assert picker.selected_path.is_file()
    assert media_label(picker.selected_path) == 'Beach.png'


def test_media_tiles_offer_context_actions_for_their_own_original(qtbot, library):
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    with patch('openlp.core.widgets.mediapicker.media_context_menu') as context:
        picker.tiles[1].customContextMenuRequested.emit(QtCore.QPoint(5, 10))
    context.assert_called_once_with(picker.tiles[1], QtCore.QPoint(5, 10),
                                    Path(library.manager.get_all_objects(Item)[1].file_path), 'Forest.png')


def test_large_image_preview_shows_original_metadata_and_friendly_name(qtbot, library):
    path = Path(library.manager.get_all_objects(Item)[0].file_path)
    preview = MediaPreview(None, path, 'Church background')
    qtbot.addWidget(preview)
    preview.show()
    qtbot.wait(20)
    assert preview.windowTitle() == 'Church background'
    assert preview.metadata['Resolution'].text() == '160 × 90'
    assert preview.metadata['File type'].text().startswith('PNG')
    assert preview.metadata['File size'].text() != '—'
    assert preview.viewer.pixmap() is not None


@pytest.mark.parametrize('platform,command,arguments', [
    ('mac', 'open', ['-R']), ('windows', 'explorer', ['/select,'])])
def test_show_in_file_manager_selects_original_file(qtbot, library, platform, command, arguments):
    path = Path(library.manager.get_all_objects(Item)[0].file_path)
    with patch('openlp.core.widgets.mediapreview.is_macosx', return_value=platform == 'mac'), \
            patch('openlp.core.widgets.mediapreview.is_win', return_value=platform == 'windows'), \
            patch('openlp.core.widgets.mediapreview.QtCore.QProcess.startDetached') as start:
        reveal_media(path)
    start.assert_called_once_with(command, arguments + [str(path.resolve())])


def test_thumbnail_grid_wraps_on_resize(qtbot, library):
    entries = library.manager.get_all_objects(Item)
    entries.extend(Item(name=f'Extra {index}', file_path=entries[0].file_path) for index in range(4))
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    picker.resize(1050, 600)
    picker.show()
    qtbot.wait(50)
    picker.reflow()
    wide_row = picker.grid.getItemPosition(picker.grid.indexOf(picker.tiles[4]))[:2]
    picker.resize(600, 600)
    qtbot.wait(50)
    picker.reflow()
    assert picker.grid.getItemPosition(picker.grid.indexOf(picker.tiles[4]))[0] > wide_row[0]
