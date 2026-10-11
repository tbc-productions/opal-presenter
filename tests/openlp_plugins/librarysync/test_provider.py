"""Exercise permission checks, integrity, pagination and resumable writes."""
import hashlib
from threading import Event
from unittest.mock import MagicMock

import pytest

from opal.plugins.librarysync.lib.google import API, WRITE_API, GoogleDriveProvider, cloud_item
from opal.plugins.librarysync.lib.provider import CloudItem, SyncError


def response(status=200, data=None, headers=None, chunks=()):
    result = MagicMock(status_code=status, headers=headers or {})
    result.json.return_value = data or {}
    result.iter_content.return_value = iter(chunks)
    result.__enter__.return_value = result
    return result


@pytest.fixture
def provider():
    auth = MagicMock()
    auth.access_token.return_value = 'test-access-token'
    result = GoogleDriveProvider(auth)
    result.session = MagicMock()
    result.find_item = MagicMock(return_value=None)
    result.check_new_name = lambda item, folder: item
    return result


def test_paged_shared_folder_listing(provider):
    provider.session.request.return_value = response(data={'files': [
        {'id': 'song', 'name': 'Amazing Grace.xml', 'size': '100', 'capabilities': {'canDownload': True}}],
        'nextPageToken': 'page-2'})
    folder = CloudItem('songs', 'Songs', folder=True)
    items, token = provider.list_folder(folder, 'page-1')
    assert items[0].category == 'songs'
    assert token == 'page-2'
    params = provider.session.request.call_args.kwargs['params']
    assert params['pageToken'] == 'page-1'
    assert params['includeItemsFromAllDrives'] == 'true'
    assert params['supportsAllDrives'] == 'true'
    assert params['pageSize'] == 200


def test_google_items_include_provider_and_available_author_metadata():
    item = cloud_item({'id': 'song', 'name': 'Welcome.xml', 'size': '2048',
                       'createdTime': '2026-10-08T01:00:00Z', 'modifiedTime': '2026-10-09T01:00:00Z',
                       'driveId': 'shared-drive',
                       'lastModifyingUser': {'displayName': 'Sam'}})
    assert item.provider_name == 'Google Drive' and item.drive_id == 'shared-drive'
    assert item.modified_by == 'Sam'
    assert item.created and item.modified and item.size == 2048
    unknown = cloud_item({'id': 'song', 'name': 'Welcome.xml'})
    assert unknown.modified_by == ''


def test_upload_rechecks_live_folder_permissions(provider, tmp_path):
    provider.folder = MagicMock(return_value=CloudItem('root', 'Church', folder=True, can_upload=False))
    with pytest.raises(SyncError, match='read-only'):
        provider.upload(CloudItem('root', 'Church', folder=True, can_upload=True), 'songs', tmp_path / 'song.xml',
                        Event(), MagicMock())
    provider.session.request.assert_not_called()


def test_download_is_atomic_and_checks_checksum(provider, tmp_path):
    contents = b'church image'
    metadata = {'id': 'image', 'name': 'Image.png', 'size': str(len(contents)), 'version': '2',
                'md5Checksum': hashlib.md5(contents).hexdigest(), 'capabilities': {'canDownload': True}}
    provider.metadata = MagicMock(return_value=metadata)
    provider.session.request.return_value = response(chunks=[contents])
    destination = tmp_path / 'Image.png'
    assert provider.download(cloud_item(metadata), destination, Event(), MagicMock()) == destination
    assert destination.read_bytes() == contents
    assert not destination.with_name('Image.png.part').exists()
    metadata['md5Checksum'] = 'wrong-checksum'
    provider.session.request.return_value = response(chunks=[b'broken'])
    with pytest.raises(SyncError, match='incomplete or changed'):
        provider.download(cloud_item(metadata), destination, Event(), MagicMock())
    assert destination.read_bytes() == contents
    assert not destination.with_name('Image.png.part').exists()


def test_changed_or_blocked_item_is_not_downloaded(provider, tmp_path):
    provider.metadata = MagicMock(return_value={'id': 'f', 'name': 'f.mp4', 'version': '3'})
    with pytest.raises(SyncError, match='changed'):
        provider.download(CloudItem('f', 'f.mp4', version='2'), tmp_path / 'f', Event(), MagicMock())
    provider.metadata.return_value['capabilities'] = {'canDownload': False}
    with pytest.raises(SyncError, match='cannot be downloaded'):
        provider.download(CloudItem('f', 'f.mp4', version='3'), tmp_path / 'f', Event(), MagicMock())
    provider.session.request.assert_not_called()


