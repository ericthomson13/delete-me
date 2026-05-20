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
    <h1>delete-me</h1>
    <p class="sub">Open cases</p>
  </header>

  {#if loading}
    <p>Loading cases…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if cases.length === 0}
    <p>No cases yet. Draft one with <code>delete-me draft</code>.</p>
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
          <tr>
            <td>{c.id}</td>
            <td>{c.broker_id}</td>
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
    color: #1f2328;
  }
  header { margin-bottom: 1.5rem; }
  h1 { margin: 0; font-size: 1.5rem; }
  .sub { color: #656d76; margin: 0.25rem 0 0; }
  table { width: 100%; border-collapse: collapse; }
  th, td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #d0d7de;
  }
  th { font-weight: 600; background: #f6f8fa; }
  .error { color: #cf222e; }
  code { background: #f6f8fa; padding: 0.1rem 0.3rem; border-radius: 3px; }
</style>
