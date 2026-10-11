# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.platform import is_win
from openlp.core.ui.library import FolderLibraryItem


class MockItem:
    id = 1
    name = 'video.mp4'
    file_path = 'path/to/video.mp4'
    folder_id = None

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockFolder:
    id = 1
    name = 'folder'
    parent_id = None

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockTreeParent:
    def removeChild(self, child):
        self.child = child

    def data(self, column, role):
        return None


class MockTreeItem:
    def __init__(self, item, parent=None):
        self._item = item
        self._parent = parent

    def data(self, column, role):
        return self._item

    def text(self):
        return ''

    def parent(self):
        return self._parent


@pytest.fixture
def folder_library_item(registry, settings):
    registry.register('main_window', MagicMock())
    mocked_manager = MagicMock()
    with patch('openlp.core.lib.mediamanageritem.MediaManagerItem._setup'), \
            patch('openlp.core.lib.mediamanageritem.MediaManagerItem.setup_item'):
        library_item = FolderLibraryItem(None, MagicMock(manager=mocked_manager), MockFolder, MockItem)
        library_item.list_view = MagicMock(**{'selectedItems.return_value': []})
    return library_item


def test_folderlibrary_retranslate_ui(folder_library_item):
    """Test the retranslate_ui() method"""
    # GIVEN: A FolderLibraryItem object with mocks
    folder_library_item.add_folder_action = MagicMock()

    # WHEN: retranslate_ui() is called
    folder_library_item.retranslate_ui()

    # THEN: there should be no errors and the text should be correct
    folder_library_item.add_folder_action.setText.assert_called_once_with('Add folder')
    folder_library_item.add_folder_action.setToolTip.assert_called_once_with('Add folder')


def test_folderlibrary_add_custom_context_actions(folder_library_item):
    """Test that add_custom_context_actions adds show-in-folder action."""
    with patch('openlp.core.ui.library.create_widget_action') as mocked_create_widget_action, \
            patch('openlp.core.ui.library._add_library_context_menu_separator') as mocked_separator:
        folder_library_item.add_custom_context_actions()
    assert mocked_create_widget_action.call_count == 1
    mocked_separator.assert_called_once_with(folder_library_item.list_view)


@pytest.mark.parametrize('plugin', ['images', 'media', 'presentations'])
def test_file_libraries_offer_inspect_for_one_file(folder_library_item, plugin):
    folder_library_item.plugin.name = plugin
    with patch('openlp.core.ui.library.create_widget_action') as create_action:
        folder_library_item.add_custom_context_actions()
    assert any(call.kwargs.get('text') == 'Inspect' for call in create_action.call_args_list)
    folder_library_item.list_view.selectedItems.return_value = [MockTreeItem(MockItem())]
    with patch.object(folder_library_item, 'inspect_item') as inspect:
        folder_library_item.on_inspect_click()
    assert inspect.call_args.args[0].file_path == MockItem.file_path


@pytest.mark.parametrize('items', [[], [MockFolder()], [MockItem(), MockItem()],
                                   [MockItem(file_path='networkstream:Camera')],
                                   [MockItem(file_path='devicestream:Camera')]])
def test_inspect_ignores_folders_multiple_selection_and_streams(folder_library_item, items):
    folder_library_item.list_view.selectedItems.return_value = [MockTreeItem(item) for item in items]
    with patch.object(folder_library_item, 'inspect_item') as inspect:
        folder_library_item.on_inspect_click()
    inspect.assert_not_called()


