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

An administrator performs the Google setup once:

1. Create a Google Cloud project and enable the Google Drive API.
2. Configure the OAuth consent screen and its audience. Create a **Desktop app**
   OAuth client and download its JSON configuration. Do not use a service account
   or a Web application client.
3. In Cloud Library, choose **Connection → Set up connection**. Select a supported
   cloud provider and enter a unique connection name. Names are compared without
   case or leading/trailing spaces. Select **Google Drive** for the API connection.
4. Choose **Next** to configure Google Drive. Enter the Client ID and Client secret,
   or choose **Load client JSON**, then paste the shared folder link or folder ID.
   The secret is masked on screen. Links with a resource key are supported. The
   folder can be in My Drive or a Google Workspace shared drive.
5. Leave **Export a connection file for the team** checked, then choose **Save connection**
   and a file location. The chosen name is included in the file and the folder selector.
6. Choose **Connect** and complete Google sign-in in the system browser to check access.
   Share the exported file with the team. **Connection → Export connection file** can
   export it again later.

For storage without API credentials, choose **Local Cloud Storage** on the first
wizard page. Choose **Next**, then browse to an existing folder on this computer.
A local or synced folder works. Review the location and choose **Save connection**,
then **Connect**.
Export is off by default because folder paths belong to the current computer.
Each computer should create its own connection pointing to its synced copy.

Local Cloud Storage uses the same Songs, Presentations, Images, Media, Custom
Slides and Themes folders as Cloud Library. Uploads and downloads publish complete
files; an overwrite requires confirmation and refuses a stale item. Deleted items
are retained under ``.librarysync-trash`` inside the chosen folder and can be
restored manually. Hidden files and symbolic links are excluded. The desktop
cloud storage app handles availability, syncing, sharing and conflicts between
computers. Local writes are not confirmed as synced to the cloud.

For Google Drive, each team member chooses **Connection → Import connection file**,
then **Connect**, and signs in with their own Google account. Existing Google folder permissions
determine what that account can download and upload. Sharing the connection file
does not grant access to the organisation folder.
The connection and account are remembered across restarts. Starting the application
uses the saved account and renews its token when necessary without opening a browser.
Reconnecting is necessary if Google revokes or expires the account's authorisation.
Disconnect asks for confirmation before closing previews and clearing the local
cache. Export connection and Disconnect are unavailable while disconnected.

Choose **Connection → Open storage** to open the selected shared Google Drive
folder in your browser, or the configured local storage folder in Finder or
Explorer. This action is available while disconnected if a connection is configured.

With no connections configured, Cloud Library displays a Fluent InfoBar with an
**Import connection** hyperlink. Connect and the folder selector are disabled
until a connection is imported. The footer shows the item count on the left and
current status on the right. During a transfer, progress, percentage and **Cancel**
share the middle of this row. Preparation uses an indeterminate progress bar.
The footer matches Library and Themes and keeps the same height during transfers.
**Cancel** is a small, subtle Fluent button.
Upload percentages update as bytes are sent and reach 100% when Drive confirms
completion. Status messages are kept brief; hover for full text and error details.
Errors and an out-of-date cache use Fluent's critical text colour.

The portable file contains the Desktop OAuth application configuration and folder
references. It never contains personal access tokens, refresh tokens, passwords,
service-account keys or an API key. Exported files and stored connection settings
use an obfuscated payload so Client ID and Client secret are not shown as plain
text. This is reversible concealment, not confidentiality: any installation can
decode the payload. Google Desktop clients are public clients. The connection
name stays readable so people can identify a shared file.
Each user's sign-in is held in the operating system's credential store: Keychain
on macOS, Windows Credential Locker, or Secret Service/KWallet on Linux. Library
Sync refuses plaintext credential backends. **Disconnect account** removes the
local sign-in; access can also be revoked in the user's Google account.

This first provider requests the ``drive`` OAuth scope to browse existing shared
folders and copy their contents. Google classifies it as a restricted scope. The
administrator must satisfy Google's applicable consent and verification policies;
Workspace organisations can configure an internal audience where appropriate.
External projects in Testing issue refresh tokens that expire after seven days.
``drive.file`` is narrower, but requires granting the app access to existing files
through a picker; importing a shared folder ID alone does not do that.

Google's primary documentation:

