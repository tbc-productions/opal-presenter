"""Shared restart reminder for changes that take effect on the next application run."""
from PySide6 import QtCore


def show_restart_message(parent, title, text):
    """Offer a secondary restart action, deferred until the caller finishes saving."""
    from openlp.core.common.i18n import translate
    from openlp.core.common.registry import Registry
    from openlp.core.widgets import fluent as QtWidgets

    dialog = QtWidgets.ContentDialog(parent)
    dialog.setTitle(title)
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    dialog.setContent(label)
    dialog.setMinimumWidth(420)
    dialog.setPrimaryButtonText(translate('OpenLP.Restart', 'OK'))
    dialog.setSecondaryButtonText(translate('OpenLP.Restart', 'Restart Opal Presenter'))
    dialog.setDefaultButton(QtWidgets.fluentqt.ContentDialogButton.Primary)
    result = dialog.exec()
    if result == dialog.ResultSecondary:
        application = Registry().get('application')
        if application is not None:
            # Some reminders appear inside a settings tab's save() method. Finish saving
            # and unwind its modal dialog before entering the normal main-window close flow.
            QtCore.QTimer.singleShot(0, application.request_restart)
    dialog.deleteLater()
