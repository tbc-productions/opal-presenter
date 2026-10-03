#!/usr/bin/env python3
"""Build OpenLP+'s pinned FluentQt wheel for Python 3.14 and Qt 6.11.1.

Requires a matching Qt C++ SDK, cmake, ninja and shiboken6_generator. The
result is a local distribution; it is not an upstream supported wheel.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

SOURCE_URL = 'https://github.com/calvinhxx/Fluent-Qt.git'
SOURCE_REVISION = '4da001f20d0e1bee4a0a1d0519535e9ff0e5eb42'
VERSION = '1.9.2+openlp.1'
QT_VERSION = '6.11.1'


def run(*args, env=None):
    subprocess.run([str(arg) for arg in args], check=True, env=env)


def replace(path, old, new):
    text = path.read_text()
    if old not in text:
        if new in text:
            return
        raise RuntimeError(f'Pinned source changed: expected text is missing in {path}')
    path.write_text(text.replace(old, new))


def relocate_macos(extension):
    """Use PySide's frameworks; never ship absolute SDK framework references."""
    dependencies = subprocess.check_output(['otool', '-L', str(extension)], text=True)
    for line in dependencies.splitlines()[1:]:
        dependency = line.strip().split(' (')[0]
        if '.framework/' in dependency and '/Qt' in dependency and not dependency.startswith('@rpath/'):
            framework = dependency[dependency.index('/Qt') + 1:]
            run('install_name_tool', '-change', dependency, '@rpath/' + framework, extension)
    run('codesign', '--force', '--sign', '-', extension)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qt-prefix', required=True, type=Path)
    parser.add_argument('--source', type=Path, help='Reuse a checkout of the pinned source revision')
    parser.add_argument('--python', default=sys.executable, help='Python 3.14 with matching build dependencies')
    parser.add_argument('--work-dir', type=Path, default=Path('.cache/fluentqt'))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--install', action='store_true', help='Install the tested wheel into the calling interpreter')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error('OpenLP+ must remain on Python 3.14')
    workspace = args.work_dir.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    source = args.source.resolve() if args.source else workspace / 'source'
    if not source.exists():
        run('git', 'clone', SOURCE_URL, source)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != SOURCE_REVISION:
        if args.source:
            raise RuntimeError('The provided source is not the pinned FluentQt revision')
        run('git', '-C', source, 'checkout', '--detach', SOURCE_REVISION)
    bindings = source / 'bindings/pyside6'
    # Widen the source guard only for our tested build. Keep the resulting
    # wheel restricted to 3.14 and identify it with an OpenLP local version.
    replace(bindings / 'CMakeLists.txt', '>=3.11,<3.14', '>=3.11,<3.15')
    replace(bindings / 'CMakeLists.txt', 'VERSION_LESS 3.14', 'VERSION_LESS 3.15')
    replace(bindings / 'tools/build_wheel.py', '    ">=3.11,<3.14",', '    ">=3.11,<3.14",\n    ">=3.14,<3.15",')
    build = workspace / 'build'
    python = Path(args.python).absolute()
    run(python, '-c',
        'import sys, PySide6, shiboken6; '
        'assert sys.version_info[:2] == (3, 14), "Python 3.14 is required"; '
        f'assert PySide6.__version__ == shiboken6.__version__ == "{QT_VERSION}", '
        '"Build dependencies must match Qt 6.11.1"')
    # The package-installed tools are adjacent to the build interpreter.
    cmake = python.parent / ('cmake.exe' if os.name == 'nt' else 'cmake')
    ninja = python.parent / ('ninja.exe' if os.name == 'nt' else 'ninja')
    options = [f'-DCMAKE_PREFIX_PATH={args.qt_prefix.resolve()}', f'-DPython_EXECUTABLE={python}',
               f'-DCMAKE_MAKE_PROGRAM={ninja}', '-DCMAKE_BUILD_TYPE=Release',
               '-DFLUENT_QT_BUILD_PYSIDE6_BINDINGS=ON', '-DFLUENT_QT_BUILD_EXAMPLES=OFF',
               '-DFLUENT_QT_INSTALL=OFF', '-DBUILD_TESTING=ON', '-DCMAKE_AUTORCC_OPTIONS=--compress-algo;zlib']
    if sys.platform == 'darwin':
        options.append('-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0')
    run(cmake, '-S', source, '-B', build, '-G', 'Ninja', *options)
    run(cmake, '--build', build, '--target', '_fluentqt', '--parallel', args.jobs)
    if sys.platform == 'darwin':
        relocate_macos(build / 'python/fluentqt/_fluentqt.so')
    run(cmake, '--build', build, '--target', 'fluentqt_pyside6_stubs', '--parallel', args.jobs)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONPATH=str(build / 'python'),
               FLUENTQT_EXPECTED_VERSION='1.9.2')
    run(python, bindings / 'tests/test_bindings.py', env=env)
    output = workspace / 'wheelhouse'
    run(python, bindings / 'tools/build_wheel.py', '--package-dir', build / 'python/fluentqt',
        '--output-dir', output, '--version', VERSION, '--pyside-version', QT_VERSION,
        '--shiboken-version', QT_VERSION, '--requires-python', '>=3.14,<3.15',
        '--description-file', bindings / 'PYPI.md', '--license-file', source / 'LICENSE',
        '--license-file', source / 'THIRD_PARTY_NOTICES.md', '--license-file', source / 'TRADEMARKS.md')
    wheel = next(output.glob(f'fluentqt-{VERSION}-*.whl'))
    if args.install:
        run(sys.executable, '-m', 'pip', 'install', wheel)
    print(f'Validated Python 3.14 FluentQt wheel: {wheel}')


if __name__ == '__main__':
    main()
