const { app, BrowserWindow, clipboard, dialog, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const https = require('https');
const { spawn } = require('child_process');

const DEFAULT_ZOOM = 1;
const MIN_ZOOM = 1;
const MAX_ZOOM = 1;
const APP_ICON_PATH = path.join(__dirname, 'renderer', 'assets', 'app_icon.png');

const SOURCE_ROOT = path.resolve(__dirname, '..');
const EXECUTABLE_ROOT = app.isPackaged ? path.dirname(process.execPath) : SOURCE_ROOT;
const RESOURCES_ROOT = app.isPackaged ? process.resourcesPath : SOURCE_ROOT;
const APP_ROOT = SOURCE_ROOT;

app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-software-rasterizer');
if (!app.isPackaged) {
  const devUserData = path.join(SOURCE_ROOT, '.tmp_electron_user_data');
  fs.mkdirSync(devUserData, { recursive: true });
  app.setPath('userData', devUserData);
}

function resolvePackageRoot() {
  if (process.env.WORKSPACE_HOME) {
    return path.resolve(process.env.WORKSPACE_HOME);
  }
  if (app.isPackaged) {
    const parentRoot = path.dirname(EXECUTABLE_ROOT);
    const launchedFromAppDir = path.basename(EXECUTABLE_ROOT).toLowerCase() === 'app';
    if (launchedFromAppDir && fs.existsSync(path.join(parentRoot, 'runtime'))) {
      return parentRoot;
    }
  }
  return EXECUTABLE_ROOT;
}

function resolveInstanceRoot() {
  if (process.env.WORKSPACE_RUNTIME_ROOT) {
    return path.resolve(process.env.WORKSPACE_RUNTIME_ROOT);
  }
  if (app.isPackaged) {
    return path.join(resolvePackageRoot(), 'runtime');
  }
  if (process.env.WORKSPACE_HOME) {
    return path.resolve(process.env.WORKSPACE_HOME);
  }
  const cwd = path.resolve(process.cwd());
  if (fs.existsSync(path.join(cwd, 'config', 'app_config.json'))) {
    return cwd;
  }
  return APP_ROOT;
}

const INSTANCE_ROOT = resolveInstanceRoot();
const PYTHON_COMMAND = process.env.PYTHON_EXECUTABLE || 'python';

let mainWindow = null;
let monitorWindow = null;
let engineProcess = null;
let licenseSlot = null;
let closeRequestSent = false;
let gracefulCloseInProgress = false;

const NETWORK_PROBE_TARGETS = [
  { name: 'Google', url: 'https://www.google.com/generate_204' },
  { name: 'Cloudflare', url: 'https://www.cloudflare.com/cdn-cgi/trace' },
  { name: 'Microsoft', url: 'https://www.microsoft.com/favicon.ico' }
];
const NETWORK_PRESSURE_CONCURRENCY = 24;
const NETWORK_PRESSURE_TIMEOUT_MS = 8000;

function probeNetworkTarget(target, timeoutMs = 5000) {
  return new Promise((resolve) => {
    const startedAt = Date.now();
    const request = https.request(
      target.url,
      {
        method: 'GET',
        timeout: timeoutMs,
        headers: {
          'User-Agent': 'Workspace-Network-Probe/1.0',
          'Accept': '*/*',
          'Cache-Control': 'no-cache'
        }
      },
      (response) => {
        response.resume();
        response.on('end', () => {
          const latencyMs = Date.now() - startedAt;
          resolve({
            name: target.name,
            ok: response.statusCode < 500,
            statusCode: response.statusCode,
            latencyMs
          });
        });
      }
    );
    request.on('timeout', () => {
      request.destroy(new Error('timeout'));
    });
    request.on('error', (error) => {
      resolve({
        name: target.name,
        ok: false,
        timedOut: error.message === 'timeout',
        error: error.message,
        latencyMs: Date.now() - startedAt
      });
    });
    request.end();
  });
}

async function testNetworkQuality() {
  const probes = await Promise.all(
    Array.from({ length: NETWORK_PRESSURE_CONCURRENCY }, (_value, index) => {
      const target = NETWORK_PROBE_TARGETS[index % NETWORK_PROBE_TARGETS.length];
      return probeNetworkTarget(target, NETWORK_PRESSURE_TIMEOUT_MS);
    })
  );
  const successful = probes.filter((probe) => probe.ok);
  const latencies = successful.map((probe) => probe.latencyMs).sort((a, b) => a - b);
  const avgLatencyMs = successful.length
    ? Math.round(successful.reduce((sum, probe) => sum + probe.latencyMs, 0) / successful.length)
    : null;
  const p95LatencyMs = latencies.length
    ? latencies[Math.min(latencies.length - 1, Math.ceil(latencies.length * 0.95) - 1)]
    : null;
  const timeoutCount = probes.filter((probe) => probe.timedOut).length;
  const successRate = probes.length ? successful.length / probes.length : 0;
  const timeoutRate = probes.length ? timeoutCount / probes.length : 1;
  let quality = '差';
  let canRun = false;
  if (successRate >= 0.95 && timeoutRate <= 0.03 && p95LatencyMs !== null && p95LatencyMs <= 1500) {
    quality = '优';
    canRun = true;
  } else if (successRate >= 0.85 && timeoutRate <= 0.1 && p95LatencyMs !== null && p95LatencyMs <= 3500) {
    quality = '良';
  }
  return {
    ok: true,
    quality,
    canRun,
    avgLatencyMs,
    p95LatencyMs,
    successCount: successful.length,
    totalCount: probes.length,
    timeoutCount,
    successRate,
    timeoutRate,
    concurrency: NETWORK_PRESSURE_CONCURRENCY,
    probes,
    recommendation: canRun ? '网络优，可以运行。' : `当前网络${quality}，建议不运行。`
  };
}

function pythonEnv() {
  return {
    ...process.env,
    WORKSPACE_RUNTIME_ROOT: INSTANCE_ROOT,
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  };
}

function getPythonScript() {
  const instanceScript = path.join(INSTANCE_ROOT, 'python', 'main.py');
  if (fs.existsSync(instanceScript)) {
    return instanceScript;
  }
  return path.join(APP_ROOT, 'python', 'main.py');
}

function getExistingPath(candidates) {
  return candidates.find((candidate) => candidate && fs.existsSync(candidate)) || '';
}

function parseJsonText(text) {
  return JSON.parse(String(text || '').replace(/^\uFEFF/, ''));
}

function readJsonPath(filePath) {
  return parseJsonText(fs.readFileSync(filePath, 'utf8'));
}

function deepMergeConfig(base, override) {
  const merged = { ...(base && typeof base === 'object' ? base : {}) };
  if (!override || typeof override !== 'object') {
    return merged;
  }
  for (const [key, value] of Object.entries(override)) {
    if (
      value &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      merged[key] &&
      typeof merged[key] === 'object' &&
      !Array.isArray(merged[key])
    ) {
      merged[key] = deepMergeConfig(merged[key], value);
    } else {
      merged[key] = value;
    }
  }
  return merged;
}

function copyFileIfDifferent(sourcePath, targetPath) {
  if (!sourcePath || !fs.existsSync(sourcePath)) {
    return false;
  }
  try {
    fs.mkdirSync(path.dirname(targetPath), { recursive: true });
    if (fs.existsSync(targetPath)) {
      const source = fs.readFileSync(sourcePath);
      const target = fs.readFileSync(targetPath);
      if (source.equals(target)) {
        return false;
      }
    }
    fs.copyFileSync(sourcePath, targetPath);
    return true;
  } catch (error) {
    return false;
  }
}

function ensureCustomerRuntimeLayout() {
  if (!app.isPackaged) {
    return;
  }

  for (const name of ['config', 'logs', 'output', 'cache', 'temp', 'state']) {
    fs.mkdirSync(path.join(INSTANCE_ROOT, name), { recursive: true });
  }

  const defaultConfig = getExistingPath([
    path.join(RESOURCES_ROOT, 'default_config', 'app_config.json'),
    path.join(RESOURCES_ROOT, 'config_templates', 'customer_demo_app_config.json'),
    path.join(APP_ROOT, 'config_templates', 'customer_demo_app_config.json'),
  ]);
  const runtimeConfig = path.join(INSTANCE_ROOT, 'config', 'app_config.json');
  if (defaultConfig && !fs.existsSync(runtimeConfig)) {
    copyFileIfDifferent(defaultConfig, runtimeConfig);
  }

  for (const fileName of ['demo_input.txt', 'local_demo_data.json']) {
    const sourcePath = getExistingPath([
      path.join(RESOURCES_ROOT, 'default_config', fileName),
      path.join(RESOURCES_ROOT, 'config', fileName),
      path.join(APP_ROOT, 'config', fileName),
    ]);
    const targetPath = path.join(INSTANCE_ROOT, 'config', fileName);
    if (sourcePath && !fs.existsSync(targetPath)) {
      copyFileIfDifferent(sourcePath, targetPath);
    }
  }

  const licenseSource = getExistingPath([
    process.env.WORKSPACE_LICENSE_PATH,
    path.join(resolvePackageRoot(), 'license.dat'),
    path.join(EXECUTABLE_ROOT, 'license.dat'),
  ]);
  if (licenseSource) {
    copyFileIfDifferent(licenseSource, path.join(INSTANCE_ROOT, 'license.dat'));
  }
}

function getEngineExecutable() {
  if (!app.isPackaged) {
    return '';
  }

  const candidates = [
    process.env.WORKSPACE_ENGINE_EXECUTABLE,
    path.join(RESOURCES_ROOT, 'engine', 'runtime_engine.exe'),
    path.join(RESOURCES_ROOT, 'app.asar.unpacked', 'engine', 'runtime_engine.exe'),
    path.join(EXECUTABLE_ROOT, 'resources', 'engine', 'runtime_engine.exe'),
    path.join(EXECUTABLE_ROOT, 'app', 'resources', 'engine', 'runtime_engine.exe'),
    path.join(EXECUTABLE_ROOT, 'engine', 'runtime_engine.exe'),
  ].filter(Boolean);

  return getExistingPath(candidates) || candidates[0] || 'runtime_engine.exe';
}

function resolveInstanceId() {
  if (process.env.WORKSPACE_INSTANCE_ID) {
    return String(process.env.WORKSPACE_INSTANCE_ID);
  }
  if (path.basename(INSTANCE_ROOT).toLowerCase() === 'runtime') {
    return path.basename(path.dirname(INSTANCE_ROOT));
  }
  return path.basename(INSTANCE_ROOT) || `electron-${Date.now()}`;
}

function buildEngineInvocation(args) {
  if (app.isPackaged) {
    return {
      command: getEngineExecutable(),
      args,
    };
  }
  return {
    command: PYTHON_COMMAND,
    args: [getPythonScript(), ...args],
  };
}

function totalConsoleInstancesRoot() {
  const parent = path.dirname(INSTANCE_ROOT);
  if (path.basename(parent).toLowerCase() === 'live_test_runs') {
    return parent;
  }
  if (path.basename(INSTANCE_ROOT).toLowerCase() === 'runtime') {
    return path.dirname(resolvePackageRoot());
  }
  return INSTANCE_ROOT;
}

function totalConsolePattern() {
  const parent = path.dirname(INSTANCE_ROOT);
  if (path.basename(parent).toLowerCase() === 'live_test_runs') {
    return path.basename(INSTANCE_ROOT);
  }
  return '*';
}

function totalConsoleScopeHash(scopeRoot) {
  return crypto
    .createHash('sha256')
    .update(path.resolve(scopeRoot).toLowerCase())
    .digest('hex')
    .slice(0, 24);
}

function totalConsoleMarkerPath(scopeRoot) {
  return path.join(
    app.getPath('temp'),
    'WorkspaceRuntimeV9',
    'total-console',
    totalConsoleScopeHash(scopeRoot),
    'total-console.json'
  );
}

function markerIsRecent(payload) {
  const startedAt = Date.parse(String(payload?.started_at || ''));
  if (!Number.isFinite(startedAt)) {
    return false;
  }
  return Date.now() - startedAt < 10000;
}

function writeTotalConsoleLaunchDiagnostic(payload) {
  if (!app.isPackaged) {
    return;
  }

  try {
    const diagnosticPath = path.join(INSTANCE_ROOT, 'state', 'total_console_launch.json');
    fs.mkdirSync(path.dirname(diagnosticPath), { recursive: true });
    fs.writeFileSync(
      diagnosticPath,
      JSON.stringify(
        {
          updated_at: new Date().toISOString(),
          ...payload,
        },
        null,
        2
      ),
      'utf8'
    );
  } catch (_ignored) {
    // Diagnostics must not block starting the backend worker.
  }
}

function getRootTotalConsoleLauncher() {
  return path.join(resolvePackageRoot(), 'open_total_console.cmd');
}

function quoteCmdArg(value) {
  return `"${String(value).replace(/"/g, '\\"')}"`;
}

function buildTotalConsoleFallbackCommand(instancesRoot, pattern, markerPath = '') {
  const invocation = buildEngineInvocation([
    'total-console',
    '--instances-root',
    instancesRoot,
    '--pattern',
    pattern,
    '--refresh-seconds',
    '10',
    '--discovery-seconds',
    '10',
    '--live-lines',
    '0',
    '--stream-interval-seconds',
    '1',
    '--stream-lines-per-tick',
    '1',
    '--event-scan-seconds',
    '10',
    '--singleton',
    ...(markerPath ? ['--singleton-marker', markerPath] : []),
  ]);
  return [quoteCmdArg(invocation.command), ...invocation.args.map(quoteCmdArg)].join(' ');
}

function readJsonFile(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    return null;
  }
}

