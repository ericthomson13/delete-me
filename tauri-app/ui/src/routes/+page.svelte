<script lang="ts">
  import { onMount } from 'svelte';
  import { listCases, sendAllDrafts, type CaseRow, type SendDraftsResponse } from '$lib/api';

  let cases = $state<CaseRow[]>([]);
  let error = $state<string | null>(null);
  let loading = $state(true);

  // Bulk "Send all drafts" state
  let sending = $state(false);
  let sendError = $state<string | null>(null);
  let sendResult = $state<SendDraftsResponse | null>(null);
  let liveSend = $state(false);

  let draftCount = $derived(cases.filter((c) => c.status === 'draft').length);

  async function refresh() {
    cases = await listCases();
  }

  onMount(async () => {
    try {
      await refresh();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });

  async function onSendAllDrafts() {
    sendError = null;
    sendResult = null;
    sending = true;
    try {
      sendResult = await sendAllDrafts({ live: liveSend });
      await refresh();
    } catch (e) {
      sendError = e instanceof Error ? e.message : String(e);
    } finally {
      sending = false;
    }
  }
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
    <p class="empty">No cases yet. Draft one with <code>delete-me case-create</code> or from the Discovery page.</p>
  {:else}
    {#if draftCount > 0}
      <div class="bulk-action">
        <button class="primary" onclick={onSendAllDrafts} disabled={sending}>
          {sending ? 'Sending…' : `${liveSend ? 'Live-send' : 'Dry-run'} all ${draftCount} drafts`}
        </button>
        <label class="checkbox">
          <input type="checkbox" bind:checked={liveSend} />
          live (requires POSTMARK_SERVER_TOKEN)
        </label>
      </div>
      {#if sendError}
        <div class="callout neg">{sendError}</div>
      {/if}
      {#if sendResult}
        <div class="callout {sendResult.summary.failed > 0 ? 'warn' : 'pos'}">
          <strong>{sendResult.summary.sent}</strong> sent ·
          <strong>{sendResult.summary.failed}</strong> failed
          {#if sendResult.summary.failed > 0}
            <ul>
              {#each sendResult.failed as f}
                <li><code>{f.broker_id}</code>: {f.error}</li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    {/if}

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

  .bulk-action {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
    padding: 0.75rem 1rem;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .checkbox {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--fg-muted);
    font-size: 0.88rem;
  }
  button.primary {
    padding: 0.4rem 1rem;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 5px;
    font-size: 0.9rem;
    cursor: pointer;
  }
  button.primary:hover:not(:disabled) { background: var(--accent-strong); }
  button.primary:disabled { opacity: 0.6; cursor: not-allowed; }

  .callout {
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
  }
  .callout.pos { border-color: rgba(26, 127, 55, 0.4); background: rgba(26, 127, 55, 0.08); }
  .callout.neg { border-color: rgba(207, 34, 46, 0.4); background: rgba(207, 34, 46, 0.08); }
  .callout.warn { border-color: rgba(214, 145, 36, 0.4); background: rgba(214, 145, 36, 0.08); }
  .callout ul { margin: 0.5rem 0 0; padding-left: 1.25rem; }
</style>
