"""Playback proxies work without changing the media saved in portable designs."""
import re
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
    managed = materialise_media(source)
    legacy = managed.parent.parent / 'playback' / (managed.stem + '.webm')
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b'older low-quality playback')
    playback = video_playback_path(source)
    assert playback.suffix == '.webm'
    assert playback.parent.name == 'playback'
    assert playback != legacy
    assert legacy.read_bytes() == b'older low-quality playback'
    subprocess.run([ffmpeg, '-nostdin', '-loglevel', 'error', '-i', str(playback),
                    '-f', 'null', '-'], check=True, capture_output=True)
    assert materialise_media(source).read_bytes() == original_bytes
    with patch('openlp.core.lib.videoplayback.QtCore.QProcess') as process, \
            patch('openlp.core.lib.videoplayback.cache_media') as cache:
        assert video_playback_path(source) == playback
    process.assert_not_called()
    cache.assert_not_called()


def test_playback_preserves_source_resolution_and_fine_detail(assets):
    original = assets / 'detail.mp4'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=s=2048x1152:r=24', '-t', '0.21', '-c:v', 'libx264', '-crf', '10',
                    str(original)], check=True, capture_output=True)
    playback = video_playback_path(original)
    frame = subprocess.run([ffmpeg, '-nostdin', '-loglevel', 'error', '-i', str(playback),
                            '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                           check=True, capture_output=True).stdout
    assert len(frame) == 2048 * 1152 * 3  # No Full HD cap or change to the source's proportions.
    comparison = subprocess.run([
        ffmpeg, '-nostdin', '-hide_banner', '-i', str(original), '-i', str(playback), '-lavfi',
        # WebM timestamps round to milliseconds. Compare corresponding frames, not neighbouring timestamps.
        '[0:v]settb=AVTB,setpts=N/TB[a];[1:v]settb=AVTB,setpts=N/TB[b];[a][b]psnr',
        '-fps_mode', 'passthrough', '-f', 'null', '-'], check=True, capture_output=True, text=True)
    score = re.search(r'PSNR .*average:([\d.]+)', comparison.stderr)
    assert score and float(score[1]) > 45


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
