# Opal Presenter

Opal Presenter is free, open-source presentation software for churches and worship
teams. Prepare a service with song lyrics, Bible passages, slides, images and
media, then present it from one workspace. Separate Preview and Live panels let
the operator prepare the next item while the current item stays on screen.

Built on the OpenLP project, Opal Presenter adds a Fluent interface and visual
slide design. Its Library Sync feature lets you upload and download library items
to and from cloud storage.

[Download releases](https://github.com/tbc-productions/opal-presenter/releases)
· [Source code](https://github.com/tbc-productions/opal-presenter)
· [Report an issue](https://github.com/tbc-productions/opal-presenter/issues)

## Main features

- **Songs and Bible passages:** organise a searchable song library, edit lyrics
  and verse order, import songs and Bibles, and display scripture readings.
- **Service planning:** arrange songs, readings, presentations and media in a
  service order; save it for reuse and move between items during a service.
- **Slide and theme design:** customise fonts, colours and backgrounds; add text,
  shapes, images and looping video to visual layouts; reuse themes across items.
- **Presentations and media:** show PDF documents, images, audio and video, with
  additional presentation support through compatible installed applications.
- **Operator workspace:** use dockable panels, workspace presets, light and dark
  appearance, keyboard shortcuts, and separate preview and live controls.
- **Remote and stage views:** control a service and open stage, live and chords
  views through a browser on the local network.
- **Library Sync:** upload and download songs, presentations, images, media,
  custom slides and themes to and from a local or synced folder. Your desktop
  storage app handles syncing and sharing.
- **Portable documents:** bundle services, songs, custom slides and themes in
  native Opal packages; import OpenLP files and export content to formats
  including OpenLyrics, PPTX, ODP, PDF and images.
- **Optional integrations:** import Planning Center service plans, control OBS
  Studio scenes and manage compatible PJLink projectors.

## Requirements

### To use the application

- A Windows, macOS or Linux computer. Check the selected release for available
  builds, supported operating system versions and processor architecture.
- A projector or second display for audience output. A single screen can be used
  to prepare and preview a service.
- Audio output if your service uses audio or video sound.
- Internet access for downloads and online integrations; local content can be
  prepared and presented offline. Browser remotes need network access to the
  presenter computer.

Some features need additional software or configuration:

- **Presentations:** native presentation control needs a compatible presentation
  application, such as Microsoft PowerPoint or LibreOffice Impress. Availability
  varies by platform.
- **Library Sync:** uploads and downloads need a folder available on the computer.
  For shared libraries, sync the folder using your desktop storage app. No cloud
  API setup or credentials are required. See the
  [Library Sync guide](documentation/library-sync.md).
- **Planning Center:** service plan imports need account credentials.
- **OBS Studio:** scene control needs OBS Studio and its Advanced Scene Switcher
  plugin.
- **Projectors:** projector control needs a reachable PJLink-compatible projector.

### To run from source

- **Python 3.14** (`>=3.14,<3.15`).
- Git and pip, plus a C++ compiler for the native interface build.
- Matching **Qt C++ SDK, PySide6 and Shiboken 6.11.1**, with CMake and Ninja.
- Opal Presenter's pinned FluentQt wheel, built using
  [the FluentQt build guide](documentation/fluentqt.md).
- ICU development libraries and `pkg-config` on macOS/Linux for PyICU, plus any
  platform prerequisites needed by the dependencies in [pyproject.toml](pyproject.toml).

Packaged releases include the Python and Qt runtime; these source-build
requirements apply when running a checkout yourself.

## Installation

### Install a packaged release

1. Open the [releases page](https://github.com/tbc-productions/opal-presenter/releases)
   and choose a release with a build for your computer. Source-code archives are
   intended for the source installation below.
2. Follow the release notes and install the appropriate package:
   - **Windows:** run the `.msi` installer, or use the portable build if provided.
   - **macOS:** open the `.dmg` and copy Opal Presenter to Applications. The macOS
     build is not signed with an Apple Developer ID, so macOS may report that the
     app is damaged and cannot be opened. After copying it, open Terminal and run:

     ```sh
     xattr -dr com.apple.quarantine "/Applications/Opal Presenter.app"
     ```

     This removes the download quarantine from Opal Presenter only. Use it for
     the app downloaded from the releases page above, then open the app from
     Applications. If Terminal reports a permission error, run the same command
     with `sudo` before `xattr` and enter your Mac administrator password.
   - **Linux:** use the Flatpak package if provided, following that release's instructions.
3. Start Opal Presenter and follow the **Set up Opal Presenter** wizard to choose
   features and the audience display. You can also import an existing OpenLP
   library during setup (see below). Add your songs, Bibles and media to the
   Library, build a service and preview an item before sending it live.

Build availability can differ between releases. If there is no package for your
platform, use the source instructions below.

### Run from source

1. Clone the repository:

   ```sh
   git clone https://github.com/tbc-productions/opal-presenter.git
   cd opal-presenter
   ```

2. Create and activate a Python 3.14 virtual environment.

   On macOS/Linux:

   ```sh
   python3.14 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows, in Command Prompt:

   ```bat
   py -3.14 -m venv .venv
   .venv\Scripts\activate.bat
   ```

3. Follow the [FluentQt build guide](documentation/fluentqt.md) to install the
   matching build tools and Qt SDK, then build and install the pinned wheel in
   this environment. Windows builds need an MSVC developer terminal. Complete
   this step before installing Opal Presenter; the standard upstream FluentQt
   wheel does not satisfy this project's dependency.

4. Install the application and start it:

   ```sh
   python -m pip install --upgrade pip
   python -m pip install -e .
   opal-presenter
   ```

   You can also start it with `python run_opal_presenter.py` from the repository root.

   The Python package is `opal`; `python -m opal` also starts the application.
   Reinstall editable installations after updating from the former `openlp` package.

Optional source-install extras include `spellcheck` and `sword-bibles`. For
example, `python -m pip install -e ".[spellcheck,sword-bibles]"` installs both;
spell checking also needs the system Enchant library.

## Existing OpenLP users

You can import an OpenLP library through the first-time setup wizard:

1. In OpenLP, choose **Tools → Open Data Folder** to find your library folder,
   then close OpenLP.
2. In Opal Presenter's **Set up Opal Presenter** wizard, go to **Import existing
   data**, select **OpenLP** under **Import from**, and choose that folder under
   **Library folder**.
3. Choose **Finish setup** to copy the library into Opal Presenter. The original
   OpenLP library is kept unchanged.

If you have already completed setup, choose **Tools → Re-run First Time Wizard**.
Opal Presenter will restart after importing the library through this menu.

OpenLP services, songs, custom slides, themes and settings can also be imported
individually; new saves use Opal formats. See the
[document compatibility guide](documentation/opal-formats.md) for details.

## Documentation and licence

- [Slide Designer](documentation/slide-designer.md)
- [Library Sync](documentation/library-sync.md)
- [Opal document formats and compatibility](documentation/opal-formats.md)
- [Source build: FluentQt](documentation/fluentqt.md)
- [Windows packaging](documentation/windows-packaging.md)
- [Upstream OpenLP documentation](https://wiki.openlp.org/) for shared functionality;
  Opal-specific behaviour may differ.

Opal Presenter is licensed under the
[GNU General Public License, version 3 or later](LICENSE). It builds on the work
of the OpenLP developers and contributors.
