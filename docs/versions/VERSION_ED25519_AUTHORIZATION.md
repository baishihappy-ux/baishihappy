# Version: Ed25519 Offline Authorization

## Purpose

Replace the shared-secret offline authorization format with separated issuer signing and customer verification.

## Confirmed Behavior

- Legacy `DF8-` authorization codes are invalid.
- New authorization codes use the `DF9-` prefix and Ed25519 signatures.
- The developer authorizer keeps the exact existing password gate, lockout behavior, four input fields, and visible labels.
- The developer authorizer loads a Windows-DPAPI-protected private key from `.package-secrets/authorization/`.
- The customer engine contains public verification material only and has no authorization-code generation command.
- `license.dat` stores the original signed code; signature, machine binding, and expiry are checked on every startup.
- Public license status does not return the provider token.

## Key Recovery

- Daily signing uses a private key protected for the current Windows user with DPAPI.
- A passphrase-encrypted offline recovery file must be created and stored separately from its passphrase.
- Missing local DPAPI state is a recovery event, not permission to silently rotate the customer public key.

## Validation

- Valid signature and activation.
- Payload tamper rejection.
- Wrong public key and legacy-code rejection.
- Expiry and machine mismatch rejection.
- Opaque or editable JSON license rejection.
- Provider-token isolation from public status.
- Encrypted recovery export and DPAPI restore roundtrip.
