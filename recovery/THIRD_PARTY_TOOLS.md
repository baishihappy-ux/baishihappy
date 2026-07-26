# Third-Party Recovery Tools

The immutable recovery-toolchain release asset mirrors pinned upstream artifacts and dependency caches so the public GitHub project remains the only disaster-recovery source.

- Python 3.13.13: Python Software Foundation License.
- Node.js 24.14.1 and npm: upstream Node.js and bundled component licenses.
- Electron 31.7.7: MIT license plus bundled Chromium third-party notices.
- Gitleaks 8.30.1: MIT license.
- Python wheels: licenses declared by the exact distributions locked in `python-lock.txt`.
- npm packages: licenses declared by the exact distributions locked in `electron/package-lock.json`.

The release workflow preserves upstream archives and package metadata. These third-party files are recovery dependencies, not customer data or project secrets.
