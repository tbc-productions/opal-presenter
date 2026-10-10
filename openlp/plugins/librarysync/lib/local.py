"""A selected desktop folder using the same Library layout as cloud providers."""
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from openlp.core.common import clean_filename
from openlp.plugins.librarysync.lib.provider import CATEGORIES, CloudChange, CloudItem, SyncError, friendly_name
from openlp.plugins.librarysync.lib.transfer import duplicate_key


def storage_url(profile, folder):
    return Path(profile['path']).as_uri()


class LocalStream:
    """The bounded response interface consumed by the existing loopback media relay."""
    def __init__(self, path, byte_range, cancel):
        self.file = path.open('rb')
        self.cancel = cancel
        size = os.fstat(self.file.fileno()).st_size
        start, end = 0, size - 1
        self.status_code = 200
        self.headers = {}
        if byte_range:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', byte_range)
            if not match or not any(match.groups()):
                self.file.close()
                raise SyncError('Invalid media range.')
            left, right = match.groups()
            start = int(left) if left else max(0, size - int(right))
            end = min(int(right), end) if left and right else end
            if start > end or not size:
                self.status_code = 416
                self.headers['Content-Range'] = f'bytes */{size}'
                start, end = 0, -1
            else:
                self.status_code = 206
                self.headers['Content-Range'] = f'bytes {start}-{end}/{size}'
        self.remaining = max(0, end - start + 1)
        self.headers['Content-Length'] = str(self.remaining)
        self.file.seek(start)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()

    def iter_content(self, chunk_size):
        while self.remaining and not self.cancel.is_set():
            data = self.file.read(min(chunk_size, self.remaining))
            if not data:
                break
            self.remaining -= len(data)
            yield data


