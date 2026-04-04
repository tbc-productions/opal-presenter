# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
The :mod:`~openlp.core.ui.dark` module looks for and loads a dark theme
"""
from subprocess import Popen, PIPE
from enum import Enum
from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.platform import is_macosx, is_win
from openlp.core.common.registry import Registry

try:
    import qdarkstyle
    HAS_DARK_THEME = True
except ImportError:
    HAS_DARK_THEME = False

WIN_REPAIR_STYLESHEET = """
QMainWindow::separator
{
  border: none;
}

QDockWidget::title
{
  border: 1px solid palette(dark);
  padding-left: 5px;
  padding-top: 2px;
  margin: 1px 0;
}

QToolBar
{
  border: none;
  margin: 0;
  padding: 0;
}
"""

MEDIA_MANAGER_DARK_STYLE = """
QWidget#media_tool_box QTabBar,
QTabWidget#media_tool_box QTabBar {
    border: 0;
}

QWidget#media_tool_box QTabBar::tab,
QTabWidget#media_tool_box QTabBar::tab,
QToolBox#media_tool_box::tab {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 palette(button), stop: 1.0 palette(mid));
    border: 0;
    border-radius: 0;
    margin-top: 0;
    margin-bottom: 0;
    min-height: 24px;
    padding: 4px 10px;
    text-align: left;
}

QWidget#media_tool_box QTabBar::tab:!selected,
QTabWidget#media_tool_box QTabBar::tab:!selected,
QToolBox#media_tool_box::tab:!selected {
    color: palette(button-text);
}

QWidget#media_tool_box QTabBar::tab:first,
QTabWidget#media_tool_box QTabBar::tab:first,
QToolBox#media_tool_box::tab:first {
    min-width: 0px;
    max-width: 0px;
    width: 0px;
    padding: 0px;
    margin: 0px;
    border: 0px;
}
/* This is here to make the tabs on KDE with the Breeze theme work */
QWidget#media_tool_box QTabBar::tab:selected,
QTabWidget#media_tool_box QTabBar::tab:selected,
QToolBox#media_tool_box::tab:selected {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 palette(light), stop: 1.0 palette(button));
    color: palette(window-text);
}
"""

MEDIA_MANAGER_LIGHT_STYLE = """
QWidget#media_tool_box QTabBar,
QTabWidget#media_tool_box QTabBar {
    border: 0;
}

QWidget#media_tool_box QTabBar::tab,
QTabWidget#media_tool_box QTabBar::tab,
QToolBox#media_tool_box::tab {
    background: palette(button);
    border: 1px solid palette(dark);
    border-radius: 0;
    margin-top: 0;
    margin-bottom: 0;
    min-height: 22px;
    padding: 2px 8px;
    text-align: left;
}

QWidget#media_tool_box QTabBar::tab:selected,
QTabWidget#media_tool_box QTabBar::tab:selected,
QToolBox#media_tool_box::tab:selected {
    background: palette(base);
    border-color: palette(highlight);
    color: palette(window-text);
}

QWidget#media_tool_box QTabBar::tab:first,
QTabWidget#media_tool_box QTabBar::tab:first,
QToolBox#media_tool_box::tab:first {
    min-width: 0px;
    max-width: 0px;
    width: 0px;
    padding: 0px;
    margin: 0px;
    border: 0px;
}
"""

DOCK_PANEL_HEADER_STYLE = """
QDockWidget::title {
    padding: 8px 12px;
    min-height: 30px;
    font-weight: 600;
}
"""

FORM_CONTROL_STYLE_REPAIR = """
QCheckBox {
    spacing: 8px;
}

QRadioButton {
    spacing: 8px;
}
"""

BUTTON_HOVER_STYLE_REPAIR = """
QPushButton:enabled,
QToolButton:enabled {
    qproperty-cursor: PointingHandCursor;
}

