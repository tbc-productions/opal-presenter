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
3. In Cloud Library, choose **Connection → Set up Google Drive** to open the admin
   wizard. Enter the Client ID and Client secret, or choose **Load Google client JSON**.
   The secret is masked on screen.
4. Give the connection a name and paste the shared folder link. Links with a resource
   key are supported. The folder can be in My Drive or a Google Workspace shared drive.
5. Leave **Export a connection file for the team** checked, then choose **Save connection**
   and a file location. The chosen name is included in the file and the folder selector.
6. Choose **Connect** and complete Google sign-in in the system browser to check access.
   Share the exported file with the team. **Connection → Export connection file** can
   export it again later.

Each team member chooses **Connection → Import connection file**, then **Connect**,
and signs in with their own Google account. Existing Google folder permissions
determine what that account can download and upload. Sharing the connection file
does not grant access to the organisation folder.
The connection and account are remembered across restarts. Starting the application
uses the saved account and renews its token when necessary without opening a browser.
Reconnecting is necessary if Google revokes or expires the account's authorisation.

With no connections configured, Cloud Library displays a Fluent InfoBar with an
**Import connection** hyperlink. Connect and the folder selector are disabled
until a connection is imported. The footer shows the item count on the left and
current status on the right. During a transfer, progress, percentage and **Cancel**
share the middle of this row. Preparation uses an indeterminate progress bar;
upload percentages update as bytes are sent and reach 100% when Drive confirms
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
**Refresh** always fetches the current folder from Drive.

Double-click an item or choose **View** to open a Fluent window within OpenLP+.
Songs and Custom Slides use the native slide renderer and slide list, with item
metadata and a named theme when present. A warning InfoBar identifies a theme that
is not installed. Themes show sample slides using the theme's actual appearance.
Images and media use the Library inspector; media streams on demand rather than
waiting for a complete download. Images use their original resolution. Provider thumbnails are used for
presentation covers. Files with download disabled use the
provider's embedded viewer when its permissions allow it.

The context menu offers **View**, **Download**, and, when permitted, **Rename**
and **Delete**. Delete moves items to the cloud bin. Rename refuses an existing
name in the same item type.

Drag cloud items onto the matching local Library tab, in either list or grid view,
or choose **Add to Library**. Drag local Library items into the currently open cloud
folder to share them. Local/cloud transfers copy and retain their source. Dragging
an existing cloud item into a cloud subfolder moves that item within its type.
Cross-type drops are rejected. The local Themes list and grid support these
transfers too. Themes has an item count, thumbnail slider and list/grid buttons
in its footer.

A read-only
folder disables uploads, and the provider rechecks permissions before writing.
You can navigate into a child folder with different permissions.

Names are compared without case or Unicode presentation differences, across the
selected type's subfolders. Uploading or downloading an existing name asks whether
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
is visible, it checks Google's incremental change list every minute and when
returning to the panel. Unrelated Drive changes do not reload the Library.
Relevant additions, edits, moves, removals and shared-drive access changes show
**Out of date** in the footer's Fluent critical colour. This warning remains
until **Refresh** retrieves the current folder. Rename, Delete and uploads are
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
Media playback continues to stream on demand.

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
            Organisation theme.otz

Songs use OpenLyrics. Custom Slides retain their title, credits and design in
native XML. Text items with embedded design media use portable ``.osz`` packages.
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
OpenLP+ would require a shared index. This implementation has no background mirroring
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
and add its profile validation and connection flow. Providers
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
