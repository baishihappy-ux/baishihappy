# Worklog

This file keeps enough context to restore the workspace after a machine loss.
It intentionally avoids public-facing product names, target-site names, secrets, customer records, local absolute paths, and phone-like values.

## Baseline Reconstruction

- Created a Python engine source tree with provider, parser, queue, export, auth, network, session, utility, and runtime-control modules.
- Created an Electron UI source tree with main/preload/renderer services and dashboard panels.
- Copied runtime configuration semantics into `runtime/config/app_config.json`.
- Disabled hot tuning as an active control source.
- Added persistent recovery context in `PROJECT_GROUND_TRUTH.md` and this worklog.

## Provider Boundary

- Implemented three provider tiers:
  - Tier A: stable direct API provider.
  - Tier B: semi-managed providers with light retry/fallback.
  - Tier C: unstable provider path with optional control/session behavior.
- Ensured Tier A bypasses:
  - control brain
  - session pool
  - heavy retry loop
  - fallback chain
- Control brain remains scoped to Tier C only.

## Runtime Scheduler

- Added multi-worker execution.
- Added shared in-flight counting.
- Added stage release gating for entry/result/detail/related stages.
- Added startup, ramp, cruise, brake, and circuit-breaker state tracking.
- Added stale run-lock recovery for unexpected close.

## Input Pool And Recovery

- Added dual-input-aware input pool state.
- Added cursor, pending, and summary state files.
- Preserved compatibility state files for cursor, claims, and distribution.
- Implemented pause-close recovery output.
- Marked completed, final discard, and hard-failed records as terminal.

## Pause And Resume

- Pause writes control state and stops new seed claims.
- Active work is allowed to drain.
- Resume clears pause state across control and pool files.
- Runtime status exposes pause/active/remaining state for the UI.

## Failure Handling

- First retryable gateway-style failure writes a retry record.
- Final repeated gateway-style failure writes the raw record to the final-discard file.
- Final discard records are terminal and are not claimed again after restart.
- Runtime status exposes completed, recovered, failed, active, remaining, and concurrency fields.

## Parser

- Restored T/F/P source-specific parser paths from packaged-engine evidence.
- Parser extracts:
  - contact
  - carrier/type
  - name
  - age
  - region
  - property/equity/occupancy
  - relationship/marital
  - employment
  - education
  - parent/source/depth
- The parser uses source-specific selectors and label rules.
- Real page variants still need runtime HTML samples for final edge-case calibration.

## Engine Module Boundaries

- Added compatibility module boundaries for:
  - source rules
  - parser manager
  - export manager
  - customer privacy
  - challenge detection
  - provider response shim
  - runtime CLI analysis
  - runtime CLI observer
  - remaining-input recovery
  - session-flow wrappers
  - session-pool manager wrapper
- Live provider responses now pass through the provider shim.
- Challenge/block/fake-success pages are classified before parsing.
- Failure masking routes through the privacy module.

## UI

- Electron UI reads runtime state, logs, events, output previews, and license status.
- UI sends start/pause/resume/stop commands.
- UI does not implement provider, parser, scheduler, or control-brain logic.
- Developer authorization tool exists separately from the client UI.

## Verification Performed

- Python compile checks passed for parser, engine, provider, queue, export, runtime CLI, and compatibility modules.
- Electron syntax checks passed for main/preload/renderer files.
- Minimal parser samples passed for T/F/P paths.
- Challenge fake-success detection passed.
- Provider tier boundary test passed for Tier A.
- Runtime analyzer CLI returned a valid status summary.

## Public Git Rules

- Keep `README.md` generic.
- Do not mention product names, target-site names, secrets, sample phone-like values, local absolute paths, or customer data in public-facing documentation.
- Keep full local evidence only in ignored `LOCAL_*.md` or `PRIVATE_*.md` files.
- Keep version notes under `docs/versions/`.
- For each meaningful future commit, add or update a version note describing:
  - commit purpose
  - touched modules
  - verification performed
  - restore notes
