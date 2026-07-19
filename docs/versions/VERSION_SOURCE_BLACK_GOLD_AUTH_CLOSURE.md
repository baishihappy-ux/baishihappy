# Current-Source Black/Gold Authorization Closure

## Purpose

Preserve the first verified development path where the current source developer authorizer and the
current source black/gold client complete the full offline authorization lifecycle without packaging.

## Changes

- Added a fixed Windows launcher for the current client source.
- Isolated the Electron development runtime from packaged customer application archives.
- Rejected a contaminated development runtime containing packaged `app.asar`.
- Permanently deleted the contaminated `electron/node_modules/` runtime and its packaged blue archives.
- Kept the accepted black/gold renderer as the only active renderer entry.
- Removed inactive modular blue renderer files.
- Fixed the native Windows developer authorizer's 64-bit ctypes function declarations.
- Added regression tests for source launcher paths, renderer isolation, visual-baseline hashes, and DF9 support.

## Verification

- 66 automated tests passed.
- JavaScript syntax checks passed for the Electron main process, preload bridge, and renderer.
- The source client returned a non-empty machine code.
- The user manually confirmed authorization generation, activation, entry to the black/gold home page,
  restart, and automatic recognition of the persisted authorization.

## Restore Notes

- Install Electron 31.7.7 into ignored `.tmp_dev_electron/` for source preview.
- The clean runtime must contain `resources/default_app.asar` and must not contain `resources/app.asar`.
- Start the client through `启动当前源码客户端.cmd` and the authorizer through
  `启动开发者授权程序.cmd`.
- Runtime authorization data remains ignored under `.tmp_dev_client/` and must never enter Git.

## Excluded Work

- No customer package was built.
- No live provider request was made.
- No remote repository was pushed.
