<script lang="ts">
  import { onMount } from 'svelte';
  import { listBrokers, type BrokerRow, type BrokerTier } from '$lib/api';

  let brokers = $state<BrokerRow[]>([]);
  let error = $state<string | null>(null);
  let loading = $state(true);

  // Filters
  let tierFilter = $state<BrokerTier | 'all'>('all');
  let dropOnly = $state(false);
  let agentOnly = $state(false);
  let query = $state('');

  let filtered = $derived(brokers.filter((b) => {
    if (tierFilter !== 'all' && b.tier !== tierFilter) return false;
    if (dropOnly && !b.drop_registered) return false;
    if (agentOnly && !b.accepts_authorized_agent) return false;
    if (query) {
      const q = query.toLowerCase();
      if (!b.id.toLowerCase().includes(q) && !b.name.toLowerCase().includes(q)) return false;
    }
    return true;
  }));

  let tierCounts = $derived({
    all: brokers.length,
    enterprise_aggregator: brokers.filter((b) => b.tier === 'enterprise_aggregator').length,
    people_search: brokers.filter((b) => b.tier === 'people_search').length,
    long_tail: brokers.filter((b) => b.tier === 'long_tail').length,
  });

  function tierLabel(t: BrokerTier | null): string {
    if (t === 'enterprise_aggregator') return 'Enterprise';
    if (t === 'people_search') return 'People search';
    if (t === 'long_tail') return 'Long tail';
    return '—';
  }

  onMount(async () => {
    try {
      brokers = await listBrokers();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });
</script>

<main>
  <header>
    <h1>Brokers</h1>
    <p class="sub">Data brokers in the registry. Filter to narrow the list.</p>
  </header>

  {#if loading}
    <p>Loading brokers…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else}
    <div class="filters">
      <div class="tier-chips">
        <button class:active={tierFilter === 'all'} onclick={() => (tierFilter = 'all')}>
          All <span class="count">{tierCounts.all}</span>
        </button>
        <button
          class:active={tierFilter === 'enterprise_aggregator'}
          onclick={() => (tierFilter = 'enterprise_aggregator')}
        >
          Enterprise <span class="count">{tierCounts.enterprise_aggregator}</span>
        </button>
        <button
          class:active={tierFilter === 'people_search'}
          onclick={() => (tierFilter = 'people_search')}
        >
          People search <span class="count">{tierCounts.people_search}</span>
        </button>
        <button
          class:active={tierFilter === 'long_tail'}
          onclick={() => (tierFilter = 'long_tail')}
        >
          Long tail <span class="count">{tierCounts.long_tail}</span>
        </button>
      </div>

      <label class="toggle">
        <input type="checkbox" bind:checked={dropOnly} />
        DROP-registered only
      </label>
      <label class="toggle">
        <input type="checkbox" bind:checked={agentOnly} />
        Accepts agent
      </label>

      <input
        type="search"
        placeholder="Filter by id or name…"
        bind:value={query}
        class="search"
      />
    </div>

    <p class="result-count">{filtered.length} of {brokers.length} brokers</p>

    {#if filtered.length === 0}
      <p class="empty">No brokers match the current filters.</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Tier</th>
            <th>Methods</th>
            <th>DROP</th>
            <th>Agent</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as b (b.id)}
            <tr>
              <td><code>{b.id}</code></td>
              <td>{b.name}</td>
              <td>{tierLabel(b.tier)}</td>
              <td>
                {#each b.methods as m (m)}<span class="pill">{m}</span>{/each}
              </td>
              <td class="check">{b.drop_registered ? '✓' : '—'}</td>
              <td class="check">{b.accepts_authorized_agent ? '✓' : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</main>

<style>
  main {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
    color: var(--fg);
  }
  header { margin-bottom: 1.5rem; }
  h1 { margin: 0; font-size: 1.5rem; letter-spacing: -0.01em; }
  .sub { color: var(--fg-muted); margin: 0.25rem 0 0; font-size: 0.92rem; }
  .empty { color: var(--fg-muted); }

  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
    margin-bottom: 0.75rem;
  }
  .tier-chips {
    display: flex;
    gap: 0.4rem;
  }
  .tier-chips button {
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--fg-muted);
    padding: 0.3rem 0.75rem;
    border-radius: var(--radius-pill);
    cursor: pointer;
    font-size: 0.85rem;
    font-family: inherit;
    transition: background 120ms, border-color 120ms, color 120ms;
  }
  .tier-chips button:hover {
    background: var(--bg-hover);
    color: var(--fg);
  }
  .tier-chips button.active {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent-strong);
  }
  .tier-chips .count {
    margin-left: 0.3rem;
    opacity: 0.75;
    font-variant-numeric: tabular-nums;
  }

  .toggle {
    font-size: 0.88rem;
    color: var(--fg-muted);
    cursor: pointer;
    user-select: none;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .toggle input {
    accent-color: var(--accent);
    margin: 0;
  }

  .search {
    flex: 1;
    min-width: 200px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 0.4rem 0.65rem;
    font-size: 0.9rem;
    font-family: inherit;
    background: var(--bg);
    color: var(--fg);
  }
  .search:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  .result-count {
    color: var(--fg-subtle);
    font-size: 0.82rem;
    margin: 0.25rem 0 1rem;
    font-variant-numeric: tabular-nums;
  }

  table { width: 100%; border-collapse: collapse; }
  th, td {
    text-align: left;
    padding: 0.55rem 0.75rem;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  th {
    font-weight: 600;
    background: var(--bg-elevated);
    font-size: 0.78rem;
    color: var(--fg-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  td code {
    background: var(--bg-elevated);
    padding: 0.1rem 0.35rem;
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    color: var(--fg);
  }

  .check {
    color: var(--accent);
    text-align: center;
    font-variant-numeric: tabular-nums;
  }

  .pill {
    display: inline-block;
    background: var(--pill-bg);
    color: var(--pill-fg);
    border-radius: var(--radius-sm);
    padding: 0.08rem 0.4rem;
    margin-right: 0.25rem;
    font-size: 0.74rem;
    font-variant-numeric: tabular-nums;
  }

  .error { color: var(--error); }
</style>
