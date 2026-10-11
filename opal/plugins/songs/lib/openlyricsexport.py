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
The :mod:`openlyricsexport` module provides the functionality for exporting songs from the database to the OpenLyrics
format.
"""
import logging
from pathlib import Path

from lxml import etree

from opal.core.common import clean_filename
from opal.core.common.i18n import translate
from opal.core.common.mixins import RegistryProperties
from opal.core.common.path import create_paths
from opal.plugins.songs.lib.openlyricsxml import OpenLyrics


log = logging.getLogger(__name__)


class OpenLyricsExport(RegistryProperties):
    """
    This provides the Openlyrics export.
    """
    def __init__(self, parent, songs, save_path):
        """
        Initialise the export.

        :param pathlib.Path save_path: The directory to save the exported songs in
        :rtype: None
        """
        log.debug('initialise OpenLyricsExport')
        self.parent = parent
        self.manager = parent.plugin.manager
        self.songs = songs
        self.save_path = Path(save_path)
        create_paths(self.save_path)

    def do_export(self):
        """
        Export the songs.
        """
        log.debug('started OpenLyricsExport')
        open_lyrics = OpenLyrics(self.manager)
        self.parent.progress_bar.setMaximum(len(self.songs))
        for song in self.songs:
            self.application.process_events()
            if self.parent.stop_export_flag:
                return False
            self.parent.increment_progress_bar(
                translate('SongsPlugin.OpenLyricsExport', 'Exporting "{title}"...').format(title=song.title))
            xml = open_lyrics.song_to_xml(song)
            from opal.core.lib.designmedia import media_references
            from opal.core.lib.itemexport import write_xml_package, xml_design
            suffix = '.xml' if getattr(self.parent, 'plain_openlyrics', False) else '.opal-song'
            tree = etree.ElementTree(etree.fromstring(xml.encode()))
            filename = '{title} ({author})'.format(title=song.title,
                                                   author=', '.join([author.display_name for author in
                                                                     sorted(song.authors,
                                                                            key=lambda a: a.display_name)]))
            filename = clean_filename(filename)
            # Ensure the filename isn't too long for some filesystems
            path_length = len(str(self.save_path))
            filename_with_ext = '{name}{suffix}'.format(name=filename[0:250 - path_length], suffix=suffix)
            # Make sure we're not overwriting an existing file
            conflicts = 0
            while (self.save_path / filename_with_ext).exists():
                conflicts += 1
                filename_with_ext = '{name}-{extra}{suffix}'.format(name=filename[0:247 - path_length],
                                                                    extra=conflicts, suffix=suffix)
            # Pass a file object, because lxml does not cope with some special
            # characters in the path (see lp:757673 and lp:744337).
            output = etree.tostring(tree, encoding='utf-8', xml_declaration=True, pretty_print=True)
            service_item = None
            if suffix == '.opal-song':
                from PySide6 import QtCore
                from opal.core.widgets import fluent as QtWidgets
                library_item = QtWidgets.QListWidgetItem()
                library_item.setData(QtCore.Qt.ItemDataRole.UserRole, song.id)
                service_item = self.parent.plugin.media_item.build_service_item(item=library_item)
            write_xml_package(self.save_path / filename_with_ext, output, service_item)
        return True
