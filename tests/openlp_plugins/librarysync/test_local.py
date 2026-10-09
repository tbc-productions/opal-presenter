"""Local cloud storage confines reads and atomic writes to a selected folder."""
from dataclasses import replace
from threading import Event
from unittest.mock import MagicMock

import pytest

from openlp.plugins.librarysync.lib.local import LocalStorageProvider
from openlp.plugins.librarysync.lib.profile import deserialize_profile, serialize_profile, validate_profile
from openlp.plugins.librarysync.lib.provider import CATEGORIES, SyncError
from openlp.plugins.librarysync.lib.worker import PROVIDERS, SyncWorker


@pytest.fixture
def storage(tmp_path):
    root = tmp_path / 'Cloud Library'
    root.mkdir()
    profile = validate_profile({'version': 1, 'provider': 'local-cloud', 'name': 'Campus Library', 'path': str(root)})
    return LocalStorageProvider(profile, Event())


def test_local_profile_roundtrip_has_no_credentials(storage):
    profile = validate_profile({'version': 1, 'provider': 'local-cloud', 'name': ' Campus Library ',
                                'path': str(storage.root), 'access_token': 'secret',
                                'folders': [{'id': '../outside'}]})
    assert profile['name'] == 'Campus Library'
    assert profile['folders'] == [{'id': '.', 'name': 'Campus Library', 'resource_key': ''}]
    assert 'access_token' not in profile and 'installed' not in profile
    assert deserialize_profile(serialize_profile(profile)) == profile
    assert PROVIDERS['local-cloud'] is LocalStorageProvider


@pytest.mark.parametrize('path', ['', '.', '../storage', None, [], 'bad\x00path'])
def test_local_profile_rejects_invalid_paths(path):
    with pytest.raises(SyncError):
        validate_profile({'version': 1, 'provider': 'local-cloud', 'name': 'Library', 'path': path})


def test_local_worker_connects_without_browser(storage):
    profile = validate_profile({'version': 1, 'provider': 'local-cloud', 'name': 'Library', 'path': str(storage.root)})
    worker = SyncWorker('local', profile, lambda provider, cancel, progress, browser, ready:
                        (provider.sign_in(cancel, browser), provider.folder('.'))[1])
    browser, result, failed = MagicMock(), MagicMock(), MagicMock()
    worker.browser.connect(browser)
    worker.ready.connect(result)
    worker.failed.connect(failed)
    worker.start()
    browser.assert_not_called()
    failed.assert_not_called()
    assert result.call_args.args[1].folder


@pytest.mark.parametrize('category', list(CATEGORIES))
def test_local_upload_download_and_category_listing(storage, tmp_path, category):
    source = tmp_path / 'export.xml'
    source.write_bytes(b'<item>Library content</item>')
    root = storage.folder('.')
    assert storage.type_folder(root, category, create=False) is None
    uploaded = storage.upload(root, category, source, Event(), MagicMock(), title='Sunday service')
    folder = storage.type_folder(root, category, create=False)
    items, token = storage.list_folder(folder)
    assert items == [uploaded] and not token
    assert uploaded.display_name == 'Sunday service'
    assert uploaded.category == category
    assert storage.find_item(root, category, ' SUNDAY SERVICE ', extension='.xml').id == uploaded.id
    destination = tmp_path / 'download.xml'
    storage.download(uploaded, destination, Event(), MagicMock())
    assert destination.read_bytes() == source.read_bytes()
    assert storage.preview(uploaded, Event()) == ('text', source.read_bytes())
    assert uploaded.can_edit and uploaded.can_delete and uploaded.can_move


def test_local_overwrite_requires_confirmation_and_current_version(storage, tmp_path):
    source = tmp_path / 'photo.png'
    source.write_bytes(b'original')
    item = storage.upload(storage.folder('.'), 'images', source, Event(), MagicMock(), title='Photo')
    source.write_bytes(b'replacement')
    with pytest.raises(SyncError, match='Confirm overwrite'):
        storage.upload(storage.folder('.'), 'images', source, Event(), MagicMock(), title='Photo')
    replaced = storage.upload(storage.folder('.'), 'images', source, Event(), MagicMock(),
                              title='Photo', overwrite=item)
    assert storage.path(replaced.id).read_bytes() == b'replacement'
    with pytest.raises(SyncError, match='changed'):
        storage.download(item, tmp_path / 'old.png', Event(), MagicMock())
    with pytest.raises(SyncError, match='changed'):
        storage.upload(storage.folder('.'), 'images', source, Event(), MagicMock(), title='Photo', overwrite=item)
    assert storage.path(replaced.id).read_bytes() == b'replacement'