def test_real_file_library_wraps_tree_with_footer_and_grid(settings, registry, qtbot, tmp_path):
    registry.register('service_manager', MagicMock())
    registry.register('main_window', MagicMock())
    plugin = MagicMock()
    plugin.name = 'images'
    plugin.icon = QtGui.QIcon()
    plugin.get_string.return_value = {'title': 'Images', 'tooltip': 'Images'}
    library = FolderLibraryItem(None, plugin, MockFolder, MockItem)
    qtbot.addWidget(library)
    library.show()
    item = QtWidgets.QTreeWidgetItem(['Background'])
    path = tmp_path / 'Background.png'
    item.setData(0, QtCore.Qt.ItemDataRole.UserRole, MockItem(file_path=str(path)))
    library.list_view.addTopLevelItem(item)
    qtbot.waitUntil(lambda: library.library_view.count_label.text() == '1 item')
    library.library_view.grid_button.click()
    assert library.library_view.grid.count() == 1
    library.library_view.grid.setCurrentRow(0)
    assert library.inspect_action.isEnabled()
    with patch('openlp.core.ui.library.MediaPreview.show_media') as preview:
        library.inspect_action.trigger()
    preview.assert_called_once_with(library, path, 'video.mp4', kind='image')
    with patch.object(library.menu, 'exec') as menu:
        point = library.library_view.grid.visualItemRect(library.library_view.grid.item(0)).center()
        library.context_menu(point)
    menu.assert_called_once()
    library.list_view.activateDnD()
    assert library.list_view.parent() is library.library_view
    folder = QtWidgets.QTreeWidgetItem(['Backgrounds'])
    folder.setData(0, QtCore.Qt.ItemDataRole.UserRole, MockFolder(name='Backgrounds'))
    library.list_view.addTopLevelItem(folder)
    library.library_view.refresh()
    library.library_view.activate_tile(library.library_view.grid.item(1))
    assert not library.list_view.selectedItems()
    assert library.current_folder.name == 'Backgrounds'


@patch('openlp.core.ui.library.is_win', return_value=True)
@patch('openlp.core.ui.library.QtCore.QProcess.startDetached')
def test_on_show_in_folder_click_windows(mocked_start_detached, mocked_is_win, folder_library_item, tmp_path):
    """Test that show in folder reveals selected file on Windows."""
    file_path = tmp_path / 'video.mp4'
    file_path.write_bytes(b'media')
    selected_tree_item = MagicMock()
    selected_tree_item.data.return_value = MockItem(file_path=str(file_path))
    folder_library_item.list_view.selectedItems.return_value = [selected_tree_item]

    folder_library_item.on_show_in_folder_click()

    mocked_start_detached.assert_called_once()


def test_folderlibrary_load_item(folder_library_item):
    """Test that the load_item() method raises a NotImplementedError"""
    with pytest.raises(NotImplementedError):
        folder_library_item.load_item(MockItem())


def test_folderlibrary_delete_item(folder_library_item):
    """Test that the delete_item() method raises a NotImplementedError"""
    with pytest.raises(NotImplementedError):
        folder_library_item.delete_item(MockItem())


def test_folderlibrary_add_middle_header_bar(folder_library_item):
    """Test that an action is created for the header bar"""
    # GIVEN: A mocked action and toolbar
    mocked_action = MagicMock()
    folder_library_item.toolbar = MagicMock(**{'add_toolbar_action.return_value': mocked_action})

    # WHEN: add_middle_header_bar() is called
    folder_library_item.add_middle_header_bar()

    # THEN: The action should have been created
    assert folder_library_item.add_folder_action is mocked_action


def test_folderlibrary_create_item_from_id_path(folder_library_item):
    """Test the create_item_from_id method"""
    # GIVEN: An instance of the FolderLibraryItem
    mocked_item = MockItem()
    folder_library_item.manager.get_object_filtered.return_value = mocked_item

    # WHEN: create_item_from_id is called
    result = folder_library_item.create_item_from_id('path/to/video.mp4')

    # THEN: The result should be a QTreeWidgetItem with a mocked object as data
    assert isinstance(result, QtWidgets.QTreeWidgetItem)
    assert result.data(0, QtCore.Qt.ItemDataRole.UserRole) is mocked_item


def test_folderlibrary_create_item_from_id_object(folder_library_item):
    """Test the create_item_from_id method"""
    # GIVEN: An instance of the FolderLibraryItem
    mocked_item = MockItem()
    folder_library_item.manager.get_object_filtered.return_value = mocked_item

    # WHEN: create_item_from_id is called
    result = folder_library_item.create_item_from_id(mocked_item)

    # THEN: The result should be a QTreeWidgetItem with a mocked object as data
    assert isinstance(result, QtWidgets.QTreeWidgetItem)
    assert result.data(0, QtCore.Qt.ItemDataRole.UserRole) is mocked_item


