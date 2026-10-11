"""Bundle the ADS native library alongside its Python bindings."""
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

binaries = collect_dynamic_libs('PySide6QtAds')
datas = collect_data_files('PySide6QtAds', includes=['license/**'])
