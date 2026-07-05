import { chartView } from '../components/chart_view.js';
import { tableView } from '../components/table_view.js';
import { getScheduler } from '../services/runtime_api.js';

export function renderSchedulerPanel(container, snapshot) {
  const scheduler = getScheduler(snapshot.status, snapshot.controlBrain);
  container.replaceChildren();
  const title = document.createElement('h2');
  title.textContent = 'Scheduler Panel';
  const chart = chartView([
    { label: 'Queue pressure', value: scheduler.queuePressure ?? 0 },
    { label: 'Failure density', value: scheduler.failureDensity ?? 0 }
  ]);
  const table = tableView(
    [
      { key: 'metric', label: 'Metric' },
      { key: 'value', label: 'Value' }
    ],
    [
      { metric: 'worker_count', value: scheduler.workerCount },
      { metric: 'dispatch_rate', value: scheduler.dispatchRate },
      { metric: 'inflight_current', value: scheduler.inflightCurrent },
      { metric: 'inflight_target', value: scheduler.inflightTarget },
      { metric: 'concurrency_target', value: scheduler.concurrencyTarget }
    ]
  );
  container.append(title, chart, table);
}
