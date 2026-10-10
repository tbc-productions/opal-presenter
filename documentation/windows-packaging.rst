Windows Qt runtime packaging
============================

Opal Presenter 4.0.1 was found installed with PySide6's Python extension modules but
without the Qt6 DLLs and Windows platform plugin. This fails at the first
``from PySide6 import QtCore`` import, before application logging starts.
Opal Presenter 4.0.2 included the Qt DLLs but failed when the media player tried to
add a nonexistent ``_internal/Lib/site-packages/PySide6`` directory to the
Windows DLL search path. The media player now uses the location of the loaded
``QtCore`` extension module, which works in both a Python environment and the
frozen application.

OpenLP registers a PyInstaller hook through the ``pyinstaller40`` entry point.
Install this source checkout in the build environment before running PyInstaller
(the packaging repository already does this). The ``openlp.core`` hook coexists
with the packaging repository's ``openlp`` plugin hook and the standard PySide6
hooks. On Windows it explicitly includes the wheel's DLLs, preserving their
relative paths, and the WebEngine helper. It rejects an incomplete or unloadable
Qt installation instead of shipping an unusable executable. Only use DLLs from
the matching PySide6 wheel, not from another Qt installation.

Windows smoke test, from the repository root::

    python -m pip install pyinstaller "PySide6==6.11.1"
    # Build and install the pinned FluentQt wheel first (see fluentqt.rst).
    python -m pip install -e .
    python -m unittest discover -s tests/packaging -v
    $python = (Get-Command python).Source
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    & $python -m PyInstaller --clean --noconfirm --noupx --name qt-smoke tests/packaging/qt_smoke.py
    & .\dist\qt-smoke\qt-smoke.exe

Run these commands in a disposable PowerShell session. A minimal PATH also
prevents unrelated developer tools' DLLs from being collected at build time.
The probe loads the OpenLP startup imports, including the media player, plus
QtCore, GUI, multimedia and WebEngine bindings. It creates a QApplication using
the Windows platform plugin and checks required bundled files. A successful
probe does not replace testing the final MSI and portable application on a
clean Windows machine.

The Gitea Windows packaging test runs this probe with Python 3.14, matching the
release builder. Application unit tests alone cannot detect omitted DLLs in a
frozen executable.
