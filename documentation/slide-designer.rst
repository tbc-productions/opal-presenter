Slide designer
==============

Open a song or custom item, then choose Edit or Edit All. The designer replaces
that inner text-editing dialog. The outer Song Editor and Custom Slides windows
retain their read-only lists and do not show the canvas or inspector.

Edit words on the left and select a section to preview it. The centre canvas
uses the projection renderer and its pagination. Preview the current output,
global, assigned item or current service theme. The Theme selector assigns an
item theme, subject to OpenLP+'s existing theme-level setting.

Add text boxes, rectangles, ellipses and images with the toolbar. Select an
element on the canvas or in the inspector. Drag to move it and drag its lower
right handle to resize it. The inspector controls geometry, rotation, opacity,
font, alignment, colours and borders. Decorations can be reordered relative to
one another; lyrics remain above them. Undo, redo and reset operate on the design.

Designs currently apply to every slide in the item. In Edit All, the section
selector and text cursor select the preview; they do not create individual-slide
overrides. Previous and Next move between overflow pages of that section.

Accepting an inner editor updates the outer dialog's draft. Cancelling the inner
editor discards its changes; cancelling the outer dialog leaves the library
unchanged. Saving writes the design along with the lyrics.

Portability
-----------

Songs store a versioned design document in the songs database. OpenLyrics XML
exports include it in an ``olp:design`` extension with namespace
``https://openlp.org/ns/slide-design/1``. Custom items store the same extension
inside their existing XML and preserve it through their existing ``.osz`` export
and import route. Service headers also retain the design.

Added images are decoded and embedded as PNG data URIs. Large images are scaled
to fit 1920 x 1080, with an 8 MB encoded-image limit. Exports include a snapshot of
the resolved static theme, including its background image. The receiving OpenLP+
installation therefore does not need those original image files or a matching
named theme. Exporting does not freeze the source library item's theme.
Explicitly assigning a new theme releases an imported theme snapshot.

This is a static design format: video/stream backgrounds and font files are not
embedded. Fonts still need to be available on the receiving computer. Other
OpenLyrics applications may ignore or reject the OpenLP+ extension. PPTX/ODP
export does not yet preserve the added design elements.
