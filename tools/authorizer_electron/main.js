const { app, BrowserWindow, ipcMain, clipboard } = require('electron');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const LICENSE_PREFIX = 'DF8-';
const DEFAULT_SECRET = 'Workspace-License-Key-v1';
const AUTHORIZE_PASSWORD = '88888888';
const LOCK_DURATIONS_MS = {
  3: 10 * 60 * 1000,
  4: 30 * 60 * 1000,
  5: 2 * 60 * 60 * 1000,
  6: 24 * 60 * 60 * 1000
};
let unlocked = false;
let mainWindow = null;

function lockStatePath() {
  return path.join(app.getPath('userData'), 'authorizer-lock.json');
}

function readLockState() {
  try {
    return JSON.parse(fs.readFileSync(lockStatePath(), 'utf8'));
  } catch (_error) {
    return { failed_attempts: 0, locked_until: 0 };
  }
}

function writeLockState(state) {
  fs.mkdirSync(path.dirname(lockStatePath()), { recursive: true });
  fs.writeFileSync(lockStatePath(), JSON.stringify(state, null, 2));
}

function lockDurationFor(attempts) {
  if (attempts >= 6) return LOCK_DURATIONS_MS[6];
  return LOCK_DURATIONS_MS[attempts] || 0;
}

function formatRemaining(ms) {
  const totalSeconds = Math.max(1, Math.ceil(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function b64url(input) {
  return Buffer.from(input).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function sign(payload) {
  return crypto.createHmac('sha256', process.env.APP_LICENSE_SECRET || DEFAULT_SECRET).update(canonical(payload)).digest('base64url');
}

function generateLicense(input) {
  const machineCode = String(input.machineCode || '').trim().toUpperCase();
  const validDays = Number.parseInt(input.validDays, 10);
  const maxConcurrency = Number.parseInt(input.maxConcurrency, 10);
  const doToken = String(input.doToken || '').trim();
  if (!machineCode) throw new Error('Machine code is required.');
  if (!Number.isFinite(validDays) || validDays <= 0) throw new Error('Valid days must be greater than 0.');
  if (!Number.isFinite(maxConcurrency) || maxConcurrency <= 0) throw new Error('Max concurrency must be greater than 0.');
  if (!doToken) throw new Error('.do API token is required.');

  const now = Math.floor(Date.now() / 1000);
  const payload = {
    v: 1,
    machine_code: machineCode,
    valid_days: validDays,
    max_concurrency: maxConcurrency,
    do_token: doToken,
    issued_at: now,
    expires_at: now + validDays * 86400,
    nonce: crypto.randomUUID().replace(/-/g, '')
  };
  const envelope = {
    v: 1,
    n: payload.nonce,
    c: b64url(canonical(payload)),
    s: sign(payload)
  };
  return LICENSE_PREFIX + b64url(canonical(envelope));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 820,
    height: 560,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'login.html'));
}

ipcMain.handle('license:generate', (_event, input) => {
  try {
    if (!unlocked) throw new Error('Authorizer is locked.');
    return { ok: true, code: generateLicense(input) };
  } catch (error) {
    return { ok: false, error: error.message };
  }
});

ipcMain.handle('auth:unlock', (_event, password) => {
  const now = Date.now();
  const state = readLockState();
  if ((state.locked_until || 0) > now) {
    return {
      ok: false,
      locked: true,
      lockedUntil: state.locked_until,
      error: `Locked. Try again in ${formatRemaining(state.locked_until - now)}.`
    };
  }

  unlocked = String(password || '') === AUTHORIZE_PASSWORD;
  if (!unlocked) {
    const failedAttempts = Number(state.failed_attempts || 0) + 1;
    const duration = lockDurationFor(failedAttempts);
    const nextState = {
      failed_attempts: failedAttempts,
      locked_until: duration ? now + duration : 0
    };
    writeLockState(nextState);
    if (duration) {
      return {
        ok: false,
        locked: true,
        lockedUntil: nextState.locked_until,
        error: `Invalid password. Locked for ${formatRemaining(duration)}.`
      };
    }
    return { ok: false, locked: false, error: `Invalid password. ${Math.max(0, 3 - failedAttempts)} attempt(s) before lock.` };
  }

  writeLockState({ failed_attempts: 0, locked_until: 0 });
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'authorizer.html'));
  }
  return { ok: true, error: '' };
});

ipcMain.handle('clipboard:copy', (_event, text) => {
  clipboard.writeText(text || '');
  return { ok: true };
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
