Interface themes
================

Settings > Configure Opal Presenter > General > UI Settings contains one
``Interface Theme (needs restart)`` selector on every platform:

* **Auto** follows the system colour scheme and is the default.
* **Dark** uses dark colours.
* **Light** uses light colours.

Modern is the only layout system. Older Classic appearance settings use Modern,
while keeping the user's colour preference. Classic dock arrangements are ignored.

Modern adds Fluent-style neutral surfaces, rounded controls, accent focus
indicators, upright layout navigation, and a compact accent Go live button. Service and
Library remain on the left; Preview and Live keep their slide lists above the
screen previews, with adjustable dividers.

Restart Opal Presenter after changing the theme. Saved layouts remain available.
Saving a different theme displays a restart reminder. Legacy QDarkStyle selections
map to Dark.
Modern is available on Windows, macOS and Linux. Native Mica remains specific
to supported Windows versions; other platforms use solid window rendering.

Modern's native FluentQt presentation retains the application's
actions, shortcuts and accessibility roles. Hover animation respects Windows'
animation preference. Dialogs and floating docks share the appearance; projected
slide content is unaffected. See ``fluentqt.rst`` for the pinned native FluentQt
runtime and build instructions.

Modern uses Qt Advanced Docking System for Service, Library, Themes, Projectors,
Cloud Library, Preview and Live. Unlock panels in the View menu, then drag a pane's tab or title
to rearrange it. Drop on the docking targets to split or tab panes, or drag
outside the window to float a pane or a whole tab group. Use the pin button
or the tab context menu to auto-hide a pane along a window edge.

Workspace, Setup, Live and Library Sync remember their own dock arrangements,
including floating groups and auto-hide sidebars. View's reset-layout command
resets all presets. Preview and Live have independent docks, with adjustable
dividers and bottom screen previews. Library Sync places Library and Themes in
one tab group, with Library selected, and Cloud Library to its right.

On Windows 11 build 22621 and later, Modern requests native Mica behind the
window frame using the documented DWM system-backdrop API. Content remains
opaque. Earlier Windows versions and unsuccessful backdrop calls retain solid
window rendering. The operating system controls material fallbacks.

The Live status badge reports Opal's output state: Ready, Live, Blank,
Theme, Logo or Desktop. Live requires a loaded item, an Opal display window
and no active hide mode. It does not confirm physical projector connectivity.
