# Project Ground Truth

This file is the persistent source of truth for this workspace.
Read it before behavior-sensitive code changes.

## Evidence Priority

Use this order when deciding behavior:

1. Real runtime state, logs, and output samples supplied with the workspace.
2. `runtime/config/app_config.json`.
3. `runtime/state/*.json`.
4. `runtime/output/*`.
5. Current reconstructed source code.
6. Chat history.

Chat history is not reliable for runtime behavior. Verify from files whenever possible.

## Public Repository Rules

- Keep `README.md` generic.
- Do not put secrets, machine codes, license data, customer records, phone-like values, local absolute paths, or target-site names in public documentation.
- Do not commit runtime secrets or generated runtime data.
- Keep `.gitignore` excluding license files, logs, output, runtime state, build artifacts, dependency folders, and temporary files.
- Before each public push, scan public documentation for secrets, phone-like values, and target-site names.
- Use fixed push terminology:
  - "force push" means overwrite GitHub history and leave only the current public snapshot on `main`.
  - "normal push" means preserve history, append a commit, and add/update a version note under `docs/versions/`.
- Keep the local working tree and GitHub publishing tree isolated. Public-only edits must be made in a temporary worktree or temporary publish directory, not directly in the sensitive local workspace unless explicitly requested.
- Every GitHub-published version of the developer authorization tool must keep the password gate and failed-password lockout policy.
- Every GitHub-published version must use the small Python native developer authorization tool as the developer authorizer. Do not publish or rely on the Electron developer authorizer.
- Developer authorization lockout policy: 3rd wrong password locks 10 minutes, 4th locks 30 minutes, 5th locks 2 hours, 6th and later locks 24 hours.
- Public GitHub snapshots are generic editions. They must not contain product-specific branding strings, product-specific English identifiers, product-specific Chinese names, or product logo assets in Electron UI, authorization UI, docs, package metadata, filenames, buttons, icons, titles, or recovery notes.
- Before pushing to GitHub, automatically run the public upload checklist: verify push mode, use an isolated publish tree, check required authorizer lockout, run privacy scans, check ignored files, run syntax checks, verify public config recovery, update version docs when needed, inspect `git status`/diff, push, confirm remote hash, and remove the temporary publish tree.
- Separate local memory from public recovery:
  - `LOCAL_*.md` and `PRIVATE_*.md` may exist on this machine with full evidence.
  - public tracked docs must stay generic and searchable-safe.

## Runtime Rules

- `runtime/config/app_config.json` is the primary parameter source.
- Runtime hot tuning is disabled unless explicitly re-enabled.
- Do not infer control behavior from architecture names alone.
- Do not invent control logic that is not visible in runtime data or current code.
- Provider tiers must remain isolated:
  - Tier A: stable direct provider, no control brain, no session pool.
  - Tier B: semi-managed provider, light retry/fallback only.
  - Tier C: unstable provider path, may use control/session feedback.

## Recovery Rules

- Completed records are terminal.
- Final discard records are terminal.
- Claimed but unfinished records are recoverable.
- Pause stops new seed claiming while allowing active work to drain.
- Resume clears pause state and allows new claims.
- Unexpected-close recovery must use cursor/pending state, not only queue depth.

## Codex Continuity

When restoring from GitHub:

1. Read this file.
2. Read `WORKLOG.md`.
3. Inspect relevant source files before answering behavior questions.
4. Treat any missing runtime samples as unknown rather than guessing.


