# Architecture Notes

This document is intentionally generic so the public repository can be used as a recovery snapshot without exposing customer data, target-site names, secrets, or operational identifiers.

## Runtime Shape

```text
workspace
  electron/
    main process
    preload bridge
    renderer dashboard
    compact monitor
  python/
    auth/
    challenge/
    control/
    engine/
    export/
    network/
    parser/
    provider_shim/
    providers/
    queue/
    runtime_cli/
    session/
    utils/
  runtime/
    config/
    logs/        ignored
    output/      ignored
    state/       ignored
  tools/
    developer authorization utility
```

## Provider Model

The provider layer is split into three tiers:

| Tier | Role | Control Boundary |
| --- | --- | --- |
| Tier A | stable direct API provider | no control brain, no session pool |
| Tier B | semi-managed provider | light retry/fallback only |
| Tier C | unstable provider path | may use control brain and session pool |

Tier A must remain hard-isolated from control-brain and session-pool behavior.

## Runtime Flow

1. UI starts or controls the engine.
2. Engine validates runtime state and config.
3. Input pool claims work and writes cursor/pending state.
4. Scheduler releases work by stage and shared in-flight limits.
5. Provider layer fetches HTML or returns a normalized failure.
6. Challenge detector rejects blocked/fake-success pages before parsing.
7. Parser extracts source-specific fields.
8. Export layer writes results, retry records, and final discard records.
9. Runtime status/events/logs feed the UI.
10. Pause/resume and unexpected-close recovery use runtime state files.

## Important Boundaries

- UI mirrors runtime state; it does not own business logic.
- Config is the main parameter source.
- Runtime hot tuning is disabled unless explicitly re-enabled.
- Control brain is scoped to Tier C.
- Runtime output/state/log files are generated data and are not committed.

## Recovery Notes

After cloning:

1. Read `PROJECT_GROUND_TRUTH.md`.
2. Read `WORKLOG.md`.
3. Restore runtime secrets locally.
4. Install dependencies as needed.
5. Run syntax/compile checks before making behavioral changes.
