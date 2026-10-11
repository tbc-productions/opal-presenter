# Library Sync

Library Sync is a bundled plugin for sharing Library items within an organisation.

- **Open:** select Library Sync in workspace navigation or **View → Mode → Library Sync**.
- **Dock layout:** Library and Themes share a dock area, with Library selected, to
  the left of Cloud Library. Each preset retains its own customised Modern layout.
- **Disable:** use Plugin Manager.
- **Appearance:** older Classic layout data is ignored; every workspace uses Modern docking.

On this page:

- [Connecting an organisation](#connecting-an-organisation)
- [Browsing and transferring](#browsing-and-transferring)
- [Cache and change checks](#cache-and-change-checks)
- [Remote organisation](#remote-organisation)
- [Connection file format](#connection-file-format)
- [Adding a provider](#adding-a-provider)
- [Validation](#validation)

## Connecting an organisation

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

### Edit or remove a connection

Choose **Connection → Edit library…** to rename the library or select another
folder. Choose **Connection → Remove library…** to clear its setup from Opal.
**Removing a library keeps its files.**

Category navigation is disabled until a library is set up.

An ordinary local folder or a folder synced by another desktop storage app also
works. Use the actual storage folder rather than a filesystem symbolic link.
Opal excludes hidden files and symbolic links within the selected folder.

### Sync, overwrites and deleted files

Uploads and downloads publish complete files. An overwrite requires confirmation
and refuses a stale item. Deleted items are retained under `.librarysync-trash`
inside the selected folder and can be restored manually.

The desktop storage app handles cloud availability and conflicts between computers.
A completed Opal upload confirms the local write; check the desktop storage app's
sync status before expecting other computers to see it. Opal does not merge
simultaneous changes made on different computers.

### Connection files and older providers

Connection-file export is disabled for Local Cloud Storage because folder paths
belong to the current computer. Each computer creates its own connection.
Existing Local Cloud Storage files can still be imported when their path matches
this computer; importing a file does not grant access to the shared folder.
Older direct cloud API connections are no longer supported.

### Open storage

Choose **Connection → Open storage** to open the configured folder in Finder or
Explorer. This action is available while disconnected if a connection is configured.
Connect and Disconnect are disabled for Local Cloud Storage; no sign-in session
is needed.

### Connection status and progress

With no connection configured, Cloud Library displays a Fluent InfoBar with a
**Set up connection** hyperlink. The folder selector is disabled until a
connection is configured.

The footer matches Library and Themes and keeps the same height during transfers:

- **Left:** item count.
- **Right:** current status.
- **Middle, during a transfer:** progress, percentage and **Cancel**.
- **Preparation:** an indeterminate progress bar.

**Cancel** is a small, subtle Fluent button. Status messages are kept brief; hover
for full text and error details. Errors and an out-of-date cache use Fluent's
critical text colour.

## Browsing and transferring

Cloud Library has the same Fluent selector and list components as Library, with
Songs, Images, Custom Slides, Media, Presentations and Themes. Each section uses
its Library icon colour. Lists show friendly item names, file size and the updated
date. Click **Name** or **Updated** to choose the sort column and click again to
reverse the direction. Newly inserted local Library items keep the selected sort order.

### Folders, search and sorting

Double-click a cloud folder to open it; the Fluent breadcrumb and **Up** return to
its ancestors.

- **Songs and Custom Slides:** flat collections; cannot contain subfolders.
- **Images, Media, Presentations and Themes:** can have subfolders.
- **Refresh:** checks for changes made by other team members.
- **Filter:** searches the loaded items in the current folder.
- **Load more:** retrieves another page when a folder has more than 200 items.

Folder listings and previews are cached between application sessions;
**Refresh** always fetches the current folder from the selected storage provider.

### Preview items

Double-click an item or choose **View** to open an independent Fluent window with
maximise, restore and close controls. Closing it stops playback and preview transfers.

- **Songs and Custom Slides:** use the native slide renderer and slide list, with
  item metadata and a named theme when present. A warning InfoBar identifies a
  theme that is not installed.
- **Themes:** show sample slides using the theme's actual appearance.
- **Images and media:** use the Library inspector. Media streams on demand rather
  than waiting for a complete download; images use their original resolution.
- **Presentations:** have a resizable slide sidebar with a thumbnail per slide;
  select a row or use the arrow keys to view it. PDFs render directly. Other
  formats use an enabled compatible presentation application to create a cached
  PDF preview in the background. Without one, a warning explains that only the
  provider's cover is available.
- **Download disabled:** files use the provider's embedded viewer when its
  permissions allow it.

Metadata uses Fluent cards in this order:

1. **Item details:** including song authors, copyright and CCLI.
2. **File information.**
3. **Creation/modification history.**

Values wrap and can be selected and copied; the panel scrolls when needed.

View refreshes an out-of-date listing before opening the selected item. A failed
opening gets one refresh and retry; further failures show critical error text.
Opening a View window restores the normal Cloud Library footer status.

### Rename and delete

The context menu offers **View**, **Add to Library**, **Rename** and **Delete**
for all item types, including Themes. The View window also provides Add to Library,
Rename and Delete. Rename and Delete are disabled when unavailable. Delete moves
items to the local `.librarysync-trash` folder. Rename refuses an existing name and file type in the same item type.

### Upload, download and move

- **Download:** drag cloud items onto the matching local Library tab, in either
  list or grid view, or choose **Add to Library**.
- **Upload:** drag local Library items into the currently open cloud folder to
  share them. If their type differs from the current Cloud Library tab, the tab
  switches and uploads go to that type's folder in the selected connection.
  The destination's write permission is checked before uploading.
- **Move:** drag an existing cloud item into a cloud subfolder to move that item
  within its type.

Local/cloud transfers copy and retain their source.
Cloud items cannot be moved between types or added to a different local Library type.
The local Themes list and grid support these
transfers too. Themes has an item count, thumbnail slider and list/grid buttons
in its footer.

A read-only folder disables uploads, and the provider rechecks permissions before writing.
You can navigate into a child folder with different permissions.

### Duplicate names and overwrites

- **Name matching:** ignores case and Unicode presentation differences within the
  destination folder. Different folders can contain items with the same name.
- **File type:** Presentations, Media and Images show File Type after Name and compare
  both name and extension. `Welcome.pptx` and `Welcome.pdf` can coexist.
- **Other types:** compare titles.
- **Sorting:** folders stay above files in either direction.
- **Overwrite prompt:** duplicate uploads or downloads ask for confirmation. Declining
  preserves the existing item; confirming updates its record rather than adding a duplicate.
- **Existing duplicates:** rename or remove them before a replacement can proceed.

### Progress and cancellation

- **Background work:** file transfers, version checks and package validation run in
  tracked workers. Progress shows the current file and transfer percentage.
- **Cancel:** stops remaining work; completed copies are retained.
- **Download validation:** the local importer sees files only after size and version
  checks succeed. Partial files are removed.
- **Retry:** downloading again follows the same overwrite checks.

## Cache and change checks

- **Saved listings:** appear without downloading the folder again.
- **Change checks:** run every ten seconds while Cloud Library is visible and when
  returning to the panel. Unrelated changes do not reload the Library.
- **Out of date:** file or folder changes show this warning in the footer's Fluent
  critical colour until the current folder refreshes automatically, at most once
  every ten seconds.
- **Refresh:** a small button allows manual refresh. Transfers defer automatic
  refresh until completion.
- **Writes while stale:** Rename, Delete and uploads are disabled while a listing is
  out of date or cached permissions are unchecked. Writes always recheck live
  permissions and file versions.
- **Cloud visibility:** checks inspect local file metadata. Cloud changes appear
  after the desktop storage app syncs them to this computer.

### Cache limits and preview lifetime

The cache is separate for each connection and local storage path.
Its retention rules are:

- **Size limit:** retain up to **512 MiB** across connections.
- **Eviction:** remove the least recently used files when necessary.
- **Expiry:** remove files unused for **30 days**.
- **Disconnect:** remove the current connection cache.

Cached content can
still be viewed if a change check fails, with that failure shown in the footer.
Successful uploads also populate the preview cache. Media uses a cached upload
when available and otherwise streams on demand.

Downloaded image, song, Custom Slides, theme and presentation previews are reused
only for the same item version. Active View windows use temporary copies, so cache
eviction cannot remove files they are currently displaying.

## Remote organisation

Uploading at the shared root creates these item-type folders as needed:

```text
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
```

### Formats and folder placement

Songs use OpenLyrics. Custom Slides retain their title, credits and design in
native Opal song and slide packages. OpenLP XML and `.osz` packages remain readable.
Images, media and presentations retain their original file format. Themes use native
portable theme packages. Bible items are excluded. Friendly titles are retained in
filenames and local records; managed download directories keep internal IDs
outside the user-facing filenames.

Existing files can be organised into these folders without using the application.
Ordinary images, media and presentations are recognised by extension even outside
an item-type folder. Native song/custom XML should be placed in its corresponding
folder. Supported nested folders inherit their item type. Upload directly into a type folder
to avoid creating another category level.

### Concurrent changes

Transfers write temporary files before publishing complete copies. Confirmed
replacements, renames, moves and deletion check the current local file version;
a change observed on this computer stops the operation and requests a refresh.
This protects local writes, but does not lock files on other computers while the
desktop storage app syncs. Check its conflict reports after concurrent edits.

## Connection file format

Saved connection settings have a versioned envelope containing the name and a compressed,
Base64-encoded payload. Imports bound both the file size and decoded payload to
64 KiB and validate its contents before use. The payload is **not encrypted**.
The wizard creates one named connection to one local folder. This example shows
the decoded configuration:

```json
{
  "version": 1,
  "provider": "local-cloud",
  "name": "Organisation Library",
  "path": "/path/to/synced/Organisation Library"
}
```

Plain version-1 Local Cloud Storage configuration files remain importable.
Imported and stored profiles use the same encoded format. Unknown fields,
including credentials, are excluded by validation.

## Adding a provider

`CloudProvider` in `opal/plugins/librarysync/lib/provider.py` defines account cache
identity, change cursor/feed, folder, paged listing, name lookup, preview, streaming,
download, upload, rename, move and deletion operations.

- **Item records:** return `CloudItem` records with the current user's capabilities.
- **Provider factory:** register in `worker.PROVIDERS`. The factory receives the
  profile and a cancellation event.
- **Storage URL:** register `storage_url(profile, folder)` in `worker.STORAGE_URLS`.
  Return a browser URL or local folder URI without signing in or making API calls.
- **Implementation:** keep both implementations in the provider module and add
  profile validation and the connection flow.
- **Authentication:** providers own authentication and network sessions; the browser
  and native Library importers do not need provider-specific transfer logic.
- **Writes:** keep writes independent or atomic. Honour cancellation and permission checks.

## Validation

Run the feature and integration checks:

```bash
python -m pytest tests/openlp_plugins/librarysync tests/openlp_core/ui/test_mainwindow.py \
    tests/openlp_core/ui/test_library.py tests/openlp_core/lib/test_pluginmanager.py
```

For a release, check the following on supported operating systems:

- **Shared storage:** the selected synced folder and desktop storage app with two team accounts.
- **Access and availability:** read-only access and offline files.
- **Transfers:** a large video, cancellation and concurrent uploads.

Automated tests exercise local files and simulated provider responses. They do not
establish that a desktop storage app has completed cloud synchronisation.
