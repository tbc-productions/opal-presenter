"""Cloud transfers validate inputs and keep UI updates on the main thread."""
import zipfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6 import QtCore, QtGui

from openlp.core.lib.plugin import PluginStatus
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.dnd import ItemDragData, ThemeDragData
from openlp.plugins.librarysync.lib.panel import CloudDragData, CloudLibrary
from openlp.plugins.librarysync.lib.preview import CloudPreviewWindow
from openlp.plugins.librarysync.lib.provider import CATEGORIES, CloudItem, SyncError
from openlp.plugins.librarysync.lib.transfer import (
    import_item, item_category, prepare_upload, read_xml_item, safe_name, safe_xml, write_upload)
from openlp.plugins.librarysync.lib.worker import SyncWorker


@pytest.fixture
def panel(settings, qtbot):
    plugin = SimpleNamespace(settings=settings, main_window=SimpleNamespace(media_tool_box=MagicMock()))
    widget = CloudLibrary(plugin, None)
    qtbot.addWidget(widget)
    widget.set_profile({'version': 1, 'provider': 'google-drive',
                        'installed': {'client_id': 'church.apps.googleusercontent.com', 'client_secret': 'client'},
                        'folders': [{'id': 'church', 'name': 'Church Library'}]})
    yield widget
    widget.shutdown()


def test_cloud_panel_has_simple_disconnected_state(panel):
    assert panel.roots.currentText() == 'Church Library'
    assert panel.connect_action.text() == 'Connect'
    assert not panel.download_action.isEnabled()
    assert not panel.preview_action.isEnabled()
    assert panel.cancel_button.isHidden()
    assert panel.tree.topLevelItemCount() == 0
    assert panel.import_info.isHidden()
    assert panel.connect_action.isEnabled()
    assert all(not tree.isEnabled() for tree in panel.trees.values())
    assert not panel.search.isEnabled()
    assert panel.status.parentWidget() is panel.footer
    panel.set_status('Ready to connect')
    assert panel.status.toolTip() == 'Ready to connect'
    from openlp.core.widgets.docks import MediaToolBox
    from fluentqt import Breadcrumb
    assert isinstance(panel.sections, MediaToolBox)
    assert isinstance(panel.tree, QtWidgets.QTreeDataGrid)
    assert isinstance(panel.breadcrumbs, Breadcrumb)
    assert [panel.sections.itemText(index) for index in range(panel.sections.count())] == [
        'Songs', 'Presentations', 'Images', 'Media', 'Custom Slides', 'Themes']
    assert not hasattr(panel, 'preview_text') and not hasattr(panel, 'preview_image')


def test_transfer_progress_shares_footer_and_starts_indeterminate(panel, monkeypatch):
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.run_thread', MagicMock())
    panel.start_job('upload', MagicMock())
    job_id = next(iter(panel.jobs))
    assert panel.footer.layout().itemAt(0).widget() is panel.footer.count_label
    assert panel.footer.layout().itemAt(1).widget() is panel.transfer_progress
    assert panel.footer.layout().itemAt(2).widget() is panel.status
    assert panel.progress.parentWidget() is panel.transfer_progress
    assert panel.cancel_button.parentWidget() is panel.transfer_progress
    assert not panel.transfer_progress.isHidden()
    assert not panel.cancel_button.isHidden()
    assert panel.progress.maximum() == 0
    panel.job_progress(job_id, 'Uploading Welcome', 40, 100)
    assert panel.progress.value() == 40 and panel.progress.text() == '40%'
    panel.update_actions()
    assert panel.progress.value() == 40
    panel.job_progress(job_id, 'Uploading Next item', 0, 0)
    assert panel.progress.maximum() == 0
    panel.jobs.clear()
    panel.update_actions()
    assert panel.transfer_progress.isHidden()
    panel.start_job('download', MagicMock())
    assert panel.progress.maximum() == 0


def test_old_transfer_progress_cannot_change_current_footer(panel):
    panel.jobs['old'] = {'kind': 'upload', 'generation': panel.generation - 1}
    panel.set_status('Ready')
    panel.job_progress('old', 'Uploading old item', 50, 100)
    assert panel.status.text() == 'Ready'
    assert panel.progress.maximum() == 0


def test_transfer_footer_height_is_stable_and_cancel_is_small_subtle(panel, qtbot):
    from openlp.core.widgets.libraryfooter import LibraryFooter
    library_footer = LibraryFooter()
    qtbot.addWidget(library_footer)
    library_footer.show()
    panel.resize(850, 600)
    panel.show()
    QtWidgets.QApplication.processEvents()
    height = panel.footer.height()
    assert height == library_footer.height()
    assert panel.footer.geometry().bottom() == panel.rect().bottom()
    assert panel.footer.geometry().top() == panel.sections.geometry().bottom() + 1
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, library_footer)
    library_footer.layout().addWidget(slider)
    button = QtWidgets.QPushButton('List', library_footer)
    button.setFluentSize(QtWidgets.fluentqt.Button.ButtonSize.Small)
    button.setFluentStyle(QtWidgets.fluentqt.Button.ButtonStyle.Subtle)
    library_footer.layout().addWidget(button)
    QtWidgets.QApplication.processEvents()
    assert height == library_footer.height()
    panel.jobs['transfer'] = {'kind': 'upload', 'generation': panel.generation}
    panel.update_actions()
    QtWidgets.QApplication.processEvents()
    assert panel.footer.height() == height
    assert panel.footer.geometry().bottom() == panel.rect().bottom()
    assert panel.footer.geometry().top() == panel.sections.geometry().bottom() + 1
    panel.job_progress('transfer', 'Uploading Welcome', 40, 100)
    QtWidgets.QApplication.processEvents()
    assert panel.footer.height() == height
    assert panel.progress.height() <= panel.footer.height() - 12
    assert panel.cancel_button.fluentSize() == QtWidgets.fluentqt.Button.ButtonSize.Small
    assert panel.cancel_button.fluentStyle() == QtWidgets.fluentqt.Button.ButtonStyle.Subtle
    panel.jobs.clear()
    panel.update_actions()
    QtWidgets.QApplication.processEvents()
    assert panel.footer.height() == height


@pytest.mark.parametrize('cached,outdated', [(False, False), (True, False), (True, True)])
def test_error_status_uses_fluent_critical_colour_and_keeps_details(panel, cached, outdated):
    panel.cached_listing = cached
    panel.out_of_date = outdated
    panel.set_status('Download failed', detail='Check your folder permissions.', error=True)
    critical = panel._status_theme.theme_tokens().colors.systemCritical.name()
    assert panel.status.styleSheet() == 'color: ' + critical + ';'
    assert 'Check your folder permissions.' in panel.status.toolTip()
    assert 'Download failed' in panel.status.toolTip()
    if outdated:
        assert panel.status.text() == 'Out of date'
        assert not panel.refresh_button.isHidden()
    else:
        assert panel.status.text() == ('Cached · Download failed' if cached else 'Download failed')
    panel.set_status('Up to date')
    assert bool(panel.status.styleSheet()) == outdated
    assert 'Check your folder permissions.' not in panel.status.toolTip()


@pytest.mark.parametrize('kind,cached,text', [
    ('changes', False, 'Couldn’t check for updates'), ('browse', True, 'Cached · Refresh failed'),
    ('upload', False, 'No connection')])
def test_failed_jobs_show_critical_status_and_preserve_error_details(panel, kind, cached, text):
    panel.cached_listing = cached
    panel.jobs['failed'] = {'kind': kind, 'generation': panel.generation, 'cached': cached}
    panel.job_failed('failed', 'No connection')
    assert panel.status.text() == text
    assert 'No connection' in panel.status.toolTip()
    assert panel._status_theme.theme_tokens().colors.systemCritical.name() in panel.status.styleSheet()
    panel.jobs.clear()


@pytest.mark.parametrize('count,text', [(1, 'Uploaded 1 item'), (2, 'Uploaded 2 items')])
def test_uploaded_status_uses_correct_item_count(panel, count, text):
    panel.jobs['upload'] = {'kind': 'upload', 'generation': panel.generation}
    panel.job_ready('upload', count)
    assert panel.status.text() == text
    assert not panel.status.styleSheet()
    panel.jobs.clear()


def test_no_connections_shows_import_infobar_and_disables_connect(panel, qtbot, monkeypatch):
    imported = MagicMock()
    monkeypatch.setattr(CloudLibrary, 'import_connection', imported)
    empty = CloudLibrary(panel.plugin, None)
    qtbot.addWidget(empty)
    assert isinstance(empty.import_info, QtWidgets.fluentqt.InfoBar)
    assert isinstance(empty.import_info.actionWidget(), QtWidgets.fluentqt.HyperlinkButton)
    assert not empty.import_info.isHidden()
    assert not empty.connect_action.isEnabled()
    assert not empty.roots.isEnabled()
    assert all(not tree.isEnabled() for tree in empty.trees.values())
    assert not empty.search.isEnabled()
    assert empty.navigation.isHidden()
    assert 'organisation' in empty.import_info.message()
    empty.resize(850, 600)
    empty.show()
    QtWidgets.QApplication.processEvents()
    assert empty.import_info.width() == empty.width() - empty.layout().contentsMargins().left() * 2
    empty.import_button.click()
    imported.assert_called_once()
    empty.shutdown()


def test_cached_listing_and_permissions_are_visible(panel):
    item = CloudItem('image', 'Sunday.png', size=100, category='images',
                     preview_url='https://drive.google.com/file/d/image/view')
    panel.category = 'images'
    panel.jobs['listing'] = {'kind': 'browse', 'generation': panel.generation, 'context': False}
    panel.job_ready('listing', (CloudItem('church', 'Church', folder=True), [item], 'next'))
    panel.jobs.clear()
    panel.tree.topLevelItem(0).setSelected(True)
    panel.update_actions()
    assert panel.tree.topLevelItemCount() == 1
    assert panel.tree.topLevelItem(0).text(0) == 'Sunday'
    assert panel.download_action.isEnabled()
    assert panel.preview_action.isEnabled()
    assert 'Read-only' in panel.status.text()
    panel.start_job = MagicMock()
    panel.browse(panel.folder)
    panel.start_job.assert_not_called()
    assert panel.tree.topLevelItemCount() == 1
    panel.filter_items('missing')
    assert panel.tree.topLevelItem(0).isHidden()
    panel.filter_items('Sunday')
    assert not panel.tree.topLevelItem(0).isHidden()


