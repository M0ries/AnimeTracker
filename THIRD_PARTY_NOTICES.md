# Third-party source notices

The model and generated adapter files in `hive_exporter/lib/` derive from
[Predidit/Kazumi](https://github.com/Predidit/Kazumi), via the existing local
project supplied for this application. They are retained in modified form for
standalone Dart / Hive CE export; their original exact revision was not recorded.
Copyright remains with the original authors and contributors.
Kazumi's GPL version 3 license is included verbatim at `hive_exporter/LICENSE`.
These source notices do not grant a new license to unrelated application code.

The exporter uses hive_ce 2.19.3, downloaded through Dart Pub; dependency source
and caches are not bundled. Its dependency licenses remain with those packages.
No Kazumi logo, application binary, or personal history is bundled.

## Native app runtime added in 2.0

The source package references these dependencies; they are downloaded during
build and are not vendored in this source archive:

- Pyodide (MPL-2.0), https://github.com/pyodide/pyodide
- CPython standard library (Python Software Foundation License), bundled by Pyodide
- SQLite (public domain), bundled by the Python runtime
- Tauri and its official plugins (MIT or Apache-2.0), https://github.com/tauri-apps
- Rust dependencies: consult Cargo.lock and each crate's license metadata.
- fake-indexeddb (Apache-2.0), used only in tests.

Before distributing compiled binaries, retain all required license texts and
notices from these dependency distributions. This source archive does not grant
rights to third-party anime cover images; no cover images are included.
