window.workspace.runtimeInfo().then((result) => {
  document.getElementById('config').textContent = result.out || result.err;
});
