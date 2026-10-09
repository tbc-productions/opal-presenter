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
"""
This module contains tests for the lib submodule of the Presentations plugin.
"""
import tempfile

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch
import fluentqt

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import get_file_type_glob
from openlp.core.lib import ServiceItemContext
from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem
from openlp.core.lib.theme import TransitionSpeed, TransitionType
from openlp.plugins.presentations.lib.db import Folder, Item
from openlp.plugins.presentations.lib.mediaitem import PresentationMediaItem


def test_inspect_presentation_uses_cached_slides_without_loading_controller(media_item, tmp_path):
    path = tmp_path / 'Sunday.pptx'
    path.write_bytes(b'presentation')
    item = Item(name='Sunday', file_path=str(path))
    controller = MagicMock()
    doc = controller.add_document.return_value
    doc.get_slide_image_paths.return_value = []
    slides = [tmp_path / 'slide1.png', tmp_path / 'slide2.png']
    doc.get_thumbnail_path.side_effect = slides + [None]
    media_item.controllers = {'Powerpoint': controller}
    with patch.object(media_item, 'find_controller_by_type', return_value='Powerpoint'), \
            patch('openlp.plugins.presentations.lib.mediaitem.MediaPreview.show_media') as preview:
        media_item.inspect_item(item)
    preview.assert_called_once_with(media_item, path, 'Sunday', kind='presentation', preview_paths=slides)
    doc.load_presentation.assert_not_called()
    controller.remove_doc.assert_called_once_with(doc)


def test_build_file_mask_string(media_item):
    """
    Test the build_file_mask_string() method
    """
    # GIVEN: Different controllers.
    impress_controller = MagicMock()
    impress_controller.enabled.return_value = True
    impress_controller.supports = ['odp']
    impress_controller.also_supports = ['ppt']
    presentation_controller = MagicMock()
    presentation_controller.enabled.return_value = True
    presentation_controller.supports = ['ppt']
    presentation_controller.also_supports = []
    presentation_viewer_controller = MagicMock()
    presentation_viewer_controller.enabled.return_value = False
    pdf_controller = MagicMock()
    pdf_controller.enabled.return_value = True
    pdf_controller.supports = ['pdf']
    pdf_controller.also_supports = ['xps', 'oxps', 'epub', 'cbz', 'fb2']
    # Mock the controllers.
    media_item.controllers = {
        'Impress': impress_controller,
        'Powerpoint': presentation_controller,
        'Powerpoint Viewer': presentation_viewer_controller,
        'Pdf': pdf_controller
    }

    # WHEN: Build the file mask.
    with patch('openlp.plugins.presentations.lib.mediaitem.translate') as mocked_translate:
        mocked_translate.side_effect = lambda module, string_to_translate: string_to_translate
        media_item.build_file_mask_string()

    # THEN: The file mask should be generated correctly with a space before all bar the first.
    assert get_file_type_glob('odp') in media_item.on_new_file_masks, \
        'The file mask should contain the odp extension'
    assert get_file_type_glob('ppt') in media_item.on_new_file_masks, \
        'The file mask should contain the ppt extension'
    assert get_file_type_glob('pdf') in media_item.on_new_file_masks, \
        'The file mask should contain the pdf extension'
    assert get_file_type_glob('PdF') in media_item.on_new_file_masks, \
        'The file mask should contain the pdf extension'
    assert get_file_type_glob('xps') in media_item.on_new_file_masks, \
        'The file mask should contain the xps extension'
    assert get_file_type_glob('oxps') in media_item.on_new_file_masks, \
        'The file mask should contain the oxps extension'
    assert get_file_type_glob('epub') in media_item.on_new_file_masks, \
        'The file mask should contain the epub extension'
    assert get_file_type_glob('cbz') in media_item.on_new_file_masks, \
        'The file mask should contain the cbz extension'
    assert get_file_type_glob('fb2') in media_item.on_new_file_masks, \
        'The file mask should contain the fb2 extension'


def test_controller_display_names_keep_internal_keys(settings, mock_plugin):
    """Visible controller names may change without changing saved identifiers."""
    from openlp.plugins.presentations.lib.pdfcontroller import PdfController
    from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacController

    pdf_controller = PdfController(mock_plugin)
    with patch('openlp.plugins.presentations.lib.applescriptbasecontroller.APPLESCRIPT_AVAILABLE', False), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.APPLESCRIPT_AVAILABLE', False):
        mac_controller = PowerPointMacController(mock_plugin)

    assert (pdf_controller.name, pdf_controller.display_name) == ('Pdf', 'PDF')
    assert (mac_controller.name, mac_controller.display_name) == ('PowerPointMac', 'PowerPoint (macOS)')


