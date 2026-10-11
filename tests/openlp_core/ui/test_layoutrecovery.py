"""Test persistent recovery from native Qt startup crashes without resetting user data."""
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from PySide6 import QtCore

from openlp.core.common.settings import Settings
from openlp.core.ui.layoutrecovery import begin_layout_startup, complete_layout_startup


def screen_list(count=1, match=0):
    screens = MagicMock()
    screens.__len__.return_value = count
    screens.get_screen_number.return_value = match
    return screens


def saved_layout(settings):
    state = QtCore.QByteArray(b'saved Qt dock state')
    settings.setValue('user interface/main window state', state)
    settings.setValue('user interface/preset layout/setup/main window state', state)
    settings.setValue('user interface/live splitter geometry', state)
    settings.setValue('user interface/main window position', QtCore.QPoint(-1920, 0))
    settings.setValue('user interface/show library', False)
    settings.setValue('core/recent files', ['Sunday.osz'])
    settings.setValue('core/screens', {'0': {'geometry': {}, 'is_primary': True}})
    return state


def test_successful_startup_preserves_layout(settings):
    state = saved_layout(settings)
    screens = screen_list()

    assert not begin_layout_startup(settings, screens)
    assert settings.value('user interface/main window state') == state
    assert Settings().value('core/layout startup pending') is True

    complete_layout_startup(settings, screens)

    screens.save_screen_settings.assert_called_once()
    assert Settings().value('core/layout startup pending') is False
    assert settings.value('user interface/main window state') == state


def test_interrupted_startup_recovers_on_next_launch(settings):
    state = saved_layout(settings)
    begin_layout_startup(settings, screen_list())
    # Reopen the settings as a new launch would, without completing the previous startup.
    next_launch = Settings()

    assert begin_layout_startup(next_launch, screen_list())
    assert not next_launch.contains('user interface/main window state')
    assert not next_launch.contains('user interface/preset layout/setup/main window state')
    assert not next_launch.contains('user interface/live splitter geometry')
    assert not next_launch.contains('user interface/main window position')
    assert QtCore.QSettings.value(next_launch, 'layout recovery/user interface/main window state') == state
    assert next_launch.value('user interface/show library') is False
    assert next_launch.value('core/recent files') == ['Sunday.osz']


@pytest.mark.parametrize('count,match', [(1, None), (2, 0)])
def test_monitor_change_recovers_before_restoring_layout(settings, count, match):
    saved_layout(settings)

    assert begin_layout_startup(settings, screen_list(count, match))
    assert not settings.contains('user interface/main window state')
    assert not settings.contains('user interface/preset layout/setup/main window state')


def test_first_launch_does_not_reset_layout(settings):
    state = saved_layout(settings)
    settings.remove('core/screens')

    assert not begin_layout_startup(settings, screen_list())
    assert settings.value('user interface/main window state') == state


@pytest.mark.parametrize('interrupted', [True, False])
def test_recovery_quarantines_modern_layouts(settings, interrupted):
    """Both crash and monitor recovery remove Modern state, retaining visibility intent."""
    state = QtCore.QByteArray(b'saved ADS dock state')
    keys = ['user interface/modern window state']
    for mode in ('default', 'setup', 'live'):
        for field in ('main window state', 'main window splitter geometry',
                      'live splitter geometry', 'preview splitter geometry'):
            keys.append(f'user interface/modern preset layout/{mode}/{field}')
        settings.setValue(f'user interface/modern preset layout/{mode}/visibility snapshot', 'saved visibility')
    for key in keys:
        settings.setValue(key, state)
    settings.setValue('core/layout startup pending', interrupted)
    settings.setValue('core/screens', {'0': {'geometry': {}, 'is_primary': True}})

    assert begin_layout_startup(settings, screen_list(match=0 if interrupted else None))

    for key in keys:
        assert not settings.contains(key)
        assert QtCore.QSettings.value(settings, 'layout recovery/' + key) == state
    for mode in ('default', 'setup', 'live'):
        assert settings.value(f'user interface/modern preset layout/{mode}/visibility snapshot') == 'saved visibility'


