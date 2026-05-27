<script lang="ts">
  import { onMount } from 'svelte';
  import {
    apiBase,
    evidenceDownloadUrl,
    listEvidencePackages,
    type EvidencePackageRow,
  } from '$lib/api';

  let rows = $state<EvidencePackageRow[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let downloadHrefs = $state<Record<number, string>>({});

  onMount(async () => {
    try {
      rows = await listEvidencePackages();
      // Resolve download URLs eagerly so right-click "Open in browser" works.
      const base = await apiBase();
      for (const r of rows) {
        downloadHrefs[r.case_id] = await evidenceDownloadUrl(r.case_id);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });

  function shortDate(iso: string | null): string {
    if (!iso) return '—';
    return iso.slice(0, 10);
  }

  function statusBadge(s: EvidencePackageRow['case_status']): string {
    if (s === 'noncompliant') return 'neg';
    if (s === 'deleted_confirmed') return 'pos';
    return 'warn';
  }
</script>

<main>
  <header class="page-head">
    <h1>Evidence packages</h1>
    <p class="lede">
      Every case that has a built evidence package. Each package is a
      zipped, hash-stamped bundle of the deletion letter, agent
      designation, audit findings, statute citations, and a draft CA AG
      complaint — ready to file with a regulator or hand to a
      plaintiff-side privacy attorney.
    </p>
  </header>

  {#if loading}
    <p>Loading…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if rows.length === 0}
    <div class="callout">
      No evidence packages built yet. Build one from a case detail page
      after a noncompliant audit verdict, or directly via the CLI:
      <pre><code>uv run delete-me evidence --case &lt;id&gt;</code></pre>
    </div>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Last audited</th>
          <th>Case</th>
          <th>Broker</th>
          <th>Case status</th>
          <th>On disk</th>
          <th>Download</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as r}
          <tr>
            <td>{shortDate(r.last_audited_at)}</td>
            <td><a href={`/cases/${r.case_id}`}>#{r.case_id}</a></td>
            <td><code>{r.broker_id}</code></td>
            <td>
              <span class="badge {statusBadge(r.case_status)}">
                {r.case_status.replace(/_/g, ' ')}
              </span>
            </td>
            <td>
              {#if r.on_disk}
                <span class="badge pos">yes</span>
              {:else}
                <span class="badge warn">missing</span>
              {/if}
            </td>
            <td>
              {#if r.on_disk && downloadHrefs[r.case_id]}
                <a href={downloadHrefs[r.case_id]} download>download .zip</a>
              {:else}
                —
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</main>

<style>
  main {
    padding: 1.5rem 2rem 3rem;
    max-width: 1100px;
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

  .callout {
    padding: 1rem 1.25rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--fg-muted);
  }
  .callout pre {
    margin: 0.5rem 0 0;
    padding: 0.5rem 0.75rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.85rem;
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
  }
  th {
    font-weight: 500;
    color: var(--fg-muted);
    background: var(--bg-elevated);
  }
  code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    color: var(--fg-muted);
  }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.55rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
    text-transform: capitalize;
  }
  .badge.pos { background: rgba(26, 127, 55, 0.15); color: var(--success); }
  .badge.neg { background: rgba(207, 34, 46, 0.15); color: var(--error); }
  .badge.warn { background: rgba(214, 145, 36, 0.18); color: #966100; }

  .error { color: var(--error); }
</style>