def test_cancelled_local_transfer_retains_destination_and_cleans_temporary(storage, tmp_path):
    source = tmp_path / 'photo.png'
    source.write_bytes(b'original')
    root = storage.folder('.')
    item = storage.upload(root, 'images', source, Event(), MagicMock(), title='Photo')
    source.write_bytes(b'new content')
    cancelled = Event()
    cancelled.set()
    with pytest.raises(SyncError, match='cancelled'):
        storage.upload(root, 'images', source, cancelled, MagicMock(), title='Photo', overwrite=item)
    assert storage.path(item.id).read_bytes() == b'original'
    assert not list(storage.root.rglob('.librarysync-*'))
    destination = tmp_path / 'download.png'
    destination.write_bytes(b'previous download')
    with pytest.raises(SyncError, match='cancelled'):
        storage.download(item, destination, cancelled, MagicMock())
    assert destination.read_bytes() == b'previous download'


@pytest.mark.parametrize('item_id', ['../outside', '/etc/passwd', 'Images/../../outside', '.librarysync-trash/item'])
def test_local_paths_cannot_escape_storage(storage, item_id):
    with pytest.raises(SyncError):
        storage.path(item_id)


def test_local_links_are_hidden_and_cannot_be_followed(storage, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'private.txt').write_text('private')
    (storage.root / 'link').symlink_to(outside, target_is_directory=True)
    items, _ = storage.list_folder(storage.folder('.'))
    assert items == []
    with pytest.raises(SyncError, match='Symbolic links'):
        storage.folder('link')
    with pytest.raises(SyncError):
        storage.path('link/private.txt')
    assert storage.change_token()


def test_local_rename_move_and_delete_keep_deleted_content(storage, tmp_path):
    source = tmp_path / 'photo.png'
    source.write_bytes(b'picture')
    root = storage.folder('.')
    item = storage.upload(root, 'images', source, Event(), MagicMock(), title='Photo')
    category = storage.type_folder(root, 'images')
    renamed = storage.rename(item, category, 'Renamed photo')
    assert not storage.path(item.id).exists()
    assert renamed.display_name == 'Renamed photo'
    folder = storage.create_folder(category, 'images', 'Service')
    moved = storage.move(renamed, folder)
    assert storage.path(moved.id).parent.name == 'Service'
    assert not storage.path(renamed.id).exists()
    storage.delete(moved)
    assert not storage.path(moved.id).exists()
    retained = list((storage.root / '.librarysync-trash').glob('*/*'))
    assert len(retained) == 1 and retained[0].read_bytes() == b'picture'
    assert all(not item.name.startswith('.') for item in storage.list_folder(storage.folder('.'))[0])
    with pytest.raises(SyncError, match='root'):
        storage.delete(storage.folder('.'))
    with pytest.raises(SyncError, match='root'):
        storage.rename(storage.folder('.'), root, 'Renamed Library')


def test_local_name_collision_and_wrong_category_do_not_overwrite(storage, tmp_path):
    source = tmp_path / 'photo.png'
    source.write_bytes(b'picture')
    root = storage.folder('.')
    item = storage.upload(root, 'images', source, Event(), MagicMock(), title='Photo')
    second = storage.upload(root, 'images', source, Event(), MagicMock(), title='Other')
    with pytest.raises(SyncError, match='already exists'):
        storage.rename(second, storage.type_folder(root, 'images'), 'Photo')
    assert storage.path(item.id).read_bytes() == b'picture'
    with pytest.raises(SyncError, match='matching'):
        storage.type_folder(storage.type_folder(root, 'images'), 'songs')
    with pytest.raises(SyncError, match='subfolders'):
        storage.create_folder(root, 'songs', 'Folder')


def test_local_changes_only_report_changed_storage(storage):
    token = storage.change_token()
    assert storage.changes(token) == ([], token)
    (storage.root / 'new.txt').write_text('new')
    changes, updated = storage.changes(token)
    assert changes[0].all_items and updated != token
    assert storage.changes(updated) == ([], updated)


