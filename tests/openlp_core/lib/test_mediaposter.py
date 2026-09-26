"""Checks for full-resolution frame capture used by presentation exports."""
from openlp.core.lib.mediaposter import video_frame
from tests.utils.constants import RESOURCE_PATH


def test_video_frame_decodes_source_pixels():
    frame = video_frame(RESOURCE_PATH / 'media' / 'mp4_file.mp4')

    assert not frame.isNull()
    assert frame.width() == 400
    assert frame.height() >= 224


def test_video_frame_missing_file_returns_empty_image(tmp_path):
    frame = video_frame(tmp_path / 'missing.mp4', timeout_ms=100)

    assert frame.isNull()
