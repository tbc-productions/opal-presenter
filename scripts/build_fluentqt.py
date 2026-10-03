#!/usr/bin/env python3
"""Build OpenLP+'s pinned FluentQt wheel for Python 3.14 and Qt 6.11.1.

Requires a matching Qt C++ SDK, cmake, ninja and shiboken6_generator. The
result is a local distribution; it is not an upstream supported wheel.
"""
import argparse
import os
import re
from pathlib import Path
import subprocess
import sys

SOURCE_URL = 'https://github.com/calvinhxx/Fluent-Qt.git'
SOURCE_REVISION = '4da001f20d0e1bee4a0a1d0519535e9ff0e5eb42'
VERSION = '1.9.2+openlp.7'
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


def patch_disabled_icons(source):
    """Native Button and overflow commands must request QIcon.Disabled."""
    replace(source / 'src/compatibility/QtCompat.h',
            'QWindow* targetWindow = nullptr)\n{\n    const qreal dpr = qMax<qreal>(1.0, devicePixelRatio);',
            'QWindow* targetWindow = nullptr, QIcon::Mode mode = QIcon::Normal)\n{\n'
            '    const qreal dpr = qMax<qreal>(1.0, devicePixelRatio);')
    replace(source / 'src/compatibility/QtCompat.h',
            'targetWindow ? icon.pixmap(targetWindow, logicalExtent) : icon.pixmap(logicalExtent);',
            'targetWindow ? icon.pixmap(targetWindow, logicalExtent, mode) : icon.pixmap(logicalExtent, mode);')
    replace(source / 'src/compatibility/QtCompat.h',
            'return icon.pixmap(logicalExtent, dpr);',
            'return icon.pixmap(logicalExtent, dpr, mode);')
    replace(source / 'src/components/basicinput/Button.cpp',
            'fluentIconPixmapForLogicalExtent(icon(), iconSize(), targetDpr, targetWindow);',
            'fluentIconPixmapForLogicalExtent(icon(), iconSize(), targetDpr, targetWindow,\n'
            '                                                isEnabled() ? QIcon::Normal : QIcon::Disabled);')
    replace(source / 'src/components/menus_toolbars/private/CommandPresenter_p.cpp',
            'window() ? window()->windowHandle() : nullptr);',
            'window() ? window()->windowHandle() : nullptr,\n'
            '            isEnabled() ? QIcon::Normal : QIcon::Disabled);')


def patch_selector_overflow(source):
    """More menus retain the leading items and make room for the selection."""
    selector = source / 'src/components/navigation/SelectorBar.cpp'
    if 'const bool hasSelection = candidates.contains(m_selectedIndex);' in selector.read_text():
        return
    replace(selector,
            '    int startPosition = 0;\n',
            '    if (m_overflowBehavior == OverflowBehavior::MoreButton) {\n'
            '        const bool hasSelection = candidates.contains(m_selectedIndex);\n'
            '        int used = hasSelection ? widths.value(m_selectedIndex) : 0;\n'
            '        for (int index : candidates) {\n'
            '            if (index == m_selectedIndex) {\n'
            '                result.append(index);\n'
            '                continue;\n'
            '            }\n'
            '            const int width = widths.value(index, metrics().minItemWidth);\n'
            '            if (used + width <= availableWidth || (!hasSelection && result.isEmpty())) {\n'
            '                result.append(index);\n'
            '                used += width;\n'
            '            }\n'
            '        }\n'
            '        return result;\n'
            '    }\n\n'
            '    int startPosition = 0;\n')


def patch_subtle_split_buttons(source):
    """SplitButton must honour Subtle just like native CommandBar presenters."""
    replace(source / 'src/components/basicinput/SplitButton.cpp',
            '    if (!isEnabled()) {\n        baseBg = colors.controlDisabled;',
            '    if (fluentStyle() == Subtle && !accentLike)\n'
            '        baseBg = Qt::transparent;\n\n'
            '    if (!isEnabled()) {\n'
            '        baseBg = fluentStyle() == Subtle ? QColor(Qt::transparent) : colors.controlDisabled;')
    replace(source / 'src/components/basicinput/SplitButton.cpp',
            ': colors.controlTertiary;',
            ': (fluentStyle() == Subtle ? colors.subtleTertiary : colors.controlTertiary);')
    replace(source / 'src/components/basicinput/SplitButton.cpp',
            ': colors.controlSecondary;',
            ': (fluentStyle() == Subtle ? colors.subtleSecondary : colors.controlSecondary);')


