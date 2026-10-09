"""Independent Fluent window for the inner song/custom slide editor."""
from PySide6 import QtCore
import fluentqt

from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.i18n import translate
from openlp.plugins.slide_designer.forms.exitguard import designer_exit_guard


class DesignerWindow(fluentqt.Window):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.heading = QtWidgets.QLabel()
        self.heading.setContentsMargins(12, 0, 12, 0)
        self.heading.setFluentTypography(fluentqt.FontRole.BodyStrong)
        self.titleBar().setContentWidget(self.heading)
        self.update_item_title()
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.host = QtWidgets.QWidget()
        self.host.setLayout(editor.dialog_layout)
        self.setContentWidget(self.host)
        self.resize(1440, 900)
        editor.mark_saved()

    def request_close_for_exit(self):
        """Use the normal save contract; failed validation or cancellation stops app exit."""
        if not self.editor.has_unsaved_changes():
            self.editor.reject()
            return True

        def tr(text):
            return translate('SongsPlugin.SlideDesigner', text)

        dialog = QtWidgets.ContentDialog(self)
        dialog.setObjectName('designer_exit_dialog')
        dialog.setTitle(tr('Save Song?') if self.editor.design_kind == 'song' else tr('Save Custom Slides?'))
        title = self.editor.design_owner.title_edit.text().strip()
        message = tr('Save changes to “{title}” before exiting OpenLP+?').format(title=title) if title else \
            tr('Save your changes before exiting OpenLP+?')
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        dialog.setContent(label)
        dialog.setPrimaryButtonText(tr('Save'))
        dialog.setSecondaryButtonText(tr('Discard'))
        dialog.setCloseButtonText(tr('Cancel'))
        dialog.setDefaultButton(fluentqt.ContentDialogButton.Primary)
        dialog.setSmokeEnabled(True)
        dialog.setDragEnabled(False)
        dialog.setMinimumWidth(420)
        try:
            choice = dialog.exec()
        finally:
            dialog.deleteLater()
        if choice == dialog.ResultSecondary:
            self.editor.reject()
            return True
        if choice != dialog.ResultPrimary:
            return False
        finished = []
        self.editor.finished.connect(finished.append)
        try:
            self.editor.accept()
        finally:
            self.editor.finished.disconnect(finished.append)
        return finished == [QtWidgets.QDialog.DialogCode.Accepted]

    def update_item_title(self):
        title = self.editor.design_owner.title_edit.text().strip()
        if not title:
            title = translate('SongsPlugin.SlideDesigner',
                              'New Song' if self.editor.design_kind == 'song' else 'New Custom Slide')
        self.setWindowTitle(f'{title} - OpenLP+')
        self.heading.setText(self.windowTitle())

    def closeEvent(self, event):
        self.editor.reject()
        event.accept()


def exec_designer_window(editor):
    """Keep the existing draft/accept contract without placing a modal window over OpenLP+."""
    owner = editor.design_owner
    owner_visible = owner.isVisible()
    owner._designer_open = True
    owner.hide()
    window = DesignerWindow(editor)
    editor.designer_window = window
    owner._fluent_dialog_host = window
    editor._fluent_dialog_host = window
    loop = QtCore.QEventLoop()
    result = [0]
    exit_guard = designer_exit_guard()
    exit_guard.add(window)

    def finished(code):
        result[0] = code
        exit_guard.remove(window)
        window.hide()
        loop.quit()

    editor.finished.connect(finished)
    try:
        window.show()
        loop.exec()
    finally:
        exit_guard.remove(window)
        editor.finished.disconnect(finished)
        editor.setLayout(window.host.layout())
        window.hide()
        window.deleteLater()
        editor.designer_window = None
        del owner._fluent_dialog_host
        del editor._fluent_dialog_host
        owner._designer_open = False
        if owner_visible:
            owner.show()
            owner.raise_()
    return result[0]
