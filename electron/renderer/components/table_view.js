export function tableView(columns, rows) {
  const table = document.createElement('table');
  table.className = 'table';
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  columns.forEach((column) => {
    const th = document.createElement('th');
    th.textContent = column.label;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const tbody = document.createElement('tbody');
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    columns.forEach((column) => {
      const td = document.createElement('td');
      const value = row[column.key];
      td.textContent = value === null || value === undefined || value === '' ? '-' : String(value);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.append(thead, tbody);
  return table;
}


