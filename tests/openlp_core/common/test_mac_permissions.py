from unittest.mock import MagicMock, patch

from openlp.core.common.mac_permissions import request_presentation_permissions


def test_presentation_permissions_are_not_requested_when_already_granted():
    graphics = MagicMock()
    graphics.CGPreflightPostEventAccess.return_value = True
    graphics.CGPreflightScreenCaptureAccess.return_value = True

    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.ctypes.CDLL', return_value=graphics), \
            patch('openlp.core.common.mac_permissions.QtWidgets.QMessageBox.information') as information:
        request_presentation_permissions(MagicMock())

    information.assert_not_called()
    graphics.CGRequestPostEventAccess.assert_not_called()
    graphics.CGRequestScreenCaptureAccess.assert_not_called()


def test_presentation_permissions_are_explained_and_requested_when_missing():
    graphics = MagicMock()
    graphics.CGPreflightPostEventAccess.return_value = False
    graphics.CGPreflightScreenCaptureAccess.return_value = False
    parent = MagicMock()

    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.ctypes.CDLL', return_value=graphics), \
            patch('openlp.core.common.mac_permissions.QtWidgets.QMessageBox.information') as information:
        request_presentation_permissions(parent)

    information.assert_called_once()
    assert information.call_args.args[0] is parent
    assert 'Accessibility' in information.call_args.args[2]
    assert 'Screen Recording' in information.call_args.args[2]
    graphics.CGRequestPostEventAccess.assert_called_once_with()
    graphics.CGRequestScreenCaptureAccess.assert_called_once_with()