def patch_menu_shortcut_alignment(source):
    """Only submenu rows reserve a trailing arrow column."""
    menu = source / 'src/components/menus_toolbars/Menu.cpp'
    replace(menu,
            'hasSubmenuAction(this) ? spacing.controlHeight.small : ::Spacing::Small;\n'
            '    QRect rect = actionGeometry(action);',
            'action->menu() ? spacing.controlHeight.small : ::Spacing::Small;\n'
            '    QRect rect = actionGeometry(action);')
    replace(menu,
            'const int textRight = itemRect.right() - textPadding - trailingColumn - shortcutReserve;',
            'const int rowTrailingColumn = action->menu() ? trailingColumn : ::Spacing::Small;\n'
            '        const int textRight = itemRect.right() - textPadding - rowTrailingColumn - shortcutReserve;')


def patch_accessibility_factories(source):
    """Avoid RTTI casts on QtWebEngine's private objects, which have no typeinfo."""
    # These global factories are queried for every QObject, including WebEngine
    # QQuickItems compiled without RTTI. Use Qt's metadata to accept only QWidget
    # objects before the native factory attempts its component/interface casts.
    files = (
        'basicinput/private/BasicValueAccessibility_p.cpp',
        'basicinput/private/ColorPickerAccessibility_p.cpp',
        'basicinput/private/MultiSelectComboBoxAccessibility_p.cpp',
        'collections/private/DataGridAccessibility_p.cpp',
        'collections/private/FlipViewAccessibility_p.cpp',
        'collections/private/SplitViewAccessibility_p.cpp',
        'date_time/private/CalendarViewAccessibility_p.cpp',
        'date_time/private/PickerAccessibility_p.cpp',
        'navigation/private/NavigationSelectionAccessibility_p.cpp',
        'scrolling/private/AnnotatedScrollBarAccessibility_p.cpp',
        'scrolling/private/PipsPagerAccessibility_p.cpp',
        'status_info/private/ProgressAccessibility_p.cpp',
        'textfields/private/AutoSuggestBoxAccessibility_p.cpp',
        'textfields/private/NumberBoxAccessibility_p.cpp',
    )
    pattern = r'dynamic_cast<([^>]+)>\(object\)'
    for relative in files:
        path = source / 'src/components' / relative
        text = path.read_text()
        patched, count = re.subn(pattern, r'dynamic_cast<\1>(qobject_cast<QWidget*>(object))', text)
        if not count and 'qobject_cast<QWidget*>(object)' not in text:
            raise RuntimeError(f'Pinned accessibility factory changed: {path}')
        path.write_text(patched)


def patch_type_discovery(source):
    """Use Qt metadata when wrapping private Qt objects without C++ RTTI."""
    native = source / 'bindings/pyside6/native'
    for filename, namespace in (('typesystem_fluentqt.xml', []), ('spatial_types.xml', ['fluent'])):
        path = native / filename
        namespaces = list(namespace)

        def patch_tag(match):
            tag = match.group(0)
            if tag == '</namespace-type>':
                namespaces.pop()
            elif tag.startswith('<namespace-type'):
                namespaces.append(re.search(r'name="([^"]+)"', tag)[1])
            elif 'polymorphic-id-expression=' not in tag:
                name = re.search(r'name="([^"]+)"', tag)[1]
                # The BindingApi shims have no Q_OBJECT and are constructed with
                # their concrete Python type; they need no base-type discovery.
                expression = ('false' if namespaces == ['fluent', 'binding'] else
                              f'qobject_cast&lt;{"::".join([*namespaces, name])}*&gt;(%B)')
                tag = tag.replace('/>', f' polymorphic-id-expression="{expression}"/>') if tag.endswith('/>') else \
                    tag[:-1] + f' polymorphic-id-expression="{expression}">'
            return tag

        text = re.sub(r'</namespace-type>|<(?:namespace-type|object-type)\b[^>]*>', patch_tag, path.read_text())
        path.write_text(text)


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
    patch_disabled_icons(source)
    patch_selector_overflow(source)
    patch_subtle_split_buttons(source)
    patch_accessibility_factories(source)
    patch_menu_shortcut_alignment(source)
    patch_type_discovery(source)
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