def test_cancelled_download_cleans_partial_file(provider, tmp_path):
    provider.metadata = MagicMock(return_value={'id': 'f', 'name': 'f.mp4', 'size': '10'})
    cancel = Event()

    def chunks(*args):
        yield b'123'
        cancel.set()
        yield b'456'
    download = response()
    download.iter_content.side_effect = chunks
    provider.session.request.return_value = download
    destination = tmp_path / 'f.mp4'
    with pytest.raises(SyncError, match='cancelled'):
        provider.download(CloudItem('f', 'f.mp4'), destination, cancel, MagicMock())
    assert list(tmp_path.iterdir()) == []


def test_new_upload_uses_friendly_filename_and_records_title(provider, tmp_path):
    source = tmp_path / 'Amazing Grace.xml'
    source.write_bytes(b'<song/>')
    provider.type_folder = MagicMock(return_value=CloudItem('songs', 'Songs', folder=True, can_upload=True))
    location = 'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'
    provider.session.request.side_effect = [response(headers={'Location': location}),
                                            response(data={'id': 'new', 'name': 'Amazing Grace.xml'})]
    result = provider.upload(CloudItem('root', 'Organisation'), 'songs', source, Event(), MagicMock())
    assert result.id == 'new'
    calls = provider.session.request.call_args_list
    names = [call.kwargs['json']['name'] for call in calls if call.args[0] == 'POST']
    assert names == ['Amazing Grace.xml']
    assert [call.args[0] for call in calls] == ['POST', 'PUT']
    assert calls[0].kwargs['json']['parents'] == ['songs']
    assert calls[0].kwargs['json']['appProperties']['openlpTitle'] == 'Amazing Grace'


def test_lost_chunk_response_resumes_same_upload(provider, tmp_path):
    source = tmp_path / 'file.mp4'
    source.write_bytes(b'1234567890')
    location = 'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'
    provider.type_folder = MagicMock(return_value=CloudItem('media', 'Media', folder=True, can_upload=True))
    provider.request = MagicMock(side_effect=[
        response(headers={'Location': location}), SyncError('network failure'),
        response(308, headers={'Range': 'bytes=0-4'}), response(data={'id': 'new', 'name': 'file.mp4'})])
    assert provider.upload(CloudItem('root', 'Church'), 'media', source, Event(), MagicMock()).id == 'new'
    calls = provider.request.call_args_list
    assert calls[2].kwargs['headers']['Content-Range'] == 'bytes */10'
    assert calls[3].kwargs['data'].getvalue() == b'67890'
    assert calls[3].kwargs['headers']['Content-Range'] == 'bytes 5-9/10'


def test_upload_reports_sent_bytes_before_drive_confirms(provider, tmp_path):
    import requests
    source = tmp_path / 'file.mp4'
    source.write_bytes(b'1234567890')
    provider.type_folder = MagicMock(return_value=CloudItem('media', 'Media', folder=True, can_upload=True))
    progress = MagicMock()

    def send(method, url, **kwargs):
        if method == 'POST':
            return response(headers={'Location': 'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'})
        prepared = requests.Request(method, url, data=kwargs['data'], headers=kwargs['headers']).prepare()
        assert prepared.headers['Content-Length'] == '10'
        assert 'Transfer-Encoding' not in prepared.headers
        assert prepared.body.read(3) == b'123'
        progress.assert_called_with(3, 10)
        assert prepared.body.read(3) == b'456'
        progress.assert_called_with(6, 10)
        assert prepared.body.read(4) == b'7890'
        progress.assert_called_with(9, 10)
        assert prepared.body.read() == b''
        assert all(call.args[0] < 10 for call in progress.call_args_list)
        return response(data={'id': 'new', 'name': 'file.mp4'})

    provider.session.request.side_effect = send
    assert provider.upload(CloudItem('root', 'Organisation'), 'media', source, Event(), progress).id == 'new'
    progress.assert_called_with(10, 10)


