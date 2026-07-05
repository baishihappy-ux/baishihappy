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
- Optional: PyInstaller, only if building the Python/Tk developer authorizer executable.

## Clone And Prepare

```powershell
git clone <public-repository-url> workspace-snapshot
cd workspace-snapshot
npm install --prefix electron
```

The repository stores source and recovery context. Runtime data, local secrets, generated licenses,
logs, output, build artifacts, and customer data are intentionally excluded.

## Run The Client UI From Source

```powershell
npm --prefix electron start
```

The client UI is a runtime mirror. It reads runtime state, events, logs, and configuration.
It must not implement provider routing, parsing, scheduling, or authorization logic directly.

## Run The Developer Authorizer From Source

Use the Electron installed under `electron/node_modules`:

```powershell
.\electron\node_modules\.bin\electron.cmd .\tools\authorizer_electron
```

The developer authorizer must open with a password gate before showing the authorization generator.

Required behavior:

- Password gate is present.
- Password is required before generation.
- 3rd wrong password locks for 10 minutes.
- 4th wrong password locks for 30 minutes.
- 5th wrong password locks for 2 hours.
- 6th and later wrong password locks for 24 hours.

## Build Or Refresh Developer Authorizer

If an Electron distribution template already exists, refresh its app payload:

```powershell
.\electron\node_modules\.bin\asar.cmd pack .\tools\authorizer_electron .\dist\DeveloperAuthorizer\resources\app.asar
```

If building the Python/Tk fallback authorizer:

```powershell
python -m pip install pyinstaller
pyinstaller DeveloperAuthorizer.spec
```

Large executable artifacts should not be committed to normal Git history. If a downloadable binary
is needed, publish it as a release attachment instead of committing `dist/`.

## Customer Package Checklist

Before preparing a customer package:

- Confirm the public source has no API token, customer data, local paths, runtime logs, runtime output, or license files.
- Confirm runtime config uses public-safe defaults.
- Confirm provider credentials enter through authorization, not source code.
- Confirm developer authorizer and client UI are separate tools.
- Confirm the client creates `license.dat` only after a valid authorization code is applied.
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
