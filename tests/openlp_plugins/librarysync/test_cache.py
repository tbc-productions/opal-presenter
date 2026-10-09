"""Persistent snapshots stay account-scoped, bounded and disposable."""
import os
import time
from dataclasses import replace
from pathlib import Path

import pytest

from openlp.plugins.librarysync.lib.cache import CloudCache
from openlp.plugins.librarysync.lib.provider import CloudItem


@pytest.fixture
def profile():
    return {'provider': 'google-drive', 'folders': [{'id': 'shared', 'name': 'Organisation'}]}


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    monkeypatch.setattr('openlp.plugins.librarysync.lib.cache.AppLocation.get_directory', lambda kind: tmp_path)
    return tmp_path


def test_listing_survives_restart_without_credentials_and_preserves_parents(profile, cache_root):
    cache = CloudCache(profile, 'account-one')
    folder = CloudItem('songs', 'Songs', folder=True, category='songs', parents=('shared',))
    item = CloudItem('song', 'Welcome.xml', category='songs', version='1', can_edit=True)
    cache.save_listing('songs', 'shared', (folder, [item], 'page-two'))
    restored = CloudCache(profile, 'account-one')
    assert restored.listing('songs', 'shared') == (folder, [item], 'page-two', '', False)
    assert 'account-one' not in str(cache.path)
    assert not CloudCache(profile, 'account-two').listing('songs', 'shared')
    assert not CloudCache({**profile, 'provider': 'another-provider'}, 'account-one').listing('songs', 'shared')
    assert not CloudCache({**profile, 'folders': [{'id': 'other'}]}, 'account-one').listing('songs', 'shared')
    assert not CloudCache(profile, '').listing('songs', 'shared')


@pytest.mark.parametrize('bad', [
    'invalid json', '[]', '{"folder": null}',
    '{"folder": {"id":"songs", "name":"Songs", "size":"large"}}'])
def test_corrupt_listing_is_a_cache_miss(profile, cache_root, bad):
    cache = CloudCache(profile, 'account')
    cache.path.mkdir(parents=True)
    cache.listing_path('songs', 'shared').write_text(bad)
    assert cache.listing('songs', 'shared') is None


def test_preview_reuse_checks_version_and_keeps_active_copy_after_clear(profile, cache_root, tmp_path):
    source, destination = tmp_path / 'source.png', tmp_path / 'active.png'
    source.write_bytes(b'image contents')
    item = CloudItem('image', 'Welcome.png', category='images', size=source.stat().st_size, version='1')
    cache = CloudCache(profile, 'account')
    cache.save_preview(item, source)
    assert CloudCache(profile, 'account').preview(item, destination)
    assert destination.read_bytes() == source.read_bytes()
    assert not cache.preview(replace(item, version='2'), destination)
    assert not CloudCache(profile, 'other-account').preview(item, destination)
    assert not cache.preview(replace(item, version=''), destination)
    cache.clear()
    assert destination.read_bytes() == source.read_bytes()
    assert not cache.preview(item, destination)


def test_corrupt_preview_size_is_a_cache_miss(profile, cache_root, tmp_path):
    cache = CloudCache(profile, 'account')
    item = CloudItem('image', 'Welcome.png', category='images', size=20, version='1')
    cache.path.mkdir(parents=True)
    cache.preview_path(item, False).write_bytes(b'incomplete')
    assert not cache.preview(item, tmp_path / 'preview.png')


def test_cache_evicts_oldest_files_across_connections_and_expires_unused_files(profile, cache_root, monkeypatch):
    monkeypatch.setattr('openlp.plugins.librarysync.lib.cache.MAX_BYTES', 10)
    cache = CloudCache(profile, 'account')
    other = CloudCache(profile, 'other-account')
    cache.store(cache.path / 'old.cache', b'123456')
    os.utime(cache.path / 'old.cache', (time.time() - 100, time.time() - 100))
    other.store(other.path / 'new.cache', b'123456')
    assert not (cache.path / 'old.cache').exists()
    assert (other.path / 'new.cache').exists()
    expired = other.path / 'new.cache'
    os.utime(expired, (0, 0))
    cache.prune()
    assert not expired.exists()
    cache.store(cache.path / 'oversized.cache', b'12345678901')
    assert not (cache.path / 'oversized.cache').exists()


def test_invalidation_removes_listings_without_other_accounts_or_previews(profile, cache_root, tmp_path):
    cache, other = CloudCache(profile, 'account'), CloudCache(profile, 'other')
    folder = CloudItem('songs', 'Songs', folder=True, category='songs')
    cache.save_listing('songs', 'shared', (folder, [], ''))
    other.save_listing('songs', 'shared', (folder, [], ''))
    source = tmp_path / 'song.xml'
    source.write_bytes(b'song')
    item = CloudItem('song', 'song.xml', category='songs', size=4, version='1')
    cache.save_preview(item, source)
    cache.clear_listings()
    assert cache.listing('songs', 'shared') is None
    assert other.listing('songs', 'shared') is not None
    assert cache.preview(item, tmp_path / 'active.xml')


def test_cache_write_failure_does_not_block_cloud_operations(profile, cache_root, monkeypatch):
    cache = CloudCache(profile, 'account')
    monkeypatch.setattr(Path, 'mkdir', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('Read only')))
    cache.save_listing('songs', 'shared', (CloudItem('songs', 'Songs', folder=True), [], ''))
    assert not cache.listing('songs', 'shared')