def test_sent_progress_does_not_change_confirmed_resume_offset(provider, tmp_path):
    source = tmp_path / 'file.mp4'
    source.write_bytes(b'1234567890')
    provider.type_folder = MagicMock(return_value=CloudItem('media', 'Media', folder=True, can_upload=True))
    progress = MagicMock()

    def send(method, url, **kwargs):
        import requests
        if method == 'POST':
            return response(headers={'Location': 'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'})
        if kwargs['data'] == b'':
            assert kwargs['headers']['Content-Range'] == 'bytes */10'
            return response(308, headers={'Range': 'bytes=0-4'})
        if kwargs['headers']['Content-Range'] == 'bytes 0-9/10':
            assert kwargs['data'].read() == b'1234567890'
            progress.assert_called_with(9, 10)
            raise requests.ConnectionError('network failure')
        assert kwargs['data'].read() == b'67890'
        assert kwargs['headers']['Content-Range'] == 'bytes 5-9/10'
        return response(data={'id': 'new', 'name': 'file.mp4'})

    provider.session.request.side_effect = send
    assert provider.upload(CloudItem('root', 'Organisation'), 'media', source, Event(), progress).id == 'new'
    progress.assert_called_with(10, 10)


def test_upload_cancel_is_checked_while_sending(provider, tmp_path):
    source = tmp_path / 'file.mp4'
    source.write_bytes(b'1234567890')
    cancel = Event()
    provider.type_folder = MagicMock(return_value=CloudItem('media', 'Media', folder=True, can_upload=True))

    def send(method, url, **kwargs):
        if method == 'POST':
            return response(headers={'Location': 'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'})
        assert kwargs['data'].read(3) == b'123'
        cancel.set()
        kwargs['data'].read(3)

    provider.session.request.side_effect = send
    with pytest.raises(SyncError, match='cancelled'):
        provider.upload(CloudItem('root', 'Organisation'), 'media', source, cancel, MagicMock())
    assert provider.session.request.call_count == 2


def test_resource_keys_are_sent_for_link_shared_items(provider, tmp_path):
    provider.metadata = MagicMock(return_value={'id': 'f', 'name': 'f.png', 'size': '1'})
    provider.session.request.return_value = response(chunks=[b'x'])
    provider.download(CloudItem('f', 'f.png', resource_key='resource'), tmp_path / 'f.png', Event(), MagicMock())
    assert provider.session.request.call_args.kwargs['headers']['X-Goog-Drive-Resource-Keys'] == 'f/resource'


def test_thumbnail_cannot_send_tokens_to_another_host(provider):
    assert provider.preview(CloudItem('f', 'f.mp4', thumbnail_url='https://attacker.example/thumbnail'), Event()) == (
        'none', b'')
    provider.session.request.assert_not_called()


def test_redirects_are_not_followed_with_credentials(provider):
    provider.session.request.return_value = response(302, headers={'Location': 'https://attacker.example'})
    with pytest.raises(SyncError, match='HTTP 302'):
        provider.request('GET', f'{API}/files/f')
    assert provider.session.request.call_args.kwargs['allow_redirects'] is False


def test_native_google_documents_offer_preview_instead_of_blob_download():
    item = cloud_item({'id': 'slides', 'name': 'Notices.pptx', 'mimeType': 'application/vnd.google-apps.presentation',
                       'capabilities': {'canDownload': True},
                       'webViewLink': 'https://docs.google.com/presentation/d/slides'})
    assert not item.can_download
    assert item.preview_url


def test_shared_profile_can_point_directly_to_a_type_folder(provider):
    provider.metadata = MagicMock(return_value={
        'id': 'songs', 'name': 'Songs', 'mimeType': 'application/vnd.google-apps.folder',
        'capabilities': {'canAddChildren': True}})
    folder = provider.folder('songs')
    assert folder.category == 'songs'
    assert provider.type_folder(folder, 'songs') == folder
    provider.session.request.assert_not_called()


def test_upload_uses_library_title_instead_of_managed_storage_name(provider, tmp_path):
    source = tmp_path / ('a' * 64 + '.png')
    source.write_bytes(b'image')
    provider.type_folder = MagicMock(return_value=CloudItem('images', 'Images', folder=True, can_upload=True))
    location = 'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'
    provider.request = MagicMock(side_effect=[
        response(headers={'Location': location}), response(data={'id': 'new', 'name': source.name})])
    provider.upload(CloudItem('root', 'Organisation'), 'images', source, Event(), MagicMock(),
                    title='Sunday background')
    name = provider.request.call_args_list[0].kwargs['json']['name']
    assert name == 'Sunday background.png'
    props = provider.request.call_args_list[0].kwargs['json']['appProperties']
    assert props['openlpTitle'] == 'Sunday background'


