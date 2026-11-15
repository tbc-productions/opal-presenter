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
import logging
import os
import shutil
import stat
import threading
import time
from pathlib import Path

from opal.core.common.platform import is_win


log = logging.getLogger(__name__)

# macOS FileProvider dataless flag (stat.SF_DATALESS = 0x40000000)
_MACOS_SF_DATALESS = getattr(stat, 'SF_DATALESS', 0x40000000)
# Windows OneDrive Files On-Demand attributes (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
_WINDOWS_CLOUD_ATTRIBUTES = 0x00001000 | 0x00400000
_HYDRATION_CHUNK_SIZE = 1024 * 1024


def _stat_is_cloud_placeholder(stat_result) -> bool:
    """Return True when a stat result indicates an unhydrated cloud-storage placeholder."""
    flags = getattr(stat_result, 'st_flags', 0)
    if isinstance(flags, int) and bool(flags & _MACOS_SF_DATALESS):
        return True
    file_attributes = getattr(stat_result, 'st_file_attributes', 0)
    if isinstance(file_attributes, int) and bool(file_attributes & _WINDOWS_CLOUD_ATTRIBUTES):
        return True
    return False


def _cloud_placeholder_targets(path) -> list[Path]:
    """Return the list of unhydrated cloud placeholder files for a file or bundle path."""
    if not path:
        return []
    try:
        path_obj = Path(os.fspath(path))
        st = path_obj.stat()
    except (OSError, TypeError, ValueError):
        return []
    mode = getattr(st, 'st_mode', 0)
    if isinstance(mode, int) and stat.S_ISDIR(mode):
        if path_obj.suffix.lower() != '.key':
            return []
        targets = []
        try:
            for root, _, files in os.walk(path_obj):
                for file_name in files:
                    candidate = Path(root) / file_name
                    try:
                        if _stat_is_cloud_placeholder(candidate.stat()):
                            targets.append(candidate)
                    except OSError:
                        continue
        except OSError:
            return []
        return targets
    if _stat_is_cloud_placeholder(st):
        return [path_obj]
    return []


def is_cloud_placeholder(path) -> bool:
    """
    Return True when ``path`` is a cloud-storage placeholder (such as an unsynced OneDrive or iCloud Drive file)
    whose contents have not yet been downloaded locally.
    """
    return bool(_cloud_placeholder_targets(path))


def _hydrate_file_contents(target: Path) -> None:
    """Sequentially read ``target`` to EOF so the OS FileProvider materialises the full file locally."""
    with target.open('rb') as handle:
        while handle.read(_HYDRATION_CHUNK_SIZE):
            pass


