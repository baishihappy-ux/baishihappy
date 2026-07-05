# Version: Authorizer Password Gate

## Purpose

Require a developer password before opening the authorization tool.

## Changes

- Electron authorization tool starts on a locked screen.
- Authorization generation is blocked in the main process until unlocked.
- Python/Tk authorization tool asks for the password before showing the generator.
- Public source keeps provider and target-source endpoints encoded rather than direct public strings.
- Public config can restore T/F/P source behavior through `encoded_key`.

## Verification

- Python compile checks pass for changed auth, parser, provider, and engine modules.
- Electron syntax checks pass for the client and authorization tool.
- Public source scan passes for direct provider-source and target-source names.

## Restore Notes

After cloning, the developer authorization tool password is required before generating authorization codes.
