const { app, BrowserWindow, ipcMain, clipboard } = require('electron');
const crypto = require('crypto');
const path = require('path');

const LICENSE_PREFIX = 'DF8-';
const DEFAULT_SECRET = 'Workspace-License-Key-v1';
const AUTHORIZE_PASSWORD = '88888888';
let unlocked = false;
let mainWindow = null;

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
  unlocked = String(password || '') === AUTHORIZE_PASSWORD;
  if (unlocked && mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'authorizer.html'));
  }
  return { ok: unlocked, error: unlocked ? '' : 'Invalid password.' };
});

ipcMain.handle('clipboard:copy', (_event, text) => {
  clipboard.writeText(text || '');
  return { ok: true };
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