def test_folderlibrary_current_folder(folder_library_item):
    """Test that the current_folder property returns the correct folder"""
    # GIVEN: A whole buncha mocks
    mocked_folder = MockFolder()
    mocked_item = MockItem()
    mocked_list_folder = MagicMock(**{'data.return_value': mocked_folder}, spec=QtWidgets.QTreeWidgetItem)
    mocked_list_item = MagicMock(**{'data.return_value': mocked_item, 'parent.return_value': mocked_list_folder})
    folder_library_item.list_view.selectedItems.return_value = [mocked_list_item]

    # WHEN: We access the property
    folder = folder_library_item.current_folder

    # THEN: The current folder should be the mocked folder
    assert folder is mocked_folder


def test_file_to_item_as_path(folder_library_item):
    """Test the file_to_item() method returns an Item from the filename as a Path"""
    # GIVEN: A FolderLibraryItem
    folder_library_item.manager.save_object = MagicMock()

    # WHEN: A Path object is passed to file_to_item()
    result = folder_library_item.file_to_item(Path('path/to/file.mp4'))

    # THEN: An Item should be returned
    assert isinstance(result, MockItem)
    assert result.name == 'file.mp4'
    if is_win():
        assert result.file_path == 'path\\to\\file.mp4'
    else:
        assert result.file_path == 'path/to/file.mp4'


def test_file_to_item_as_str(folder_library_item):
    """Test the file_to_item() method returns an Item from the filename as a str"""
    # GIVEN: A FolderLibraryItem
    folder_library_item.manager.save_object = MagicMock()

    # WHEN: A Path object is passed to file_to_item()
    result = folder_library_item.file_to_item('path/to/file.mp4')

    # THEN: An Item should be returned
    assert isinstance(result, MockItem)
    assert result.name == 'file.mp4'
    assert result.file_path == 'path/to/file.mp4'


def test_validate_and_load(folder_library_item):
    """Adding files updates only the new entries rather than reloading the library."""
    file_list = ['path1/image1.jpg', 'path2/image2.jpg']
    folder_library_item.manager.get_all_objects.return_value = [MockItem(file_path='existing.jpg')]
    folder_library_item._insert_saved_items = MagicMock()
    folder_library_item.load_list = MagicMock()
    folder_library_item.settings_section = 'tests'
    folder_library_item.choose_folder_form = MagicMock(**{'exec.return_value': QtWidgets.QDialog.Accepted,
                                                          'folder': None, 'is_new_folder': False})

    folder_library_item.validate_and_load(file_list)

    folder_library_item.load_list.assert_not_called()
    folder_library_item.manager.get_all_objects.assert_called_once()
    added, folder = folder_library_item._insert_saved_items.call_args.args
    assert folder is None
    assert [item.file_path for item in added] == file_list


def test_add_one_image_keeps_existing_tree_rows(folder_library_item, tmp_path):
    """Importing into a folder retains its expanded state, selection and existing thumbnail rows."""
    image = tmp_path / 'new.jpg'
    image.write_bytes(b'image')
    folder_library_item.settings.value = MagicMock(return_value=False)
    folder_library_item.list_view = QtWidgets.QTreeWidget()
    folder_library_item.list_view.setSortingEnabled(True)
    folder = MockFolder(id=7, name='Images')
    folder_row = QtWidgets.QTreeWidgetItem(['Images (1)'])
    folder_row.setData(0, QtCore.Qt.ItemDataRole.UserRole, folder)
    existing = QtWidgets.QTreeWidgetItem(['old.jpg'])
    folder_row.addChild(existing)
    folder_library_item.list_view.addTopLevelItem(folder_row)
    folder_row.setExpanded(True)
    existing.setSelected(True)
    folder_library_item.manager.get_all_objects.return_value = []
    folder_library_item.manager.save_object.return_value = True
    folder_library_item.load_item = MagicMock(side_effect=lambda item: QtWidgets.QTreeWidgetItem([item.name]))
    folder_library_item.load_list = MagicMock()
    folder_library_item.settings_section = 'tests'

    folder_library_item.validate_and_load([image], target_folder=folder_row)

    folder_library_item.load_list.assert_not_called()
    folder_library_item.load_item.assert_called_once()
    assert folder_row.childCount() == 2
    assert any(folder_row.child(i) is existing for i in range(2))
    assert existing.isSelected()
    assert folder_row.isExpanded()
    assert folder_row.text(0) == 'Images (2)'


