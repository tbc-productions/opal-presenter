"""Shared picker behaviour using a small library and native Fluent controls."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from fluentqt import GridView, TreeView

from openlp.core.widgets.mediapicker import MediaPicker, MediaLibraryPathEdit
from openlp.plugins.images.lib.db import Folder, Item
from openlp.core.app import OpenLP
from openlp.core.lib.designmedia import cache_media, resolve_media, media_label
from openlp.core.widgets.mediapreview import MediaPreview, reveal_media
from openlp.core.widgets.libraryview import LibraryView, LIBRARY_THUMBNAIL_ROLE
from openlp.core.widgets.views import TreeWidgetWithDnD


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
    assert picker.browser.count_label.text() == '2 items'
    assert not picker.insert_button.isEnabled()
    picker.select_path(Path(library.manager.get_all_objects(Item)[0].file_path))
    assert picker.selected_path.name == 'Beach.png'
    assert picker.insert_button.isEnabled()
    picker.search.setText('Forest')
    assert picker.browser.count_label.text() == '1 item'
    assert picker.selected_path is None
    picker.search.clear()
    picker.folder_combo.setCurrentIndex(1)
    assert picker.browser.count_label.text() == '1 item'
    assert picker.list_view.topLevelItem(0).text(0) == 'Forest'


@pytest.mark.parametrize('name', ['images', 'media', 'presentations'])
def test_picker_shares_view_and_thumbnail_preferences_with_library(qtbot, library, settings, name):
    host = QtWidgets.QWidget()
    qtbot.addWidget(host)
    host.plugin = SimpleNamespace(name=name)
    host.settings = settings
    host.item_class, host.folder_class = Item, Folder
    host.context_menu = MagicMock()
    host.on_double_clicked = MagicMock()
    host.list_view = TreeWidgetWithDnD(host, name)
    view = LibraryView(host)
    qtbot.addWidget(view)
    view.set_view(1)
    view.thumbnail_slider.setValue(150)
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    assert picker.browser.preferences is view.preferences
    assert isinstance(picker.browser.grid, GridView)
    assert isinstance(picker.list_view, TreeView)
    assert picker.browser.grid_button.isChecked()
    assert picker.browser.thumbnail_slider.value() == 150
    picker.browser.list_button.click()
    picker.browser.thumbnail_slider.setValue(75)
    assert view.list_button.isChecked()
    assert view.thumbnail_slider.value() == 75
    assert view.tree.iconSize() == picker.list_view.iconSize()
    assert settings.value('advanced/library thumbnail size') == 75


def test_picker_grid_navigation_selection_search_and_thumbnail_update(qtbot, library, tmp_path):
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    picker.show()
    picker.browser.grid_button.click()
    picker.browser.activate_tile(picker.browser.grid.item(0))
    assert [crumb.text for crumb in picker.browser.breadcrumbs.items()] == ['Library', 'Backgrounds']
    grid = picker.browser.grid
    qtbot.wait(20)
    qtbot.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=grid.visualItemRect(grid.item(0)).center())
    assert picker.selected_path.name == 'Forest.png'
    assert picker.insert_button.isEnabled()
    thumbnail = tmp_path / 'updated.png'
    image = QtGui.QImage(160, 90, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('green'))
    image.save(str(thumbnail))
    library.generate_thumbnail_path = lambda item: thumbnail
    picker.thumbnail_ready(picker.selected_path)
    assert picker.list_view.currentItem().icon(0).pixmap(10, 10).toImage().pixelColor(4, 2).name() == '#008000'
    assert picker.list_view.currentItem().data(0, LIBRARY_THUMBNAIL_ROLE) == picker.selected_path
    picker.search.setText('Beach')
    assert picker.browser.count_label.text() == '1 item'
    assert grid.count() == 1
    assert picker.browser.folder_item() is None
    assert picker.selected_path is None
    assert not picker.insert_button.isEnabled()


def test_picker_keeps_image_and_video_folders_separate(qtbot, library, tmp_path):
    from openlp.plugins.media.lib.db import Folder as MediaFolder, Item as MediaItem
    folder = MediaFolder(id=1, name='Videos')
    path = tmp_path / 'Loop.mp4'
    path.write_bytes(b'video')
    item = MediaItem(id=1, name=path.name, file_path=str(path), folder_id=1)
    manager = MagicMock()
    manager.get_all_objects.side_effect = lambda model: [folder] if model == MediaFolder else [item]
    video_library = SimpleNamespace(manager=manager, item_class=MediaItem, folder_class=MediaFolder)
    with patch('openlp.core.widgets.mediapicker.PluginManager.get_plugin_by_name',
               side_effect=lambda name: SimpleNamespace(media_item=library if name == 'images' else video_library,
                                                        is_active=lambda: True)):
        picker = MediaPicker()
    qtbot.addWidget(picker)
    assert picker.browser.count_label.text() == '3 items'
    assert picker.list_view.topLevelItem(0).child(0).text(0) == 'Forest'
    assert picker.list_view.topLevelItem(1).child(0).text(0) == 'Loop'
    picker.select_path(path)
    assert picker.selected_path == path
    thumbnail = tmp_path / 'Loop.png'
    image = QtGui.QImage(160, 90, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('green'))
    image.save(str(thumbnail))
    video_library.generate_thumbnail_path = lambda item: thumbnail
    picker.thumbnail_ready(path)
    picker.browser.grid_button.click()
    assert picker.browser.grid.count() == 1
    assert picker.browser.grid.item(0).icon().pixmap(10, 10).toImage().pixelColor(4, 2).name() == '#008000'
    picker.kind_combo.setCurrentIndex(1)
    assert picker.selected_path is None
    assert picker.browser.count_label.text() == '2 items'


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


@pytest.mark.parametrize('mode', [0, 1])
def test_picker_adds_files_to_the_browsed_folder(qtbot, library, tmp_path, mode):
    path = tmp_path / 'New image.png'
    image = QtGui.QImage(100, 50, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('green'))
    image.save(str(path))
    picker = MediaPicker(kinds=('image',))
    qtbot.addWidget(picker)
    picker.browser.set_view(mode)
    if mode:
        picker.browser.activate_tile(picker.browser.grid.item(0))
    else:
        picker.list_view.setCurrentItem(picker.list_view.topLevelItem(0))
    with patch('openlp.core.widgets.mediapicker.FileDialog.getOpenFileNames', return_value=([path], None)):
        picker.add_files()
    added = library.manager.save_object.call_args.args[0]
    assert added.folder_id == 1
    assert picker.selected_path == Path(added.file_path)
    assert picker.insert_button.isEnabled()


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
    picker.show()
    picker.browser.grid_button.click()
    picker.browser.activate_tile(picker.browser.grid.item(0))
    grid = picker.browser.grid
    position = grid.visualItemRect(grid.item(0)).center()
    with patch('openlp.core.widgets.mediapicker.media_context_menu') as context:
        grid.customContextMenuRequested.emit(position)
    context.assert_called_once_with(grid.viewport(), position,
                                    Path(library.manager.get_all_objects(Item)[1].file_path), 'Forest.png')


def test_large_image_preview_shows_original_metadata_and_friendly_name(qtbot, library):
    path = Path(library.manager.get_all_objects(Item)[0].file_path)
    preview = MediaPreview(None, path, 'Church background')
    qtbot.addWidget(preview)
    preview.show()
    qtbot.wait(20)
    assert preview.windowTitle() == 'Church background'
    assert [label.text() for label in preview.findChildren(QtWidgets.QLabel)
            if label.text() == 'Church background'] == ['Church background']
    assert preview.metadata['Resolution'].text() == '160 × 90'
    assert preview.metadata['File type'].text().startswith('PNG')
    assert preview.metadata['File size'].text() != '—'
    assert preview.viewer.pixmap() is not None
    qtbot.keyClick(preview, QtCore.Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not preview.isVisible())
    assert preview.result() == QtWidgets.QDialog.DialogCode.Rejected
    preview.show()
    close = next(button for button in preview.findChildren(QtWidgets.QPushButton) if button.text() == 'Close')
    qtbot.mouseClick(close, QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not preview.isVisible())
    assert preview.result() == QtWidgets.QDialog.DialogCode.Accepted


def test_presentation_inspector_browses_slides_and_uses_source_metadata(qtbot, library, tmp_path):
    source = tmp_path / 'Sunday.pptx'
    source.write_bytes(b'presentation file')
    images = [Path(item.file_path) for item in library.manager.get_all_objects(Item)]
    preview = MediaPreview(None, source, 'Sunday service', kind='presentation', preview_paths=images)
    qtbot.addWidget(preview)
    preview.show()
    assert preview.metadata['Slides'].text() == '2'
    assert preview.metadata['File type'].text().startswith('PPTX')
    assert preview.metadata['File size'].text() == '17 B'
    assert preview.page_label.text() == 'Slide 1 of 2'
    assert not preview.previous_button.isEnabled()
    preview.next_button.click()
    assert preview.page_label.text() == 'Slide 2 of 2'
    assert not preview.next_button.isEnabled()
    preview.previous_button.click()
    assert preview.page == 0


def test_audio_inspector_has_playback_controls_and_releases_player(settings, qtbot, tmp_path):
    import wave
    path = tmp_path / 'Music.wav'
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\x00\x00' * 8000)
    preview = MediaPreview(None, path, kind='media')
    qtbot.addWidget(preview)
    assert 'Audio codec' in preview.metadata
    assert 'Resolution' not in preview.metadata
    assert not preview.audio.isMuted()
    assert preview.position_slider is not None
    preview.stop_video()
    assert preview.player.source().isEmpty()


def test_inspector_missing_original_reports_error(settings, qtbot, tmp_path):
    with patch('openlp.core.widgets.mediapreview.QtWidgets.QMessageBox.warning') as warning:
        MediaPreview.show_media(None, tmp_path / 'missing.png')
    warning.assert_called_once()


def test_pdf_inspector_renders_pages_without_library_thumbnails(settings, qtbot, tmp_path):
    path = tmp_path / 'Slides.pdf'
    writer = QtGui.QPdfWriter(str(path))
    painter = QtGui.QPainter(writer)
    painter.drawText(100, 100, 'First page')
    writer.newPage()
    painter.drawText(100, 100, 'Second page')
    painter.end()
    preview = MediaPreview(None, path, kind='presentation')
    qtbot.addWidget(preview)
    assert preview.metadata['Slides'].text() == '2'
    assert not preview.image.isNull()
    preview.next_button.click()
    assert preview.page_label.text() == 'Slide 2 of 2'


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
    picker.browser.grid_button.click()
    qtbot.wait(20)
    wide_row = picker.browser.grid.visualItemRect(picker.browser.grid.item(3)).top()
    picker.resize(600, 600)
    qtbot.wait(50)
    assert picker.browser.grid.visualItemRect(picker.browser.grid.item(3)).top() > wide_row
