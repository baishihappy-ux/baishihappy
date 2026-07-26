# Version: Initial Recovery Snapshot

## Purpose

Initial public recovery snapshot of the reconstructed workspace.

## Included

- Python engine source tree.
- Electron UI source tree.
- Developer authorization utility source.
- Runtime config template.
- Generic recovery documentation.

## Excluded

- Runtime license file.
- Runtime logs.
- Runtime output.
- Runtime state.
- Dependency folders.
- Build artifacts.
- Secrets.
- Customer records.

## Verification

- Python compile checks passed for key engine modules.
- Electron syntax checks passed for key UI modules.
- Provider tier boundary checks passed.
- Parser smoke checks passed.

## Restore Notes

This historical instruction is superseded by `docs/唯一恢复方式.md`. Use the public GitHub ZIP and root recovery entry, then read `PROJECT_GROUND_TRUTH.md` and `WORKLOG.md` before making behavior-sensitive changes.