@pytest.mark.parametrize('byte_range,status,expected', [
    ('', 200, b'0123456789'), ('bytes=2-5', 206, b'2345'), ('bytes=7-', 206, b'789'),
    ('bytes=-3', 206, b'789'), ('bytes=20-30', 416, b'')])
def test_local_media_supports_ranges(storage, byte_range, status, expected):
    path = storage.root / 'clip.mp4'
    path.write_bytes(b'0123456789')
    item = storage.item(path)
    with storage.stream(item, byte_range, Event()) as response:
        assert response.status_code == status
        assert b''.join(response.iter_content(2)) == expected
        assert int(response.headers['Content-Length']) == len(expected)
    assert response.file.closed


def test_local_stream_rejects_stale_item(storage):
    path = storage.root / 'clip.mp4'
    path.write_bytes(b'clip')
    item = storage.item(path)
    with pytest.raises(SyncError, match='changed'):
        storage.stream(replace(item, version='stale'), '', Event())


def test_local_transfer_rejects_source_changes_and_cleans_up(storage, tmp_path):
    source = tmp_path / 'photo.png'
    source.write_bytes(b'picture')
    with pytest.raises(SyncError, match='source file changed'):
        storage.upload(storage.folder('.'), 'images', source, Event(),
                       lambda *args: source.write_bytes(b'changed picture'), title='Photo')
    folder = storage.type_folder(storage.folder('.'), 'images', create=False)
    assert storage.list_folder(folder) == ([], '')
    assert not list(storage.root.rglob('.librarysync-*'))


def test_local_concurrent_name_collision_preserves_other_writer(storage, tmp_path):
    source = tmp_path / 'photo.png'
    source.write_bytes(b'picture')

    def concurrent_upload(*args):
        (storage.root / 'Images' / 'Photo.png').write_bytes(b'other writer')

    with pytest.raises(SyncError, match='already exists'):
        storage.upload(storage.folder('.'), 'images', source, Event(), concurrent_upload, title='Photo')
    assert (storage.root / 'Images' / 'Photo.png').read_bytes() == b'other writer'
    assert not list(storage.root.rglob('.librarysync-*'))


@pytest.mark.parametrize('category,extensions', [
    ('images', ('.png', '.jpg')), ('media', ('.mp4', '.mp3')), ('presentations', ('.pptx', '.pdf'))])
def test_local_storage_allows_same_name_with_different_extensions(storage, tmp_path, category, extensions):
    root = storage.folder('.')
    uploaded = []
    for extension in extensions:
        source = tmp_path / ('Welcome' + extension)
        source.write_bytes(extension.encode())
        uploaded.append(storage.upload(root, category, source, Event(), MagicMock(), title='Welcome'))
    folder = storage.type_folder(root, category)
    assert len(storage.list_folder(folder)[0]) == 2
    for item, extension in zip(uploaded, extensions):
        assert storage.find_item(folder, category, 'WELCOME', extension=extension.upper()).id == item.id
        assert storage.path(item.id).read_bytes() == extension.encode()
    with pytest.raises(SyncError, match='Confirm overwrite'):
        storage.upload(root, category, source, Event(), MagicMock(), title='Welcome')


def test_local_rename_and_move_allow_another_format_with_same_name(storage, tmp_path):
    root = storage.folder('.')
    png, jpg = tmp_path / 'Welcome.png', tmp_path / 'Other.jpg'
    png.write_bytes(b'png')
    jpg.write_bytes(b'jpg')
    first = storage.upload(root, 'images', png, Event(), MagicMock(), title='Welcome')
    second = storage.upload(root, 'images', jpg, Event(), MagicMock(), title='Other')
    category = storage.type_folder(root, 'images')
    second = storage.rename(second, category, 'Welcome')
    folder = storage.create_folder(category, 'images', 'Service')
    first = storage.move(first, folder)
    second = storage.move(second, folder)
    assert {item.name for item in storage.list_folder(folder)[0]} == {'Welcome.png', 'Welcome.jpg'}
    assert storage.path(first.id).read_bytes() == b'png'
    assert storage.path(second.id).read_bytes() == b'jpg'
