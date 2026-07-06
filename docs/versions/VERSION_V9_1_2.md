# Version: V9.1.2

## Purpose

Checkpoint the local follow-up fixes for direct CLI execution, T/P offline page handling, and packaged gender lookup data.

## Changes

- Fixed direct execution for the Python engine entrypoint.
- Added a direct JSON CLI entrypoint for the runtime analyzer.
- Calibrated T/P page handling so phone-search listing pages enqueue detail pages without exporting fake records.
- Kept detail pages and Possible Associates pages exportable as records.
- Added fast local first-name gender lookup using `_gender_map.js` with cached in-memory lookups.
- Bundled `_gender_map.js` into packaged engine output so each customer package carries its own gender lookup data.
- Updated engine packaging to fail fast when the gender map asset is missing.

## Verification

- Python compile checks passed for changed parser, engine, runtime CLI, and utility modules.
- Electron syntax checks passed for main, preload, and renderer files.
- Direct runtime analyzer execution, module execution, source engine `analyze-run`, and packaged engine `analyze-run` passed against the local validation customer package.
- T/P offline HTML samples passed page classification checks.
- Runner simulation confirmed listing pages queue detail tasks without result rows and detail pages export records.
- Gender lookup sample checks returned `M/100` and `F/0`.
- Cached gender lookup benchmark completed 10,000 lookups in under 10 ms.
- Packaged engine and customer package `_gender_map.js` hashes matched the source gender map.

## Restore Notes

This is a local recovery checkpoint. GitHub publishing is intentionally deferred. If a public snapshot is requested later, run the public upload checklist from `PROJECT_GROUND_TRUTH.md`.
