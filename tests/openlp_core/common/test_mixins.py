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
Package to test the opal.core.common.mixins package.
"""
import pytest
from unittest.mock import MagicMock, patch

from opal.core.common.mixins import RegistryProperties
from opal.core.common.registry import Registry


@pytest.fixture
def registry_env():
    """An instance of the Registry"""
    Registry.create()

    class Test(RegistryProperties):
        pass
    return Test()


def test_no_application(registry_env):
    """
    Test property if no registry value assigned
    """
    # GIVEN an Empty Registry
    # WHEN there is no Application
    # THEN the application should be none
    assert registry_env.application is None, 'The application value should be None'


def test_application(registry_env):
    """
    Test property if registry value assigned
    """
    # GIVEN an Empty Registry
    application = MagicMock()

    # WHEN the application is registered
    Registry().register('application', application)

    # THEN the application should be none
    assert registry_env.application == application, 'The application value should match'


@patch('opal.core.common.mixins.is_win')
def test_application_on_windows(mocked_is_win, registry_env):
    """
    Test property if registry value assigned on Windows
    """
    # GIVEN an Empty Registry and we're on Windows
    application = MagicMock()
    mocked_is_win.return_value = True

    # WHEN the application is registered
    Registry().register('application', application)

    # THEN the application should be none
    assert registry_env.application == application, 'The application value should match'


@patch('opal.core.common.mixins.is_win')
def test_get_application_on_windows(mocked_is_win):
    """
    Set that getting the application object on Windows happens dynamically
    """
    # GIVEN an Empty Registry and we're on Windows
    mocked_is_win.return_value = True
    mock_application = MagicMock()
    reg_props = RegistryProperties()
    registry = Registry()

    # WHEN the application is accessed
    with patch.object(registry, 'get') as mocked_get:
        mocked_get.return_value = mock_application
        actual_application = reg_props.application

    # THEN the application should be the mock object, and the correct function should have been called
    assert mock_application == actual_application, 'The application value should match'
    mocked_is_win.assert_called_with()
    mocked_get.assert_called_with('application')


def test_debug_logging_preserves_queued_qobject_receiver(qapp, caplog):
    """Debug tracing must not deliver GUI callbacks in a worker thread."""
    import logging
    from PySide6 import QtCore
    from opal.core.common.mixins import LogMixin

    class Receiver(QtCore.QObject, LogMixin):
        def receive(self, title, message):
            deliveries.append((QtCore.QThread.currentThread(), title, message))
            loop.quit()

    class Worker(QtCore.QObject):
        ready = QtCore.Signal(str, str)

        def start(self):
            self.ready.emit('Web remote update', 'A new version is available')

    deliveries = []
    loop = QtCore.QEventLoop()
    receiver = Receiver()
    with caplog.at_level(logging.DEBUG):
        receiver.log_debug('Enable method tracing')
        assert receiver.receive.__self__ is receiver
        thread = QtCore.QThread()
        worker = Worker()
        worker.moveToThread(thread)
        worker.ready.connect(receiver.receive, QtCore.Qt.ConnectionType.QueuedConnection)
        thread.started.connect(worker.start)
        thread.finished.connect(worker.deleteLater)
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(2000)
        try:
            thread.start()
            loop.exec()
        finally:
            timer.stop()
            thread.quit()
            assert thread.wait(2000)
    assert deliveries == [(receiver.thread(), 'Web remote update', 'A new version is available')]
    assert 'Entering receive' in caplog.text


def test_logging_wrapper_retains_method_arguments_and_exceptions(caplog):
    """Binding the tracing wrapper must preserve normal method behaviour."""
    import logging
    from opal.core.common.mixins import LogMixin

    class Receiver(LogMixin):
        def multiply(self, value, *, factor=2):
            return value * factor

        def fail(self):
            raise ValueError('Test exception')

    receiver = Receiver()
    with caplog.at_level(logging.DEBUG):
        receiver.log_debug('Enable method tracing')
        assert receiver.multiply(3, factor=4) == 12
        with pytest.raises(ValueError, match='Test exception'):
            receiver.fail()
    assert 'Entering multiply' in caplog.text
    assert 'Entering fail' in caplog.text
