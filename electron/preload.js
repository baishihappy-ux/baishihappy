const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('t1Runtime', {
  get_status: () => ipcRenderer.invoke('runtime:get_status'),
  get_logs: (options) => ipcRenderer.invoke('runtime:get_logs', options || {}),
  get_events: (options) => ipcRenderer.invoke('runtime:get_events', options || {}),
  send_command: (command) => ipcRenderer.invoke('runtime:send_command', command),
  set_target_source: (value) => ipcRenderer.invoke('runtime:set_target_source', value),
  preflight: () => ipcRenderer.invoke('runtime:preflight'),
  input_status: () => ipcRenderer.invoke('runtime:input_status'),
  get_results: (kind, maxLines) => ipcRenderer.invoke('runtime:results', kind, maxLines),
  test_network: () => ipcRenderer.invoke('runtime:test_network'),
  active_run_lock: () => ipcRenderer.invoke('runtime:active_run_lock'),
  get_machine_code: () => ipcRenderer.invoke('license:machine_code'),
  get_license_status: () => ipcRenderer.invoke('license:status'),
  activate_license: (code) => ipcRenderer.invoke('license:activate', code),
  copy_text: (text) => ipcRenderer.invoke('clipboard:copy_text', text),
  open_monitor: () => ipcRenderer.invoke('monitor:open'),
  on_logs_changed: (callback) => ipcRenderer.on('runtime:logs_changed', callback),
  on_events_changed: (callback) => ipcRenderer.on('runtime:events_changed', callback)
});