def test_stopped_worker_cannot_start_another_metadata_request(provider):
    provider.cancel = Event()
    provider.cancel.set()
    with pytest.raises(SyncError, match='cancelled'):
        provider.folder('church')
    provider.session.request.assert_not_called()


def test_google_provider_rejects_untrusted_preview_destinations():
    item = cloud_item({'id': 'f', 'name': 'Welcome.pptx', 'webViewLink': 'https://attacker.example'})
    assert not item.preview_url


def test_read_only_type_folder_can_be_browsed_without_creating_anything(provider):
    root = CloudItem('root', 'Organisation', folder=True)
    provider.folder = MagicMock(return_value=root)
    provider.session.request.return_value = response(data={'files': [{
        'id': 'songs', 'name': 'Songs', 'mimeType': 'application/vnd.google-apps.folder',
        'capabilities': {'canAddChildren': False}}]})
    child = provider.type_folder(root, 'songs', create=False)
    assert child.id == 'songs' and not child.can_upload
    assert [call.args[0] for call in provider.session.request.call_args_list] == ['GET']


def test_empty_type_folder_is_not_created_for_reader(provider):
    root = CloudItem('root', 'Organisation', folder=True)
    provider.folder = MagicMock(return_value=root)
    provider.session.request.return_value = response(data={'files': []})
    assert provider.type_folder(root, 'images', create=False) is None
    with pytest.raises(SyncError, match='read-only'):
        provider.create_folder(root, 'images', 'Advent')
    assert provider.session.request.call_count == 1


@pytest.mark.parametrize('name', ['', '.', '..', '../outside', 'path/child', 'path\\child', 'x' * 201])
def test_new_folder_rejects_paths_before_network_request(provider, name):
    with pytest.raises(SyncError, match='folder name'):
        provider.create_folder(CloudItem('root', 'Organisation', folder=True), 'images', name)
    provider.session.request.assert_not_called()


def test_creating_nested_folder_preserves_library_type(provider):
    target = CloudItem('images', 'Images', folder=True, category='images', can_upload=True)
    provider.folder = MagicMock(return_value=target)
    provider.session.request.return_value = response(data={
        'id': 'advent', 'name': 'Advent', 'mimeType': 'application/vnd.google-apps.folder'})
    child = provider.create_folder(target, 'images', 'Advent')
    assert child.category == 'images'
    call = provider.session.request.call_args
    assert call.args[0] == 'POST'
    assert call.kwargs['json']['parents'] == ['images']
    assert call.kwargs['json']['appProperties']['openlpType'] == 'images'


def test_cloud_folder_drop_copies_without_modifying_source(provider):
    item = CloudItem('image', 'Sunday [123456abcdef].png', version='3', category='images', can_copy=True)
    provider.type_folder = MagicMock(return_value=CloudItem('advent', 'Advent', folder=True, can_upload=True))
    provider.metadata = MagicMock(return_value={
        'id': item.id, 'name': item.name, 'version': '3', 'capabilities': {'canCopy': True}})
    provider.session.request.return_value = response(data={'id': 'new', 'name': 'Sunday.png'})
    assert provider.copy(item, CloudItem('advent', 'Advent', category='images', folder=True)).id == 'new'
    call = provider.session.request.call_args
    assert call.args[:2] == ('POST', f'{API}/files/image/copy')
    assert call.kwargs['json']['parents'] == ['advent']
    assert call.kwargs['json']['name'] == 'Sunday.png'


def test_cloud_copy_rechecks_source_permissions_and_version(provider):
    provider.type_folder = MagicMock(return_value=CloudItem('advent', 'Advent', folder=True, can_upload=True))
    item = CloudItem('image', 'Sunday.png', version='3', category='images', can_copy=True)
    provider.metadata = MagicMock(return_value={
        'id': item.id, 'name': item.name, 'version': '4', 'capabilities': {'canCopy': True}})
    with pytest.raises(SyncError, match='changed'):
        provider.copy(item, CloudItem('advent', 'Advent', category='images', folder=True))
    provider.metadata.return_value['capabilities']['canCopy'] = False
    with pytest.raises(SyncError, match='permission'):
        provider.copy(item, CloudItem('advent', 'Advent', category='images', folder=True))
    provider.session.request.assert_not_called()


