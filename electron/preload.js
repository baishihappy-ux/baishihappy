const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('workspaceRuntime', {
  runtimeInfo: () => ipcRenderer.invoke('runtime:info'),
  licenseStatus: () => ipcRenderer.invoke('license:status'),
  activateLicense: (code) => ipcRenderer.invoke('license:activate', code),
  copyText: (value) => ipcRenderer.invoke('clipboard:write', value),
  importInputFile: () => ipcRenderer.invoke('input:import'),
  setTargetSource: (value) => ipcRenderer.invoke('target:set', value),
  testNetwork: () => ipcRenderer.invoke('network:test'),
  activeRunLock: () => ipcRenderer.invoke('engine:activeRunLock'),
  startEngine: (targetSource) => ipcRenderer.invoke('engine:start', targetSource),
  pauseEngine: () => ipcRenderer.invoke('engine:pause'),
  resumeEngine: () => ipcRenderer.invoke('engine:resume'),
  gracefulClose: () => ipcRenderer.invoke('app:gracefulClose'),
  cancelCloseRequest: () => ipcRenderer.invoke('app:closeCancel'),
  startDemo: () => ipcRenderer.invoke('demo:start'),
  tailLog: (maxLines) => ipcRenderer.invoke('engine:tailLog', maxLines),
  runtimeMetrics: () => ipcRenderer.invoke('engine:runtimeMetrics'),
  openRuntimeMonitor: () => ipcRenderer.invoke('monitor:open'),
  diagnosticStatus: () => ipcRenderer.invoke('diagnostic:status'),
  setDiagnosticEnabled: (enabled) => ipcRenderer.invoke('diagnostic:setEnabled', enabled),
  readResults: (kind, maxLines) => ipcRenderer.invoke('engine:results', kind, maxLines),
  onEngineStdout: (handler) => ipcRenderer.on('engine:stdout', (_event, value) => handler(value)),
  onEngineStderr: (handler) => ipcRenderer.on('engine:stderr', (_event, value) => handler(value)),
  onEngineExit: (handler) => ipcRenderer.on('engine:exit', (_event, value) => handler(value)),
  onAppCloseRequest: (handler) => ipcRenderer.on('app:close-request', () => handler())
});


