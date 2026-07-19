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
- Use fixed push terminology:
  - Strong/force push: overwrite GitHub history and leave only the current public snapshot on `main`.
  - Normal push: preserve GitHub history and append a commit.
- Keep the sensitive local workspace isolated from the GitHub publishing workspace. Public-only changes should be prepared in a temporary worktree or publish directory, then pushed and cleaned up.
- Every GitHub-published developer authorization tool must retain password `88888888` and the failed-password lockout policy.
- The developer authorization tool standard is a small Python native Windows tool. The Electron developer authorizer is not the publishing standard because it creates very large runtime bundles.
- Public GitHub snapshots are generic recovery editions. They must not include product-specific branding strings, product-specific Chinese names, product-specific English identifiers, or product logo assets anywhere in UI, docs, package metadata, filenames, buttons, icons, titles, or generated recovery notes.
- Failed-password lockout policy:
  - 3rd wrong password: 10 minutes.
  - 4th wrong password: 30 minutes.
  - 5th wrong password: 2 hours.
  - 6th and later wrong password: 24 hours.
- Before any GitHub upload, automatically run the upload checklist:
  - confirm force push or normal push
  - create/use an isolated publish tree
  - confirm authorizer password and lockout logic
  - scan for secrets, customer data, target names, phone-like values, local paths, license data, logs, output, and runtime state
  - confirm ignored local-only files stay untracked
  - run Python and Electron syntax checks
  - verify public config can restore required source behavior
  - add/update version documentation when preserving history
  - inspect `git status` and diff before commit
  - push, confirm the remote hash, and remove the temporary publish tree
- For each meaningful future commit, add or update a version note describing:
  - commit purpose
  - touched modules
  - verification performed
  - restore notes

## V9.1.1 Local Restore Point

- Reconnected the packaged client UI to the current source engine authorization path.
- Restored the black/gold runtime dashboard client UI while keeping the developer authorization tool separate.
- Removed the hot-tuning client and backend IPC path from the active client.
- Fixed authorization field normalization for `valid`, `max_instances`, and `remaining_days`.
- Made packaged client starts use live provider mode rather than dry-run mode.
- Added current-source engine packaging with `scripts/build_engine.ps1`.
- Fixed runtime JSON writes to use per-file locking and atomic replacement.
- Fixed retry scheduling so retry tasks are not skipped by an early empty-queue stop.
- Rebuilt and replaced the current-source engine in the local validation customer package.

## V9.1.2 Local Follow-up

- Fixed direct script execution for the Python engine entrypoint and runtime analyzer CLI.
- Rebuilt and replaced the customer package engine after the CLI entrypoint fix.
- Calibrated T/P offline HTML handling: phone-search listing pages now queue detail links without writing result rows, while detail and associate pages remain exportable records.
- Added fast local first-name gender lookup using `_gender_map.js`: returns `M/100` or `F/0` without per-record SSA count aggregation.
- Engine packaging now bundles `_gender_map.js` under the packaged engine internal directory so every customer package carries the gender lookup data.

## Current-Source Black/Gold Authorization Closure

- Confirmed that the active monolithic renderer is the accepted black/gold client and includes its own authorization screen.
- Identified the incorrect blue window as a packaged `app.asar` embedded inside the project's Electron dependency tree, not as the current renderer source.
- Isolated source preview under ignored `.tmp_dev_electron/` and made the Windows launcher reject a development runtime containing packaged `app.asar`.
- Permanently deleted the contaminated `electron/node_modules/` runtime, including its packaged blue archive and backup, after stopping only processes launched from that exact path.
- Kept the current `electron/main.js`, `electron/preload.js`, black/gold renderer, current `python/main.py`, DF9 Ed25519 authorization, and restored T1 engine on one source path.
- Removed the inactive modular blue renderer files from the active source tree.
- Fixed 64-bit Windows ctypes declarations in the source developer authorizer; the visible four customer fields remain unchanged.
- Automated verification: 66 unit tests passed, including T1 identity flow, 502 handling, interruption recovery, 160-session/32-inflight separation, DF9 signature checks, and development-entry isolation.
- Manual verification completed with the user:
  - opened the source developer authorizer;
  - generated a DF9 authorization code;
  - activated the source black/gold client;
  - entered the black/gold home page;
  - closed and restarted the client;
  - confirmed authorization was recognized without entering the code again.
- No customer package was built, no remote Git push was performed, and no live provider request was made.

## Next Plan After Authorization Milestone

1. Preserve this milestone as a local Git checkpoint after secret/runtime-data scanning.
2. Continue source-only runtime acceptance from the black/gold client using offline fixtures.
3. Validate UI controls against the restored T1 runtime state, pause/resume flow, and exported test data.
4. Perform a live provider run only after explicit authorization and with a deliberately bounded request budget.
5. Package a customer build only after explicit packaging approval.
