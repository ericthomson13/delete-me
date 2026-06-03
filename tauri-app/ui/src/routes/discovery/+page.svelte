<script lang="ts">
  import { onMount } from 'svelte';
  import {
    checkPassword,
    createCase,
    listBreachProviders,
    listCases,
    listProfiles,
    runBreachCheck,
    runPresenceCheck,
    type BreachCheckResponse,
    type BreachProvidersResponse,
    type CaseRow,
    type PasswordCheckResponse,
    type PresenceCheckResponse,
    type ProfileRow,
  } from '$lib/api';

  // Profile picker
  let profiles = $state<ProfileRow[]>([]);
  let profileId = $state<number | null>(null);
  let loadingProfiles = $state(true);
  let profileError = $state<string | null>(null);

  // Presence-check
  let presence = $state<PresenceCheckResponse | null>(null);
  let presenceRunning = $state(false);
  let presenceError = $state<string | null>(null);

  // Breach providers
  let providers = $state<BreachProvidersResponse | null>(null);
  let providersLoading = $state(true);

  // Breach-check
  let breach = $state<BreachCheckResponse | null>(null);
  let breachRunning = $state(false);
  let breachError = $state<string | null>(null);
  let breachProviderHints = $state<Array<{ source_id: string; detail: string }> | null>(null);

  // Password-check
  let passwordInput = $state('');
  let passwordResult = $state<PasswordCheckResponse | null>(null);
  let passwordRunning = $state(false);
  let passwordError = $state<string | null>(null);

  // Existing cases for the current profile, keyed by broker_id. Drives the
  // "Create case" vs "Existing case" CTA on each presence row.
  let casesByBroker = $state<Record<string, CaseRow>>({});
  let creatingFor = $state<Record<string, boolean>>({});
  let createError = $state<Record<string, string>>({});

  let selectedProfile = $derived(profiles.find((p) => p.id === profileId) ?? null);

  onMount(async () => {
    try {
      const [ps, prov] = await Promise.all([listProfiles(), listBreachProviders()]);
      profiles = ps;
      if (ps.length > 0) profileId = ps[0].id;
      providers = prov;
    } catch (e) {
      profileError = e instanceof Error ? e.message : String(e);
    } finally {
      loadingProfiles = false;
      providersLoading = false;
    }
  });

  // Re-fetch cases whenever the active profile changes.
  $effect(() => {
    const pid = profileId;
    if (pid === null) {
      casesByBroker = {};
      return;
    }
    void refreshCasesForProfile(pid);
  });

  async function refreshCasesForProfile(pid: number) {
    try {
      const cases = await listCases(pid);
      const map: Record<string, CaseRow> = {};
      // First case wins (matches the cases-from-presence CLI semantics).
      for (const c of cases) {
        if (!(c.broker_id in map)) map[c.broker_id] = c;
      }
      casesByBroker = map;
    } catch (e) {
      // Non-fatal — the CTA just defaults to "Create case" if we can't tell.
      console.error('listCases failed', e);
    }
  }

  async function onRunPresence() {
    if (profileId === null) return;
    presenceError = null;
    presenceRunning = true;
    try {
      presence = await runPresenceCheck(profileId);
    } catch (e) {
      presenceError = e instanceof Error ? e.message : String(e);
    } finally {
      presenceRunning = false;
    }
  }

  async function onCreateCase(brokerId: string) {
    if (profileId === null) return;
    delete createError[brokerId];
    createError = { ...createError };
    creatingFor = { ...creatingFor, [brokerId]: true };
    try {
      const created = await createCase(profileId, brokerId);
      casesByBroker = {
        ...casesByBroker,
        [brokerId]: created as unknown as CaseRow,
      };
    } catch (e) {
      createError = {
        ...createError,
        [brokerId]: e instanceof Error ? e.message : String(e),
      };
    } finally {
      creatingFor = { ...creatingFor, [brokerId]: false };
    }
  }

  async function onRunBreach() {
    if (profileId === null) return;
    breachError = null;
    breachProviderHints = null;
    breachRunning = true;
    try {
      breach = await runBreachCheck(profileId);
    } catch (e) {
      breachError = e instanceof Error ? e.message : String(e);
      const hints = (e as Error & { providers?: Array<{ source_id: string; detail: string }> }).providers;
      if (hints) breachProviderHints = hints;
    } finally {
      breachRunning = false;
    }
  }

  async function onCheckPassword() {
    if (!passwordInput) return;
    passwordError = null;
    passwordRunning = true;
    try {
      passwordResult = await checkPassword(passwordInput);
    } catch (e) {
      passwordError = e instanceof Error ? e.message : String(e);
    } finally {
      passwordRunning = false;
      // Clear from memory ASAP — we don't keep it after the call.
      passwordInput = '';
    }
  }

  function statusBadge(status: 'found' | 'not_found' | 'inconclusive'): string {
    if (status === 'found') return 'neg'; // found means you're listed — bad
    if (status === 'not_found') return 'pos';
    return 'warn';
  }
</script>

