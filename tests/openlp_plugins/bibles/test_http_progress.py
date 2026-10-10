"""Bible downloads keep GUI timers running and report failures on the GUI thread."""
from threading import Event, get_ident
from unittest.mock import MagicMock, patch

from PySide6 import QtCore

from openlp.plugins.bibles.lib.importers.http import get_soup_for_bible_ref


def test_download_keeps_gui_timers_running(qapp, registry):
    registry.register('application', MagicMock())
    gui_thread = get_ident()
    release = Event()
    download_threads = []
    timer_threads = []

    def download(url, headers, proxy):
        download_threads.append(get_ident())
        assert release.wait(2), 'GUI timer did not run during the download'
        return '<html><body><p>Genesis</p></body></html>'

    def tick():
        timer_threads.append(get_ident())
        release.set()

    QtCore.QTimer.singleShot(20, tick)
    with patch('openlp.plugins.bibles.lib.importers.http.get_proxy_settings', return_value={}), \
            patch('openlp.plugins.bibles.lib.importers.http.get_web_page', side_effect=download):
        soup = get_soup_for_bible_ref('https://example.com/bible')
    assert soup.get_text() == 'Genesis'
    assert download_threads and download_threads[0] != gui_thread
    assert timer_threads == [gui_thread]


def test_download_failure_is_reported_on_gui_thread(qapp, registry):
    registry.register('application', MagicMock())
    error_threads = []
    with patch('openlp.plugins.bibles.lib.importers.http.get_proxy_settings', return_value={}), \
            patch('openlp.plugins.bibles.lib.importers.http.get_web_page', side_effect=ConnectionError), \
            patch('openlp.plugins.bibles.lib.importers.http.send_error_message',
                  side_effect=lambda error: error_threads.append((error, get_ident()))):
        assert get_soup_for_bible_ref('https://example.com/bible') is None
    assert error_threads == [('download', get_ident())]
