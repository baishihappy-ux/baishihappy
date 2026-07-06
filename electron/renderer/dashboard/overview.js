import { statusCard } from '../components/status_card.js';
import { getProvider, getScheduler, getSession } from '../services/runtime_api.js';

export function renderOverview(container, snapshot) {
  const { status, controlBrain } = snapshot;
  const provider = getProvider(status);
  const scheduler = getScheduler(status, controlBrain);
  const session = getSession(status);
  container.replaceChildren();

  const title = document.createElement('h2');
  title.textContent = 'Dashboard';
  const cards = document.createElement('div');
  cards.className = 'cards';
  cards.append(
    statusCard('Concurrency', scheduler.currentConcurrency ?? scheduler.concurrencyTarget),
    statusCard('Provider Tier', provider.tier || 'unknown', provider.tier === 'tier_a_stable_api' ? 'good' : ''),
    statusCard('Failure Rate', status.failure_rate ?? scheduler.failureDensity ?? 0),
    statusCard('Throughput', scheduler.throughputRate ?? 0),
    statusCard('Session Active', status.active_chain_sessions_current ?? session.size ?? 0)
  );
  container.append(title, cards);
}


