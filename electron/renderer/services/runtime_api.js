import { ipcClient } from './ipc_client.js';

export async function readRuntimeSnapshot() {
  const [statusPayload, logs, events] = await Promise.all([
    ipcClient.getStatus(),
    ipcClient.getLogs(300),
    ipcClient.getEvents(200)
  ]);
  return {
    runtimeRoot: statusPayload.runtime_root,
    status: statusPayload.status || {},
    controlBrain: statusPayload.control_brain || null,
    paths: statusPayload.paths || {},
    logs,
    events
  };
}

export function getProvider(status) {
  return status.provider || {
    active: status.provider_active || 'unknown',
    tier: 'unknown',
    uses_control_brain: false,
    uses_session_pool: false
  };
}

export function getControlState(status, controlBrain) {
  return controlBrain || status.control_brain || null;
}

export function getSession(status) {
  return status.pool || {
    size: status.active_chain_sessions_current || 0,
    states: status.worker_state_counts || {},
    stability: status.session_stability ?? null,
    chain_breaks: status.active_chain_failed_total || 0,
    recoveries: 0
  };
}

export function getScheduler(status, controlBrain) {
  const stateVector = controlBrain?.state_vector || status.control_brain?.state_vector || {};
  return {
    currentConcurrency: status.current_concurrency ?? stateVector.concurrency_load ?? null,
    concurrencyTarget: controlBrain?.signal?.concurrency_target ?? status.scheduler_ramp_worker_target ?? null,
    queuePressure: stateVector.queue_pressure ?? status.queue_pressure ?? null,
    failureDensity: stateVector.failure_density ?? status.provider_failure_density_rate ?? null,
    throughputRate: stateVector.throughput_rate ?? status.rate_per_minute ?? null,
    workerCount: status.scheduler_alive_workers ?? status.scheduler_started_workers ?? null,
    inflightCurrent: status.do_inflight_current ?? status.scheduler_do_inflight_current ?? null,
    inflightTarget: status.do_inflight_target ?? status.scheduler_do_inflight_target ?? null,
    dispatchRate: status.provider_request_rate_per_minute ?? status.claim_rate_per_minute ?? null
  };
}


