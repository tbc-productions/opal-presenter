"""Shared Fluent item-count footer for Library lists and designer media browsers."""
from fluentqt import FontRole

from openlp.core.common.i18n import translate
from openlp.core.widgets import fluent as QtWidgets


class LibraryFooter(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.count_label = QtWidgets.QLabel(self)
        self.count_label.setFluentTypography(FontRole.Caption)
        layout.addWidget(self.count_label, 1)
        self.set_count(0)

    def set_count(self, count):
        text = (translate('OpenLP.LibraryView', '1 item') if count == 1
                else translate('OpenLP.LibraryView', '{count} items').format(count=count))
        self.count_label.setText(text)
