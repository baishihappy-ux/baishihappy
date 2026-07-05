# Version: Authorizer Password Gate

## Purpose

Require a developer password before opening the authorization tool.

## Changes

- Electron authorization tool starts on a locked screen.
- Authorization generation is blocked in the main process until unlocked.
- Electron authorization tool persists failed-password lockout in the app user data directory.
- Python/Tk authorization tool asks for the password before showing the generator.
- Python/Tk authorization tool persists failed-password lockout in the user's home directory.
- Lockout policy: 3rd wrong password locks 10 minutes, 4th locks 30 minutes, 5th locks 2 hours, 6th and later locks 24 hours.
- Public source keeps provider and target-source endpoints encoded rather than direct public strings.
- Public config can restore T/F/P source behavior through `encoded_key`.

## Verification

- Python compile checks pass for changed auth, parser, provider, and engine modules.
- Electron syntax checks pass for the client and authorization tool.
- Public source scan passes for direct provider-source and target-source names.

## Restore Notes

After cloning, the developer authorization tool password is required before generating authorization codes.
The failed-password lockout policy must remain present in every GitHub-published version.
