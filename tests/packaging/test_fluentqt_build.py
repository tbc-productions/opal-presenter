"""The FluentQt source patches must work with Windows' legacy default encoding."""
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FluentQtBuildTest(unittest.TestCase):
    def test_source_patch_preserves_utf8_with_cp1252_default(self):
        build = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/build_fluentqt.py'))
        read_text, write_text = Path.read_text, Path.write_text

        def windows_read(path, *args, **kwargs):
            kwargs.setdefault('encoding', 'cp1252')
            return read_text(path, *args, **kwargs)

        def windows_write(path, text, *args, **kwargs):
            kwargs.setdefault('encoding', 'cp1252')
            kwargs.setdefault('newline', '\r\n')
            return write_text(path, text, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'QtCompat.h'
            original = '// \u201cFluentQt\u201d copyright\nQIcon::Normal\n'
            source.write_bytes(original.encode('utf-8'))
            with patch.object(Path, 'read_text', windows_read), patch.object(Path, 'write_text', windows_write):
                build['replace'](source, 'QIcon::Normal', 'QIcon::Disabled')
                build['replace'](source, 'QIcon::Normal', 'QIcon::Disabled')
            self.assertEqual(source.read_text(encoding='utf-8'), original.replace('QIcon::Normal', 'QIcon::Disabled'))


if __name__ == '__main__':
    unittest.main()