QPushButton:hover,
QToolButton:hover {
    border-color: palette(highlight);
}
"""


def get_dock_panel_header_stylesheet():
    """
    Return stylesheet used to make dock panel headers easier to read.
    """
    return DOCK_PANEL_HEADER_STYLE

PROGRESSBAR_STYLE = """
QProgressBar{
    height: 10px;
}
"""


class UiThemes(Enum):
    """
    An enumeration for themes.
    """
    Automatic = 'automatic'
    DefaultLight = 'light:default'
    DefaultDark = 'dark:default'
    Native = 'native'
    QDarkStyle = 'dark:qdarkstyle'


class NativeInputPaddingFilter(QtCore.QObject):
    """
    Apply content padding to native QLineEdit controls without overriding native painting.
    """

    def __init__(self, parent=None, padding=4):
        super().__init__(parent)
        self.padding = max(0, int(padding))

    def _apply_padding(self, widget):
        if isinstance(widget, QtWidgets.QLineEdit):
            margins = widget.textMargins()
            widget.setTextMargins(max(margins.left(), self.padding),
                                  max(margins.top(), self.padding),
                                  max(margins.right(), self.padding),
                                  max(margins.bottom(), self.padding))
            return
        if isinstance(widget, QtWidgets.QAbstractSpinBox):
            line_edit = widget.findChild(QtWidgets.QLineEdit)
            if line_edit:
                self._apply_padding(line_edit)

    def eventFilter(self, watched, event):
        if isinstance(watched, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox)) and event.type() in (
                QtCore.QEvent.Type.Polish,
                QtCore.QEvent.Type.Show):
            self._apply_padding(watched)
        return super().eventFilter(watched, event)


def apply_native_input_padding(app, padding=4):
    """
    Add native-preserving text padding to QLineEdit widgets in the application.
    """
    app_key = id(app)
    existing_filter = _NATIVE_INPUT_PADDING_FILTERS.get(app_key)
    if existing_filter is not None:
        return
    event_filter = NativeInputPaddingFilter(app, padding=padding)
    app.installEventFilter(event_filter)
    _NATIVE_INPUT_PADDING_FILTERS[app_key] = event_filter
    for widget in app.allWidgets():
        event_filter._apply_padding(widget)


def get_macos_native_style_name():
    """
    Return the available macOS native Qt style name, or ``None`` if not available.
    """
    available = QtWidgets.QStyleFactory.keys()
    return next((s for s in available if s.lower() == 'macos' or s.lower() == 'macintosh'), None)


def get_native_system_font():
    """
    Return the platform's general UI font for native themed rendering.
    """
    try:
        return QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.GeneralFont)
    except Exception:
        return QtWidgets.QApplication.font()


def is_ui_theme_dark():
    ui_theme_name = Registry().get('settings').value('advanced/ui_theme_name')

    if ui_theme_name is None or ui_theme_name in (UiThemes.Automatic, UiThemes.Native):
        return is_system_darkmode()
    else:
        return ui_theme_name.value.startswith('dark:')


def is_ui_theme(ui_theme: UiThemes):
    ui_theme_name = Registry().get('settings').value('advanced/ui_theme_name')
    return ui_theme_name == ui_theme


def init_ui_theme_if_needed(ui_theme_name):
    return not isinstance(ui_theme_name, UiThemes)


def has_ui_theme(ui_theme: UiThemes):
    if ui_theme == UiThemes.QDarkStyle:
        return HAS_DARK_THEME
    return True


IS_SYSTEM_DARKMODE = None
_NATIVE_INPUT_PADDING_FILTERS = {}


def is_system_darkmode():
    global IS_SYSTEM_DARKMODE

    if IS_SYSTEM_DARKMODE is None:
        try:
            if is_win():
                IS_SYSTEM_DARKMODE = is_windows_darkmode()
            elif is_macosx():
                IS_SYSTEM_DARKMODE = is_macosx_darkmode()
            else:
                IS_SYSTEM_DARKMODE = False
        except Exception:
            IS_SYSTEM_DARKMODE = False

    return IS_SYSTEM_DARKMODE


def is_windows_darkmode():
    """
    Detects if Windows is using dark mode system theme.

    Source: https://github.com/olivierkes/manuskript/blob/731e017e9e0dd7e4062f1af419705c11b2825515/manuskript/main.py
    (GPL3)

    Changes:
        * Allowed palette to be set on any operating system;
        * Split Windows Dark Mode detection to another function.
    """
    theme_settings = QtCore.QSettings('HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes'
                                      '\\Personalize',
                                      QtCore.QSettings.Format.NativeFormat)
    return theme_settings.value('AppsUseLightTheme') == 0


def is_macosx_darkmode():
    """
    Detects if Mac OS X is using dark mode system theme.

    Source: https://stackoverflow.com/a/65357166 (CC BY-SA 4.0)

    Changes:
        * Using OpenLP formatting rules
        * Handling exceptions
    """
    try:
        command = 'defaults read -g AppleInterfaceStyle'
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        stdin = process.communicate()[0]
        return bool(stdin)
    except Exception:
        return False


def set_default_theme(app):
    """
    Setup theme
    """
    if is_ui_theme(UiThemes.Native):
        if is_macosx():
            native = get_macos_native_style_name()
            if native:
                app.setStyle(native)
        app.setFont(get_native_system_font())
        # Ensure any previously-customized palette is reset when using the native theme.
        app.setPalette(app.style().standardPalette())
        return
    if is_ui_theme(UiThemes.DefaultDark) or (is_ui_theme(UiThemes.Automatic) and is_ui_theme_dark()):
        set_default_darkmode(app)
    elif is_ui_theme(UiThemes.DefaultLight) or is_ui_theme(UiThemes.Automatic):
        set_default_lightmode(app)


def set_default_lightmode(app):
    """
    Setup lightmode on the application if Default Light theme is enabled in the OpenLP Settings.
    """
    app.setStyle('Fusion')
    light_palette = QtGui.QPalette()
    disabled_color = QtGui.QColor(127, 127, 127)
    light_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(245, 245, 245))
    light_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtCore.Qt.GlobalColor.black)
    light_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, disabled_color)
    light_palette.setColor(QtGui.QPalette.ColorRole.Base, QtCore.Qt.GlobalColor.white)
    light_palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(245, 245, 245))
    light_palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtCore.Qt.GlobalColor.white)
    light_palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtCore.Qt.GlobalColor.black)
    light_palette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.black)
    light_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, disabled_color)
    light_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(245, 245, 245))
    light_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtCore.Qt.GlobalColor.black)
    light_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, disabled_color)
    light_palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtCore.Qt.GlobalColor.red)
    light_palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(42, 130, 218))
    light_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(42, 130, 218))
    light_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtCore.Qt.GlobalColor.white)
    light_palette.setColor(QtGui.QPalette.ColorGroup.Disabled,
                           QtGui.QPalette.ColorRole.HighlightedText,
                           disabled_color)
    app.setPalette(light_palette)


def set_default_darkmode(app):
    """
    Setup darkmode on the application if enabled in the OpenLP Settings or using a dark mode system theme.

    Source:
    https://github.com/olivierkes/manuskript/blob/731e017e9e0dd7e4062f1af419705c11b2825515/manuskript/main.py
    (GPL3)

    Changes:
        * Allowed palette to be set on any operating system;
        * Split Windows Dark Mode detection to another function.
    """
    app.setStyle('Fusion')
    dark_palette = QtGui.QPalette()
    dark_color = QtGui.QColor(45, 45, 45)
    disabled_color = QtGui.QColor(127, 127, 127)
    dark_palette.setColor(QtGui.QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtCore.Qt.GlobalColor.white)
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, disabled_color)
    dark_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(18, 18, 18))
    dark_palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, dark_color)
    dark_palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtCore.Qt.GlobalColor.white)
    dark_palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtCore.Qt.GlobalColor.black)
    dark_palette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.white)
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, disabled_color)
    dark_palette.setColor(QtGui.QPalette.ColorRole.Button, dark_color)
    dark_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtCore.Qt.GlobalColor.white)
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, disabled_color)
    dark_palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtCore.Qt.GlobalColor.red)
    dark_palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtCore.Qt.GlobalColor.black)
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.HighlightedText, disabled_color)
    # Fixes ugly (not to mention hard to read) disabled menu items.
    # Source: https://bugreports.qt.io/browse/QTBUG-10322?focusedCommentId=371060#comment-371060
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled,
                          QtGui.QPalette.ColorRole.Light,
                          QtCore.Qt.GlobalColor.transparent)
    # Fixes ugly media manager headers.
    dark_palette.setColor(QtGui.QPalette.ColorRole.Mid, QtGui.QColor(64, 64, 64))
    app.setPalette(dark_palette)


def get_alternate_rows_repair_stylesheet(base_color_name):
    return 'QTableWidget, QListWidget, QTreeWidget {alternate-background-color: ' + base_color_name + ';}\n'


def use_alternate_rows():
    registry = Registry()
    service_list = getattr(registry, 'service_list', None)
    if not service_list:
        return False
    settings = registry.get('settings')
    return False if settings is None else bool(settings.value('advanced/alternate rows'))


def get_application_stylesheet():
    """
    Return the correct application stylesheet based on the current style and operating system

    :return str: The correct stylesheet as a string
    """
    stylesheet = ''
    ui_theme_name = Registry().get('settings').value('advanced/ui_theme_name')
    use_alternate_rows_enabled = use_alternate_rows()
    is_qdarkstyle = ui_theme_name == UiThemes.QDarkStyle
    is_system_theme = ui_theme_name == UiThemes.Automatic
    if is_system_theme:
        return FORM_CONTROL_STYLE_REPAIR
    if is_macosx() and not is_qdarkstyle:
        # Keep macOS rendering close to native while applying minimal control/hover repairs.
        stylesheet += FORM_CONTROL_STYLE_REPAIR
        stylesheet += BUTTON_HOVER_STYLE_REPAIR
        stylesheet += 'QWidget#slide_controller_toolbar QToolButton::checked {' \
            '  background-color: palette(highlight);' \
            '  color: palette(highlighted-text);' \
            '}'
        return stylesheet
    if is_qdarkstyle:
        stylesheet = qdarkstyle.load_stylesheet_pyqt()
    else:
        stylesheet += FORM_CONTROL_STYLE_REPAIR
        stylesheet += BUTTON_HOVER_STYLE_REPAIR
        if not use_alternate_rows_enabled:
            base_color = QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorGroup.Active,
                                                                QtGui.QPalette.ColorRole.Base)
            alternate_rows_repair_stylesheet = get_alternate_rows_repair_stylesheet(base_color.name())
            stylesheet += alternate_rows_repair_stylesheet
        if is_win():
            stylesheet += WIN_REPAIR_STYLESHEET
    if not is_win():
        stylesheet += DOCK_PANEL_HEADER_STYLE
    stylesheet += 'QWidget#slide_controller_toolbar QToolButton::checked {' \
        '  background-color: palette(highlight);' \
        '  color: palette(highlighted-text);' \
        '}'
    return stylesheet


def get_library_stylesheet():
    """
    Return the correct stylesheet for the main window

    :return str: The correct stylesheet as a string
    """
    if is_ui_theme(UiThemes.Automatic) or is_ui_theme(UiThemes.QDarkStyle):
        return ''
    if is_ui_theme(UiThemes.DefaultDark) or is_ui_theme_dark():
        return MEDIA_MANAGER_DARK_STYLE
    return MEDIA_MANAGER_LIGHT_STYLE