def test_display_type_combo_uses_controller_keys(media_item):
    """The selector shows friendly names while returning saved controller keys."""
    pdf_controller = MagicMock()
    pdf_controller.name = 'Pdf'
    pdf_controller.display_name = 'PDF'
    pdf_controller.enabled.return_value = True
    mac_controller = MagicMock()
    mac_controller.name = 'PowerPointMac'
    mac_controller.display_name = 'PowerPoint (macOS)'
    mac_controller.enabled.return_value = True
    media_item.controllers = {'Pdf': pdf_controller, 'PowerPointMac': mac_controller}
    media_item.automatic = 'Automatic'
    media_item.display_type_combo_box = QtWidgets.QComboBox()
    media_item.presentation_widget = MagicMock()

    media_item.populate_display_types()

    media_item.presentation_widget.setVisible.assert_called_once_with(True)
    combo = media_item.display_type_combo_box
    assert [combo.itemText(index) for index in range(combo.count())] == \
        ['Automatic', 'PDF', 'PowerPoint (macOS)']
    assert [combo.itemData(index) for index in range(combo.count())] == \
        ['automatic', 'Pdf', 'PowerPointMac']
    combo.setCurrentIndex(2)
    assert media_item._selected_controller_name() == 'PowerPointMac'

    media_item.controllers = {'Pdf': pdf_controller}
    media_item.populate_display_types()
    media_item.presentation_widget.setVisible.assert_called_with(False)


def test_validate_and_load_reports_only_unsupported_imports(media_item, tmp_path):
    """Only unsupported inputs should be reported or excluded from import."""
    controller = MagicMock()
    controller.enabled.return_value = True
    controller.supports = ['odp']
    controller.also_supports = []
    media_item.controllers = {'Impress': controller}
    supported = tmp_path / 'new.odp'
    unsupported = tmp_path / 'old.xyz'
    supported.write_bytes(b'presentation')
    unsupported.write_bytes(b'unsupported')

    with patch('openlp.plugins.presentations.lib.mediaitem.FolderLibraryItem.validate_and_load') as load, \
            patch('openlp.plugins.presentations.lib.mediaitem.critical_error_message_box') as error:
        media_item.validate_and_load([supported, unsupported])

    load.assert_called_once_with([supported], None)
    error.assert_called_once()
    assert str(unsupported) in error.call_args.args[1]
    assert str(supported) not in error.call_args.args[1]


def test_load_item_with_unsupported_type_does_not_show_import_error(media_item, tmp_path):
    """Refreshing the library should display an unsupported item without an import alert."""
    file_path = tmp_path / 'old.xyz'
    file_path.write_bytes(b'unsupported')
    media_item.controllers = {}

    with patch('openlp.plugins.presentations.lib.mediaitem.critical_error_message_box') as error:
        result = media_item.load_item(Item(name=file_path.name, file_path=str(file_path)))

    assert result is not None
    assert result.text(0) == 'old'
    error.assert_not_called()


def test_find_controller_by_type_accepts_uppercase_fallback_extension(media_item):
    """A fallback presentation controller should accept uppercase extensions."""
    controller = MagicMock()
    controller.enabled.return_value = True
    controller.supports = ['odp']
    controller.also_supports = ['pptx']
    media_item.controllers = {'Impress': controller}

    assert media_item.find_controller_by_type(Path('Slides.PPTX')) == 'Impress'


def test_clean_up_thumbnails(media_item):
    """
    Test that the clean_up_thumbnails method works as expected when files exist.
    """
    # GIVEN: A mocked controller, and mocked os.path.getmtime
    mocked_disabled_controller = MagicMock()
    mocked_disabled_controller.enabled.return_value = False
    mocked_disabled_supports = PropertyMock()
    type(mocked_disabled_controller).supports = mocked_disabled_supports
    mocked_enabled_controller = MagicMock()
    mocked_enabled_controller.enabled.return_value = True
    mocked_doc = MagicMock(**{'get_thumbnail_path.return_value': Path()})
    mocked_enabled_controller.add_document.return_value = mocked_doc
    mocked_enabled_controller.supports = ['tmp']
    media_item.controllers = {
        'Enabled': mocked_enabled_controller,
        'Disabled': mocked_disabled_controller
    }

    thumb_path = MagicMock(st_mtime=100)
    file_path = MagicMock(st_mtime=400)
    with patch.object(Path, 'stat', side_effect=[thumb_path, file_path]), \
            patch.object(Path, 'exists', return_value=True):
        presentation_file = Path('file.tmp')

        # WHEN: calling clean_up_thumbnails
        media_item.clean_up_thumbnails(presentation_file, True)

    # THEN: doc.presentation_deleted should have been called since the thumbnails mtime will be greater than
    #       the presentation_file's mtime.
    mocked_doc.assert_has_calls([call.get_thumbnail_path(1, True), call.presentation_deleted()], True)
    assert mocked_disabled_supports.call_count == 0


def test_clean_up_thumbnails_missing_file(media_item):
    """
    Test that the clean_up_thumbnails method works as expected when file is missing.
    """
    # GIVEN: A mocked controller, and mocked os.path.exists
    mocked_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    mocked_controller.supports = ['tmp']
    media_item.controllers = {
        'Mocked': mocked_controller
    }
    presentation_file = Path('file.tmp')
    with patch.object(Path, 'exists', return_value=False):

        # WHEN: calling clean_up_thumbnails
        media_item.clean_up_thumbnails(presentation_file, True)

    # THEN: doc.presentation_deleted should have been called since the presentation file did not exist.
    mocked_doc.assert_has_calls([call.get_thumbnail_path(1, True), call.presentation_deleted()], True)


