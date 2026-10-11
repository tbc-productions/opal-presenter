"""Translate Qt mnemonic labels for Fluent controls that paint literal text."""
import re

from PySide6 import QtGui


def display_text(text):
    """Remove shortcut markers and turn escaped ampersands into literal ones."""
    return re.sub(r'&(&?)', r'\1', text)


class MnemonicButtonMixin:
    """Keep Alt-key shortcuts while giving Fluent's painter readable labels."""
    def setText(self, text):
        super().setText(display_text(text))
        self.setShortcut(QtGui.QKeySequence.mnemonic(text))
