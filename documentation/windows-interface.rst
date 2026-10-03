Windows interface appearances
=============================

Settings > Configure OpenLP+ > General > UI Settings contains an
``Interface appearance (needs restart)`` choice:

* **Classic** preserves the existing rendering and remains the default.
* **Modern** adds solid content panels, blue selection accents, upright layout
  navigation, larger panel headers, and a prominent Go live button. Service and
  Library remain on the left; Preview and Live keep their slide lists above the
  screen previews, with adjustable dividers.

Appearance is independent of the existing Interface Theme color scheme.
Modern supports system, light and dark colors; selecting QDarkStyle with Modern
uses Modern's dark palette. Selecting Classic retains QDarkStyle rendering.
Restart OpenLP+ after changing either setting. Saved layouts remain available.
macOS and Linux continue using their existing interface.

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