def test_cloud_drag_requires_matching_library(panel):
    mime = CloudDragData(panel, [CloudItem('f', 'Sunday.png', category='images')])
    assert mime.can_import(SimpleNamespace(plugin=SimpleNamespace(name='images')))
    assert not mime.can_import(SimpleNamespace(plugin=SimpleNamespace(name='songs')))
    blocked = CloudDragData(panel, [CloudItem('f', 'Sunday.png', category='images', can_download=False)])
    assert not blocked.can_import(SimpleNamespace(plugin=SimpleNamespace(name='images')))


def test_upload_drop_is_disabled_for_readers(panel):
    panel.connected = True
    view = QtWidgets.QListWidget()
    view.addItem('Amazing Grace')
    view.item(0).setSelected(True)
    library = SimpleNamespace(plugin=SimpleNamespace(name='songs'), list_view=view,
                              get_library_tab_icon=lambda: QtGui.QIcon())
    mime = ItemDragData(library=library)
    panel.folder = CloudItem('church', 'Church', folder=True, can_upload=False)
    assert not panel.can_upload(mime)
    panel.folder = CloudItem('church', 'Church', folder=True, can_upload=True)
    assert panel.can_upload(mime)
    mime.indexes = ()
    assert not panel.can_upload(mime)
    view.deleteLater()


def test_local_drop_can_switch_cloud_type_but_same_type_requires_matching_folder(panel):
    panel.connected = True
    view = QtWidgets.QListWidget()
    view.addItem('Sunday')
    view.item(0).setSelected(True)
    library = SimpleNamespace(plugin=SimpleNamespace(name='images'), list_view=view,
                              get_library_tab_icon=lambda: QtGui.QIcon())
    mime = ItemDragData(library=library)
    panel.folder = CloudItem('root', 'Organisation', folder=True, can_upload=True)
    assert panel.category == 'songs'
    assert panel.can_upload(mime)
    panel.category = 'images'
    assert panel.can_upload(mime)
    assert panel.can_upload(mime, CloudItem('advent', 'Advent', folder=True, category='images', can_upload=True))
    assert not panel.can_upload(mime, CloudItem(
        'custom', 'Custom Slides', folder=True, category='custom', can_upload=True))
    view.deleteLater()