class LocalStorageProvider:
    def __init__(self, profile, cancel=None):
        self.root = Path(profile['path']).resolve()
        self.cancel = cancel
        if not self.root.is_dir():
            raise SyncError('The local storage folder is unavailable. Check its location and try again.')

    def path(self, item_id):
        relative = Path(item_id)
        if relative.is_absolute() or '..' in relative.parts or any(part.startswith('.') for part in relative.parts):
            raise SyncError('Choose an item inside the local storage folder.')
        path = self.root
        for part in relative.parts:
            path /= part
            if path.is_symlink():
                raise SyncError('Symbolic links are not supported in local cloud storage.')
        if not path.resolve().is_relative_to(self.root):
            raise SyncError('Choose an item inside the local storage folder.')
        return path

    def item(self, path):
        relative = path.relative_to(self.root)
        self.path(relative.as_posix())
        stat = path.stat()
        folder = path.is_dir()
        category = next((key for key, name in CATEGORIES.items()
                         if relative.parts and name.casefold() == relative.parts[0].casefold()), '')
        writable = os.access(path if folder else path.parent, os.W_OK)
        return CloudItem(
            relative.as_posix(), path.name, folder=folder, size=0 if folder else stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            created=datetime.fromtimestamp(getattr(stat, 'st_birthtime', stat.st_ctime), timezone.utc).isoformat(),
            version=f'{stat.st_ino}:{stat.st_mtime_ns}:{stat.st_size}', category=category,
            can_download=not folder and os.access(path, os.R_OK), can_upload=folder and writable,
            can_edit=writable and path != self.root, can_delete=writable and path != self.root,
            can_copy=not folder and os.access(path, os.R_OK), can_move=not folder and writable,
            parents=() if path == self.root else (relative.parent.as_posix(),),
            provider_name='Local Cloud Storage')

    def cache_account(self):
        return str(self.root)

    def sign_in(self, cancel, open_browser):
        self.folder('.')

    def disconnect(self):
        pass

    def close(self):
        pass

    def change_token(self):
        fingerprint = hashlib.sha256()
        # ponytail: poll file metadata; very large libraries should use a filesystem watcher instead.
        for directory, folders, files in os.walk(self.root, followlinks=False):
            folders[:] = sorted(name for name in folders if not name.startswith('.')
                                and not (Path(directory) / name).is_symlink())
            for name in sorted(folders + files):
                if self.cancel and self.cancel.is_set():
                    raise SyncError('Operation cancelled.')
                path = Path(directory) / name
                if name.startswith('.') or path.is_symlink():
                    continue
                stat = path.stat()
                fingerprint.update(f'{path.relative_to(self.root)}:{stat.st_mtime_ns}:{stat.st_size}'.encode())
        return fingerprint.hexdigest()

    def changes(self, token):
        current = self.change_token()
        return ([CloudChange('.', all_items=True)] if current != token else []), current

    def folder(self, folder_id, resource_key=''):
        item = self.item(self.path(folder_id))
        if not item.folder:
            raise SyncError('Choose a local folder, rather than a file.')
        return item

    def list_folder(self, folder, page_token=''):
        path = self.path(folder.id)
        items = [self.item(child) for child in path.iterdir()
                 if not child.name.startswith('.') and not child.is_symlink() and (child.is_file() or child.is_dir())]
        items.sort(key=lambda item: (not item.folder, item.name.casefold()))
        start = int(page_token or 0)
        return items[start:start + 200], str(start + 200) if start + 200 < len(items) else ''

    def type_folder(self, folder, category, create=True):
        if category not in CATEGORIES:
            raise SyncError('Choose a supported Library type.')
        current = self.folder(folder.id)
        if current.category:
            if current.category != category:
                if not create:
                    return None
                raise SyncError('Choose the matching item-type folder or the shared Library root.')
            target = current
        else:
            path = self.path(folder.id) / CATEGORIES[category]
            self.path(path.relative_to(self.root).as_posix())
            if not path.exists() and not create:
                return None
            if create:
                path.mkdir(exist_ok=True)
            target = self.item(path)
        if not target.folder:
            raise SyncError('A file is using the Library type folder name. Rename it and try again.')
        if create and not target.can_upload:
            raise SyncError('This folder is read-only. Choose a writable storage folder.')
        return target

    def find_item(self, folder, category, title, exclude='', extension=''):
        target = self.type_folder(folder, category, create=False)
        if target is None:
            return None
        items, token = self.list_folder(target)
        while token:
            page, token = self.list_folder(target, token)
            items.extend(page)
        matches = [item for item in items if item.id != exclude
                   and duplicate_key(category, item.display_name, '' if item.folder else Path(item.name).suffix) ==
                   duplicate_key(category, title, extension)]
        if len(matches) > 1:
            raise SyncError('Several items have this name. Rename the duplicates before uploading.')
        return matches[0] if matches else None

    def checked(self, item):
        current = self.item(self.path(item.id))
        if current.version != item.version:
            raise SyncError('This item changed. Refresh before trying again.')
        return self.path(item.id)

    @staticmethod
    def filename(title, suffix=''):
        title = title.strip()
        if not title or len(title) > 200 or title in ('.', '..') or any(char in title for char in '/\\\x00'):
            raise SyncError('Enter a name without path separators (up to 200 characters).')
        return (clean_filename(title).strip(' .') or 'Item') + suffix

    def create_folder(self, folder, category, name):
        if category in ('songs', 'custom'):
            raise SyncError('Songs and Custom Slides cannot contain subfolders.')
        target = self.type_folder(folder, category)
        filename = self.filename(name)
        if self.find_item(target, category, name):
            raise SyncError('An item with this name already exists.')
        path = self.path(target.id) / filename
        path.mkdir()
        return self.item(path)

    def transfer(self, source, destination, cancel, progress, check=lambda: None, overwrite=False):
        temporary = None
        try:
            with (source.open('rb') as data,
                  NamedTemporaryFile(dir=destination.parent, prefix='.librarysync-', delete=False) as output):
                temporary = Path(output.name)
                initial = os.fstat(data.fileno())
                total, copied = initial.st_size, 0
                while chunk := data.read(256 * 1024):
                    if cancel and cancel.is_set():
                        raise SyncError('Transfer cancelled.')
                    output.write(chunk)
                    copied += len(chunk)
                    progress(copied, total)
                output.flush()
                current = os.fstat(data.fileno())
                if copied != total or current.st_mtime_ns != initial.st_mtime_ns or current.st_size != total:
                    raise SyncError('The source file changed during transfer. Refresh and try again.')
            if cancel and cancel.is_set():
                raise SyncError('Transfer cancelled.')
            check()
            if overwrite:
                os.replace(temporary, destination)
            else:
                # A hard link publishes the complete file and refuses a concurrent name collision.
                os.link(temporary, destination)
        except FileExistsError as error:
            raise SyncError('An item with this name already exists. Refresh before uploading again.') from error
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def download(self, item, destination, cancel, progress):
        source = self.checked(item)
        if item.folder or not item.can_download:
            raise SyncError('This item cannot be downloaded.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.transfer(source, destination, cancel, progress, lambda: self.checked(item), overwrite=True)
        return destination

    def upload(self, folder, category, source, cancel, progress, title='', overwrite=None):
        target = self.type_folder(folder, category)
        title = title.strip() or friendly_name(source.name)
        filename = self.filename(title, source.suffix)
        existing = self.find_item(target, category, title, extension=source.suffix)
        if existing is not None and (overwrite is None or existing.id != overwrite.id):
            raise SyncError('This name already exists. Confirm overwrite before uploading.')
        if overwrite is not None and (existing is None or existing.id != overwrite.id):
            raise SyncError('The item to overwrite changed. Refresh before uploading again.')
        destination = self.checked(overwrite) if overwrite else self.path(target.id) / filename
        self.transfer(source, destination, cancel, progress,
                      (lambda: self.checked(overwrite)) if overwrite else lambda: None, overwrite=bool(overwrite))
        return self.item(destination)

    def rename(self, item, folder, title):
        source = self.checked(item)
        if source == self.root:
            raise SyncError('The storage root cannot be renamed.')
        filename = self.filename(title, '' if item.folder else source.suffix)
        if self.find_item(folder, item.category, title, exclude=item.id,
                          extension='' if item.folder else source.suffix):
            raise SyncError('An item with this name already exists.')
        destination = source.with_name(filename)
        if destination != source:
            if destination.exists():
                raise SyncError('An item with this name already exists.')
            if item.folder:
                source.rename(destination)
            else:
                os.link(source, destination)
                source.unlink()
        return self.item(destination)

    def delete(self, item):
        source = self.checked(item)
        if source == self.root:
            raise SyncError('The storage root cannot be deleted.')
        trash = self.root / '.librarysync-trash'
        if trash.is_symlink():
            raise SyncError('The local storage bin cannot be a symbolic link.')
        trash.mkdir(exist_ok=True)
        deleted = trash / uuid4().hex
        deleted.mkdir()
        source.rename(deleted / source.name)

    def copy(self, item, folder):
        source = self.checked(item)
        return self.upload(folder, item.category, source, self.cancel, lambda *args: None,
                           title=item.display_name)

    def move(self, item, folder):
        source = self.checked(item)
        target = self.type_folder(folder, item.category)
        destination = self.path(target.id) / source.name
        if source == destination:
            return item
        if item.folder or self.find_item(target, item.category, item.display_name, extension=source.suffix):
            raise SyncError('An item with this name already exists, or the item is a folder.')
        os.link(source, destination)
        source.unlink()
        return self.item(destination)

    def preview(self, item, cancel):
        path = self.checked(item)
        if cancel.is_set():
            raise SyncError('Preview cancelled.')
        if not item.folder and path.suffix.lower() in ('.xml', '.txt') and item.size <= 1024 * 1024:
            with path.open('rb') as data:
                value = data.read(1024 * 1024 + 1)
            return ('text', value) if len(value) <= 1024 * 1024 else ('none', b'')
        return 'none', b''

    def stream(self, item, byte_range, cancel):
        return LocalStream(self.checked(item), byte_range, cancel)