function writeJsonAtomic(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tempPath = `${filePath}.tmp`;
  fs.writeFileSync(tempPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  fs.renameSync(tempPath, filePath);
}

async function ensureSingleTotalConsole() {
  const scopeRoot = totalConsoleInstancesRoot();
  const pattern = totalConsolePattern();
  const markerPath = totalConsoleMarkerPath(scopeRoot);
  if (fs.existsSync(markerPath)) {
    const marker = readJsonFile(markerPath);
    if (marker && isPidAlive(marker.pid)) {
      writeTotalConsoleLaunchDiagnostic({
        opened: false,
        alreadyRunning: true,
        pid: marker.pid || 0,
        markerPath,
      });
      return { opened: false, alreadyRunning: true, pid: marker.pid || 0 };
    }
    try {
      fs.unlinkSync(markerPath);
    } catch (error) {
      return { opened: false, error: error.message };
    }
  }

  try {
    const launcherPath = getRootTotalConsoleLauncher();
    if (app.isPackaged && fs.existsSync(launcherPath)) {
      writeTotalConsoleLaunchDiagnostic({
        opened: false,
        state: 'starting',
        launcher: 'shell.openPath',
        scriptPath: launcherPath,
        cwd: scopeRoot,
        markerPath,
      });

      const openError = await shell.openPath(launcherPath);
      if (openError) {
        writeTotalConsoleLaunchDiagnostic({
          opened: false,
          state: 'shell-open-error',
          launcher: 'shell.openPath',
          scriptPath: launcherPath,
          error: openError,
          markerPath,
        });
        return { opened: false, error: openError, scriptPath: launcherPath, markerPath };
      }

      writeTotalConsoleLaunchDiagnostic({
        opened: true,
        state: 'root-script-opened',
        launcher: 'shell.openPath',
        scriptPath: launcherPath,
        markerPath,
      });
      return { opened: true, launcher: 'shell.openPath', scriptPath: launcherPath, markerPath };
    }

    writeTotalConsoleLaunchDiagnostic({
      opened: false,
      state: 'starting',
      launcher: 'cmd.exe /k',
      instancesRoot: scopeRoot,
      pattern,
      cwd: scopeRoot,
      markerPath,
    });

    const commandLine = `chcp 65001 >nul && ${buildTotalConsoleFallbackCommand(scopeRoot, pattern, markerPath)}`;
    const child = spawn('cmd.exe', ['/d', '/c', 'start', '', '/D', resolvePackageRoot(), 'cmd.exe', '/k', commandLine], {
      cwd: resolvePackageRoot(),
      env: pythonEnv(),
      windowsHide: false,
      detached: true,
      stdio: 'ignore',
    });
    child.unref();

    writeTotalConsoleLaunchDiagnostic({
      opened: true,
      state: 'fallback-opened',
      launcher: 'cmd.exe /k',
      instancesRoot: scopeRoot,
      pattern,
      pid: child.pid || 0,
      markerPath,
    });
    return { opened: true, launcher: 'cmd.exe /k', pid: child.pid || 0, instancesRoot: scopeRoot, pattern, markerPath };
  } catch (error) {
    writeTotalConsoleLaunchDiagnostic({
      opened: false,
      state: 'spawn-throw',
      error: error.message,
      markerPath,
    });
    return { opened: false, error: error.message };
  }
}

async function startDetachedCustomerWorker(args) {
  const invocation = buildEngineInvocation(args);
  try {
    const child = spawn(invocation.command, invocation.args, {
      cwd: INSTANCE_ROOT,
      env: pythonEnv(),
      windowsHide: true,
      detached: true,
      stdio: 'ignore'
    });
    child.unref();
    return { started: true, detached: true, autoCloseUi: false, totalConsole: { opened: false, disabled: true } };
  } catch (error) {
    return { started: false, detached: true, autoCloseUi: false, error: error.message };
  }
}

ensureCustomerRuntimeLayout();

function activeRunLockInfo() {
  const lockPath = path.join(INSTANCE_ROOT, 'temp', 'run.lock');
  try {
    if (!fs.existsSync(lockPath)) {
      return { active: false, path: lockPath, pid: 0 };
    }
    const payload = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
    const pid = Number(payload.pid || 0);
    if (pid > 0 && isPidAlive(pid)) {
      return { active: true, path: lockPath, pid };
    }
    try {
      fs.unlinkSync(lockPath);
    } catch (_ignored) {
      // Best-effort stale lock cleanup.
    }
    return { active: false, path: lockPath, pid };
  } catch (error) {
    return { active: false, path: lockPath, pid: 0, error: error.message };
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1050,
    height: 655,
    minWidth: 720,
    minHeight: 655,
    center: true,
    show: false,
    title: 'Workspace Runtime V9.1',
    icon: APP_ICON_PATH,
    backgroundColor: '#050505',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.on('close', (event) => {
    if (app.isQuittingAfterUserConfirm) {
      return;
    }
    event.preventDefault();
    if (closeRequestSent || gracefulCloseInProgress) {
      return;
    }
    closeRequestSent = true;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('app:close-request');
    }
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.setZoomFactor(DEFAULT_ZOOM);
    mainWindow.webContents.setVisualZoomLevelLimits(MIN_ZOOM, MAX_ZOOM);
  });

  mainWindow.webContents.on('before-input-event', (event, input) => {
    const key = String(input.key || '').toLowerCase();
    if (!input.control) {
      return;
    }

    if (['+', '=', '-', '_', '0'].includes(key)) {
      mainWindow.webContents.setZoomFactor(DEFAULT_ZOOM);
      event.preventDefault();
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

function createMonitorWindow() {
  if (monitorWindow && !monitorWindow.isDestroyed()) {
    monitorWindow.show();
    monitorWindow.focus();
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.hide();
    }
    return { ok: true, opened: true, reused: true };
  }

  monitorWindow = new BrowserWindow({
    width: 389,
    height: 430,
    minWidth: 360,
    minHeight: 340,
    show: false,
    title: 'Workspace Runtime Board',
    icon: APP_ICON_PATH,
    backgroundColor: '#050505',
    autoHideMenuBar: true,
    alwaysOnTop: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
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
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.hide();
      }
    }
  });

  monitorWindow.webContents.on('did-finish-load', () => {
    if (monitorWindow && !monitorWindow.isDestroyed()) {
      monitorWindow.webContents.setZoomFactor(DEFAULT_ZOOM);
      monitorWindow.webContents.setVisualZoomLevelLimits(MIN_ZOOM, MAX_ZOOM);
    }
  });

  monitorWindow.loadFile(path.join(__dirname, 'monitor', 'index.html'));
  return { ok: true, opened: true, reused: false };
}


function parseJsonFromStdout(stdout) {
  const text = String(stdout || '').trim();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    // Continue searching; Python logs may appear before the JSON payload.
  }
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      return JSON.parse(lines[index]);
    } catch (error) {
      // Continue searching; Python logs may appear before the JSON line.
    }
  }
  return null;
}

