# Version: GitHub Upload Protocol

## Purpose

Record the accepted GitHub publishing rules and the verified developer authorizer lockout behavior.

## Changes

- Fixed terminology for future uploads:
  - Force push: overwrite GitHub history and leave only the current public snapshot.
  - Normal push: preserve GitHub history and append a commit.
- Documented that local sensitive workspace and GitHub publishing workspace must stay isolated.
- Documented the required public upload checklist.
- Reconfirmed developer authorizer password gate and failed-password lockout policy.

## Verification

- Developer authorizer lockout behavior was manually accepted.
- Public publishing rules were recorded in `PROJECT_GROUND_TRUTH.md` and `WORKLOG.md`.

## Restore Notes

After cloning from GitHub, read `PROJECT_GROUND_TRUTH.md` and `WORKLOG.md` before any future upload.
Every GitHub-published authorizer must retain the password gate and lockout policy.
