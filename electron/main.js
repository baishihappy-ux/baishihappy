const { app, BrowserWindow, ipcMain, clipboard } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const https = require('https');
const path = require('path');

const projectRoot = __dirname.includes('app.asar') ? path.resolve(process.cwd(), '..') : path.resolve(__dirname, '..');
const customerRoot = process.env.APP_HOME || projectRoot;
const runtimeRoot = process.env.APP_RUNTIME_ROOT || path.join(customerRoot, 'runtime');
const appIconPath = path.join(__dirname, 'renderer', 'assets', 'app_icon.png');
let mainWindow = null;
let monitorWindow = null;
let engineProcess = null;
let watchers = [];
let gracefulCloseInProgress = false;

function engineArgs(command, extra = []) {
  return ['-m', 'python.engine.cli', command, '--root', customerRoot, ...extra];
}

function runEngine(command, extra = []) {
  return new Promise((resolve) => {
    const child = spawn('python', engineArgs(command, extra), { cwd: projectRoot, windowsHide: true });
    let out = '';
    let err = '';
    child.stdout.on('data', (data) => { out += data.toString(); });
    child.stderr.on('data', (data) => { err += data.toString(); });
    child.on('close', (code) => resolve({ ok: code === 0, code, out, err }));
  });
}

function readJsonFile(filePath, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function writeJsonFile(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function configPath() {
  return path.join(runtimeRoot, 'config', 'app_config.json');
}

function encodedUrl(key) {
  const values = {
    do: [104,116,116,112,115,58,47,47,97,112,105,46,115,99,114,97,112,101,46,100,111,47],
    T: [104,116,116,112,115,58,47,47,119,119,119,46,116,114,117,101,112,101,111,112,108,101,115,101,97,114,99,104,46,99,111,109],
    F: [104,116,116,112,115,58,47,47,119,119,119,46,102,97,115,116,112,101,111,112,108,101,115,101,97,114,99,104,46,99,111,109],
    P: [104,116,116,112,115,58,47,47,119,119,119,46,112,101,111,112,108,101,115,101,97,114,99,104,110,111,119,46,99,111,109]
  };
  return String.fromCharCode(...(values[key] || []));
}

function setTargetSource(value) {
  const raw = String(value || 'T').trim().toUpperCase();
  const target = ['T', 'F', 'P'].includes(raw) ? raw : 'T';
  const filePath = configPath();
  const config = readJsonFile(filePath, {}) || {};
  config.runtime = config.runtime || {};
  config.runtime.target_source = target;
  writeJsonFile(filePath, config);
  return { ok: true, targetSource: target, path: filePath };
}

function readTail(filePath, maxLines = 300) {
  try {
    const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/).filter(Boolean);
    return lines.slice(-maxLines);
  } catch {
    return [];
  }
}

function activeRunLock() {
  const lockPath = path.join(runtimeRoot, 'temp', 'run.lock');
  const payload = readJsonFile(lockPath, null);
  if (!payload) return { active: false, stale: false, path: lockPath, pid: 0 };
  const pid = Number(payload.pid || 0);
  let alive = false;
  try {
    if (pid > 0) {
      process.kill(pid, 0);
      alive = true;
    }
  } catch {
    alive = false;
  }
  return { active: alive, stale: !alive, path: lockPath, pid, payload };
}

function inputStatus() {
  const config = readJsonFile(configPath(), {}) || {};
  const inputFile = config.input_file || '../input.txt';
  const targetSource = config.runtime?.target_source || 'T';
  const candidates = [];
  if (targetSource === 'T') {
    candidates.push(path.join(customerRoot, '号码补齐父级input.txt'));
    candidates.push(path.join(customerRoot, '裂变关联人父级input.txt'));
  }
  candidates.push(path.resolve(path.join(runtimeRoot, 'config'), inputFile));
  candidates.push(path.join(customerRoot, path.basename(inputFile)));
  const inputPath = candidates.find((candidate) => {
    try { return fs.existsSync(candidate) && fs.statSync(candidate).size > 0; } catch { return false; }
  }) || candidates[0];
  let rowCount = 0;
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) {
        rowCount += fs.readFileSync(candidate, 'utf8').split(/\r?\n/).filter((line) => /\d/.test(line)).length;
      }
    } catch {
      // Ignore unreadable candidate.
    }
  }
  const distribution = readJsonFile(path.join(runtimeRoot, 'state', 'input_distribution.json'), {}) || {};
  const dualCursor = readJsonFile(path.join(runtimeRoot, 'state', 't_dual_input_cursor.json'), {}) || {};
  const dualPending = readJsonFile(path.join(runtimeRoot, 'state', 't_dual_input_pending.json'), {}) || {};
  const dualSummary = readJsonFile(path.join(runtimeRoot, 'state', 't_dual_input_summary.json'), {}) || {};
  const dualRows = Number(dualSummary.a_total || 0) + Number(dualSummary.b_total || 0);
  const pendingCount = Object.keys(dualPending.items || {}).length;
  return {
    input_file: inputFile,
    target_path: inputPath,
    exists: fs.existsSync(inputPath) || dualRows > 0 || rowCount > 0,
    row_count: Math.max(rowCount, dualRows),
    distribution,
    dual_cursor: dualCursor,
    dual_pending_count: pendingCount,
    dual_summary: dualSummary
  };
}