def test_adding_image_to_new_folder_keeps_existing_rows(folder_library_item, tmp_path):
    image = tmp_path / 'new.jpg'
    image.write_bytes(b'image')
    folder_library_item.settings.value = MagicMock(return_value=False)
    folder_library_item._get_proportional_folder_icon = MagicMock(
        return_value=QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon))
    folder_library_item.list_view = QtWidgets.QTreeWidget()
    old_folder = QtWidgets.QTreeWidgetItem(['Old folder'])
    folder_library_item.list_view.addTopLevelItem(old_folder)
    folder = MockFolder(id=8, name='New folder', parent_id=None)
    folder.items = []
    folder.folders = []
    folder_library_item.choose_folder_form = MagicMock(**{
        'exec.return_value': QtWidgets.QDialog.DialogCode.Accepted,
        'folder': folder,
        'is_new_folder': True
    })
    folder_library_item.manager.get_all_objects.return_value = []
    folder_library_item.manager.save_object.return_value = True
    folder_library_item.load_item = MagicMock(side_effect=lambda item: QtWidgets.QTreeWidgetItem([item.name]))
    folder_library_item.load_list = MagicMock()
    folder_library_item.settings_section = 'tests'

    folder_library_item.validate_and_load([image])

    folder_library_item.load_list.assert_not_called()
    assert folder_library_item.list_view.topLevelItemCount() == 2
    assert any(folder_library_item.list_view.topLevelItem(i) is old_folder for i in range(2))
    new_folder_row = folder_library_item._find_folder_tree_item(8)
    assert new_folder_row is not None
    assert new_folder_row.text(0) == 'New folder (1)'
    assert new_folder_row.childCount() == 1


@patch('openlp.core.ui.library.copy2')
@patch('openlp.core.ui.library.create_paths')
@patch('openlp.core.ui.library.AppLocation.get_section_data_path')
def test_prepare_library_file_copies_to_data_folder(mocked_get_section_data_path, mocked_create_paths,
                                                    mocked_copy2, folder_library_item, tmp_path):
    """
    Test that library files are copied to managed storage when enabled.
    """
    source_file = tmp_path / 'clip.mp4'
    source_file.write_bytes(b'media')
    managed_root = tmp_path / 'managed'
    mocked_get_section_data_path.return_value = managed_root
    folder_library_item.settings_section = 'tests'
    folder_library_item.settings.value = MagicMock(side_effect=lambda key: {
        'advanced/copy library files to data folder': True
    }.get(key, False))

    result = folder_library_item._prepare_library_file(source_file)

    expected_destination = managed_root / 'library' / 'clip.mp4'
    assert result == expected_destination
    mocked_create_paths.assert_called_once_with(managed_root / 'library')
    mocked_copy2.assert_called_once_with(source_file, expected_destination)


@patch('openlp.core.ui.library.AppLocation.get_section_data_path')
def test_cloud_download_already_in_managed_storage_is_not_copied(mocked_data_path, folder_library_item, tmp_path):
    source = tmp_path / 'library' / 'cloud-id' / 'clip.mp4'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'media')
    mocked_data_path.return_value = tmp_path
    folder_library_item.settings_section = 'tests'
    folder_library_item._copy_file_to_library_storage = MagicMock()
    assert folder_library_item._prepare_library_file(source) == source
    folder_library_item._copy_file_to_library_storage.assert_not_called()


@patch('openlp.core.ui.library.sha256_file_hash')
def test_cloud_import_reuses_worker_checksum(mocked_hash, folder_library_item, tmp_path):
    source = tmp_path / 'clip.mp4'
    source.write_bytes(b'media')
    folder_library_item.choose_folder_form = MagicMock(**{'exec.return_value': QtWidgets.QDialog.DialogCode.Rejected})
    folder_library_item.manager.get_all_objects.return_value = []
    folder_library_item.manager.save_object.return_value = True
    folder_library_item._prepare_library_file = MagicMock(return_value=source)
    folder_library_item._insert_saved_items = MagicMock()
    folder_library_item.settings_section = 'tests'
    folder_library_item.validate_and_load([source], file_hashes={source: 'verified-sha256'},
                                         file_names={source: 'Welcome video.mp4'})
    mocked_hash.assert_not_called()
    assert folder_library_item.manager.save_object.call_args.args[0].file_hash == 'verified-sha256'
    assert folder_library_item.manager.save_object.call_args.args[0].name == 'Welcome video.mp4'


