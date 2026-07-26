# Version: Public Privacy Cleanup

## Purpose

Keep the public repository useful for recovery while avoiding searchable operational details.

## Changes

- Public documentation remains generic.
- API source names are represented generically.
- Target-source public config uses placeholders.
- Full local config can be kept in ignored local files.
- Local-only notes should use ignored `LOCAL_*.md` or `PRIVATE_*.md` names.

## Verification

- Scanned tracked documentation and source for direct provider-source names.
- Scanned tracked documentation for phone-like values and local absolute paths.
- Python compile checks passed for changed modules.
- Electron main syntax check passed.

## Restore Notes

This historical note is superseded by `docs/唯一恢复方式.md`. Runtime secrets are not restored from a private source backup; operators re-enter or rotate required credentials outside the public repository before live network use.