def test_generate_slide_data_from_folder(media_item):
    """
    Test that the generate slide data function exits early when the item is a Folder instead of an Item
    """
    # GIVEN: A Folder instance
    media_item.list_view = MagicMock()
    mocked_service_item = MagicMock()
    folder = Folder(id=1, name='Mock folder')
    list_item = QtWidgets.QTreeWidgetItem(None)
    list_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, folder)

    # WHEN: generate_slide_data is called
    result = media_item.generate_slide_data(mocked_service_item, item=list_item)

    # THEN: The result should be false
    assert result is False


def test_generate_slide_data_from_list_view(media_item):
    """
    Test that the generate slide data function exits early when there are more than 1 items selected
    """
    # GIVEN: A Folder instance
    mocked_service_item = MagicMock()
    list_item = QtWidgets.QTreeWidgetItem(None)
    media_item.list_view = MagicMock(selectedItems=MagicMock(return_value=[list_item, list_item]))

    # WHEN: generate_slide_data is called
    result = media_item.generate_slide_data(mocked_service_item)

    # THEN: The result should be false
    assert result is False


def test_generate_slide_data_with_file_path_from_item(media_item):
    """
    Test that the generate slide data function exits early when there is no display type combobox text
    """
    # GIVEN: A Folder instance
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock(currentText=MagicMock(return_value=''))
    mocked_service_item = MagicMock()
    item = Item(id=1, file_path='path/to/presentation.odp')
    list_item = QtWidgets.QTreeWidgetItem(None)
    list_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)

    # WHEN: generate_slide_data is called
    with patch('openlp.plugins.presentations.lib.mediaitem.QtWidgets.ContentDialog'):
        result = media_item.generate_slide_data(mocked_service_item, item=list_item)

    # THEN: The result should be false
    assert result is False


@pytest.mark.parametrize('suffix', ['pptx', 'odp'])
@pytest.mark.parametrize('context', [ServiceItemContext.Preview, ServiceItemContext.Live])
@pytest.mark.parametrize('selection', ['empty', 'automatic', 'disabled', 'unsupported'])
def test_existing_library_presentation_without_controller_shows_dialog(
        media_item, tmp_path, suffix, context, selection):
    """Preview and Live reject stored presentations with an actionable ContentDialog."""
    path = tmp_path / f'Sunday sermon.{suffix}'
    path.write_bytes(b'presentation')
    tree_item = QtWidgets.QTreeWidgetItem()
    tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, Item(id=1, file_path=str(path)))
    controller = MagicMock()
    controller.enabled.return_value = False
    controller.supports = [suffix]
    controller.also_supports = []
    selected = {'empty': '', 'automatic': 'automatic', 'disabled': 'Powerpoint', 'unsupported': 'Pdf'}[selection]
    if selection == 'unsupported':
        controller.enabled.return_value = True
        controller.supports = ['pdf']
    media_item.controllers = {selected: controller} if selected else {}
    media_item.display_type_combo_box = MagicMock()
    media_item.display_type_combo_box.itemData.return_value = selected
    service_item = MagicMock()

    with patch('openlp.plugins.presentations.lib.mediaitem.QtWidgets.ContentDialog') as dialog:
        result = media_item.generate_slide_data(service_item, item=tree_item, context=context)

    assert result is False
    dialog.assert_called_once()
    dialog.return_value.setTitle.assert_called_once_with('Presentation Unavailable')
    message = dialog.return_value.setContent.call_args.args[0]
    assert message.text() == 'No presentation application is available.'
    dialog.return_value.setPrimaryButtonText.assert_called_once_with('OK')
    dialog.return_value.setSecondaryButtonText.assert_called_once_with('Open Settings')
    controller.add_document.assert_not_called()
    service_item.add_from_command.assert_not_called()


def test_unavailable_remote_presentation_does_not_open_modal_dialog(media_item, tmp_path):
    """Remote failure must not block the operator with a local modal dialog."""
    path = tmp_path / 'sermon.pptx'
    path.write_bytes(b'presentation')
    tree_item = QtWidgets.QTreeWidgetItem()
    tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, Item(id=1, file_path=str(path)))
    media_item.controllers = {}
    media_item.display_type_combo_box = MagicMock()
    media_item.display_type_combo_box.itemData.return_value = ''

    with patch('openlp.plugins.presentations.lib.mediaitem.QtWidgets.ContentDialog') as dialog:
        assert not media_item.generate_slide_data(MagicMock(), item=tree_item, remote=True)
    dialog.assert_not_called()


@pytest.mark.parametrize('open_settings', [False, True])
def test_unavailable_presentation_dialog_commands(media_item, open_settings):
    """OK dismisses the dialog; the secondary command opens the Presentations settings tab."""
    from openlp.core.common.registry import Registry

    parent = QtWidgets.QWidget()
    parent.resize(1000, 700)
    parent.show()
    settings_form = MagicMock()
    Registry().register('settings_form', settings_form)

    def choose():
        dialog = parent.findChild(fluentqt.ContentDialog)
        assert dialog.title() == 'Presentation Unavailable'
        assert dialog.content().text() == 'No presentation application is available.'
        assert dialog.primaryButtonText() == 'OK'
        assert dialog.secondaryButtonText() == 'Open Settings'
        assert dialog.closeButtonText() == ''
        assert dialog.defaultButton() == fluentqt.ContentDialogButton.Primary
        text = 'Open Settings' if open_settings else 'OK'
        button = next(button for button in dialog.findChildren(fluentqt.Button) if button.text() == text)
        button.click()

    QtCore.QTimer.singleShot(0, choose)
    try:
        with patch.object(type(media_item), 'main_window', new_callable=PropertyMock, return_value=parent):
            media_item._show_unavailable_presentation(Path('sermon.pptx'))
        if open_settings:
            settings_form.exec.assert_called_once_with('Presentations')
        else:
            settings_form.exec.assert_not_called()
    finally:
        parent.close()


