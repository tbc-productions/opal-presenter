Interface themes
================

Settings > Configure OpenLP+ > General > UI Settings contains one
``Interface Theme (needs restart)`` selector on every platform:

* **Classic (Auto)** follows the system colour scheme with Classic styling.
* **Classic Dark** uses Classic styling with dark colours.
* **Classic Light** uses Classic styling with light colours.
* **Modern (Auto)** follows the system colour scheme with Modern styling and is the default.
* **Modern Dark** uses Modern styling with dark colours.
* **Modern Light** uses Modern styling with light colours.

Modern adds Fluent-style neutral surfaces, rounded controls, accent focus
indicators, upright layout navigation, and a compact accent Go live button. Service and
Library remain on the left; Preview and Live keep their slide lists above the
screen previews, with adjustable dividers.

Restart OpenLP+ after changing the theme. Saved layouts remain available.
Saving a different theme displays a restart reminder. Switching between Classic
and Modern replaces the workspace's dock widgets, so the change applies at startup.
Existing appearance and colour settings load into the combined selector;
legacy QDarkStyle selections map to the corresponding Dark option.
Modern is available on Windows, macOS and Linux. Native Mica remains specific
to supported Windows versions; other platforms use solid window rendering.

Modern's Fluent presentation uses the existing PySide6 widgets and retains their
actions, shortcuts and accessibility roles. Hover animation respects Windows'
animation preference. Dialogs and floating docks share the appearance; projected
slide content is unaffected. No FluentQt dependency is required: its published
bindings target an older Python and Qt runtime than this application uses.

Modern uses Qt Advanced Docking System for Service, Library, Themes and
Projectors. Unlock panels in the View menu, then drag a pane's tab or title
to rearrange it. Drop on the docking targets to split or tab panes, or drag
outside the window to float a pane or a whole tab group. Use the pin button
or the tab context menu to auto-hide a pane along a window edge.

Default, Setup and Live remember their own dock arrangements, including
floating groups and auto-hide sidebars. Modern and Classic store their docking
layouts separately. View's reset-layout command resets the active appearance's
presets. Preview and Live remain together in the central slide-controller area,
with their existing adjustable dividers and bottom screen previews.

On Windows 11 build 22621 and later, Modern requests native Mica behind the
window frame using the documented DWM system-backdrop API. Content remains
opaque. Earlier Windows versions and unsuccessful backdrop calls retain solid
window rendering. The operating system controls material fallbacks.

The Live status badge reports OpenLP's output state: Ready, Live, Blank,
Theme, Logo or Desktop. Live requires a loaded item, an OpenLP display window
and no active hide mode. It does not confirm physical projector connectivity.
