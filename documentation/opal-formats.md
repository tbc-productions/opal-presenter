# Opal Presenter documents

Opal Presenter 4.0.4 exports its own document formats. OpenLP files remain importable;
opening an OpenLP service leaves the source untouched and its next save asks for an Opal
filename. Automatic repairs remain in memory until saved.

Opal uses independent settings,
data, cache, credentials and installer identities, and does not import an old profile on startup.

## File extensions

| Document | Native extension | Compatible inputs |
| --- | --- | --- |
| Packaged service | `.opal-service` | `.osz` |
| Service with links | `.opal-service-lite` | `.oszl` |
| Song package | `.opal-song` | OpenLyrics XML, song `.osz` |
| Custom slide package | `.opal-slides` | Custom XML, custom `.osz` |
| Theme package | `.opal-theme` | `.otz` |
| Settings backup | `.opal-settings` | `.conf`, settings `.zip` |
| Formatting styles | `.opal-styles` | styles `.json` |
| Library connection | `.opal-connection` | connection `.json` |

## Package structure and validation

Services, songs, slides, themes and settings use ZIP archives. A root `manifest.json`
contains these fields:

- `format: "opal-presenter"`
- `version: 1`
- `type`
- `payload`

The payload
names its existing JSON, XML or INI document. Media retains the existing content-addressed
storage and validation. Package versions are independent of application versions.

Styles and connections use JSON with the same `format`, `version` and `type` fields,
and their existing payload under `data`. Connection credentials remain excluded from
exports; the previous compressed connection payload is retained inside this envelope.

The document types are `service`, `service-lite`, `song`, `slides`, `theme`,
`settings`, `styles` and `connection`.

Before restoring media or settings, readers reject:

- Unsupported versions.
- Wrong kinds of document.
- Missing payloads.
- Unsafe ZIP paths.

OpenLP settings imports retain Opal's profile location.

## XML namespaces and settings compatibility

New XML extensions use:

- `urn:net.tbcproductions.OpalPresenter:slide-design:1`
- `urn:net.tbcproductions.OpalPresenter:library-sync:1`

Readers also accept the OpenLP extension namespaces.

Settings backups declare `OpalPresenter_settings_export`;
`OpenLP_settings_export` remains accepted on import.

## Sharing and exports

Native songs preserve visual designs, theme snapshots and packaged media. For sharing
with another application, choose plain OpenLyrics XML. That option preserves lyrics,
metadata and supported chords, and omits visual designs, theme snapshots and media.
PPTX, ODP, PDF and image exports remain available.

Library Sync writes native Opal packages, reads older cloud files and updates filenames
and document types when replacing an older upload. Importing never rewrites the source.