def test_convert_pdf_menu_position(media_item):
    """Conversion belongs after the separator and immediately before Show in folder."""
    media_item.list_view = QtWidgets.QTreeWidget()
    media_item.add_custom_context_actions()
    actions = media_item.list_view.actions()
    assert actions[-4].isSeparator()
    assert actions[-3] is media_item.powerpoint_settings_action
    assert actions[-2] is media_item.convert_pdf_action
    assert actions[-2].text() == 'Convert to PDF'
    assert actions[-1].text() == 'Show in folder'
    assert not media_item.convert_pdf_action.isVisible()


@pytest.mark.parametrize('suffix,enabled,name,accessible,multiple,expected', [
    ('pptx', True, 'PowerPointMac', True, False, True),
    ('odp', True, 'Impress', True, False, True),
    ('pptx', True, 'Keynote', True, False, True),
    ('pptx', False, 'PowerPointMac', True, False, False),
    ('pdf', True, 'PowerPointMac', True, False, False),
    ('pptx', True, 'PowerPointMac', False, False, False),
    ('pptx', True, 'PowerPointMac', True, True, False),
    ('pptx', True, 'Viewer', True, False, False),
])
def test_convert_pdf_availability(media_item, tmp_path, suffix, enabled, name, accessible, multiple, expected):
    source = tmp_path / f'sermon.{suffix}'
    if accessible:
        source.write_bytes(b'presentation')
    tree_item = QtWidgets.QTreeWidgetItem()
    item = Item(name=source.name, file_path=str(source))
    tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
    media_item.list_view = MagicMock()
    media_item.list_view.selectedItems.return_value = [tree_item, tree_item] if multiple else [tree_item]
    controller = MagicMock()
    controller.name = name
    controller.enabled.return_value = enabled
    controller.supports = ['odp']
    controller.also_supports = ['pptx']
    media_item.controllers = {name: controller}
    assert bool(media_item._pdf_export_selection()) is expected


@pytest.mark.parametrize('folder_id', [None, 12])
def test_convert_pdf_adds_and_selects_copy_in_same_folder(media_item, tmp_path, folder_id):
    parent = QtWidgets.QWidget()
    parent.resize(1000, 700)
    parent.show()
    source = tmp_path / 'sermon.pptx'
    output = tmp_path / 'sermon.pdf'
    source.write_bytes(b'presentation')
    output.write_bytes(b'%PDF-1.7 converted')
    original = Item(name=source.name, file_path=str(source), folder_id=folder_id)
    media_item.list_view = QtWidgets.QTreeWidget()
    original_tree = QtWidgets.QTreeWidgetItem(media_item.list_view)
    original_tree.setData(0, QtCore.Qt.ItemDataRole.UserRole, original)
    controller = MagicMock()
    controller.name = 'PowerPointMac'
    folder = Folder(id=folder_id, name='Sermons') if folder_id else None
    media_item.manager.get_object.return_value = folder

    def insert(items, target_folder):
        assert target_folder is folder
        converted_tree = QtWidgets.QTreeWidgetItem(media_item.list_view)
        converted_tree.setData(0, QtCore.Qt.ItemDataRole.UserRole, items[0])

    try:
        with patch.object(type(media_item), 'main_window', new_callable=PropertyMock, return_value=parent), \
                patch.object(media_item, '_pdf_export_selection', return_value=(original, controller)), \
                patch.object(media_item, '_prepare_library_file', return_value=output), \
                patch.object(media_item, '_insert_saved_items', side_effect=insert), \
                patch('openlp.plugins.presentations.lib.pdfexport.export_to_pdf', return_value=output):
            media_item.on_convert_to_pdf()
        added = media_item.manager.save_object.call_args.args[0]
        assert added.file_path == str(output)
        assert added.folder_id == folder_id
        assert added.file_hash
        selected = media_item.list_view.selectedItems()
        assert len(selected) == 1
        assert selected[0].data(0, QtCore.Qt.ItemDataRole.UserRole) is added
        assert source.read_bytes() == b'presentation'
    finally:
        parent.close()


def test_convert_pdf_failure_shows_error_without_adding_item(media_item, tmp_path):
    parent = QtWidgets.QWidget()
    parent.resize(1000, 700)
    parent.show()
    original = Item(file_path=str(tmp_path / 'sermon.pptx'))
    controller = MagicMock()
    controller.name = 'Keynote'
    try:
        with patch.object(type(media_item), 'main_window', new_callable=PropertyMock, return_value=parent), \
                patch.object(media_item, '_pdf_export_selection', return_value=(original, controller)), \
                patch('openlp.plugins.presentations.lib.pdfexport.export_to_pdf', side_effect=RuntimeError('failed')), \
                patch('openlp.plugins.presentations.lib.mediaitem.critical_error_message_box') as error:
            media_item.on_convert_to_pdf()
        media_item.manager.save_object.assert_not_called()
        error.assert_called_once_with('Conversion Failed', 'The presentation could not be converted to PDF.\n\nfailed')
    finally:
        parent.close()


