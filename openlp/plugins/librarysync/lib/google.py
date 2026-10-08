"""Drive v3 provider: paged reads, checked downloads and resumable, permission-aware writes."""
import hashlib
import mimetypes
import time
from pathlib import Path
from dataclasses import replace
from threading import RLock
from urllib.parse import urlparse

import requests

from openlp.core.common import clean_filename
from openlp.plugins.librarysync.lib.provider import CATEGORIES, CloudItem, SyncError, friendly_name


API = 'https://www.googleapis.com/drive/v3'
WRITE_API = 'https://www.googleapis.com/drive/v2'
FOLDER_MIME = 'application/vnd.google-apps.folder'
FIELDS = ('id,name,mimeType,size,modifiedTime,createdTime,version,md5Checksum,'
          'webViewLink,thumbnailLink,resourceKey,parents,lastModifyingUser(displayName),'
          'capabilities(canAddChildren,canDownload,canCopy,canEdit,canTrash,canMoveItemWithinDrive),appProperties')
CHUNK_SIZE = 8 * 1024 * 1024


def cloud_item(data, category=''):
    permissions = data.get('capabilities', {})
    category = data.get('appProperties', {}).get('openlpType', category)
    if not category and data.get('mimeType') == FOLDER_MIME:
        category = next((key for key, name in CATEGORIES.items() if name.casefold() == data['name'].casefold()), '')
    return CloudItem(id=data['id'], name=data['name'], folder=data.get('mimeType') == FOLDER_MIME,
                     size=int(data.get('size', 0)), modified=data.get('modifiedTime', ''),
                     can_upload=permissions.get('canAddChildren', False),
                     can_download=(permissions.get('canDownload', True)
                                   and not data.get('mimeType', '').startswith('application/vnd.google-apps.')),
                     checksum=data.get('md5Checksum', ''),
                     version=data.get('version', ''),
                     category=category,
                     preview_url=(data.get('webViewLink', '')
                                  if preview_url_allowed(data.get('webViewLink', '')) else ''),
                     thumbnail_url=data.get('thumbnailLink', ''),
                     resource_key=data.get('resourceKey', ''),
                     title=data.get('appProperties', {}).get('openlpTitle', ''),
                     can_copy=permissions.get('canCopy', False), can_edit=permissions.get('canEdit', False),
                     can_delete=permissions.get('canTrash', False), created=data.get('createdTime', ''),
                     parents=tuple(data.get('parents', [])), can_move=permissions.get('canMoveItemWithinDrive', False),
                     provider_name='Google Drive',
                     modified_by=data.get('lastModifyingUser', {}).get('displayName', ''))


def preview_url_allowed(value):
    url = urlparse(value)
    return url.scheme == 'https' and url.hostname in ('drive.google.com', 'docs.google.com')


def item_properties(category, title):
    # Drive limits each property key/value pair to 124 UTF-8 bytes; longer titles live in the filename.
    return {'openlpType': category, 'openlpTitle': title if len(title.encode('utf-8')) <= 100 else None}


