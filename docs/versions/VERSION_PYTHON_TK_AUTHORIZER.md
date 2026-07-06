# Version: Small Python Developer Authorizer

## Purpose

Make the small Python developer authorizer the only publishing standard and avoid large Electron authorizer bundles.

## Changes

- Removed the Electron developer authorizer source path.
- Kept the client Electron UI unchanged.
- Kept password `88888888` and the failed-password lockout policy in the Python authorizer.
- Replaced the Tk UI dependency with a native Windows UI implemented through Python standard library calls.
- Changed the visible provider credential field to the generic label `Provider Token`.
- Added `scripts/build_developer_authorizer.ps1`.
- Updated restore and packaging documentation to build the Python/Tk authorizer.

## Verification

- Python compile check must pass for `tools/developer_authorizer.py`.
- Built authorizer output should be generated under `dist/DeveloperAuthorizerTk/`.
- Public upload checks must continue to confirm password and lockout behavior.

## Restore Notes

Every future GitHub push, whether force push or normal push, must preserve the small Python developer authorizer standard and failed-password lockout policy.