def test_stream_rechecks_version_and_passes_native_player_range(provider):
    provider.metadata = MagicMock(return_value={
        'id': 'f', 'name': 'Opening video.mp4', 'version': '2', 'capabilities': {'canDownload': True}})
    provider.session.request.return_value = response(206)
    provider.stream(CloudItem('f', 'Opening video.mp4', version='2'), 'bytes=100-', Event()).close()
    call = provider.session.request.call_args
    assert call.kwargs['headers']['Range'] == 'bytes=100-'
    assert call.kwargs['headers']['Authorization'] == 'Bearer test-access-token'
    assert call.kwargs['stream']
    provider.metadata.return_value['version'] = '3'
    with pytest.raises(SyncError, match='changed'):
        provider.stream(CloudItem('f', 'Opening video.mp4', version='2'), 'bytes=100-', Event())


def test_overwrite_updates_existing_drive_id_with_a_version_precondition(provider, tmp_path):
    source = tmp_path / 'Sunday.png'
    source.write_bytes(b'image')
    folder = CloudItem('images', 'Images', folder=True, category='images', can_upload=True)
    existing = CloudItem('existing', 'Sunday.png', category='images', version='3', can_edit=True)
    provider.type_folder = MagicMock(return_value=folder)
    provider.find_item.return_value = existing
    provider.metadata = MagicMock(return_value={
        'id': existing.id, 'name': existing.name, 'version': '3', '_etag': '"revision-three"',
        'capabilities': {'canEdit': True}})
    location = 'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'
    provider.request = MagicMock(side_effect=[
        response(data={'etag': '"revision-three"', 'version': '3'}),
        response(headers={'Location': location}), response(data={'id': 'existing'})])
    assert provider.upload(folder, 'images', source, Event(), MagicMock(), overwrite=existing).id == existing.id
    lock, initial, chunk = provider.request.call_args_list
    assert initial.args == ('PUT', 'https://www.googleapis.com/upload/drive/v2/files/existing')
    assert initial.kwargs['headers']['If-Match'] == '"revision-three"'
    assert chunk.kwargs['headers']['If-Match'] == '"revision-three"'
    assert 'parents' not in initial.kwargs['json']
    assert initial.kwargs['json']['title'] == 'Sunday.png'
    assert initial.kwargs['json']['properties'][1] == {
        'key': 'openlpTitle', 'value': 'Sunday', 'visibility': 'PRIVATE'}


def test_existing_name_requires_confirmation_and_changed_revision_cannot_be_overwritten(provider, tmp_path):
    source = tmp_path / 'Sunday.png'
    source.write_bytes(b'image')
    folder = CloudItem('images', 'Images', folder=True, category='images', can_upload=True)
    existing = CloudItem('existing', 'Sunday.png', category='images', version='3', can_edit=True)
    provider.type_folder = MagicMock(return_value=folder)
    provider.find_item.return_value = existing
    with pytest.raises(SyncError, match='confirm overwrite'):
        provider.upload(folder, 'images', source, Event(), MagicMock())
    provider.metadata = MagicMock(return_value={
        'id': existing.id, 'name': existing.name, 'version': '4', '_etag': '"revision-four"',
        'capabilities': {'canEdit': True}})
    with pytest.raises(SyncError, match='Another user changed'):
        provider.upload(folder, 'images', source, Event(), MagicMock(), overwrite=existing)
    provider.session.request.assert_not_called()


def test_find_duplicate_name_checks_all_pages_and_matches_case_and_unicode(provider):
    folder = CloudItem('images', 'Images', folder=True, category='images')
    provider.type_folder = MagicMock(return_value=folder)
    item = CloudItem('last-page', 'ＳＵＮＤＡＹ.JPG', category='images')
    provider.list_folder = MagicMock(side_effect=[([], 'second'), ([item], '')])
    assert GoogleDriveProvider.find_item(provider, folder, 'images', 'Sunday', extension='.jpg') is item
    assert provider.list_folder.call_args_list[-1].args == (folder, 'second')


