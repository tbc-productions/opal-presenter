"""Shared native Fluent command button defaults."""
import fluentqt
from PySide6 import QtGui
from openlp.core.widgets.fluent_text import MnemonicButtonMixin


def set_fluent_button_icon(button, icon):
    """Let Fluent paint its own glyphs in the same colour as the button text."""
    name = icon.name() if isinstance(icon, QtGui.QIcon) else ''
    if name.startswith('ic_fluent_'):
        from openlp.core.ui.fluenticons import _icon_font
        family, glyphs = _icon_font()
        glyph = chr(glyphs[name])
        size = min(button.iconSize().width(), button.iconSize().height())
        if button.iconGlyph() != glyph or button.iconPixelSize() != size or button.iconFontFamily() != family \
                or not fluentqt.Button.icon(button).isNull():
            fluentqt.Button.setIcon(button, QtGui.QIcon())
            button.setIconGlyph(glyph, size, family)
    else:
        if button.iconGlyph():
            button.setIconGlyph('')
        if fluentqt.Button.icon(button).cacheKey() != icon.cacheKey():
            fluentqt.Button.setIcon(button, icon)


class FluentButtonIconMixin:
    """Retain QIcon access while native Fluent owns glyph colours and states."""
    def setIcon(self, icon):
        self._source_icon = QtGui.QIcon(icon)
        set_fluent_button_icon(self, self._source_icon)

    def icon(self):
        return self._source_icon if hasattr(self, '_source_icon') else super().icon()

    def setIconSize(self, size):
        super().setIconSize(size)
        if self.icon().name().startswith('ic_fluent_'):
            set_fluent_button_icon(self, self.icon())


class FluentPushButton(FluentButtonIconMixin, MnemonicButtonMixin, fluentqt.Button):
    """Fluent command preserving Qt's automatic icon-and-text presentation."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(self.text())
        self.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore)


QPushButton = FluentPushButton


class FluentCheckBox(MnemonicButtonMixin, fluentqt.CheckBox):
    """Decode Qt labels while preserving checkbox shortcuts."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(self.text())


class FluentRadioButton(MnemonicButtonMixin, fluentqt.RadioButton):
    """Decode Qt labels while preserving radio-button shortcuts."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(self.text())


QCheckBox = FluentCheckBox
QRadioButton = FluentRadioButton
