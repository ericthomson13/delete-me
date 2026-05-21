<script lang="ts">
  import { onMount } from 'svelte';
  import { listProfiles, saveProfile, type ProfileRow } from '$lib/api';

  let profiles = $state<ProfileRow[]>([]);
  let selectedId = $state<number | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let saveError = $state<string | null>(null);
  let saving = $state(false);
  let savedAt = $state<Date | null>(null);

  // Form fields (single-form, edits the selected profile or creates new)
  let full_legal_name = $state('');
  let current_address = $state('');
  let email = $state('');
  let phone = $state('');
  let dob_year = $state<number | null>(null);
  let prior_addresses_text = $state(''); // newline-separated
  let former_names_text = $state(''); // newline-separated

  function loadIntoForm(p: ProfileRow | null) {
    full_legal_name = p?.full_legal_name ?? '';
    current_address = p?.current_address ?? '';
    email = p?.email ?? '';
    phone = p?.phone ?? '';
    dob_year = p?.dob_year ?? null;
    prior_addresses_text = (p?.prior_addresses ?? []).join('\n');
    former_names_text = (p?.former_names ?? []).join('\n');
  }

  function selectProfile(id: number | null) {
    selectedId = id;
    const p = id === null ? null : profiles.find((x) => x.id === id) ?? null;
    loadIntoForm(p);
    saveError = null;
    savedAt = null;
  }

  async function refresh() {
    try {
      profiles = await listProfiles();
      if (selectedId === null && profiles.length > 0) {
        selectProfile(profiles[0].id);
      } else if (selectedId !== null) {
        // Re-sync form with latest server state
        const p = profiles.find((x) => x.id === selectedId) ?? null;
        loadIntoForm(p);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  onMount(refresh);

  function splitLines(s: string): string[] {
    return s
      .split('\n')
      .map((x) => x.trim())
      .filter(Boolean);
  }

  async function onSave(e: Event) {
    e.preventDefault();
    saveError = null;
    saving = true;
    try {
      if (dob_year !== null && (!Number.isInteger(dob_year) || dob_year < 1900 || dob_year > 2100)) {
        throw new Error('DOB year must be an integer between 1900 and 2100');
      }
      const saved = await saveProfile({
        full_legal_name: full_legal_name.trim(),
        current_address: current_address.trim(),
        email: email.trim() || null,
        phone: phone.trim() || null,
        dob_year,
        prior_addresses: splitLines(prior_addresses_text),
        former_names: splitLines(former_names_text),
      });
      savedAt = new Date();
      await refresh();
      selectedId = saved.id;
    } catch (e) {
      saveError = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  function startNew() {
    selectProfile(null);
  }

  let isEditing = $derived(selectedId !== null);
  let canSave = $derived(full_legal_name.trim().length > 0 && current_address.trim().length > 0);
</script>

<main>
  <header>
    <h1>People</h1>
    <p class="sub">
      Yourself, plus anyone you're acting as authorized agent for under
      <a href="https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.135"
         target="_blank" rel="noopener">CCPA §1798.135(c)</a>.
    </p>
  </header>

  {#if loading}
    <p>Loading profiles…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else}
    {#if profiles.length > 0}
      <section class="existing">
        <span class="label">Existing</span>
        <div class="chips">
          {#each profiles as p (p.id)}
            <button
              type="button"
              class:active={p.id === selectedId}
              onclick={() => selectProfile(p.id)}
            >
              {p.full_legal_name}
              <span class="chip-id">#{p.id}</span>
            </button>
          {/each}
          <button
            type="button"
            class:active={selectedId === null}
            class="new"
            onclick={startNew}
          >+ New</button>
        </div>
      </section>
    {/if}

    <form onsubmit={onSave}>
      <fieldset>
        <legend>{isEditing ? `Edit profile #${selectedId}` : 'New profile'}</legend>

        <div class="row">
          <label class="field">
            <span class="field-label">Full legal name <span class="req">*</span></span>
            <input
              type="text"
              bind:value={full_legal_name}
              placeholder="Jane A. Doe"
              required
            />
          </label>

          <label class="field narrow">
            <span class="field-label">DOB year</span>
            <input
              type="number"
              bind:value={dob_year}
              placeholder="1987"
              min="1900"
              max="2100"
            />
          </label>
        </div>

        <label class="field">
          <span class="field-label">Current address <span class="req">*</span></span>
          <textarea
            bind:value={current_address}
            placeholder="123 Main St, Apt 4&#10;Springfield, IL 62704"
            rows="3"
            required
          ></textarea>
        </label>

        <div class="row">
          <label class="field">
            <span class="field-label">Email</span>
            <input type="email" bind:value={email} placeholder="jane@example.com" />
          </label>
          <label class="field">
            <span class="field-label">Phone</span>
            <input type="tel" bind:value={phone} placeholder="555-555-1212" />
          </label>
        </div>

        <label class="field">
          <span class="field-label">Prior addresses</span>
          <span class="hint">One per line</span>
          <textarea
            bind:value={prior_addresses_text}
            rows="3"
            placeholder="456 Oak Ave, Chicago, IL 60601&#10;789 Pine Rd, Madison, WI 53703"
          ></textarea>
        </label>

        <label class="field">
          <span class="field-label">Former names</span>
          <span class="hint">One per line</span>
          <textarea
            bind:value={former_names_text}
            rows="2"
            placeholder="Jane A. Smith"
          ></textarea>
        </label>
      </fieldset>

      <div class="actions">
        <button type="submit" class="primary" disabled={!canSave || saving}>
          {saving ? 'Saving…' : isEditing ? 'Save changes' : 'Create profile'}
        </button>
        {#if savedAt}
          <span class="saved">Saved {savedAt.toLocaleTimeString()}</span>
        {/if}
        {#if saveError}
          <span class="error">{saveError}</span>
        {/if}
      </div>
    </form>
  {/if}
</main>

<style>
  main {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 720px;
    margin: 0 auto;
    padding: 2rem;
    color: var(--fg);
  }
  header { margin-bottom: 1.5rem; }
  h1 { margin: 0; font-size: 1.5rem; letter-spacing: -0.01em; }
  .sub { color: var(--fg-muted); margin: 0.25rem 0 0; font-size: 0.92rem; line-height: 1.45; }
  .sub a {
    color: var(--accent);
    text-decoration: none;
    border-bottom: 1px solid var(--accent-soft);
  }
  .sub a:hover { border-bottom-color: var(--accent); }

  .existing {
    margin-bottom: 1.25rem;
  }
  .existing .label {
    display: block;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--fg-muted);
    margin-bottom: 0.4rem;
  }
  .chips {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .chips button {
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--fg-muted);
    padding: 0.3rem 0.75rem;
    border-radius: var(--radius-pill);
    cursor: pointer;
    font-size: 0.85rem;
    font-family: inherit;
  }
  .chips button:hover {
    background: var(--bg-hover);
    color: var(--fg);
  }
  .chips button.active {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent-strong);
  }
  .chips button.new { font-weight: 500; }
  .chips .chip-id {
    margin-left: 0.3rem;
    opacity: 0.6;
    font-variant-numeric: tabular-nums;
    font-size: 0.78rem;
  }

  fieldset {
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1rem 1.25rem 1.25rem;
    margin: 0;
    background: var(--bg);
  }
  legend {
    padding: 0 0.5rem;
    font-size: 0.85rem;
    color: var(--fg-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .row {
    display: flex;
    gap: 1rem;
  }
  .row .field { flex: 1; }
  .row .field.narrow { flex: 0 0 8rem; }

  .field {
    display: flex;
    flex-direction: column;
    margin-bottom: 0.9rem;
  }
  .field-label {
    font-size: 0.85rem;
    color: var(--fg);
    margin-bottom: 0.25rem;
    font-weight: 500;
  }
  .req { color: var(--accent); margin-left: 0.1rem; }
  .hint {
    font-size: 0.78rem;
    color: var(--fg-subtle);
    margin-bottom: 0.3rem;
  }

  input, textarea {
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 0.4rem 0.6rem;
    font-size: 0.9rem;
    font-family: inherit;
    background: var(--bg);
    color: var(--fg);
    width: 100%;
    box-sizing: border-box;
  }
  textarea { resize: vertical; line-height: 1.4; }
  input:focus, textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-top: 1rem;
  }
  .primary {
    background: var(--accent);
    color: white;
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    padding: 0.45rem 1.1rem;
    font-size: 0.9rem;
    font-family: inherit;
    font-weight: 500;
    cursor: pointer;
  }
  .primary:hover:not(:disabled) { background: var(--accent-strong); border-color: var(--accent-strong); }
  .primary:disabled {
    background: var(--bg-elevated);
    color: var(--fg-subtle);
    border-color: var(--border);
    cursor: not-allowed;
  }

  .saved { color: var(--success); font-size: 0.85rem; }
  .error { color: var(--error); font-size: 0.85rem; }
</style>
