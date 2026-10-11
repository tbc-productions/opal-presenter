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
The entrypoint for OpenLP
"""
import atexit
import faulthandler
import logging
import multiprocessing

# from OpenGL import GL  # noqa

from opal.core.app import main
from opal.core.common.applocation import AppLocation
from opal.core.common.path import create_paths

log = logging.getLogger(__name__)
error_log_file = None


def tear_down_fault_handling():
    """
    When Python exits, close the file we were using for the faulthandler
    """
    global error_log_file  # noqa: F824
    error_log_file.close()


def set_up_fault_handling():
    """
    Set up the Python fault handler
    """
    global error_log_file
    # Create the cache directory if it doesn't exist, and enable the fault handler to log to an error log file
    try:
        create_paths(AppLocation.get_directory(AppLocation.CacheDir))
        error_log_file = (AppLocation.get_directory(AppLocation.CacheDir) / 'error.log').open('wb')
        atexit.register(tear_down_fault_handling)
        faulthandler.enable(error_log_file)
    except OSError:
        log.exception('An exception occurred when enabling the fault handler')
        atexit.unregister(tear_down_fault_handling)
        if error_log_file:
            error_log_file.close()


def start():
    """
    Instantiate and run the application.
    """
    # PyInstaller's worker dispatch is required on every platform, before opening logs or settings.
    multiprocessing.freeze_support()
    set_up_fault_handling()
    main()


if __name__ == '__main__':
    start()                 # pragma: nocover
