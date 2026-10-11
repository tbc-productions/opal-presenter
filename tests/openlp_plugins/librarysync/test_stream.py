"""Native media previews relay ranges over loopback without putting credentials in player URLs."""
from threading import Event, Thread
from unittest.mock import MagicMock

import requests

from opal.plugins.librarysync.lib.provider import CloudItem
from opal.plugins.librarysync.lib.stream import MediaStream


def test_loopback_relay_supports_ranges_head_and_cancellation():
    provider = MagicMock()
    reply = MagicMock(status_code=206, headers={
        'Content-Type': 'video/mp4', 'Content-Length': '5', 'Content-Range': 'bytes 5-9/10'})
    reply.iter_content.return_value = [b'67890']
    reply.__enter__.return_value = reply
    provider.stream.return_value = reply
    cancel = Event()
    item = CloudItem('id', 'Opening video.mp4', size=10, category='media')
    stream = MediaStream(provider, item, cancel)
    thread = Thread(target=stream.serve)
    thread.start()
    try:
        assert stream.url.startswith('http://127.0.0.1:')
        assert 'access_token' not in stream.url
        assert requests.head(stream.url, timeout=2).headers['Content-Length'] == '10'
        result = requests.get(stream.url, headers={'Range': 'bytes=5-9'}, timeout=2)
        assert result.status_code == 206
        assert result.content == b'67890'
        assert result.headers['Content-Range'] == 'bytes 5-9/10'
        assert 'Authorization' not in result.request.headers
        provider.stream.assert_called_once_with(item, 'bytes=5-9', cancel)
        assert requests.get(stream.url, headers={'Range': 'bytes=5-9,10-15'}, timeout=2).status_code == 416
        assert requests.get(stream.url.rsplit('/', 2)[0] + '/other-route', timeout=2).status_code == 404
        assert provider.stream.call_count == 1
    finally:
        cancel.set()
        thread.join(timeout=3)
    assert not thread.is_alive()