class GoogleDriveProvider:
    def __init__(self, auth, cancel=None):
        self.auth = auth
        self.cancel = cancel
        self.session = requests.Session()
        self.resource_keys = {}
        self.request_lock = RLock()
        self.roots = set()
        self.catalogues = {}

    def close(self):
        self.session.close()

    def sign_in(self, cancel, open_browser):
        self.auth.sign_in(cancel, open_browser)

    def disconnect(self):
        self.auth.disconnect()

    def request(self, method, url, *, cancel=None, retry=False, **kwargs):
        """Only retry reads or chunk/status requests; never repeat a file creation blindly."""
        cancel = cancel or self.cancel
        headers = kwargs.pop('headers', {})
        if self.resource_keys:
            headers['X-Goog-Drive-Resource-Keys'] = ','.join(
                f'{key}/{value}' for key, value in self.resource_keys.copy().items())
        for attempt in range(4 if retry else 1):
            if cancel and cancel.is_set():
                raise SyncError('Transfer cancelled.')
            try:
                with self.request_lock:
                    token = self.auth.access_token()
                    if cancel and cancel.is_set():
                        raise SyncError('Transfer cancelled.')
                    response = self.session.request(method, url,
                                                    headers={**headers, 'Authorization': 'Bearer ' + token},
                                                    timeout=(10, 30), allow_redirects=False, **kwargs)
            except requests.RequestException as error:
                raise SyncError('Could not contact Google Drive. Check your connection and retry.') from error
            if cancel and cancel.is_set():
                response.close()
                raise SyncError('Transfer cancelled.')
            if response.status_code == 401 and attempt == 0 and retry:
                self.auth.token['expires_at'] = 0
                response.close()
                continue
            if response.status_code in (429, 500, 502, 503, 504) and retry and attempt < 3:
                response.close()
                if cancel:
                    if cancel.wait(2 ** attempt):
                        raise SyncError('Transfer cancelled.')
                else:
                    time.sleep(2 ** attempt)
                continue
            if response.status_code in (200, 201, 206, 308):
                return response
            status = response.status_code
            response.close()
            if status == 403:
                raise SyncError('Google Drive refused access. '
                                'Check your folder permissions or the organisation’s API quota.')
            if status == 404:
                raise SyncError('The cloud item was removed or your account no longer has access. Refresh the folder.')
            if status == 412:
                raise SyncError('Another user changed this item. Refresh before trying again.')
            raise SyncError(f'Google Drive could not complete the request (HTTP {status}). Retry the operation.')
        raise SyncError('Google Drive is busy. Try again shortly.')

    def metadata(self, file_id):
        with self.request('GET', f'{API}/files/{file_id}', retry=True,
                          params={'fields': FIELDS, 'supportsAllDrives': 'true'}) as response:
            data = response.json()
            data['_etag'] = response.headers.get('ETag', '')
        if data.get('resourceKey'):
            self.resource_keys[file_id] = data['resourceKey']
        return data

    def folder(self, folder_id, resource_key=''):
        if resource_key:
            self.resource_keys[folder_id] = resource_key
        item = cloud_item(self.metadata(folder_id))
        if not item.folder:
            raise SyncError('Choose a Google Drive folder, rather than a file.')
        return item

    def list_folder(self, folder, page_token=''):
        query = f"'{folder.id}' in parents and trashed = false"
        with self.request('GET', f'{API}/files', retry=True, params={
                'q': query, 'pageSize': 200, 'pageToken': page_token, 'orderBy': 'folder,name_natural',
                'fields': f'nextPageToken,files({FIELDS})', 'supportsAllDrives': 'true',
                'includeItemsFromAllDrives': 'true'}) as response:
            data = response.json()
        category = folder.category or next((key for key, name in CATEGORIES.items() if name == folder.name), '')
        items = [cloud_item(item, category) for item in data.get('files', [])]
        for item in items:
            if item.resource_key:
                self.resource_keys[item.id] = item.resource_key
        return items, data.get('nextPageToken', '')

    def preview(self, item, cancel):
        """A thumbnail or small text preview does not download the full media file."""
        if item.resource_key:
            self.resource_keys[item.id] = item.resource_key
        if item.thumbnail_url:
            url = urlparse(item.thumbnail_url)
            if url.scheme == 'https' and url.hostname and url.hostname.endswith('.googleusercontent.com'):
                with self.request('GET', item.thumbnail_url, cancel=cancel, retry=True, stream=True) as response:
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        if cancel.is_set():
                            raise SyncError('Preview cancelled.')
                        data.extend(chunk)
                        if len(data) > 2 * 1024 * 1024:
                            return 'none', b''
                    return 'image', bytes(data)
        small_text = Path(item.name).suffix.lower() in ('.xml', '.txt')
        if item.can_download and small_text and item.size <= 1024 * 1024:
            with self.request('GET', f'{API}/files/{item.id}', cancel=cancel, retry=True, stream=True,
                              params={'alt': 'media', 'supportsAllDrives': 'true'}) as response:
                data = bytearray()
                for chunk in response.iter_content(65536):
                    if cancel.is_set():
                        raise SyncError('Preview cancelled.')
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        return 'none', b''
                return 'text', bytes(data)
        return 'none', b''

    def download(self, item, destination, cancel, progress):
        if item.resource_key:
            self.resource_keys[item.id] = item.resource_key
        current = cloud_item(self.metadata(item.id), item.category)
        if current.folder or not current.can_download:
            raise SyncError('This item cannot be downloaded. Use its cloud preview instead.')
        if current.version != item.version:
            raise SyncError('This item changed in the cloud. Refresh and download the current version.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + '.part')
        size, checksum = 0, hashlib.md5()
        try:
            with (
                self.request('GET', f'{API}/files/{item.id}', cancel=cancel, retry=True, stream=True,
                             params={'alt': 'media', 'supportsAllDrives': 'true'}) as response,
                temporary.open('wb') as output,
            ):
                for chunk in response.iter_content(256 * 1024):
                    if cancel.is_set():
                        raise SyncError('Transfer cancelled.')
                    output.write(chunk)
                    size += len(chunk)
                    checksum.update(chunk)
                    progress(size, current.size)
            if size != current.size or (current.checksum and checksum.hexdigest() != current.checksum):
                raise SyncError('The download was incomplete or changed. Refresh and try again.')
            if cancel.is_set():
                raise SyncError('Transfer cancelled.')
            temporary.replace(destination)
            return destination
        finally:
            temporary.unlink(missing_ok=True)

    def stream(self, item, byte_range, cancel):
        if item.resource_key:
            self.resource_keys[item.id] = item.resource_key
        current = cloud_item(self.metadata(item.id), item.category)
        if not current.can_download or current.folder:
            raise SyncError('This item cannot be played with your current permissions.')
        if current.version != item.version:
            raise SyncError('This item changed in the cloud. Refresh before previewing it.')
        return self.request('GET', f'{API}/files/{item.id}', cancel=cancel, retry=True, stream=True,
                            params={'alt': 'media', 'supportsAllDrives': 'true'},
                            headers={'Range': byte_range} if byte_range else {})

    def type_folder(self, folder, category, create=True):
        """Recheck permissions when transferring, even if the cached listing still says writable."""
        current = self.folder(folder.id, folder.resource_key) if create else folder
        if category not in CATEGORIES:
            raise SyncError('Choose a supported Library type.')
        current = replace(current, category=current.category or folder.category)
        if create and not current.can_upload:
            raise SyncError('You have read-only access to this folder. Ask a folder owner for upload permission.')
        if current.category:
            if current.category != category:
                if not create:
                    return None
                raise SyncError('Choose the matching item-type folder or the shared Library root.')
            return current
        name = CATEGORIES[category]
        matches, token = [], ''
        while True:
            with self.request('GET', f'{API}/files', retry=True, params={
                    'q': f"'{folder.id}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false",
                    'fields': f'nextPageToken,files({FIELDS})', 'orderBy': 'createdTime', 'pageSize': 200,
                    'pageToken': token, 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}) as response:
                data = response.json()
            matches.extend(item for item in data.get('files', []) if cloud_item(item).category == category)
            token = data.get('nextPageToken', '')
            if not token:
                break
        if matches:
            child = cloud_item(matches[0], category)
            if create and not child.can_upload:
                raise SyncError(f'You cannot upload to the {name} folder. Ask its owner for write permission.')
            return child
        if not create:
            return None
        with self.request('POST', f'{API}/files', params={'supportsAllDrives': 'true', 'fields': FIELDS}, json={
                'name': name, 'mimeType': FOLDER_MIME, 'parents': [folder.id],
                'appProperties': {'openlpType': category}}) as response:
            created = cloud_item(response.json(), category)
        shared = self.type_folder(folder, category, create=False)
        if shared is not None and shared.id != created.id:
            children, token = self.list_folder(created)
            if children or token:
                return created  # A concurrent writer already uses it; never bin their files.
            self.delete(created)
            return shared
        return created

    def create_folder(self, folder, category, name):
        if category in ('songs', 'custom'):
            raise SyncError('Songs and Custom Slides cannot contain subfolders.')
        name = name.strip()
        if not name or len(name) > 200 or name in ('.', '..') or any(char in name for char in '/\\\x00'):
            raise SyncError('Enter a folder name without path separators (up to 200 characters).')
        target = self.type_folder(folder, category)
        if self.find_item(target, category, name):
            raise SyncError('An item with this name already exists. Choose a different folder name.')
        with self.request('POST', f'{API}/files', params={'supportsAllDrives': 'true', 'fields': FIELDS}, json={
                'name': name, 'mimeType': FOLDER_MIME, 'parents': [target.id],
                'appProperties': {'openlpType': category}}) as response:
            return cloud_item(response.json(), category)

    def find_item(self, folder, category, title, exclude=''):
        from openlp.plugins.librarysync.lib.transfer import name_key
        target = self.type_folder(folder, category, create=False)
        if target is None:
            return None
        matches = [item for item in self.catalogue(target) if item.id != exclude
                   and name_key(item.display_name) == name_key(title)]
        if len(matches) > 1:
            raise SyncError('Several cloud items have this name. Rename or delete the duplicates before uploading.')
        return matches[0] if matches else None

    def category_root(self, folder):
        current, visited = folder, set()
        while self.roots and current.id not in self.roots and current.parents and current.id not in visited:
            visited.add(current.id)
            parent = self.folder(current.parents[0])
            if parent.category != folder.category:
                break
            current = parent
        return current

    def catalogue(self, folder, fresh=False):
        root = self.category_root(folder)
        if not fresh and root.id in self.catalogues:
            return self.catalogues[root.id]
        items, pending, visited = [], [root], set()
        while pending:
            current = pending.pop()
            if current.id in visited:
                continue
            visited.add(current.id)
            token = ''
            while True:
                page, token = self.list_folder(current, token)
                items.extend(page)
                pending.extend(child for child in page if child.folder and child.category in ('', root.category))
                if not token:
                    break
        self.catalogues[root.id] = items
        return items

    def move(self, item, folder):
        target = self.type_folder(folder, item.category)
        if target.id in item.parents:
            return item
        if self.find_item(target, item.category, item.display_name, exclude=item.id):
            raise SyncError('This name already exists. Rename duplicates before moving them.')
        headers = self.checked_write(item, 'can_move')
        with self.request('PATCH', f'{WRITE_API}/files/{item.id}', headers=headers,
                          params={'supportsAllDrives': 'true', 'fields': 'id',
                                  'addParents': target.id, 'removeParents': ','.join(item.parents)}):
            pass
            self.catalogues.clear()
        return cloud_item(self.metadata(item.id), item.category)

    def checked_write(self, item, permission):
        data = self.metadata(item.id)
        current = cloud_item(data, item.category)
        if not getattr(current, permission):
            raise SyncError('You do not have write permission for this cloud item.')
        if current.version != item.version:
            raise SyncError('Another user changed this item. Refresh before trying again.')
        # Drive v3 ignores conditional reads and omits ETags; use v2 for conditional mutations.
        with self.request('GET', f'{WRITE_API}/files/{item.id}', retry=True,
                          params={'fields': 'etag,version', 'supportsAllDrives': 'true'}) as response:
            lock = response.json()
        if lock.get('version') != item.version:
            raise SyncError('Another user changed this item. Refresh before trying again.')
        etag = lock.get('etag')
        if not etag:
            raise SyncError('Google Drive did not provide a version lock. Refresh before trying this change again.')
        return {'If-Match': etag}

    def rename(self, item, folder, title):
        from openlp.plugins.librarysync.lib.transfer import safe_name
        title = title.strip()
        if not title or len(title) > 200 or safe_name(title) != title:
            raise SyncError('Enter a name without path separators (up to 200 characters).')
        if self.find_item(folder, item.category, title, exclude=item.id):
            raise SyncError('An item with this name already exists. Choose a unique name.')
        headers = self.checked_write(item, 'can_edit')
        with self.request('PATCH', f'{WRITE_API}/files/{item.id}', headers=headers,
                          params={'supportsAllDrives': 'true', 'fields': 'id'}, json={
                              'title': title + ('' if item.folder else Path(item.name).suffix),
                              'properties': self.write_properties(item.category, title)}):
            pass
        self.catalogues.clear()
        return cloud_item(self.metadata(item.id), item.category)

    def delete(self, item):
        headers = self.checked_write(item, 'can_delete')
        # Move to Drive's bin so an organisation can recover an accidental deletion.
        with self.request('PATCH', f'{WRITE_API}/files/{item.id}', headers=headers,
                          params={'supportsAllDrives': 'true', 'fields': 'id'}, json={'labels': {'trashed': True}}):
            pass
        self.catalogues.clear()

    @staticmethod
    def write_properties(category, title):
        return [{'key': key, 'value': value, 'visibility': 'PRIVATE'}
                for key, value in item_properties(category, title).items()]

    def copy(self, item, folder):
        target = self.type_folder(folder, item.category)
        current = cloud_item(self.metadata(item.id), item.category)
        if current.folder or not current.can_copy:
            raise SyncError('You do not have permission to copy this item in the cloud.')
        if current.version != item.version:
            raise SyncError('This item changed in the cloud. Refresh before copying it.')
        if target.id == item.id:
            raise SyncError('Choose a subfolder as the destination.')
        if self.find_item(target, item.category, current.display_name):
            raise SyncError('This name already exists in the destination. Confirm overwrite before copying.')
        with self.request('POST', f'{API}/files/{item.id}/copy',
                          params={'supportsAllDrives': 'true', 'fields': FIELDS}, json={
                              'name': current.display_name + Path(current.name).suffix,
                              'parents': [target.id],
                              'appProperties': item_properties(item.category, current.display_name)}) as response:
            result = cloud_item(response.json(), item.category)
        return self.check_new_name(result, target)

    def check_new_name(self, item, folder):
        """A second writer must retract its new copy instead of leaving duplicate names."""
        # ponytail: Drive has no unique-name constraint; an external index is needed for strict concurrent creation.
        from openlp.plugins.librarysync.lib.transfer import name_key
        matches = [other for other in self.catalogue(folder, fresh=True)
                   if name_key(other.display_name) == name_key(item.display_name)]
        winner = min(matches + [item], key=lambda other: (other.created, other.id))
        if winner.id != item.id:
            self.delete(item)
            raise SyncError('Another user shared this name first. Refresh to choose whether to overwrite it.')
        return item

    def upload(self, folder, category, source, cancel, progress, title='', overwrite=None):
        target = self.type_folder(folder, category)
        title = title.strip() or friendly_name(source.name)
        filename = clean_filename(title).strip(' .') or 'Item'
        name = filename + source.suffix
        size = source.stat().st_size
        existing = self.find_item(target, category, title)
        if existing is not None and (overwrite is None or existing.id != overwrite.id):
            raise SyncError('This name already exists in the cloud. Refresh and confirm overwrite before uploading.')
        if overwrite is not None and (existing is None or existing.id != overwrite.id):
            raise SyncError('The item to overwrite changed. Refresh before uploading again.')
        headers = self.checked_write(overwrite, 'can_edit') if overwrite is not None else {}
        parameters = {'uploadType': 'resumable', 'supportsAllDrives': 'true', 'fields': FIELDS}
        if overwrite is not None and overwrite.parents and target.id not in overwrite.parents:
            if not overwrite.can_move:
                raise SyncError('You cannot move this replacement into the destination folder.')
            parameters.update(addParents=target.id, removeParents=','.join(overwrite.parents))
        metadata = {'name': name,
                    'appProperties': item_properties(category, title)}
        if overwrite is None:
            metadata['parents'] = [target.id]
        else:
            metadata = {'title': name, 'properties': self.write_properties(category, title)}
            parameters['fields'] = 'id'
        version = 'v2' if overwrite else 'v3'
        url = f'https://www.googleapis.com/upload/drive/{version}/files' + (f'/{overwrite.id}' if overwrite else '')
        with self.request('PUT' if overwrite else 'POST', url, cancel=cancel,
                          params=parameters,
                          headers={**headers, 'X-Upload-Content-Length': str(size),
                                   'X-Upload-Content-Type': mimetypes.guess_type(source.name)[0] or
                                   'application/octet-stream'},
                          json=metadata) as response:
            location = response.headers.get('Location', '')
        url = urlparse(location)
        if url.scheme != 'https' or url.hostname != 'www.googleapis.com':
            raise SyncError('Google Drive returned an invalid upload location.')
        offset, stalls = 0, 0
        with source.open('rb') as data:
            while True:
                data.seek(offset)
                chunk = data.read(CHUNK_SIZE)
                end = offset + len(chunk)
                content_range = f'bytes {offset}-{end - 1}/{size}' if chunk else f'bytes */{size}'
                # A failed chunk is resolved through the resumable session, avoiding a second file creation.
                try:
                    response = self.request('PUT', location, cancel=cancel, data=chunk,
                                            headers={**headers, 'Content-Range': content_range})
                except SyncError:
                    if cancel.is_set():
                        raise
                    response = self.request('PUT', location, cancel=cancel, retry=True, data=b'',
                                            headers={**headers, 'Content-Range': f'bytes */{size}'})
                with response:
                    if response.status_code in (200, 201):
                        progress(size, size)
                        if overwrite:
                            self.catalogues.clear()
                            return cloud_item(self.metadata(overwrite.id), category)
                        result = cloud_item(response.json(), category)
                        return self.check_new_name(result, target)
                    confirmed = response.headers.get('Range', '')
                    new_offset = int(confirmed.rsplit('-', 1)[-1]) + 1 if confirmed else 0
                    stalls = stalls + 1 if new_offset <= offset else 0
                    if stalls >= 3:
                        raise SyncError('The upload stalled. Refresh before retrying. Existing files are retained.')
                    offset = new_offset
                    progress(offset, size)