* `Desktop OAuth and PKCE <https://developers.google.com/identity/protocols/oauth2/native-app>`_
* `Drive scopes <https://developers.google.com/workspace/drive/api/guides/api-specific-auth>`_
* `Refresh token expiration <https://developers.google.com/identity/protocols/oauth2#expiration>`_

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
items to the cloud bin. Rename refuses an existing name and file type in the same item type.

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

Network operations, checksum work and package validation run in tracked background
workers. Progress shows the current file and transfer percentage. **Cancel** stops
remaining work; copies already completed are retained. Downloads become visible to
the local importer only after size, version and available checksum checks succeed.
Partial files are removed. Downloading again follows the same overwrite checks.

Cache and change checks
-----------------------

Saved listings appear without downloading the folder again. While Cloud Library
is visible, it checks the provider for changes every ten seconds and when
returning to the panel. Unrelated changes do not reload the Library.
Relevant additions, edits, moves, removals and shared-drive access changes show
**Out of date** in the footer's Fluent critical colour. This warning remains
until the current folder refreshes automatically, at most once every ten seconds.
A small **Refresh** button also allows a manual refresh. Transfers defer automatic
refresh until they finish. Rename, Delete and uploads are
disabled while the listing is out of date or its cached permissions have not yet
been checked. Writes always recheck live permissions and file versions.

Read the `Drive changes API documentation
<https://developers.google.com/workspace/drive/api/reference/rest/v3/changes/list>`_
for the incremental cursor and shared-drive options used here.

The cache is separate for each connection and account sign-in and contains no
OAuth credentials. It retains up to 512 MiB across connections and removes the
least recently used files when necessary; files unused for 30 days expire.
Disconnecting removes the current connection/account cache. Cached content can
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
Drive metadata and local records; managed download directories keep internal IDs
outside the user-facing filenames.

Existing files can be organised into these folders without using the application.
Ordinary images, media and presentations are recognised by extension even outside
an item-type folder. Native song/custom XML should be placed in its corresponding
folder. Supported nested folders inherit their item type. Upload directly into a type folder
to avoid creating another category level.

Uploads use resumable sessions. Confirmed replacements, renames, moves and deletion
check the current file version and use an HTTP version precondition. A change made
by another user causes the operation to stop and request a refresh; a missing
version lock also prevents writes. Interrupted chunks resume within the same session.
Refresh before retrying an upload whose final response was lost; it may have completed.
Browsing and new uploads use Drive v3. Conditional mutations use Drive v2's file
ETag and its update endpoints, since the v3 metadata response does not supply that
lock. See Google's `file metadata <https://developers.google.com/workspace/drive/api/reference/rest/v2/files>`_
and `content updates <https://developers.google.com/workspace/drive/api/reference/rest/v2/files/update>`_.

New uploads check for duplicates before and after creation and retract their own
later copy when a simultaneous creation is detected. Drive itself has no unique-name
constraint, so strict uniqueness across simultaneous creators or changes outside
Opal Presenter would require a shared index. This implementation has no background mirroring
or automatic conflict merging.

Connection file format
----------------------

The exported JSON has a versioned envelope containing the name and a compressed,
Base64-encoded payload. Imports bound both the file size and decoded payload to
64 KiB and validate its contents before use. The payload is **not encrypted**.
The decoded configuration can reference several shared folders; the folder
selector switches between them. The wizard creates one named connection to one
folder. This example shows the decoded configuration::

    {
      "version": 1,
      "provider": "google-drive",
      "name": "Organisation Library",
      "installed": {
        "client_id": "YOUR_DESKTOP_CLIENT.apps.googleusercontent.com",
        "client_secret": "YOUR_DESKTOP_CLIENT_CONFIGURATION"
      },
      "folders": [
        {"id": "SHARED_FOLDER_ID", "name": "Organisation Library", "resource_key": ""}
      ]
    }

Older plain version-1 configuration files remain importable. Imported and stored
profiles are normalised to the obfuscated format; personal tokens are always
excluded. For advanced multi-folder configuration, use ``read_profile`` and
``write_profile`` in ``lib/profile.py`` to edit and re-export the decoded profile.

Adding a provider
-----------------

``CloudProvider`` in ``openlp/plugins/librarysync/lib/provider.py`` defines the
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

For a release, test against real Google accounts with reader and writer permissions,
including a shared drive, token renewal, a large video, cancellation and concurrent
uploads. Automated tests use simulated Google responses and do not establish that
a particular organisation's Google Cloud project or account policies are configured correctly.
