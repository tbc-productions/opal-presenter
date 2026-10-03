"""Collect FluentQt's Python namespaces and native binding for frozen builds."""
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# Spatial is an optional Qt3D/OpenGL extension and is not used by OpenLP.
hiddenimports = collect_submodules('fluentqt', filter=lambda name: name != 'fluentqt.spatial')
datas = collect_data_files('fluentqt')
binaries = collect_dynamic_libs('fluentqt')