@pytest.mark.parametrize('category', CATEGORIES)
@pytest.mark.parametrize('writable', [True, False])
def test_local_cross_type_drop_switches_view_and_checks_correct_destination(panel, qtbot, monkeypatch,
                                                                            tmp_path, category, writable):
    panel.connected = True
    panel.update_actions()
    view = QtWidgets.QListWidget()
    qtbot.addWidget(view)
    view.addItem('Welcome')
    view.item(0).setSelected(True)
    library = SimpleNamespace(plugin=SimpleNamespace(name=category), list_view=view,
                              get_library_tab_icon=lambda: QtGui.QIcon())
    mime = (ThemeDragData(library, view.selectedIndexes()) if category == 'themes'
            else ItemDragData(library=library))
    panel.change_type(list(CATEGORIES).index('images' if category == 'songs' else 'songs'), browse=False)
    wrong_folder = CloudItem('wrong-subfolder', 'Old folder', folder=True, category=panel.category)
    panel.folder, panel.history = wrong_folder, [wrong_folder]
    panel.search.setText('Old filter')
    old_tree = panel.tree
    row = QtWidgets.QTreeWidgetItem(['Old folder'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, wrong_folder)
    old_tree.addTopLevelItem(row)
    old_tree.itemAt = MagicMock(return_value=row)
    source = (category, tmp_path / 'Welcome.xml', None, 'Welcome')
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.prepare_upload', MagicMock(return_value=[source]))
    panel.start_job, panel.browse = MagicMock(), MagicMock()
    enter = QtGui.QDragEnterEvent(QtCore.QPoint(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                                  QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(old_tree.viewport(), enter)
    assert enter.isAccepted()
    assert panel.category == category and panel.tree is panel.trees[category]
    assert panel.sections.currentIndex() == list(CATEGORIES).index(category)
    old_tree.dragLeaveEvent(QtGui.QDragLeaveEvent())
    panel.browse.assert_not_called()
    move = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                                QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(panel.tree.viewport(), enter)
    QtWidgets.QApplication.sendEvent(panel.tree.viewport(), move)
    assert move.isAccepted()
    event = QtGui.QDropEvent(QtCore.QPointF(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    if category == 'images':
        old_tree.dropEvent(event)
    else:
        QtWidgets.QApplication.sendEvent(panel.tree.viewport(), event)
    assert event.isAccepted()
    assert panel.category == category and panel.tree is panel.trees[category]
    assert panel.sections.currentIndex() == list(CATEGORIES).index(category)
    assert panel.folder is None and not panel.history and not panel.search.text()
    panel.browse.assert_not_called()
    panel.start_job.assert_called_once()
    kind, prepare, context = panel.start_job.call_args.args
    assert kind == 'prepare-upload' and context['folder'] is None
    provider = MagicMock()
    shared = CloudItem('shared', 'Organisation', folder=True, can_upload=True)
    target = CloudItem('correct-type', CATEGORIES[category], folder=True, category=category, can_upload=writable)
    provider.folder.return_value, provider.type_folder.return_value = shared, target
    provider.find_item.return_value = None
    try:
        if writable:
            plan = prepare(provider)
            assert context['folder'] is target
            assert plan == [(source, None)]
            provider.find_item.assert_called_once_with(target, category, 'Welcome', exclude='', extension='.xml')
            panel.run_upload = MagicMock()
            panel.jobs['prepared'] = {'kind': kind, 'context': context, 'generation': panel.generation}
            panel.job_ready('prepared', plan)
            panel.job_completed('prepared')
            panel.run_upload.assert_called_once_with(context, plan)
        else:
            with pytest.raises(SyncError, match='read-only'):
                prepare(provider)
            provider.find_item.assert_not_called()
            panel.jobs['prepared'] = {'kind': kind, 'context': context, 'generation': panel.generation, 'failed': True}
            panel.job_completed('prepared')
            panel.browse.assert_called_once_with()
        root = panel.roots.currentData()
        provider.folder.assert_called_once_with(root['id'], root['resource_key'])
        provider.type_folder.assert_called_once_with(shared, category, create=False)
        provider.upload.assert_not_called()
    finally:
        context['temporary'].cleanup()


def test_leaving_cloud_after_type_switch_loads_the_selected_type(panel, qtbot):
    panel.connected = True
    panel.folder = CloudItem('songs', 'Songs', folder=True, category='songs', can_upload=True)
    panel.update_actions()
    view = QtWidgets.QListWidget()
    qtbot.addWidget(view)
    view.addItem('Welcome')
    view.item(0).setSelected(True)
    library = SimpleNamespace(plugin=SimpleNamespace(name='images'), list_view=view,
                              get_library_tab_icon=lambda: QtGui.QIcon())
    mime = ItemDragData(library=library)
    panel.browse = MagicMock()
    event = QtGui.QDragEnterEvent(QtCore.QPoint(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                                  QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(panel.tree.viewport(), event)
    assert event.isAccepted() and panel.category == 'images'
    panel.tree.dragLeaveEvent(QtGui.QDragLeaveEvent())
    panel.browse.assert_called_once_with()


@pytest.mark.parametrize('blocked', ['disconnected', 'busy', 'outdated', 'unverified', 'browsing',
                                     'unsupported', 'invalid'])
def test_cross_type_drop_keeps_transfer_guards(panel, qtbot, blocked):
    panel.connected = blocked != 'disconnected'
    view = QtWidgets.QListWidget()
    qtbot.addWidget(view)
    view.addItem('Welcome')
    view.item(0).setSelected(True)
    library = SimpleNamespace(plugin=SimpleNamespace(name='bibles' if blocked == 'unsupported' else 'images'),
                              list_view=view, get_library_tab_icon=lambda: QtGui.QIcon())
    mime = ItemDragData(library=library)
    panel.folder = CloudItem('songs', 'Songs', folder=True, category='songs', can_upload=True)
    if blocked in ('busy', 'browsing'):
        panel.jobs['block'] = {'kind': 'upload' if blocked == 'busy' else 'browse'}
    elif blocked == 'outdated':
        panel.out_of_date = True
    elif blocked == 'unverified':
        panel.cached_listing, panel.cache_checked = True, False
    elif blocked == 'invalid':
        view.clear()
    assert not panel.can_upload(mime)
    event = QtGui.QDragEnterEvent(QtCore.QPoint(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                                  QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    panel.tree.dragEnterEvent(event)
    assert not event.isAccepted()
    assert panel.category == 'songs'
    panel.jobs.clear()


def test_cloud_drop_uses_writable_subfolder_and_matching_type(panel):
    panel.connected = True
    panel.category = 'images'
    item = CloudItem('f', 'Sunday.png', category='images', can_copy=True, can_move=True)
    mime = CloudDragData(panel, [item])
    target = CloudItem('advent', 'Advent', folder=True, category='images', can_upload=True)
    row = QtWidgets.QTreeWidgetItem(['Advent'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, target)
    panel.tree.addTopLevelItem(row)
    panel.tree.itemAt = MagicMock(return_value=row)
    panel.upload = MagicMock()
    event = QtGui.QDropEvent(QtCore.QPointF(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    panel.tree.dropEvent(event)
    assert event.isAccepted()
    panel.upload.assert_called_once_with(mime, target)
    assert not panel.can_upload(mime, CloudItem('reader', 'Read only', folder=True, category='images'))
    panel.category = 'custom'
    assert not panel.can_upload(mime, target)


def test_download_rejects_wrong_library_even_when_called_directly(panel):
    panel.start_job = MagicMock()
    panel.download([CloudItem('f', 'song.xml', category='songs')],
                   SimpleNamespace(plugin=SimpleNamespace(name='images')))
    panel.start_job.assert_not_called()
    assert 'matching' in panel.status.text()


def test_breadcrumb_returns_to_ancestor_without_crossing_type(panel):
    panel.category = 'images'
    root = CloudItem('images', 'Images', folder=True, category='images')
    advent = CloudItem('advent', 'Advent', folder=True, category='images')
    panel.folder = CloudItem('week', 'Week one', folder=True, category='songs')
    panel.history = [root, advent]
    panel.update_breadcrumbs()
    assert [crumb.text for crumb in panel.breadcrumbs.items()] == ['Images', 'Advent', 'Week one']
    panel.browse = MagicMock()
    panel.activate_breadcrumb(1, panel.breadcrumbs.items()[1])
    panel.browse.assert_called_once_with(advent)
    assert panel.history == [root]


def test_file_import_keeps_friendly_name_and_requested_local_subfolder(tmp_path):
    plugin = MagicMock()
    plugin.name = 'images'
    target = MagicMock()
    path = tmp_path / 'Sunday.png'
    import_item(CloudItem('f', 'Sunday [123456abcdef].png', category='images'), path, plugin,
                target=target, prepared='checksum')
    plugin.media_item.validate_and_load.assert_called_once_with(
        [path], target, file_hashes={path: 'checksum'}, file_names={path: 'Sunday.png'})


def test_remote_drop_imports_into_matching_library(panel):
    view = QtWidgets.QTreeWidget()
    library = SimpleNamespace(plugin=SimpleNamespace(name='images'), list_view=view, item_class=dict, folder_class=list)
    panel.drop_views[view.viewport()] = (library, view, False, False)
    panel.download = MagicMock()
    mime = CloudDragData(panel, [CloudItem('image', 'Sunday.png', category='images')])
    event = QtGui.QDropEvent(
        QtCore.QPointF(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    assert panel.eventFilter(view.viewport(), event)
    assert event.isAccepted()
    panel.download.assert_called_once_with(list(mime.items), library, None)
    panel.drop_views.clear()
    view.deleteLater()


def test_folder_navigation_waits_for_current_listing(panel):
    panel.folder = CloudItem('root', 'Church', folder=True)
    row = MagicMock()
    row.data.return_value = CloudItem('songs', 'Songs', folder=True)
    panel.jobs['listing'] = {'kind': 'browse'}
    panel.browse = MagicMock()
    panel.activate_item(row)
    panel.browse.assert_not_called()
    assert not panel.history
    panel.jobs.clear()


def test_preview_opens_inside_application_without_external_browser(panel, monkeypatch):
    row = QtWidgets.QTreeWidgetItem(['Sunday notices'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, CloudItem(
        'f', 'Sunday notices.pdf', category='presentations', can_download=False,
        preview_url='https://another-cloud.example/view/f'))
    panel.tree.addTopLevelItem(row)
    row.setSelected(True)
    window = CloudPreviewWindow(panel)
    QtWidgets.QVBoxLayout(window.contentWidget())
    window.show = MagicMock()
    show = MagicMock(return_value=window)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.show_preview', show)
    opened = MagicMock()
    monkeypatch.setattr(QtGui.QDesktopServices, 'openUrl', opened)
    panel.update_actions()
    assert panel.preview_action.isEnabled()
    panel.open_preview()
    assert show.call_args.args[0] is panel.window()
    window.show.assert_called_once()
    assert panel.status.text() == 'Ready'
    opened.assert_not_called()
    panel.preview_windows.clear()


@pytest.mark.parametrize('writable', [True, False])
def test_opening_and_closing_view_restores_normal_footer_status(panel, monkeypatch, writable):
    from tempfile import TemporaryDirectory
    from threading import Event
    panel.folder = CloudItem('images', 'Images', folder=True, category='images', can_upload=writable)
    window = CloudPreviewWindow(panel)
    QtWidgets.QVBoxLayout(window.contentWidget())
    window.show = MagicMock()
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.show_preview', lambda *args: window)
    temporary = TemporaryDirectory()
    cancelled = Event()
    worker = SimpleNamespace(cancel=cancelled, stop=cancelled.set)
    panel.jobs['view'] = {'kind': 'preview', 'generation': panel.generation, 'context': temporary, 'worker': worker}
    panel.set_status('Opening Welcome…')
    panel.job_ready('view', (CloudItem('image', 'Welcome.png', category='images'), None, None))
    status = 'Drag-and-drop items to upload' if writable else 'Read-only'
    assert panel.status.text() == status
    window.closeWindow()
    panel.job_completed('view')
    assert panel.status.text() == status
    assert not panel.preview_windows and not Path(temporary.name).exists()


@pytest.mark.parametrize('category', ['songs', 'themes'])
@pytest.mark.parametrize('writable', [True, False])
def test_viewer_commands_use_viewed_item_and_disable_read_only_writes(panel, writable, category):
    window = CloudPreviewWindow(panel)
    QtWidgets.QVBoxLayout(window.contentWidget())
    item = CloudItem('viewed', 'Welcome.xml', category=category, can_edit=writable, can_delete=True)
    panel.add_preview_commands(window, item)
    assert window.cloud_commands['download'].text() == 'Add to Library'
    panel.download, panel.rename_item, panel.delete_items = MagicMock(), MagicMock(), MagicMock()
    panel.selected_items = MagicMock(return_value=[CloudItem('other', 'Other.xml', category='songs')])
    window.cloud_commands['download'].trigger()
    panel.download.assert_called_once_with([item])
    assert window.cloud_commands['rename'].isEnabled() == writable
    assert window.cloud_commands['delete'].isEnabled() == writable
    if not writable:
        panel.preview_command(window, 'rename')
        panel.preview_command(window, 'delete')
        panel.rename_item.assert_not_called()
        panel.delete_items.assert_not_called()
    else:
        window.cloud_commands['rename'].trigger()
        window.cloud_commands['delete'].trigger()
        panel.rename_item.assert_called_once_with(item, window.cloud_folder, window)
        panel.delete_items.assert_called_once_with([item], window)
    panel.profile = None
    panel.preview_command(window, 'download')
    assert panel.download.call_count == 1


def test_viewer_rename_keeps_original_folder_and_media_view_does_not_block_downloads(panel):
    window = CloudPreviewWindow(panel)
    window.accept = MagicMock()
    QtWidgets.QVBoxLayout(window.contentWidget())
    folder = CloudItem('original', 'Songs', folder=True, category='songs')
    panel.folder = folder
    item = CloudItem('viewed', 'Welcome.xml', category='songs', can_edit=True, can_delete=True)
    panel.add_preview_commands(window, item)
    panel.preview_windows.add(window)
    context = SimpleNamespace(preview_window=window)
    worker = MagicMock()
    panel.jobs['stream'] = {'kind': 'preview', 'context': context, 'worker': worker}
    assert not panel.busy()
    panel.cancel_previews()
    worker.cancel.set.assert_not_called()
    panel.folder = CloudItem('other', 'Images', folder=True, category='images')
    panel.request_name = MagicMock(return_value='Renamed')
    panel.start_job = MagicMock()
    window.cloud_commands['rename'].trigger()
    kind, operation = panel.start_job.call_args.args
    assert kind == 'rename'
    provider = MagicMock()
    operation(provider)
    provider.rename.assert_called_once_with(item, folder, 'Renamed')
    window.accept.assert_called_once()
    panel.jobs['download'] = {'kind': 'download'}
    panel.update_actions()
    assert not any(action.isEnabled() for action in window.cloud_commands.values())
    panel.jobs.clear()
    panel.preview_windows.clear()


def test_provider_runs_in_worker_and_delivers_on_gui_thread(panel, qtbot, monkeypatch):
    thread_ids = []
    provider = MagicMock()
    provider.type_folder.return_value = None
    monkeypatch.setitem(__import__('openlp.plugins.librarysync.lib.worker', fromlist=['PROVIDERS']).PROVIDERS,
                        'google-drive', lambda profile, cancel: provider)
    app = QtWidgets.QApplication.instance()
    if not hasattr(app, 'worker_threads'):
        app.worker_threads = {}

    def operation(*args):
        thread_ids.append(QtCore.QThread.currentThread())
        return (CloudItem('church', 'Church', folder=True), [], '')

    panel.start_job('browse', operation, False)
    qtbot.waitUntil(lambda: not panel.jobs, timeout=5000)
    qtbot.waitUntil(lambda: not app.worker_threads, timeout=5000)
    assert thread_ids and thread_ids[0] is not app.thread()
    assert panel.folder.id == 'church'
    provider.close.assert_called_once()


def test_restart_restores_saved_connection_and_account_without_prompt(panel, qtbot, monkeypatch):
    from openlp.core.common.settings import Settings
    from openlp.plugins.librarysync.lib.auth import GoogleAuth
    from openlp.plugins.librarysync.lib.worker import PROVIDERS
    from openlp.plugins.librarysync.lib.profile import validate_profile
    store = MagicMock()
    store.load.return_value = {'access_token': 'saved-test-token', 'expires_at': time.time() + 3600,
                               'refresh_token': 'saved-test-refresh'}
    provider = MagicMock()
    auth = GoogleAuth(panel.profile['installed'], store=store)

    def folder(*args):
        assert auth.access_token() == 'saved-test-token'
        return CloudItem('church', 'Church Library', folder=True)
    provider.folder.side_effect = folder
    provider.type_folder.return_value = None
    provider.list_folder.return_value = ([], '')
    monkeypatch.setitem(PROVIDERS, 'google-drive', lambda profile, cancel: provider)
    imported, opened = MagicMock(), MagicMock()
    monkeypatch.setattr(CloudLibrary, 'import_connection', imported)
    monkeypatch.setattr(QtGui.QDesktopServices, 'openUrl', opened)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.PluginManager.get_plugin_by_name', lambda name: None)
    fresh_settings = Settings(panel.plugin.settings.fileName(), QtCore.QSettings.Format.IniFormat)
    assert isinstance(fresh_settings.value('librarysync/profile'), dict)
    restored = CloudLibrary(SimpleNamespace(settings=fresh_settings), None)
    qtbot.addWidget(restored)
    restored.startup()
    qtbot.waitUntil(lambda: not restored.jobs, timeout=5000)
    assert restored.profile == validate_profile(panel.profile)
    assert restored.connected
    assert restored.import_info.isHidden()
    assert restored.connect_action.text() == 'Reconnect'
    imported.assert_not_called()
    opened.assert_not_called()
    provider.sign_in.assert_not_called()
    restored.shutdown()


@pytest.mark.parametrize('name,category,expected', [
    ('song.xml', 'songs', 'songs'), ('video.mp4', '', 'media'), ('deck.pptx', '', 'presentations'),
    ('attack.exe', 'images', ''), ('db.sqlite', 'bibles', '')])
def test_only_supported_library_formats_are_importable(name, category, expected):
    assert item_category(CloudItem('f', name, category=category)) == expected


@pytest.mark.parametrize('data', [
    b'<!DOCTYPE x [<!ENTITY ex SYSTEM "file:///etc/passwd">]><x>&ex;</x>', b'<broken>'])
def test_cloud_xml_rejects_external_entities_and_invalid_documents(data):
    with pytest.raises(SyncError):
        safe_xml(data)


def test_cloud_package_cannot_hide_multiple_xml_files(tmp_path):
    path = tmp_path / 'item.osz'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('song.xml', '<song/>')
        archive.writestr('other.xml', '<song/>')
    with pytest.raises(SyncError, match='one small XML'):
        read_xml_item(path)


def test_custom_import_preserves_title_and_credits(tmp_path):
    path = tmp_path / 'remote copy.xml'
    path.write_text('<song version="1.0"><title>Welcome</title><credit>Church</credit>'
                    '<lyrics><verse type="custom" label="1">Hello church</verse></lyrics></song>')
    plugin = MagicMock(name='custom', status=PluginStatus.Active)
    plugin.name = 'custom'
    plugin.is_active.return_value = True
    plugin.db_manager.save_object.return_value = True
    import_item(CloudItem('custom', path.name, category='custom'), path, plugin)
    item = plugin.db_manager.save_object.call_args.args[0]
    assert item.title == 'Welcome'
    assert item.credits == 'Church'
    assert 'Hello church' in item.text
    plugin.media_item.on_search_text_button_clicked.assert_not_called()
    plugin.media_item.list_view.addItem.assert_called_once()


def test_remote_filename_cannot_escape_storage():
    assert safe_name('../../outside.xml') == 'outside.xml'
    assert safe_name('..\\..\\outside.xml') == 'outside.xml'


def test_worker_error_never_exposes_credentials(qapp, monkeypatch):
    from openlp.plugins.librarysync.lib.worker import PROVIDERS
    monkeypatch.setitem(PROVIDERS, 'google-drive', lambda profile, cancel: MagicMock())
    worker = SyncWorker('job', {'provider': 'google-drive'}, MagicMock(side_effect=RuntimeError('private-token')))
    errors = []
    worker.failed.connect(lambda job, message: errors.append(message))
    worker.start()
    assert len(errors) == 1 and 'private-token' not in errors[0]


def test_worker_stop_finishes_without_publishing(qapp, monkeypatch):
    from openlp.plugins.librarysync.lib.worker import PROVIDERS
    provider = MagicMock()
    monkeypatch.setitem(PROVIDERS, 'google-drive', lambda profile, cancel: provider)
    worker = SyncWorker('job', {'provider': 'google-drive'}, lambda *args: 'result')
    ready, completed = [], []
    worker.ready.connect(lambda *args: ready.append(args))
    worker.completed.connect(completed.append)
    worker.stop()
    worker.start()
    assert worker.cancel.is_set()
    assert not ready
    assert completed == ['job']
    provider.close.assert_called_once()


def test_file_import_does_not_report_unsaved_file_as_added(tmp_path):
    plugin = MagicMock()
    plugin.name = 'images'
    plugin.media_item.validate_and_load.return_value = []
    with pytest.raises(SyncError, match='could not be saved'):
        import_item(CloudItem('image', 'Sunday.png', category='images'), tmp_path / 'Sunday.png', plugin)


def test_song_round_trip_uses_native_export_and_real_database(settings, tmp_path, qtbot):
    from openlp.core.db.manager import DBManager
    from openlp.plugins.songs.lib.db import Song, init_schema
    from openlp.plugins.songs.lib.openlyricsxml import OpenLyrics
    from tests.utils.constants import RESOURCE_PATH
    manager = DBManager('songs', init_schema, db_url='sqlite:///' + str(tmp_path / 'songs.sqlite'))
    try:
        source = RESOURCE_PATH / 'songs' / 'openlyrics' / 'Amazing Grace.xml'
        original = OpenLyrics(manager).xml_to_song(source.read_text(encoding='utf-8'))
        from openlp.plugins.songs.lib.mediaitem import SongListWidget
        view = SongListWidget()
        qtbot.addWidget(view)
        view.addItem(SongListWidget.make_item(original.title, original.song_author_display, original.id))
        view.item(0).setSelected(True)
        plugin = SimpleNamespace(name='songs', manager=manager, is_active=lambda: True)
        library = SimpleNamespace(plugin=plugin, list_view=view, get_library_tab_icon=lambda: QtGui.QIcon(),
                                  on_search_text_button_clicked=MagicMock())
        plugin.media_item = library
        [(category, path, contents, title)] = prepare_upload(ItemDragData(library=library), tmp_path / 'upload')
        write_upload(path, contents)
        import_item(CloudItem('song', path.name, category=category, title='A copied song'), path, plugin,
                    prepared=read_xml_item(path))
        imported = manager.get_all_objects(Song)[-1]
        assert imported.id != original.id
        assert imported.title == 'A copied song'
        assert imported.lyrics == original.lyrics
        assert imported.verse_order == original.verse_order
        assert imported.copyright == original.copyright
        assert original.sort_key and imported.sort_key
        assert ([author.display_name for author in imported.authors]
                == [author.display_name for author in original.authors])
        library.on_search_text_button_clicked.assert_not_called()
        assert view.count() == 2
        assert view.item(0).data(QtCore.Qt.ItemDataRole.UserRole) == imported.id
        assert view.item(1).data(QtCore.Qt.ItemDataRole.UserRole) == original.id
        import_item(CloudItem('song', path.name, category=category, title=original.title), path, plugin,
                    prepared=read_xml_item(path), overwrite=original.id)
        assert view.count() == 2
        assert len(manager.get_all_objects(Song)) == 2
        assert original.song_author_display == imported.song_author_display
        from openlp.plugins.songs.lib.mediaitem import SongMediaItem
        library.save_auto_select_id = MagicMock()
        library.auto_select_id = -1
        SongMediaItem.display_results_song(library, manager.get_all_objects(Song))
        assert view.count() == 2
    finally:
        manager.finalise()


def test_cloud_lists_show_metadata_and_keep_downloads_in_sorted_position(panel, qtbot, monkeypatch):
    from PySide6 import QtTest
    from openlp.core.widgets.views import FileTreeWidgetItem
    panel.resize(850, 650)
    panel.show()
    zone = QtCore.QTimeZone(b'Australia/Sydney')
    monkeypatch.setattr(QtCore.QTimeZone, 'systemTimeZone', lambda: zone)
    folder = CloudItem('songs', 'Songs', folder=True, category='songs', can_upload=True)
    items = [CloudItem('a', 'Zeta.xml', category='songs', size=1024, modified='2026-10-08T01:00:00Z'),
             CloudItem('b', 'Alpha.xml', category='songs', size=4096, modified='2026-10-09T01:00:00Z')]
    panel.jobs['listing'] = {'kind': 'browse', 'generation': panel.generation, 'context': False}
    panel.job_ready('listing', (folder, items, ''))
    panel.jobs.clear()
    panel.update_actions()
    QtWidgets.QApplication.processEvents()
    assert not panel.tree.header().isHidden()
    assert panel.tree.header().geometry().top() >= 0
    assert panel.tree.viewport().geometry().top() >= panel.tree.header().height()
    assert [panel.tree.topLevelItem(i).text(0) for i in range(2)] == ['Alpha', 'Zeta']
    assert panel.tree.topLevelItem(0).text(1) == '4 KB'
    from openlp.plugins.librarysync.lib.preview import cloud_metadata
    assert panel.tree.topLevelItem(0).text(2) == cloud_metadata(items[1])['Modified']
    assert not panel.folder_action.isEnabled()
    header = panel.tree.header()
    point = QtCore.QPoint(header.sectionViewportPosition(2) + header.sectionSize(2) // 2, header.height() // 2)
    QtTest.QTest.mouseClick(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert panel.tree.sortColumn() == 2
    assert [panel.tree.topLevelItem(i).text(0) for i in range(2)] == ['Zeta', 'Alpha']
    QtTest.QTest.mouseClick(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert [panel.tree.topLevelItem(i).text(0) for i in range(2)] == ['Alpha', 'Zeta']
    panel.tree.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
    panel.tree.addTopLevelItem(FileTreeWidgetItem(['Middle']))
    assert [panel.tree.topLevelItem(i).text(0) for i in range(3)] == ['Alpha', 'Middle', 'Zeta']
    panel.search.setText('middle')
    assert [panel.tree.isRowHidden(i) for i in range(3)] == [True, False, True]
    panel.search.clear()
    assert not any(panel.tree.isRowHidden(i) for i in range(3))


def test_cloud_write_context_actions_follow_item_permissions(panel):
    folder = CloudItem('songs', 'Songs', folder=True, category='songs', can_upload=True)
    item = CloudItem('song', 'Welcome.xml', category='songs')
    panel.jobs['listing'] = {'kind': 'browse', 'generation': panel.generation, 'context': False}
    panel.job_ready('listing', (folder, [item], ''))
    panel.jobs.clear()
    row = panel.tree.topLevelItem(0)
    row.setSelected(True)
    panel.update_actions()
    assert not panel.rename_action.isEnabled() and not panel.delete_action.isEnabled()
    from dataclasses import replace
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, replace(item, can_edit=True, can_delete=True))
    panel.update_actions()
    assert panel.rename_action.isEnabled() and panel.delete_action.isEnabled()


@pytest.mark.parametrize('writable,can_delete', [(True, True), (True, False), (False, False)])
def test_theme_context_menu_includes_write_actions_with_item_permissions(panel, monkeypatch, writable, can_delete):
    panel.start_job = MagicMock()
    panel.sections.setCurrentIndex(5)
    assert panel.category == 'themes'
    item = CloudItem('theme', 'Welcome.otz', category='themes', can_edit=writable, can_delete=can_delete)
    row = QtWidgets.QTreeWidgetItem(['Welcome'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
    panel.tree.addTopLevelItem(row)
    panel.tree.itemAt = MagicMock(return_value=row)
    menu = MagicMock()
    monkeypatch.setattr(QtWidgets, 'QMenu', MagicMock(return_value=menu))
    panel.context_menu(QtCore.QPoint(10, 10))
    assert [call.args[0] for call in menu.addAction.call_args_list] == [
        panel.preview_action, panel.download_action, panel.rename_action, panel.delete_action]
    assert panel.rename_action.isEnabled() == writable
    assert panel.delete_action.isEnabled() == (writable and can_delete)


@pytest.mark.parametrize('operation', ['rename', 'folder'])
@pytest.mark.parametrize('accepted', [True, False])
def test_cloud_names_use_content_dialog_and_cancel_without_writing(panel, monkeypatch, operation, accepted):
    from openlp.core.widgets.views import FileTreeWidgetItem
    folder = CloudItem('images', 'Images', folder=True, category='images', can_upload=True)
    item = CloudItem('image', 'Welcome.png', category='images', can_edit=True)
    panel.folder, panel.category = folder, 'images'
    row = FileTreeWidgetItem(['Welcome'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, item)
    panel.tree.addTopLevelItem(row)
    row.setSelected(True)
    panel.update_actions()
    panel.start_job = MagicMock()

    def respond(dialog):
        assert isinstance(dialog, QtWidgets.fluentqt.ContentDialog)
        assert dialog.primaryButtonText() == ('Rename' if operation == 'rename' else 'Create')
        assert dialog.closeButtonText() == 'Cancel'
        field = dialog.content().findChild(QtWidgets.QLineEdit)
        assert field.text() == ('Welcome' if operation == 'rename' else '')
        field.setText('New name')
        return dialog.ResultPrimary if accepted else dialog.ResultNone

    monkeypatch.setattr(QtWidgets.fluentqt.ContentDialog, 'exec', respond)
    panel.rename_selected() if operation == 'rename' else panel.create_folder()
    if accepted:
        kind, run = panel.start_job.call_args.args
        assert kind == operation
        provider = MagicMock()
        run(provider)
        if operation == 'rename':
            provider.rename.assert_called_once_with(item, folder, 'New name')
        else:
            provider.create_folder.assert_called_once_with(folder, 'images', 'New name')
    else:
        panel.start_job.assert_not_called()


def test_connection_menu_order_icons_and_separator(panel, monkeypatch):
    def inspect(menu, position):
        actions = menu.actions()
        assert [action.text() for action in actions] == [
            'Open storage', '', 'Import connection…', 'Export connection…', '',
            'Set up connection…', 'Disconnect…']
        assert actions[1].isSeparator() and actions[4].isSeparator()
        assert [action.icon().name() for action in actions if not action.isSeparator()] == [
            'ic_fluent_folder_open_24_regular', 'ic_fluent_arrow_import_24_regular',
            'ic_fluent_arrow_export_24_regular',
            'ic_fluent_add_24_regular', 'ic_fluent_plug_disconnected_24_regular']
    monkeypatch.setattr(QtWidgets.QMenu, 'exec', inspect)
    panel.configure()


@pytest.mark.parametrize('provider', ['google-drive', 'local-cloud'])
def test_open_storage_menu_uses_selected_root_and_system_launcher(panel, monkeypatch, tmp_path, provider):
    opened = MagicMock(return_value=True)
    monkeypatch.setattr(QtGui.QDesktopServices, 'openUrl', opened)
    if provider == 'local-cloud':
        path = tmp_path / 'Church Library #1'
        panel.set_profile({'version': 1, 'provider': provider, 'name': 'Local storage', 'path': str(path)})
        expected = QtCore.QUrl.fromLocalFile(str(path))
    else:
        profile = dict(panel.profile, folders=[{'id': 'first', 'name': 'First'},
                                               {'id': 'second', 'name': 'Second', 'resource_key': 'link-key'}])
        panel.set_profile(profile)
        with QtCore.QSignalBlocker(panel.roots):
            panel.roots.setCurrentIndex(1)
        expected = QtCore.QUrl('https://drive.google.com/drive/folders/second?resourcekey=link-key')

    def inspect(menu, position):
        storage = menu.actions()[0]
        assert storage.text() == 'Open storage' and storage.isEnabled()
        storage.trigger()

    monkeypatch.setattr(QtWidgets.QMenu, 'exec', inspect)
    assert not panel.connected
    panel.configure()
    opened.assert_called_once_with(expected)


def test_open_storage_without_resource_key_and_launcher_failure(panel, monkeypatch):
    opened = MagicMock(return_value=False)
    monkeypatch.setattr(QtGui.QDesktopServices, 'openUrl', opened)
    panel.open_storage()
    opened.assert_called_once_with(QtCore.QUrl('https://drive.google.com/drive/folders/church'))
    assert panel.status.text() == 'Couldn’t open storage'
    assert panel._status_theme.theme_tokens().colors.systemCritical.name() in panel.status.styleSheet()


def test_open_storage_requires_a_configured_root(panel, monkeypatch):
    opened = MagicMock()
    monkeypatch.setattr(QtGui.QDesktopServices, 'openUrl', opened)
    with QtCore.QSignalBlocker(panel.roots):
        panel.roots.clear()
    panel.open_storage()
    panel.profile = None

    def inspect(menu, position):
        assert not menu.actions()[0].isEnabled()

    monkeypatch.setattr(QtWidgets.QMenu, 'exec', inspect)
    panel.configure()
    panel.open_storage()
    opened.assert_not_called()


def test_upload_checks_duplicate_and_only_overwrites_after_confirmation(panel, tmp_path):
    from tempfile import TemporaryDirectory
    existing = CloudItem('song', 'Welcome.xml', category='songs', can_edit=True, version='3')
    source = ('songs', tmp_path / 'Welcome.xml', '<song/>', 'Welcome')
    temporary = TemporaryDirectory()
    context = {'folder': CloudItem('songs', 'Songs', folder=True, category='songs', can_upload=True),
               'temporary': temporary, 'copy': False}
    panel.confirm_overwrite = MagicMock(return_value=True)
    panel.start_job = MagicMock()
    panel.jobs['check'] = {'kind': 'prepare-upload', 'context': context, 'generation': panel.generation}
    panel.job_ready('check', [(source, existing)])
    panel.confirm_overwrite.assert_not_called()
    panel.job_completed('check')
    panel.confirm_overwrite.assert_called_once_with('Welcome', 'Cloud Library')
    kind, operation, supplied = panel.start_job.call_args.args
    assert kind == 'upload'
    provider = MagicMock()
    from threading import Event
    operation(provider, Event(), MagicMock())
    assert provider.upload.call_args.kwargs['overwrite'] is existing
    temporary.cleanup()


def test_download_declined_overwrite_preserves_local_item_and_starts_no_job(panel, monkeypatch):
    plugin = SimpleNamespace(is_active=lambda: True)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.PluginManager.get_plugin_by_name', lambda name: plugin)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.local_item', lambda *args: SimpleNamespace(id=42))
    panel.confirm_overwrite = MagicMock(return_value=False)
    panel.start_job = MagicMock()
    panel.download([CloudItem('song', 'Welcome.xml', category='songs')])
    panel.confirm_overwrite.assert_called_once_with('Welcome', 'local Library')
    panel.start_job.assert_not_called()


def test_cancelling_during_overwrite_prompt_does_not_launch_upload(panel, tmp_path):
    from tempfile import TemporaryDirectory
    from threading import Event
    temporary = TemporaryDirectory()
    worker = SimpleNamespace(cancel=Event())
    source = ('songs', tmp_path / 'Welcome.xml', '<song/>', 'Welcome')
    existing = CloudItem('song', 'Welcome.xml', category='songs', can_edit=True)
    context = {'folder': CloudItem('songs', 'Songs', folder=True, category='songs', can_upload=True),
               'temporary': temporary, 'copy': False}
    panel.jobs['check'] = {'kind': 'prepare-upload', 'context': context, 'generation': panel.generation,
                           'worker': worker}
    panel.job_ready('check', [(source, existing)])
    panel.run_upload = MagicMock()

    def answer(*args):
        worker.cancel.set()
        return True
    panel.confirm_overwrite = answer
    panel.job_completed('check')
    panel.run_upload.assert_not_called()
    assert not Path(temporary.name).exists()


def test_cloud_move_collision_cannot_overwrite_without_permission_to_remove_original(panel):
    from tempfile import TemporaryDirectory
    temporary = TemporaryDirectory()
    source = CloudItem('source', 'Sunday.png', category='images', can_move=True, can_delete=False)
    existing = CloudItem('other', 'Sunday.png', category='images', can_edit=True)
    context = {'folder': CloudItem('advent', 'Advent', folder=True, category='images', can_upload=True),
               'temporary': temporary, 'copy': True}
    panel.jobs['check'] = {'kind': 'prepare-upload', 'context': context, 'generation': panel.generation}
    panel.job_ready('check', [(source, existing)])
    panel.run_upload = MagicMock()
    panel.confirm_overwrite = MagicMock(return_value=True)
    panel.job_completed('check')
    panel.run_upload.assert_not_called()
    panel.confirm_overwrite.assert_not_called()
    assert not Path(temporary.name).exists()


def test_cloud_image_view_loads_original_instead_of_drive_thumbnail(panel, qtbot, tmp_path, monkeypatch):
    from threading import Event
    from openlp.plugins.librarysync.lib.preview import show_preview

    source = tmp_path / 'original.png'
    image = QtGui.QImage(1920, 1080, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('blue'))
    image.save(str(source))
    monkeypatch.setattr('openlp.plugins.librarysync.lib.cache.AppLocation.get_directory', lambda kind: tmp_path)
    item = CloudItem('image', 'Welcome.png', category='images', size=source.stat().st_size, version='1',
                     thumbnail_url='https://drive.google.com/thumbnail')
    panel.selected_items = MagicMock(return_value=[item])
    panel.start_job = MagicMock()
    panel.open_preview()
    kind, operation, temporary = panel.start_job.call_args.args
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    provider.preview.return_value = ('image', b'low resolution thumbnail')
    provider.download.side_effect = lambda item, destination, *args: destination.write_bytes(source.read_bytes())
    try:
        result_item, path, prepared, cached = operation(provider, Event(), MagicMock(), MagicMock(), MagicMock())
        assert kind == 'preview' and not cached
        second = operation(provider, Event(), MagicMock(), MagicMock(), MagicMock())
        assert second[3]
        provider.preview.assert_not_called()
        provider.download.assert_called_once()
        window = show_preview(panel, result_item, path, prepared)
        qtbot.addWidget(window)
        assert window.image.size() == image.size()
        assert window.metadata['Resolution'].text() == '1920 × 1080'
        assert 'Preview resolution' not in window.metadata
        window.reject()
    finally:
        temporary.cleanup()


def test_cloud_presentation_downloads_deck_and_reuses_rendered_pdf(panel, monkeypatch, tmp_path):
    from threading import Event
    monkeypatch.setattr('openlp.plugins.librarysync.lib.cache.AppLocation.get_directory', lambda kind: tmp_path)
    controller = SimpleNamespace(name='Keynote', keynote_app=None)
    plugin = SimpleNamespace(is_active=lambda: True, media_item=SimpleNamespace(
        find_controller_by_type=lambda path: 'Keynote', controllers={'Keynote': controller}))
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.PluginManager.get_plugin_by_name', lambda name: plugin)
    item = CloudItem('deck', 'Welcome.pptx', category='presentations', size=4, version='1')
    panel.selected_items = MagicMock(return_value=[item])
    panel.start_job = MagicMock()
    panel.open_preview()
    kind, operation, temporary = panel.start_job.call_args.args
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    provider.download.side_effect = lambda item, destination, *args: destination.write_bytes(b'deck')

    def convert(name, source, **kwargs):
        path = source.with_suffix('.pdf')
        path.write_bytes(b'%PDF-1.4 rendered slides')
        return path

    export = MagicMock(side_effect=convert)
    monkeypatch.setattr('openlp.plugins.presentations.lib.pdfexport.export_to_pdf', export)
    try:
        result = operation(provider, Event(), MagicMock(), MagicMock(), MagicMock())
        assert kind == 'preview' and result[2].suffix == '.pdf'
        assert result[2].read_bytes() == b'%PDF-1.4 rendered slides'
        result = operation(provider, Event(), MagicMock(), MagicMock(), MagicMock())
        assert result[3] and result[2].read_bytes() == b'%PDF-1.4 rendered slides'
        provider.download.assert_called_once()
        provider.preview.assert_not_called()
        export.assert_called_once()
    finally:
        temporary.cleanup()


@pytest.mark.parametrize('later_page', [False, True])
def test_view_refreshes_outdated_listing_then_opens_current_version(panel, later_page):
    folder = CloudItem('songs', 'Songs', folder=True, category='songs')
    old = CloudItem('song', 'Welcome.xml', category='songs', version='1')
    current = CloudItem('song', 'Welcome.xml', category='songs', version='2')
    row = QtWidgets.QTreeWidgetItem(['Welcome'])
    row.setData(0, QtCore.Qt.ItemDataRole.UserRole, old)
    panel.tree.addTopLevelItem(row)
    row.setSelected(True)
    panel.out_of_date = True
    panel.refresh, panel.load_more, panel.start_job = MagicMock(), MagicMock(), MagicMock()
    panel.open_preview()
    panel.refresh.assert_called_once()
    panel.start_job.assert_not_called()
    assert panel.pending_view == old.id
    panel.jobs['refresh'] = {'kind': 'browse', 'generation': panel.generation, 'context': False}
    panel.job_ready('refresh', (folder, [] if later_page else [current], 'second' if later_page else '', False,
                                ('fresh-cursor', False)))
    panel.job_completed('refresh')
    if later_page:
        assert panel.pending_view == old.id
        panel.load_more.assert_called_once()
        panel.start_job.assert_not_called()
        panel.jobs['page'] = {'kind': 'browse', 'generation': panel.generation, 'context': True}
        panel.job_ready('page', (folder, [current], '', False, ('fresh-cursor', False)))
        panel.job_completed('page')
    assert panel.pending_view is None and not panel.out_of_date
    assert panel.selected_items() == [current]
    kind, operation, temporary = panel.start_job.call_args.args
    assert kind == 'preview' and temporary.refreshed and temporary.view_id == current.id
    temporary.cleanup()


@pytest.mark.parametrize('refreshed', [False, True])
def test_view_failure_refreshes_and_retries_only_once(panel, refreshed):
    from tempfile import TemporaryDirectory
    temporary = TemporaryDirectory()
    temporary.view_id, temporary.refreshed = 'song', refreshed
    panel.jobs['view'] = {'kind': 'preview', 'generation': panel.generation, 'context': temporary}
    panel.refresh = MagicMock()
    panel.set_status('Opening Welcome…')
    panel.job_failed('view', 'This item changed in the cloud')
    if not refreshed:
        assert panel.status.text() == 'Opening Welcome…'
    else:
        assert panel.status.text() == 'This item changed in the cloud'
        assert panel.status.styleSheet()
    panel.job_completed('view')
    if not refreshed:
        panel.refresh.assert_called_once()
        assert panel.pending_view == 'song'
    else:
        panel.refresh.assert_not_called()
    assert not Path(temporary.name).exists()


def test_updated_column_can_be_resized_when_cloud_list_overflows(panel, qtbot):
    panel.connected = True
    panel.update_actions()
    from PySide6 import QtTest
    from openlp.plugins.librarysync.lib.preview import format_local_time

    panel.resize(650, 500)
    panel.show()
    qtbot.wait(20)
    header = panel.tree.header()
    date = format_local_time(QtCore.QDateTime.currentDateTimeUtc().toString(QtCore.Qt.DateFormat.ISODate))
    panel.tree.addTopLevelItem(QtWidgets.QTreeWidgetItem(['Welcome', '700 KB', date]))
    qtbot.wait(20)
    assert header.sectionSize(2) > panel.tree.fontMetrics().horizontalAdvance(date)
    assert header.sectionResizeMode(2) == QtWidgets.QHeaderView.ResizeMode.Interactive
    header.resizeSection(2, 600)
    qtbot.wait(20)
    scrollbar = panel.tree.horizontalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    qtbot.wait(20)
    edge = QtCore.QPoint(header.sectionViewportPosition(2) + header.sectionSize(2) - 2, header.height() // 2)
    assert header.viewport().rect().contains(edge)
    end = edge - QtCore.QPoint(40, 0)
    QtTest.QTest.mousePress(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=edge)
    QtTest.QTest.mouseMove(header.viewport(), end, 20)
    QtTest.QTest.mouseRelease(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=end)
    qtbot.wait(20)
    assert header.sectionSize(2) < 600
    resized = header.sectionSize(2)
    panel.resize(750, 500)
    qtbot.wait(20)
    assert header.sectionSize(2) == resized


@pytest.mark.parametrize('column', [1, 2])
def test_cloud_metadata_resize_handle_follows_mouse_without_shifting_name(panel, qtbot, column):
    panel.connected = True
    panel.update_actions()
    from PySide6 import QtTest

    panel.resize(850, 500)
    panel.show()
    qtbot.wait(20)
    header = panel.tree.header()
    header.resizeSection(column, 160)
    qtbot.wait(20)
    name_width = header.sectionSize(0)
    original = header.sectionSize(column)
    edge = QtCore.QPoint(header.sectionViewportPosition(column) + original - 2, header.height() // 2)
    QtTest.QTest.mousePress(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=edge)
    for delta in (10, 20, 40):
        position = edge - QtCore.QPoint(delta, 0)
        QtTest.QTest.mouseMove(header.viewport(), position, 20)
        assert header.sectionSize(0) == name_width
        assert header.sectionSize(column) == original - delta
        assert header.sectionViewportPosition(column) + header.sectionSize(column) - 2 == position.x()
    QtTest.QTest.mouseRelease(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position)
    assert header.sectionSize(column) == original - 40


@pytest.fixture
def persistent_cache(panel, tmp_path, monkeypatch):
    from openlp.plugins.librarysync.lib.cache import CloudCache
    monkeypatch.setattr('openlp.plugins.librarysync.lib.cache.AppLocation.get_directory', lambda kind: tmp_path)
    cache = CloudCache(panel.profile, 'account')
    folder = CloudItem('songs', 'Songs', folder=True, category='songs', can_upload=True, drive_id='library-drive')
    item = CloudItem('song', 'Welcome.xml', category='songs', version='1', can_edit=True, can_delete=True)
    cache.save_listing('songs', 'church', (folder, [item], ''), 'baseline')
    cache.save_listing('songs', 'songs', (folder, [item], ''), 'baseline')
    return cache, folder, item


def test_persistent_listing_is_shown_after_restart_without_reloading_drive(panel, persistent_cache, qtbot, monkeypatch):
    from openlp.plugins.librarysync.lib.worker import PROVIDERS
    cache, folder, item = persistent_cache
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    monkeypatch.setitem(PROVIDERS, 'google-drive', lambda profile, cancel: provider)
    monkeypatch.setattr(panel, 'install_drop_targets', MagicMock())
    panel.startup()
    qtbot.waitUntil(lambda: not panel.jobs, timeout=5000)
    assert panel.folder == folder and panel.tree.topLevelItemCount() == 1
    assert panel.tree.topLevelItem(0).text(0) == 'Welcome'
    assert panel.cached_listing and panel.change_token == 'baseline'
    assert 'Cached' in panel.status.text()
    provider.folder.assert_not_called()
    provider.list_folder.assert_not_called()
    provider.change_token.assert_not_called()
    provider.changes.assert_not_called()


def test_refresh_bypasses_cache_and_captures_change_baseline_before_listing(panel, persistent_cache):
    from threading import Event
    cache, folder, item = persistent_cache
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    provider.change_token.return_value = 'before-listing'
    provider.folder.return_value = CloudItem('church', 'Organisation', folder=True)
    provider.type_folder.return_value = folder
    provider.list_folder.return_value = ([item], '')
    panel.start_job = MagicMock()
    panel.refresh()
    operation = panel.start_job.call_args.args[1]
    result = operation(provider, Event(), MagicMock(), MagicMock(), MagicMock())
    assert not result[3]
    assert result[4] == ('before-listing', False)
    calls = [call[0] for call in provider.mock_calls]
    assert calls.index('change_token') < calls.index('list_folder')
    assert cache.listing('songs', 'church')[-2:] == ('before-listing', False)


@pytest.mark.parametrize('change,expected', [
    (('unrelated', ('elsewhere',), False), False), (('song', (), False), True),
    (('new-song', ('songs',), False), True), (('church', (), False), True), (('', (), True), True),
    (('', (), True, 'other-drive'), False), (('', (), True, 'library-drive'), True)])
def test_visible_poll_marks_relevant_changes_out_of_date_and_persists_cursor(
        panel, persistent_cache, qtbot, change, expected):
    from threading import Event
    from openlp.plugins.librarysync.lib.provider import CloudChange
    cache, folder, item = persistent_cache
    panel.jobs['snapshot'] = {'kind': 'browse', 'context': False, 'generation': panel.generation}
    panel.job_ready('snapshot', (folder, [item], '', True, ('baseline', False)))
    panel.jobs.clear()
    panel.tree.topLevelItem(0).setSelected(True)
    panel.start_job = MagicMock()
    panel.show()
    qtbot.wait(20)
    panel.start_job.reset_mock()
    panel.poll_changes()
    kind, operation = panel.start_job.call_args.args
    assert kind == 'changes'
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    provider.changes.return_value = ([CloudChange(*change)], 'next-cursor')
    result = operation(provider, Event())
    assert result == ('next-cursor', expected)
    provider.list_folder.assert_not_called()
    panel.jobs['poll'] = {'kind': 'changes', 'context': None, 'generation': panel.generation}
    panel.job_ready('poll', result)
    panel.jobs.clear()
    panel.update_actions()
    assert panel.out_of_date == expected
    assert panel.rename_action.isEnabled() == (not expected)
    assert panel.preview_action.isEnabled()
    assert ('Out of date' in panel.status.text()) == expected
    assert bool(panel.status.styleSheet()) == expected
    assert cache.listing('songs', 'church')[-2:] == ('next-cursor', expected)
    if expected:
        panel.set_status('Viewing Welcome')
        assert 'Out of date' in panel.status.text()


def test_poll_stops_when_hidden_and_failure_keeps_cached_view_available(panel, persistent_cache, qtbot):
    cache, folder, item = persistent_cache
    panel.jobs['snapshot'] = {'kind': 'browse', 'context': False, 'generation': panel.generation}
    panel.job_ready('snapshot', (folder, [item], '', True, ('baseline', False)))
    panel.jobs.clear()
    panel.tree.topLevelItem(0).setSelected(True)
    panel.start_job = MagicMock()
    panel.poll_changes()
    panel.start_job.assert_not_called()
    panel.show()
    qtbot.wait(20)
    worker = MagicMock()
    panel.jobs['poll'] = {'kind': 'changes', 'context': None, 'generation': panel.generation, 'worker': worker}
    panel.job_failed('poll', 'No connection')
    panel.jobs.clear()
    panel.update_actions()
    assert panel.tree.topLevelItemCount() == 1
    assert panel.preview_action.isEnabled() and not panel.rename_action.isEnabled()
    assert panel.status.text() == 'Cached · Couldn’t check for updates'
    assert 'No connection' in panel.status.toolTip()
    panel.jobs['poll'] = {'kind': 'changes', 'worker': worker}
    panel.hide()
    assert not panel.change_timer.isActive()
    worker.stop.assert_called_once()
    panel.jobs.clear()
    panel.start_job.reset_mock()
    panel.poll_changes()
    panel.start_job.assert_not_called()


def test_mutation_invalidates_disk_listing_even_after_partial_failure(panel, persistent_cache, monkeypatch):
    cache, folder, item = persistent_cache
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.run_thread', MagicMock())
    provider = MagicMock()
    provider.cache_account.return_value = 'account'

    def partial_operation(*args):
        raise SyncError('One of the items changed')
    panel.cache[('songs', 'church')] = (time.monotonic(), (folder, [item], ''))
    panel.start_job('delete', partial_operation)
    worker = next(iter(panel.jobs.values()))['worker']
    with pytest.raises(SyncError):
        worker.operation(provider)
    assert cache.listing('songs', 'church') is None
    job_id = next(iter(panel.jobs))
    panel.jobs[job_id]['failed'] = True
    panel.job_completed(job_id)
    assert not panel.cache


def test_disconnect_clears_only_signed_in_accounts_cache(panel, persistent_cache, monkeypatch):
    cache, folder, item = persistent_cache
    panel.connected = True
    monkeypatch.setattr(QtWidgets.fluentqt.ContentDialog, 'exec', lambda dialog: dialog.ResultPrimary)
    panel.start_job = MagicMock()
    panel.disconnect()
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    panel.start_job.call_args.args[1](provider)
    provider.disconnect.assert_called_once()
    assert cache.listing('songs', 'church') is None


def test_loading_more_preserves_cursor_so_changes_to_earlier_pages_are_not_lost(panel, persistent_cache):
    from threading import Event
    cache, folder, item = persistent_cache
    panel.folder, panel.change_token, panel.out_of_date = folder, 'earlier-page-baseline', True
    panel.start_job = MagicMock()
    panel.browse(folder, 'page-two', force=True)
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    provider.list_folder.return_value = ([], '')
    result = panel.start_job.call_args.args[1](provider, Event(), MagicMock(), MagicMock(), MagicMock())
    provider.change_token.assert_not_called()
    assert result[4] == ('earlier-page-baseline', True)


def test_poll_for_an_old_folder_cannot_overwrite_current_status(panel, persistent_cache):
    cache, folder, item = persistent_cache
    panel.jobs['old-poll'] = {'kind': 'changes', 'generation': panel.generation, 'context': None}
    panel.generation += 1
    panel.set_status('Current folder')
    panel.job_ready('old-poll', ('next', True))
    assert not panel.out_of_date and panel.status.text() == 'Current folder'
    panel.jobs.clear()


def test_change_poll_can_run_while_a_media_view_stream_is_open(panel, persistent_cache, qtbot):
    cache, folder, item = persistent_cache
    panel.folder, panel.change_token = folder, 'baseline'
    panel.start_job = MagicMock()
    panel.show()
    qtbot.wait(20)
    panel.start_job.reset_mock()
    panel.jobs['stream'] = {'kind': 'preview', 'context': SimpleNamespace(preview_window=QtWidgets.QWidget()),
                            'worker': MagicMock()}
    panel.poll_changes()
    assert panel.start_job.call_args.args[0] == 'changes'
    panel.jobs.clear()


def test_setup_connection_checks_existing_name_before_saving(panel, monkeypatch):
    wizard = MagicMock()
    wizard.exec.return_value = QtWidgets.QDialog.DialogCode.Rejected
    factory = MagicMock(return_value=wizard)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.ConnectionWizard', factory)
    panel.setup_connection()
    factory.assert_called_once_with(panel, existing_names=['Church Library'])
    assert panel.profile['name'] == 'Church Library'


@pytest.mark.parametrize('accepted', [False, True])
def test_disconnect_confirms_with_content_dialog_before_starting(panel, monkeypatch, accepted):
    panel.connected = True
    panel.start_job = MagicMock()

    def respond(dialog):
        assert isinstance(dialog, QtWidgets.fluentqt.ContentDialog)
        assert dialog.title() == 'Disconnect connection?'
        assert dialog.primaryButtonText() == 'Disconnect'
        assert dialog.closeButtonText() == 'Cancel'
        assert dialog.defaultButton() == QtWidgets.fluentqt.ContentDialogButton.Close
        assert 'Church Library' in dialog.content().text()
        assert 'library files will be kept' in dialog.content().text()
        panel.start_job.assert_not_called()
        return dialog.ResultPrimary if accepted else dialog.ResultNone

    monkeypatch.setattr(QtWidgets.fluentqt.ContentDialog, 'exec', respond)
    panel.disconnect()
    if accepted:
        assert panel.start_job.call_args.args[0] == 'disconnect'
    else:
        panel.start_job.assert_not_called()
        assert panel.connected


def test_connection_menu_actions_disable_after_disconnect_and_reenable_after_reconnect(panel, monkeypatch):
    def inspect(menu, position):
        actions = menu.actions()
        assert actions[0].isEnabled()
        assert actions[3].isEnabled() == panel.connected
        assert actions[6].isEnabled() == panel.connected

    monkeypatch.setattr(QtWidgets.QMenu, 'exec', inspect)
    panel.connected = True
    panel.update_actions()
    assert all(tree.isEnabled() for tree in panel.trees.values())
    assert panel.search.isEnabled()
    panel.configure()
    panel.jobs['disconnect'] = {'kind': 'disconnect', 'generation': panel.generation}
    panel.job_completed('disconnect')
    assert not panel.connected
    assert all(not tree.isEnabled() for tree in panel.trees.values())
    assert not panel.search.isEnabled()
    assert panel.profile
    panel.configure()
    panel.jobs['browse'] = {'kind': 'browse', 'generation': panel.generation, 'context': None}
    panel.job_ready('browse', (CloudItem('church', 'Church Library', folder=True), [], ''))
    panel.job_completed('browse')
    assert panel.connected
    assert all(tree.isEnabled() for tree in panel.trees.values())
    assert panel.search.isEnabled()
    panel.configure()


def test_disconnected_handlers_do_not_export_or_prompt(panel, monkeypatch):
    dialog = MagicMock()
    save = MagicMock()
    monkeypatch.setattr(QtWidgets.fluentqt.ContentDialog, 'exec', dialog)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.FileDialog.getSaveFileName', save)
    panel.start_job = MagicMock()
    panel.disconnect()
    panel.export_connection()
    dialog.assert_not_called()
    save.assert_not_called()
    panel.start_job.assert_not_called()


def test_replacing_profile_resets_connection_state(panel):
    panel.connected = True
    panel.set_profile(panel.profile)
    assert not panel.connected


@pytest.mark.parametrize('category,extensions', [
    ('images', ('.png', '.jpg')), ('media', ('.mp4', '.mp3')), ('presentations', ('.pptx', '.pdf'))])
def test_cloud_file_type_column_preserves_size_and_date_sorting(panel, category, extensions):
    panel.change_type(list(CATEGORIES).index(category), browse=False)
    folder = CloudItem(category, CATEGORIES[category], folder=True, category=category)
    items = [CloudItem('larger', 'Welcome' + extensions[0], category=category, size=2048,
                       modified='2026-10-08T01:00:00Z'),
             CloudItem('smaller', 'Welcome' + extensions[1], category=category, size=512,
                       modified='2026-10-09T01:00:00Z')]
    panel.jobs['listing'] = {'kind': 'browse', 'generation': panel.generation, 'context': False}
    panel.job_ready('listing', (folder, items, ''))
    panel.jobs.clear()
    tree = panel.tree
    assert [tree.headerItem().text(index) for index in range(tree.columnCount())] == [
        'Name', 'File Type', 'Size', 'Updated']
    assert {tree.topLevelItem(index).text(1) for index in range(2)} == {
        extension[1:].upper() for extension in extensions}
    tree.sortItems(2, QtCore.Qt.SortOrder.AscendingOrder)
    assert tree.topLevelItem(0).data(0, QtCore.Qt.ItemDataRole.UserRole).id == 'smaller'
    assert tree.topLevelItem(0).text(2) == panel.format_size(512)
    tree.sortItems(3, QtCore.Qt.SortOrder.AscendingOrder)
    assert tree.topLevelItem(0).data(0, QtCore.Qt.ItemDataRole.UserRole).id == 'larger'
    assert tree.topLevelItem(0).text(3)
    assert panel.trees['songs'].columnCount() == 3
    assert panel.trees['custom'].columnCount() == 3
    assert panel.trees['themes'].columnCount() == 3


@pytest.mark.parametrize('same_extension', [False, True])
def test_batch_cloud_moves_distinguish_file_extensions(panel, same_extension):
    panel.connected = True
    panel.change_type(list(CATEGORIES).index('images'), browse=False)
    folder = CloudItem('images', 'Images', folder=True, category='images', can_upload=True)
    items = [CloudItem('first', 'Welcome.png', category='images', can_move=True),
             CloudItem('second', 'Welcome.PNG' if same_extension else 'Welcome.jpg',
                       category='images', can_move=True)]
    panel.folder = folder
    panel.start_job = MagicMock()
    panel.upload(CloudDragData(panel, items), folder)
    if same_extension:
        panel.start_job.assert_not_called()
    else:
        kind, prepare, context = panel.start_job.call_args.args
        assert kind == 'prepare-upload'
        provider = MagicMock()
        provider.find_item.return_value = None
        assert prepare(provider) == [(item, None) for item in items]
        assert [call.kwargs['extension'] for call in provider.find_item.call_args_list] == ['.png', '.jpg']
        context['temporary'].cleanup()


@pytest.mark.parametrize('same_extension', [False, True])
def test_batch_downloads_distinguish_file_extensions(panel, monkeypatch, same_extension):
    plugin = SimpleNamespace(is_active=lambda: True)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.PluginManager.get_plugin_by_name', lambda name: plugin)
    existing = MagicMock(return_value=None)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.local_item', existing)
    panel.start_job = MagicMock()
    items = [CloudItem('first', 'Welcome.png', category='images'),
             CloudItem('second', 'Welcome.PNG' if same_extension else 'Welcome.jpg', category='images')]
    panel.download(items)
    if same_extension:
        panel.start_job.assert_not_called()
    else:
        assert panel.start_job.call_args.args[0] == 'download'
        assert [call.args[-1] for call in existing.call_args_list] == ['.png', '.jpg']


@pytest.mark.parametrize('category', ['images', 'media', 'presentations'])
def test_local_library_duplicate_lookup_matches_actual_file_extension(category):
    from openlp.plugins.librarysync.lib.transfer import local_item
    first = SimpleNamespace(id=1, name='Welcome.png', file_path='/library/Welcome.png')
    second = SimpleNamespace(id=2, name='Welcome.jpg', file_path='/library/Welcome.jpg')
    plugin = MagicMock()
    plugin.media_item.manager.get_all_objects.return_value = [first, second]
    assert local_item(category, plugin, 'WELCOME', '.PNG') is first
    assert local_item(category, plugin, 'Welcome', '.jpg') is second
    assert local_item(category, plugin, 'Welcome', '.pdf') is None


def test_importing_another_image_format_does_not_replace_existing_file(tmp_path):
    first = SimpleNamespace(id=1, name='Welcome.png', file_path='/library/Welcome.png')
    plugin = MagicMock()
    plugin.name = 'images'
    plugin.is_active.return_value = True
    plugin.media_item.manager.get_all_objects.return_value = [first]
    plugin.media_item.validate_and_load.return_value = True
    path = tmp_path / 'Welcome.jpg'
    path.write_bytes(b'new format')
    import_item(CloudItem('second', path.name, category='images'), path, plugin, prepared='new-hash')
    plugin.media_item.manager.save_object.assert_not_called()
    plugin.media_item.validate_and_load.assert_called_once_with(
        [path], None, file_hashes={path: 'new-hash'}, file_names={path: 'Welcome.jpg'})
    assert first.file_path == '/library/Welcome.png'


@pytest.mark.parametrize('category,extension', [('images', '.png'), ('media', '.mp4'), ('presentations', '.pdf')])
def test_view_reuses_uploaded_bytes_without_downloading(panel, tmp_path, monkeypatch, category, extension):
    from tempfile import TemporaryDirectory
    from threading import Event
    from openlp.plugins.librarysync.lib.cache import CloudCache

    monkeypatch.setattr('openlp.plugins.librarysync.lib.cache.AppLocation.get_directory', lambda kind: tmp_path)
    source = tmp_path / ('Welcome' + extension)
    source.write_bytes(b'uploaded file')
    item = CloudItem('uploaded', source.name, category=category, size=source.stat().st_size, version='2')
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    provider.upload.return_value = item
    panel.start_job = MagicMock()
    temporary = TemporaryDirectory()
    context = {'temporary': temporary, 'folder': CloudItem('folder', category, folder=True), 'copy': False}
    panel.run_upload(context, [((category, source, None, 'Welcome'), None)])
    kind, upload, _ = panel.start_job.call_args.args
    assert kind == 'upload'
    assert upload(provider, Event(), MagicMock()) == 1
    source.unlink()
    temporary.cleanup()
    panel.selected_items = MagicMock(return_value=[item])
    panel.open_preview()
    kind, view, temporary = panel.start_job.call_args.args
    try:
        result = view(provider, Event(), MagicMock(), MagicMock(), MagicMock())
        assert kind == 'preview'
        assert result[3] and result[1].read_bytes() == b'uploaded file'
        provider.download.assert_not_called()
        provider.preview.assert_not_called()
        provider.media_metadata.assert_not_called()
        assert not CloudCache(panel.profile, 'another-account').preview(item, tmp_path / 'other')
    finally:
        temporary.cleanup()


@pytest.mark.parametrize('outcome', ['failed', 'cancelled', 'modified'])
def test_unsuccessful_or_changed_upload_does_not_seed_preview(panel, tmp_path, monkeypatch, outcome):
    from tempfile import TemporaryDirectory
    from threading import Event
    from openlp.plugins.librarysync.lib.cache import CloudCache

    monkeypatch.setattr('openlp.plugins.librarysync.lib.cache.AppLocation.get_directory', lambda kind: tmp_path)
    source = tmp_path / 'Welcome.png'
    source.write_bytes(b'original file')
    item = CloudItem('uploaded', source.name, category='images', size=source.stat().st_size, version='2')
    provider = MagicMock()
    provider.cache_account.return_value = 'account'
    cancel = Event()

    def upload(*args, **kwargs):
        if outcome == 'failed':
            raise SyncError('Upload failed')
        if outcome == 'cancelled':
            cancel.set()
        else:
            source.write_bytes(b'changed bytes')
        return item
    provider.upload.side_effect = upload
    panel.start_job = MagicMock()
    temporary = TemporaryDirectory()
    context = {'temporary': temporary, 'folder': CloudItem('folder', 'Images', folder=True), 'copy': False}
    try:
        panel.run_upload(context, [(('images', source, None, 'Welcome'), None)])
        operation = panel.start_job.call_args.args[1]
        if outcome == 'failed':
            with pytest.raises(SyncError):
                operation(provider, cancel, MagicMock())
        else:
            operation(provider, cancel, MagicMock())
        assert not CloudCache(panel.profile, 'account').preview(item, tmp_path / 'preview.png')
    finally:
        temporary.cleanup()


def test_outdated_listing_refreshes_automatically_at_most_every_ten_seconds(panel, persistent_cache, monkeypatch):
    _, folder, _ = persistent_cache
    panel.poll_changes = MagicMock()
    panel.show()
    panel.folder = folder
    panel.browse = MagicMock()
    clock = SimpleNamespace(monotonic=MagicMock(return_value=1000))
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.time', clock)
    panel.jobs['changes'] = {'kind': 'changes', 'context': None, 'generation': panel.generation}
    panel.job_ready('changes', ('next', True))
    panel.job_completed('changes')
    assert panel.auto_refresh_timer.isActive()
    assert panel.refresh_button.isVisible() and panel.status.text() == 'Out of date'
    assert not panel.refresh_button.icon().isNull()
    assert panel.refresh_button.fluentSize() == QtWidgets.fluentqt.Button.ButtonSize.Small
    assert panel.refresh_button.fluentStyle() == QtWidgets.fluentqt.Button.ButtonStyle.Subtle
    panel.auto_refresh()
    panel.browse.assert_called_once_with(folder, force=True)
    clock.monotonic.return_value = 1001
    panel.auto_refresh()
    assert panel.browse.call_count == 1
    assert panel.auto_refresh_timer.remainingTime() > 8500
    clock.monotonic.return_value = 1010
    panel.auto_refresh()
    assert panel.browse.call_count == 2
    panel.out_of_date = False
    panel.set_ready_status()
    panel.auto_refresh()
    assert panel.browse.call_count == 2 and panel.refresh_button.isHidden()


def test_automatic_refresh_defers_transfers_and_stops_when_hidden(panel, persistent_cache):
    _, folder, _ = persistent_cache
    panel.poll_changes = MagicMock()
    panel.show()
    panel.folder, panel.out_of_date = folder, True
    panel.browse = MagicMock()
    panel.schedule_auto_refresh()
    panel.jobs['transfer'] = {'kind': 'upload'}
    panel.auto_refresh()
    panel.browse.assert_not_called()
    assert not panel.auto_refresh_timer.isActive()
    panel.jobs.clear()
    panel.schedule_auto_refresh()
    assert panel.auto_refresh_timer.isActive()
    panel.hide()
    panel.auto_refresh()
    panel.browse.assert_not_called()
    assert not panel.auto_refresh_timer.isActive()


def test_changing_connection_cancels_pending_automatic_refresh(panel, persistent_cache):
    _, folder, _ = persistent_cache
    panel.poll_changes = MagicMock()
    panel.show()
    panel.folder, panel.out_of_date = folder, True
    panel.set_status('')
    panel.schedule_auto_refresh()
    assert panel.auto_refresh_timer.isActive() and panel.refresh_button.isVisible()
    panel.set_profile({**panel.profile, 'name': 'Another Library'})
    assert not panel.auto_refresh_timer.isActive()
    assert not panel.out_of_date and panel.refresh_button.isHidden()


def test_name_prompt_rejects_blank_enter_and_trims_valid_name(panel, monkeypatch):
    from PySide6 import QtTest
    panel.resize(850, 600)
    panel.show()

    def enter_name(dialog):
        dialog.setAnimationEnabled(False)
        dialog.open()
        QtWidgets.QApplication.processEvents()
        field = dialog.findChild(QtWidgets.QLineEdit)
        for text in ('', '   '):
            field.setText(text)
            assert not dialog._native_commands['primary'].isEnabled()
            QtTest.QTest.keyClick(field, QtCore.Qt.Key.Key_Return)
            QtWidgets.QApplication.processEvents()
            assert dialog.isOpen()
        field.setText('  Sunday service  ')
        assert dialog._native_commands['primary'].isEnabled()
        QtTest.QTest.keyClick(field, QtCore.Qt.Key.Key_Return)
        QtWidgets.QApplication.processEvents()
        assert not dialog.isOpen()
        return dialog.result()

    monkeypatch.setattr(QtWidgets.ContentDialog, 'exec', enter_name)
    assert panel.request_name('New cloud folder', 'Folder name', 'Create') == 'Sunday service'
