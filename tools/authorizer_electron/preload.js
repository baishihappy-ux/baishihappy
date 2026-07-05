const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('authorizer', {
  unlock: (password) => ipcRenderer.invoke('auth:unlock', password),
  generate: (input) => ipcRenderer.invoke('license:generate', input),
  copy: (text) => ipcRenderer.invoke('clipboard:copy', text)
});
