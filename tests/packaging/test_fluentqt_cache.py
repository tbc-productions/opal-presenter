"""Check cold builds, shared wheel hits and cache invalidation without Qt."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('opal_fluentqt_cache', ROOT / 'scripts/cache_fluentqt.py')
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class OpalFluentQtCacheTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.script = self.root / 'presenter/scripts/build_fluentqt.py'
        self.script.parent.mkdir(parents=True)
        self.script.write_text("QT_VERSION = '6.11.1'\n")
        self.calls = []
        self.patcher = patch.object(cache.subprocess, 'check_output', return_value='Opal test compiler')
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def fake_run(self, *args):
        self.calls.append(args)
        if '-O' in args:
            (Path(args[-1]) / '6.11.1').mkdir()
        if '--work-dir' in args:
            output = Path(args[-1]) / 'wheelhouse'
            output.mkdir()
            with zipfile.ZipFile(output / 'fluentqt-test.whl', 'w') as wheel:
                wheel.writestr('fluentqt/__init__.py', '# validated wheel')

    def test_second_repository_reuses_wheel_without_installing_build_tools(self):
        with patch.object(cache, 'run', side_effect=self.fake_run):
            wheel = cache.ensure_wheel(self.script, self.root / 'shared')
            other = self.root / 'packaging/source/scripts/build_fluentqt.py'
            other.parent.mkdir(parents=True)
            other.write_bytes(self.script.read_bytes())
            self.calls.clear()
            self.assertEqual(cache.ensure_wheel(other, self.root / 'shared'), wheel)
            self.assertEqual(self.calls, [])

    def test_changed_patches_rebuild_wheel_but_reuse_qt_sdk(self):
        with patch.object(cache, 'run', side_effect=self.fake_run):
            first = cache.ensure_wheel(self.script, self.root / 'shared')
            self.script.write_text("QT_VERSION = '6.11.1'\n# changed source patches\n")
            self.calls.clear()
            second = cache.ensure_wheel(self.script, self.root / 'shared')
            self.assertNotEqual(first.parent, second.parent)
            self.assertTrue(any('--work-dir' in args for args in self.calls))
            self.assertFalse(any('install-qt' in args for args in self.calls))

    def test_compiler_and_qt_version_change_wheel_key(self):
        key = cache.wheel_key(self.script, '6.11.1')
        self.assertNotEqual(key, cache.wheel_key(self.script, '6.12.0'))
        with patch.object(cache.subprocess, 'check_output', return_value='new compiler'), \
                patch.dict(cache.os.environ, VCToolsVersion='new compiler'):
            self.assertNotEqual(key, cache.wheel_key(self.script, '6.11.1'))

    def test_checkout_line_endings_do_not_change_wheel_key(self):
        key = cache.wheel_key(self.script, '6.11.1')
        helper = self.root / 'cache_fluentqt.py'
        helper.write_bytes(Path(cache.__file__).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.script.write_bytes(self.script.read_text().encode().replace(b'\n', b'\r\n'))
        with patch.object(cache, '__file__', str(helper)):
            self.assertEqual(key, cache.wheel_key(self.script, '6.11.1'))

    def test_failed_build_does_not_publish_wheel(self):
        def fail_build(*args):
            if '--work-dir' in args:
                raise subprocess.CalledProcessError(1, args)
            self.fake_run(*args)

        with patch.object(cache, 'run', side_effect=fail_build):
            with self.assertRaises(subprocess.CalledProcessError):
                cache.ensure_wheel(self.script, self.root / 'shared')
        self.assertEqual(list((self.root / 'shared').rglob('*.whl')), [])

    def test_corrupt_wheel_is_rebuilt(self):
        with patch.object(cache, 'run', side_effect=self.fake_run):
            wheel = cache.ensure_wheel(self.script, self.root / 'shared')
            wheel.write_bytes(b'interrupted download')
            self.calls.clear()
            cache.ensure_wheel(self.script, self.root / 'shared')
            self.assertTrue(any('--work-dir' in args for args in self.calls))
            self.assertTrue(zipfile.is_zipfile(wheel))

    def test_install_replaces_stale_same_version_wheel(self):
        wheel = self.root / 'fluentqt-current.whl'
        wheel.write_bytes(b'validated wheel')
        output = self.root / '.cache/fluentqt/wheelhouse'
        output.mkdir(parents=True)
        (output / 'fluentqt-stale.whl').touch()
        previous = Path.cwd()
        cache.os.chdir(self.root)
        self.addCleanup(cache.os.chdir, previous)
        with patch.object(cache, 'ensure_wheel', return_value=wheel), patch.object(cache, 'run') as install, \
                patch.object(cache.sys, 'argv', ['cache_fluentqt.py', str(self.script), '--install']):
            cache.main()
        self.assertEqual([path.name for path in output.glob('*.whl')], [wheel.name])
        install.assert_called_once_with(cache.sys.executable, '-m', 'pip', 'install', '--force-reinstall',
                                        '--no-deps', Path('.cache/fluentqt/wheelhouse') / wheel.name)


if __name__ == '__main__':
    unittest.main()
