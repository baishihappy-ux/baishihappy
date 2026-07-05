export function chartView(items) {
  const wrap = document.createElement('div');
  items.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'chart-row';
    const label = document.createElement('div');
    label.textContent = item.label;
    const bar = document.createElement('div');
    bar.className = 'bar';
    const fill = document.createElement('span');
    const value = Number.isFinite(Number(item.value)) ? Number(item.value) : 0;
    fill.style.width = `${Math.max(0, Math.min(100, value * 100))}%`;
    bar.appendChild(fill);
    const text = document.createElement('div');
    text.textContent = Number.isFinite(value) ? value.toFixed(2) : '-';
    row.append(label, bar, text);
    wrap.appendChild(row);
  });
  return wrap;
}
