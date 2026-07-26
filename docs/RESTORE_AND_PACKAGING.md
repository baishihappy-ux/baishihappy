# Restore And Packaging Guide

## Authoritative Recovery

The sole formal recovery procedure is documented in `docs/唯一恢复方式.md`.

The user obtains source only through the GitHub `Code` menu and `Download ZIP`, extracts it into a new empty folder, and double-clicks root `恢复生产环境.cmd`.

Recovery does not require a Git client, Git metadata, an old workspace, a copied customer package, or a private source backup.

## What The Recovery Entry Does

The recovery entry:

1. Verifies the public source manifest by path, size, and SHA-256.
2. Prepares pinned Windows x64 Python, Node.js, npm, Electron, PyInstaller, and secret-scanning tools.
3. Creates project-local isolated dependencies.
4. Verifies repository-owned production build assets.
5. Runs filesystem-based privacy and secret scans without Git metadata.
6. Runs Python tests and JavaScript syntax checks.
7. Builds the developer authorizer, production engine, and a non-deliverable customer-shell validation package.
8. Reports development readiness and production-build readiness separately.

## Development Entrypoints

After recovery:

- `启动当前源码客户端.cmd` starts the current Electron and Python source from the restored local toolchain.
- `启动开发者授权程序.cmd` starts the current Python-native developer authorizer source from the restored local toolchain.

Neither launcher points to an old package, copied “latest” directory, historical customer archive, or globally installed runtime.

## Build Resources

Production engine builds load the gender mapping asset only from:

`assets/build/gender/_gender_map.js`

The expected SHA-256 is:

`20b0122a7be802b95e1c6ccb44854bfb4a55023c672dec0dbae348058a0859dc`

Searching parent folders or falling back to ignored generated assets is forbidden.

## Security Boundary

The public recovery source must never contain:

- customer records or enterprise assets;
- login state, runtime cache, logs, output, or screenshots;
- `runtime/license.dat`;
- issuer private keys or `.package-secrets`;
- generated formal customer packages;
- code-signing certificates or publishing credentials.

Customer engines contain public verification keys only. The developer authorizer may contain issuer logic, but its protected private key remains external to source and build artifacts.

## Production Validation Versus Formal Packaging

Recovery performs a validation build marked `NOT_FOR_DELIVERY`.

It does not:

- create a formal customer suite;
- consume a formal nine-digit suite ID;
- generate suite-specific keys;
- issue authorization codes;
- sign executables;
- publish a release.

Formal packaging remains a separate explicitly authorized operation.

## Public Upload Safety

Publishing maintenance may use Git internally, but publishing operations are not recovery operations. Before public upload:

1. Generate the public source manifest.
2. Scan the manifest-defined tree, not ignored local data.
3. Confirm required build assets and dependency locks.
4. Run tests and production validation builds.
5. Prepare the public update in an isolated publish tree.
6. Preserve history with a normal push unless the user explicitly requests history replacement.
7. Download the resulting real GitHub ZIP and run the sole recovery entry again.
