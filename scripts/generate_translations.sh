#!/bin/sh
# vim: autoindent shiftwidth=4 expandtab textwidth=120 tabstop=4 softtabstop=4

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008-2024 OpenLP Developers                              #
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
#
# This script generates qm files from ts files.  These are not for comitting
# but for testing only.
#
###############################################################################
pwd=`pwd`
result=${PWD##*/}; echo $result

if [ $result != 'scripts' ] ; then
	echo 'This script must be run from the scripts directory'
	exit
fi

cd ../resources/i18n

LCONVERT_CMD=''
LRELEASE_CMD=''
if command -v lconvert-qt5 >/dev/null 2>&1; then
	LCONVERT_CMD='lconvert-qt5'
elif command -v lconvert >/dev/null 2>&1; then
	LCONVERT_CMD='lconvert'
fi
if command -v lrelease-qt5 >/dev/null 2>&1; then
	LRELEASE_CMD='lrelease-qt5'
elif command -v lrelease >/dev/null 2>&1; then
	LRELEASE_CMD='lrelease'
fi

if [ -z "$LCONVERT_CMD" ] && [ -z "$LRELEASE_CMD" ]; then
	echo 'No Qt translation tool found (lconvert/lrelease).'
	echo 'Install Qt tools and ensure they are on PATH, for example:'
	echo '  brew install qt'
	echo '  export PATH="/opt/homebrew/opt/qt/bin:$PATH"'
	exit 127
fi

rm -f *.qm

for file in *.ts;
 do
  echo $file
  qm_file=${file%%ts}qm
  if [ -n "$LCONVERT_CMD" ]; then
	"$LCONVERT_CMD" -i "$file" -o "$qm_file" || exit 1
  else
	"$LRELEASE_CMD" "$file" -qm "$qm_file" || exit 1
  fi
 done