def test_simultaneous_new_upload_retracts_only_its_own_later_copy(provider):
    folder = CloudItem('images', 'Images', folder=True, category='images')
    first = CloudItem('first', 'Sunday.png', category='images', created='2026-10-09T01:00:00Z')
    second = CloudItem('second', 'Sunday.png', category='images', created='2026-10-09T01:00:01Z')
    provider.list_folder = MagicMock(return_value=([first, second], ''))
    provider.delete = MagicMock()
    with pytest.raises(SyncError, match='shared this name first'):
        GoogleDriveProvider.check_new_name(provider, second, folder)
    provider.delete.assert_called_once_with(second)


def test_rename_rejects_duplicate_and_delete_is_permission_checked_and_recoverable(provider):
    item = CloudItem('image', 'Sunday.png', version='3', category='images', can_edit=True, can_delete=True)
    folder = CloudItem('images', 'Images', folder=True, category='images')
    provider.find_item.return_value = CloudItem('other', 'Advent.png', category='images')
    with pytest.raises(SyncError, match='unique name'):
        provider.rename(item, folder, 'Advent')
    provider.session.request.assert_not_called()
    provider.metadata = MagicMock(return_value={
        'id': item.id, 'name': item.name, 'version': '3', '_etag': '"three"', 'capabilities': {'canTrash': True}})
    provider.session.request.side_effect = [response(data={'version': '3', 'etag': '"three"'}),
                                            response(data={'id': item.id})]
    provider.delete(item)
    call = provider.session.request.call_args
    assert call.args == ('PATCH', f'{WRITE_API}/files/image')
    assert call.kwargs['json'] == {'labels': {'trashed': True}}
    assert call.kwargs['headers']['If-Match'] == '"three"'
    provider.metadata.return_value['capabilities'] = {'canTrash': False}
    with pytest.raises(SyncError, match='write permission'):
        provider.delete(item)


@pytest.mark.parametrize('category', ['songs', 'custom'])
def test_flat_text_libraries_cannot_create_subfolders(provider, category):
    with pytest.raises(SyncError, match='cannot contain subfolders'):
        provider.create_folder(CloudItem('root', 'Organisation', folder=True), category, 'Advent')
    provider.session.request.assert_not_called()


def test_type_folder_recognises_existing_case_insensitive_names_across_pages(provider):
    root = CloudItem('root', 'Organisation', folder=True, can_upload=True)
    provider.request = MagicMock(side_effect=[response(data={'files': [], 'nextPageToken': 'second'}),
                                              response(data={'files': [{
                                                  'id': 'shared', 'name': 'SONGS',
                                                  'mimeType': 'application/vnd.google-apps.folder',
                                                  'capabilities': {'canAddChildren': True}}]})])
    child = provider.type_folder(root, 'songs', create=False)
    assert child.id == 'shared'
    assert provider.request.call_args.kwargs['params']['pageToken'] == 'second'


def test_first_upload_uses_older_type_folder_created_by_another_writer(provider):
    root = CloudItem('root', 'Organisation', folder=True, can_upload=True)
    shared = {'id': 'shared', 'name': 'Songs', 'mimeType': 'application/vnd.google-apps.folder',
              'capabilities': {'canAddChildren': True}}
    created = {**shared, 'id': 'mine'}
    provider.folder = MagicMock(return_value=root)
    provider.request = MagicMock(side_effect=[response(data={'files': []}), response(data=created),
                                              response(data={'files': [shared, created]}),
                                              response(data={'files': []})])
    provider.delete = MagicMock()
    assert provider.type_folder(root, 'songs').id == 'shared'
    provider.delete.assert_called_once()
    assert provider.delete.call_args.args[0].id == 'mine'


@pytest.mark.parametrize('destination_has_item', [False, True])
def test_name_uniqueness_only_checks_destination_folder(provider, destination_has_item):
    parent = CloudItem('presentations', 'Presentations', folder=True, category='presentations')
    child = CloudItem('advent', 'Advent', folder=True, category='presentations', parents=(parent.id,))
    nested = CloudItem('nested', 'Nested', folder=True, category='presentations', parents=(child.id,))
    parent_item = CloudItem('parent-file', 'Welcome.pptx', category='presentations', parents=(parent.id,))
    child_item = CloudItem('child-file', 'Welcome.pptx', category='presentations', parents=(child.id,))
    provider.type_folder = MagicMock(side_effect=lambda folder, *args, **kwargs: folder)
    provider.folder = MagicMock()
    provider.list_folder = MagicMock(side_effect=[([parent_item, child], ''), ([nested], 'second'),
                                                  ([child_item] if destination_has_item else [], '')])
    assert GoogleDriveProvider.find_item(provider, parent, 'presentations', 'Welcome', extension='.pptx') is parent_item
    result = GoogleDriveProvider.find_item(provider, child, 'presentations', 'Welcome', extension='.pptx')
    assert result == (child_item if destination_has_item else None)
    assert [call.args for call in provider.list_folder.call_args_list] == [
        (parent, ''), (child, ''), (child, 'second')]
    provider.folder.assert_not_called()