function runPython(args) {
  return new Promise((resolve) => {
    let child;
    let invocation;
    try {
      invocation = buildEngineInvocation(args);
      child = spawn(invocation.command, invocation.args, {
        cwd: INSTANCE_ROOT,
        env: pythonEnv(),
        windowsHide: true
      });
    } catch (error) {
      resolve({ ok: false, code: -1, data: null, error: error.message, stdout: '', stderr: '' });
      return;
    }
    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });
    child.on('error', (error) => {
      resolve({ ok: false, code: -1, data: null, error: error.message, stderr });
    });
    child.on('close', (code) => {
      const data = parseJsonFromStdout(stdout);
      try {
        const diagnosticPath = path.join(INSTANCE_ROOT, 'state', 'engine_invocation.json');
        fs.mkdirSync(path.dirname(diagnosticPath), { recursive: true });
        fs.writeFileSync(
          diagnosticPath,
          JSON.stringify(
            {
              updated_at: new Date().toISOString(),
              command: invocation?.command || '',
              args: invocation?.args || [],
              cwd: INSTANCE_ROOT,
              code,
              parsed_json: Boolean(data),
              stdout_tail: stdout.slice(-4000),
              stderr_tail: stderr.slice(-4000),
            },
            null,
            2
          ),
          'utf8'
        );
      } catch (_ignored) {
        // Diagnostics must not block UI authorization checks.
      }
      resolve({ ok: code === 0, code, data, stdout, stderr });
    });
  });
}

function normalizeLicenseData(data) {
  if (!data || typeof data !== 'object') {
    return data;
  }
  const normalized = { ...data };
  if (typeof normalized.valid !== 'boolean') {
    normalized.valid = Boolean(normalized.ok);
  }
  if (!normalized.max_instances && normalized.max_concurrency) {
    normalized.max_instances = normalized.max_concurrency;
  }
  if (!normalized.max_concurrency && normalized.max_instances) {
    normalized.max_concurrency = normalized.max_instances;
  }
  const payload = normalized.payload && typeof normalized.payload === 'object' ? normalized.payload : null;
  if (payload) {
    if (!normalized.max_instances && payload.max_concurrency) {
      normalized.max_instances = payload.max_concurrency;
    }
    if (!normalized.max_concurrency && payload.max_concurrency) {
      normalized.max_concurrency = payload.max_concurrency;
    }
    if (!normalized.expires_at && payload.expires_at) {
      normalized.expires_at = payload.expires_at;
    }
  }
  const expiresAt = Number(normalized.expires_at || 0);
  if (!normalized.remaining_days && Number.isFinite(expiresAt) && expiresAt > 0) {
    normalized.remaining_days = Math.max(0, Math.ceil((expiresAt - Date.now() / 1000) / 86400));
  }
  return normalized;
}

