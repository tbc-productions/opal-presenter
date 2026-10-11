"""Only the JPEG XR encoder is needed for editable PowerPoint picture effects."""
from PyInstaller.utils.hooks import collect_dynamic_libs

hiddenimports = ['imagecodecs._jpegxr']
binaries = collect_dynamic_libs('imagecodecs')