def test_repeated_failed_recovery_preserves_backup(settings):
    state = saved_layout(settings)
    begin_layout_startup(settings, screen_list(match=None))

    assert begin_layout_startup(settings, screen_list())
    assert QtCore.QSettings.value(settings, 'layout recovery/user interface/main window state') == state


def test_completion_saves_current_monitors(settings):
    screens = screen_list()
    current = {'0': {'geometry': {'width': 1280}, 'is_primary': True}}
    screens.save_screen_settings.side_effect = lambda: settings.setValue('core/screens', current)

    begin_layout_startup(settings, screens)
    complete_layout_startup(settings, screens)

    assert Settings().value('core/screens') == current
    assert not begin_layout_startup(settings, screens)


def test_abrupt_process_exit_leaves_recoverable_marker(tmp_path):
    # The shared settings fixture keeps its mkstemp handle open, which prevents
    # QSettings atomic file replacement on Windows. Use a closed file for this disk test.
    settings = Settings(str(tmp_path / 'layout.ini'), QtCore.QSettings.Format.IniFormat)
    saved_layout(settings)
    settings.sync()
    # os._exit bypasses Python exception handlers and Qt/Python shutdown, like a native crash.
    script = '''
import os
import sys
from unittest.mock import MagicMock
from PySide6 import QtCore
from openlp.core.common.settings import Settings
from openlp.core.ui.layoutrecovery import begin_layout_startup
Settings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
Settings.set_filename(sys.argv[1])
screens = MagicMock()
screens.__len__.return_value = 1
screens.get_screen_number.return_value = 0
settings = Settings()
'''
    crash_script = script + '''
begin_layout_startup(settings, screens)
assert settings.status() == QtCore.QSettings.Status.NoError
os._exit(23)
'''
    result = subprocess.run([sys.executable, '-c', crash_script, settings.fileName()],
                            capture_output=True, text=True, timeout=30)

    assert result.returncode == 23, result.stderr
    # Use another process for the next launch as well: QSettings instances in this
    # test process share an INI cache with the fixture that wrote the original file.
    recovery_script = script + '''
assert settings.value('core/layout startup pending') is True
assert begin_layout_startup(settings, screens)
assert not settings.contains('user interface/main window state')
assert QtCore.QSettings.value(settings, 'layout recovery/user interface/main window state') == \
    QtCore.QByteArray(b'saved Qt dock state')
'''
    recovered = subprocess.run([sys.executable, '-c', recovery_script, settings.fileName()],
                               capture_output=True, text=True, timeout=30)
    assert recovered.returncode == 0, recovered.stderr


def test_application_keeps_marker_until_queued_startup_completes(settings, qapp, monkeypatch):
    from openlp.core import app as app_module

    settings.setValue('core/has run wizard', True)
    settings.setValue('core/show splash', False)
    settings.setValue('core/update check', False)
    settings.setValue('api/update check', False)
    screens = screen_list()
    monkeypatch.setattr(app_module.ScreenList, 'create', lambda app: screens)
    monkeypatch.setattr(app_module, 'loader', lambda: None)
    monkeypatch.setattr(app_module, 'State', MagicMock())
    monkeypatch.setattr(app_module, 'set_default_theme', lambda app: None)
    monkeypatch.setattr(app_module, 'get_application_stylesheet', lambda: '')
    monkeypatch.setattr(qapp, 'backup_on_upgrade', lambda *args: None)
    monkeypatch.setattr(qapp, 'exec', lambda: 0)
    timers = []
    monkeypatch.setattr(app_module.QtCore.QTimer, 'singleShot', lambda delay, callback: timers.append(callback))

    def create_window():
        assert settings.value('core/layout startup pending') is True
        return MagicMock()

    monkeypatch.setattr(app_module, 'MainWindow', create_window)
    monkeypatch.setattr(app_module, 'refine_modern_layout', lambda window: None)

    assert qapp.run([], MagicMock()) == 0
    assert settings.value('core/layout startup pending') is True
    assert len(timers) == 1
    timers[0]()
    assert settings.value('core/layout startup pending') is False
