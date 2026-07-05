# Version: Restore And Packaging Guide

## Purpose

Document how to restore the source workspace on a new machine and package the developer/customer tools safely.

## Changes

- Added `docs/RESTORE_AND_PACKAGING.md`.
- Documented source restore steps.
- Documented client UI source launch.
- Documented developer authorizer source launch.
- Documented developer authorizer lockout requirements.
- Documented why large executable artifacts should be distributed as release attachments rather than committed to Git history.
- Documented the public upload checklist.

## Verification

- Documentation avoids secrets, customer data, local absolute paths, target-source names, and runtime data.
- Commands are based on the current project layout.

## Restore Notes

On a new machine, read `PROJECT_GROUND_TRUTH.md`, `WORKLOG.md`, and `docs/RESTORE_AND_PACKAGING.md` before packaging.
