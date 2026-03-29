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

MEDIA_MANAGER_STYLE = """
QTabWidget#media_tool_box QTabBar::tab,
QToolBox#media_tool_box::tab {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 palette(button), stop: 1.0 palette(mid));
    border: 0;
    border-radius: 2px;
    margin-top: 0;
    margin-bottom: 0;
    text-align: left;
}
/* This is here to make the tabs on KDE with the Breeze theme work */
QTabWidget#media_tool_box QTabBar::tab:selected,
QToolBox#media_tool_box::tab:selected {}
"""

DOCK_PANEL_HEADER_STYLE = """
QDockWidget::title {
    padding: 8px 12px;
    min-height: 30px;
    font-weight: 600;
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
    elif is_ui_theme(UiThemes.DefaultLight):
        set_default_lightmode(app)


def set_default_lightmode(app):
    """
    Setup lightmode on the application if Default Light theme is enabled in the OpenLP Settings.
    """
    if is_macosx():
        native = get_macos_native_style_name()
        if native:
            app.setStyle(native)
    else:
        app.setStyle('Fusion')
    app.setPalette(app.style().standardPalette())


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
    if is_macosx():
        native = get_macos_native_style_name()
        if native:
            app.setStyle(native)
        # macOS native style handles dark mode through the system palette; skip the manual palette override.
        return
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


def get_application_stylesheet():
    """
    Return the correct application stylesheet based on the current style and operating system

    :return str: The correct stylesheet as a string
    """
    stylesheet = ''
    ui_theme_name = Registry().get('settings').value('advanced/ui_theme_name')
    use_alternate_rows = Registry().get('settings').value('advanced/alternate rows')
    is_qdarkstyle = ui_theme_name == UiThemes.QDarkStyle
    is_native_theme = ui_theme_name == UiThemes.Native
    if is_macosx() and not is_qdarkstyle:
        return stylesheet
    if is_native_theme:
        return stylesheet
    if is_qdarkstyle:
        stylesheet = qdarkstyle.load_stylesheet_pyqt()
    else:
        if not use_alternate_rows:
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
    if is_ui_theme(UiThemes.Native) or is_ui_theme(UiThemes.QDarkStyle):
        return ''
    return MEDIA_MANAGER_STYLE
