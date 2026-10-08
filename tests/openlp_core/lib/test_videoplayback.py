"""Playback proxies work without changing the media saved in portable designs."""
import subprocess
from unittest.mock import patch

import imageio_ffmpeg
import pytest

from openlp.core.lib.designmedia import media_to_source, materialise_media
from openlp.core.lib.videoplayback import video_playback_path


@pytest.fixture
def assets(tmp_path):
    with patch('openlp.core.lib.designmedia.asset_root', return_value=tmp_path / 'managed'), \
            patch('openlp.core.lib.videoplayback.asset_root', return_value=tmp_path / 'managed'):
        yield tmp_path


def test_mp4_proxy_is_decodable_cached_and_keeps_original(assets):
    original = assets / 'clip.mp4'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'color=c=orange:s=320x180:r=24', '-t', '0.2', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(original)], check=True, capture_output=True)
    source, _ = media_to_source(original)
    original_bytes = original.read_bytes()
    playback = video_playback_path(source)
    assert playback.suffix == '.webm'
    assert playback.parent.name == 'playback'
    subprocess.run([ffmpeg, '-nostdin', '-loglevel', 'error', '-i', str(playback),
                    '-f', 'null', '-'], check=True, capture_output=True)
    assert materialise_media(source).read_bytes() == original_bytes
    with patch('openlp.core.lib.videoplayback.QtCore.QProcess') as process, \
            patch('openlp.core.lib.videoplayback.cache_media') as cache:
        assert video_playback_path(source) == playback
    process.assert_not_called()
    cache.assert_not_called()


def test_failed_conversion_removes_partial_playback_and_retains_original(assets):
    original = assets / 'broken.mp4'
    original.write_bytes(b'not a video')
    with pytest.raises(ValueError, match='could not be prepared'):
        video_playback_path(original)
    assert list((assets / 'managed' / 'playback').iterdir()) == []
    assert original.read_bytes() == b'not a video'


def test_browser_video_format_does_not_require_conversion(assets):
    original = assets / 'clip.webm'
    original.write_bytes(b'webm original')
    with patch('openlp.core.lib.videoplayback.QtCore.QProcess') as process:
        assert video_playback_path(original) == original
    process.assert_not_called()
