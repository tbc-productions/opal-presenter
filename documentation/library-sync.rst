Library Sync
============

Library Sync is a bundled plugin for sharing Library items within an organisation.
Select **Library Sync** in the workspace navigation or **View → Mode → Library Sync**.
The preset places Library and Themes in the same dock area, with Library selected,
to the left of Cloud Library. Each preset retains its own customised Modern layout.
The plugin can be disabled in Plugin Manager. Older Classic layout data is ignored;
the application uses Modern docking for every workspace.

Connecting an organisation
--------------------------

Library Sync uses **Local Cloud Storage**. Opal reads and writes the selected
folder on this computer; the desktop storage app handles syncing and sharing.
No API credentials or cloud API setup are required.

1. One team member creates a folder in their cloud storage app and shares it with
   the team. Give contributors editing permission.
2. Each team member syncs the shared folder to their computer using the desktop
   storage app. Make it available offline when needed without an internet connection.
3. In Cloud Library, choose **Set up connection**, or
   **Connection → Set up connection**. Select **Local Cloud Storage** and enter
   a unique library name.
4. Choose **Next**, then **Browse…** and select the shared folder on this computer.
   Each computer selects its own synced copy; the folder paths can differ.
5. Review the location and choose **Save library**. Opal opens the folder
   automatically and remembers it across restarts. Connect is disabled for local storage.

Choose **Connection → Edit library…** to rename the library or select another
folder. Choose **Connection → Remove library…** to clear its setup from Opal.
Removing a library keeps its files.
Category navigation is disabled until a library is set up.

An ordinary local folder or a folder synced by another desktop storage app also
works. Use the actual storage folder rather than a filesystem symbolic link.
Opal excludes hidden files and symbolic links within the selected folder.

Uploads and downloads publish complete files. An overwrite requires confirmation
and refuses a stale item. Deleted items are retained under ``.librarysync-trash``
inside the selected folder and can be restored manually.
The desktop storage app handles cloud availability and conflicts between computers.
A completed Opal upload confirms the local write; check the desktop storage app's
sync status before expecting other computers to see it. Opal does not merge
simultaneous changes made on different computers.

Connection-file export is disabled for Local Cloud Storage because folder paths
belong to the current computer. Each computer creates its own connection.
Existing Local Cloud Storage files can still be imported when their path matches
this computer; importing a file does not grant access to the shared folder.
Older direct cloud API connections are no longer supported.

Choose **Connection → Open storage** to open the configured folder in Finder or
Explorer. This action is available while disconnected if a connection is configured.
Connect and Disconnect are disabled for Local Cloud Storage; no sign-in session
is needed.

With no connection configured, Cloud Library displays a Fluent InfoBar with a
**Set up connection** hyperlink. The folder selector is disabled until a
connection is configured. The footer shows the item count on the left and current
status on the right. During a transfer, progress, percentage and **Cancel** share
the middle of this row. Preparation uses an indeterminate progress bar.
The footer matches Library and Themes and keeps the same height during transfers.
**Cancel** is a small, subtle Fluent button. Status messages are kept brief; hover
for full text and error details. Errors and an out-of-date cache use Fluent's
critical text colour.

Browsing and transferring
-------------------------

Cloud Library has the same Fluent selector and list components as Library, with
Songs, Images, Custom Slides, Media, Presentations and Themes. Each section uses
its Library icon colour. Lists show friendly item names, file size and the updated
date. Click **Name** or **Updated** to choose the sort column and click again to
reverse the direction. Newly inserted local Library items keep the selected sort order.

Double-click a cloud folder to open it; the Fluent breadcrumb and **Up** return to
its ancestors. Songs and Custom Slides are flat collections and cannot contain
subfolders. Images, Media, Presentations and Themes can have subfolders. **Refresh**
checks for changes made by other team members. The filter searches the loaded
items in the current folder. **Load more** retrieves another page when a folder
has more than 200 items. Folder listings and previews are cached between application sessions;
**Refresh** always fetches the current folder from the selected storage provider.

Double-click an item or choose **View** to open an independent Fluent window with
maximise, restore and close controls. Closing it stops playback and preview transfers.
Songs and Custom Slides use the native slide renderer and slide list, with item
metadata and a named theme when present. A warning InfoBar identifies a theme that
is not installed. Themes show sample slides using the theme's actual appearance.
Metadata uses Fluent cards, with item details first (including song authors,
copyright and CCLI), file information next, and creation/modification history last.
Values wrap and can be selected and copied; the panel scrolls when needed.
Images and media use the Library inspector; media streams on demand rather than
waiting for a complete download. Images use their original resolution. Presentations
have a resizable slide sidebar with a thumbnail per slide; select a row or use the
arrow keys to view it. PDFs render directly. Other formats use an enabled compatible
presentation application to create a cached PDF preview in the background. Without
one, a warning explains that only the provider's cover is available.
Files with download disabled use the
provider's embedded viewer when its permissions allow it.
View refreshes an out-of-date listing before opening the selected item. A failed
opening gets one refresh and retry; further failures show critical error text.
Opening a View window restores the normal Cloud Library footer status.

The context menu offers **View**, **Add to Library**, **Rename** and **Delete**
for all item types, including Themes. The View window also provides Add to Library,
Rename and Delete. Rename and Delete are disabled when unavailable. Delete moves
items to the local ``.librarysync-trash`` folder. Rename refuses an existing name and file type in the same item type.

Drag cloud items onto the matching local Library tab, in either list or grid view,
or choose **Add to Library**. Drag local Library items into the currently open cloud
folder to share them. If their type differs from the current Cloud Library tab,
the tab switches and uploads go to that type's folder in the selected connection.
The destination's write permission is checked before uploading.
Local/cloud transfers copy and retain their source. Dragging
an existing cloud item into a cloud subfolder moves that item within its type.
Cloud items cannot be moved between types or added to a different local Library type.
The local Themes list and grid support these
transfers too. Themes has an item count, thumbnail slider and list/grid buttons
in its footer.

