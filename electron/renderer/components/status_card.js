export function statusCard(label, value, tone = '') {
  const card = document.createElement('div');
  card.className = `status-card ${tone}`.trim();
  const labelNode = document.createElement('div');
  labelNode.className = 'label';
  labelNode.textContent = label;
  const valueNode = document.createElement('div');
  valueNode.className = 'value';
  valueNode.textContent = value === null || value === undefined || value === '' ? '-' : String(value);
  card.append(labelNode, valueNode);
  return card;
}