@patch('openlp.core.ui.library.AppLocation.get_section_data_path')
def test_validate_and_load_numbers_duplicate_filenames(mocked_get_section_data_path, folder_library_item, tmp_path):
    """Imported files with the same name keep distinct copies and library names."""
    sources = []
    for number in range(3):
        source_dir = tmp_path / f'source{number}'
        source_dir.mkdir()
        source = source_dir / 'My file.pptx'
        source.write_bytes(f'presentation {number}'.encode())
        sources.append(source)

    managed_root = tmp_path / 'managed'
    mocked_get_section_data_path.return_value = managed_root
    folder_library_item.settings_section = 'tests'
    folder_library_item.settings.value = MagicMock(side_effect=lambda key: {
        'advanced/copy library files to data folder': True
    }.get(key, False))
    folder_library_item.choose_folder_form = MagicMock(**{
        'exec.return_value': QtWidgets.QDialog.DialogCode.Rejected
    })
    folder_library_item.manager.get_all_objects.return_value = []
    folder_library_item.load_list = MagicMock()
    folder_library_item.load_item = MagicMock(side_effect=lambda item: QtWidgets.QTreeWidgetItem([item.name]))

    folder_library_item.validate_and_load(sources)

    saved_items = [call.args[0] for call in folder_library_item.manager.save_object.call_args_list]
    assert [item.name for item in saved_items] == ['My file.pptx', 'My file (2).pptx', 'My file (3).pptx']
    for number, item in enumerate(saved_items):
        stored_path = Path(item.file_path)
        assert stored_path.parent == managed_root / 'library'
        assert stored_path.name == item.name
        assert stored_path.read_bytes() == f'presentation {number}'.encode()


@patch('openlp.core.ui.library.critical_error_message_box')
@patch('openlp.core.ui.library.AppLocation.get_section_data_path')
def test_validate_and_load_rejects_reimport_of_managed_file(mocked_get_section_data_path, mocked_error,
                                                            folder_library_item, tmp_path):
    """Importing the same source again must not create another numbered library copy."""
    source = tmp_path / 'slides.pptx'
    source.write_bytes(b'presentation')
    managed_root = tmp_path / 'managed'
    mocked_get_section_data_path.return_value = managed_root
    folder_library_item.settings_section = 'tests'
    folder_library_item.settings.value = MagicMock(side_effect=lambda key: {
        'advanced/copy library files to data folder': True
    }.get(key, False))
    folder_library_item.choose_folder_form = MagicMock(**{
        'exec.return_value': QtWidgets.QDialog.DialogCode.Rejected
    })
    folder_library_item.manager.get_all_objects.return_value = []
    folder_library_item.load_list = MagicMock()
    folder_library_item.load_item = MagicMock(side_effect=lambda item: QtWidgets.QTreeWidgetItem([item.name]))

    folder_library_item.validate_and_load([source])
    imported_item = folder_library_item.manager.save_object.call_args.args[0]
    folder_library_item.manager.get_all_objects.return_value = [imported_item]
    folder_library_item.manager.save_object.reset_mock()

    folder_library_item.validate_and_load([source])

    folder_library_item.manager.save_object.assert_not_called()
    mocked_error.assert_called_once()
    assert not (managed_root / 'library' / 'slides (2).pptx').exists()


@patch('openlp.core.ui.library.AppLocation.get_section_data_path')
def test_delete_managed_library_file_only_inside_data_path(mocked_get_section_data_path, folder_library_item, tmp_path):
    """
    Test that managed file deletion only happens for files inside OpenLP data storage.
    """
    managed_root = tmp_path / 'managed'
    managed_library = managed_root / 'library'
    managed_library.mkdir(parents=True)
    external_root = tmp_path / 'external'
    external_root.mkdir(parents=True)
    managed_file = managed_library / 'abc123.jpg'
    external_file = external_root / 'outside.jpg'
    managed_file.write_bytes(b'img')
    external_file.write_bytes(b'img')
    mocked_get_section_data_path.return_value = managed_root
    folder_library_item.settings_section = 'tests'

    folder_library_item._delete_managed_library_file(MockItem(file_path=str(managed_file)))
    folder_library_item._delete_managed_library_file(MockItem(file_path=str(external_file)))

    assert not managed_file.exists()
    assert external_file.exists()


