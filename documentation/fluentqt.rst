FluentQt and Python 3.14
=======================

OpenLP+ uses the native ``calvinhxx/Fluent-Qt`` library. Upstream's published
1.8.2 wheels do not support Python 3.14. OpenLP builds a pinned source revision
as ``FluentQt 1.9.2+openlp.3`` instead. This is an OpenLP build, not an upstream
Python compatibility guarantee. Python remains 3.14; Qt, PySide6 and Shiboken
must all be 6.11.1 to match PySide6-QtAds.

Install the build prerequisites into a Python 3.14 virtual environment::

    python -m pip install cmake ninja aqtinstall PySide6==6.11.1 shiboken6_generator==6.11.1

Install the Qt 6.11.1 C++ SDK using aqt or the Qt installer. For macOS::

    python -m aqt install-qt mac desktop 6.11.1 clang_64 --archives qtbase -O .cache/qt
    python scripts/build_fluentqt.py --qt-prefix .cache/qt/6.11.1/macos --install

On Windows use the ``win64_msvc2022_64`` SDK and run from an MSVC developer
terminal. On Linux use the ``linux_gcc_64`` SDK with the system C++ compiler and
Qt's system build prerequisites installed. Pass the installed SDK directory to
``--qt-prefix``. Each platform must build its own wheel.

The script checks the source revision and build dependency versions, widens the
source's Python version guard, builds the native extension and type stubs, runs
the upstream binding tests, then writes a wheel under
``.cache/fluentqt/wheelhouse``. On macOS it relocates Qt framework references to
PySide's runtime and targets macOS 13. Install this wheel before installing the
project, or give pip the wheelhouse via ``--find-links``. Do not substitute the
upstream 1.8.2 wheel.

UI integration
--------------

On macOS the application menu bar and its submenus use native system menus,
including About, Preferences and Quit roles. Other platforms use Fluent menu
chrome, and in-window context and dropdown menus remain Fluent on all platforms.

Adapters use unique Fluent class names and expose Qt-style Python aliases.
Qt selects accessibility interfaces from meta-object class names; reusing
QTabBar or QToolButton for a different native type causes invalid casts and
can crash during macOS accessibility hit testing.

``openlp.core.widgets.fluent`` is the operator UI construction boundary. Native
Fluent controls replace the compatible button, label, input, selection, menu and
slider classes. Native CommandBar owns toolbar actions and responsive overflow;
Open service uses FluentQt's native SplitButton. Qt still supplies application,
layout, docking, model and projection infrastructure. CommandBar rejects
QWidgetAction, so embedded Fluent inputs and SplitButton sit beside command
groups in a layout container. Preview and Live slide actions, including the
Live display modes and Go To verse command, use native CommandBar presenters.
Their rows use the native control height; Hide and Play remain SplitButtons
beside the command groups. The layout preset rail is part of the main content
layout rather than a Qt toolbar. Library navigation uses a single native
SelectorBar row with a More overflow menu. Original coloured QIcons occupy
the native icon slots and appear in the overflow menu; configured plugin icon
colours are preserved. More-mode overflow reserves space for the selected
item while retaining earlier items that fit. Page changes wait until the
overflow popup closes so Library focus handlers cannot interrupt menu activation.
Bible sub-tabs and result tabs retain native TabView.

The appearance selector contains Auto, Dark and Light. Existing Classic colour
preferences migrate to the same colour choice in Fluent. Saved ADS layouts
retain their existing Modern storage keys to avoid losing panel placement.

Flat collections use native FluentQt DataGrid, including the sortable Songs
Library. Preview and Live slide lists also use DataGrid. Presentation, Images
and Media use TreeView. Library rows retain the standard Fluent body font
without reducing its size during column setup. Single-column grids show a heading where the screen needs it; tables
retain their column headings. Folder and service hierarchies retain native
TreeView with supplied column headings visible, preserving expansion and
parent/child item contracts. Thumbnail preferences adjust DataGrid row and
icon sizes rather than switching to ListView.
The Theme Manager switches between DataGrid for its list and GridView for its
thumbnail grid, sharing theme records and selection across both views.

Native Fluent controls now cover item collections, numeric/date/time fields,
font selection, group cards, tab navigation, progress indicators and command
buttons in toolbars, dialogs and wizards. Qt retains structural window/modal
hosts and item models. The specialised song editor and HTML text views retain
Qt's document, cursor, spell-checking and rich-text engines; FluentQt's public
TextEdit API does not expose the operations these editors need. System file
and print dialogs retain their platform implementations. Colour selection uses FluentQt's native ColorPicker.

Theme changes display a restart reminder. Native controls can update their
colours live, but existing QAction icons and ADS docking surfaces cache the
startup scheme. Restarting applies the selected scheme consistently.

The Python 3.14 wheel and native application have been verified on macOS arm64.
Windows/Linux source builds and frozen application bundles still need platform
verification before release.

The OpenLP wheel also fixes native FluentQt QIcon painting: disabled Button
and CommandBar overflow presenters request QIcon.Disabled rather than the
normal icon image. QAction enabled state remains owned by FluentQt.
