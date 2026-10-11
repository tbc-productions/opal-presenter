"""Screen setup reminders and navigation to the Screens settings page."""
from PySide6 import QtCore

from opal.core.common.i18n import translate
from opal.core.common.registry import Registry


def show_screen_setup_message(parent, title, text):
    """Return whether the screen setup reminder's secondary action was selected."""
    from opal.core.widgets import fluent as QtWidgets

    dialog = QtWidgets.ContentDialog(parent)
    dialog.setTitle(title)
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    dialog.setContent(label)
    dialog.setMinimumWidth(420)
    dialog.setPrimaryButtonText(translate('OpenLP.Ui', 'OK'))
    dialog.setSecondaryButtonText(translate('OpenLP.ScreensTab', 'Configure screens'))
    dialog.setDefaultButton(QtWidgets.fluentqt.ContentDialogButton.Primary)
    result = dialog.exec()
    dialog.deleteLater()
    return result == QtWidgets.fluentqt.ContentDialog.ResultSecondary


def request_screen_configuration():
    """Open Screens after the display refresh, or after startup has created the settings form."""
    registry = Registry()
    if registry.has('settings_form'):
        QtCore.QTimer.singleShot(0, _open_screen_settings)
    elif _configure_screens_after_startup not in registry.functions_list.get('bootstrap_completion', []):
        registry.register_function('bootstrap_completion', _configure_screens_after_startup)


def _configure_screens_after_startup():
    QtCore.QTimer.singleShot(0, _open_screen_settings)


def _open_screen_settings():
    Registry().remove_function('bootstrap_completion', _configure_screens_after_startup)
    settings_form = Registry().get('settings_form')
    if settings_form is not None:
        settings_form.exec(translate('OpenLP.ScreensTab', 'Screens'))
