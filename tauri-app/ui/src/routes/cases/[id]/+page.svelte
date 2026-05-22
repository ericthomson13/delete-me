<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import {
    getCase,
    listCaseAudits,
    runAudit,
    buildEvidence,
    evidenceDownloadUrl,
    type CaseDetail,
    type AuditRow,
    type CaseStatus,
  } from '$lib/api';

  const caseId = $derived(Number(page.params.id));

  let caseData = $state<CaseDetail | null>(null);
  let audits = $state<AuditRow[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let auditing = $state(false);
  let auditError = $state<string | null>(null);

  let buildingEvidence = $state(false);
  let evidenceError = $state<string | null>(null);

  async function refresh() {
    try {
      const [c, a] = await Promise.all([getCase(caseId), listCaseAudits(caseId)]);
      caseData = c;
      audits = a;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  onMount(refresh);

  async function onRunAudit() {
    auditError = null;
    auditing = true;
    try {
      await runAudit(caseId);
      await refresh();
    } catch (e) {
      auditError = e instanceof Error ? e.message : String(e);
    } finally {
      auditing = false;
    }
  }

  async function onBuildEvidence() {
    evidenceError = null;
    buildingEvidence = true;
    try {
      await buildEvidence(caseId);
      await refresh();
    } catch (e) {
      evidenceError = e instanceof Error ? e.message : String(e);
    } finally {
      buildingEvidence = false;
    }
  }

  let downloadHref = $state<string | null>(null);
  $effect(() => {
    if (caseData?.evidence_path) {
      evidenceDownloadUrl(caseId).then((u) => (downloadHref = u));
    } else {
      downloadHref = null;
    }
  });

  function statusClass(s: CaseStatus): string {
    if (s === 'deleted_confirmed' || s === 'acknowledged') return 'pos';
    if (s === 'noncompliant' || s === 'failed') return 'neg';
    if (s === 'audit_inconclusive') return 'warn';
    return 'neutral';
  }

  function fmt(ts: string | null | undefined): string {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  }
</script>

<main>
  <a class="back" href="/">← Cases</a>

  {#if loading}
    <p>Loading case…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if caseData}
    <header>
      <h1>Case <span class="muted">#{caseData.id}</span></h1>
      <p class="sub">
        Broker <code>{caseData.broker_id}</code> · Profile <code>#{caseData.profile_id}</code>
      </p>
    </header>

    <section class="meta">
      <dl>
        <div>
          <dt>Status</dt>
          <dd><span class="badge {statusClass(caseData.status)}">{caseData.status}</span></dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{fmt(caseData.created_at)}</dd>
        </div>
        <div>
          <dt>Sent</dt>
          <dd>{fmt(caseData.sent_at)}</dd>
        </div>
        <div>
          <dt>Audit due</dt>
          <dd>{fmt(caseData.audit_due_at)}</dd>
        </div>
        <div>
          <dt>Last audited</dt>
          <dd>{fmt(caseData.last_audited_at)}</dd>
        </div>
        {#if caseData.transport_message_id}
          <div>
            <dt>Message ID</dt>
            <dd><code class="small">{caseData.transport_message_id}</code></dd>
          </div>
        {/if}
        {#if caseData.last_error}
          <div class="full">
            <dt>Last error</dt>
            <dd class="error">{caseData.last_error}</dd>
          </div>
        {/if}
      </dl>
    </section>

    <section>
      <div class="section-head">
        <h2>Audits <span class="count">{audits.length}</span></h2>
        <button class="secondary" onclick={onRunAudit} disabled={auditing}>
          {auditing ? 'Running…' : 'Run audit now'}
        </button>
      </div>
      {#if auditError}<p class="error">{auditError}</p>{/if}
      {#if audits.length === 0}
        <p class="empty">No audits yet. Use the button above to run one.</p>
      {:else}
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Found</th>
              <th>Checked</th>
              <th>Notes</th>
              <th>Listings</th>
            </tr>
          </thead>
          <tbody>
            {#each audits as a (a.id)}
              <tr>
                <td><code>{a.source}</code></td>
                <td class="check">
                  {#if a.inconclusive}
                    <span class="badge warn">inconclusive</span>
                  {:else if a.found}
                    <span class="badge neg">found</span>
                  {:else}
                    <span class="badge pos">clean</span>
                  {/if}
                </td>
                <td>{fmt(a.checked_at)}</td>
                <td class="notes">{a.notes ?? '—'}</td>
                <td>
                  {#if a.listings_url}
                    <a href={a.listings_url} target="_blank" rel="noopener">link ↗</a>
                  {:else}—{/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>

    <section>
      <div class="section-head">
        <h2>Evidence package</h2>
        <div class="actions">
          {#if downloadHref}
            <a class="secondary" href={downloadHref} download>Download zip</a>
          {/if}
          <button class="secondary" onclick={onBuildEvidence} disabled={buildingEvidence}>
            {buildingEvidence ? 'Building…' : caseData.evidence_path ? 'Rebuild' : 'Build evidence package'}
          </button>
        </div>
      </div>
      {#if evidenceError}<p class="error">{evidenceError}</p>{/if}
      {#if caseData.evidence_path}
        <p class="evidence-path">
          On disk: <code>{caseData.evidence_path}</code>
        </p>
      {:else}
        <p class="empty">
          No evidence package built yet. Build one to bundle the letter, agent
          designation, send receipt, audit evidence, statute citations, and a
          pre-filled CA AG complaint draft into a single zip.
        </p>
      {/if}
    </section>

    <section>
      <div class="section-head">
        <h2>Letter</h2>
      </div>
      <pre class="letter">{caseData.letter_markdown}</pre>
    </section>
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

  .back {
    display: inline-block;
    color: var(--fg-muted);
    text-decoration: none;
    font-size: 0.88rem;
    margin-bottom: 1rem;
  }
  .back:hover { color: var(--fg); }

  header { margin-bottom: 1.5rem; }
  h1 { margin: 0; font-size: 1.5rem; letter-spacing: -0.01em; }
  h1 .muted { color: var(--fg-subtle); font-weight: 500; }
  .sub { color: var(--fg-muted); margin: 0.25rem 0 0; font-size: 0.92rem; }
  .sub code { background: var(--bg-elevated); padding: 0.1rem 0.3rem; border-radius: var(--radius-sm); font-size: 0.85rem; }

  section { margin-bottom: 2rem; }

  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
    gap: 1rem;
  }
  .section-head .actions { display: flex; gap: 0.5rem; }
  h2 {
    margin: 0;
    font-size: 0.92rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--fg-muted);
    font-weight: 600;
  }
  .count {
    color: var(--fg-subtle);
    margin-left: 0.4rem;
    font-variant-numeric: tabular-nums;
  }

  .meta dl {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 0.85rem 1.25rem;
    margin: 0;
    padding: 1rem 1.25rem;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }
  .meta dl div.full { grid-column: 1 / -1; }
  .meta dt {
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--fg-subtle);
    margin-bottom: 0.15rem;
  }
  .meta dd {
    margin: 0;
    font-size: 0.92rem;
    color: var(--fg);
  }
  .meta dd code.small { font-size: 0.75rem; }

  .badge {
    display: inline-block;
    border-radius: var(--radius-sm);
    padding: 0.1rem 0.45rem;
    font-size: 0.75rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }
  .badge.pos { background: rgba(26, 127, 55, 0.14); color: var(--success); }
  .badge.neg { background: rgba(207, 34, 46, 0.14); color: var(--error); }
  .badge.warn { background: rgba(154, 103, 0, 0.16); color: #9a6700; }
  .badge.neutral { background: var(--bg-elevated); color: var(--fg-muted); }

  table { width: 100%; border-collapse: collapse; }
  th, td {
    text-align: left;
    padding: 0.5rem 0.75rem;
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
  }
  td.check { white-space: nowrap; }
  td.notes { color: var(--fg-muted); font-size: 0.88rem; }
  td a { color: var(--accent); text-decoration: none; }
  td a:hover { text-decoration: underline; }

  .secondary {
    background: var(--bg);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 0.35rem 0.85rem;
    font-size: 0.85rem;
    font-family: inherit;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    line-height: 1.4;
  }
  .secondary:hover:not(:disabled) {
    background: var(--bg-hover);
    border-color: var(--border-strong);
  }
  .secondary:disabled {
    color: var(--fg-subtle);
    cursor: not-allowed;
  }

  .evidence-path {
    color: var(--fg-muted);
    font-size: 0.88rem;
    margin: 0;
  }
  .evidence-path code {
    background: var(--bg-elevated);
    padding: 0.15rem 0.4rem;
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    word-break: break-all;
  }

  .empty { color: var(--fg-muted); font-size: 0.9rem; }
  .error { color: var(--error); font-size: 0.85rem; }

  pre.letter {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1rem 1.25rem;
    font-size: 0.85rem;
    line-height: 1.5;
    color: var(--fg);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 480px;
    overflow: auto;
    font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace;
  }
</style>
