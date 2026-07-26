# Version: ZIP-Only Disaster Recovery

## Purpose

Make the public GitHub project the only source needed to reconstruct the development and production-build environment after machine loss.

## Contract

- The sole manual source acquisition path is the GitHub `Code` menu followed by `Download ZIP`.
- Recovery runs from the root `恢复生产环境.cmd`.
- Recovery, tests, and security scans do not require Git metadata.
- Project-specific source, UI assets, and production build assets are public when required for reconstruction.
- Customer data, runtime state, private keys, license files, logs, outputs, packaging secrets, and signing credentials remain excluded.

## Validation

The Windows continuous-integration job downloads the real GitHub archive into a new empty directory, confirms that no Git metadata exists, poisons any accidental Git invocation, and runs the recovery entry.

## Delivery Boundary

Recovery builds a non-deliverable validation customer shell. It does not create a formal customer suite, consume a suite ID, issue licenses, or sign deliverables.