function readPauseState() {
  const poolPath = path.join(INSTANCE_ROOT, 'state', 'phone_pool_state.json');
  const controlPath = path.join(INSTANCE_ROOT, 'state', 'pause_control.json');
  const payload = readJsonFile(poolPath) || {};
  const control = readJsonFile(controlPath) || {};
  const totalAvailable = Number(payload.total_available || 0);
  const totalPausedByUser = Number(payload.total_paused_by_user || 0);
  const pauseRequested = Boolean(
    control.pause_requested
    || control.stop_new_seed_requested
    || payload.pause_requested
    || payload.stop_new_seed_requested
  );
  return {
    root: INSTANCE_ROOT,
    poolPath,
    controlPath,
    poolExists: fs.existsSync(poolPath),
    controlExists: fs.existsSync(controlPath),
    pauseRequested,
    totalAvailable: Number.isFinite(totalAvailable) ? totalAvailable : 0,
    totalPausedByUser: Number.isFinite(totalPausedByUser) ? totalPausedByUser : 0,
    pauseRequestedAt: String(control.pause_requested_at || payload.pause_requested_at || ''),
    pauseReason: String(control.pause_reason || payload.pause_reason || ''),
    resumeRequestedAt: String(control.resume_requested_at || payload.resume_requested_at || ''),
  };
}

function withPauseVerification(result, expectedPaused) {
  const pauseState = readPauseState();
  const verified = expectedPaused
    ? pauseState.pauseRequested
    : !pauseState.pauseRequested;
  return {
    ...result,
    pauseState,
    pauseVerified: verified,
    ok: Boolean(result.ok && verified),
    error: result.ok && !verified
      ? expectedPaused
        ? `暂停未落到当前运行目录：${pauseState.root}；available=${pauseState.totalAvailable}，pause=${pauseState.pauseRequested}`
        : `恢复未落到当前运行目录：${pauseState.root}；pause=${pauseState.pauseRequested}`
      : result.error,
  };
}

function loadRuntimeConfig() {
  const configPath = path.join(INSTANCE_ROOT, 'config', 'app_config.json');
  const defaultConfigPath = getExistingPath([
    path.join(RESOURCES_ROOT, 'default_config', 'app_config.json'),
    path.join(RESOURCES_ROOT, 'config_templates', 'customer_provider_app_config.json'),
    path.join(APP_ROOT, 'config_templates', 'customer_provider_app_config.json'),
  ]);
  let defaultConfig = {};
  if (defaultConfigPath) {
    try {
      defaultConfig = readJsonPath(defaultConfigPath);
    } catch (error) {
      defaultConfig = {};
    }
  }
  try {
    const runtimeConfig = readJsonPath(configPath);
    const merged = deepMergeConfig(defaultConfig, runtimeConfig);
    merged.input_file = canonicalInstanceInputFile();
    return merged;
  } catch (error) {
    defaultConfig.input_file = canonicalInstanceInputFile();
    return defaultConfig;
  }
}

function loadPackagedDefaultConfig() {
  const defaultConfigPath = getExistingPath([
    path.join(RESOURCES_ROOT, 'default_config', 'app_config.json'),
    path.join(RESOURCES_ROOT, 'config_templates', 'customer_provider_app_config.json'),
    path.join(APP_ROOT, 'config_templates', 'customer_provider_app_config.json'),
  ]);
  if (!defaultConfigPath) {
    return {};
  }
  try {
    return readJsonPath(defaultConfigPath);
  } catch (error) {
    return {};
  }
}

function repairRuntimeConfigFromPackagedDefault(config) {
  const packagedDefault = loadPackagedDefaultConfig();
  if (!packagedDefault || Object.keys(packagedDefault).length === 0) {
    return config || {};
  }
  const processing = config?.processing || {};
  const defaultProcessing = packagedDefault.processing || {};
  const runtimeLooksTruncated = !config?.processing || (
    Boolean(defaultProcessing.direct_phone_search_only)
    && processing.direct_phone_search_only !== true
  );
  if (!runtimeLooksTruncated) {
    return config;
  }
  return deepMergeConfig(packagedDefault, config || {});
}

function saveRuntimeConfig(config) {
  const configPath = path.join(INSTANCE_ROOT, 'config', 'app_config.json');
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, 'utf8');
}

function canonicalInstanceInputFile() {
  return path.basename(INSTANCE_ROOT).toLowerCase() === 'runtime' ? '../input.txt' : 'input.txt';
}

function normalizeTargetSource(value) {
  const raw = String(value || 'F').trim().toUpperCase();
  if (raw === 'T') {
    return 'T';
  }
  if (raw === 'P') {
    return 'P';
  }
  return 'F';
}

function setRuntimeTargetSource(value) {
  const targetSource = normalizeTargetSource(value);
  const config = repairRuntimeConfigFromPackagedDefault(loadRuntimeConfig());
  config.runtime = config.runtime || {};
  config.runtime.target_source = targetSource;
  config.input_file = canonicalInstanceInputFile();
  saveRuntimeConfig(config);
  return { ok: true, targetSource };
}

function runtimeDiagnosticModeEnabled() {
  const config = loadRuntimeConfig();
  return Boolean(
    (config.runtime && config.runtime.diagnostic_mode) ||
    (config.logging && config.logging.diagnostic_events_enabled)
  );
}

function setRuntimeDiagnosticMode(enabled) {
  const config = loadRuntimeConfig();
  config.runtime = config.runtime || {};
  config.logging = config.logging || {};
  const value = Boolean(enabled);
  config.runtime.diagnostic_mode = value;
  config.logging.diagnostic_events_enabled = value;
  config.logging.scheduler_samples_enabled = value;
  config.logging.verbose_stage_events_enabled = value;
  config.input_file = canonicalInstanceInputFile();
  saveRuntimeConfig(config);
  return { ok: true, enabled: value };
}

function isPathInside(candidatePath, rootPath) {
  const relative = path.relative(path.resolve(rootPath), path.resolve(candidatePath));
  return relative === '' || Boolean(relative && !relative.startsWith('..') && !path.isAbsolute(relative));
}

function resolveConfiguredInputPath(config = loadRuntimeConfig()) {
  const inputFile = canonicalInstanceInputFile();
  const targetPath = path.resolve(INSTANCE_ROOT, inputFile);
  const packageRoot = resolvePackageRoot();
  if (!isPathInside(targetPath, INSTANCE_ROOT) && !isPathInside(targetPath, packageRoot)) {
    throw new Error(`input_file is outside the allowed instance folder: ${inputFile}`);
  }
  return targetPath;
}

function countInputRows(filePath) {
  try {
    return fs
      .readFileSync(filePath, 'utf8')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean).length;
  } catch (error) {
    return 0;
  }
}

function resolvePackageInputPath(fileName) {
  return path.resolve(resolvePackageRoot(), fileName);
}

function readInputDistributionStatus() {
  const candidates = [
    path.join(INSTANCE_ROOT, 'state', 'input_distribution.json'),
    path.join(resolvePackageRoot(), 'runtime', 'state', 'input_distribution.json'),
  ];
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) {
        return JSON.parse(fs.readFileSync(candidate, 'utf8'));
      }
    } catch (error) {
      return {};
    }
  }
  return {};
}

function writeInputDistributionStatus(payload = {}) {
  const statePath = path.join(INSTANCE_ROOT, 'state', 'input_distribution.json');
  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  fs.writeFileSync(
    statePath,
    JSON.stringify(
      {
        updated_at: new Date().toISOString(),
        ...payload,
      },
      null,
      2,
    ),
    'utf8',
  );
}

function resetInputRuntimeState() {
  const stateDir = path.join(INSTANCE_ROOT, 'state');
  const names = [
    'input_cursor.json',
    'input_queue_summary.json',
    'requeue_pool.jsonl',
    'requeue_seen.json',
    'phone_pool_state.json',
    'tps_smart_session_customer_phone_pool.json',
  ];
  const removed = [];
  for (const name of names) {
    const target = path.join(stateDir, name);
    try {
      if (fs.existsSync(target)) {
        fs.unlinkSync(target);
        removed.push(name);
      }
    } catch (_err) {
      // Best effort: stale queue files should not block importing a fresh input file.
    }
  }
  return removed;
}