function readResults(kind = 'main', maxLines = 80) {
  const txtPath = path.join(runtimeRoot, 'output', 'results.txt');
  const csvPath = path.join(runtimeRoot, 'output', kind === 'demo' ? 'demo_results.csv' : 'results.csv');
  const filePath = fs.existsSync(txtPath) ? txtPath : csvPath;
  try {
    const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/).filter(Boolean);
    return { ok: true, exists: true, path: filePath, lineCount: lines.length, dataRows: lines.length, preview: lines.slice(0, maxLines).join('\n') };
  } catch (error) {
    return { ok: false, exists: false, path: filePath, lineCount: 0, dataRows: 0, preview: '', error: error.message };
  }
}

function probe(url, timeoutMs = 5000) {
  return new Promise((resolve) => {
    const started = Date.now();
    const request = https.request(url, { method: 'GET', timeout: timeoutMs, headers: { 'User-Agent': 'Workspace-Probe/1.0' } }, (response) => {
      response.resume();
      response.on('end', () => resolve({ ok: response.statusCode < 500, statusCode: response.statusCode, latencyMs: Date.now() - started, url }));
    });
    request.on('timeout', () => request.destroy(new Error('timeout')));
    request.on('error', (error) => resolve({ ok: false, error: error.message, timedOut: error.message === 'timeout', latencyMs: Date.now() - started, url }));
    request.end();
  });
}

async function testNetwork() {
  const config = readJsonFile(configPath(), {}) || {};
  const targetSource = config.runtime?.target_source || 'T';
  const sourceTargets = {
    T: encodedUrl('T'),
    F: encodedUrl('F'),
    P: encodedUrl('P')
  };
  const targets = [
    encodedUrl('do'),
    sourceTargets[targetSource] || sourceTargets.T,
    'https://www.cloudflare.com/cdn-cgi/trace',
    'https://www.google.com/generate_204'
  ].filter(Boolean);
  const probes = await Promise.all(Array.from({ length: 12 }, (_v, index) => probe(targets[index % targets.length], 8000)));
  const successful = probes.filter((item) => item.ok);
  const latencies = successful.map((item) => item.latencyMs).sort((a, b) => a - b);
  const p95LatencyMs = latencies.length ? latencies[Math.min(latencies.length - 1, Math.ceil(latencies.length * 0.95) - 1)] : null;
  const successRate = probes.length ? successful.length / probes.length : 0;
  const canRun = successRate >= 0.75 && p95LatencyMs !== null && p95LatencyMs <= 5000;
  return { ok: true, canRun, quality: canRun ? 'good' : 'bad', successCount: successful.length, totalCount: probes.length, p95LatencyMs, probes, targets };
}

async function preflight() {
  const license = await runEngine('license-status');
  let licensePayload = {};
  try { licensePayload = JSON.parse(license.out || '{}'); } catch {}
  const input = inputStatus();
  const lock = activeRunLock();
  const outputDir = path.join(runtimeRoot, 'output');
  const stateDir = path.join(runtimeRoot, 'state');
  const outputWritable = (() => {
    try {
      fs.mkdirSync(outputDir, { recursive: true });
      fs.mkdirSync(stateDir, { recursive: true });
      return true;
    } catch {
      return false;
    }
  })();
  const checks = {
    license: Boolean(licensePayload.ok),
    input: input.exists && input.row_count > 0,
    lock: !lock.active,
    outputWritable
  };
  return {
    ok: Object.values(checks).every(Boolean),
    checks,
    license: licensePayload,
    input,
    lock,
    pending_recovery: { pendingCount: Number(input.dual_pending_count || 0), hasPending: Number(input.dual_pending_count || 0) > 0 },
    output: { outputDir, stateDir, writable: outputWritable }
  };
}

function runtimePaths() {
  return {
    root: runtimeRoot,
    status: path.join(runtimeRoot, 'state', 'status.json'),
    controlBrain: path.join(runtimeRoot, 'state', 'control_brain.json'),
    events: path.join(runtimeRoot, 'state', 'events.jsonl'),
    log: path.join(runtimeRoot, 'logs', 'runtime.log')
  };
}

function getStatus() {
  const paths = runtimePaths();
  return {
    runtime_root: runtimeRoot,
    status: readJsonFile(paths.status, {}),
    control_brain: readJsonFile(paths.controlBrain, null),
    paths
  };
}

