const REFRESH_MS = 3000;

let fallbackStartedAtMs = 0;
let stoppedElapsedMs = 0;

function $(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const node = $(id);
  if (node) {
    node.textContent = String(value ?? '');
  }
}

function setLevel(id, level = '') {
  const node = $(id);
  const card = node ? node.closest('.metric-card') : null;
  if (!card) {
    return;
  }
  card.classList.remove('metric-good', 'metric-warn', 'metric-bad');
  if (level) {
    card.classList.add(`metric-${level}`);
  }
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

function updateTimer(metrics = {}) {
  const status = metrics.raw?.status || {};
  const stateText = String(status.status || '').toLowerCase();
  const startedAtMs = parseTimeMs(status.started_at);
  const updatedAtMs = parseTimeMs(status.updated_at);
  const running = stateText === 'running';
  const paused = stateText.includes('pause');
  const finished = ['completed', 'failed', 'finished', 'circuit_breaker'].includes(stateText) || Boolean(metrics.terminalReason);
  if (startedAtMs) {
    const endMs = finished || paused ? (updatedAtMs || Date.now()) : Date.now();
    stoppedElapsedMs = Math.max(0, endMs - startedAtMs);
    setText('runtimeTimer', formatElapsed(stoppedElapsedMs));
    return;
  }
  if (running && !fallbackStartedAtMs) {
    fallbackStartedAtMs = Date.now();
  }
  if (running && fallbackStartedAtMs) {
    stoppedElapsedMs = Date.now() - fallbackStartedAtMs;
  }
  setText('runtimeTimer', formatElapsed(stoppedElapsedMs));
}

function updateMetrics(metrics = {}) {
  const values = metrics.values || {};
  const levels = metrics.levels || {};
  setText('metricRequestRate', values.requestRate || '0/min');
  setText('metricSaveRate', values.saveRate || '0/min');
  setText('metricAccessSuccessRate', values.accessSuccessRate || '--');
  setText('metric502Rate', values.bad502Rate || '0%');
  setText('metricDoInflight', values.doInflight || '0/0');
  setText('metricRemaining', values.remaining || '0');
  setText('metricSavedTotal', values.savedTotal || '0');
  setText('metricCompletedTotal', values.completedTotal || '0');
  setText('metricRuntimeState', values.runtimeState || 'Idle');
  setLevel('metricAccessSuccessRate', levels.accessSuccessRate || '');
  setLevel('metric502Rate', levels.bad502Rate || '');
  setLevel('metricRuntimeState', levels.runtimeState || '');
  updateTimer(metrics);
  const updated = new Date();
  setText('monitorUpdated', `${String(updated.getHours()).padStart(2, '0')}:${String(updated.getMinutes()).padStart(2, '0')}:${String(updated.getSeconds()).padStart(2, '0')}`);
  const root = metrics.root || metrics.raw?.status?.root || '';
  if (root) {
    setText('monitorRoot', root);
  }
}

async function refresh() {
  if (!window.workspaceRuntime?.runtimeMetrics) {
    setText('metricRuntimeState', 'Board unavailable');
    setLevel('metricRuntimeState', 'bad');
    return;
  }
  try {
    const metrics = await window.workspaceRuntime.runtimeMetrics();
    updateMetrics(metrics || {});
  } catch (error) {
    setText('metricRuntimeState', 'Board error');
    setLevel('metricRuntimeState', 'bad');
  }
}

refresh();
window.setInterval(refresh, REFRESH_MS);
