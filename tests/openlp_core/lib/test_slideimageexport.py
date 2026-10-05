"""Image exports retain slide numbering and never publish incomplete renders."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui

from openlp.core.lib.presentationexport import PresentationPage
from openlp.core.lib.slideimageexport import render_slide_images


@pytest.fixture
def renderer(mock_settings):
    display = MagicMock(_is_initialised=True)
    callbacks = {}
    display.display_watcher.register_event_listener.side_effect = lambda name, cb, _: callbacks.update({name: cb})

    def run(action, *args, **kwargs):
        if action == 'waitForDesignPreview':
            callbacks[kwargs['return_event_name']](QtCore.QJsonValue(args[0]))

    display.run_in_display.side_effect = run
    pixmap = QtGui.QPixmap(128, 72)
    pixmap.fill(QtGui.QColor('#234567'))
    pixmap.setDevicePixelRatio(2)
    display.webview.grab.return_value = pixmap
    with patch('openlp.core.lib.slideimageexport.DisplayWindow', return_value=display), \
            patch('openlp.core.lib.slideimageexport.ScreenList', return_value=SimpleNamespace(
                current=SimpleNamespace(display_geometry=QtCore.QRect(0, 0, 64, 36)))):
        yield display


def test_slide_names_and_numbering(tmp_path, renderer):
    pages = [PresentationPage(section_name=title, section_index=section, theme=object(), html_text=f'Text {index}',
                              html_footer=f'Footer {index}')
             for index, (title, section) in enumerate([
                 ('Welcome', 0), ('Welcome', 0), ('Welcome', 0), ('Welcome', 1), ('Path/Title', 2)])]
    with patch('openlp.core.lib.slideimageexport.service_pages', return_value=pages):
        images = render_slide_images([], tmp_path)

    assert [name for _, name in images] == [
        'Welcome.png', 'Welcome (2).png', 'Welcome (3).png', 'Welcome.png', 'Path_Title.png']
    assert len({path for path, _ in images}) == 5
    assert images[-1][0].name == 'Path_Title.png'
    for path, _ in images:
        image = QtGui.QImage(str(path))
        assert image.size() == QtCore.QSize(64, 36)
        assert image.pixelColor(0, 0).name() == '#234567'
    assert renderer.set_theme.call_args_list[0].args[0] is pages[0].theme
    assert renderer.load_verses.call_args_list[0].args[0][0]['footer'] == 'Footer 0'
    renderer.deleteLater.assert_called_once()


def test_renderer_timeout_never_saves_a_partial_image(tmp_path, renderer):
    page = PresentationPage(section_name='Welcome', section_index=0, theme=object())
    with patch('openlp.core.lib.slideimageexport.service_pages', return_value=[page]), \
            patch('openlp.core.lib.slideimageexport.wait_for', side_effect=[True, False]):
        with pytest.raises(RuntimeError, match='finish rendering'):
            render_slide_images([], tmp_path)
    assert list(tmp_path.rglob('*.png')) == []
    renderer.deleteLater.assert_called_once()
