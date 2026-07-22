# Restore And Packaging Guide

This guide is for restoring the workspace from the public repository on a new machine.
It intentionally avoids secrets, customer data, local absolute paths, and target-source names.

## First Read

Before changing code or packaging a customer build, read:

1. `PROJECT_GROUND_TRUTH.md`
2. `WORKLOG.md`
3. `docs/versions/`

These files define the current behavior rules, public repository rules, and recovery context.

## Requirements

- Windows workstation.
- Git.
- Python 3.9+.
- Node.js and npm.
- PyInstaller, for building the small Python developer authorizer executable.
- `cryptography==49.0.0`, installed from `requirements-authorization.txt`.

## Clone And Prepare

```powershell
git clone <public-repository-url> workspace-snapshot
cd workspace-snapshot
npm install --prefix electron
npm install --prefix .tmp_dev_electron --no-audit --no-fund --save=false electron@31.7.7
python -m pip install -r requirements-authorization.txt
```

The repository stores source and recovery context. Runtime data, local secrets, generated licenses,
logs, output, build artifacts, and customer data are intentionally excluded.

## Run The Client UI From Source

```powershell
npm --prefix electron start
```

On Windows, `启动当前源码客户端.cmd` is the fixed double-click development entry. It resolves the
workspace from the launcher's own directory, loads the current `electron/` files, and invokes the
current `python/main.py` engine. Its shared UI/engine runtime root is isolated under ignored
`.tmp_dev_client/runtime/`.
The Electron development runtime is separately isolated under ignored `.tmp_dev_electron/`. The
launcher requires Electron's standard `default_app.asar` and rejects any development runtime that
contains a packaged `app.asar`; this prevents a historical packaged UI from intercepting the source
entry. It must never point to a copied "latest" directory, a historical customer package, or a
packaged engine. Source changes are picked up on the next launch without packaging.

The launcher must pass `.tmp_dev_client/runtime/` as `DINGFENG_RUNTIME_ROOT`. Passing its parent
directory makes Python append another `runtime/` layer while Electron continues reading the parent,
which separates visible UI state from the engine's real configuration, logs, output, and controls.

Do not use `electron/node_modules/electron/dist/resources/app.asar` as a development entry. A prior
local dependency tree had been overwritten by a packaged blue client, so passing a source path to
that executable still launched the packaged UI. That contaminated local dependency tree was
permanently deleted. The isolated development runtime is a hard boundary between source preview and
customer-package archives.

The client UI is a runtime mirror. It reads runtime state, events, logs, and configuration.
It must not implement provider routing, parsing, scheduling, or authorization logic directly.

## Run The Developer Authorizer From Source

```powershell
python .\tools\developer_authorizer.py
```

On Windows, `启动开发者授权程序.cmd` directly executes that same current source file. It must never
start a previously built authorizer executable. Packaging is a separate customer-delivery action,
not a requirement for development preview.

The developer authorizer must open with a password gate before showing the authorization generator.

The visible generator fields and labels remain exactly:

- `Machine Code`
- `Valid Days`
- `Max Windows`
- `Provider Token`

Authorization codes use Ed25519 public-key signatures. The customer engine contains only the public
verification key and rejects all legacy `DF8-` codes. The issuer private key is external to source,
Git, build artifacts, and customer packages.

The local issuer key is stored under `.package-secrets/authorization/` and protected by Windows
DPAPI for the current user. No private-key disaster-recovery backup is required. If that protected
key is lost, generate a new keypair, replace the customer verification key, rebuild the customer
application, and redistribute it. The new application intentionally rejects codes signed by the
lost key.

Required behavior:

- Password gate is present.
- Password is required before generation.
- 3rd wrong password locks for 10 minutes.
- 4th wrong password locks for 30 minutes.
- 5th wrong password locks for 2 hours.
- 6th and later wrong password locks for 24 hours.

## Build Or Refresh Developer Authorizer

The developer authorizer publishing standard is the small Python native Windows tool, not Electron.

```powershell
python -m pip install pyinstaller
.\scripts\build_developer_authorizer.ps1
```

Large executable artifacts should not be committed to normal Git history. If a downloadable binary
is needed, publish it as a release attachment instead of committing `dist/`.

## Customer Package Checklist

Before preparing a customer package:

- Confirm the public source has no API token, customer data, local paths, runtime logs, runtime output, or license files.
- Confirm runtime config uses public-safe defaults.
- Confirm provider credentials enter through authorization, not source code.
- Confirm developer authorizer and client UI are separate tools.
- Confirm the customer engine contains no issuer module, private key, `.package-secrets`, or authorization-code generation command.
- Confirm the client creates `license.dat` only after a valid Ed25519 authorization code is applied.
- Confirm every startup verifies the stored authorization code again and public status output contains no provider token.
- Confirm runtime state and output directories are generated at run time.

## Public Upload Checklist

Before any GitHub upload:

1. Confirm whether the upload is a force push or a normal push.
2. Use an isolated publish tree, not the sensitive local workspace.
3. Confirm developer authorizer password and lockout logic.
4. Scan for secrets, customer data, target names, phone-like values, local paths, license data, logs, output, and runtime state.
5. Confirm ignored local-only files are not tracked.
6. Run Python and Electron syntax checks.
7. Verify public config can restore required source behavior.
8. Add or update version documentation when preserving history.
9. Inspect `git status` and diff before commit.
10. Push, confirm the remote hash, then remove the temporary publish tree.

## Recovery Principle

The public repository should be enough for Codex to recover the source workspace and rebuild tools.
Sensitive runtime evidence may exist locally, but it must stay outside the public repository.
