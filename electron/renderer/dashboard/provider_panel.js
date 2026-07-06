import { tableView } from '../components/table_view.js';
import { getProvider } from '../services/runtime_api.js';

const providers = [
  { tier: 'Tier A', name: '.do / primary_provider', mode: 'Stable API', control: 'No control brain' },
  { tier: 'Tier B', name: 'cloudbypass, zenrows, scrapfly', mode: 'Semi-managed', control: 'Light retry / fallback' },
  { tier: 'Tier C', name: 'unstable_http', mode: 'Unstable', control: 'Control brain active' }
];

function tierClass(tier) {
  if (tier === 'tier_a_stable_api') return 'tier-a';
  if (tier === 'tier_b_semi_managed') return 'tier-b';
  if (tier === 'tier_c_unstable') return 'tier-c';
  return '';
}

export function renderProviderPanel(container, snapshot) {
  const provider = getProvider(snapshot.status);
  container.replaceChildren();
  const title = document.createElement('h2');
  title.textContent = 'Provider Panel';
  const active = document.createElement('p');
  active.innerHTML = `Active: <span class="${tierClass(provider.tier)}">${provider.active || '-'}</span> (${provider.tier || '-'})`;
  const flags = document.createElement('p');
  flags.className = 'muted';
  flags.textContent = `control_brain=${Boolean(provider.uses_control_brain)} session_pool=${Boolean(provider.uses_session_pool)}`;
  const table = tableView(
    [
      { key: 'tier', label: 'Tier' },
      { key: 'name', label: 'Provider' },
      { key: 'mode', label: 'Mode' },
      { key: 'control', label: 'Runtime Control' }
    ],
    providers
  );
  container.append(title, active, flags, table);
}


