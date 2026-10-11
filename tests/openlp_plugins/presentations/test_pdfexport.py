"""PDF conversion must preserve source files and existing exports."""
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from opal.plugins.presentations.lib.pdfexport import export_to_pdf, PdfExportWorker, _export_mac, _export_libreoffice, \
    _export_windows, pdf_export_error_text, PdfExportCancelled, _run_libreoffice


@pytest.mark.parametrize('controller', ['Keynote', 'PowerPointMac', 'Impress', 'maclo', 'Powerpoint'])
def test_export_preserves_source_and_existing_pdf(tmp_path, controller):
    source = tmp_path / 'Sunday.pptx'
    source.write_bytes(b'original presentation')
    source.with_suffix('.pdf').write_bytes(b'existing PDF')
    copies = []

    def export(name, copy, output, *args):
        assert name == controller
        assert copy != source
        assert copy.read_bytes() == b'original presentation'
        copies.append(copy)
        output.write_bytes(b'%PDF-1.7\nconverted slides')

    with patch('opal.plugins.presentations.lib.pdfexport._export_mac', side_effect=export), \
            patch('opal.plugins.presentations.lib.pdfexport._export_windows', side_effect=export), \
            patch('opal.plugins.presentations.lib.pdfexport._export_libreoffice', side_effect=export), \
            patch('opal.plugins.presentations.lib.pdfexport.is_win', return_value=controller == 'Powerpoint'):
        output = export_to_pdf(controller, source)
    assert output == tmp_path / 'Sunday (2).pdf'
    assert output.read_bytes().startswith(b'%PDF-')
    assert source.read_bytes() == b'original presentation'
    assert source.with_suffix('.pdf').read_bytes() == b'existing PDF'
    assert not copies[0].exists()


@pytest.mark.parametrize('failure', ['exception', 'missing', 'invalid'])
def test_export_failure_does_not_publish_pdf(tmp_path, failure):
    source = tmp_path / 'Sunday.odp'
    source.write_bytes(b'original presentation')

    def export(name, copy, output, *args):
        if failure == 'exception':
            raise RuntimeError('Application failed')
        if failure == 'invalid':
            output.write_bytes(b'not a PDF')

    with patch('opal.plugins.presentations.lib.pdfexport._export_mac', side_effect=export), \
            pytest.raises((RuntimeError, FileNotFoundError)):
        export_to_pdf('Keynote', source)
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes() == b'original presentation'


def test_mac_export_passes_paths_as_arguments(tmp_path):
    source = tmp_path / 'quote" and spaces.pptx'
    destination = tmp_path / 'slides.pdf'
    applescript, objc = MagicMock(), MagicMock()
    with patch.dict('sys.modules', {'applescript': applescript, 'objc': objc}), \
            patch('opal.plugins.presentations.lib.pdfexport.subprocess.run') as run:
        _export_mac('PowerPointMac', source, destination)
    run.assert_called_once_with(['/usr/bin/open', '-g', '-b', 'com.microsoft.Powerpoint', str(source)],
                                check=True, capture_output=True, text=True, timeout=30)
    script = applescript.AppleScript.call_args.args[0]
    assert str(source) not in script
    assert 'save targetDocument in outputFile as save as PDF' in script
    applescript.AppleScript.return_value.call.assert_called_once_with(
        'export_pdf', source.name, source.stem, str(destination))


def test_error_text_exposes_subprocess_stderr():
    import subprocess
    error = subprocess.CalledProcessError(1, ['/usr/bin/open'], stderr=b'Unable to find application\n')
    assert pdf_export_error_text(error) == 'Unable to find application'


def test_error_text_explains_automation_permissions():
    error = RuntimeError('Not authorised')
    error.number = -1743
    assert 'Privacy & Security → Automation' in pdf_export_error_text(error)


def test_export_uses_library_name_for_hashed_source(tmp_path):
    source = tmp_path / ('a' * 64 + '.pptx')
    source.write_bytes(b'original presentation')
    (tmp_path / 'Sunday sermon.pdf').write_bytes(b'existing PDF')

    def export(name, copy, output, *args):
        output.write_bytes(b'%PDF-1.7 converted')

    with patch('opal.plugins.presentations.lib.pdfexport._export_mac', side_effect=export):
        output = export_to_pdf('Keynote', source, output_name='Sunday sermon.pptx')
    assert output.name == 'Sunday sermon (2).pdf'
    assert source.read_bytes() == b'original presentation'


