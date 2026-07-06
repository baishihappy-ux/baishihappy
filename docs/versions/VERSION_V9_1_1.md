# Version: V9.1.1

## Purpose

Checkpoint the working client, authorization, runtime, and packaging changes after live runtime validation.

## Changes

- Reconnected the packaged client UI to the current source engine authorization path.
- Added current-source engine packaging through `scripts/build_engine.ps1`.
- Removed the hot-tuning client UI and backend IPC path from the active client.
- Fixed authorization status normalization for success, concurrency, and remaining-days display.
- Made packaged client starts use live provider execution instead of dry-run execution.
- Fixed runtime JSON writes with per-file locking and atomic replacement.
- Fixed retry scheduling so retry tasks are allowed to reach final success or final failure.
- Kept the runtime dashboard as a read-only mirror of runtime metrics.

## Verification

- Python compile checks passed for changed engine, provider, and runtime-state modules.
- Electron syntax checks passed for changed main, preload, renderer, and monitor files.
- Local validation package reached the authorized client homepage.
- Runtime validation showed live provider failures recorded as failures rather than fake saved rows.

## Public Restore Notes

This is a generic public recovery snapshot. Public GitHub snapshots must not include product-specific branding, product-specific logos, secrets, customer data, local paths, runtime state, or generated output.


