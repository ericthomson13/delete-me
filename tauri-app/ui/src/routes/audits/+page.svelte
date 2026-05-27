<script lang="ts">
  import { onMount } from 'svelte';
  import { listAllAudits, type AggregateAuditRow } from '$lib/api';

  let rows = $state<AggregateAuditRow[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Filters
  let query = $state('');
  let statusFilter = $state<'all' | 'found' | 'not_found' | 'inconclusive'>('all');

  let filtered = $derived(rows.filter((r) => {
    if (statusFilter === 'found' && !r.found) return false;
    if (statusFilter === 'not_found' && (r.found || r.inconclusive)) return false;
    if (statusFilter === 'inconclusive' && !r.inconclusive) return false;
    if (query) {
      const q = query.toLowerCase();
      const hay = `${r.broker_id} ${r.source} ${r.notes ?? ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }));

  let counts = $derived({
    all: rows.length,
    found: rows.filter((r) => r.found).length,
    not_found: rows.filter((r) => !r.found && !r.inconclusive).length,
    inconclusive: rows.filter((r) => r.inconclusive).length,
  });

  onMount(async () => {
    try {
      rows = await listAllAudits();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });

  function statusBadge(r: AggregateAuditRow): string {
    if (r.found) return 'neg';     // listed = bad
    if (r.inconclusive) return 'warn';
    return 'pos';
  }

  function statusLabel(r: AggregateAuditRow): string {
    if (r.found) return 'listed';
    if (r.inconclusive) return 'inconclusive';
    return 'gone';
  }

  function shortDate(iso: string | null): string {
    if (!iso) return '—';
    return iso.slice(0, 10);
  }
</script>

<main>
  <header class="page-head">
    <h1>Audits</h1>
    <p class="lede">
      Every audit result across every case, newest first. Each row links
      back to its case for context.
    </p>
  </header>

  {#if loading}
    <p>Loading…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if rows.length === 0}
    <p class="empty">
      No audits yet. Audits run automatically ~60 days after a case is
      sent, or on demand via the case detail page.
    </p>
  {:else}
    <section class="filters">
      <div class="chips">
        <button class:active={statusFilter === 'all'} onclick={() => (statusFilter = 'all')}>
          All ({counts.all})
        </button>
        <button class:active={statusFilter === 'found'} onclick={() => (statusFilter = 'found')}>
          Listed ({counts.found})
        </button>
        <button class:active={statusFilter === 'not_found'} onclick={() => (statusFilter = 'not_found')}>
          Gone ({counts.not_found})
        </button>
        <button class:active={statusFilter === 'inconclusive'} onclick={() => (statusFilter = 'inconclusive')}>
          Inconclusive ({counts.inconclusive})
        </button>
      </div>
      <input
        type="search"
        placeholder="Filter by broker, source, notes…"
        bind:value={query}
      />
    </section>

    <table>
      <thead>
        <tr>
          <th>Checked</th>
          <th>Case</th>
          <th>Broker</th>
          <th>Source</th>
          <th>Status</th>
          <th>Listing</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {#each filtered as r}
          <tr>
            <td>{shortDate(r.checked_at)}</td>
            <td><a href={`/cases/${r.case_id}`}>#{r.case_id}</a></td>
            <td><code>{r.broker_id}</code></td>
            <td><code>{r.source}</code></td>
            <td><span class="badge {statusBadge(r)}">{statusLabel(r)}</span></td>
            <td>
              {#if r.listings_url}
                <a href={r.listings_url} target="_blank" rel="noreferrer noopener">open</a>
              {:else}—{/if}
            </td>
            <td class="notes">{r.notes ?? ''}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if filtered.length === 0}
      <p class="empty">No audits match the current filter.</p>
    {/if}
  {/if}
</main>

<style>
  main {
    padding: 1.5rem 2rem 3rem;
    max-width: 1200px;
    margin: 0 auto;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: var(--fg);
  }
  .page-head h1 {
    font-size: 1.6rem;
    margin: 0 0 0.4rem;
    letter-spacing: -0.01em;
  }
  .page-head .lede {
    color: var(--fg-muted);
    margin: 0 0 1.5rem;
    max-width: 70ch;
    line-height: 1.45;
  }

  .filters {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }
  .chips {
    display: flex;
    gap: 0.4rem;
  }
  .chips button {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    color: var(--fg-muted);
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all 120ms;
  }
  .chips button:hover { color: var(--fg); }
  .chips button.active {
    background: var(--accent-soft);
    color: var(--accent-strong);
    border-color: var(--accent-soft);
  }
  .filters input[type='search'] {
    flex: 1;
    min-width: 200px;
    max-width: 360px;
    padding: 0.35rem 0.7rem;
    background: var(--bg);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 5px;
    font-size: 0.9rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  th, td {
    padding: 0.5rem 0.6rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  th {
    font-weight: 500;
    color: var(--fg-muted);
    background: var(--bg-elevated);
    position: sticky;
    top: 0;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    color: var(--fg-muted);
  }
  .notes {
    color: var(--fg-muted);
    font-size: 0.85em;
    max-width: 36ch;
  }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.55rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
  }
  .badge.pos { background: rgba(26, 127, 55, 0.15); color: var(--success); }
  .badge.neg { background: rgba(207, 34, 46, 0.15); color: var(--error); }
  .badge.warn { background: rgba(214, 145, 36, 0.18); color: #966100; }

  .empty { color: var(--fg-muted); }
  .error { color: var(--error); }
</style>
