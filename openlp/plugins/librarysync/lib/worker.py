"""Run provider operations through OpenLP's tracked worker lifecycle."""
from threading import Event

from PySide6 import QtCore

from openlp.core.threading import ThreadWorker
from openlp.plugins.librarysync.lib.auth import GoogleAuth
from openlp.plugins.librarysync.lib.google import GoogleDriveProvider
from openlp.plugins.librarysync.lib.local import LocalStorageProvider
from openlp.plugins.librarysync.lib.provider import SyncError


def google_drive(profile, cancel):
    provider = GoogleDriveProvider(GoogleAuth(profile['installed']), cancel)
    provider.resource_keys.update({folder['id']: folder['resource_key'] for folder in profile['folders']
                                   if folder['resource_key']})
    return provider


PROVIDERS = {'google-drive': google_drive, 'local-cloud': LocalStorageProvider}


class SyncWorker(ThreadWorker):
    # Allow the current bounded HTTP request to unwind and remove partial downloads before exit.
    shutdown_wait_ms = 45000
    ready = QtCore.Signal(str, object)
    failed = QtCore.Signal(str, str)
    completed = QtCore.Signal(str)
    progress = QtCore.Signal(str, str, object, object)
    browser = QtCore.Signal(str)

    def __init__(self, job_id, profile, operation):
        super().__init__()
        self.job_id, self.profile, self.operation = job_id, profile, operation
        self.cancel = Event()

    def stop(self):
        self.cancel.set()

    def start(self):
        provider = None
        try:
            provider = PROVIDERS[self.profile['provider']](self.profile, self.cancel)
            result = self.operation(provider, self.cancel,
                                    lambda name, current, total: self.progress.emit(self.job_id, name, current, total),
                                    self.browser.emit, lambda value: self.ready.emit(self.job_id, value))
            if result is not None and not self.cancel.is_set():
                self.ready.emit(self.job_id, result)
        except SyncError as error:
            if not self.cancel.is_set():
                self.failed.emit(self.job_id, str(error))
        except Exception:
            # Third-party exceptions can include request URLs or credentials; show a safe message instead.
            if not self.cancel.is_set():
                self.failed.emit(self.job_id, 'The cloud operation failed. Check the connection and retry.')
        finally:
            try:
                if provider:
                    provider.close()
            finally:
                self.completed.emit(self.job_id)
                self.quit.emit()