<main>
  <header class="page-head">
    <h1>Discovery</h1>
    <p class="lede">
      Find out where you're exposed before sending letters. Presence-check probes
      brokers that publish a consumer-facing search. Breach-check queries
      configured leak providers. Password-check uses HIBP's free k-anonymity
      lookup — your password never leaves this machine in a recoverable form.
    </p>
  </header>

  {#if loadingProfiles}
    <p>Loading…</p>
  {:else if profileError}
    <p class="error">{profileError}</p>
  {:else if profiles.length === 0}
    <div class="callout warn">
      No profiles yet. Add one on the <a href="/profiles">People</a> page first.
    </div>
  {:else}
    <section class="profile-picker">
      <label for="profile-select">Profile</label>
      <select id="profile-select" bind:value={profileId}>
        {#each profiles as p}
          <option value={p.id}>{p.full_legal_name}</option>
        {/each}
      </select>
      {#if selectedProfile}
        <span class="muted">{selectedProfile.email ?? '(no email on file)'}</span>
      {/if}
    </section>

    <!-- ============================================ PRESENCE-CHECK -->
    <section>
      <div class="section-head">
        <h2>Presence-check</h2>
        <button class="primary" onclick={onRunPresence} disabled={presenceRunning || profileId === null}>
          {presenceRunning ? 'Checking…' : 'Run presence-check'}
        </button>
      </div>

      {#if presenceError}
        <div class="callout neg">{presenceError}</div>
      {:else if !presence}
        <p class="muted">
          Queries every broker with an audit_source adapter. Brokers without one
          show in the coverage footer.
        </p>
      {:else if presence.summary.brokers_checked === 0}
        <p class="empty">No brokers to check.</p>
      {:else}
        <table>
          <thead>
            <tr>
              <th>Broker</th>
              <th>Source</th>
              <th>Status</th>
              <th>Listing</th>
              <th>Case</th>
            </tr>
          </thead>
          <tbody>
            {#each presence.results.filter((r) => r.source !== '(none)') as r}
              <tr>
                <td><code>{r.broker_id}</code></td>
                <td><code>{r.source}</code></td>
                <td><span class="badge {statusBadge(r.status)}">{r.status.replace('_', ' ')}</span></td>
                <td>
                  {#if r.listings_url}
                    <a href={r.listings_url} target="_blank" rel="noreferrer noopener">open</a>
                  {:else}
                    —
                  {/if}
                </td>
                <td>
                  {#if casesByBroker[r.broker_id]}
                    <a href={`/cases/${casesByBroker[r.broker_id].id}`}>
                      #{casesByBroker[r.broker_id].id}
                      <span class="muted">({casesByBroker[r.broker_id].status.replace(/_/g, ' ')})</span>
                    </a>
                  {:else if r.status === 'found'}
                    <button
                      class="link-button"
                      onclick={() => onCreateCase(r.broker_id)}
                      disabled={creatingFor[r.broker_id]}
                    >
                      {creatingFor[r.broker_id] ? 'creating…' : 'Create case'}
                    </button>
                    {#if createError[r.broker_id]}
                      <div class="row-error">{createError[r.broker_id]}</div>
                    {/if}
                  {:else}
                    —
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>

        <p class="footer-line">
          <strong>{presence.summary.found}</strong> found ·
          <strong>{presence.summary.not_found}</strong> not found ·
          <strong>{presence.summary.inconclusive}</strong> inconclusive ·
          <strong>{presence.summary.no_audit_source_configured}</strong>
          with no audit source configured
          (of {presence.summary.brokers_checked} brokers checked)
        </p>
        {#if presence.summary.no_audit_source_configured > 0}
          <p class="muted">
            Brokers without an audit source can't be presence-checked. Coverage
            grows as adapters are added.
          </p>
        {/if}
      {/if}
    </section>

    <!-- ============================================ BREACH-CHECK -->
    <section>
      <div class="section-head">
        <h2>Breach-check</h2>
        <button
          class="primary"
          onclick={onRunBreach}
          disabled={breachRunning || profileId === null || (providers !== null && providers.active.length === 0)}
        >
          {breachRunning ? 'Checking…' : 'Run breach-check'}
        </button>
      </div>

      {#if providersLoading}
        <p class="muted">Loading provider status…</p>
      {:else if providers && providers.active.length === 0}
        <div class="callout warn">
          <strong>No breach providers configured.</strong> Set up at least one
          to enable this section:
          <ul>
            {#each providers.providers as p}
              <li><code>{p.source_id}</code>: {p.detail}</li>
            {/each}
          </ul>
        </div>
      {:else if providers}
        <p class="muted">
          Active providers: {providers.active.map((s) => `[${s}]`).join(' ')}
          {#if providers.providers.some((p) => !p.available)}
            · Skipped: {providers.providers.filter((p) => !p.available).map((p) => `[${p.source_id}]`).join(' ')}
          {/if}
        </p>
      {/if}

      {#if breachError && breachProviderHints}
        <div class="callout warn">
          <strong>{breachError}.</strong> Setup hints:
          <ul>
            {#each breachProviderHints as p}
              <li><code>{p.source_id}</code>: {p.detail}</li>
            {/each}
          </ul>
        </div>
      {:else if breachError}
        <div class="callout neg">{breachError}</div>
      {/if}

      {#if breach}
        {#each Object.entries(breach.results) as [email, rows]}
          <h3 class="address-head">{email}</h3>
          {#if rows.length === 0}
            <p class="empty">No breaches found for this address.</p>
          {:else}
            <table>
              <thead>
                <tr><th>Date</th><th>Source</th><th>Breach</th><th>Data classes</th></tr>
              </thead>
              <tbody>
                {#each rows as r}
                  <tr>
                    <td>{r.breach_date ?? '—'}</td>
                    <td><code>{r.source}</code></td>
                    <td>{r.breach_name}</td>
                    <td>
                      {#if r.data_classes.length}
                        {#each r.data_classes as c}<span class="pill">{c}</span>{/each}
                      {:else}—{/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        {/each}
        {#if breach.providers.disabled_mid_run.length > 0}
          <div class="callout warn">
            Disabled mid-run (auth or quota error):
            <ul>
              {#each breach.providers.disabled_mid_run as d}
                <li><code>{d.source_id}</code>: {d.detail}</li>
              {/each}
            </ul>
          </div>
        {/if}
      {/if}
    </section>

    <!-- ============================================ PASSWORD-CHECK -->
    <section>
      <div class="section-head">
        <h2>Password-check</h2>
      </div>
      <p class="muted">
        Hashed locally with SHA-1; only the first 5 hex characters of the hash
        are sent to HIBP. Nothing is stored. Free, no API key required.
      </p>
      <form
        onsubmit={(e) => {
          e.preventDefault();
          onCheckPassword();
        }}
        class="password-form"
      >
        <input
          type="password"
          bind:value={passwordInput}
          placeholder="Enter a password to check"
          autocomplete="off"
        />
        <button class="primary" type="submit" disabled={passwordRunning || !passwordInput}>
          {passwordRunning ? 'Checking…' : 'Check'}
        </button>
      </form>

      {#if passwordError}
        <div class="callout neg">{passwordError}</div>
      {:else if passwordResult}
        {#if passwordResult.found}
          <div class="callout neg">
            <strong>Found.</strong> This password has been seen
            <strong>{passwordResult.breach_count.toLocaleString()}</strong>
            time(s) in known breaches. Treat it as compromised — change it
            everywhere you've used it and consider a password manager.
          </div>
        {:else}
          <div class="callout pos">
            Not found in HIBP's breach corpus.
          </div>
        {/if}
      {/if}
    </section>
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

  .profile-picker {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    padding: 0.7rem 1rem;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .profile-picker label { font-weight: 500; }
  .profile-picker select {
    padding: 0.3rem 0.5rem;
    background: var(--bg);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
  }
  .profile-picker .muted { color: var(--fg-muted); font-size: 0.9rem; }

  section {
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
  }
  section:last-child { border-bottom: none; }

  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }
  .section-head h2 {
    font-size: 1.2rem;
    margin: 0;
    letter-spacing: -0.01em;
  }
  .address-head {
    margin: 1.25rem 0 0.5rem;
    font-size: 1rem;
    color: var(--fg-muted);
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

  .pill {
    display: inline-block;
    margin: 0.1rem 0.2rem 0.1rem 0;
    padding: 0.05rem 0.5rem;
    border-radius: 4px;
    background: var(--pill-bg);
    color: var(--pill-fg);
    font-size: 0.75rem;
  }

  .callout {
    padding: 0.75rem 1rem;
    margin-top: 0.75rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
  }
  .callout.pos {
    border-color: rgba(26, 127, 55, 0.4);
    background: rgba(26, 127, 55, 0.08);
  }
  .callout.neg {
    border-color: rgba(207, 34, 46, 0.4);
    background: rgba(207, 34, 46, 0.08);
  }
  .callout.warn {
    border-color: rgba(214, 145, 36, 0.4);
    background: rgba(214, 145, 36, 0.08);
  }
  .callout ul { margin: 0.5rem 0 0; padding-left: 1.25rem; }
  .callout li { margin-bottom: 0.25rem; }

  .footer-line {
    margin-top: 0.75rem;
    color: var(--fg-muted);
    font-size: 0.9rem;
  }
  .footer-line strong { color: var(--fg); }

  .empty, .muted { color: var(--fg-muted); }
  .error { color: var(--error); }

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

  .password-form {
    display: flex;
    gap: 0.5rem;
    margin: 0.75rem 0 0.5rem;
  }
  .password-form input {
    flex: 1;
    max-width: 30rem;
    padding: 0.4rem 0.7rem;
    background: var(--bg);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 5px;
    font-size: 0.95rem;
  }

  .link-button {
    background: none;
    border: none;
    padding: 0;
    color: var(--accent);
    cursor: pointer;
    font-size: inherit;
    font-family: inherit;
    text-decoration: underline;
  }
  .link-button:hover:not(:disabled) { color: var(--accent-strong); }
  .link-button:disabled { color: var(--fg-muted); cursor: wait; }

  .row-error {
    margin-top: 0.2rem;
    color: var(--error);
    font-size: 0.8em;
  }
</style>