def test_new_name_check_does_not_retract_file_due_to_same_name_in_parent(provider):
    parent = CloudItem('presentations', 'Presentations', folder=True, category='presentations')
    child = CloudItem('advent', 'Advent', folder=True, category='presentations', parents=(parent.id,))
    original = CloudItem('original', 'Welcome.pptx', category='presentations', created='2026-10-09T01:00:00Z')
    uploaded = CloudItem('uploaded', 'Welcome.pptx', category='presentations', created='2026-10-09T02:00:00Z')
    provider.list_folder = MagicMock(side_effect=[([original, child], ''), ([uploaded], '')])
    provider.delete = MagicMock()
    provider.catalogue(parent)
    assert GoogleDriveProvider.check_new_name(provider, uploaded, child) is uploaded
    provider.delete.assert_not_called()
    assert provider.list_folder.call_args.args == (child, '')


def test_move_changes_parents_of_same_file_with_version_lock(provider):
    target = CloudItem('advent', 'Advent', folder=True, category='images', can_upload=True)
    item = CloudItem('f', 'Sunday.png', category='images', version='3', parents=('images',), can_move=True)
    provider.type_folder = MagicMock(return_value=target)
    provider.metadata = MagicMock(return_value={
        'id': 'f', 'name': 'Sunday.png', 'version': '3', '_etag': '"three"',
        'capabilities': {'canMoveItemWithinDrive': True}})
    provider.request = MagicMock(side_effect=[response(data={'version': '3', 'etag': '"three"'}),
                                              response(data={'id': 'f'})])
    assert provider.move(item, target).id == 'f'
    call = provider.request.call_args
    assert call.args == ('PATCH', f'{WRITE_API}/files/f')
    assert call.kwargs['headers']['If-Match'] == '"three"'
    assert call.kwargs['params']['addParents'] == 'advent'
    assert call.kwargs['params']['removeParents'] == 'images'


def test_writes_are_refused_when_provider_cannot_supply_a_version_lock(provider):
    item = CloudItem('f', 'Sunday.png', version='3', can_edit=True)
    provider.metadata = MagicMock(return_value={
        'id': 'f', 'name': 'Sunday.png', 'version': '3', 'capabilities': {'canEdit': True}})
    provider.request = MagicMock(return_value=response(data={'version': '3'}))
    with pytest.raises(SyncError, match='version lock'):
        provider.checked_write(item, 'can_edit')
    provider.request.assert_called_once()


def test_revision_changed_between_v3_permissions_and_v2_lock_prevents_write(provider):
    item = CloudItem('f', 'Sunday.png', version='3', can_edit=True)
    provider.metadata = MagicMock(return_value={
        'id': 'f', 'name': 'Sunday.png', 'version': '3', 'capabilities': {'canEdit': True}})
    provider.request = MagicMock(return_value=response(data={'version': '4', 'etag': '"four"'}))
    with pytest.raises(SyncError, match='Another user changed'):
        provider.checked_write(item, 'can_edit')
    assert provider.request.call_args.args[0] == 'GET'


def test_rename_uses_conditional_v2_metadata_and_private_title_property(provider):
    folder = CloudItem('images', 'Images', folder=True, category='images')
    item = CloudItem('f', 'Sunday.png', category='images', version='3', can_edit=True)
    provider.metadata = MagicMock(return_value={
        'id': 'f', 'name': 'Sunday.png', 'version': '3', 'capabilities': {'canEdit': True}})
    provider.request = MagicMock(side_effect=[response(data={'version': '3', 'etag': '"three"'}),
                                              response(data={'id': 'f'})])
    assert provider.rename(item, folder, 'Welcome').id == 'f'
    read, write = provider.request.call_args_list
    assert read.args[1] == f'{WRITE_API}/files/f'
    assert write.args == ('PATCH', f'{WRITE_API}/files/f')
    assert write.kwargs['headers']['If-Match'] == '"three"'
    assert write.kwargs['json']['title'] == 'Welcome.png'
    assert write.kwargs['json']['properties'][1]['value'] == 'Welcome'