def test_repair_converted_pdf_names_preserves_custom_labels(media_item, tmp_path):
    hashed_stem = 'a' * 64
    source = Item(name='Sunday sermon.pptx', file_path=str(tmp_path / f'{hashed_stem}.pptx'))
    converted = Item(name=f'{hashed_stem}.pdf', file_path=str(tmp_path / f'{hashed_stem}.pdf'))
    duplicate = Item(name=f'{hashed_stem} (2).pdf', file_path=str(tmp_path / f'{hashed_stem} (2).pdf'))
    custom = Item(name='Custom title.pdf', file_path=str(tmp_path / f'{hashed_stem} (3).pdf'))
    unrelated = Item(name='b' * 64 + '.pdf', file_path=str(tmp_path / ('b' * 64 + '.pdf')))
    media_item._repair_converted_pdf_names([source, converted, duplicate, custom, unrelated])
    assert converted.name == 'Sunday sermon.pdf'
    assert duplicate.name == 'Sunday sermon (2).pdf'
    assert custom.name == 'Custom title.pdf'
    assert unrelated.name == 'b' * 64 + '.pdf'
    assert media_item.manager.save_object.call_args_list == [call(converted), call(duplicate)]


@pytest.mark.parametrize('dismiss', ['button', 'escape', 'close'])
def test_cancel_conversion_waits_and_discards_result(media_item, tmp_path, dismiss):
    from openlp.plugins.presentations.lib.mediaitem import PdfConversionProgressDialog

    parent = QtWidgets.QWidget()
    parent.resize(1000, 700)
    parent.show()
    source = tmp_path / 'sermon.pptx'
    output = tmp_path / 'sermon.pdf'
    source.write_bytes(b'original')
    original = Item(name=source.name, file_path=str(source))
    controller = MagicMock()
    controller.name = 'Keynote'

    def export(*args, cancel_event, **kwargs):
        assert cancel_event.wait(timeout=2)
        output.write_bytes(b'%PDF-1.7')
        return output

    def cancel():
        dialog = parent.findChild(PdfConversionProgressDialog)
        if dismiss == 'button':
            button = next(button for button in dialog.findChildren(fluentqt.Button) if button.text() == 'Cancel')
            button.click()
        elif dismiss == 'escape':
            from PySide6 import QtTest
            QtTest.QTest.keyClick(dialog, QtCore.Qt.Key.Key_Escape)
        else:
            dialog.close()
        assert dialog.wasCanceled()
        assert dialog.isVisible()
        assert dialog.labelText() == 'Cancelling…'

    QtCore.QTimer.singleShot(0, cancel)
    try:
        with patch.object(type(media_item), 'main_window', new_callable=PropertyMock, return_value=parent), \
                patch.object(media_item, '_pdf_export_selection', return_value=(original, controller)), \
                patch('openlp.plugins.presentations.lib.pdfexport.export_to_pdf', side_effect=export), \
                patch('openlp.plugins.presentations.lib.mediaitem.critical_error_message_box') as error:
            media_item.on_convert_to_pdf()
        assert not output.exists()
        assert source.read_bytes() == b'original'
        media_item.manager.save_object.assert_not_called()
        error.assert_not_called()
    finally:
        parent.close()


@pytest.mark.parametrize('suffix,icon_name', [
    ('pptx', 'slide_text_person'), ('odp', 'slide_text'), ('key', 'slide_text_sparkle'), ('pdf', 'pdf')
])
def test_presentation_file_type_icon_follows_name_for_missing_files(media_item, tmp_path, suffix, icon_name):
    from openlp.core.ui.icons import UiIcons
    from openlp.core.widgets.fluent_tree import LIBRARY_FILE_TYPE_ICON_ROLE, FluentLibraryTreeDelegate

    media_item.list_view = QtWidgets.QTreeWidget()
    source = tmp_path / f'sermon.{suffix}'
    item = Item(name=source.name, file_path=str(source))
    tree_item = media_item.load_item(item)
    media_item.list_view.addTopLevelItem(tree_item)
    delegate = FluentLibraryTreeDelegate(media_item.list_view)
    index = media_item.list_view.indexFromItem(tree_item)
    assert tree_item.text(0) == 'sermon'
    assert tree_item.icon(0).cacheKey() == UiIcons().document_question_mark.cacheKey()
    assert tree_item.data(0, LIBRARY_FILE_TYPE_ICON_ROLE).cacheKey() == getattr(UiIcons(), icon_name).cacheKey()
    icons = delegate.trailingIcons(index)
    assert len(icons) == 1
    assert icons[0].cacheKey() == getattr(UiIcons(), icon_name).cacheKey()


