"""Independent Fluent window for the inner song/custom slide editor."""
from PySide6 import QtCore
import fluentqt

from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.i18n import translate


class DesignerWindow(fluentqt.Window):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        title = editor.design_owner.title_edit.text().strip()
        if not title:
            title = translate('SongsPlugin.SlideDesigner',
                              'New Song' if editor.design_kind == 'song' else 'New Custom Slide')
        self.setWindowTitle(f'{title} - OpenLP+')
        heading = QtWidgets.QLabel(self.windowTitle())
        heading.setContentsMargins(12, 0, 12, 0)
        heading.setFluentTypography(fluentqt.FontRole.BodyStrong)
        self.titleBar().setContentWidget(heading)
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.host = QtWidgets.QWidget()
        self.host.setLayout(editor.dialog_layout)
        self.setContentWidget(self.host)
        self.resize(1440, 900)

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
    loop = QtCore.QEventLoop()
    result = [0]

    def finished(code):
        result[0] = code
        window.hide()
        loop.quit()

    editor.finished.connect(finished)
    try:
        window.show()
        loop.exec()
    finally:
        editor.finished.disconnect(finished)
        editor.setLayout(window.host.layout())
        window.hide()
        window.deleteLater()
        editor.designer_window = None
        owner._designer_open = False
        if owner_visible:
            owner.show()
            owner.raise_()
    return result[0]
