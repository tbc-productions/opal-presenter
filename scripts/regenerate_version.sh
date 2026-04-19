#!/bin/bash
# Script to regenerate the .version file
# This is useful when the version file gets out of sync with the current git state

set -e

echo "Regenerating OpenLP+ .version file..."

if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Are you in the OpenLP+ repository root?"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found at .venv"
    echo "Please create a virtual environment and install OpenLP+ first."
    exit 1
fi

echo "Running: pip install -e ."
.venv/bin/python -m pip install -e .

echo "Version file regenerated successfully."
echo "New version: $(cat openlp/.version)"