function suggestedInputFileName() {
  const instanceId = resolveInstanceId();
  const match = String(instanceId || '').match(/(\d+)$/);
  return match ? `input${match[1]}.txt` : 'input.txt';
}

function inputFileStatus() {
  const config = loadRuntimeConfig();
  const inputFile = canonicalInstanceInputFile();
  const tDualAInputFile = '号码补齐父级input.txt';
  const tDualBInputFile = '裂变关联人父级input.txt';
  const tDualAPath = resolvePackageInputPath(tDualAInputFile);
  const tDualBPath = resolvePackageInputPath(tDualBInputFile);
  let targetPath = '';
  let exists = false;
  let rowCount = 0;
  const tDualAExists = fs.existsSync(tDualAPath);
  const tDualBExists = fs.existsSync(tDualBPath);
  const tDualARowCount = tDualAExists ? countInputRows(tDualAPath) : 0;
  const tDualBRowCount = tDualBExists ? countInputRows(tDualBPath) : 0;
  const tDualTotalRows = tDualARowCount + tDualBRowCount;
  let distribution = {};
  let error = '';
  try {
    targetPath = resolveConfiguredInputPath(config);
    exists = fs.existsSync(targetPath);
    rowCount = exists ? countInputRows(targetPath) : 0;
    distribution = readInputDistributionStatus();
  } catch (err) {
    error = err.message;
  }
  const importedRows = Number(distribution.imported_rows || 0);
  const totalRows = Number(distribution.total_rows || rowCount || 0);
  return {
    input_file: inputFile,
    target_path: targetPath,
    exists,
    row_count: rowCount,
    imported_rows: importedRows,
    total_rows: totalRows,
    t_dual_a_input_file: tDualAInputFile,
    t_dual_b_input_file: tDualBInputFile,
    t_dual_a_target_path: tDualAPath,
    t_dual_b_target_path: tDualBPath,
    t_dual_a_exists: tDualAExists,
    t_dual_b_exists: tDualBExists,
    t_dual_a_row_count: tDualARowCount,
    t_dual_b_row_count: tDualBRowCount,
    t_dual_total_rows: tDualTotalRows,
    suggested_file_name: suggestedInputFileName(),
    instance_id: resolveInstanceId(),
    error,
  };
}

async function importInputFile() {
  const beforeStatus = inputFileStatus();
  const result = await dialog.showOpenDialog(mainWindow, {
    title: `选择号码文件（建议 ${beforeStatus.suggested_file_name}）`,
    properties: ['openFile'],
    filters: [
      { name: 'Text files', extensions: ['txt'] },
      { name: 'All files', extensions: ['*'] },
    ],
  });
  if (result.canceled || !result.filePaths.length) {
    return { ok: false, canceled: true, input_status: beforeStatus };
  }

  const sourcePath = result.filePaths[0];
  const targetPath = resolveConfiguredInputPath();
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.copyFileSync(sourcePath, targetPath);
  const rowCount = countInputRows(targetPath);
  const resetStateFiles = resetInputRuntimeState();
  writeInputDistributionStatus({
    input_file: path.relative(resolvePackageRoot(), targetPath),
    imported_rows: rowCount,
    total_rows: rowCount,
    input_txt_file_names: [path.basename(sourcePath)],
    reset_input_state_files: resetStateFiles,
  });

  return {
    ok: true,
    canceled: false,
    source_path: sourcePath,
    source_name: path.basename(sourcePath),
    target_path: targetPath,
    input_status: inputFileStatus(),
  };
}

function sanitizeSlotPart(value) {
  return String(value || 'unknown').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 80) || 'unknown';
}

function isPidAlive(pid) {
  const parsed = Number(pid);
  if (!Number.isInteger(parsed) || parsed < 1) {
    return false;
  }
  try {
    process.kill(parsed, 0);
    return true;
  } catch (error) {
    return error.code === 'EPERM';
  }
}

function cleanupDeadSlots(slotDir) {
  let entries = [];
  try {
    entries = fs.readdirSync(slotDir, { withFileTypes: true });
  } catch (error) {
    return;
  }

  for (const entry of entries) {
    if (!entry.isFile() || !/^slot-\d+\.json$/.test(entry.name)) {
      continue;
    }
    const slotPath = path.join(slotDir, entry.name);
    try {
      const slot = JSON.parse(fs.readFileSync(slotPath, 'utf8'));
      if (!isPidAlive(slot.pid)) {
        fs.unlinkSync(slotPath);
      }
    } catch (error) {
      try {
        fs.unlinkSync(slotPath);
      } catch (_ignored) {
        // Another process may have claimed or removed it.
      }
    }
  }
}

function releaseLicenseSlot() {
  if (!licenseSlot) {
    return;
  }
  try {
    fs.unlinkSync(licenseSlot.path);
  } catch (error) {
    // Slot files are best-effort cleanup; stale slots are removed on next claim.
  }
  licenseSlot = null;
}

function claimLicenseSlot(status) {
  if (!status || !status.valid) {
    return status;
  }

  const requestedMaxInstances = Number(status.max_instances || 1);
  const maxInstances = Number.isFinite(requestedMaxInstances)
    ? Math.max(1, Math.floor(requestedMaxInstances))
    : 1;
  const product = sanitizeSlotPart(status.product || 'WORKSPACE');
  const machineCode = sanitizeSlotPart(status.machine_code || 'unknown-machine');
  const licenseId = sanitizeSlotPart(status.license_id || status.license_machine_code || machineCode);
  const slotDir = path.join(app.getPath('temp'), 'WorkspaceRuntimeV9', 'license-slots', product, machineCode, licenseId);

  if (licenseSlot && licenseSlot.slotDir === slotDir) {
    return {
      ...status,
      max_instances: maxInstances,
      active_slot: licenseSlot.index,
    };
  }

  releaseLicenseSlot();
  fs.mkdirSync(slotDir, { recursive: true });
  cleanupDeadSlots(slotDir);

  for (let index = 1; index <= maxInstances; index += 1) {
    const slotPath = path.join(slotDir, `slot-${index}.json`);
    let handle = null;
    try {
      handle = fs.openSync(slotPath, 'wx');
      const payload = {
        pid: process.pid,
        started_at: new Date().toISOString(),
        app_root: APP_ROOT,
        instance_root: INSTANCE_ROOT,
        slot: index,
        max_instances: maxInstances,
      };
      fs.writeFileSync(handle, JSON.stringify(payload, null, 2), 'utf8');
      fs.closeSync(handle);
      licenseSlot = { path: slotPath, slotDir, index };
      return {
        ...status,
        max_instances: maxInstances,
        active_slot: index,
      };
    } catch (error) {
      if (handle !== null) {
        try {
          fs.closeSync(handle);
        } catch (_ignored) {
          // Ignore close errors on failed slot writes.
        }
      }
      if (error.code !== 'EEXIST') {
        return {
          ...status,
          valid: false,
          reason: `授权并发数占用失败: ${error.message}`,
          max_instances: maxInstances,
        };
      }
    }
  }

  return {
    ...status,
    valid: false,
    reason: `授权并发数已达上限（允许 ${maxInstances} 并发）`,
    max_instances: maxInstances,
  };
}

async function loadMachineCodeFallback() {
  const result = await runPython(['machine-code']);
  return result.data?.machine_code || '';
}

