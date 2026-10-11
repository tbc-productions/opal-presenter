# FluentQt and Python 3.14

Opal Presenter uses the native `calvinhxx/Fluent-Qt` library. Upstream's published
1.8.2 wheels do not support Python 3.14. Opal builds a pinned source revision
as `FluentQt 1.9.3+openlp.1` instead. This is an Opal build, not an upstream
Python compatibility guarantee. Python remains 3.14; Qt, PySide6 and Shiboken
must all be 6.11.1 to match PySide6-QtAds.

On this page:

- [Build and install](#build-and-install)
- [UI integration](#ui-integration)
- [Platform verification](#platform-verification)
- [Native binding fixes](#native-binding-fixes)
- [Service selection and drag feedback](#service-selection-and-drag-feedback)

## Build and install

### 1. Install prerequisites

Install the build prerequisites into a Python 3.14 virtual environment:

```bash
python -m pip install cmake ninja aqtinstall PySide6==6.11.1 shiboken6_generator==6.11.1
```

### 2. Install the Qt SDK and build the wheel

Install the Qt 6.11.1 C++ SDK using aqt or the Qt installer. For macOS:

```bash
python -m aqt install-qt mac desktop 6.11.1 clang_64 --archives qtbase -O .cache/qt
python scripts/build_fluentqt.py --qt-prefix .cache/qt/6.11.1/macos --install
```

For other platforms:

- **Windows:** use the `win64_msvc2022_64` SDK and run from an MSVC developer terminal.
- **Linux:** use the `linux_gcc_64` SDK with the system C++ compiler and
  Qt's system build prerequisites installed.

Pass the installed SDK directory to
`--qt-prefix`. Each platform must build its own wheel.

The script checks the source revision and build dependency versions, widens the
source's Python version guard, builds the native extension and type stubs, runs
the upstream binding tests, then writes a wheel under
`.cache/fluentqt/wheelhouse`. On macOS it relocates Qt framework references to
PySide's runtime and targets macOS 13.

### 3. Install the built wheel

Install this wheel before installing the project, or give pip the wheelhouse via
`--find-links`. Do not substitute the
upstream 1.8.2 wheel.

## UI integration

### Menus and accessibility

On macOS the application menu bar and its submenus use native system menus,
including About, Preferences and Quit roles. Other platforms use Fluent menu
chrome, and in-window context and dropdown menus remain Fluent on all platforms.
Shortcut labels share a consistent right inset; only submenu rows reserve space
for a submenu arrow. The pinned wheel patches this layout in FluentQt.

Adapters use unique Fluent class names and expose Qt-style Python aliases.
Qt selects accessibility interfaces from meta-object class names; reusing
QTabBar or QToolButton for a different native type causes invalid casts and
can crash during macOS accessibility hit testing.

### Widgets and command bars

`opal.core.widgets.fluent` is the operator UI construction boundary:

- **Native Fluent controls:** replace compatible button, label, input, selection,
  menu and slider classes.
- **Qt infrastructure:** supplies application, layout, docking, model and projection support.
- **CommandBar:** owns toolbar actions and responsive overflow. It rejects
  QWidgetAction, so embedded Fluent inputs and SplitButton sit beside command groups
  in a layout container. Open service uses FluentQt's native SplitButton.
- **Preview and Live:** slide actions, Live display modes and Go To verse use native
  CommandBar presenters. Rows use native control height; Hide and Play remain
  SplitButtons beside the command groups.
- **Command groups:** separators share one CommandBar and responsive overflow menu
  by default. Groups keep their natural width and leave spare space after commands,
  or give it to expanding inputs.
- **Library toolbars:** expand one CommandBar across the row, placing Preview, Live
  and Add to Service at the trailing edge. SplitButtons share CommandBar height
  and honour the native Subtle style.
- **Layout preset rail:** belongs to the main content layout rather than a Qt toolbar.
- **Library navigation:** a native SelectorBar row with a More overflow menu.
  Original coloured QIcons occupy native slots and appear in overflow; configured
  plugin icon colours are preserved. More-mode reserves space for the selected item
  while retaining earlier items that fit.
- **Page changes:** wait until the overflow popup closes so Library focus handlers
  cannot interrupt menu activation.
- **Bible tabs:** sub-tabs and result tabs retain native TabView.

### Appearance and saved layouts

The appearance selector contains Auto, Dark and Light. Existing Classic colour
preferences migrate to the same colour choice in Fluent. Saved ADS layouts
retain their existing Modern storage keys to avoid losing panel placement.

### Lists, trees and grids

- **DataGrid:** used by flat collections, including the sortable Songs Library,
  and by Preview and Live slide lists.
- **TreeView:** used by Presentation, Images and Media. Folder and service hierarchies
  retain supplied column headings, expansion and parent/child item contracts.
- **Row typography:** Library rows retain the standard Fluent body font without
  reducing it during column setup.
- **Headings:** single-column grids show a heading where the screen needs it;
  tables retain their column headings.
- **Thumbnail size:** preferences adjust DataGrid row and icon sizes rather than
  switching to ListView.
- **Theme Manager:** switches between DataGrid for its list and GridView for its
  thumbnail grid, sharing theme records and selection across both views.

### Native controls and specialised editors

- **Fluent controls:** cover item collections, numeric/date/time fields, font
  selection, group cards, tab navigation, progress indicators and command buttons
  in toolbars, dialogs and wizards.
- **Qt hosts:** retain structural window/modal hosts and item models.
- **Text editors:** the specialised song editor and HTML text views retain Qt's
  document, cursor, spell-checking and rich-text engines. FluentQt's public TextEdit
  API does not expose the operations these editors need.
- **System pickers:** file and print dialogs retain platform implementations.
- **Colour selection:** uses FluentQt's native ColorPicker.

### Dialogs

- **Compact prompts and forms:** use the shared `ContentDialog` and `FormDialog` adapters.
- **Action order:** primary on the left, secondary in the middle, Cancel or Close
  on the right. The default action controls emphasis without changing order.
- **Content:** retains FluentQt's native padding and scrolls within the host so
  lengthy messages leave buttons visible.
- **FormDialog commands:** forward through the existing button box, preserving
  validation and Help behaviour.
- **Larger editors:** retain `QDialog` with a visible heading.

See the [dialog design pattern](dialogs.md) for implementation and verification guidance.

### Applying theme changes

Theme changes display a restart reminder. Native controls can update their
colours live, but existing QAction icons and ADS docking surfaces cache the
startup scheme. Restarting applies the selected scheme consistently.

### Tooltips and help

Hover hints use native FluentQt ToolTip surfaces, including widget and action
hints, Library row metadata, and immediate Service notes and drag hints. Qt's
existing tooltip text and hover delay are retained; long hints wrap within the
screen and dismiss on leaving the target, interaction or timeout. Settings help
continues to use persistent, dismissible TeachingTip cards.

## Platform verification

The Python 3.14 wheel and native application have been verified on macOS arm64.
Windows/Linux source builds and frozen application bundles still need platform
verification before release.

## Native binding fixes

The Opal wheel also fixes native FluentQt QIcon painting: disabled Button
and CommandBar overflow presenters request QIcon.Disabled rather than the
normal icon image. QAction enabled state remains owned by FluentQt.

### Accessibility factories

The Opal wheel guards FluentQt's global accessibility factories with Qt widget
metadata before attempting C++ RTTI casts. QtWebEngine's private Quick objects
can be compiled without RTTI; casting those objects from the progress factory
previously crashed macOS startup when the renderer received focus. Native
Fluent and WebEngine accessibility remain enabled.

### Type discovery

Binding type discovery also uses Qt metadata instead of C++ RTTI. Qt's private
item models and partially constructed layout children can lack usable RTTI;
wrapping those objects previously crashed the test suite. BindingApi shims
without their own Qt meta-object retain their concrete Python wrapper type.

## Service selection and drag feedback

Library plugins, Cloud Library, Themes, Preview, Live and Service use the same
boxed drag card, with the item type icon, title and a count for multiple items.
The card follows the Fluent appearance and keeps the count visible when a long
title is shortened.

### Selecting, moving and editing notes

- **Selection:** Ctrl/Command-click, Shift-click and Shift-arrow are supported.
- **Dragging:** moves selected service items together in their original order.
  Moving or cancelling a drag preserves selection and expanded slides.
- **Preview and Go Live:** disabled for multiple selected rows.
- **Notes:** saved text applies to every selected service item, with parent and
  slide selections counted once. Matching existing notes appear in the editor;
  different notes start empty.
- **Save or Cancel:** saving replaces each selected item's notes; Cancel preserves them.

### Importing and deleting selected items

Dropping selected service items into the Library imports each into its matching
plugin, including mixed selections. Every item must have an enabled, supported
Library destination before the import begins. Existing overwrite confirmations
still apply. Cancelling an import stops the remaining items and retains items
already imported. Delete removes all selected service items, using the existing
confirmation preference.
