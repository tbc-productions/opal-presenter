#!/usr/bin/env python3
"""Reuse validated FluentQt wheels and Qt SDKs across Opal's CI repositories."""
import argparse
from contextlib import contextmanager
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import zipfile


@contextmanager
def cache_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'opal.lock').open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.write(b'\0')
            lock.flush()
            lock.seek(0)
            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    time.sleep(1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def wheel_key(build_script, qt_version):
    compiler = (os.environ['VCToolsVersion'] if os.name == 'nt' else
                subprocess.check_output(['clang' if sys.platform == 'darwin' else 'c++', '--version'], text=True))
    inputs = [sha256(build_script.read_bytes()).hexdigest(), sha256(Path(__file__).read_bytes()).hexdigest(),
              sys.platform, platform.machine(), platform.release(), sys.version,
              sysconfig.get_config_var('SOABI'), qt_version, compiler,
              os.environ.get('VSCMD_ARG_TGT_ARCH', ''), os.environ.get('MACOSX_DEPLOYMENT_TARGET', ''),
              os.environ.get('CC', ''), os.environ.get('CXX', ''),
              os.environ.get('CFLAGS', ''), os.environ.get('CXXFLAGS', ''), os.environ.get('LDFLAGS', '')]
    return sha256(json.dumps(inputs).encode()).hexdigest()


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def ensure_wheel(build_script, root):
    config = runpy.run_path(str(build_script))
    qt_version = config['QT_VERSION']
    key = wheel_key(build_script, qt_version)
    wheelhouse = root / 'wheels' / key
    with cache_lock(root):
        wheels = list(wheelhouse.glob('*.whl'))
        if wheels:
            try:
                with zipfile.ZipFile(wheels[0]) as archive:
                    valid = archive.testzip() is None
            except zipfile.BadZipFile:
                valid = False
            if valid:
                print(f'Reusing validated FluentQt wheel: {wheels[0]}', flush=True)
                return wheels[0]
            wheels[0].unlink()
        print(f'Building FluentQt wheel for shared cache: {wheelhouse}', flush=True)
        aqt = ('aqtinstall @ git+https://github.com/miurahr/aqtinstall.git@'
               '076e1659807d0b362a3ed684d54c2e9c775eb9c7' if os.name == 'nt' else 'aqtinstall')
        run(sys.executable, '-m', 'pip', 'install', 'cmake', 'ninja', aqt,
            f'PySide6=={qt_version}', f'shiboken6_generator=={qt_version}')
        host, architecture, directory = {
            'win32': ('windows', 'win64_msvc2022_64', 'msvc2022_64'),
            'darwin': ('mac', 'clang_64', 'macos'),
            'linux': ('linux', 'linux_gcc_64', 'gcc_64'),
        }[sys.platform]
        sdk = root / 'qt' / f'{host}-{platform.machine()}-{architecture}-{qt_version}'
        if not (sdk / 'opal-complete').is_file():
            sdk.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=sdk.parent) as temporary:
                archives = ['qtbase', 'icu'] if sys.platform == 'linux' else ['qtbase']
                run(sys.executable, '-m', 'aqt', 'install-qt', host, 'desktop', qt_version, architecture,
                    '--archives', *archives, '-O', temporary)
                (Path(temporary) / 'opal-complete').touch()
                if sdk.exists():
                    shutil.rmtree(sdk)
                shutil.move(temporary, sdk)
        else:
            print(f'Reusing Qt SDK: {sdk}', flush=True)
        with tempfile.TemporaryDirectory(prefix='opal-fluentqt-') as temporary:
            run(sys.executable, build_script, '--qt-prefix', sdk / qt_version / directory,
                '--work-dir', temporary)
            wheel = next((Path(temporary) / 'wheelhouse').glob('*.whl'))
            wheelhouse.mkdir(parents=True, exist_ok=True)
            staged = wheelhouse / (wheel.name + '.tmp')
            shutil.copy2(wheel, staged)
            staged.replace(wheelhouse / wheel.name)
        return wheelhouse / wheel.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build_script', type=Path)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error('Opal Presenter must remain on Python 3.14')
    root = Path(os.environ.get('OPAL_CACHE_DIR', Path.home() / '.cache' / 'opal-presenter')).resolve()
    wheel = ensure_wheel(args.build_script.resolve(), root)
    output = Path('.cache/fluentqt/wheelhouse')
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob('fluentqt-*.whl'):
        old.unlink()
    shutil.copy2(wheel, output / wheel.name)
    if args.install:
        run(sys.executable, '-m', 'pip', 'install', '--force-reinstall', '--no-deps', output / wheel.name)


if __name__ == '__main__':
    main()
