<script lang="ts">
  import { onMount } from 'svelte';
  import { listCases, type CaseRow } from '$lib/api';

  let cases = $state<CaseRow[]>([]);
  let error = $state<string | null>(null);
  let loading = $state(true);

  onMount(async () => {
    try {
      cases = await listCases();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });
</script>

<main>
  <header>
    <h1>Cases</h1>
    <p class="sub">Open cases.</p>
  </header>

  {#if loading}
    <p>Loading cases…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if cases.length === 0}
    <p class="empty">No cases yet. Draft one with <code>delete-me draft</code>.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Broker</th>
          <th>Status</th>
          <th>Sent</th>
          <th>Audit due</th>
        </tr>
      </thead>
      <tbody>
        {#each cases as c (c.id)}
          <tr class="row" onclick={() => (window.location.href = `/cases/${c.id}`)}>
            <td>#{c.id}</td>
            <td><code>{c.broker_id}</code></td>
            <td>{c.status}</td>
            <td>{c.sent_at ?? '—'}</td>
            <td>{c.audit_due_at ?? '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</main>

<style>
  main {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem;
    color: var(--fg);
  }
  header { margin-bottom: 1.5rem; }
  h1 { margin: 0; font-size: 1.5rem; letter-spacing: -0.01em; }
  .sub { color: var(--fg-muted); margin: 0.25rem 0 0; font-size: 0.92rem; }
  .empty { color: var(--fg-muted); }
  table { width: 100%; border-collapse: collapse; }
  th, td {
    text-align: left;
    padding: 0.55rem 0.75rem;
    border-bottom: 1px solid var(--border);
  }
  tr.row { cursor: pointer; transition: background 80ms; }
  tr.row:hover { background: var(--bg-hover); }
  th {
    font-weight: 600;
    background: var(--bg-elevated);
    font-size: 0.85rem;
    color: var(--fg-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  td code {
    background: var(--bg-elevated);
    padding: 0.1rem 0.3rem;
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
  }
  .error { color: var(--error); }
  code { background: var(--bg-elevated); padding: 0.1rem 0.3rem; border-radius: var(--radius-sm); }
</style>
