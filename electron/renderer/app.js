import { renderOverview } from './dashboard/overview.js';
import { renderProviderPanel } from './dashboard/provider_panel.js';
import { renderSessionPanel } from './dashboard/session_panel.js';
import { renderSchedulerPanel } from './dashboard/scheduler_panel.js';
import { renderLogsPanel } from './dashboard/logs_panel.js';
import { ipcClient } from './services/ipc_client.js';
import { readRuntimeSnapshot } from './services/runtime_api.js';

const nodes = {
  licenseScreen: document.getElementById('license-screen'),
  homeScreen: document.getElementById('home-screen'),
  machineCode: document.getElementById('machine-code'),
  copyMachine: document.getElementById('copy-machine'),
  licenseCode: document.getElementById('license-code'),
  activateLicense: document.getElementById('activate-license'),
  refreshLicense: document.getElementById('refresh-license'),
  licenseMessage: document.getElementById('license-message'),
  root: document.getElementById('runtime-root'),
  overview: document.getElementById('overview'),
  provider: document.getElementById('provider-panel'),
  session: document.getElementById('session-panel'),
  scheduler: document.getElementById('scheduler-panel'),
  logs: document.getElementById('logs-panel')
};

let latestSnapshot = null;
let dashboardStarted = false;

function showLicense(message = '') {
  nodes.homeScreen.classList.add('hidden');
  nodes.licenseScreen.classList.remove('hidden');
  nodes.licenseMessage.textContent = message;
}

function showHome() {
  nodes.licenseScreen.classList.add('hidden');
  nodes.homeScreen.classList.remove('hidden');
  if (!dashboardStarted) {
    dashboardStarted = true;
    startDashboardLoops();
  }
}

async function loadMachineCode() {
  const result = await window.t1Runtime.get_machine_code();
  nodes.machineCode.value = (result.out || '').trim();
}

async function checkLicense() {
  await loadMachineCode();
  const result = await window.t1Runtime.get_license_status();
  let payload = {};
  try {
    payload = JSON.parse(result.out || '{}');
  } catch {
    payload = { ok: false, reason: result.err || 'license status parse failed' };
  }
  if (payload.ok) {
    showHome();
    await refreshStatus();
    await refreshProvider();
    await refreshLogs();
  } else {
    showLicense(payload.reason || '鏈巿鏉?);
  }
}

async function activateLicense() {
  const code = nodes.licenseCode.value.trim();
  if (!code) {
    nodes.licenseMessage.textContent = '璇疯緭鍏ユ巿鏉冪爜';
    return;
  }
  nodes.activateLicense.disabled = true;
  const result = await window.t1Runtime.activate_license(code);
  nodes.activateLicense.disabled = false;
  let payload = {};
  try {
    payload = JSON.parse(result.out || '{}');
  } catch {
    payload = { ok: false, reason: result.err || '婵€娲诲け璐? };
  }
  if (payload.ok) {
    nodes.licenseMessage.textContent = '鎺堟潈鎴愬姛';
    await checkLicense();
  } else {
    nodes.licenseMessage.textContent = payload.reason || '鎺堟潈澶辫触';
  }
}

async function refreshStatus() {
  latestSnapshot = await readRuntimeSnapshot();
  nodes.root.textContent = latestSnapshot.runtimeRoot || '';
  renderOverview(nodes.overview, latestSnapshot);
  renderSessionPanel(nodes.session, latestSnapshot);
  renderSchedulerPanel(nodes.scheduler, latestSnapshot);
}

async function refreshProvider() {
  if (!latestSnapshot) latestSnapshot = await readRuntimeSnapshot();
  renderProviderPanel(nodes.provider, latestSnapshot);
}

async function refreshLogs() {
  latestSnapshot = await readRuntimeSnapshot();
  renderLogsPanel(nodes.logs, latestSnapshot);
}

function startDashboardLoops() {
  setInterval(refreshStatus, 1000);
  setInterval(refreshProvider, 5000);
  setInterval(refreshLogs, 1500);
  window.t1Runtime.on_logs_changed(refreshLogs);
  window.t1Runtime.on_events_changed(refreshLogs);
}

nodes.copyMachine.addEventListener('click', async () => {
  await window.t1Runtime.copy_text(nodes.machineCode.value);
  nodes.licenseMessage.textContent = '鏈哄櫒鐮佸凡澶嶅埗';
});

nodes.activateLicense.addEventListener('click', activateLicense);
nodes.refreshLicense.addEventListener('click', checkLicense);

document.querySelectorAll('[data-command]').forEach((button) => {
  button.addEventListener('click', async () => {
    button.disabled = true;
    await ipcClient.sendCommand(button.dataset.command);
    await refreshStatus();
    button.disabled = false;
  });
});

await checkLicense();


