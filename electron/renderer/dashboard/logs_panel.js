import { logStream } from '../components/log_stream.js';

function formatEvent(event) {
  if (event.raw) return event.raw;
  const time = event.time || event.ts || '';
  const name = event.event || event.type || 'event';
  const message = event.message || event.reason || '';
  const record = event.record ? ` ${event.record}` : '';
  return `${time} ${name}${record} ${message}`.trim();
}

export function renderLogsPanel(container, snapshot) {
  container.replaceChildren();
  const title = document.createElement('h2');
  title.textContent = 'Logs & Events';
  const eventTitle = document.createElement('h3');
  eventTitle.textContent = 'Event Timeline';
  const logTitle = document.createElement('h3');
  logTitle.textContent = 'Runtime Log';
  const events = logStream(snapshot.events.map(formatEvent));
  const logs = logStream(snapshot.logs);
  container.append(title, eventTitle, events, logTitle, logs);
}