async function startEngineWorker(targetSourceValue) {
  if (engineProcess && !engineProcess.killed) {
    return {
      started: false,
      alreadyRunning: true,
      duplicateWindow: true,
      message: '本窗口已经打开，请勿重复打开。',
    };
  }

  const runLock = activeRunLockInfo();
  if (runLock.active) {
    return {
      started: false,
      alreadyRunning: true,
      duplicateWindow: true,
      pid: runLock.pid,
      message: '本窗口已经打开，请勿重复打开。',
    };
  }

  await runPython(['resume-run', '--root', INSTANCE_ROOT, '--storage', 'auto']);

  const targetSource = normalizeTargetSource(targetSourceValue || loadRuntimeConfig().runtime?.target_source || 'F');
  setRuntimeTargetSource(targetSource);
  const config = loadRuntimeConfig();
  const runtime = config.runtime || {};
  const instanceId = app.isPackaged ? resolveInstanceId() : `electron-${Date.now()}`;
  const runArgs = ['run', '--root', INSTANCE_ROOT, '--instance-id', instanceId, '--target-source', targetSource];
  if (app.isPackaged || runtime.enable_network === true) {
    runArgs.push('--enable-network');
  }
  const invocation = buildEngineInvocation(runArgs);

  if (app.isPackaged) {
    const result = await startDetachedCustomerWorker(runArgs);
    return {
      ...result,
      instanceId,
      console: false,
      targetSource,
    };
  }
  
  engineProcess = spawn(invocation.command, invocation.args, {
    cwd: INSTANCE_ROOT,
    env: pythonEnv(),
    windowsHide: runtime.hide_backend_console_in_production !== false
  });
  engineProcess.stdout.on('data', (chunk) => {
    if (mainWindow) {
      mainWindow.webContents.send('engine:stdout', chunk.toString('utf8'));
    }
  });
  engineProcess.stderr.on('data', (chunk) => {
    if (mainWindow) {
      mainWindow.webContents.send('engine:stderr', chunk.toString('utf8'));
    }
  });
  engineProcess.on('close', (code) => {
    if (mainWindow) {
      mainWindow.webContents.send('engine:exit', { code });
    }
    engineProcess = null;
  });
  const totalConsole = await ensureSingleTotalConsole();
  return { started: true, console: false, instanceId, targetSource, totalConsole };
}

function startDemoWorker() {
  if (engineProcess && !engineProcess.killed) {
    return { started: false, alreadyRunning: true };
  }

  const instanceId = `electron-demo-${Date.now()}`;
  const invocation = buildEngineInvocation(['demo-run', '--root', INSTANCE_ROOT, '--instance-id', instanceId]);

  engineProcess = spawn(invocation.command, invocation.args, {
    cwd: INSTANCE_ROOT,
    env: pythonEnv(),
    windowsHide: true
  });
  engineProcess.stdout.on('data', (chunk) => {
    if (mainWindow) {
      mainWindow.webContents.send('engine:stdout', chunk.toString('utf8'));
    }
  });
  engineProcess.stderr.on('data', (chunk) => {
    if (mainWindow) {
      mainWindow.webContents.send('engine:stderr', chunk.toString('utf8'));
    }
  });
  engineProcess.on('close', (code) => {
    if (mainWindow) {
      mainWindow.webContents.send('engine:exit', { code });
    }
    engineProcess = null;
  });
  return { started: true, console: false, instanceId, demoMode: true };
}

async function pauseEngineWorker() {
  const result = await runPython([
    'pause-run',
    '--root',
    INSTANCE_ROOT,
    '--storage',
    'auto',
    '--enforce-seconds',
    '5',
    '--interval-seconds',
    '1',
  ]);
  const verified = withPauseVerification(result, true);
  return {
    ...verified,
    paused: Boolean(verified.ok && verified.pauseVerified),
  };
}

async function resumeEngineWorker() {
  const result = await runPython(['resume-run', '--root', INSTANCE_ROOT, '--storage', 'auto']);
  const verified = withPauseVerification(result, false);
  return {
    ...verified,
    paused: false,
    resumed: Boolean(verified.ok && verified.pauseVerified),
  };
}

function tailRuntimeLog(maxLines = 160) {
  const logPath = path.join(INSTANCE_ROOT, 'logs', 'runtime.log');
  try {
    const content = fs.readFileSync(logPath, 'utf8');
    return content.split(/\r?\n/).slice(-maxLines).join('\n');
  } catch (error) {
    return '';
  }
}

function readResults(kind = 'main', maxLines = 80) {
  const relativePath = kind === 'demo'
    ? path.join('output', 'demo_results.csv')
    : path.join('output', 'results.csv');
  const resultPath = path.join(INSTANCE_ROOT, relativePath);
  try {
    const content = fs.readFileSync(resultPath, 'utf8');
    const lines = content.split(/\r?\n/).filter((line) => line.trim());
    const previewLines = lines.slice(0, Number(maxLines) || 80);
    return {
      ok: true,
      kind,
      path: resultPath,
      exists: true,
      lineCount: lines.length,
      dataRows: Math.max(0, lines.length - 1),
      preview: previewLines.join('\n')
    };
  } catch (error) {
    return {
      ok: false,
      kind,
      path: resultPath,
      exists: false,
      lineCount: 0,
      dataRows: 0,
      preview: '',
      error: error.message
    };
  }
}

function resolveRuntimeOutputPath(status, fallbackRelativePath = path.join('output', 'results.csv')) {
  const outputs = status && typeof status === 'object' ? status.outputs || {} : {};
  const csvFile = outputs.csv_file || outputs.csv || fallbackRelativePath;
  if (path.isAbsolute(String(csvFile))) {
    return String(csvFile);
  }
  return path.join(INSTANCE_ROOT, String(csvFile));
}

function countCsvDataRows(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split(/\r?\n/).filter((line) => line.trim());
    return Math.max(0, lines.length - 1);
  } catch (error) {
    return 0;
  }
}

function readJsonSafe(filePath, fallback = {}) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    return fallback;
  }
}

