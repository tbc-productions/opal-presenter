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
from openlp.core.widgets.dnd import ItemDragData
from openlp.plugins.librarysync.lib.panel import CloudDragData, CloudLibrary
from openlp.plugins.librarysync.lib.provider import CloudItem, SyncError
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
    assert panel.connect_button.text() == 'Connect'
    assert not panel.download_action.isEnabled()
    assert not panel.preview_action.isEnabled()
    assert panel.cancel_button.isHidden()
    assert panel.tree.topLevelItemCount() == 0
    assert panel.import_info.isHidden()
    assert panel.connect_button.isEnabled()
    assert panel.status.parentWidget() is panel.footer
    panel.set_status('Ready to connect')
    assert panel.status.toolTip() == 'Ready to connect'
    from openlp.core.widgets.docks import MediaToolBox
    from openlp.core.widgets.fluent_tree import FluentLibraryTreeDelegate
    from fluentqt import Breadcrumb
    assert isinstance(panel.sections, MediaToolBox)
    assert isinstance(panel.tree.itemDelegate(), FluentLibraryTreeDelegate)
    assert isinstance(panel.breadcrumbs, Breadcrumb)
    assert [panel.sections.itemText(index) for index in range(panel.sections.count())] == [
        'Songs', 'Images', 'Custom Slides', 'Media', 'Presentations', 'Themes']
    assert not hasattr(panel, 'preview_text') and not hasattr(panel, 'preview_image')


def test_no_connections_shows_import_infobar_and_disables_connect(panel, qtbot, monkeypatch):
    imported = MagicMock()
    monkeypatch.setattr(CloudLibrary, 'import_connection', imported)
    empty = CloudLibrary(panel.plugin, None)
    qtbot.addWidget(empty)
    assert isinstance(empty.import_info, QtWidgets.fluentqt.InfoBar)
    assert isinstance(empty.import_info.actionWidget(), QtWidgets.fluentqt.HyperlinkButton)
    assert not empty.import_info.isHidden()
    assert not empty.connect_button.isEnabled()
    assert not empty.roots.isEnabled()
    assert empty.breadcrumbs.isHidden()
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


def test_local_drop_requires_active_matching_cloud_type(panel):
    view = QtWidgets.QListWidget()
    view.addItem('Sunday')
    view.item(0).setSelected(True)
    library = SimpleNamespace(plugin=SimpleNamespace(name='images'), list_view=view,
                              get_library_tab_icon=lambda: QtGui.QIcon())
    mime = ItemDragData(library=library)
    panel.folder = CloudItem('root', 'Organisation', folder=True, can_upload=True)
    assert panel.category == 'songs'
    assert not panel.can_upload(mime)
    panel.category = 'images'
    assert panel.can_upload(mime)
    assert panel.can_upload(mime, CloudItem('advent', 'Advent', folder=True, category='images', can_upload=True))
    assert not panel.can_upload(mime, CloudItem(
        'custom', 'Custom Slides', folder=True, category='custom', can_upload=True))
    view.deleteLater()


def test_cloud_drop_uses_writable_subfolder_and_matching_type(panel):
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
    assert [crumb.text for crumb in panel.breadcrumbs.items()] == ['Church Library', 'Images', 'Advent', 'Week one']
    panel.browse = MagicMock()
    panel.activate_breadcrumb(2, panel.breadcrumbs.items()[2])
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
    window = MagicMock()
    show = MagicMock(return_value=window)
    monkeypatch.setattr('openlp.plugins.librarysync.lib.panel.show_preview', show)
    opened = MagicMock()
    monkeypatch.setattr(QtGui.QDesktopServices, 'openUrl', opened)
    panel.update_actions()
    assert panel.preview_action.isEnabled()
    panel.open_preview()
    assert show.call_args.args[0] is panel.window()
    window.show.assert_called_once()
    opened.assert_not_called()
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
    assert restored.connect_button.text() == 'Reconnect'
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


def test_cloud_lists_show_metadata_and_keep_downloads_in_sorted_position(panel, qtbot):
    from PySide6 import QtTest
    from openlp.core.widgets.views import FileTreeWidgetItem
    panel.resize(850, 650)
    panel.show()
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
    assert panel.tree.topLevelItem(0).text(2) != '—'
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
