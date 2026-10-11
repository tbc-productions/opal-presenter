"""Bundled Library Sync plugin and its Cloud Library dock."""
from PySide6 import QtCore

from opal.core.common.i18n import translate
from opal.core.common.registry import Registry
from opal.core.lib.plugin import Plugin, StringContent
from opal.core.state import State
from opal.core.ui.advanceddocking import AdvancedDockWidget
from opal.core.ui.icons import UiIcons
from opal.core.ui.mainwindow import _set_dock_visible
from opal.plugins.librarysync.lib.panel import CloudLibrary


class LibrarySyncPlugin(Plugin):
    def __init__(self):
        super().__init__('librarysync')
        self.weight = 22
        self.icon = UiIcons().library_sync
        self.panel = None
        State().add_service('library_sync', self.weight, is_plugin=True)
        State().update_pre_conditions('library_sync', self.check_pre_conditions())

    def set_plugin_text_strings(self):
        name = translate('LibrarySync', 'Library Sync')
        self.text_strings[StringContent.Name] = {'singular': name, 'plural': name}

    def initialise(self):
        super().initialise()
        window = self.main_window
        if self.panel is None:
            self.panel = CloudLibrary(self, window)
            dock = AdvancedDockWidget(window, 'cloud_library_dock', self.icon)
            dock.setWindowTitle(translate('LibrarySync', 'Cloud Library'))
            dock.setWidget(self.panel)
            window.cloud_library_dock = dock
            window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.panel.closing = False
        window.layout_preset_navigation.buttons[3].show()
        window.mode_library_sync_item.setVisible(True)
        _set_dock_visible(window.cloud_library_dock, self.settings.value('core/view mode') == 'librarysync')
        window.set_lock_panel(self.settings.value('user interface/lock panel'))
        Registry().register_function('librarysync_install_drop_targets', self.panel.install_drop_targets)
        self.panel.startup()

    def finalise(self):
        if self.panel:
            self.panel.shutdown()
            Registry().remove_function('librarysync_install_drop_targets', self.panel.install_drop_targets)
            if not self.is_active():
                _set_dock_visible(self.main_window.cloud_library_dock, False)
                self.main_window.layout_preset_navigation.buttons[3].hide()
                self.main_window.mode_library_sync_item.setVisible(False)
                if self.settings.value('core/view mode') == 'librarysync':
                    self.main_window._activate_layout_preset('default')
        super().finalise()

    @staticmethod
    def about():
        return translate('LibrarySync', 'Browse, preview and copy Library items between this computer and shared '
                         'cloud folders. Google Drive uses each person’s own account and folder permissions.')
