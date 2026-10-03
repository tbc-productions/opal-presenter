"""Shared native Fluent command button defaults."""
import fluentqt


class FluentPushButton(fluentqt.Button):
    """Fluent command preserving Qt's automatic icon-and-text presentation."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)


QPushButton = FluentPushButton