@patch('openlp.core.ui.library.sha256_file_hash')
def test_recursively_delete_folder(mocked_sha256_file_hash, folder_library_item):
    """
    Test that recursively_delete_folder() works
    """
    # GIVEN: A Folder object and mocked functions
    folder_library_item.manager.get_all_objects.side_effect = [
        [MockItem(), MockItem(), MockItem()],
        [MockFolder()],
        [MockItem(), MockItem()],
        []
    ]
    folder_library_item.service_path = Path()
    folder_library_item.manager.delete_object = MagicMock()
    folder_library_item.delete_item = MagicMock()
    mocked_folder = MockFolder()
    mocked_folder.id = 1
    mocked_folder.parent_id = None
    mocked_sha256_file_hash.return_value = 'abcd'

    # WHEN: recursively_delete_group() is called
    folder_library_item.recursively_delete_folder(mocked_folder)

    # THEN: delete_file() should have been called 12 times and manager.delete_object() 7 times.
    assert folder_library_item.manager.delete_object.call_count == 6, \
        'delete_object() should be called 6 times, called {} times'.format(
            folder_library_item.manager.delete_object.call_count)
    assert folder_library_item.delete_item.call_count == 5, 'delete_item() should have been called 5 times'


@patch('openlp.core.ui.library.sha256_file_hash')
def test_on_delete_click(mocked_sha256_file_hash, folder_library_item):
    """
    Test that on_delete_click() works
    """
    # GIVEN: An ImageGroups object and mocked functions
    folder_library_item.check_item_selected = MagicMock(return_value=True)
    folder_library_item.delete_item = MagicMock()
    mocked_item = MockItem()
    mocked_item.id = 1
    mocked_item.file_path = 'imagefile.png'
    mocked_item.file_hash = 'abcd'
    folder_library_item.service_path = Path()
    mocked_row_item = MagicMock()
    mocked_row_item.data.return_value = mocked_item
    mocked_row_item.text.return_value = ''
    folder_library_item.list_view.selectedItems.return_value = [None, mocked_row_item]
    mocked_sha256_file_hash.return_value = 'abcd'

    # WHEN: Calling on_delete_click
    folder_library_item.on_delete_click()

    # THEN: delete_file should have been called twice
    assert folder_library_item.delete_item.call_count == 1, 'delete_item() should have been called once'


@patch('openlp.core.ui.library.sha256_file_hash')
def test_on_delete_click_with_parent(mocked_sha256_file_hash, folder_library_item):
    """
    Test that on_delete_click() works
    """
    # GIVEN: An ImageGroups object and mocked functions
    folder_library_item.check_item_selected = MagicMock(return_value=True)
    folder_library_item.delete_item = MagicMock()
    mocked_item = MockItem()
    mocked_item.id = 1
    mocked_item.folder_id = 1
    mocked_item.file_path = 'imagefile.png'
    mocked_item.file_hash = 'abcd'
    folder_library_item.service_path = Path()
    mocked_row_item = MagicMock()
    mocked_row_item.data.return_value = mocked_item
    mocked_row_item.text.return_value = ''
    folder_library_item.list_view.selectedItems.return_value = [mocked_row_item]
    mocked_sha256_file_hash.return_value = 'abcd'

    # WHEN: Calling on_delete_click
    folder_library_item.on_delete_click()

    # THEN: delete_file should have been called twice
    assert folder_library_item.delete_item.call_count == 1, 'delete_item() should have been called once'


