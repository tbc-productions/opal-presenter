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
# This script automates the generation of resources.py for Opal Presenter saving a
# backup of the old resources, inserting the coding and copyright header and
# conforming it to the project coding standards.
#
# To make use of the script:
# 1 - Add the new image files in resources/images/
# 2 - Modify resources/images/openlp-2.qrc as appropriate
# 3 - run sh scripts/generate_resources.sh
#
# Once you have confirmed the resources are correctly modified to an updated,
# working state you may optionally remove opal/core/resources.py.old
#
###############################################################################

# Dependencies
#
# Depending on your platform, you will need to install the following for the "rcc" command:
#
# Debian: qt6-base-dev-tools
# Fedora: pyside6-tools

# Resolve paths relative to this script so it works from any cwd.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

# Find the "rcc" binary
COMMANDS=""
if [ -n "$VIRTUAL_ENV" ]; then
    COMMANDS="$COMMANDS $VIRTUAL_ENV/bin/pyside6-rcc"
fi
COMMANDS="$COMMANDS $PROJECT_ROOT/.venv/bin/pyside6-rcc pyside6-rcc rcc /usr/lib/qt6/libexec/rcc /usr/lib/qt6/rcc"
RCC_CMD=""
for RCC_CMD in $COMMANDS; do
    echo $RCC_CMD
    if command -v $RCC_CMD 2>&1 >/dev/null; then
        if [ "$RCC_CMD" = "rcc" ]; then
            RCC_VERSION=`rcc -v | cut -d' ' -f2 | cut -d. -f1`
            if [ "$RCC_VERSION" = "6" ]; then
                break
            fi
        else
            break
        fi
    fi
    RCC_CMD=""
done

if [ "$RCC_CMD" = "" ]; then
    echo "ERROR: rcc binary not found"
    exit 1
fi

# Backup the existing resources
if [ -f "$PROJECT_ROOT/opal/core/resources.py" ]; then
    echo "Backup old resources file"
    mv "$PROJECT_ROOT/opal/core/resources.py" "$PROJECT_ROOT/opal/core/resources.py.old"
fi

# Create the new data from the updated qrc
echo "Generate new resources file"
if ! $RCC_CMD -g python -o "$PROJECT_ROOT/opal/core/resources.py.new" "$PROJECT_ROOT/resources/images/openlp-2.qrc"; then
    echo "ERROR: Failed to generate resources from openlp-2.qrc"
    if [ -f "$PROJECT_ROOT/opal/core/resources.py.old" ]; then
        mv "$PROJECT_ROOT/opal/core/resources.py.old" "$PROJECT_ROOT/opal/core/resources.py"
    fi
    exit 1
fi

# Remove patch breaking lines
echo "Remove comments at top of file"
if [ ! -f "$PROJECT_ROOT/opal/core/resources.py.new" ]; then
    echo "ERROR: Generated resources file not found"
    if [ -f "$PROJECT_ROOT/opal/core/resources.py.old" ]; then
        mv "$PROJECT_ROOT/opal/core/resources.py.old" "$PROJECT_ROOT/opal/core/resources.py"
    fi
    exit 1
fi
cat "$PROJECT_ROOT/opal/core/resources.py.new" | sed '1,5d' > "$PROJECT_ROOT/opal/core/resources.py"

# Patch resources.py to Opal Presenter coding style
ARCH=`uname -m`
echo "Architecture is: $ARCH"
PATCH_STATUS=0
if [ "$ARCH" = "arm64" ]; then
    echo "Running ARM64 patch"
    patch --posix -s "$PROJECT_ROOT/opal/core/resources.py" "$SCRIPT_DIR/resources.arm64.patch" >/dev/null 2>&1 || PATCH_STATUS=$?
else
    echo "Running x86 patch"
    patch --posix -s "$PROJECT_ROOT/opal/core/resources.py" "$SCRIPT_DIR/resources.patch" >/dev/null 2>&1 || PATCH_STATUS=$?
fi

if [ "$PATCH_STATUS" -ne 0 ]; then
    echo "Patch did not apply cleanly (exit code: $PATCH_STATUS). Applying fallback normalisation."
    # Keep behaviour consistent even if legacy patch hunks drift.
    sed '/^qInitResources()$/d' "$PROJECT_ROOT/opal/core/resources.py" > "$PROJECT_ROOT/opal/core/resources.py.tmp"
    mv "$PROJECT_ROOT/opal/core/resources.py.tmp" "$PROJECT_ROOT/opal/core/resources.py"
    PATCH_STATUS=0
fi

if [ "$PATCH_STATUS" -eq 0 ]; then
    # Ensure import-time registration does not happen twice.
    sed '/^qInitResources()$/d' "$PROJECT_ROOT/opal/core/resources.py" > "$PROJECT_ROOT/opal/core/resources.py.tmp"
    mv "$PROJECT_ROOT/opal/core/resources.py.tmp" "$PROJECT_ROOT/opal/core/resources.py"
fi

# Remove temporary file
rm -f "$PROJECT_ROOT/opal/core/resources.py.new" 2>/dev/null
rm -f "$PROJECT_ROOT/opal/core/resources.py.old" 2>/dev/null
rm -f "$PROJECT_ROOT/opal/core/resources.py.orig" 2>/dev/null
rm -f "$PROJECT_ROOT/opal/core/resources.py.rej" 2>/dev/null