def test_libreoffice_uses_isolated_profile(tmp_path):
    source = tmp_path / 'copy.odp'
    output = tmp_path / 'converted.pdf'

    def run(command, cancel_event):
        assert f'-env:UserInstallation={(tmp_path / "profile").as_uri()}' in command
        assert 'pdf:impress_pdf_Export' in command
        assert '--headless' in command
        source.with_suffix('.pdf').write_bytes(b'%PDF-1.7')

    with patch('opal.plugins.presentations.lib.pdfexport._run_libreoffice', side_effect=run):
        _export_libreoffice('maclo', source, output, tmp_path)
    assert output.read_bytes() == b'%PDF-1.7'


def test_cancel_after_native_export_discards_output(tmp_path):
    source = tmp_path / 'sermon.pptx'
    source.write_bytes(b'original')
    cancel_event = Event()
    temporary_files = []

    def export(name, copy, output, *args):
        output.write_bytes(b'%PDF-1.7')
        temporary_files.extend([copy, output])
        cancel_event.set()

    with patch('opal.plugins.presentations.lib.pdfexport._export_mac', side_effect=export), \
            pytest.raises(PdfExportCancelled):
        export_to_pdf('PowerPointMac', source, cancel_event=cancel_event)
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes() == b'original'
    assert all(not path.exists() for path in temporary_files)


def test_cancel_during_publication_removes_only_new_output(tmp_path):
    import shutil
    source = tmp_path / 'sermon.pptx'
    source.write_bytes(b'original')
    existing = source.with_suffix('.pdf')
    existing.write_bytes(b'existing PDF')
    cancel_event = Event()
    real_copy = shutil.copyfileobj

    def export(name, copy, output, *args):
        output.write_bytes(b'%PDF-1.7')

    def publish(source_file, target_file):
        real_copy(source_file, target_file)
        cancel_event.set()

    with patch('opal.plugins.presentations.lib.pdfexport._export_mac', side_effect=export), \
            patch('opal.plugins.presentations.lib.pdfexport.shutil.copyfileobj', side_effect=publish), \
            pytest.raises(PdfExportCancelled):
        export_to_pdf('Keynote', source, cancel_event=cancel_event)
    assert existing.read_bytes() == b'existing PDF'
    assert not (tmp_path / 'sermon (2).pdf').exists()


def test_cancelled_worker_does_not_start_export():
    controller = MagicMock()
    controller.name = 'Keynote'
    worker = PdfExportWorker(controller, Path('missing.pptx'))
    worker.cancel()
    worker.run()
    assert worker.cancelled
    assert worker.error is None
    assert worker.output is None


def test_cancel_terminates_and_reaps_isolated_process():
    import subprocess
    import sys
    processes = []
    real_popen = subprocess.Popen

    def start(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    cancel_event = Event()
    cancel_event.set()
    with patch('opal.plugins.presentations.lib.pdfexport.subprocess.Popen', side_effect=start), \
            pytest.raises(PdfExportCancelled):
        _run_libreoffice([sys.executable, '-c', 'import time; time.sleep(60)'], cancel_event)
    assert len(processes) == 1
    assert processes[0].poll() is not None


def test_worker_reports_export_failure():
    controller = MagicMock(name='controller')
    controller.name = 'Keynote'
    worker = PdfExportWorker(controller, Path('slides.pptx'))
    error = RuntimeError('Cannot export')
    with patch('opal.plugins.presentations.lib.pdfexport.export_to_pdf', side_effect=error):
        worker.run()
    assert worker.error is error
    assert worker.output is None


@pytest.mark.parametrize('controller', ['Powerpoint', 'Impress'])
@pytest.mark.parametrize('failed', [False, True])
def test_windows_export_closes_only_export_document_and_releases_com(tmp_path, controller, failed):
    com = MagicMock()
    win32 = MagicMock()
    application = win32.client.Dispatch.return_value
    document = (application.Presentations.Open.return_value if controller == 'Powerpoint' else
                application.createInstance.return_value.loadComponentFromURL.return_value)
    if failed:
        if controller == 'Powerpoint':
            document.ExportAsFixedFormat.side_effect = RuntimeError('Export failed')
        else:
            document.storeToURL.side_effect = RuntimeError('Export failed')
    source, output = tmp_path / 'copy.pptx', tmp_path / 'converted.pdf'
    with patch.dict('sys.modules', {'pythoncom': com, 'win32com': win32, 'win32com.client': win32.client}):
        if failed:
            with pytest.raises(RuntimeError):
                _export_windows(controller, source, output)
        else:
            _export_windows(controller, source, output)
    com.CoInitialize.assert_called_once()
    com.CoUninitialize.assert_called_once()
    application.Quit.assert_not_called()
    if controller == 'Powerpoint':
        application.Presentations.Open.assert_called_once_with(str(source), ReadOnly=True, WithWindow=False)
        document.Close.assert_called_once()
        document.ExportAsFixedFormat.assert_called_once_with(str(output), 2)
    else:
        document.close.assert_called_once_with(True)
        document.storeToURL.assert_called_once()
