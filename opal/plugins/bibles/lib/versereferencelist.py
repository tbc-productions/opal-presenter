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

from opal.plugins.bibles.lib import get_reference_separator


class VerseReferenceList(object):
    """
    The VerseReferenceList class encapsulates a list of verse references, but maintains the order in which they were
    added.
    """

    def __init__(self):
        self.verse_list = []
        self.version_list = []
        self.current_index = -1

    def add(self, book, chapter, verse, version, copyright, permission):
        self.add_version(version, copyright, permission)
        if not self.verse_list or self.verse_list[self.current_index]['book'] != book:
            self.verse_list.append({'version': version, 'book': book, 'chapter': chapter, 'start': verse, 'end': verse})
            self.current_index += 1
        elif self.verse_list[self.current_index]['chapter'] != chapter:
            self.verse_list.append({'version': version, 'book': book, 'chapter': chapter, 'start': verse, 'end': verse})
            self.current_index += 1
        elif (self.verse_list[self.current_index]['end'] + 1) == verse:
            self.verse_list[self.current_index]['end'] = verse
        else:
            self.verse_list.append({'version': version, 'book': book, 'chapter': chapter, 'start': verse, 'end': verse})
            self.current_index += 1

    def add_version(self, version, copyright, permission):
        for bible_version in self.version_list:
            if bible_version['version'] == version:
                return
        self.version_list.append({'version': version, 'copyright': copyright, 'permission': permission})

    def format_verses(self, consolidate_chapters=False):
        """Format references, optionally joining consecutive chapters into one range."""
        verse_sep = get_reference_separator('sep_v_display')
        range_sep = get_reference_separator('sep_r_display')
        list_sep = get_reference_separator('sep_l_display')
        verse_list = []
        for verse in self.verse_list:
            previous = verse_list[-1] if verse_list else None
            if (consolidate_chapters and previous and previous['book'] == verse['book']
                    and previous['version'] == verse['version']
                    and int(previous['end_chapter']) + 1 == int(verse['chapter'])
                    and int(verse['start']) == 1):
                previous['end_chapter'] = verse['chapter']
                previous['end'] = verse['end']
            else:
                verse_list.append(dict(verse, end_chapter=verse['chapter']))
        result = ''
        for index, verse in enumerate(verse_list):
            previous = verse_list[index - 1] if index else None
            if previous:
                if previous['version'] != verse['version']:
                    result += ' ({version})'.format(version=previous['version'])
                result += '{sep} '.format(sep=list_sep)
            if not previous or previous['book'] != verse['book']:
                result += '{book} {chapter}{sep}'.format(
                    book=verse['book'], chapter=verse['chapter'], sep=verse_sep)
            elif previous['end_chapter'] != verse['chapter']:
                result += '{chapter}{sep}'.format(chapter=verse['chapter'], sep=verse_sep)
            result += str(verse['start'])
            if verse['chapter'] != verse['end_chapter']:
                result += '{range}{chapter}{sep}{end}'.format(
                    range=range_sep, chapter=verse['end_chapter'], sep=verse_sep, end=verse['end'])
            elif verse['start'] != verse['end']:
                result += '{sep}{end}'.format(sep=range_sep, end=verse['end'])
        if verse_list and len(self.version_list) > 1:
            result += ' ({version})'.format(version=verse['version'])
        return result

    def format_versions(self, copyright=True, permission=True):
        """
        Format a string with the bible versions used

        :param copyright: If the copyright info should be included, default is true.
        :param permission: If the permission info should be included, default is true.
        :return: A formatted string with the bible versions used
        """
        result = ''
        for index, version in enumerate(self.version_list):
            if index > 0:
                if result[-1] not in [';', ',', '.']:
                    result += ';'
                result += ' '
            result += version['version']
            if copyright and version['copyright'].strip():
                result += ', ' + version['copyright']
            if permission and version['permission'].strip():
                result += ', ' + version['permission']
        result = result.rstrip()
        if result.endswith(','):
            return result[:len(result) - 1]
        return result

    def format_copyrights(self):
        """
        Format a string with all copyrights from the used bible versions.

        :return: A semicolon separated string with copyrights.
        """
        return '; '.join([version['copyright'] for version in self.version_list if version['copyright'].strip()])

    def format_permissions(self):
        """
        Format a string with all permission strings from the used bible versions.

        :return: A semicolon separated string with permissions.
        """
        return '; '.join([version['permission'] for version in self.version_list if version['permission'].strip()])
