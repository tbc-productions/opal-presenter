# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
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
This module contains the first time wizard.
"""
import json
import logging
import time
from pathlib import Path
from tempfile import gettempdir

import requests
from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.api.deploy import REMOTE_URL, download_and_install
from openlp.core.common import trace_error_handler
from openlp.core.common.applocation import AppLocation
from openlp.core.common.httputils import CONNECTION_TIMEOUT, DownloadWorker, download_file, get_proxy_settings
from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.common.path import create_paths
from openlp.core.common.registry import Registry
from openlp.core.lib import build_icon
from openlp.core.lib.plugin import PluginStatus
from openlp.core.lib.ui import critical_error_message_box
from openlp.core.threading import ThreadWorker, get_thread_worker, is_thread_finished, run_thread
from openlp.core.ui.firsttimewizard import FirstTimePage, UiFirstTimeWizard
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.style import UiThemes, is_ui_theme
from openlp.core.widgets.widgets import ProxyDialog


log = logging.getLogger(__name__)

FTW_DOWNLOAD_TIMEOUT = 5
FTW_DOWNLOAD_RETRIES = 0


class _ThumbnailRelay(QtCore.QObject):
    """
    A QObject relay that lives on the main thread so that thumbnail download signals from worker threads
    are safely dispatched via Qt's queued connection mechanism before updating the list item.
    """
    def __init__(self, item, ftw, parent=None):
        super().__init__(parent)
        self._item = item
        self._ftw = ftw

    @QtCore.Slot(object)
    def on_downloaded(self, thumbnail_path):
        self._item.setIcon(build_icon(thumbnail_path))
        if self._item.listWidget():
            self._item.listWidget().viewport().update()
        self._item._download_finished = True
        self._ftw._on_theme_thumbnail_download_finished()

    @QtCore.Slot()
    def on_failed(self):
        self._item.setIcon(UiIcons().get_icon_variant('exception'))
        self._item._download_finished = True
        self._ftw._on_theme_thumbnail_download_finished()


class ThumbnailReceiver(QtCore.QObject):
    """
    Small QObject helper that owns the slots invoked when a thumbnail download finishes.
    """
    def __init__(self, item):
        super().__init__()
        self._item = item

    @QtCore.Slot()
    def on_failed(self):
        self._item.setIcon(UiIcons().get_icon_variant('exception'))

    @QtCore.Slot(Path)
    def on_succeeded(self, thumbnail_path):
        self._item.setIcon(build_icon(thumbnail_path))


class ThemeListWidgetItem(QtWidgets.QListWidgetItem):
    """
    Subclass a QListWidgetItem to allow dynamic loading of thumbnails from an online resource
    """
    def __init__(self, themes_url, sample_theme_data, *args, **kwargs):
        super().__init__(*args, **kwargs)
        title = sample_theme_data['title']
        self._themes_url = themes_url
        self._thumbnail = sample_theme_data['thumbnail']
        self.file_name = sample_theme_data['file_name']
        self.sha256 = sample_theme_data['sha256']
        self._download_started = False
        self._download_finished = False
        self._relay = None
        self.setIcon(UiIcons().get_icon_variant('picture'))  # Place holder until thumbnail is loaded
        self.setText(title)
        self.setToolTip(title)

    def start_download(self, ftw):
        """
        Start downloading the thumbnail image for this item. Safe to call multiple times.
        """
        if self._download_started or self._download_finished:
            return
        self._download_started = True
        # The relay is a QObject on the main thread; its slots will be called via queued connection
        # when signals are emitted from the worker thread, ensuring thread-safe UI updates.
        self._relay = _ThumbnailRelay(self, ftw)
        worker = DownloadWorker(self._themes_url, self._thumbnail, timeout=ftw.ftw_download_timeout,
                retries=ftw.ftw_download_retries)
        worker.download_failed.connect(self._relay.on_failed)
        worker.download_succeeded.connect(self._relay.on_downloaded)
        thread_name = 'thumbnail_download_{thumbnail}'.format(
            thumbnail=self._thumbnail.replace('/', '_').replace('\\', '_'))
        try:
            run_thread(worker, thread_name)
            ftw.thumbnail_download_threads.append(thread_name)
        except Exception as err:
            self._download_finished = True
            ftw._on_theme_thumbnail_download_finished()


class DownloadSetupWorker(ThreadWorker):
    """
    Calculate the total download size for the selected items without blocking the UI thread.
    """
    progress_updated = QtCore.Signal(str, object, object, bool)
    download_succeeded = QtCore.Signal(int)
    download_failed = QtCore.Signal()

    def __init__(self, songs_url, bibles_url, themes_url, songs, bibles, themes, download_remote, timeout, retries):
        super().__init__()
        self.songs_url = songs_url
        self.bibles_url = bibles_url
        self.themes_url = themes_url
        self.songs = songs
        self.bibles = bibles
        self.themes = themes
        self.download_remote = download_remote
        self.timeout = timeout
        self.retries = retries
        self.is_cancelled = False
        self._http_session = requests.Session()

    def _get_file_size(self, url):
        """
        Fetch a file size with a single fast attempt.
        """
        retry_limit = self.retries
        attempts = 0
        while attempts <= retry_limit:
            try:
                response = self._http_session.head(url, timeout=float(self.timeout), allow_redirects=True)
                response.raise_for_status()
                content_length = response.headers.get('Content-Length')
                return int(content_length) if content_length and content_length.isdigit() else 0
            except OSError:
                log.debug('Unable to query file size for %s', url, exc_info=True)
                if attempts >= retry_limit:
                    raise
                attempts += 1

    def _get_remote_size(self):
        """
        Fetch the remote installer size with a single fast attempt.
        """
        retry_limit = self.retries
        attempts = 0
        while attempts <= retry_limit:
            try:
                response = self._http_session.get(REMOTE_URL + 'version.json', timeout=float(self.timeout))
                response.raise_for_status()
                version_info = response.json()
                return version_info['latest']['size']
            except (OSError, ValueError, KeyError, TypeError):
                log.debug('Unable to query web remote size from %s', REMOTE_URL + 'version.json', exc_info=True)
                if attempts >= retry_limit:
                    raise
                attempts += 1

    @QtCore.Slot()
    def start(self):
        """
        Calculate the download size for each selected item and the optional web remote.
        """
        total_size = 0
        total_items = len(self.songs) + len(self.bibles) + len(self.themes) + (1 if self.download_remote else 0)
        completed_items = 0
        try:
            self.progress_updated.emit(translate('OpenLP.FirstTimeWizard', 'Calculating download sizes...'),
                                       0, total_items, True)
            for filename, _sha256 in self.songs:
                if self.is_cancelled:
                    break
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking song size: {name}').format(name=filename),
                    completed_items, total_items, False)
                total_size += self._get_file_size('{path}{name}'.format(path=self.songs_url, name=filename))
                completed_items += 1
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking song size: {name}').format(name=filename),
                    completed_items, total_items, False)
            for filename, _sha256 in self.bibles:
                if self.is_cancelled:
                    break
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking Bible size: {name}').format(name=filename),
                    completed_items, total_items, False)
                total_size += self._get_file_size('{path}{name}'.format(path=self.bibles_url, name=filename))
                completed_items += 1
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking Bible size: {name}').format(name=filename),
                    completed_items, total_items, False)
            for file_name, _sha256 in self.themes:
                if self.is_cancelled:
                    break
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking theme size: {name}').format(name=file_name),
                    completed_items, total_items, False)
                total_size += self._get_file_size('{url}{file}'.format(url=self.themes_url, file=file_name))
                completed_items += 1
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking theme size: {name}').format(name=file_name),
                    completed_items, total_items, False)
            if self.download_remote and not self.is_cancelled:
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking web remote size...'),
                    completed_items, total_items, False)
                total_size += self._get_remote_size()
                completed_items += 1
                self.progress_updated.emit(
                    translate('OpenLP.FirstTimeWizard', 'Checking web remote size...'),
                    completed_items, total_items, False)
            if self.is_cancelled:
                self.download_failed.emit()
            else:
                self.download_succeeded.emit(total_size)
        except OSError:
            trace_error_handler(log)
            self.download_failed.emit()
        finally:
            self._http_session.close()
            self.quit.emit()


class _BaseDownloadWorker(ThreadWorker):
    """
    Shared progress and cancellation behavior for first-time wizard download workers.
    """
    def __init__(self, timeout, retries):
        super().__init__()
        self.is_cancelled = False
        self.previous_size = 0
        self.timeout = timeout
        self.retries = retries
        self._http_session = requests.Session()

    def update_progress(self, block_count, block_size):
        """
        Emit the byte delta for the current download.
        """
        increment = (block_count * block_size) - self.previous_size
        self.previous_size = block_count * block_size
        if increment > 0:
            self.progress_updated.emit(increment)

    def _download_web_remote(self):
        """
        Download the web remote package and return the installed version.
        """
        try:
            return download_and_install(callback=self, can_update_range=False, timeout=self.timeout,
                                        retries=self.retries, session=self._http_session)
        except Exception:
            if not self.is_cancelled:
                log.exception('Error downloading web remote')
            return None

    @QtCore.Slot()
    def cancel_download(self):
        """
        Cancel the download if the wizard closes.
        """
        self.is_cancelled = True


class DownloadResourcesWorker(_BaseDownloadWorker):
    """
    Download the selected resources without blocking the UI thread.
    """
    progress_updated = QtCore.Signal(int)
    status_updated = QtCore.Signal(str)
    download_finished = QtCore.Signal(object, object)
    download_failed = QtCore.Signal()

    def __init__(self, songs_url, bibles_url, themes_url, songs, bibles, themes, download_remote, timeout, retries):
        super().__init__(timeout, retries)
        self.songs_url = songs_url
        self.bibles_url = bibles_url
        self.themes_url = themes_url
        self.songs = songs
        self.bibles = bibles
        self.themes = themes
        self.download_remote = download_remote

    def _download_file(self, url, destination_path, sha256=None):
        """
        Download a single file and return True on success.
        """
        self.previous_size = 0
        return download_file(self, url, destination_path, sha256, timeout=self.timeout, retries=self.retries,
                             session=self._http_session)

    def _download_resource_group(self, items, base_url, destination_path, label):
        """
        Download one resource group (songs, bibles or themes) and return a list of failed item labels.
        """
        missed_files = []
        status_template = translate('OpenLP.FirstTimeWizard', 'Downloading {name}...')
        for file_name, sha256 in items:
            if self.is_cancelled:
                break
            self.status_updated.emit(status_template.format(name=file_name))
            if not self._download_file('{path}{name}'.format(path=base_url, name=file_name),
                                       destination_path / file_name, sha256):
                missed_files.append('{label}: {name}'.format(label=label, name=file_name))
        return missed_files

    @QtCore.Slot()
    def start(self):
        """
        Download all selected resources.
        """
        songs_destination_path = Path(gettempdir(), 'openlp')
        bibles_destination_path = AppLocation.get_section_data_path('bibles')
        themes_destination_path = AppLocation.get_section_data_path('themes')
        missed_files = []
        remote_version = None
        try:
            resource_groups = (
                (self.songs, self.songs_url, songs_destination_path, 'Song'),
                (self.bibles, self.bibles_url, bibles_destination_path, 'Bible'),
                (self.themes, self.themes_url, themes_destination_path, 'Theme')
            )
            for items, base_url, destination, label in resource_groups:
                missed_files.extend(self._download_resource_group(items, base_url, destination, label))
                if self.is_cancelled:
                    break
            if self.download_remote and not self.is_cancelled:
                self.status_updated.emit(translate('OpenLP.FirstTimeWizard', 'Downloading {name}...').format(
                    name='Web Remote'))
                remote_version = self._download_web_remote()
                if not remote_version:
                    missed_files.append('Web Remote')
            if self.is_cancelled:
                self.download_failed.emit()
            else:
                self.download_finished.emit(missed_files, remote_version)
        except OSError:
            trace_error_handler(log)
            self.download_failed.emit()
        finally:
            self._http_session.close()
            self.quit.emit()


class WebRemoteDownloadWorker(_BaseDownloadWorker):
    """
    Download the web remote without blocking the UI thread.
    """
    progress_updated = QtCore.Signal(int)  # byte increment
    download_succeeded = QtCore.Signal(str)  # version string
    download_failed = QtCore.Signal()

    @QtCore.Slot()
    def start(self):
        """
        Download and install the web remote in a background thread.
        """
        version = self._download_web_remote()
        if version:
            self.download_succeeded.emit(version)
        else:
            self.download_failed.emit()
        self.quit.emit()


class ResourceIndexDownloadWorker(ThreadWorker):
    """
    Download the first-time wizard resource index without blocking the UI thread.
    """
    progress_updated = QtCore.Signal(str, object, object, bool)
    download_succeeded = QtCore.Signal(str)
    download_failed = QtCore.Signal()

    def __init__(self, base_url, user_agent, timeout=FTW_DOWNLOAD_TIMEOUT):
        super().__init__()
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.is_cancelled = False
        self._http_session = requests.Session()

    @staticmethod
    def format_download_size(size):
        """
        Convert a byte count into a readable string.

        :param int size: The size in bytes.
        :return: Formatted size string.
        :rtype: str
        """
        units = ['bytes', 'KB', 'MB', 'GB']
        size = float(size)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        if unit_index == 0:
            return '{size:.0f} {unit}'.format(size=size, unit=units[unit_index])
        return '{size:.1f} {unit}'.format(size=size, unit=units[unit_index])

    @staticmethod
    def get_progress_status(current_size, total_size=None):
        """
        Build the current resource index download status text.

        :param int current_size: Bytes downloaded so far.
        :param int | None total_size: Total download size when known.
        :return: Status text.
        :rtype: str
        """
        current = ResourceIndexDownloadWorker.format_download_size(current_size)
        if total_size:
            percent = int((current_size / total_size) * 100) if total_size else 0
            total = ResourceIndexDownloadWorker.format_download_size(total_size)
            return translate('OpenLP.FirstTimeWizard',
                             'Downloading resource index: {current} of {total} ({percent}%)').format(
                current=current, total=total, percent=percent)
        return translate('OpenLP.FirstTimeWizard', 'Downloading resource index: {current}').format(current=current)

    @QtCore.Slot()
    def start(self):
        """
        Start downloading the first-time wizard resource index.
        """
        bytes_downloaded = 0
        chunk_size = 4096
        downloaded_chunks = []
        response = None
        try:
            proxy = get_proxy_settings()
            self.progress_updated.emit(translate('OpenLP.FirstTimeWizard', 'Connecting to resource server...'),
                                       None, None, True)
            response = self._http_session.get('{host}{name}'.format(host=self.base_url, name='download_3.0.json'),
                                              headers={'User-Agent': self.user_agent}, proxies=proxy,
                                              timeout=float(self.timeout), stream=True)
            response.raise_for_status()
            total_size_header = response.headers.get('Content-Length')
            total_size = int(total_size_header) if total_size_header and total_size_header.isdigit() else None
            self.progress_updated.emit(self.get_progress_status(0, total_size), 0, total_size, total_size is None)
            for chunk in response.iter_content(chunk_size=chunk_size):
                if self.is_cancelled:
                    break
                if not chunk:
                    continue
                downloaded_chunks.append(chunk)
                bytes_downloaded += len(chunk)
                self.progress_updated.emit(self.get_progress_status(bytes_downloaded, total_size),
                                           bytes_downloaded, total_size, total_size is None)
            if self.is_cancelled:
                self.download_failed.emit()
            else:
                self.download_succeeded.emit(b''.join(downloaded_chunks).decode(response.encoding or 'utf-8'))
        except OSError:
            trace_error_handler(log)
            self.download_failed.emit()
        finally:
            if response:
                response.close()
            self._http_session.close()
            self.quit.emit()

    @QtCore.Slot()
    def cancel_download(self):
        """
        Cancel the download if the wizard closes.
        """
        self.is_cancelled = True


class FirstTimeForm(QtWidgets.QWizard, UiFirstTimeWizard, RegistryProperties):
    """
    This is the FirstTimeWizard, designed to help new users to get up and running quickly.
    """
    log.info('ThemeWizardForm loaded')

    def __init__(self, parent=None):
        """
        Create and set up the first time wizard.
        """
        super(FirstTimeForm, self).__init__(parent,
                                            QtCore.Qt.WindowType.WindowSystemMenuHint |
                                            QtCore.Qt.WindowType.WindowTitleHint)
        self.has_web_access = True
        self.web = ''
        self.is_index_downloaded = False
        self.ftw_download_timeout = FTW_DOWNLOAD_TIMEOUT
        self.ftw_download_retries = FTW_DOWNLOAD_RETRIES
        self.download_setup_thread = None
        self.download_setup_in_progress = False
        self.download_resources_thread = None
        self.download_resources_in_progress = False
        self.remote_download_thread = None
        self.remote_download_in_progress = False
        self.setup_ui(self)
        self.customButtonClicked.connect(self._on_custom_button_clicked)
        self.themes_list_widget.itemSelectionChanged.connect(self.on_themes_list_widget_selection_changed)
        self.themes_deselect_all_button.clicked.connect(self.themes_list_widget.clearSelection)
        self.themes_select_all_button.clicked.connect(self.themes_list_widget.selectAll)
        self.setOption(QtWidgets.QWizard.WizardOption.HaveHelpButton, True)
        self.helpRequested.connect(self.provide_help)
        self.theme_thumbnail_downloads_pending = 0
        self.theme_thumbnails_loading = False

    def provide_help(self):
        """
        Provide help within the wizard by opening the appropriate page of the openlp manual in the user's browser
        """
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://manual.openlp.org/wizard.html"))

    def get_next_page_id(self):
        """
        Returns the id of the next FirstTimePage to go to based on enabled plugins
        """
        if FirstTimePage.Remote < self.currentId() < FirstTimePage.Songs and self.songs_check_box.isChecked():
            # If the songs plugin is enabled then go to the songs page
            return FirstTimePage.Songs
        elif FirstTimePage.Remote < self.currentId() < FirstTimePage.Bibles and self.bible_check_box.isChecked():
            # Otherwise, if the Bibles plugin is enabled then go to the Bibles page
            return FirstTimePage.Bibles
        elif FirstTimePage.Remote < self.currentId() < FirstTimePage.Themes:
            # Otherwise, if the current page is somewhere between the Welcome and the Themes pages, go to the themes
            return FirstTimePage.Themes
        else:
            # If all else fails, go to the next page
            return self.currentId() + 1

    def nextId(self):
        """
        Determine the next page in the Wizard to go to.
        """
        self.application.process_events()
        if self.currentId() == FirstTimePage.Download:
            if not self.has_web_access:
                return FirstTimePage.NoInternet
            elif self.remote_interface_check_box.isChecked():
                return FirstTimePage.Remote
            elif self.songs_check_box.isChecked():
                return FirstTimePage.Songs
            elif self.bible_check_box.isChecked():
                return FirstTimePage.Bibles
            else:
                return FirstTimePage.Themes
        elif self.currentId() == FirstTimePage.Progress:
            return -1
        elif self.currentId() == FirstTimePage.NoInternet:
            return FirstTimePage.Progress
        return self.get_next_page_id()

    def exec(self):
        """
        Run the wizard.
        """
        self.set_defaults()
        return super().exec()

    def initialize(self, screens):
        """
        Set up the First Time Wizard

        :param screens: The screens detected by OpenLP
        """
        self.screens = screens
        self.was_cancelled = False
        self.thumbnail_download_threads = []
        self.has_run_wizard = False
        self.resource_index_thread = None
        self.resource_index_downloaded = None
        self.resource_index_failed = False
        self.ftw_download_timeout = FTW_DOWNLOAD_TIMEOUT
        self.ftw_download_retries = FTW_DOWNLOAD_RETRIES
        self.download_setup_thread = None
        self.download_setup_in_progress = False
        self.download_resources_thread = None
        self.download_resources_in_progress = False
        self.remote_download_thread = None
        self.remote_download_in_progress = False
        self.theme_thumbnail_downloads_pending = 0
        self.theme_thumbnails_loading = False
        if hasattr(self, 'themes_loading_widget'):
            self.themes_loading_widget.setVisible(False)

    def _reset_download_progress(self):
        """
        Reset the resource retrieval progress widgets.
        """
        self.download_status_label.clear()
        self.download_status_label.setVisible(False)
        self.download_progress_bar.setVisible(True)
        self.download_progress_bar.setRange(0, 1)
        self.download_progress_bar.setValue(0)

    def _update_download_progress(self, status_text, current=None, maximum=None, busy=False):
        """
        Update the resource retrieval page while the index and available resources are loaded.

        :param str status_text: The current retrieval status.
        :param int current: The current step in the retrieval process.
        :param int maximum: The total number of steps in the retrieval process.
        :param bool busy: Whether the progress bar should show an indeterminate state.
        """
        self.download_status_label.setText(status_text)
        self.download_status_label.setVisible(True)
        if busy:
            self.download_progress_bar.setRange(0, 0)
        else:
            if maximum is not None:
                self.download_progress_bar.setRange(0, maximum)
            if current is not None:
                self.download_progress_bar.setValue(current)
        self.download_page.repaint()
        self.application.process_events()

    def _on_resource_index_downloaded(self, web_config):
        """
        Store the downloaded resource index content from the background worker.
        """
        self.resource_index_downloaded = web_config

    def _on_resource_index_download_failed(self):
        """
        Track when the background resource index download fails.
        """
        self.resource_index_failed = True

    def _update_navigation_buttons(self, page_id):
        """
        Set button visibility and enabled state for the current wizard page.

        :param int page_id: The active wizard page id.
        """
        back_button = self.button(QtWidgets.QWizard.WizardButton.BackButton)
        cancel_button = self.button(QtWidgets.QWizard.WizardButton.CancelButton)
        internet_settings_button = self.button(QtWidgets.QWizard.WizardButton.CustomButton1)
        next_button = self.button(QtWidgets.QWizard.WizardButton.NextButton)

        back_button.setVisible(page_id != FirstTimePage.Welcome)
        back_button.setEnabled(page_id not in (FirstTimePage.Welcome, FirstTimePage.Download,
                                               FirstTimePage.Progress, FirstTimePage.Remote))
        cancel_button.setVisible(page_id != FirstTimePage.NoInternet)
        cancel_enabled = page_id not in (FirstTimePage.Download, FirstTimePage.NoInternet, FirstTimePage.Progress)
        if page_id == FirstTimePage.Progress and self.remote_download_in_progress:
            cancel_enabled = True
        if page_id == FirstTimePage.Progress and self.download_setup_in_progress:
            cancel_enabled = True
        if page_id == FirstTimePage.Progress and self.download_resources_in_progress:
            cancel_enabled = True
        cancel_button.setEnabled(cancel_enabled)
        next_button.setVisible(page_id not in (FirstTimePage.Download, FirstTimePage.NoInternet,
                                               FirstTimePage.Progress))
        next_enabled = page_id not in (FirstTimePage.Download, FirstTimePage.NoInternet,
                                       FirstTimePage.Progress)
        if page_id == FirstTimePage.Themes and self.theme_thumbnail_downloads_pending > 0:
            next_enabled = False
        next_button.setEnabled(next_enabled)
        internet_settings_button.setVisible(page_id in (FirstTimePage.SampleOption, FirstTimePage.NoInternet))
        internet_settings_button.setEnabled(page_id in (FirstTimePage.SampleOption, FirstTimePage.NoInternet))

    @QtCore.Slot(int)
    def _on_download_setup_finished(self, max_progress):
        """
        Finish preparing the download page once the size calculation worker completes.
        """
        self.download_setup_thread = None
        self.download_setup_in_progress = False
        if self.was_cancelled:
            return
        self.max_progress = max_progress
        if self.max_progress:
            # Add on 2 for plugins status setting plus a "finished" point.
            self.max_progress += 2
            self.progress_bar.setValue(0)
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(self.max_progress)
            self.progress_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Setting Up And Downloading'))
            self.progress_page.setSubTitle(
                translate('OpenLP.FirstTimeWizard', 'Please wait while OpenLP+ is set up and your data is downloaded.'))
        else:
            self.progress_bar.setVisible(False)
            self.progress_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Setting Up'))
            self.progress_page.setSubTitle('Setup complete.')
        self._start_download_resources()

    @QtCore.Slot()
    def _on_download_setup_failed(self):
        """
        Handle a failure while calculating the download sizes.
        """
        self.download_setup_thread = None
        self.download_setup_in_progress = False
        if self.was_cancelled:
            return
        critical_error_message_box(translate('OpenLP.FirstTimeWizard', 'Download Error'),
                                   translate('OpenLP.FirstTimeWizard', 'There was a connection problem during '
                                             'download, so further downloads will be skipped. Try to re-run the '
                                             'First Time Wizard later.'))
        self.max_progress = 0
        self.has_web_access = None
        self.progress_bar.setVisible(False)
        self.progress_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Setting Up'))
        self.progress_page.setSubTitle('Setup complete.')
        self.application.set_normal_cursor()

    @QtCore.Slot(int)
    def _on_download_resources_progress_updated(self, increment):
        """
        Update the progress bar while the selected resources are downloading.
        """
        self._increment_progress_bar(None, increment)

    @QtCore.Slot(str)
    def _on_download_resources_status_updated(self, status_text):
        """
        Update the progress label while the selected resources are downloading.
        """
        self._increment_progress_bar(status_text, 0)

    @QtCore.Slot(object, object)
    def _on_download_resources_finished(self, missed_files, remote_version):
        """
        Finish the resource download phase and show any warnings.
        """
        self.download_resources_thread = None
        self.download_resources_in_progress = False
        if self.was_cancelled:
            self.application.set_normal_cursor()
            return
        if remote_version:
            self.settings.setValue('api/download version', remote_version)
        if missed_files:
            file_list = ''
            for entry in missed_files:
                file_list += '{text}<br />'.format(text=entry)
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg.setWindowTitle(translate('OpenLP.FirstTimeWizard', 'Network Error'))
            msg.setText(translate('OpenLP.FirstTimeWizard', 'Unable to download some files'))
            msg.setInformativeText(translate('OpenLP.FirstTimeWizard',
                                             'The following files were not able to be '
                                             'downloaded:<br />{text}'.format(text=file_list)))
            msg.setStandardButtons(msg.StandardButton.Ok)
            msg.exec()
        self._post_wizard()
        self.application.set_normal_cursor()

    @QtCore.Slot()
    def _on_download_resources_failed(self):
        """
        Handle a failure while downloading selected resources.
        """
        self.download_resources_thread = None
        self.download_resources_in_progress = False
        if self.was_cancelled:
            self.application.set_normal_cursor()
            return
        critical_error_message_box(translate('OpenLP.FirstTimeWizard', 'Download Error'),
                                   translate('OpenLP.FirstTimeWizard', 'There was a connection problem while '
                                             'downloading, so further downloads will be skipped. Try to re-run '
                                             'the First Time Wizard later.'))
        self._post_wizard()
        self.application.set_normal_cursor()

    @QtCore.Slot(int)
    def _on_remote_progress_updated(self, increment):
        """
        Update the wizard progress bar from the remote download worker.
        """
        self._increment_progress_bar(None, increment)

    @QtCore.Slot(str)
    def _on_remote_download_succeeded(self, version):
        """
        Store the downloaded remote version from the worker.
        """
        self._remote_version = version

    @QtCore.Slot()
    def _on_remote_download_failed(self):
        """
        Record a failed remote download.
        """
        self._remote_failed = True

    def _set_theme_thumbnail_loading(self, loading):
        """
        Show or hide the theme thumbnail loading indicator.
        """
        self.theme_thumbnails_loading = loading
        self.themes_loading_widget.setVisible(loading)
        self._update_navigation_buttons(FirstTimePage.Themes)
        self.application.process_events()

    def _on_theme_thumbnail_download_finished(self):
        """
        Track completion of one theme thumbnail download.
        """
        if self.theme_thumbnail_downloads_pending > 0:
            self.theme_thumbnail_downloads_pending -= 1
        if self.theme_thumbnail_downloads_pending == 0:
            self._set_theme_thumbnail_loading(False)

    def _start_theme_thumbnail_downloads(self):
        """
        Start the theme thumbnail downloads that still need to run.
        """
        pending_items = []
        for list_index in range(self.themes_list_widget.count()):
            item = self.themes_list_widget.item(list_index)
            if isinstance(item, ThemeListWidgetItem) and not item._download_finished:
                pending_items.append(item)
        self.theme_thumbnail_downloads_pending = len(pending_items)
        if not pending_items:
            self._set_theme_thumbnail_loading(False)
            return
        self._set_theme_thumbnail_loading(True)
        for item in pending_items:
            item.start_download(self)

    def _start_download_setup(self):
        """
        Start calculating download sizes on a background worker.
        """
        if self.download_setup_in_progress:
            return
        self.max_progress = 0
        self.button(QtWidgets.QWizard.WizardButton.FinishButton).setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.progress_page.setTitle(translate('OpenLP.FirstTimeWizard', 'Setting Up And Downloading'))
        self.progress_page.setSubTitle(
            translate('OpenLP.FirstTimeWizard', 'Please wait while OpenLP+ is set up and your data is downloaded.'))
        self.download_setup_in_progress = True
        songs = []
        bibles = []
        themes = []
        for i in range(self.songs_list_widget.count()):
            item = self.songs_list_widget.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                filename, sha256 = item.data(QtCore.Qt.ItemDataRole.UserRole)
                songs.append((filename, sha256))
        iterator = QtWidgets.QTreeWidgetItemIterator(self.bibles_tree_widget)
        while iterator.value():
            item = iterator.value()
            if item.parent() and item.checkState(0) == QtCore.Qt.CheckState.Checked:
                filename, sha256 = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                bibles.append((filename, sha256))
            iterator += 1
        for item in self.themes_list_widget.selectedItems():
            themes.append((item.file_name, item.sha256))
        worker = DownloadSetupWorker(self.songs_url, self.bibles_url, self.themes_url,
                         songs, bibles, themes,
                         self.remote_interface_check_box.isChecked() and self.remote_page.can_download_remote,
                         self.ftw_download_timeout, self.ftw_download_retries)
        worker.progress_updated.connect(self._update_download_progress)
        worker.download_succeeded.connect(self._on_download_setup_finished)
        worker.download_failed.connect(self._on_download_setup_failed)
        self.download_setup_thread = 'first_time_download_setup'
        run_thread(worker, self.download_setup_thread)

    def _start_download_resources(self):
        """
        Start downloading the selected resources on a background worker.
        """
        if self.download_resources_in_progress:
            return
        songs = []
        bibles = []
        themes = []
        for i in range(self.songs_list_widget.count()):
            item = self.songs_list_widget.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                filename, sha256 = item.data(QtCore.Qt.ItemDataRole.UserRole)
                songs.append((filename, sha256))
        iterator = QtWidgets.QTreeWidgetItemIterator(self.bibles_tree_widget)
        while iterator.value():
            item = iterator.value()
            if item.parent() and item.checkState(0) == QtCore.Qt.CheckState.Checked:
                filename, sha256 = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                bibles.append((filename, sha256))
            iterator += 1
        for item in self.themes_list_widget.selectedItems():
            themes.append((item.file_name, item.sha256))
        worker = DownloadResourcesWorker(self.songs_url, self.bibles_url, self.themes_url,
                         songs, bibles, themes,
                         self.remote_interface_check_box.isChecked() and self.remote_page.can_download_remote,
                         self.ftw_download_timeout, self.ftw_download_retries)
        worker.progress_updated.connect(self._on_download_resources_progress_updated)
        worker.status_updated.connect(self._on_download_resources_status_updated)
        worker.download_finished.connect(self._on_download_resources_finished)
        worker.download_failed.connect(self._on_download_resources_failed)
        self.download_resources_in_progress = True
        self.download_resources_thread = 'first_time_download_resources'
        run_thread(worker, self.download_resources_thread)

    def _download_index(self):
        """
        Download the configuration file and kick off the theme screenshot download threads
        """
        # Check if the index file has already been downloaded
        if self.is_index_downloaded:
            return
        # check to see if we have web access
        self.has_web_access = False
        self.config = ''
        user_agent = 'OpenLP+/' + QtWidgets.QApplication.applicationVersion()
        self.resource_index_downloaded = None
        self.resource_index_failed = False
        self.resource_index_thread = 'first_time_resource_index'
        self.application.process_events()
        worker = ResourceIndexDownloadWorker(self.web, user_agent, self.ftw_download_timeout)
        worker.progress_updated.connect(self._update_download_progress)
        worker.download_succeeded.connect(self._on_resource_index_downloaded)
        worker.download_failed.connect(self._on_resource_index_download_failed)
        run_thread(worker, self.resource_index_thread)
        while not is_thread_finished(self.resource_index_thread):
            self.application.process_events()
            time.sleep(0.05)
        if self.resource_index_failed:
            QtWidgets.QMessageBox.critical(self, translate('OpenLP.FirstTimeWizard', 'Network Error'),
                                           translate('OpenLP.FirstTimeWizard', 'There was a network error attempting '
                                                     'to connect to retrieve initial configuration information'),
                                           QtWidgets.QMessageBox.StandardButton.Ok)
        elif self.resource_index_downloaded and self._parse_config(self.resource_index_downloaded):
            self.has_web_access = True
        self.resource_index_thread = None
        self.application.process_events()
        self.downloading = translate('OpenLP.FirstTimeWizard', 'Downloading {name}...')
        self.is_index_downloaded = True

    def _parse_config(self, web_config):
        try:
            config = json.loads(web_config)
            meta = config['_meta']
            self.web = meta['base_url']
            self.songs_url = self.web + meta['songs_dir'] + '/'
            self.bibles_url = self.web + meta['bibles_dir'] + '/'
            self.themes_url = self.web + meta['themes_dir'] + '/'
            songs = list(config['songs'].values())
            bible_languages = list(config['bibles'].values())
            themes = list(config['themes'].values())
            total_steps = len(songs) + len(themes)
            for lang in bible_languages:
                total_steps += len(lang['translations'])
            total_steps = max(1, total_steps)
            completed_steps = 0
            self._update_download_progress(translate('OpenLP.FirstTimeWizard', 'Reading available resources...'),
                                           current=completed_steps, maximum=total_steps)
            for song in songs:
                self._update_download_progress(
                    translate('OpenLP.FirstTimeWizard', 'Loading song: {name}').format(name=song['title']),
                    current=completed_steps, maximum=total_steps)
                self.application.process_events()
                item = QtWidgets.QListWidgetItem(song['title'], self.songs_list_widget)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, (song['file_name'], song['sha256']))
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                completed_steps += 1
            for lang in bible_languages:
                self.application.process_events()
                lang_item = QtWidgets.QTreeWidgetItem(self.bibles_tree_widget, [lang['title']])
                for translation in lang['translations'].values():
                    self._update_download_progress(
                        translate('OpenLP.FirstTimeWizard', 'Loading Bible: {name}').format(
                            name=translation['title']),
                        current=completed_steps, maximum=total_steps)
                    self.application.process_events()
                    item = QtWidgets.QTreeWidgetItem(lang_item, [translation['title']])
                    item.setData(0, QtCore.Qt.ItemDataRole.UserRole, (translation['file_name'], translation['sha256']))
                    item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                    item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                    completed_steps += 1
            self.bibles_tree_widget.expandAll()
            self.application.process_events()
            for theme in themes:
                self._update_download_progress(
                    translate('OpenLP.FirstTimeWizard', 'Loading theme: {name}').format(name=theme['title']),
                    current=completed_steps, maximum=total_steps)
                ThemeListWidgetItem(self.themes_url, theme, self.themes_list_widget)
                completed_steps += 1
            self._update_download_progress(translate('OpenLP.FirstTimeWizard', 'Available resources loaded.'),
                                           current=total_steps, maximum=total_steps)
            self.application.process_events()
        except Exception:
            log.exception('Unable to parse sample config file %s', web_config)
            QtWidgets.QMessageBox.critical(self, translate('OpenLP.FirstTimeWizard', 'Invalid index file'),
                                           translate('OpenLP.FirstTimeWizard',
                                                     'OpenLP+ was unable to read the resource index file. '
                                                     'Please try again later.'))
            return False
        return True

    def set_defaults(self):
        """
        Set up display at start of theme edit.
        """
        self.restart()
        self.web = 'https://get.openlp.org/ftw/'
        self.currentIdChanged.connect(self.on_current_id_changed)
        Registry().register_function('config_screen_changed', self.screen_selection_widget.load)
        # Check if this is a re-run of the wizard.
        self.has_run_wizard = self.settings.value('core/has run wizard')
        create_paths(Path(gettempdir(), 'openlp'))
        self.theme_combo_box.clear()
        self.remote_page.can_download_remote = False
        self.download_setup_thread = None
        self.download_setup_in_progress = False
        self.remote_download_thread = None
        self.remote_download_in_progress = False
        self.theme_thumbnail_downloads_pending = 0
        self.theme_thumbnails_loading = False
        self.themes_loading_widget.setVisible(False)
        self._reset_download_progress()
        self.button(QtWidgets.QWizard.WizardButton.CustomButton1).setVisible(False)
        self.projector_check_box.setChecked(
            self.has_run_wizard and self.settings.value('projector/status') == PluginStatus.Active)
        self.remote_interface_check_box.setChecked(
            self.has_run_wizard and self.settings.value('remote_interface/status') == PluginStatus.Active)
        if self.has_run_wizard and self.plugin_manager is not None:
            self.songs_check_box.setChecked(self.plugin_manager.get_plugin_by_name('songs').is_active())
            self.bible_check_box.setChecked(self.plugin_manager.get_plugin_by_name('bibles').is_active())
            self.presentation_check_box.setChecked(
                self.plugin_manager.get_plugin_by_name('presentations').is_active())
            self.image_check_box.setChecked(self.plugin_manager.get_plugin_by_name('images').is_active())
            # temp fix for #677 when we have an error
            try:
                self.media_check_box.setChecked(self.plugin_manager.get_plugin_by_name('media').is_active())
            except Exception:
                self.media_check_box.setEnabled(False)
            self.custom_check_box.setChecked(self.plugin_manager.get_plugin_by_name('custom').is_active())
            self.song_usage_check_box.setChecked(self.plugin_manager.get_plugin_by_name('songusage').is_active())
            self.alert_check_box.setChecked(self.plugin_manager.get_plugin_by_name('alerts').is_active())
            self.obs_studio_check_box.setChecked(self.plugin_manager.get_plugin_by_name('obs_studio').is_active())
            # Add any existing themes to list.
            self.theme_combo_box.insertSeparator(0)
            self.theme_combo_box.addItems(sorted(self.theme_manager.get_theme_names()))
            default_theme = self.settings.value('themes/global theme')
            # Pre-select the current default theme.
            index = self.theme_combo_box.findText(default_theme)
            self.theme_combo_box.setCurrentIndex(index)

    def on_current_id_changed(self, page_id):
        """
        Detects Page changes and updates as appropriate.
        """
        self._update_navigation_buttons(page_id)
        self.application.process_events()
        if page_id == FirstTimePage.Download:
            self.application.set_busy_cursor()
            self._download_index()
            self.application.set_normal_cursor()
            self.next()
        elif page_id == FirstTimePage.Themes:
            self._start_theme_thumbnail_downloads()
        elif page_id == FirstTimePage.Progress:
            self.application.set_busy_cursor()
            self._start_download_setup()

    def accept(self):
        """
        Called when the user clicks 'Finish'. Reimplement it to to save the plugin status

        :rtype: None
        """
        imported_settings = False
        if hasattr(self, 'import_settings_page') and self.import_settings_page.file_edit.text():
            file_path = self.import_settings_page.file_edit.text()
            if file_path and Path(file_path).exists():
                imported_settings = self.settings.import_settings(Path(file_path))
                if not imported_settings:
                    QtWidgets.QMessageBox.critical(self, translate('OpenLP.FirstTimeWizard', 'Import settings'),
                                                   translate('OpenLP.FirstTimeWizard', 'An error occurred while importing settings from the selected file.'))

        if not imported_settings:
            self._set_plugin_status(self.songs_check_box, 'songs/status')
            self._set_plugin_status(self.bible_check_box, 'bibles/status')
            self._set_plugin_status(self.presentation_check_box, 'presentations/status')
            self._set_plugin_status(self.image_check_box, 'images/status')
            self._set_plugin_status(self.media_check_box, 'media/status')
            self._set_plugin_status(self.custom_check_box, 'custom/status')
            self._set_plugin_status(self.song_usage_check_box, 'songusage/status')
            self._set_plugin_status(self.alert_check_box, 'alerts/status')
            self._set_plugin_status(self.obs_studio_check_box, 'obs_studio/status')
            self._set_plugin_status(self.projector_check_box, 'projector/status')
            self._set_plugin_status(self.remote_interface_check_box, 'remote_interface/status')
            if self.theme_combo_box.currentIndex() != -1:
                self.settings.setValue('themes/global theme', self.theme_combo_box.currentText())

        self.screen_selection_widget.save()
        Registry().remove_function('config_screen_changed', self.screen_selection_widget.load)
        super().accept()

    def reject(self):
        """
        Called when the user clicks the cancel button. Reimplement it to clean up the threads.

        :rtype: None
        """
        self.was_cancelled = True
        if self.resource_index_thread:
            worker = get_thread_worker(self.resource_index_thread)
            if worker:
                worker.cancel_download()
        if self.download_setup_thread:
            worker = get_thread_worker(self.download_setup_thread)
            if worker:
                worker.cancel_download()
        if self.remote_download_thread:
            worker = get_thread_worker(self.remote_download_thread)
            if worker:
                worker.cancel_download()
        for thread_name in self.thumbnail_download_threads:
            worker = get_thread_worker(thread_name)
            if worker:
                worker.cancel_download()
        # Was the thread created.
        if self.thumbnail_download_threads or self.resource_index_thread or self.download_setup_thread:
            while any([not is_thread_finished(thread_name) for thread_name in self.thumbnail_download_threads]) or \
                    (self.resource_index_thread and not is_thread_finished(self.resource_index_thread)) or \
                    (self.download_setup_thread and not is_thread_finished(self.download_setup_thread)):
                self.application.process_events()
                time.sleep(0.1)
        if self.remote_download_thread and not is_thread_finished(self.remote_download_thread):
            while not is_thread_finished(self.remote_download_thread):
                self.application.process_events()
                time.sleep(0.1)
        self.application.set_normal_cursor()
        Registry().remove_function('config_screen_changed', self.screen_selection_widget.load)
        super().reject()

    def _on_custom_button_clicked(self, which):
        """
        Slot to handle the a click on one of the wizards custom buttons.

        :param int QtWidgets.QWizard which: The button pressed
        :rtype: None
        """
        # Internet settings button
        if which == QtWidgets.QWizard.WizardButton.CustomButton1.value:
            proxy_dialog = ProxyDialog(self, show_ftw_options=True, timeout=self.ftw_download_timeout,
                                       retries=self.ftw_download_retries)
            proxy_dialog.retranslate_ui()
            if proxy_dialog.exec():
                self.ftw_download_timeout = proxy_dialog.timeout
                self.ftw_download_retries = proxy_dialog.retries

    def on_projectors_check_box_clicked(self):
        # When clicking projectors_check box, change the visibility setting for Projectors panel.
        if self.settings.value('projector/show after wizard'):
            self.settings.setValue('projector/show after wizard', False)
        else:
            self.settings.setValue('projector/show after wizard', True)

    def on_themes_list_widget_selection_changed(self):
        """
        Update the `theme_combo_box` with the selected items

        :rtype: None
        """
        existing_themes = []
        if self.theme_manager:
            existing_themes = self.theme_manager.get_theme_names()
        for list_index in range(self.themes_list_widget.count()):
            item = self.themes_list_widget.item(list_index)
            if item.text() not in existing_themes:
                cbox_index = self.theme_combo_box.findText(item.text())
                if item.isSelected() and cbox_index == -1:
                    self.theme_combo_box.insertItem(0, item.text())
                elif not item.isSelected() and cbox_index != -1:
                    self.theme_combo_box.removeItem(cbox_index)

    def update_progress(self, count, block_size):
        """
        Calculate and display the download progress. This method is called by download_file().
        """
        increment = (count * block_size) - self.previous_size
        self._increment_progress_bar(None, increment)
        self.previous_size = count * block_size

    def _increment_progress_bar(self, status_text, increment=1):
        """
        Update the wizard progress page.

        :param status_text: Current status information to display.
        :param increment: The value to increment the progress bar by.
        """
        if status_text:
            self.progress_label.setText(status_text)
        if increment > 0:
            self.progress_bar.setValue(self.progress_bar.value() + increment)
        self.application.process_events()

    def _pre_wizard(self):
        """
        Prepare the UI for the process.
        """
        self._start_download_setup()

    def _post_wizard(self):
        """
        Clean up the UI after the process has finished.
        """
        if self.max_progress:
            self.progress_bar.setValue(self.progress_bar.maximum())
            if self.has_run_wizard:
                text = translate('OpenLP.FirstTimeWizard',
                                 'Download complete. Click the \'{finish_button}\' button to return to OpenLP+.')
            else:
                text = translate('OpenLP.FirstTimeWizard',
                                 'Download complete. Click the \'{finish_button}\' button to start OpenLP+.')
        else:
            if self.has_run_wizard:
                text = translate('OpenLP.FirstTimeWizard', 'Click the \'{finish_button}\' button to return to OpenLP+.')
            else:
                text = translate('OpenLP.FirstTimeWizard', 'Click the \'{finish_button}\' button to start OpenLP+.')
        self.progress_label.setText(text.format(finish_button=self.finish_button_text))
        finish_button = self.button(QtWidgets.QWizard.WizardButton.FinishButton)
        finish_button.setEnabled(True)
        if not is_ui_theme(UiThemes.QDarkStyle):
            finish_button.setDefault(True)
        self.button(QtWidgets.QWizard.WizardButton.CancelButton).setVisible(False)
        self.application.process_events()

    def _perform_wizard(self):
        """
        Run the tasks in the wizard.
        """

        if self.has_web_access:
            if not self._download_selected() and not self.was_cancelled:
                critical_error_message_box(translate('OpenLP.FirstTimeWizard', 'Download Error'),
                                           translate('OpenLP.FirstTimeWizard', 'There was a connection problem while '
                                                     'downloading, so further downloads will be skipped. Try to re-run '
                                                     'the First Time Wizard later.'))

    def _download_selected(self):
        """
        Download selected songs, bibles and themes. Returns False on download error
        """
        # Build directories for downloads
        songs_destination_path = Path(gettempdir(), 'openlp')
        bibles_destination_path = AppLocation.get_section_data_path('bibles')
        themes_destination_path = AppLocation.get_section_data_path('themes')
        missed_files = []
        # Download songs
        for i in range(self.songs_list_widget.count()):
            item = self.songs_list_widget.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                filename, sha256 = item.data(QtCore.Qt.ItemDataRole.UserRole)
                self._increment_progress_bar(self.downloading.format(name=filename), 0)
                self.previous_size = 0
                destination = songs_destination_path / str(filename)
                if not download_file(self, '{path}{name}'.format(path=self.songs_url, name=filename),
                                     destination, sha256):
                    missed_files.append('Song: {name}'.format(name=filename))
        # Download Bibles
        bibles_iterator = QtWidgets.QTreeWidgetItemIterator(self.bibles_tree_widget)
        while bibles_iterator.value():
            item = bibles_iterator.value()
            if item.parent() and item.checkState(0) == QtCore.Qt.CheckState.Checked:
                bible, sha256 = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                self._increment_progress_bar(self.downloading.format(name=bible), 0)
                self.previous_size = 0
                if not download_file(self, '{path}{name}'.format(path=self.bibles_url, name=bible),
                                     bibles_destination_path / bible, sha256):
                    missed_files.append('Bible: {name}'.format(name=bible))
            bibles_iterator += 1
        # Download themes
        for item in self.themes_list_widget.selectedItems():
            self._increment_progress_bar(self.downloading.format(name=item.file_name), 0)
            self.previous_size = 0
            if not download_file(self, '{url}{file}'.format(url=self.themes_url, file=item.file_name),
                                 themes_destination_path / item.file_name, item.sha256):
                missed_files.append('Theme: {name}'.format(name=item.file_name))
        # Remote
        if self.remote_page.can_download_remote:
            self._increment_progress_bar(self.downloading.format(name='Web Remote'), 0)
            self._remote_version = None
            self._remote_failed = False
            self.remote_download_in_progress = True
            self._update_navigation_buttons(FirstTimePage.Progress)
            remote_worker = WebRemoteDownloadWorker()
            remote_worker.download_succeeded.connect(self._on_remote_download_succeeded)
            remote_worker.download_failed.connect(self._on_remote_download_failed)
            remote_worker.progress_updated.connect(self._on_remote_progress_updated)
            self.remote_download_thread = 'first_time_remote_download'
            run_thread(remote_worker, self.remote_download_thread)
            while not is_thread_finished(self.remote_download_thread):
                self.application.process_events()
                time.sleep(0.05)
            self.remote_download_in_progress = False
            self.remote_download_thread = None
            self._update_navigation_buttons(FirstTimePage.Progress)
            if self.was_cancelled:
                return False
            if self._remote_failed:
                missed_files.append('Web Remote')
            elif self._remote_version:
                self.settings.setValue('api/download version', self._remote_version)
        if missed_files:
            file_list = ''
            for entry in missed_files:
                file_list += '{text}<br \\>'.format(text=entry)
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg.setWindowTitle(translate('OpenLP.FirstTimeWizard', 'Network Error'))
            msg.setText(translate('OpenLP.FirstTimeWizard', 'Unable to download some files'))
            msg.setInformativeText(translate('OpenLP.FirstTimeWizard',
                                             'The following files were not able to be '
                                             'downloaded:<br \\>{text}'.format(text=file_list)))
            msg.setStandardButtons(msg.StandardButton.Ok)
            msg.exec()
        return True

    def _set_plugin_status(self, field, tag):
        """
        Set the status of a plugin.
        """
        status = PluginStatus.Active if field.checkState() == QtCore.Qt.CheckState.Checked else PluginStatus.Inactive
        self.settings.setValue(tag, status)