function parseEventTimeMs(value) {
  const parsed = Date.parse(String(value || ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function readRecentEvents(windowMs = 60 * 1000) {
  if (!runtimeDiagnosticModeEnabled()) {
    return [];
  }
  const eventsPath = path.join(INSTANCE_ROOT, 'state', 'events.jsonl');
  try {
    const stat = fs.statSync(eventsPath);
  const maxBytes = 1024 * 1024;
    const readBytes = Math.min(stat.size, maxBytes);
    const buffer = Buffer.alloc(readBytes);
    const fd = fs.openSync(eventsPath, 'r');
    try {
      fs.readSync(fd, buffer, 0, readBytes, Math.max(0, stat.size - readBytes));
    } finally {
      fs.closeSync(fd);
    }
    const lines = buffer.toString('utf8').split(/\r?\n/).filter((line) => line.trim());
    const events = [];
    let latestMs = 0;
    for (const line of lines) {
      try {
        const event = JSON.parse(line);
        const timeMs = parseEventTimeMs(event.time);
        if (!timeMs) {
          continue;
        }
        latestMs = Math.max(latestMs, timeMs);
        events.push({ ...event, timeMs });
      } catch (error) {
        // Ignore partially written or truncated JSONL rows.
      }
    }
    const referenceMs = latestMs || Date.now();
    const cutoffMs = referenceMs - windowMs;
    return events.filter((event) => event.timeMs >= cutoffMs);
  } catch (error) {
    return [];
  }
}

function numberValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function reqStatus(event) {
  const direct = numberValue(event.status_code || event.target_status_code || event.http_status_code, NaN);
  if (Number.isFinite(direct) && direct > 0) {
    return direct;
  }
  const match = String(event.message || '').match(/\bstatus=([0-9]{3})\b/);
  return match ? Number(match[1]) : 0;
}

function eventIsAdvanceable(event) {
  if (typeof event.chain_advanceable === 'boolean') {
    return event.chain_advanceable;
  }
  return /\badvance=true\b/.test(String(event.message || ''));
}

function formatMetricPercent(value) {
  if (!Number.isFinite(value)) {
    return '--';
  }
  return `${value.toFixed(1)}%`;
}

function circuitBreakerDetected(status, recentEvents) {
  const errorText = String(status.last_error || status.error || status.circuit_breaker_reason || '');
  if (/熔断|连续502|502_CIRCUIT_BREAKER|circuit_breaker/i.test(errorText)) {
    return true;
  }
  return recentEvents.some((event) => {
    const eventName = String(event.event || '');
    const message = String(event.message || event.failure_stage || '');
    return /PROVIDER_502_CIRCUIT_BREAKER|502_CIRCUIT_BREAKER/i.test(eventName) ||
      /熔断|连续502|502_CIRCUIT_BREAKER|circuit_breaker/i.test(message);
  });
}

function runtimeTerminalReason(status, recentEvents) {
  if (circuitBreakerDetected(status, recentEvents)) {
    return 'circuit_breaker';
  }
  const raw = String(status.status || '').toLowerCase();
  if (raw === 'completed') {
    return 'completed';
  }
  if (raw === 'failed') {
    return 'failed';
  }
  return '';
}

function runtimeStateText(status, successRate, badRate, terminalReason = '') {
  if (terminalReason === 'circuit_breaker') {
    return { text: '502熔断', level: 'bad' };
  }
  const raw = String(status.status || '').toLowerCase();
  if (raw === 'completed') {
    return { text: '已完成', level: 'good' };
  }
  if (raw === 'failed') {
    return { text: '异常停止', level: 'bad' };
  }
  if (raw.includes('pause')) {
    return { text: '已暂停', level: 'warn' };
  }
  const updatedAt = parseEventTimeMs(status.updated_at);
  if (updatedAt && Date.now() - updatedAt > 90 * 1000 && raw === 'running') {
    return { text: '状态停滞', level: 'warn' };
  }
  if (Number.isFinite(successRate) && successRate < 95) {
    return { text: '压力偏高', level: 'bad' };
  }
  if (Number.isFinite(badRate) && badRate >= 10) {
    return { text: '降速观察', level: 'warn' };
  }
  if (raw === 'running') {
    return { text: '标准运行', level: 'good' };
  }
  return { text: '待启动', level: 'warn' };
}

function runtimeMetrics() {
  const statusPath = path.join(INSTANCE_ROOT, 'state', 'status.json');
  const status = readJsonSafe(statusPath, {});
  const diagnosticMode = runtimeDiagnosticModeEnabled();
  const recentEvents = diagnosticMode ? readRecentEvents(60 * 1000) : [];
  const reqEvents = recentEvents.filter((event) => event.event === 'REQ');
  const saveEvents = recentEvents.filter((event) => event.event === 'SAVE');
  const statusCodes = reqEvents.map(reqStatus);
  const requestCount = diagnosticMode && reqEvents.length
    ? reqEvents.length
    : Math.round(numberValue(status.provider_request_rate_per_minute, 0));
  const saveCount = diagnosticMode && saveEvents.length
    ? saveEvents.length
    : Math.round(numberValue(status.rate_per_minute, 0));
  const raw502Count = diagnosticMode && statusCodes.length
    ? statusCodes.filter((code) => code === 502).length
    : Math.round(numberValue(status.provider_502_30s_count, 0));
  let finalSuccessCount = 0;
  let finalFailureCount = 0;
  if (diagnosticMode && reqEvents.length) {
    reqEvents.forEach((event, index) => {
      const code = statusCodes[index];
      if (code === 200 || code === 404 || (code === 502 && eventIsAdvanceable(event))) {
        finalSuccessCount += 1;
        return;
      }
      if (code === 502) {
        finalFailureCount += 1;
      }
    });
  } else {
    const statusWindowCount = Math.round(numberValue(status.provider_request_30s_count || status.provider_request_count, 0));
    const status502Count = Math.round(numberValue(status.provider_502_30s_count, 0));
    finalSuccessCount = Math.max(0, statusWindowCount - status502Count);
    finalFailureCount = Math.max(0, status502Count);
  }
  const finalTotal = finalSuccessCount + finalFailureCount;
  const successRate = finalTotal ? (finalSuccessCount / finalTotal) * 100 : NaN;
  const badRate = requestCount ? (raw502Count / requestCount) * 100 : 0;
  const doCurrent = numberValue(status.do_inflight_current || status.scheduler_do_inflight_current, 0);
  const doLimit = numberValue(
    status.do_inflight_hard_limit ||
      status.do_inflight_target ||
      status.scheduler_do_inflight_target ||
      status.authorized_concurrency,
    0
  );
  const remaining = numberValue(
    status.remaining_work !== undefined ? status.remaining_work : status.remaining,
    0
  );
  const statusSavedTotal = Math.trunc(numberValue(status.saved, 0));
  const savedTotal = diagnosticMode
    ? Math.max(countCsvDataRows(resolveRuntimeOutputPath(status)), statusSavedTotal)
    : statusSavedTotal;
  const completedTotal = Math.trunc(numberValue(status.customer_completed_seeds, 0));
  const activeSeeds = Math.trunc(numberValue(status.active_seeds, 0));
  const activeChains = Math.trunc(numberValue(status.active_chain_sessions_current, 0));
  const schedulerAliveWorkers = Math.trunc(numberValue(status.scheduler_alive_workers, 0));
  const warmExpiredTotal = Math.max(
    Math.trunc(numberValue(status.warm_pool_factory_expired_total, 0)),
    0
  );
  const creditCostTotal = Math.trunc(numberValue(status.provider_credit_cost_total, 0));
  const http502RetrySuccessTotal = Math.trunc(numberValue(status.http_502_retry_success_total, 0));
  const http502RetryFailedTotal = Math.trunc(numberValue(status.http_502_retry_failed_total, 0));
  const providerElapsedAvg = Math.trunc(numberValue(status.provider_elapsed_avg_ms, 0));
  const providerElapsedP95 = Math.trunc(numberValue(status.provider_elapsed_p95_ms, 0));
  const providerStageWaitAvg = Math.trunc(numberValue(status.provider_stage_wait_avg_ms, 0));
  const providerDoWaitAvg = Math.trunc(numberValue(status.provider_do_wait_avg_ms, 0));
  const providerOutboundAvg = Math.trunc(numberValue(status.provider_outbound_elapsed_avg_ms, 0));
  const providerWarmupAvg = Math.trunc(numberValue(status.provider_warmup_elapsed_avg_ms, 0));
  const providerResultphoneAvg = Math.trunc(numberValue(status.provider_resultphone_elapsed_avg_ms, 0));
  const terminalReason = runtimeTerminalReason(status, recentEvents);
  const stateInfo = runtimeStateText(status, successRate, badRate, terminalReason);
  return {
    ok: true,
    root: INSTANCE_ROOT,
    generatedAt: new Date().toISOString(),
    windowSeconds: 60,
    values: {
      requestRate: `${requestCount}/min`,
      saveRate: `${saveCount}/min`,
      accessSuccessRate: formatMetricPercent(successRate),
      bad502Rate: formatMetricPercent(badRate),
      doInflight: `${doCurrent}/${doLimit}`,
      remaining: String(Math.max(0, Math.trunc(remaining))),
      savedTotal: String(savedTotal),
      completedTotal: String(completedTotal),
      creditCostTotal: String(Math.max(0, creditCostTotal)),
      http502RetryTotal: `${Math.max(0, http502RetrySuccessTotal)}/${Math.max(0, http502RetryFailedTotal)}`,
      warmExpiredTotal: String(warmExpiredTotal),
      localWaitSplit: `${providerStageWaitAvg}/${providerDoWaitAvg}ms`,
      requestLatency: `${providerElapsedAvg}/${providerElapsedP95}ms`,
      outboundLatency: `${providerOutboundAvg}ms`,
      pageLatencySplit: `${providerWarmupAvg}/${providerResultphoneAvg}ms`,
      runtimeState: stateInfo.text,
    },
    terminalReason,
    levels: {
      accessSuccessRate: !Number.isFinite(successRate) ? 'warn' : successRate >= 99 ? 'good' : successRate >= 95 ? 'warn' : 'bad',
      bad502Rate: badRate < 5 ? 'good' : badRate < 10 ? 'warn' : 'bad',
      runtimeState: stateInfo.level,
    },
    raw: {
      requestCount,
      saveCount,
      finalSuccessCount,
      finalFailureCount,
      raw502Count,
      savedTotal,
      completedTotal,
      creditCostTotal,
      http502RetrySuccessTotal,
      http502RetryFailedTotal,
      activeSeeds,
      activeChains,
      schedulerAliveWorkers,
      warmExpiredTotal,
      providerElapsedAvg,
      providerElapsedP95,
      providerStageWaitAvg,
      providerDoWaitAvg,
      providerOutboundAvg,
      providerWarmupAvg,
      providerResultphoneAvg,
      doCurrent,
      doLimit,
      remaining,
      status,
      diagnosticMode,
    },
  };
}

function activeRuntimeWorkCount() {
  const lock = activeRunLockInfo();
  if (!lock.active && !(engineProcess && !engineProcess.killed)) {
    return 0;
  }
  const metrics = runtimeMetrics();
  const raw = metrics.raw || {};
  return Math.max(
    0,
    Math.trunc(numberValue(raw.activeChains, 0)),
    Math.trunc(numberValue(raw.schedulerAliveWorkers, 0)),
    Math.trunc(numberValue(raw.doCurrent, 0))
  );
}

function sleepMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms || 0))));
}

