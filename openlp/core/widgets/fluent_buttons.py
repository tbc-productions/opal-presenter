"""Shared native Fluent command button defaults."""
import fluentqt
from openlp.core.widgets.fluent_text import MnemonicButtonMixin


class FluentPushButton(MnemonicButtonMixin, fluentqt.Button):
    """Fluent command preserving Qt's automatic icon-and-text presentation."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(self.text())
        self.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)


QPushButton = FluentPushButton
