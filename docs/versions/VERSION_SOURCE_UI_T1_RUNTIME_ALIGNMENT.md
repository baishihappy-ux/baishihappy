# Source UI And T1 Runtime Alignment

## Purpose

Make the current-source black/gold client and the current Python T1 engine use one development
runtime tree after the verified authorization closure.

## Change

- `启动当前源码客户端.cmd` now sets `DINGFENG_RUNTIME_ROOT` to
  `.tmp_dev_client/runtime/`.
- The launcher regression test locks that exact path.
- Authorization, configuration, state, logs, output, pause controls, and input-progress files now
  resolve under one root for both Electron and Python.

## Offline Evidence

- Provider: local fixture only; network disabled.
- Input: three synthetic reserved numbers.
- Session lanes: one; test cooldown: zero.
- Result: `FINISHED`, three completed inputs, zero remaining, zero failures, zero worker errors.
- Request mix: eight total — one entry, three searches, one parent detail, three associates.
- Export: four result rows in both CSV and TXT outputs.
- Runtime state, logs, interruption state, and 502 recycle state were created successfully.

## Still Pending

- Manual black/gold UI confirmation after the runtime-root change.
- UI-driven local fixture run, visible metrics/log/result comparison, pause/resume, and interruption.

## Exclusions

- No live provider request.
- No customer package or installer.
- No remote Git push.
- Ignored authorization and temporary acceptance data are not part of this checkpoint.
