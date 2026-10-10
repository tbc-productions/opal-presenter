"""Aspect ratios for previewing a design on another display."""

from math import gcd

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.display.screens import ScreenList
from openlp.core.common.i18n import translate
from openlp.core.lib.ui import create_button_box
from openlp.core.ui.icons import UiIcons


def tr(text):
    return translate('SongsPlugin.SlideDesigner', text)


def ratio_components(width, height):
    divisor = gcd(width, height)
    ratio = width // divisor, height // divisor
    return (16, 10) if ratio == (8, 5) else ratio


class OutputCombo(QtWidgets.QComboBox):
    opening = QtCore.Signal()

    def showPopup(self):
        self.opening.emit()
        super().showPopup()


class PreviewOutput(QtWidgets.QWidget):
    def __init__(self, designer):
        super().__init__(designer)
        self.designer = designer
        self.combo = OutputCombo()
        self.combo.setAccessibleName(tr('Preview aspect ratio'))
        self.combo.setMinimumWidth(100)
        self.combo.setMaximumWidth(300)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self.combo)
        self.profile_button = designer.tool_button(
            tr('Create or edit aspect ratio profile'), UiIcons().edit, icon_only=True)
        self.profile_button.clicked.connect(self.edit_profile)
        row.addWidget(self.profile_button)
        self.delete_button = designer.tool_button(tr('Delete aspect ratio profile'), UiIcons().delete, icon_only=True)
        self.delete_button.clicked.connect(self.delete_profile)
        row.addWidget(self.delete_button)
        self.populate()
        self.combo.currentIndexChanged.connect(self.changed)
        self.combo.opening.connect(self.refresh_outputs)

    def refresh_outputs(self):
        before = self.combo.currentData()
        self.populate()
        if before != self.combo.currentData():
            self.changed()

    def profiles(self):
        profiles = self.designer.settings.value('slide_designer/preview profiles')
        if not isinstance(profiles, dict):
            return {}
        return {name: size for name, size in profiles.items() if isinstance(name, str) and name.strip()
                and isinstance(size, list) and len(size) == 2
                and all(type(value) is int and 1 <= value <= 16384 for value in size)}

    def populate(self):
        selected = self.combo.currentData()
        with QtCore.QSignalBlocker(self.combo):
            self.combo.clear()
            for screen in ScreenList():
                size = screen.display_geometry.size()
                width, height = ratio_components(size.width(), size.height())
                self.combo.addItem(f'{screen} · {screen.name or tr("Display")} · '
                                   f'{width}:{height}',
                                   ('display', screen.number, size.width(), size.height()))
            for name, width, height in (('16:9', 1920, 1080), ('16:10', 1920, 1200),
                                        ('64:27', 2560, 1080), ('4:3', 1440, 1080)):
                self.combo.addItem(name, ('preset', width, height))
            for name, size in self.profiles().items():
                width, height = ratio_components(*size)
                self.combo.addItem(f'{name} · {width}:{height}', ('profile', name, *size))
            index = self.index(selected)
            if index < 0 and selected and selected[0] in ('display', 'profile'):
                index = next((i for i in range(self.combo.count())
                              if self.combo.itemData(i)[:2] == selected[:2]), -1)
            self.combo.setCurrentIndex(index if index >= 0 else self.index(('preset', 1920, 1080)))
        self.delete_button.setEnabled(self.combo.currentData()[0] == 'profile')

    def index(self, data):
        return next((index for index in range(self.combo.count()) if self.combo.itemData(index) == data), -1)

    def output_size(self):
        """Use one bounded canvas per ratio, independently of the display resolution."""
        data = self.combo.currentData()
        width, height = ratio_components(*data[-2:])
        scale = max(1, min(round(1080 / height), 16384 // width))
        return QtCore.QSize(width * scale, height * scale)

    def changed(self):
        self.delete_button.setEnabled(self.combo.currentData()[0] == 'profile')
        self.designer.commit_text()
        self.designer.fit_canvas()
        self.designer.schedule_refresh()

    def save_profile(self, name, width, height, previous=None):
        profiles = self.profiles()
        if previous:
            profiles.pop(previous, None)
        profiles[name] = [width, height]
        self.designer.settings.setValue('slide_designer/preview profiles', profiles)
        self.populate()
        self.combo.setCurrentIndex(self.index(('profile', name, width, height)))
        self.changed()

    def delete_profile(self):
        data = self.combo.currentData()
        if data[0] != 'profile':
            return
        profiles = self.profiles()
        profiles.pop(data[1], None)
        self.designer.settings.setValue('slide_designer/preview profiles', profiles)
        self.populate()
        self.changed()

    def edit_profile(self):
        data = self.combo.currentData()
        previous = data[1] if data[0] == 'profile' else None
        dialog = QtWidgets.FormDialog(self.window())
        dialog.setWindowTitle(tr('Preview aspect ratio profile'))
        dialog.setMinimumWidth(420)
        layout = QtWidgets.QFormLayout(dialog.content_widget)
        name = QtWidgets.QLineEdit()
        name.setText(previous or '')
        name.setPlaceholderText(tr('Unique profile name'))
        name.selectAll()
        width, height = QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
        ratio_width, ratio_height = ratio_components(*data[-2:])
        for field, value in ((width, ratio_width), (height, ratio_height)):
            field.setRange(1, 16384)
            field.setValue(value)
        for caption, field in ((tr('Name'), name), (tr('Ratio width'), width), (tr('Ratio height'), height)):
            label = QtWidgets.QLabel(caption)
            label.setBuddy(field)
            layout.addRow(label, field)
        buttons = create_button_box(dialog, 'preview_profile_buttons', ['save', 'cancel'])
        layout.addRow(buttons)
        save = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save)

        def validate():
            text = name.text().strip()
            save.setEnabled(bool(text) and (text == previous or text not in self.profiles()))
        name.setMaxLength(120)
        name.textChanged.connect(validate)
        validate()
        QtCore.QTimer.singleShot(0, name, name.setFocus)
        try:
            if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                self.save_profile(name.text().strip(), width.value(), height.value(), previous)
        finally:
            dialog.deleteLater()