def test_generate_slide_data_from_pdf(media_item):
    """
    Test that the generate slide data function makes the correct ajustments to a pdf service item.
    """
    # GIVEN: A mocked pdf service item
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock()
    mocked_service_item = MagicMock()

    # WHEN: generate_slide_data is called
    media_item.generate_slide_data(mocked_service_item, context=ServiceItemContext.Live, file_path=Path('test.pdf'))

    # THEN: The service item should retain the plugin-provided name (so the service
    # manager shows the presentation icon after save/reload) and still override the theme.
    assert isinstance(mocked_service_item.name, MagicMock), \
        'PDF items must not overwrite service_item.name; it should remain the plugin default.'
    mocked_service_item.add_capability.assert_any_call(ItemCapabilities.ProvidesOwnTheme)
    assert mocked_service_item.pdf_transition_settings == {
        'enabled': False,
        'effect': TransitionType.Fade,
        'speed_seconds': 0.8,
        'easing': 'balanced',
        'type': TransitionType.Fade,
        'speed': TransitionSpeed.Normal
    }


def test_generate_slide_data_from_pdf_inherits_item_transition_settings(media_item):
    """
    Test that generating PDF slide data for live/preview inherits transition settings from an existing ServiceItem.
    """
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock(currentText=MagicMock(return_value='Pdf'))
    media_item.find_controller_by_type = MagicMock(return_value='Pdf')
    mocked_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    media_item.controllers = {'Pdf': mocked_controller}

    source_item = ServiceItem(None)
    source_item.slide_transition_settings = {
        'enabled': True,
        'type': TransitionType.Slide,
        'speed': TransitionSpeed.Slow
    }
    target_service_item = ServiceItem(None)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / 'test.pdf'
        pdf_path.write_text('x')
        (temp_path / 'mainslide001.png').write_text('x')
        mocked_doc.get_thumbnail_path.return_value = None
        mocked_doc.get_temp_folder.return_value = temp_path
        mocked_doc.get_thumbnail_folder.return_value = temp_path

        result = media_item.generate_slide_data(
            target_service_item,
            item=source_item,
            context=ServiceItemContext.Live,
            file_path=pdf_path
        )

    assert result is True
    assert target_service_item.data_string == {'file_path': pdf_path}
    assert target_service_item.slide_transition_settings == {
        'enabled': True,
        'type': TransitionType.Slide,
        'speed': TransitionSpeed.Slow
    }
    assert target_service_item.pdf_transition_settings['enabled'] is True
    assert target_service_item.pdf_transition_settings['effect'] == TransitionType.Slide
    assert target_service_item.pdf_transition_settings['speed'] == TransitionSpeed.Slow
    assert target_service_item.pdf_transition_settings['speed_seconds'] == 1.2


