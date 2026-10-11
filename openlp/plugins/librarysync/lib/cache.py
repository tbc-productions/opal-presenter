"""Account-scoped, disposable cloud listings and preview files."""
import hashlib
import json
import shutil
import time
from dataclasses import asdict, fields
from pathlib import Path
from tempfile import NamedTemporaryFile

from openlp.core.common.applocation import AppLocation
from openlp.plugins.librarysync.lib.provider import CloudItem


MAX_BYTES = 512 * 1024 * 1024
MAX_AGE = 30 * 24 * 60 * 60
MAX_LISTING = 8 * 1024 * 1024


def restore_item(data):
    if not isinstance(data, dict):
        raise ValueError('Invalid cached item')
    for field in fields(CloudItem):
        if field.name == 'parents':
            parents = data.get('parents', [])
            if not isinstance(parents, list) or not all(isinstance(parent, str) for parent in parents):
                raise ValueError('Invalid cached parents')
            data['parents'] = tuple(parents)
        elif field.name in data and type(data[field.name]) is not field.type:
            raise ValueError('Invalid cached field')
    item = CloudItem(**data)
    if not item.id or not item.name or item.size < 0:
        raise ValueError('Invalid cached item')
    return item


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class CloudCache:
    def __init__(self, profile, account):
        self.root = AppLocation.get_directory(AppLocation.CacheDir) / 'librarysync'
        connection = [profile['provider'], profile['folders']]
        self.path = self.root / digest([connection, account]) if isinstance(account, str) and account else None

    def listing_path(self, category, folder):
        return self.path / ('listing-' + digest([category, folder]) + '.cache')

    def listing(self, category, folder):
        if self.path is None:
            return None
        path = self.listing_path(category, folder)
        try:
            if path.stat().st_size > MAX_LISTING or time.time() - path.stat().st_mtime > MAX_AGE:
                return None
            data = json.loads(path.read_text(encoding='utf-8'))
            current = restore_item(data['folder'])
            items = [restore_item(item) for item in data['items']]
            token = data['token']
            if current.category not in ('', category) or not isinstance(token, str):
                return None
            cursor, outdated = data.get('changes', ''), data.get('outdated', False)
            if not isinstance(cursor, str) or not isinstance(outdated, bool):
                return None
            path.touch()
            return current, items, token, cursor, outdated
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def save_listing(self, category, folder, result, changes='', outdated=False):
        current, items, token = result
        data = json.dumps({'folder': asdict(current), 'items': [asdict(item) for item in items],
                           'token': token, 'changes': changes, 'outdated': outdated})
        if len(data.encode()) <= MAX_LISTING and self.path is not None:
            self.store(self.listing_path(category, folder), data.encode())

    def preview_path(self, item, cover, slides=False):
        if self.path is None or not (item.version or item.checksum or item.modified):
            return None
        key = [item.id, item.category, item.version, item.checksum, item.modified, item.size, cover]
        if slides:
            key.append('slides')
        return self.path / ('preview-' + digest(key) + '.cache')

    def preview(self, item, destination, cover=False, slides=False):
        path = self.preview_path(item, cover, slides)
        if path is None:
            return False
        try:
            if time.time() - path.stat().st_mtime > MAX_AGE or (
                    not cover and not slides and path.stat().st_size != item.size):
                return False
            shutil.copyfile(path, destination)
            path.touch()
            return True
        except OSError:
            return False

    def save_preview(self, item, source, cover=False, slides=False):
        path = self.preview_path(item, cover, slides)
        if path is not None:
            self.store(path, source=source)

    def store(self, path, data=None, source=None):
        temporary = None
        try:
            size = source.stat().st_size if source is not None else len(data)
            if size > MAX_BYTES:
                return
            self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
            with NamedTemporaryFile(dir=self.path, delete=False) as output:
                temporary = Path(output.name)
                if source is not None:
                    with source.open('rb') as input_file:
                        shutil.copyfileobj(input_file, output)
                else:
                    output.write(data)
            temporary.replace(path)
            self.prune()
        except OSError:
            pass  # A disposable cache must never prevent browsing or viewing a cloud item.
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def prune(self):
        files = []
        total = 0
        for path in self.root.glob('*/*.cache'):
            try:
                info = path.stat()
                if time.time() - info.st_mtime > MAX_AGE:
                    path.unlink(missing_ok=True)
                else:
                    files.append((info.st_mtime, path, info.st_size))
                    total += info.st_size
            except OSError:
                continue
        for _, path, size in sorted(files):
            if total <= MAX_BYTES:
                break
            try:
                path.unlink(missing_ok=True)
                total -= size
            except OSError:
                continue

    def clear_listings(self):
        if self.path is not None:
            for path in self.path.glob('listing-*.cache'):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def clear(self):
        if self.path is not None:
            shutil.rmtree(self.path, ignore_errors=True)
