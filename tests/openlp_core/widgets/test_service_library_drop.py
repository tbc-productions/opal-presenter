"""Service drops keep native library data, ownership and overwrite choices intact."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui

from openlp.core.common.applocation import AppLocation
from openlp.core.common.registry import Registry
from openlp.core.db.manager import DBManager
from openlp.core.lib.mediamanageritem import MediaManagerItem
from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem
from openlp.core.ui.library import FolderLibraryItem
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.dnd import ItemDragData
from openlp.core.widgets.docks import MediaToolBox
from openlp.core.widgets.libraryview import LibraryView
from openlp.core.widgets.views import ListWidgetWithDnD, TreeWidgetWithDnD
from openlp.plugins.custom.lib.customxmlhandler import CustomXML
from openlp.plugins.custom.lib.mediaitem import CustomMediaItem
from openlp.plugins.songs.lib.mediaitem import SongMediaItem
from openlp.plugins.songs.lib.openlyricsxml import OpenLyrics
from tests.utils.constants import RESOURCE_PATH


@pytest.fixture
def libraries(settings, tmp_path, qtbot, monkeypatch):
    import importlib
    monkeypatch.setattr(AppLocation, 'get_section_data_path', lambda section: tmp_path / 'data' / section)
    window = QtWidgets.QWidget()
    qtbot.addWidget(window)
    Registry().register('main_window', window)
    result = {}
    for category in ('songs', 'custom', 'media', 'images', 'presentations'):
        (tmp_path / 'data' / category).mkdir(parents=True)
        db = importlib.import_module(f'openlp.plugins.{category}.lib.db')
        manager = DBManager(category, db.init_schema, db_url='sqlite:///' + str(tmp_path / f'{category}.sqlite'))
        plugin = SimpleNamespace(name=category, manager=manager, db_manager=manager)
        with patch.object(MediaManagerItem, '_setup'), patch.object(MediaManagerItem, 'setup_item'), \
                patch.object(SongMediaItem, 'setup_item'), patch.object(CustomMediaItem, 'setup_item'):
            if category == 'songs':
                library = SongMediaItem(window, plugin)
                library.open_lyrics = OpenLyrics(manager)
                library.on_clear_text_button_click = MagicMock()
            elif category == 'custom':
                library = CustomMediaItem(window, plugin)
                library.on_search_text_button_clicked = MagicMock()
            else:
                library = FolderLibraryItem(window, plugin, db.Folder, db.Item)
                library._insert_saved_items = MagicMock()
        library.settings_section = category
        library.on_new_file_masks = ''
        library.record_class = db.Song if category == 'songs' else db.CustomSlide if category == 'custom' else db.Item
        library.list_view = (ListWidgetWithDnD(library, category) if category == 'custom'
                             else TreeWidgetWithDnD(library, category))
        library.list_view.setAcceptDrops(True)
        library.setLayout(QtWidgets.QVBoxLayout())
        library.layout().addWidget(library.list_view)
        result[category] = library
    yield result
    for library in result.values():
        library.plugin.manager.finalise()


def text_item(category, title='Imported item'):
    item = ServiceItem(SimpleNamespace(name=category))
    item.title = title
    item.theme = 'Service theme'
    item.slide_design = {'version': 1, 'lyrics': {'font_size': 48}}
    item.add_from_text('First verse', 'v1')
    item.add_from_text('Second verse', 'v2')
    if category == 'songs':
        item.xml_version = (RESOURCE_PATH / 'songs' / 'openlyrics' / 'Amazing Grace.xml').read_text(encoding='utf-8')
    return item


def file_item(category, path):
    item = ServiceItem(SimpleNamespace(name=category))
    item.title = path.stem
    if category == 'images':
        item.add_from_image(path, path.stem)
    else:
        item.add_from_command(str(path.parent), path.name, QtGui.QIcon())
    return item


@pytest.mark.parametrize('category', ['songs', 'custom'])
def test_text_drop_adds_native_content_and_overwrites_only_when_confirmed(libraries, category):
    library = libraries[category]
    item = text_item(category)
    assert library.import_service_item(item)
    record_type = library.record_class
    original = library.plugin.manager.get_all_objects(record_type)[0]
    record_id = original.id
    before = original.lyrics if category == 'songs' else original.text
    item.theme = 'Replacement theme'
    item.slide_design['lyrics']['font_size'] = 64
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Cancel) as prompt:
        assert not library.import_service_item(item)
        prompt.assert_called_once()
        box = prompt.call_args.args[0]
        assert box.defaultButton() is box.button(QtWidgets.QMessageBox.StandardButton.Cancel)
        assert box.button(QtWidgets.QMessageBox.StandardButton.Yes).text() == 'Overwrite'
        assert box.button(QtWidgets.QMessageBox.StandardButton.No) is None
    assert library.plugin.manager.get_all_objects(record_type)[0].theme_name == 'Service theme'
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert library.import_service_item(item)
    records = library.plugin.manager.get_all_objects(record_type)
    assert len(records) == 1 and records[0].id == record_id
    assert records[0].theme_name == 'Replacement theme'
    if category == 'songs':
        assert records[0].lyrics == before
    if category == 'custom':
        assert [verse[1] for verse in CustomXML(records[0].text).get_verses()] == ['First verse', 'Second verse']
    assert item.edit_id is None


@pytest.mark.parametrize('category,suffix', [('media', '.mp4'), ('images', '.png'), ('presentations', '.pptx')])
def test_file_drop_copies_service_files_and_preserves_original_on_cancel(libraries, tmp_path, category, suffix):
    library = libraries[category]
    service_file = tmp_path / ('Clip' + suffix)
    service_file.write_bytes(b'original data')
    item = file_item(category, service_file)
    assert library.import_service_item(item)
    record = library.manager.get_all_objects(library.item_class)[0]
    record_id = record.id
    stored = Path(record.file_path)
    assert stored != service_file and stored.read_bytes() == b'original data'
    replacement = tmp_path / 'replacement' / service_file.name
    replacement.parent.mkdir()
    replacement.write_bytes(b'replacement data')
    item = file_item(category, replacement)
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Cancel):
        assert not library.import_service_item(item)
    assert record.file_path == str(stored) and stored.read_bytes() == b'original data'
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert library.import_service_item(item)
    records = library.manager.get_all_objects(library.item_class)
    assert len(records) == 1 and records[0].id == record_id
    replacement.unlink()
    service_file.unlink()
    assert Path(records[0].file_path).read_bytes() == b'replacement data'
    assert stored.read_bytes() == b'original data'


@pytest.mark.parametrize('category', ['songs', 'custom', 'media', 'images', 'presentations'])
@pytest.mark.parametrize('grid', [False, True])
def test_service_drag_switches_library_navigation_and_imports_from_any_library_view(
        libraries, tmp_path, qtbot, category, grid):
    box = MediaToolBox()
    qtbot.addWidget(box)
    for name, library in libraries.items():
        if name == 'images' and grid:
            library.library_view = LibraryView(library)
            library.layout().removeWidget(library.list_view)
            library.layout().addWidget(library.library_view)
            library.library_view.grid_button.click()
        box.addItem(library, QtGui.QIcon(), name)
    box.resize(900, 700)
    box.show()
    box.setCurrentIndex(3)
    target = libraries['images'].library_view.grid.viewport() if grid else libraries['images'].list_view.viewport()
    if category in ('songs', 'custom'):
        item = text_item(category)
    else:
        path = tmp_path / ('Item.png' if category == 'images' else 'Item.mp4' if category == 'media' else 'Item.pptx')
        path.write_bytes(b'file')
        item = file_item(category, path)
    mime = ItemDragData(item=item)
    event = QtGui.QDragEnterEvent(QtCore.QPoint(20, 20), QtCore.Qt.DropAction.CopyAction |
                                  QtCore.Qt.DropAction.MoveAction, mime, QtCore.Qt.MouseButton.LeftButton,
                                  QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(target, event)
    assert event.isAccepted() and event.dropAction() == QtCore.Qt.DropAction.CopyAction
    assert box.currentWidget() is libraries[category]
    destination = libraries[category].list_view.viewport()
    drop = QtGui.QDropEvent(QtCore.QPointF(20, 20), QtCore.Qt.DropAction.CopyAction |
                            QtCore.Qt.DropAction.MoveAction, mime, QtCore.Qt.MouseButton.LeftButton,
                            QtCore.Qt.KeyboardModifier.NoModifier)
    with patch.object(libraries[category], 'import_service_item', return_value=True) as imported:
        box.eventFilter(destination, drop)
    imported.assert_called_once_with(item, None)
    assert drop.isAccepted() and drop.dropAction() == QtCore.Qt.DropAction.CopyAction


def test_service_drag_is_handled_on_later_library_children(libraries, qtbot):
    box = MediaToolBox()
    qtbot.addWidget(box)
    box.addItem(libraries['images'], QtGui.QIcon(), 'Images')
    box.addItem(libraries['songs'], QtGui.QIcon(), 'Songs')
    box.show()
    target = QtWidgets.QWidget(libraries['images'])
    target.setAcceptDrops(True)
    target.show()
    mime = ItemDragData(item=text_item('songs'))
    event = QtGui.QDragEnterEvent(QtCore.QPoint(20, 20), QtCore.Qt.DropAction.CopyAction, mime,
                                  QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(target, event)
    assert event.isAccepted()
    assert box.currentWidget() is libraries['songs']


@pytest.mark.parametrize('choice', [QtWidgets.QMessageBox.StandardButton.Cancel,
                                   QtWidgets.QMessageBox.StandardButton.No,
                                   QtWidgets.QMessageBox.StandardButton.Yes])
def test_grouped_image_duplicate_choices(libraries, tmp_path, choice):
    library = libraries['images']
    first = tmp_path / 'First.png'
    second = tmp_path / 'Second.png'
    third = tmp_path / 'Third.png'
    first.write_bytes(b'first')
    second.write_bytes(b'second')
    third.write_bytes(b'third')
    assert library.import_service_item(file_item('images', second))
    original = library.manager.get_all_objects(library.item_class)[0]
    original_path = Path(original.file_path)
    second.write_bytes(b'replacement')
    item = file_item('images', first)
    item.add_from_image(second, second.stem)
    item.add_from_image(third, third.stem)
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=choice) as prompt:
        assert library.import_service_item(item) is (choice != QtWidgets.QMessageBox.StandardButton.Cancel)
    box = prompt.call_args.args[0]
    box._sync_content()
    assert [box._native_commands[slot].text() for slot in ('primary', 'secondary', 'close')] == [
        'Overwrite', 'Skip', 'Cancel']
    assert box.defaultButton() is box.button(QtWidgets.QMessageBox.StandardButton.Cancel)
    records = library.manager.get_all_objects(library.item_class)
    assert len(records) == (1 if choice == QtWidgets.QMessageBox.StandardButton.Cancel else 3)
    updated = next(record for record in records if record.id == original.id)
    assert Path(updated.file_path).read_bytes() == (
        b'replacement' if choice == QtWidgets.QMessageBox.StandardButton.Yes else b'second')
    assert original_path.read_bytes() == b'second'
    assert first.read_bytes() == b'first' and second.read_bytes() == b'replacement' and third.read_bytes() == b'third'


@pytest.mark.parametrize('last_choice', [QtWidgets.QMessageBox.StandardButton.No,
                                        QtWidgets.QMessageBox.StandardButton.Cancel])
def test_skipping_all_duplicates_or_cancelling_after_skip_saves_nothing(libraries, tmp_path, last_choice):
    library = libraries['images']
    first = tmp_path / 'First.png'
    second = tmp_path / 'Second.png'
    for path in (first, second):
        path.write_bytes(b'original')
        assert library.import_service_item(file_item('images', path))
        path.write_bytes(b'replacement')
    item = file_item('images', first)
    item.add_from_image(second, second.stem)
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               side_effect=[QtWidgets.QMessageBox.StandardButton.No, last_choice]), \
            patch.object(library, '_copy_file_to_library_storage') as copy_file:
        assert library.import_service_item(item) is (last_choice == QtWidgets.QMessageBox.StandardButton.No)
    copy_file.assert_not_called()
    records = library.manager.get_all_objects(library.item_class)
    assert len(records) == 2
    assert all(Path(record.file_path).read_bytes() == b'original' for record in records)


@pytest.mark.parametrize('action,expected', [('secondary', None), ('primary', True),
                                           ('enter', False), ('escape', False)])
def test_collection_duplicate_prompt_mouse_and_keyboard(libraries, qtbot, action, expected):
    library = libraries['images']
    parent = library.window()
    parent.resize(420, 240)
    parent.show()
    QtWidgets.fluentqt.initialize_resources()

    def choose():
        box = next(widget for widget in QtWidgets.QApplication.allWidgets()
                   if isinstance(widget, QtWidgets.QMessageBox) and widget.isVisible())
        assert parent.rect().contains(box.geometry())
        positions = []
        for slot in ('primary', 'secondary', 'close'):
            button = box._native_commands[slot]
            positions.append(button.mapTo(box, QtCore.QPoint()).x())
            assert box.rect().contains(QtCore.QRect(button.mapTo(box, QtCore.QPoint()), button.size()))
        assert positions == sorted(positions)
        if action in ('enter', 'escape'):
            qtbot.keyClick(box, QtCore.Qt.Key.Key_Return if action == 'enter' else QtCore.Qt.Key.Key_Escape)
        else:
            qtbot.mouseClick(box._native_commands[action], QtCore.Qt.MouseButton.LeftButton)

    QtCore.QTimer.singleShot(0, choose)
    assert library.confirm_service_item_import('A very long image title ' * 30, [object()], allow_skip=True) is expected


def test_media_stream_drop_uses_stream_descriptor_and_duplicate_prompt(libraries):
    library = libraries['media']
    item = ServiceItem(SimpleNamespace(name='media'))
    item.title = 'Camera'
    item.add_capability(ItemCapabilities.CanStream)
    item.add_from_command('networkstream:Camera&&http://example.com/video&&:network-caching=1000',
                          'Camera', QtGui.QIcon())
    assert library.import_service_item(item)
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Cancel):
        assert not library.import_service_item(item)
    assert len(library.manager.get_all_objects(library.item_class)) == 1


def test_missing_file_does_not_replace_library_record(libraries, tmp_path):
    library = libraries['media']
    source = tmp_path / 'Clip.mp4'
    source.write_bytes(b'original')
    item = file_item('media', source)
    assert library.import_service_item(item)
    stored = library.manager.get_all_objects(library.item_class)[0].file_path
    source.unlink()
    with pytest.raises(FileNotFoundError):
        library.import_service_item(item)
    assert library.manager.get_all_objects(library.item_class)[0].file_path == stored


@pytest.mark.parametrize('original_available', [True, False])
def test_rendered_presentation_import_keeps_source_or_exports_visible_slides(libraries, tmp_path, original_available):
    import pymupdf
    library = libraries['presentations']
    original = tmp_path / 'Slides.pdf'
    original.write_bytes(b'original PDF')
    page = tmp_path / 'page.png'
    image = QtGui.QImage(120, 70, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('#ff8500'))
    assert image.save(str(page))
    item = ServiceItem(SimpleNamespace(name='presentations'))
    item.title = 'Slides'
    item.add_from_image(page, 'Slides')
    item.add_from_image(page, 'Slides')
    item.data_string = {'file_path': original}
    if not original_available:
        original.unlink()

    assert library.import_service_item(item)
    record = library.manager.get_all_objects(library.item_class)[0]
    assert record.name == 'Slides.pdf'
    if original_available:
        assert Path(record.file_path).read_bytes() == b'original PDF'
    else:
        with pymupdf.open(record.file_path) as document:
            assert len(document) == 2
            assert document[0].rect.width == pytest.approx(90, abs=1)
            assert document[0].rect.height == pytest.approx(52.5, abs=1)


def test_song_drop_keeps_audio_and_can_overwrite_from_the_same_managed_file(libraries, tmp_path):
    library = libraries['songs']
    audio = tmp_path / 'backing.mp3'
    audio.write_bytes(b'backing track')
    item = text_item('songs')
    item.background_audio = [(audio, 'hash')]
    assert library.import_service_item(item)
    song = library.plugin.manager.get_all_objects(library.record_class)[0]
    stored = song.media_files[0].file_path
    assert stored != audio and stored.read_bytes() == b'backing track'
    item.background_audio = [(stored, 'hash')]
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert library.import_service_item(item)
        item.background_audio = []
        assert library.import_service_item(item)
    assert not song.media_files


def test_file_drop_into_folder_and_replacement_keep_the_folder(libraries, tmp_path):
    library = libraries['images']
    folder = library.folder_class(name='Backgrounds')
    library.manager.save_object(folder)
    row = QtWidgets.QTreeWidgetItem(['Backgrounds'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, folder)
    library.list_view.addTopLevelItem(row)
    source = tmp_path / 'Background.png'
    source.write_bytes(b'image')
    item = file_item('images', source)
    assert library.import_service_item(item, row)
    record = library.manager.get_all_objects(library.item_class)[0]
    assert record.folder_id == folder.id
    child = QtWidgets.QTreeWidgetItem(row, ['Background.png'])
    child.setData(0, QtCore.Qt.ItemDataRole.UserRole, record)
    assert folder.id == record.id
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert library.import_service_item(item)
    assert record.folder_id == folder.id
    assert library.list_view.topLevelItem(0) is row and row.childCount() == 0


def test_unsafe_song_xml_does_not_replace_existing_song(libraries):
    library = libraries['songs']
    item = text_item('songs')
    assert library.import_service_item(item)
    song = library.plugin.manager.get_all_objects(library.record_class)[0]
    original_lyrics = song.lyrics
    item.xml_version = '<!DOCTYPE song [<!ENTITY secret SYSTEM "file:///etc/passwd">]><song>&secret;</song>'
    with pytest.raises(ValueError, match='unsafe XML'):
        library.import_service_item(item)
    assert song.lyrics == original_lyrics


@pytest.mark.parametrize('name,valid', [('bibles', True), ('songs', False)])
def test_unsupported_or_invalid_service_drag_does_not_switch_library(libraries, qtbot, name, valid):
    box = MediaToolBox()
    qtbot.addWidget(box)
    box.addItem(libraries['songs'], QtGui.QIcon(), 'Songs')
    box.addItem(libraries['images'], QtGui.QIcon(), 'Images')
    box.setCurrentIndex(1)
    item = text_item(name)
    item.is_valid = valid
    mime = ItemDragData(item=item)
    event = QtGui.QDragEnterEvent(QtCore.QPoint(), QtCore.Qt.DropAction.CopyAction, mime,
                                  QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    assert box.eventFilter(box, event)
    assert not event.isAccepted() and box.currentWidget() is libraries['images']


def test_native_drop_imports_custom_slides_and_cancel_keeps_service_and_library(libraries, qtbot):
    box = MediaToolBox()
    qtbot.addWidget(box)
    box.addItem(libraries['images'], QtGui.QIcon(), 'Images')
    box.addItem(libraries['custom'], QtGui.QIcon(), 'Custom Slides')
    box.resize(900, 700)
    box.show()
    item = text_item('custom')
    identity = item.unique_identifier
    slides = repr(item.slides)
    mime = ItemDragData(item=item)

    def drop():
        enter = QtGui.QDragEnterEvent(QtCore.QPoint(20, 20), QtCore.Qt.DropAction.CopyAction, mime,
                                      QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(box, enter)
        event = QtGui.QDropEvent(QtCore.QPointF(20, 20), QtCore.Qt.DropAction.CopyAction, mime,
                                 QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(box, event)
        return event.isAccepted()

    assert drop()
    assert box.currentWidget() is libraries['custom']
    item.theme = 'Changed theme'
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Cancel):
        assert not drop()
    records = libraries['custom'].plugin.manager.get_all_objects(libraries['custom'].record_class)
    assert len(records) == 1 and records[0].theme_name == 'Service theme'
    assert item.unique_identifier == identity and repr(item.slides) == slides


@pytest.mark.parametrize('choice', [QtWidgets.QMessageBox.StandardButton.Yes,
                                   QtWidgets.QMessageBox.StandardButton.No,
                                   QtWidgets.QMessageBox.StandardButton.Cancel])
def test_conflicting_names_in_one_image_item_prompt_before_any_files_are_saved(libraries, tmp_path, choice):
    library = libraries['images']
    first = tmp_path / 'first.png'
    second = tmp_path / 'second.png'
    first.write_bytes(b'first')
    second.write_bytes(b'second')
    item = ServiceItem(SimpleNamespace(name='images'))
    item.title = 'Images'
    item.add_from_image(first, 'Same name')
    item.add_from_image(second, 'Same name')
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True, return_value=choice):
        assert library.import_service_item(item) is (choice != QtWidgets.QMessageBox.StandardButton.Cancel)
    records = library.manager.get_all_objects(library.item_class)
    assert len(records) == int(choice != QtWidgets.QMessageBox.StandardButton.Cancel)
    if records:
        assert Path(records[0].file_path).read_bytes() == (
            b'second' if choice == QtWidgets.QMessageBox.StandardButton.Yes else b'first')


def test_failed_file_save_keeps_existing_record_and_removes_uncommitted_copy(libraries, tmp_path, monkeypatch):
    from sqlalchemy.exc import InvalidRequestError
    library = libraries['images']
    source = tmp_path / 'Image.png'
    source.write_bytes(b'original')
    item = file_item('images', source)
    assert library.import_service_item(item)
    record = library.manager.get_all_objects(library.item_class)[0]
    stored = record.file_path
    source.write_bytes(b'replacement')
    monkeypatch.setattr(library.manager.session, 'commit', MagicMock(side_effect=InvalidRequestError('Save failed')))
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Yes), pytest.raises(RuntimeError, match='saved'):
        library.import_service_item(item)
    assert record.file_path == stored and Path(stored).read_bytes() == b'original'
    assert list(Path(stored).parent.iterdir()) == [Path(stored)]


def test_legacy_file_title_with_extension_finds_existing_library_item(libraries, tmp_path):
    library = libraries['media']
    source = tmp_path / 'Clip.mp4'
    source.write_bytes(b'video')
    item = file_item('media', source)
    assert library.import_service_item(item)
    item.title = 'Clip.mp4'
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Cancel) as prompt:
        assert not library.import_service_item(item)
        prompt.assert_called_once()
    assert len(library.manager.get_all_objects(library.item_class)) == 1


def test_failed_song_overwrite_does_not_continue_saving_service_metadata(libraries, monkeypatch):
    from sqlalchemy.exc import InvalidRequestError
    library = libraries['songs']
    item = text_item('songs')
    assert library.import_service_item(item)
    song = library.plugin.manager.get_all_objects(library.record_class)[0]
    item.theme = 'Replacement theme'
    commit = library.plugin.manager.session.commit
    failed = MagicMock(side_effect=[InvalidRequestError('Save failed'), commit])
    monkeypatch.setattr(library.plugin.manager.session, 'commit', failed)
    with patch('openlp.core.lib.mediamanageritem.QtWidgets.QMessageBox.exec', autospec=True,
               return_value=QtWidgets.QMessageBox.StandardButton.Yes), pytest.raises(RuntimeError, match='saved'):
        library.import_service_item(item)
    assert failed.call_count == 1 and song.theme_name == 'Service theme'


@pytest.mark.parametrize('cancel_second', [False, True])
def test_service_batch_drop_routes_mixed_plugins_and_stops_on_cancel(libraries, qtbot, cancel_second):
    box = MediaToolBox()
    qtbot.addWidget(box)
    for name in ('songs', 'custom'):
        box.addItem(libraries[name], QtGui.QIcon(), name)
    box.show()
    items = [text_item('songs'), text_item('custom'), text_item('songs')]
    mime = ItemDragData(items=items)
    target = libraries['songs'].list_view.viewport()
    event = QtGui.QDropEvent(QtCore.QPointF(20, 20), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    with patch.object(libraries['songs'], 'import_service_item', return_value=True) as songs, \
            patch.object(libraries['custom'], 'import_service_item', return_value=not cancel_second) as custom:
        box.eventFilter(target, event)
    assert songs.call_count == (1 if cancel_second else 2)
    custom.assert_called_once_with(items[1], None)
    assert event.isAccepted() == (not cancel_second)


def test_service_batch_with_unsupported_item_does_not_import_partially(libraries, qtbot):
    box = MediaToolBox()
    qtbot.addWidget(box)
    box.addItem(libraries['songs'], QtGui.QIcon(), 'Songs')
    mime = ItemDragData(items=[text_item('songs'), text_item('custom')])
    event = QtGui.QDropEvent(QtCore.QPointF(20, 20), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    with patch.object(libraries['songs'], 'import_service_item') as imported:
        box.eventFilter(libraries['songs'].list_view.viewport(), event)
    imported.assert_not_called()
    assert not event.isAccepted()
