const REFRESH_MS = 3000;

let fallbackStartedAtMs = 0;
let stoppedElapsedMs = 0;

function $(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const node = $(id);
  if (node) node.textContent = String(value ?? '');
}

function setLevel(id, level = '') {
  const card = $(id)?.closest('.metric-card');
  if (!card) return;
  card.classList.remove('metric-good', 'metric-warn', 'metric-bad');
  if (level) card.classList.add(`metric-${level}`);
}

function numberValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseTimeMs(value) {
  const parsed = Date.parse(String(value || ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatElapsed(ms) {
  const totalSeconds = Math.max(0, Math.floor(Number(ms || 0) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, '0')).join(':');
}

function runtimeStateText(status) {
  const raw = String(status || '').toLowerCase();
  if (raw.includes('running')) return { text: '标准运行', level: 'good' };
  if (raw.includes('pause')) return { text: '已暂停', level: 'warn' };
  if (raw.includes('finish') || raw.includes('completed')) return { text: '已完成', level: 'good' };
  if (raw.includes('fail') || raw.includes('error')) return { text: '异常停止', level: 'bad' };
  return { text: '待启动', level: 'warn' };
}

function updateTimer(status = {}) {
  const stateText = String(status.status || '').toLowerCase();
  const startedAtMs = parseTimeMs(status.started_at);
  const updatedAtMs = parseTimeMs(status.updated_at);
  const running = stateText === 'running';
  const paused = stateText.includes('pause');
  const finished = ['completed', 'failed', 'finished'].includes(stateText);
  if (startedAtMs) {
    const endMs = finished || paused ? (updatedAtMs || Date.now()) : Date.now();
    stoppedElapsedMs = Math.max(0, endMs - startedAtMs);
    setText('runtimeTimer', formatElapsed(stoppedElapsedMs));
    return;
  }
  if (running && !fallbackStartedAtMs) fallbackStartedAtMs = Date.now();
  if (running && fallbackStartedAtMs) stoppedElapsedMs = Date.now() - fallbackStartedAtMs;
  setText('runtimeTimer', formatElapsed(stoppedElapsedMs));
}

function updateMetrics(snapshot = {}) {
  const status = snapshot.status || {};
  const requestRate = Math.round(numberValue(status.provider_request_rate_per_minute || status.claim_rate_per_minute, 0));
  const saveRate = Math.round(numberValue(status.rate_per_minute || status.throughput_rate, 0));
  const requestCount = numberValue(status.provider_request_30s_count || status.provider_request_count, 0);
  const bad502 = numberValue(status.provider_502_30s_count || status.error_502_count, 0);
  const successRate = requestCount ? Math.max(0, ((requestCount - bad502) / requestCount) * 100) : NaN;
  const badRate = requestCount ? (bad502 / requestCount) * 100 : 0;
  const doCurrent = Math.round(numberValue(status.do_inflight_current || status.scheduler_do_inflight_current, 0));
  const doLimit = Math.round(numberValue(status.do_inflight_hard_limit || status.do_inflight_target || status.authorized_concurrency, 0));
  const stateInfo = runtimeStateText(status.status);

  setText('metricRequestRate', `${requestRate}/min`);
  setText('metricSaveRate', `${saveRate}/min`);
  setText('metricAccessSuccessRate', Number.isFinite(successRate) ? `${successRate.toFixed(1)}%` : '--');
  setText('metric502Rate', `${badRate.toFixed(1)}%`);
  setText('metricDoInflight', `${doCurrent}/${doLimit}`);
  setText('metricRemaining', String(Math.max(0, Math.trunc(numberValue(status.remaining_work || status.remaining, 0)))));
  setText('metricSavedTotal', String(Math.trunc(numberValue(status.saved || status.saved_total, 0))));
  setText('metricCompletedTotal', String(Math.trunc(numberValue(status.customer_completed_seeds || status.completed || status.processed, 0))));
  setText('metricRuntimeState', stateInfo.text);
  setLevel('metricAccessSuccessRate', Number.isFinite(successRate) && successRate >= 95 ? 'good' : 'warn');
  setLevel('metric502Rate', badRate < 5 ? 'good' : badRate < 10 ? 'warn' : 'bad');
  setLevel('metricRuntimeState', stateInfo.level);
  updateTimer(status);

  const updated = new Date();
  setText('monitorUpdated', `${String(updated.getHours()).padStart(2, '0')}:${String(updated.getMinutes()).padStart(2, '0')}:${String(updated.getSeconds()).padStart(2, '0')}`);
  if (snapshot.runtime_root) setText('monitorRoot', snapshot.runtime_root);
}

async function refresh() {
  try {
    const snapshot = await window.t1Runtime.get_status();
    updateMetrics(snapshot || {});
  } catch {
    setText('metricRuntimeState', '监控异常');
    setLevel('metricRuntimeState', 'bad');
  }
}

refresh();
window.setInterval(refresh, REFRESH_MS);
