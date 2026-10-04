Slide designer
==============

Open a song or custom item, then choose Edit or Edit All. The designer replaces
that inner text-editing dialog. The outer Song Editor and Custom Slides windows
retain their read-only lists and do not show the canvas or design panes.

Edit words on the left and select a section to preview it. The centre canvas
uses the projection renderer and its pagination. Preview the current output,
global, assigned item or current service theme. The Theme selector assigns an
item theme, subject to OpenLP+'s existing theme-level setting.

Add text boxes, rectangles, ellipses and images with the toolbar. Select an
element on the canvas or in Layers. The top row in Layers is the frontmost object;
drag rows to reorder them, or use the arrow buttons and the Arrange menu. Slide
text is a layer too, and new objects are added at the front. Selecting a covered
object in Layers shows an outline that can be dragged without raising the object.
Drag its lower right handle to resize it. Properties controls geometry, rotation,
opacity, font, alignment, colours and borders. Layers and Properties can be shown
independently. Undo, redo and Reset design in the toolbar operate on the design.

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
Layer order is saved with the design and used by the projection renderer. Older
designs without an explicit order retain their original text-above-decorations
appearance.

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
