"""Export separate copies of presentations without touching the operator's open deck."""
import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from uuid import uuid4

from PySide6 import QtCore

from openlp.core.common.platform import is_win
from openlp.core.common.i18n import translate

log = logging.getLogger(__name__)
PDF_EXPORT_CONTROLLERS = {'Powerpoint', 'PowerPointMac', 'Keynote', 'Impress', 'maclo'}


class PdfExportCancelled(Exception):
    """Normal cancellation, with no PDF published or failure dialog required."""


def _check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise PdfExportCancelled()


def _run_libreoffice(command, cancel_event):
    """Stop only the isolated conversion process and its children on cancellation."""
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as process:
        deadline = time.monotonic() + 900
        try:
            while True:
                _check_cancelled(cancel_event)
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(command, 900)
                try:
                    stdout, stderr = process.communicate(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        except (PdfExportCancelled, subprocess.TimeoutExpired):
            # The process owns this session; the operator's existing Impress instance is separate.
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            except ProcessLookupError:
                process.communicate()
            raise


# Paths are passed as arguments, never interpolated into AppleScript source.
MAC_EXPORT_SCRIPT = '''
on export_pdf(documentName, documentStem, outputPath)
    set outputFile to POSIX file outputPath
    with timeout of 900 seconds
        tell application "APPLICATION"
            set targetDocument to missing value
            repeat with attempt from 1 to 300
                repeat with documentIndex from 1 to count of DOCUMENTS
                    try
                        set candidateName to name of DOCUMENT documentIndex
                        if candidateName is documentName or candidateName is documentStem then
                            set targetDocument to DOCUMENT documentIndex
                            exit repeat
                        end if
                    end try
                end repeat
                if targetDocument is not missing value then exit repeat
                delay 0.2
            end repeat
            if targetDocument is missing value then error "The presentation did not open"
            try
                EXPORT
            on error errorMessage number errorNumber
                close targetDocument saving no
                error errorMessage number errorNumber
            end try
            close targetDocument saving no
        end tell
    end timeout
end export_pdf
'''


def _mac_export_script(controller_name, keynote_app=None):
    """Compile against the installed Keynote application's dictionary, including renamed apps."""
    keynote = controller_name == 'Keynote'
    app = str(keynote_app or 'Keynote') if keynote else 'Microsoft PowerPoint'
    script = MAC_EXPORT_SCRIPT.replace('APPLICATION', app.replace('\\', '\\\\').replace('"', '\\"'))
    script = script.replace('DOCUMENTS', 'documents' if keynote else 'presentations')
    script = script.replace('DOCUMENT', 'document' if keynote else 'presentation')
    script = script.replace('EXPORT', 'export targetDocument as PDF to outputFile' if keynote else
                            'save targetDocument in outputFile as save as PDF')
    return app, script


def _export_mac(controller_name, source, destination, keynote_app=None):
    """Give the application access through Launch Services, then export that specific copy."""
    app, script = _mac_export_script(controller_name, keynote_app)
    import applescript
    import objc

    launch_args = (['-a', app] if controller_name == 'Keynote' else ['-b', 'com.microsoft.Powerpoint'])
    subprocess.run(['/usr/bin/open', '-g', *launch_args, str(source)],
                   check=True, capture_output=True, text=True, timeout=30)
    if controller_name == 'PowerPointMac':
        # PowerPoint's AppleScript Save command expects a file object that already exists.
        destination.touch()
    # Match the controllers' automation identity and give each worker its own NSAppleScript.
    with objc.autorelease_pool():
        applescript.AppleScript(script).call('export_pdf', source.name, source.stem, str(destination))


def pdf_export_error_text(error):
    """Expose the application's reason rather than a subprocess command or a generic failure."""
    if isinstance(error, subprocess.TimeoutExpired):
        return translate('PresentationPlugin.PdfExport', 'The presentation application took too long to respond.')
    reason = getattr(error, 'stderr', None) or getattr(error, 'message', None) or str(error)
    if isinstance(reason, bytes):
        reason = reason.decode('utf-8', errors='replace')
    reason = str(reason).strip()
    if getattr(error, 'number', None) == -1743 or '-1743' in reason or \
            'not authorized to send apple events' in reason.lower():
        return translate('PresentationPlugin.PdfExport',
                         'macOS blocked access to the presentation application. Allow Opal Presenter to control it '
                         'in System Settings → Privacy & Security → Automation.')
    return reason or translate('PresentationPlugin.PdfExport', 'The application did not provide an error message.')


def _export_windows(controller_name, source, destination, com_name=None):
    """Create COM objects on the export worker's own apartment."""
    import pythoncom
    from win32com.client import Dispatch

    pythoncom.CoInitialize()
    document = None
    try:
        if controller_name == 'Powerpoint':
            application = Dispatch(com_name or 'PowerPoint.Application')
            document = application.Presentations.Open(str(source), ReadOnly=True, WithWindow=False)
            document.ExportAsFixedFormat(str(destination), 2)  # ppFixedFormatTypePDF
        else:
            manager = Dispatch('com.sun.star.ServiceManager')
            manager._FlagAsMethod('Bridge_GetStruct')

            def property_value(name, value):
                prop = manager.Bridge_GetStruct('com.sun.star.beans.PropertyValue')
                prop.Name, prop.Value = name, value
                return prop

            desktop = manager.createInstance('com.sun.star.frame.Desktop')
            document = desktop.loadComponentFromURL(source.as_uri(), '_blank', 0,
                                                    (property_value('Hidden', True),
                                                     property_value('ReadOnly', True)))
            if document is None:
                raise RuntimeError('Impress could not open the presentation')
            document.storeToURL(destination.as_uri(), (property_value('FilterName', 'impress_pdf_Export'),))
    finally:
        try:
            if document is not None:
                if controller_name == 'Powerpoint':
                    document.Close()
                else:
                    document.close(True)
        finally:
            pythoncom.CoUninitialize()


def _export_libreoffice(controller_name, source, destination, work_dir, cancel_event=None):
    """A separate profile prevents a command-line export being forwarded to the live application."""
    binary = ('/Applications/LibreOffice.app/Contents/MacOS/soffice' if controller_name == 'maclo' else
              shutil.which('libreoffice') or shutil.which('soffice'))
    if not binary:
        raise RuntimeError('Impress executable is unavailable')
    profile = (work_dir / 'profile').as_uri()
    _run_libreoffice([binary, f'-env:UserInstallation={profile}', '--headless', '--norestore',
                     '--convert-to', 'pdf:impress_pdf_Export', '--outdir', str(work_dir), str(source)], cancel_event)
    source.with_suffix('.pdf').rename(destination)


def export_to_pdf(controller_name, source, *, keynote_app=None, com_name=None, output_name=None, cancel_event=None):
    """Return a new PDF beside the source, preserving existing files even when names collide."""
    _check_cancelled(cancel_event)
    source = Path(source).resolve()
    name = Path(output_name).with_suffix('.pdf').name if output_name else source.with_suffix('.pdf').name
    named_destination = source.parent / name
    with TemporaryDirectory(prefix='openlp-pdf-') as directory:
        work_dir = Path(directory)
        copy = work_dir / f'openlp-conversion-{uuid4().hex}{source.suffix}'
        shutil.copy2(source, copy)
        _check_cancelled(cancel_event)
        output = work_dir / 'converted.pdf'
        if controller_name in {'Keynote', 'PowerPointMac'}:
            _export_mac(controller_name, copy, output, keynote_app)
        elif is_win() and controller_name in {'Powerpoint', 'Impress'}:
            _export_windows(controller_name, copy, output, com_name)
        elif controller_name in {'Impress', 'maclo'}:
            _export_libreoffice(controller_name, copy, output, work_dir, cancel_event)
        else:
            raise ValueError('Unsupported PDF export controller')
        _check_cancelled(cancel_event)
        # Some applications report success even when they did not write a PDF.
        if not output.is_file():
            raise RuntimeError(translate('PresentationPlugin.PdfExport',
                                         'The presentation application did not create a PDF.'))
        with output.open('rb') as exported:
            if exported.read(5) != b'%PDF-':
                raise RuntimeError('The application did not produce a PDF')
        number = 1
        while True:
            _check_cancelled(cancel_event)
            destination = named_destination if number == 1 else \
                named_destination.with_name(f'{named_destination.stem} ({number}).pdf')
            try:
                handle = destination.open('xb')
            except FileExistsError:
                number += 1
                continue
            try:
                with handle, output.open('rb') as exported:
                    shutil.copyfileobj(exported, handle)
                _check_cancelled(cancel_event)
            except Exception:
                destination.unlink(missing_ok=True)
                raise
            return destination


class PdfExportWorker(QtCore.QThread):
    """Keep application automation off the GUI thread; library writes stay on the GUI thread."""
    def __init__(self, controller, source, source_name=None):
        super().__init__()
        self.controller_name = controller.name
        self.keynote_app = getattr(controller, 'keynote_app', None)
        self.com_name = getattr(controller, 'com_obj_name', None)
        self.source = source
        self.output_name = source_name
        self.output = None
        self.error = None
        self._cancel_event = Event()

    @property
    def cancelled(self):
        return self._cancel_event.is_set()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        try:
            self.output = export_to_pdf(self.controller_name, self.source,
                                        keynote_app=self.keynote_app, com_name=self.com_name,
                                        output_name=self.output_name, cancel_event=self._cancel_event)
            if self.cancelled and self.output:
                self.output.unlink(missing_ok=True)
                self.output = None
        except PdfExportCancelled:
            pass
        except Exception as error:
            if not self.cancelled:
                self.error = error
                log.exception('Could not convert presentation to PDF')
