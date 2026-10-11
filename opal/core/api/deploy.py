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
Download and "install" the remote web client
"""
import json
import logging
import re
from datetime import date
from zipfile import BadZipFile, ZipFile

from PySide6 import QtCore

from opal.core.common.applocation import AppLocation
from opal.core.common.httputils import download_file, get_web_page, get_openlp_user_agent
from opal.core.common.registry import Registry
from opal.core.threading import ThreadWorker, run_thread
from opal.core.lib.nativefile import validate_archive

REMOTE_URL = 'https://api.github.com/repos/tbc-productions/opal-presenter-web-remote/releases/latest'
LOCAL_VERSION = re.compile(r'appVersion.*=.*[\'"](.*?)[\'"];?')

log = logging.getLogger(__name__)


class RemoteVersionWorker(ThreadWorker):
    """
    A worker class to fetch the version of the web remote. This is run from within a thread so that it
    doesn't affect the loading time of OpenLP.
    """
    new_version = QtCore.Signal(str)
    no_internet = QtCore.Signal()

    def __init__(self, current_version):
        """
        Constructor for the version check worker.

        :param string current_version: The current version of the web remote
        """
        log.debug('VersionWorker - Initialise')
        super().__init__(None)
        self.current_version = current_version or '0.0'

    def start(self):
        """
        Check the latest version of the web remote against the version file on the OpenLP server.
        """
        log.debug('RemoteVersionWorker - Start')
        version_info = None
        retries = 0
        while retries < 3:
            try:
                version_info = download_version_info()
                log.debug('New version found: %s', version_info['latest']['version'])
                break
            except (OSError, TypeError, ValueError, KeyError):
                log.exception('Unable to connect to OpenLP server to download version file')
                retries += 1
        else:
            self.no_internet.emit()
        if version_info and (QtCore.QVersionNumber.fromString(version_info['latest']['version']) >
                             QtCore.QVersionNumber.fromString(self.current_version)):
            self.new_version.emit(version_info['latest']['version'])
        self.quit.emit()


def deploy_zipfile(app_root_path, zip_name):
    """
    Process the downloaded zip file and add to the correct directory

    :param str zip_name: the zip file name to be processed
    :param pathlib.Path app_root_path: The directory to expand the zip to

    :return: None
    """
    zip_path = app_root_path / zip_name
    with ZipFile(zip_path) as web_zip:
        validate_archive(web_zip)
        web_zip.extractall(app_root_path)


def download_version_info(timeout=None, retries=None, session=None):
    """
    Download the version information file
    """
    try:
        if timeout is None:
            file_contents = get_web_page(REMOTE_URL, headers={'User-Agent': get_openlp_user_agent()},
                                         retries=retries, session=session)
        else:
            file_contents = get_web_page(REMOTE_URL, headers={'User-Agent': get_openlp_user_agent()},
                                         timeout=timeout, retries=retries, session=session)
    except ConnectionError:
        return False
    if not file_contents:
        return None
    try:
        release = json.loads(file_contents)
        if release.get('draft') or release.get('prerelease'):
            return None
        asset = next((asset for asset in release.get('assets', [])
                      if asset.get('name') == 'opal-presenter-web-remote.zip'), None)
        if not asset:
            return None
        if not isinstance(asset.get('size'), int) or asset['size'] < 0:
            raise ValueError('Invalid remote bundle size.')
        if not isinstance(asset['browser_download_url'], str) or not asset['browser_download_url'].startswith(
                'https://github.com/tbc-productions/opal-presenter-web-remote/releases/download/'):
            raise ValueError('Invalid remote bundle download URL.')
        return {'latest': {'version': release['tag_name'].removeprefix('v'), 'filename': asset['name'],
                           'size': asset['size'], 'url': asset['browser_download_url']}}
    except (ValueError, KeyError, TypeError):
        log.warning('Invalid Opal Web Remote release metadata')
        return None


def get_latest_size():
    """
    Download the version info file and get the size of the latest file
    """
    version_info = download_version_info()
    if not version_info:
        log.warning('Unable to access the version information, abandoning download')
        return 0
    return version_info['latest']['size']


def download_and_install(callback=None, can_update_range=True, timeout=None, retries=None, session=None):
    """
    Download the web site and deploy it.
    """
    if timeout is not None or retries is not None:
        version_info = download_version_info(timeout=timeout, retries=retries, session=session)
    else:
        version_info = download_version_info(session=session)
    if not version_info:
        log.warning('Unable to access the version information, abandoning download')
        # Show the user an error message
        return None
    file_size = version_info['latest']['size']
    if can_update_range:
        callback.setRange(0, file_size)
    zip_path = AppLocation.get_section_data_path('remotes') / 'remote.zip'
    download_kwargs = {}
    if timeout is not None:
        download_kwargs['timeout'] = timeout
    if retries is not None:
        download_kwargs['retries'] = retries
    if download_file(callback, version_info['latest']['url'], zip_path,
                     session=session, **download_kwargs):
        if not zip_path.exists():
            # File was deleted because the download was cancelled
            return None
        try:
            deploy_zipfile(AppLocation.get_section_data_path('remotes'), 'remote.zip')
        except (OSError, ValueError, BadZipFile):
            log.exception('Could not install the Opal Web Remote bundle')
            return None
        return version_info['latest']['version']
    return None


def check_for_remote_update(main_window):
    """
    Run a thread to download and check the version of OpenLP

    :param MainWindow main_window: The OpenLP main window.
    """
    last_check_date = Registry().get('settings').value('api/last version test')
    if date.today().strftime('%Y-%m-%d') <= last_check_date:
        log.debug('Version check skipped, last checked today')
        return
    worker = RemoteVersionWorker(Registry().get('settings').value('api/download version'))
    # TODO: Use this to figure out if there's an Internet connection?
    # worker.no_internet.connect(main_window.on_no_internet)
    run_thread(worker, 'remote-version',
               queued_connections=[(worker.new_version, main_window.on_new_remote_version)])


def get_installed_version():
    """
    Get the version of the remote that is installed, or None if there is no remote
    """
    version_file = AppLocation.get_section_data_path('remotes') / 'assets' / 'version.js'
    if not version_file.exists():
        return None
    version_read = version_file.read_text()
    if not version_read:
        return None
    match = LOCAL_VERSION.search(version_read)
    if not match:
        return None
    return match.group(1)
