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
- Developer authorization form labels remain `Machine Code`, `Valid Days`, `Max Windows`, and `Provider Token`.
- Customer authorization accepts only the Ed25519-signed `DF9-` format; legacy `DF8-` codes are invalid.
- Customer engines contain public verification keys only. Issuer modules, private keys, `.package-secrets`, and authorization generation commands must stay out of customer packages.
- The issuer private key is Windows-DPAPI protected for daily use. No disaster-recovery backup is required; if the key is lost, rotate the keypair, replace the customer public key, rebuild, and redistribute the customer application.
- `license.dat` stores the signed authorization code. Every startup re-verifies signature, machine binding, and expiry; public status responses must never expose the provider token.
- The public GitHub project is the only disaster-recovery source. Project-specific source, UI assets, branding, and build assets required to reconstruct the development and production-build environment must be present in the public ZIP.
- The only formal manual recovery path is GitHub `Code` -> `Download ZIP` -> extract into a new empty folder -> double-click root `恢复生产环境.cmd`.
- Git clone, Git pull, and `.git` metadata are not recovery steps or recovery requirements. Recovery tests and security scans must work against the real GitHub ZIP with no `.git` directory.
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

1. Use only the procedure in `docs/唯一恢复方式.md`.
2. Read this file.
3. Read `WORKLOG.md`.
4. Inspect relevant source files before answering behavior questions.
5. Treat any missing runtime samples as unknown rather than guessing.
