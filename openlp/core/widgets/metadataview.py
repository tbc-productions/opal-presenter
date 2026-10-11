"""Grouped, selectable metadata for Library inspectors and Cloud Library views."""
from fluentqt import FontRole, Label, ScrollBar, Spacing
from PySide6 import QtCore

from openlp.core.common.i18n import translate
from openlp.core.widgets import fluent as QtWidgets


class MetadataView(QtWidgets.QScrollArea):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setVerticalScrollBar(ScrollBar(QtCore.Qt.Orientation.Vertical, self))
        self.setHorizontalScrollBar(ScrollBar(QtCore.Qt.Orientation.Horizontal, self))
        self.setStyleSheet('QScrollArea { background: transparent; }')
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(Spacing.Small, 0, Spacing.Small, Spacing.Small)
        layout.setSpacing(Spacing.Medium)
        self.fields = {}
        file_keys = ('File size', 'File type', 'Item type', 'Source', 'Access')
        history_keys = ('Created', 'Modified', 'Modified by')
        groups = [('Details', [key for key in values if key not in file_keys + history_keys]),
                  ('File', file_keys), ('History', history_keys)]
        for title, keys in groups:
            keys = [key for key in keys if key in values]
            if not keys:
                continue
            card = QtWidgets.Card(content)
            fields = QtWidgets.QVBoxLayout(card)
            fields.setContentsMargins(Spacing.Medium, Spacing.Medium, Spacing.Medium, Spacing.Medium)
            fields.setSpacing(Spacing.Small)
            heading = QtWidgets.QLabel(translate('OpenLP.MetadataView', title), card)
            heading.setFluentTypography(FontRole.BodyStrong)
            fields.addWidget(heading)
            for key in keys:
                row = QtWidgets.QWidget(card)
                pair = QtWidgets.QVBoxLayout(row)
                pair.setContentsMargins(0, 0, 0, 0)
                pair.setSpacing(2)
                caption = QtWidgets.QLabel(translate('OpenLP.MetadataView', key), row)
                caption.setTextColorRole(Label.TextColorRole.Secondary)
                pair.addWidget(caption)
                value = QtWidgets.QLabel(values[key], row)
                value.setFluentTypography(FontRole.Body if title == 'Details' else FontRole.Caption)
                value.setTextFormat(QtCore.Qt.TextFormat.PlainText)
                value.setWordWrap(True)
                value.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
                value.setAccessibleName(caption.text())
                pair.addWidget(value)
                self.fields[key] = value
                fields.addWidget(row)
            layout.addWidget(card)
        layout.addStretch()
        self.setWidget(content)
        content.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