async function waitForRuntimeIdle(timeoutMs = 30 * 60 * 1000) {
  const deadline = Date.now() + Math.max(1, Number(timeoutMs || 1));
  let lastActive = activeRuntimeWorkCount();
  while (Date.now() < deadline) {
    lastActive = activeRuntimeWorkCount();
    if (lastActive <= 0) {
      return { idle: true, active: 0 };
    }
    await sleepMs(2000);
  }
  return { idle: false, active: lastActive };
}

function terminateBackendProcess() {
  const lock = activeRunLockInfo();
  const pids = new Set();
  if (engineProcess && !engineProcess.killed && engineProcess.pid) {
    pids.add(Number(engineProcess.pid));
  }
  if (lock.active && lock.pid > 0) {
    pids.add(Number(lock.pid));
  }
  for (const pid of pids) {
    try {
      process.kill(pid);
    } catch (_ignored) {
      // The process may already have exited after draining work.
    }
  }
}

async function gracefulCloseApp() {
  if (gracefulCloseInProgress) {
    return { ok: true, closing: true };
  }
  gracefulCloseInProgress = true;
  closeRequestSent = true;
  try {
    await pauseEngineWorker();
  } catch (_ignored) {
    // Closing should continue even if there is no active runtime to pause.
  }
  await waitForRuntimeIdle();
  terminateBackendProcess();
  app.isQuittingAfterUserConfirm = true;
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.destroy();
  }
  app.quit();
  return { ok: true, closing: true };
}

ipcMain.handle('runtime:info', async () => {
  const result = await runPython(['runtime-info', '--root', INSTANCE_ROOT]);
  if (!result.data) {
    result.data = {
      root: INSTANCE_ROOT,
      machine_code: '',
      runtime: loadRuntimeConfig().runtime || {},
      input_file: loadRuntimeConfig().input_file || 'input.txt',
      app_name: loadRuntimeConfig().app_name || 'Workspace Runtime V9.1',
      preview_completion_modal: process.env.WORKSPACE_PREVIEW_COMPLETION_MODAL === '1'
    };
  } else {
    result.data.preview_completion_modal = process.env.WORKSPACE_PREVIEW_COMPLETION_MODAL === '1';
  }
  if (!result.data.machine_code) {
    result.data.machine_code = await loadMachineCodeFallback();
  }
  return {
    ...result,
    instanceRoot: INSTANCE_ROOT,
    appRoot: APP_ROOT,
    packageRoot: resolvePackageRoot(),
    inputStatus: inputFileStatus(),
  };
});

ipcMain.handle('license:status', async () => {
  const pythonResult = await runPython(['license-status', '--root', INSTANCE_ROOT]);
  if (pythonResult.data) {
    pythonResult.data = normalizeLicenseData(pythonResult.data);
    if (pythonResult.data.valid) {
      if (app.isPackaged) {
        return pythonResult;
      }
      const data = claimLicenseSlot(pythonResult.data);
      return {
        ...pythonResult,
        ok: data.valid,
        code: data.valid ? pythonResult.code : 5,
        data,
      };
    }
    return pythonResult;
  }
  return {
    ok: false,
    code: pythonResult.code || -1,
    data: null,
    stdout: pythonResult.stdout || '',
    stderr: pythonResult.stderr || pythonResult.error || 'Python 授权状态不可用'
  };
});

ipcMain.handle('license:activate', async (_event, code) => {
  const licenseCode = String(code || '');
  const pythonResult = await runPython(['activate', '--root', INSTANCE_ROOT, '--code', licenseCode]);
  if (pythonResult.data) {
    pythonResult.data = normalizeLicenseData(pythonResult.data);
  }
  if (pythonResult.data && pythonResult.data.valid) {
    if (app.isPackaged) {
      return pythonResult;
    }
    const data = claimLicenseSlot(pythonResult.data);
    return {
      ...pythonResult,
      ok: data.valid,
      code: data.valid ? pythonResult.code : 5,
      data,
    };
  }
  return pythonResult.data
    ? pythonResult
    : {
        ok: false,
        code: pythonResult.code || -1,
        data: null,
        stdout: pythonResult.stdout || '',
        stderr: pythonResult.stderr || pythonResult.error || 'Python 授权激活不可用'
      };
});

ipcMain.handle('clipboard:write', async (_event, value) => {
  clipboard.writeText(String(value || ''));
  return { ok: true };
});

ipcMain.handle('target:set', async (_event, value) => {
  try {
    return setRuntimeTargetSource(value);
  } catch (error) {
    return { ok: false, error: error.message };
  }
});

ipcMain.handle('diagnostic:status', async () => ({ ok: true, enabled: runtimeDiagnosticModeEnabled() }));

ipcMain.handle('diagnostic:setEnabled', async (_event, enabled) => {
  try {
    return setRuntimeDiagnosticMode(enabled);
  } catch (error) {
    return { ok: false, enabled: runtimeDiagnosticModeEnabled(), error: error.message };
  }
});

ipcMain.handle('network:test', async () => {
  try {
    return await testNetworkQuality();
  } catch (error) {
    return {
      ok: false,
      quality: '差',
      canRun: false,
      error: error.message,
      recommendation: '当前网络差，建议不运行。'
    };
  }
});

ipcMain.handle('engine:activeRunLock', async () => activeRunLockInfo());

ipcMain.handle('engine:start', async (_event, targetSource) => {
  return startEngineWorker(targetSource);
});

ipcMain.handle('engine:pause', async () => {
  return pauseEngineWorker();
});

ipcMain.handle('engine:resume', async () => {
  return resumeEngineWorker();
});

ipcMain.handle('input:import', async () => {
  try {
    return await importInputFile();
  } catch (error) {
    return { ok: false, canceled: false, error: error.message, input_status: inputFileStatus() };
  }
});

ipcMain.handle('demo:start', async () => {
  return startDemoWorker();
});

ipcMain.handle('engine:tailLog', async (_event, maxLines) => {
  return tailRuntimeLog(Number(maxLines) || 160);
});

ipcMain.handle('engine:runtimeMetrics', async () => {
  return runtimeMetrics();
});

ipcMain.handle('monitor:open', async () => {
  return createMonitorWindow();
});

ipcMain.handle('app:closeCancel', async () => {
  closeRequestSent = false;
  return { ok: true };
});

ipcMain.handle('app:gracefulClose', async () => gracefulCloseApp());

ipcMain.handle('engine:results', async (_event, kind, maxLines) => {
  return readResults(kind || 'main', Number(maxLines) || 80);
});

app.whenReady().then(createWindow);

app.on('before-quit', () => {
  releaseLicenseSlot();
});

app.on('window-all-closed', () => {
  releaseLicenseSlot();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (!TUNER_MODE && BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});



