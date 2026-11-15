# -*- coding: utf-8 -*-

##########################################################################
# Opal Presenter - Open Source Lyrics Projection                         #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
Regression tests for work that must not run, or fail, outside the GUI thread.
"""
import threading
import zipfile
import zlib
from unittest.mock import MagicMock, patch

from PySide6 import QtCore

from opal.core.common.registry import Registry
from opal.core.ui.media.mediaplayer import MediaPlayer, _FFmpegErrorRelay
from opal.plugins.media.lib.mediaitem import MediaLengthWorker, MediaMediaItem, ThumbnailGeneratorWorker


def _run_in_thread(function):
    """Run a callable in another thread and wait for it to return."""
    thread = threading.Thread(target=function)
    thread.start()
    thread.join(5)
    assert not thread.is_alive()


def _media_item():
    """A media library item without its widgets."""
    Registry().register('service_list', MagicMock())
    Registry().register('main_window', MagicMock())
    Registry().register('live_controller', MagicMock())
    with patch('opal.plugins.media.lib.mediaitem.FolderLibraryItem._setup'), \
            patch('opal.plugins.media.lib.mediaitem.MediaMediaItem.setup_item'):
        media_item = MediaMediaItem(None, MagicMock())
    media_item.manager = MagicMock()
    return media_item


def test_exception_hook_in_worker_thread_shows_dialog_in_gui_thread(qapp, qtbot):
    """
    An uncaught exception in a worker thread must not build the exception dialog in that thread
    """
    # GIVEN: An application and a record of where the dialog is shown
    gui_thread = threading.current_thread()
    shown = []
    with patch.object(qapp, '_show_exception_report',
                      side_effect=lambda message: shown.append((threading.current_thread(), message))):
        # WHEN: The exception hook is called from another thread
        def raise_in_worker():
            try:
                raise RuntimeError('boom in worker')
            except RuntimeError as error:
                qapp.hook_exception(type(error), error, error.__traceback__)

        _run_in_thread(raise_in_worker)

        # THEN: Nothing is shown from the worker thread, and the report arrives in the GUI thread
        assert shown == []
        qtbot.waitUntil(lambda: len(shown) == 1, timeout=2000)
    assert shown[0][0] is gui_thread
    assert 'boom in worker' in shown[0][1]


def test_exception_hook_does_not_nest_dialogs(qapp):
    """
    A second exception raised while the exception dialog is open must not open another event loop
    """
    # GIVEN: An application whose exception dialog raises another exception while it is open
    with patch('opal.core.app.ExceptionForm') as MockedExceptionForm, \
            patch.object(qapp, 'set_normal_cursor'):
        form = MockedExceptionForm.return_value
        form.exec.side_effect = lambda: qapp.hook_exception(ValueError, ValueError('second'), None)

        # WHEN: The exception hook is called
        qapp.hook_exception(RuntimeError, RuntimeError('first'), None)

    # THEN: The dialog was run once only
    form.exec.assert_called_once_with()


def test_service_load_worker_reports_corrupt_stream(tmp_path):
    """
    A corrupt compressed stream must be reported as a failed load, not escape the worker
    """
    from opal.core.ui.servicemanager import ServiceLoadWorker
    # GIVEN: A service archive whose media entry cannot be decompressed
    path = tmp_path / 'Damaged.osz'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('service_data.osj', '[]')
        archive.writestr('media.mp4', b'media')
    worker = ServiceLoadWorker(path, tmp_path / 'extracted')
    failed, loaded, finished = MagicMock(), MagicMock(), MagicMock()
    worker.failed.connect(failed)
    worker.loaded.connect(loaded)
    worker.quit.connect(finished)

    # WHEN: Extraction raises an error that is not a BadZipFile
    with patch('opal.core.ui.servicemanager.service_payload', return_value='service_data.osj'), \
            patch('opal.core.ui.servicemanager.validate_service'), \
            patch('opal.core.ui.servicemanager.zipfile.ZipFile.extract',
                  side_effect=zlib.error('Error -3 while decompressing data: invalid block type')):
        worker.start()

    # THEN: The failure is reported and the worker still finishes
    failed.assert_called_once_with(str(path))
    loaded.assert_not_called()
    finished.assert_called_once_with()


def test_media_length_result_is_queued_to_bound_slot(settings):
    """
    The media length result updates the service list, so it must be queued to a bound GUI-thread slot
    """
    # GIVEN: A media item and a service item
    media_item = _media_item()
    service_item = MagicMock(unique_identifier='item-1')

    # WHEN: A media length probe is queued
    with patch('opal.plugins.media.lib.mediaitem.run_thread') as mocked_run_thread:
        media_item._queue_media_length_probe(service_item, 'video.mp4')

    # THEN: The worker knows its item and its signal is wired through queued_connections to a bound method
    worker = mocked_run_thread.call_args.args[0]
    assert isinstance(worker, MediaLengthWorker)
    assert (worker.service_item_id, worker.media_path) == ('item-1', 'video.mp4')
    (signal, slot), = mocked_run_thread.call_args.kwargs['queued_connections']
    assert slot == media_item._apply_media_length_probe_result
    assert slot.__self__ is media_item


def test_media_length_worker_emits_item_length_and_path():
    """
    The media length worker reports which service item and file its result belongs to
    """
    # GIVEN: A worker for a file
    worker = MediaLengthWorker('video.mp4', 'item-1')
    ready = MagicMock()
    worker.media_length_ready.connect(ready)

    # WHEN: The length is read, and then when reading it fails
    with patch('opal.plugins.media.lib.mediaitem.media_info') as mocked_media_info:
        mocked_media_info.return_value.get_media_duration.return_value = 4200
        worker.start()
        mocked_media_info.return_value.get_media_duration.side_effect = OSError('unreadable')
        worker.start()

    # THEN: Both results carry the item identifier and the path
    assert [call.args for call in ready.call_args_list] == [('item-1', 4200, 'video.mp4'), ('item-1', 0, 'video.mp4')]


def test_thumbnail_generation_can_be_queued_while_running(settings):
    """
    Queueing thumbnails while an earlier batch is still running must not reuse its thread name
    """
    # GIVEN: A media item with pending thumbnails and an application that tracks worker threads
    media_item = _media_item()
    Registry().remove('application')
    application = MagicMock(worker_threads={})
    Registry().register('application', application)
    started = []

    def fake_run_thread(worker, thread_name, **kwargs):
        # run_thread() refuses a name that is still registered
        assert thread_name not in application.worker_threads
        application.worker_threads[thread_name] = {'thread': MagicMock(), 'worker': worker}
        started.append((worker, kwargs))

    # WHEN: Thumbnails are queued twice without the first worker having finished
    with patch.object(media_item, '_collect_pending_thumbnails',
                      return_value=[('video.mp4', 'video.png', MagicMock())]), \
            patch('opal.plugins.media.lib.mediaitem.run_thread', side_effect=fake_run_thread):
        media_item._queue_thumbnail_generation()
        media_item._queue_thumbnail_generation()

    # THEN: Two workers were started under different names, and the first was asked to stop
    assert len(application.worker_threads) == 2
    (first, first_kwargs), (second, _) = started
    assert first._cancelled.is_set() and not second._cancelled.is_set()
    (signal, slot), = first_kwargs['queued_connections']
    assert slot == media_item._on_thumbnail_generated


def test_thumbnail_worker_stops_between_items():
    """
    A stopped thumbnail worker finishes without generating the remaining thumbnails
    """
    # GIVEN: A stopped worker with items to process
    worker = ThumbnailGeneratorWorker([('a.mp4', 'a.png', None), ('b.mp4', 'b.png', None)])
    finished = MagicMock()
    worker.quit.connect(finished)
    worker.stop()

    # WHEN: The worker runs
    with patch('opal.plugins.media.lib.mediaitem.media_info') as mocked_media_info:
        worker.start()

    # THEN: No thumbnails are generated and the worker still quits
    mocked_media_info.return_value.create_media_thumbnail.assert_not_called()
    finished.assert_called_once_with()


def test_ffmpeg_error_from_decoder_thread_is_handled_in_gui_thread(qapp, qtbot):
    """
    FFmpeg errors are logged from decoder threads; handling them shows a dialog, so it must be queued
    """
    # GIVEN: The Qt message handler that MediaPlayer installs, and a record of where errors are handled
    gui_thread = threading.current_thread()
    handled = []
    installed = []
    with patch.object(MediaPlayer, '_qt_handler_installed', False), \
            patch.object(MediaPlayer, '_qt_previous_handler', None), \
            patch.object(MediaPlayer, '_ffmpeg_error_relay', None), \
            patch('opal.core.ui.media.mediaplayer.QtCore.qInstallMessageHandler',
                  side_effect=lambda handler: installed.append(handler)), \
            patch.object(MediaPlayer, '_notify_ffmpeg_error',
                         side_effect=lambda text: handled.append((threading.current_thread(), text))):
        MediaPlayer._install_qt_message_handler()
        handler, = installed
        assert isinstance(MediaPlayer._ffmpeg_error_relay, _FFmpegErrorRelay)

        # WHEN: A decode error and an unrelated message are logged from another thread
        _run_in_thread(lambda: handler(QtCore.QtMsgType.QtWarningMsg, None, '[AVCodec] error while decoding'))
        _run_in_thread(lambda: handler(QtCore.QtMsgType.QtWarningMsg, None, 'unrelated message'))

        # THEN: Nothing is handled in the logging thread, and only the decode error reaches the GUI thread
        assert handled == []
        qtbot.waitUntil(lambda: len(handled) == 1, timeout=2000)
        MediaPlayer._ffmpeg_error_relay.deleteLater()
    assert handled == [(gui_thread, '[AVCodec] error while decoding')]
