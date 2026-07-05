export const ipcClient = {
  getStatus() {
    return window.t1Runtime.get_status();
  },
  getLogs(limit = 300) {
    return window.t1Runtime.get_logs({ limit });
  },
  getEvents(limit = 200) {
    return window.t1Runtime.get_events({ limit });
  },
  sendCommand(command) {
    return window.t1Runtime.send_command(command);
  }
};