def ensure_local_file(path, timeout: float = 120.0) -> bool:
    """
    Ensure that a cloud-backed file (such as an unsynced OneDrive or iCloud Drive placeholder) is downloaded locally
    before callers open, seek or probe it.

    For normal local files (and test doubles) this returns ``True`` immediately after a single ``stat`` check.
    When called on the Qt GUI thread for an unhydrated cloud file, hydration runs on a background thread while the
    Qt event loop continues processing paint/timer events.
    """
    targets = _cloud_placeholder_targets(path)
    if not targets:
        return True
    path_obj = Path(os.fspath(path))
    log.info('Materialising cloud placeholder file: %s', path_obj)

    def _hydrate_all():
        for target in targets:
            _hydrate_file_contents(target)

    qt_app = None
    on_gui_thread = False
    try:
        from PySide6 import QtCore
        qt_app = QtCore.QCoreApplication.instance()
        on_gui_thread = qt_app is not None and QtCore.QThread.currentThread() is qt_app.thread()
    except Exception:
        on_gui_thread = False

    if not on_gui_thread:
        try:
            _hydrate_all()
        except OSError:
            log.exception('Failed to materialise cloud file %s', path_obj)
            return False
        return not is_cloud_placeholder(path_obj)

    done = threading.Event()
    errors = []

    def _worker():
        try:
            _hydrate_all()
        except Exception as exc:
            errors.append(exc)
        finally:
            done.set()

    opal_app = None
    main_window = None
    try:
        from opal.core.common.i18n import translate
        from opal.core.common.registry import Registry
        opal_app = Registry().get('application')
        main_window = Registry().get('main_window')
        if opal_app and hasattr(opal_app, 'set_busy_cursor'):
            opal_app.set_busy_cursor()
        if main_window and hasattr(main_window, 'show_status_message'):
            main_window.show_status_message(
                translate('OpenLP', 'Downloading from cloud storage: {file_name}…').format(file_name=path_obj.name))
    except Exception:
        pass

    thread = threading.Thread(target=_worker, name=f'opal-cloud-hydrate-{path_obj.name}', daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout if timeout and timeout > 0 else None
    try:
        from PySide6 import QtCore
        while not done.wait(0.02):
            if deadline is not None and time.monotonic() >= deadline:
                log.warning('Timed out waiting for cloud file %s to materialise', path_obj)
                return False
            qt_app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
    finally:
        if opal_app and hasattr(opal_app, 'set_normal_cursor'):
            try:
                opal_app.set_normal_cursor()
            except Exception:
                pass
        if main_window and hasattr(main_window, 'show_status_message'):
            try:
                main_window.show_status_message('')
            except Exception:
                pass

    if errors:
        log.error('Failed to materialise cloud file %s: %s', path_obj, errors[0])
        return False
    return not is_cloud_placeholder(path_obj)


def replace_params(args, kwargs, params):
    """
    Apply a transformation function to the specified args or kwargs

    :param tuple args: Positional arguments
    :param dict kwargs: Key Word arguments
    :param params: A tuple of tuples with the position and the key word to replace.
    :return: The modified positional and keyword arguments
    :rtype: tuple[tuple, dict]


    Usage:
        Take a method with the following signature, and assume we which to apply the str function to arg2:
            def method(arg1=None, arg2=None, arg3=None)

        As arg2 can be specified postitionally as the second argument (1 with a zero index) or as a keyword, the we
        would call this function as follows:

        replace_params(args, kwargs, ((1, 'arg2', str),))
    """
    args = list(args)
    for position, key_word, transform in params:
        if len(args) > position:
            args[position] = transform(args[position])
        elif key_word in kwargs:
            kwargs[key_word] = transform(kwargs[key_word])
    return tuple(args), kwargs


def which(*args, **kwargs):
    """
    Wraps :func:shutil.which` so that it return a Path objects.

    :rtype: Path

    See the following link for more information on the other parameters:
        https://docs.python.org/3/library/shutil.html#shutil.which
    """
    file_name = shutil.which(*args, **kwargs)
    if file_name:
        return str_to_path(file_name)
    return None


def path_to_str(path=None):
    """
    A utility function to convert a Path object or NoneType to a string equivalent.

    :param Path | None path: The value to convert to a string
    :return: An empty string if :param:`path` is None, else a string representation of the :param:`path`
    :rtype: str
    """
    if isinstance(path, str):
        return path
    if not isinstance(path, Path) and path is not None:
        raise TypeError('parameter \'path\' must be of type Path or NoneType')
    if path is None:
        return ''
    else:
        return str(path)


def str_to_path(string):
    """
    A utility function to convert a str object to a Path or NoneType.

    This function is of particular use because initating a Path object with an empty string causes the Path object to
    point to the current working directory.

    :param str string: The string to convert
    :return: None if :param:`string` is empty, or a Path object representation of :param:`string`
    :rtype: Path | None
    """
    if isinstance(string, Path):
        return string
    if not isinstance(string, str):
        log.error('parameter \'string\' must be of type str, got {} which is a {} instead'.format(string, type(string)))
        return None
    if string == '':
        return None
    return Path(string)


def create_paths(*paths, **kwargs):
    """
    Create one or more paths

    :param Path paths: The paths to create
    :param bool do_not_log: To not log anything. This is need for the start up, when the log isn't ready.
    :rtype: None
    """
    for path in paths:
        if not kwargs.get('do_not_log', False):
            log.debug('create_path {path}'.format(path=path))
        try:
            if not path.exists():
                path.mkdir(parents=True)
        except OSError:
            if not kwargs.get('do_not_log', False):
                log.exception('failed to check if directory exists or create directory')


def files_to_paths(file_names):
    """
    Convert a list of file names in to a list of file paths.

    :param list[str] file_names: The list of file names to convert.
    :return: The list converted to file paths
    :rtype: Path
    """
    if file_names:
        return [str_to_path(file_name) for file_name in file_names]


def resolve(path_obj, is_strict=False):
    """
    Resolve a Path object, bypassing symlink resolving on Windows

    :param Path path_obj: The path object to resolve
    :return: The resolved Path object
    :rtype: Path
    """
    if is_win():
        resolved_path = Path(os.path.realpath(path_obj))
        if is_strict:
            # Mirror the behaviour of Path.resolve(strict=True)
            resolved_path.lstat()
        return resolved_path
    return path_obj.resolve(strict=is_strict)
