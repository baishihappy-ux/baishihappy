function isFailureLine(line) {
  return /401|502|503|504|timeout|fail|error/i.test(line);
}

export function logStream(lines) {
  const wrap = document.createElement('div');
  wrap.className = 'log-list';
  if (!lines.length) {
    const empty = document.createElement('div');
    empty.className = 'muted';
    empty.textContent = 'No runtime log lines found.';
    wrap.appendChild(empty);
    return wrap;
  }
  lines.forEach((line) => {
    const node = document.createElement('div');
    node.className = `log-line ${isFailureLine(line) ? 'failure' : ''}`.trim();
    node.textContent = line;
    wrap.appendChild(node);
  });
  return wrap;
}
