# Windows Qt runtime packaging

Frozen Windows builds require PySide6's Python extension modules, the matching
Qt6 DLLs and the Windows platform plugin. Missing Qt runtime files can cause
`from PySide6 import QtCore` to fail before application logging starts.
The media player uses the location of the loaded `QtCore` extension module
for the Windows DLL search path, which works in both a Python environment and
the frozen application.

## PyInstaller integration

- **Hook registration:** Opal registers a PyInstaller hook through the `pyinstaller40`
  entry point. Install this source checkout in the build environment before running
  PyInstaller; the packaging repository already does this.
- **Other hooks:** `opal.core` coexists with the packaging repository's `opal` plugin
  hook and standard PySide6 hooks.
- **Windows runtime:** explicitly includes the wheel's DLLs with their relative paths
  and the WebEngine helper.
- **Validation:** rejects an incomplete or unloadable Qt installation instead of
  shipping an unusable executable.
- **DLL source:** use only DLLs from the matching PySide6 wheel, not another Qt installation.

## Windows smoke test

Run these commands from the repository root in a disposable PowerShell session.
Build and install the pinned wheel using the [FluentQt build guide](fluentqt.md)
before installing the source checkout:

```powershell
python -m pip install pyinstaller "PySide6==6.11.1"
# Build and install the pinned FluentQt wheel first (see fluentqt.md).
python -m pip install -e .
python -m unittest discover -s tests/packaging -v
$python = (Get-Command python).Source
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
& $python -m PyInstaller --clean --noconfirm --noupx --name qt-smoke tests/packaging/qt_smoke.py
& .\dist\qt-smoke\qt-smoke.exe
```

### What the probe checks

- **DLL isolation:** a minimal PATH prevents unrelated developer tools' DLLs from
  being collected at build time.
- **Startup imports:** the probe loads Opal's startup imports, including the media
  player, plus QtCore, GUI, multimedia and WebEngine bindings.
- **Platform plugin:** creates a QApplication using the Windows platform plugin.
- **Bundled files:** checks required runtime files.

A successful probe does not replace testing the final MSI and portable application
on a clean Windows machine.

## Continuous integration

The Gitea Windows packaging test runs this probe with Python 3.14, matching the
release builder. Application unit tests alone cannot detect omitted DLLs in a
frozen executable.
