import { chartView } from '../components/chart_view.js';
import { tableView } from '../components/table_view.js';
import { getSession } from '../services/runtime_api.js';

export function renderSessionPanel(container, snapshot) {
  const session = getSession(snapshot.status);
  const states = session.states || {};
  const total = Math.max(1, session.size || Object.values(states).reduce((sum, value) => sum + Number(value || 0), 0));
  container.replaceChildren();

  const title = document.createElement('h2');
  title.textContent = 'Session Panel';
  const chart = chartView([
    { label: 'READY', value: Number(states.READY || 0) / total },
    { label: 'BUSY', value: Number(states.BUSY || 0) / total },
    { label: 'DEAD', value: Number(states.DEAD || 0) / total },
    { label: 'Stability', value: session.stability ?? 0 }
  ]);
  const table = tableView(
    [
      { key: 'metric', label: 'Metric' },
      { key: 'value', label: 'Value' }
    ],
    [
      { metric: 'active_chain_sessions', value: snapshot.status.active_chain_sessions_current ?? session.size ?? 0 },
      { metric: 'active_chain_peak', value: snapshot.status.active_chain_sessions_peak ?? '-' },
      { metric: 'session_depth', value: snapshot.controlBrain?.state_vector?.chain_length_limit ?? '-' },
      { metric: 'failed_sessions', value: session.chain_breaks ?? 0 }
    ]
  );
  container.append(title, chart, table);
}