A read-only
folder disables uploads, and the provider rechecks permissions before writing.
You can navigate into a child folder with different permissions.

Names are compared without case or Unicode presentation differences within the
destination folder. Different folders can contain items with the same name.
Presentations, Media and Images show **File Type** after Name and compare both name
and extension. For example, ``Welcome.pptx`` and ``Welcome.pdf`` can coexist.
Folders stay above files when sorting in either direction.
Other Library types continue to compare titles. Uploading or downloading a duplicate asks whether
to overwrite it. Declining preserves the existing item. A confirmed overwrite
updates the existing record rather than adding a confusing duplicate. Existing
legacy duplicates must be renamed or removed before a replacement can proceed.

File transfers, version checks and package validation run in tracked background
workers. Progress shows the current file and transfer percentage. **Cancel** stops
remaining work; copies already completed are retained. Downloads become visible to
the local importer only after size and version checks succeed.
Partial files are removed. Downloading again follows the same overwrite checks.

Cache and change checks
-----------------------

Saved listings appear without downloading the folder again. While Cloud Library
is visible, it checks the provider for changes every ten seconds and when
returning to the panel. Unrelated changes do not reload the Library.
Changes to files and folders in the selected storage show
**Out of date** in the footer's Fluent critical colour. This warning remains
until the current folder refreshes automatically, at most once every ten seconds.
A small **Refresh** button also allows a manual refresh. Transfers defer automatic
refresh until they finish. Rename, Delete and uploads are
disabled while the listing is out of date or its cached permissions have not yet
been checked. Writes always recheck live permissions and file versions.

Change checks inspect local file metadata. Cloud changes become visible after the
desktop storage app syncs them to this computer.

The cache is separate for each connection and local storage path.
It retains up to 512 MiB across connections and removes the
least recently used files when necessary; files unused for 30 days expire.
Disconnecting removes the current connection cache. Cached content can
still be viewed if a change check fails, with that failure shown in the footer.
Successful uploads also populate the preview cache. Media uses a cached upload
when available and otherwise streams on demand.

Downloaded image, song, Custom Slides, theme and presentation previews are reused
only for the same item version. Active View windows use temporary copies, so cache
eviction cannot remove files they are currently displaying.

Remote organisation
-------------------

Uploading at the shared root creates these item-type folders as needed::

    Organisation Library/
        Songs/
            Amazing Grace.xml
        Custom Slides/
            Welcome.xml
        Images/
            Sunday background.png
        Media/
            Opening video.mp4
        Presentations/
            Weekly notices.pptx
        Themes/
            Organisation theme.opal-theme

Songs use OpenLyrics. Custom Slides retain their title, credits and design in
native Opal song and slide packages. Legacy XML and ``.osz`` packages remain readable.
Images, media and presentations retain their original file format. Themes use native
portable theme packages. Bible items are excluded. Friendly titles are retained in
filenames and local records; managed download directories keep internal IDs
outside the user-facing filenames.

Existing files can be organised into these folders without using the application.
Ordinary images, media and presentations are recognised by extension even outside
an item-type folder. Native song/custom XML should be placed in its corresponding
folder. Supported nested folders inherit their item type. Upload directly into a type folder
to avoid creating another category level.

Transfers write temporary files before publishing complete copies. Confirmed
replacements, renames, moves and deletion check the current local file version;
a change observed on this computer stops the operation and requests a refresh.
This protects local writes, but does not lock files on other computers while the
desktop storage app syncs. Check its conflict reports after concurrent edits.

Connection file format
----------------------

Saved connection settings have a versioned envelope containing the name and a compressed,
Base64-encoded payload. Imports bound both the file size and decoded payload to
64 KiB and validate its contents before use. The payload is **not encrypted**.
The wizard creates one named connection to one local folder. This example shows
the decoded configuration::

    {
      "version": 1,
      "provider": "local-cloud",
      "name": "Organisation Library",
      "path": "/path/to/synced/Organisation Library"
    }

Plain version-1 Local Cloud Storage configuration files remain importable.
Imported and stored profiles use the same encoded format. Unknown fields,
including credentials, are excluded by validation.

Adding a provider
-----------------

``CloudProvider`` in ``opal/plugins/librarysync/lib/provider.py`` defines the
account cache identity, change cursor/feed, folder, paged listing, name lookup,
preview, streaming, download, upload, rename,
move and deletion operations. Return ``CloudItem``
records with the current user's capabilities. Register a provider factory in
``worker.PROVIDERS`` (the factory receives the profile and a cancellation event)
and a ``storage_url(profile, folder)`` function in ``worker.STORAGE_URLS`` to
return its browser URL or local folder URI without signing in or making API calls.
Keep both implementations in the provider module, and add its profile validation
and connection flow. Providers
own authentication and their network sessions; the browser and native Library
importers do not need provider-specific transfer logic. New providers must keep
writes independent or atomic and must honour cancellation and permission checks.

Validation
----------

Run the feature and integration checks with::

    python -m pytest tests/openlp_plugins/librarysync tests/openlp_core/ui/test_mainwindow.py \
        tests/openlp_core/ui/test_library.py tests/openlp_core/lib/test_pluginmanager.py

For a release, test the selected synced folder on supported operating systems,
including the desktop storage app with two team accounts, read-only access,
offline files, a large video, cancellation and concurrent uploads. Automated tests
exercise local files and simulated provider responses; they do not establish that
a desktop storage app has completed cloud synchronisation.
