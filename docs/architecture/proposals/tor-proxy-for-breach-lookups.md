# Proposal: Tor (SOCKS) proxy support for breach lookups

**Status:** open, not recommended for prioritization today.
**Authored:** 2026-05-27.
**Trigger to revisit:** a user threat model that requires hiding lookup
*origin* from the breach providers themselves.

## Context

`delete-me breach-check` queries three external services with the user's
email address:

- HIBP (`/api/v3/breachedaccount/{email}`)
- IntelX phonebook search (POST body `{term: email}`)
- DeHashed (`/search?query=email:{email}`)

For each call, the provider's HTTP server learns:
1. The email being queried (the payload).
2. The originating IP (the request source).

The k-anonymity Pwned Passwords endpoint (used by `password-check`)
solves (1) for *passwords* — only the first 5 hex chars of the SHA-1
leave the machine. The email endpoints have no equivalent affordance.

This proposal addresses only (2) — hiding *who is asking*, not *what they
are asking about*.

## Threat model considered

| Adversary | Defended today | Adds with Tor |
|---|---|---|
| Passive network observer (ISP, coffee-shop wifi) | TLS hides the URL path + body | Tor adds origin-IP unlinkability from the eventual exit node |
| The breach provider's logging | Sees email + IP + UA today | Sees email + Tor exit IP + UA — they still learn the email |
| An adversary who compromises the provider | Same as above | Same as above |
| An adversary correlating queries across providers | Same source IP across the 3 calls | Different exit IPs per circuit — modest unlinkability gain |

**Honest summary:** Tor turns "they know who" into "they know someone
asked about this email." It does not turn into "they don't know
anything." For most users querying their own email, the breach provider
already knows them — they paid for the API key. For the rare user
querying someone else's email (which TOS-wise they shouldn't be doing
anyway), origin-IP hiding is a meaningful step.

The realistic value case is **opsec hygiene for security researchers**
and **users in jurisdictions where querying certain leaks may be legally
sensitive**. Not a typical-user feature.

## Proposed implementation

### Scope
- One env var `DELETE_ME_BREACH_PROXY` (URL like `socks5://127.0.0.1:9050`
  or `http://proxy.example.com:8080`). Empty/unset → no proxy (today's
  behavior).
- Honored by `HIBPAdapter`, `IntelXAdapter`, `DeHashedAdapter`.
- NOT honored by `PwnedPasswordsClient` (k-anonymity already hides the
  password; the prefix isn't sensitive).
- NOT honored by the `audit/` people-search adapters (they're querying
  the broker the user is opting out from — proxy-routing those would
  trigger more aggressive anti-bot for marginal privacy gain).

### Code change
A shared helper:

```python
# core-py/delete_me/breaches/_proxy.py
import os, httpx

def proxy_for_breach_lookups() -> str | None:
    return os.environ.get("DELETE_ME_BREACH_PROXY") or None

def client_kwargs(timeout: float = 15.0, **extra) -> dict:
    """httpx.Client kwargs honoring the optional breach-lookup proxy."""
    kw: dict = {"timeout": timeout, **extra}
    proxy = proxy_for_breach_lookups()
    if proxy:
        kw["proxy"] = proxy  # httpx ≥ 0.26
    return kw
```

Each adapter swaps its `httpx.Client(...)` instantiation to use
`client_kwargs(...)`. Tests inject a fake client as today (the helper is
bypassed when `client` is provided to `__init__`).

### Dependencies
- `httpx[socks]` extra (currently we depend on `httpx`). Adds the
  `socksio` transitive dep. About 50 KB installed.
- Update `pyproject.toml` `dependencies` entry to `httpx[socks]>=0.28`.

### Docs
- `USER_GUIDE.md` Discovery section: short paragraph + example
  `export DELETE_ME_BREACH_PROXY=socks5://127.0.0.1:9050`, with a
  pointer to running Tor locally (`brew install tor; tor &` on macOS,
  `apt install tor; systemctl start tor` on Debian-family).
- `INSTALL.md` env-var table: one new row.
- Honest privacy caveat in the user guide: "Tor hides where the request
  came from; it does not hide which email you asked about. The provider
  still sees the email."

### Tests
- 3 new tests asserting the env var is read at `__init__` time and the
  resulting `httpx.Client` gets the `proxy=` kwarg (use a recording
  factory or `httpx.MockTransport` to verify).
- 1 test that `PwnedPasswordsClient` ignores the env var (it should
  never proxy — that endpoint has its own privacy story).
- 1 test that the people-search adapters ignore the env var.

### Effort
- Code: ~half a day (1 helper module, 3 adapter `__init__` tweaks, 1
  pyproject change, ~50 lines of tests).
- Docs: ~1 hour (USER_GUIDE + INSTALL + the honest caveat).
- Total realistic: **half a day with docs.**

## Risks / costs

1. **Tor exit IPs are widely blocked.** HIBP, IntelX, and DeHashed all
   have anti-abuse infra that flags traffic from known exit nodes. The
   feature ships but mostly fails in practice — users see more 401/403
   responses, not fewer breaches. We'd want to set expectations clearly
   in the docs and treat block responses the same as today (the
   orchestrator already handles them gracefully).
2. **Operational dependency on Tor.** Users have to run a local Tor
   proxy. Most don't. A real-world rollout would either:
   - Add a `delete-me doctor` check that says "Tor not reachable at
     127.0.0.1:9050" with setup instructions, or
   - Bundle a tor binary in the Tauri sidecar (significant scope creep).
3. **httpx[socks] is a new transitive dep on socksio.** Small but real;
   any future supply-chain concerns inherit it.
4. **Doesn't solve the actual leak.** The provider sees the email. If
   that's not acceptable for the threat model, the answer isn't Tor —
   it's not querying that provider at all.

## Recommendation

**Don't build it now.** The cost is low (half a day) but the value is
narrow (opsec-conscious researchers in specific jurisdictions). Most
users querying their own email get nothing actionable from this. Exit-IP
blocking probably eats the working-case anyway.

**Build it when** one of these triggers:
- A user files an issue describing a concrete threat model where origin
  hiding matters (security researcher workflows, lookup-as-investigation).
- We add a "lookup someone else's exposure" feature (e.g., a service
  operator running breach-check across customer profiles in bulk) where
  the provider's correlation across queries becomes a real concern.
- HIBP adds a k-anonymity-style breach endpoint that obsoletes the
  need (would make this proposal moot for HIBP).

**Until then:** the existing soft-degrade behavior is correct — if a
user really needs Tor today, they can route their entire shell with
`torsocks delete-me breach-check`. That's a worse UX but covers the
edge case.

## Open questions

- If we build it, do we also expose the proxy to the IntelX/DeHashed
  *opt-out* flows (currently CLI-only, but a future Tauri-side opt-out
  could benefit)? Probably yes for consistency, but that's its own
  scope.
- Should the env var be `DELETE_ME_HTTP_PROXY` (broader) instead of
  `DELETE_ME_BREACH_PROXY` (narrower)? Broader is more flexible but
  invites "why doesn't this proxy my Postmark calls too?" support
  questions. The narrow name keeps the contract honest.