@patch('openlp.core.ui.library.sha256_file_hash')
@patch('openlp.core.ui.library.QtWidgets.QMessageBox.question')
def test_on_delete_click_as_folder(mocked_question, mocked_sha256_file_hash, folder_library_item):
    """
    Test that on_delete_click() works
    """
    # GIVEN: An ImageGroups object and mocked functions
    folder_library_item.check_item_selected = MagicMock(return_value=True)
    folder_library_item.delete_item = MagicMock()
    folder_library_item.recursively_delete_folder = MagicMock()
    mocked_folder = MockFolder()
    mocked_folder.id = 1
    folder_library_item.service_path = Path()
    folder_library_item.list_view.selectedItems.return_value = [MockTreeItem(mocked_folder)]
    mocked_sha256_file_hash.return_value = 'abcd'
    mocked_question.return_value = QtWidgets.QMessageBox.StandardButton.Yes

    # WHEN: Calling on_delete_click
    folder_library_item.on_delete_click()

    # THEN: delete_file should have been called twice
    assert folder_library_item.recursively_delete_folder.call_count == 1, \
        'recursively_delete_folder() should have been called once'


@patch('openlp.core.ui.library.sha256_file_hash')
@patch('openlp.core.ui.library.QtWidgets.QMessageBox.question')
def test_on_delete_click_as_folder_with_parent(mocked_question, mocked_sha256_file_hash, folder_library_item):
    """
    Test that on_delete_click() works
    """
    # GIVEN: An ImageGroups object and mocked functions
    folder_library_item.check_item_selected = MagicMock(return_value=True)
    folder_library_item.delete_item = MagicMock()
    folder_library_item.recursively_delete_folder = MagicMock()
    mocked_folder = MockFolder()
    mocked_folder.id = 1
    mocked_folder.parent_id = 1
    folder_library_item.service_path = Path()
    folder_library_item.list_view.selectedItems.return_value = [MockTreeItem(mocked_folder, MockTreeParent())]
    mocked_sha256_file_hash.return_value = 'abcd'
    mocked_question.return_value = QtWidgets.QMessageBox.StandardButton.Yes

    # WHEN: Calling on_delete_click
    folder_library_item.on_delete_click()

    # THEN: delete_file should have been called twice
    assert folder_library_item.recursively_delete_folder.call_count == 1, \
        'recursively_delete_folder() should have been called once'


def test_on_add_folder_click(folder_library_item):
    """Test that the on_add_folder_click adds a folder to the list"""
    # GIVEN: A folder library item and some mocks
    mocked_folder = MockFolder()
    mocked_folder.id = 1
    mocked_item = MockItem()
    folder_library_item.add_folder_form = MagicMock(**{'exec.return_value': True, 'new_folder': mocked_folder})
    folder_library_item.manager.save_object = MagicMock(return_value=True)
    folder_library_item.manager.get_all_objects = MagicMock(return_value=[mocked_item])
    folder_library_item.load_list = MagicMock()
    folder_library_item.expand_folder = MagicMock()

    # WHEN: on_add_folder_click() is called
    folder_library_item.on_add_folder_click()

    # THEN: Things should happen
    folder_library_item.manager.save_object.assert_called_once_with(mocked_folder)
    folder_library_item.manager.get_all_objects.assert_called_once()
    folder_library_item.load_list.assert_called_once_with([mocked_item])
    folder_library_item.expand_folder.assert_called_once_with(1)


@patch('openlp.core.ui.library.critical_error_message_box')
def test_on_add_folder_click_fails(mocked_critical_error_message_box, folder_library_item):
    """Test that the on_add_folder_click adds a folder to the list"""
    # GIVEN: A folder library item and some mocks
    mocked_folder = MockFolder()
    mocked_folder.id = 1
    folder_library_item.add_folder_form = MagicMock(**{'exec.return_value': True, 'new_folder': mocked_folder})
    folder_library_item.manager.save_object = MagicMock(return_value=False)
    folder_library_item.manager.get_all_objects = MagicMock()
    folder_library_item.load_list = MagicMock()
    folder_library_item.expand_folder = MagicMock()

    # WHEN: on_add_folder_click() is called
    folder_library_item.on_add_folder_click()

    # THEN: Things should happen
    folder_library_item.manager.save_object.assert_called_once_with(mocked_folder)
    folder_library_item.manager.get_all_objects.assert_not_called()
    folder_library_item.load_list.assert_not_called()
    folder_library_item.expand_folder.assert_not_called()
    mocked_critical_error_message_box.assert_called_once_with(message='Could not add the new folder.')