def test_losing_type_folder_with_another_users_files_is_never_removed(provider):
    root = CloudItem('root', 'Organisation', folder=True, can_upload=True)
    shared = {'id': 'shared', 'name': 'Songs', 'mimeType': 'application/vnd.google-apps.folder',
              'capabilities': {'canAddChildren': True}}
    created = {**shared, 'id': 'mine'}
    provider.folder = MagicMock(return_value=root)
    provider.request = MagicMock(side_effect=[response(data={'files': []}), response(data=created),
                                              response(data={'files': [shared, created]})])
    provider.list_folder = MagicMock(return_value=([CloudItem('song', 'Sunday.xml')], ''))
    provider.delete = MagicMock()
    assert provider.type_folder(root, 'songs').id == 'mine'
    provider.delete.assert_not_called()


def test_cache_account_uses_stable_grant_and_never_exposes_tokens(provider):
    provider.auth.token = {'refresh_token': 'account-one-grant', 'access_token': 'short-lived-one'}
    first = provider.cache_account()
    provider.auth.token['access_token'] = 'short-lived-two'
    assert provider.cache_account() == first
    assert 'account-one-grant' not in first
    provider.auth.token['refresh_token'] = 'another-account-grant'
    assert provider.cache_account() != first
    provider.auth.token = {}
    assert provider.cache_account() == ''


def test_changes_follow_all_pages_and_include_shared_drive_and_removed_items(provider):
    provider.session.request.side_effect = [
        response(data={'changes': [{'fileId': 'new', 'changeType': 'file', 'file': {'parents': ['songs']}}],
                       'nextPageToken': 'next'}),
        response(data={'changes': [{'fileId': 'removed', 'changeType': 'file'}, {'changeType': 'drive'}],
                       'newStartPageToken': 'current'})]
    changes, token = provider.changes('saved')
    assert token == 'current'
    assert changes[0].id == 'new' and changes[0].parents == ('songs',)
    assert changes[1].id == 'removed' and changes[2].all_items
    calls = provider.session.request.call_args_list
    assert [call.kwargs['params']['pageToken'] for call in calls] == ['saved', 'next']
    assert all(call.kwargs['params']['includeItemsFromAllDrives'] == 'true' for call in calls)
    assert all(call.kwargs['params']['includeRemoved'] == 'true' for call in calls)
    assert all(call.kwargs['params']['pageSize'] == 1000 for call in calls)


def test_change_baseline_and_invalid_cursor_response(provider):
    provider.session.request.return_value = response(data={'startPageToken': 'baseline'})
    assert provider.change_token() == 'baseline'
    assert provider.session.request.call_args.args[1] == f'{API}/changes/startPageToken'
    provider.session.request.return_value = response(data={'nextPageToken': 'same'})
    with pytest.raises(SyncError, match='invalid change list'):
        provider.changes('same')
    provider.session.request.return_value = response(data={})
    with pytest.raises(SyncError, match='invalid change token'):
        provider.change_token()


@pytest.mark.parametrize('category,extensions', [
    ('images', ('.png', '.jpg')), ('media', ('.mp4', '.mp3')), ('presentations', ('.pptx', '.pdf'))])
def test_drive_duplicate_checks_and_concurrent_uploads_distinguish_extensions(provider, category, extensions):
    folder = CloudItem(category, category, folder=True, category=category)
    first = CloudItem('first', 'Welcome' + extensions[0], category=category, created='2026-10-09T01:00:00Z')
    second = CloudItem('second', 'Welcome' + extensions[1], category=category, created='2026-10-09T02:00:00Z')
    provider.type_folder = MagicMock(return_value=folder)
    provider.list_folder = MagicMock(return_value=([first, second], ''))
    provider.delete = MagicMock()
    assert GoogleDriveProvider.find_item(provider, folder, category, 'WELCOME',
                                         extension=extensions[0].upper()) is first
    assert GoogleDriveProvider.find_item(provider, folder, category, 'Welcome', extension=extensions[1]) is second
    assert GoogleDriveProvider.check_new_name(provider, second, folder) is second
    provider.delete.assert_not_called()