def test_generate_slide_data_from_pdf_ignores_default_target_settings_and_uses_source_custom_settings(media_item):
    """
    Test that default-equivalent target settings do not block custom settings from the source service item.
    """
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock(currentText=MagicMock(return_value='Pdf'))
    media_item.find_controller_by_type = MagicMock(return_value='Pdf')
    mocked_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    media_item.controllers = {'Pdf': mocked_controller}

    source_item = ServiceItem(None)
    source_item.slide_transition_settings = {
        'enabled': True,
        'type': TransitionType.Zoom,
        'speed': TransitionSpeed.Fast
    }
    target_service_item = ServiceItem(None)
    target_service_item.slide_transition_settings = {
        'enabled': False,
        'type': 'fade',
        'speed': 'normal'
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / 'test.pdf'
        pdf_path.write_text('x')
        (temp_path / 'mainslide001.png').write_text('x')
        mocked_doc.get_thumbnail_path.return_value = None
        mocked_doc.get_temp_folder.return_value = temp_path
        mocked_doc.get_thumbnail_folder.return_value = temp_path

        result = media_item.generate_slide_data(
            target_service_item,
            item=source_item,
            context=ServiceItemContext.Service,
            file_path=pdf_path
        )

    assert result is True
    assert target_service_item.slide_transition_settings == {
        'enabled': True,
        'type': TransitionType.Zoom,
        'speed': TransitionSpeed.Fast
    }
    assert target_service_item.pdf_transition_settings['enabled'] is True
    assert target_service_item.pdf_transition_settings['effect'] == TransitionType.Zoom
    assert target_service_item.pdf_transition_settings['speed'] == TransitionSpeed.Fast
    assert target_service_item.pdf_transition_settings['speed_seconds'] == 0.4


def test_generate_slide_data_from_pdf_uses_target_custom_settings_over_source(media_item):
    """
    Test that existing target service item custom transition settings take precedence over inherited source settings.
    """
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock(currentText=MagicMock(return_value='Pdf'))
    media_item.find_controller_by_type = MagicMock(return_value='Pdf')
    mocked_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    media_item.controllers = {'Pdf': mocked_controller}

    source_item = ServiceItem(None)
    source_item.slide_transition_settings = {
        'enabled': True,
        'type': TransitionType.Zoom,
        'speed': TransitionSpeed.Slow
    }
    target_service_item = ServiceItem(None)
    target_service_item.slide_transition_settings = {
        'enabled': True,
        'type': TransitionType.Convex,
        'speed': TransitionSpeed.Fast
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / 'test.pdf'
        pdf_path.write_text('x')
        (temp_path / 'mainslide001.png').write_text('x')
        mocked_doc.get_thumbnail_path.return_value = None
        mocked_doc.get_temp_folder.return_value = temp_path
        mocked_doc.get_thumbnail_folder.return_value = temp_path

        result = media_item.generate_slide_data(
            target_service_item,
            item=source_item,
            context=ServiceItemContext.Service,
            file_path=pdf_path
        )

    assert result is True
    assert target_service_item.slide_transition_settings == {
        'enabled': True,
        'type': TransitionType.Convex,
        'speed': TransitionSpeed.Fast
    }
    assert target_service_item.pdf_transition_settings['effect'] == TransitionType.Convex
    assert target_service_item.pdf_transition_settings['speed'] == TransitionSpeed.Fast


def test_generate_slide_data_from_pdf_uses_legacy_pdf_transition_settings_when_present(media_item):
    """
    Test that legacy pdf_transition_settings are respected when slide_transition_settings are default-equivalent.
    """
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock(currentText=MagicMock(return_value='Pdf'))
    media_item.find_controller_by_type = MagicMock(return_value='Pdf')
    mocked_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    media_item.controllers = {'Pdf': mocked_controller}

    source_item = ServiceItem(None)
    source_item.slide_transition_settings = {'enabled': False, 'type': 'fade', 'speed': 'normal'}
    source_item.pdf_transition_settings = {'enabled': True, 'effect': TransitionType.Slide, 'speed': TransitionSpeed.Slow}
    target_service_item = ServiceItem(None)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / 'test.pdf'
        pdf_path.write_text('x')
        (temp_path / 'mainslide001.png').write_text('x')
        mocked_doc.get_thumbnail_path.return_value = None
        mocked_doc.get_temp_folder.return_value = temp_path
        mocked_doc.get_thumbnail_folder.return_value = temp_path

        result = media_item.generate_slide_data(
            target_service_item,
            item=source_item,
            context=ServiceItemContext.Service,
            file_path=pdf_path
        )

    assert result is True
    assert target_service_item.slide_transition_settings == {
        'enabled': True,
        'type': TransitionType.Slide,
        'speed': TransitionSpeed.Slow
    }
    assert target_service_item.pdf_transition_settings['effect'] == TransitionType.Slide
    assert target_service_item.pdf_transition_settings['speed'] == TransitionSpeed.Slow
    assert target_service_item.pdf_transition_settings['speed_seconds'] == 1.2


def test_generate_slide_data_from_pdf_preserves_existing_service_item_transition_settings(media_item):
    """
    Test that regenerating a PDF service item keeps that item's custom transition settings.
    """
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock(currentText=MagicMock(return_value='Pdf'))
    media_item.find_controller_by_type = MagicMock(return_value='Pdf')
    mocked_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    media_item.controllers = {'Pdf': mocked_controller}

    target_service_item = ServiceItem(None)
    target_service_item.slide_transition_settings = {
        'enabled': True,
        'type': TransitionType.Convex,
        'speed': TransitionSpeed.Fast
    }
    list_item = QtWidgets.QTreeWidgetItem(None)
    list_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, Item(id=1, file_path='test.pdf'))

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / 'test.pdf'
        pdf_path.write_text('x')
        (temp_path / 'mainslide001.png').write_text('x')
        mocked_doc.get_thumbnail_path.return_value = None
        mocked_doc.get_temp_folder.return_value = temp_path
        mocked_doc.get_thumbnail_folder.return_value = temp_path

        result = media_item.generate_slide_data(
            target_service_item,
            item=list_item,
            context=ServiceItemContext.Service,
            file_path=pdf_path
        )

    assert result is True
    assert target_service_item.slide_transition_settings == {
        'enabled': True,
        'type': TransitionType.Convex,
        'speed': TransitionSpeed.Fast
    }
    assert target_service_item.pdf_transition_settings['enabled'] is True
    assert target_service_item.pdf_transition_settings['effect'] == TransitionType.Convex
    assert target_service_item.pdf_transition_settings['speed'] == TransitionSpeed.Fast
    assert target_service_item.pdf_transition_settings['speed_seconds'] == 0.4


def test_generate_slide_data_rebuilds_missing_first_thumbnail_cache(media_item):
    """
    Test that generate_slide_data retries thumbnail export by clearing stale cache when slide 1 is missing.
    """
    # GIVEN: A presentation service item where initial thumbnail lookup fails, but succeeds after cache cleanup.
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock(
        currentText=MagicMock(return_value='Powerpoint'),
        currentIndex=MagicMock(return_value=0),
        itemData=MagicMock(return_value='Powerpoint')
    )
    mocked_service_item = MagicMock()
    mocked_doc = MagicMock()
    mocked_doc.get_thumbnail_path.side_effect = [None, None, Path('slide1.png'), None]
    mocked_doc.get_titles_and_notes.return_value = ([], [])
    mocked_controller = MagicMock()
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    media_item.controllers = {'Powerpoint': mocked_controller}

    with patch.object(Path, 'exists', return_value=True), patch('os.access', return_value=True):
        # WHEN: generate_slide_data is called for a PPTX file.
        success = media_item.generate_slide_data(
            mocked_service_item,
            item=MagicMock(),
            file_path=Path('test.pptx')
        )

    # THEN: The stale cache should be cleaned and thumbnails regenerated successfully.
    assert success is True
    mocked_doc.presentation_deleted.assert_called_once()
    assert mocked_doc.load_presentation.call_count == 2
    mocked_service_item.add_from_command.assert_called_once()


@patch('openlp.core.lib.ui.Registry')
def test_generate_slide_data_with_nonexistent_path(MockRegistry, media_item):
    """
    Test that the generate slide data function shows the right error for non-existent paths.
    """
    # GIVEN: A mocked pdf service item
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock()
    mocked_service_item = MagicMock()

    # WHEN: generate_slide_data is called with a file_path that doesn't really exist
    success = media_item.generate_slide_data(
            mocked_service_item,
            item=mocked_service_item,
            context=ServiceItemContext.Live,
            file_path=Path('test.pdf')
    )

    # THEN: a error message box should appear telling the user that the path doesn't exist
    MockRegistry.return_value.get.return_value.error_message.assert_called_once_with(
            'Missing Presentation',
            'The presentation test.pdf no longer exists.'
    )

    # THEN: The slide data could not be generated.
    assert success is False, 'The slide data could not be generated'


@patch('openlp.core.lib.ui.Registry')
def test_generate_slide_data_with_inaccessible_path(MockRegistry, media_item):
    """
    Test that the generate slide data function shows the right error for inaccessible paths.
    """
    # GIVEN: A mocked pdf service item
    media_item.list_view = MagicMock()
    media_item.display_type_combo_box = MagicMock()
    mocked_service_item = MagicMock()

    with patch('openlp.plugins.presentations.lib.mediaitem.Path') as mocked_path:
        # GIVEN: A fake file which "exists" cannot be read - so it's inaccessible
        mocked_path.exists.return_value = True
        file_path = mocked_path('test.pdf')
        file_path.suffix = '.pdf'

        # WHEN: generate_slide_data is called with a file_path that can't be read
        success = media_item.generate_slide_data(
                mocked_service_item,
                item=mocked_service_item,
                context=ServiceItemContext.Live,
                file_path=file_path
        )

        # THEN: a error message box should appear telling the user that the path doesn't exist
        MockRegistry.return_value.get.return_value.error_message.assert_called_once_with(
                'Missing Presentation',
                f'The presentation {file_path} is inaccessible.'
        )

        # THEN: The slide data could not be generated.
        assert success is False, 'The slide data could not be generated'


@patch('openlp.plugins.presentations.lib.mediaitem.FolderLibraryItem._setup')
@patch('openlp.plugins.presentations.lib.mediaitem.PresentationMediaItem.setup_item')
def test_search_found(mock_setup, mock_item, registry):
    """
    Test that the search method works correctly
    """
    # GIVEN: The Mediaitem set up a list of presentations
    media_item = PresentationMediaItem(None, MagicMock(), None)
    media_item.manager = MagicMock()
    media_item.manager.get_all_objects.return_value = [MagicMock(file_path='test.odp')]

    # WHEN: Retrieving the test file
    result = media_item.search('test.odp', False)

    # THEN: a file should be found
    assert result == [['test.odp', 'test.odp']], 'The result file contain the file name'


@patch('openlp.plugins.presentations.lib.mediaitem.FolderLibraryItem._setup')
@patch('openlp.plugins.presentations.lib.mediaitem.PresentationMediaItem.setup_item')
def test_search_not_found(mock_setup, mock_item, registry):
    """
    Test that the search doesn't find anything
    """
    # GIVEN: The Mediaitem set up a list of media
    media_item = PresentationMediaItem(None, MagicMock(), None)
    media_item.manager = MagicMock()
    media_item.manager.get_all_objects.return_value = []

    # WHEN: Retrieving the test file
    result = media_item.search('test.pptx', False)

    # THEN: a file should be found
    assert result == [], 'The result file should be empty'


def test_load_item_metadata_columns(media_item):
    """Test that load_item populates the Date column and tooltip with type and size for an accessible file"""
    # GIVEN: A presentation file item and a controlled stat result
    file_path = Path('/presentations/slides.pptx')
    item = MagicMock(file_path=file_path)
    mocked_stat = MagicMock()
    mocked_stat.st_size = 5 * 1024 * 1024  # 5.0 MB
    mocked_stat.st_mtime = 1700000000.0
    mocked_controller = MagicMock()
    mocked_doc = MagicMock()
    mocked_doc.get_thumbnail_path.return_value = None
    mocked_controller.add_document.return_value = mocked_doc
    mocked_controller.supports = ['pptx']
    mocked_controller.also_supports = []
    media_item.controllers = {'pptx': mocked_controller}

    with patch.object(Path, 'exists', return_value=True), \
            patch('os.access', return_value=True), \
            patch.object(Path, 'stat', return_value=mocked_stat), \
            patch('openlp.plugins.presentations.lib.mediaitem.PresentationMediaItem.find_controller_by_type',
                  return_value='pptx'), \
            patch('openlp.plugins.presentations.lib.mediaitem.UiIcons') as mocked_icons:
        mocked_icons.return_value.document_question_mark = QtGui.QIcon()

        # WHEN: load_item() is called for initial load (skips generating thumbnails)
        result = media_item.load_item(item, is_initial_load=True)

    # THEN: Date column should be populated, tooltip enriched with type and size
    assert result.text(1) == datetime.fromtimestamp(1700000000.0).strftime('%Y-%m-%d %H:%M')
    assert result.toolTip(0) == '/presentations/slides.pptx\nPPTX · 5.0 MB'