function getEvents(limit = 200) {
  return readTail(runtimePaths().events, limit).map((line) => {
    try {
      return JSON.parse(line);
    } catch {
      return { raw: line };
    }
  });
}

function getLogs(limit = 300) {
  return readTail(runtimePaths().log, limit);
}

function startEngine() {
  if (engineProcess && engineProcess.exitCode === null) {
    return { ok: true, status: 'already_running', pid: engineProcess.pid };
  }
  engineProcess = spawn('python', engineArgs('run'), { cwd: projectRoot, windowsHide: true });
  engineProcess.on('close', () => {});
  return { ok: true, status: 'started', pid: engineProcess.pid };
}

async function sendCommand(command) {
  if (command === 'start') {
    const check = await preflight();
    if (!check.ok) return { ok: false, error: '启动前检查未通过', preflight: check };
    return startEngine();
  }
  if (command === 'pause') return runEngine('pause-run');
  if (command === 'resume') return runEngine('resume-run');
  if (command === 'stop') return runEngine('pause-run', ['--reason', 'ui_stop_requested']);
  return { ok: false, error: `unknown command: ${command}` };
}

async function activateLicense(code) {
  return runEngine('activate', ['--code', code]);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1050,
    height: 655,
    minWidth: 720,
    minHeight: 655,
    center: true,
    title: 'Workspace App',
    icon: appIconPath,
    backgroundColor: '#050505',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  mainWindow.on('close', (event) => {
    if (gracefulCloseInProgress) return;
    event.preventDefault();
    gracefulCloseInProgress = true;
    sendCommand('pause').finally(() => {
      if (mainWindow && !mainWindow.isDestroyed()) mainWindow.destroy();
      app.quit();
    });
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  installRuntimeWatchers(mainWindow);
}

function createMonitorWindow() {
  if (monitorWindow && !monitorWindow.isDestroyed()) {
    monitorWindow.show();
    monitorWindow.focus();
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.hide();
    return { ok: true, opened: true, reused: true };
  }
  monitorWindow = new BrowserWindow({
    width: 389,
    height: 430,
    minWidth: 360,
    minHeight: 340,
    show: false,
    title: 'Run Monitor',
    icon: appIconPath,
    backgroundColor: '#050505',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  monitorWindow.on('closed', () => {
    monitorWindow = null;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
  monitorWindow.once('ready-to-show', () => {
    if (monitorWindow && !monitorWindow.isDestroyed()) {
      monitorWindow.show();
      if (mainWindow && !mainWindow.isDestroyed()) mainWindow.hide();
    }
  });
  monitorWindow.loadFile(path.join(__dirname, 'monitor', 'index.html'));
  return { ok: true, opened: true, reused: false };
}

function watchFileIfPresent(filePath, channel, win) {
  try {
    if (!fs.existsSync(filePath)) return;
    const watcher = fs.watch(filePath, { persistent: false }, () => {
      if (!win.isDestroyed()) win.webContents.send(channel);
    });
    watchers.push(watcher);
  } catch {
    // Runtime files can be absent before the first engine run.
  }
}

function installRuntimeWatchers(win) {
  const paths = runtimePaths();
  watchers.forEach((watcher) => watcher.close());
  watchers = [];
  watchFileIfPresent(paths.events, 'runtime:events_changed', win);
  watchFileIfPresent(paths.log, 'runtime:logs_changed', win);
}

ipcMain.handle('runtime:get_status', () => getStatus());
ipcMain.handle('runtime:get_logs', (_event, options = {}) => getLogs(options.limit));
ipcMain.handle('runtime:get_events', (_event, options = {}) => getEvents(options.limit));
ipcMain.handle('runtime:send_command', (_event, command) => sendCommand(command));
ipcMain.handle('runtime:set_target_source', (_event, value) => setTargetSource(value));
ipcMain.handle('runtime:preflight', () => preflight());
ipcMain.handle('runtime:input_status', () => inputStatus());
ipcMain.handle('runtime:results', (_event, kind, maxLines) => readResults(kind, Number(maxLines) || 80));
ipcMain.handle('runtime:test_network', () => testNetwork());
ipcMain.handle('runtime:active_run_lock', () => activeRunLock());
ipcMain.handle('monitor:open', () => createMonitorWindow());
ipcMain.handle('license:machine_code', () => runEngine('machine-code'));
ipcMain.handle('license:status', () => runEngine('license-status'));
ipcMain.handle('license:activate', (_event, code) => activateLicense(code));
ipcMain.handle('clipboard:copy_text', (_event, text) => {
  clipboard.writeText(text || '');
  return { ok: true };
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  watchers.forEach((watcher) => watcher.close());
  if (process.platform !== 'darwin') app.quit();
});
