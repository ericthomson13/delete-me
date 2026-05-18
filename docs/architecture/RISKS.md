# Top Risks and Mitigations

Extracted from `PLAN.md`. Each risk should map to at least one concrete
mitigation in the codebase; if a contributor finds a risk listed here whose
mitigation isn't present, that's a bug.

## 1. Unauthorized Practice of Law (UPL)

A privacy tool that generates legal-looking documents is one bad UI string
from being a lawyer-without-a-license. Mitigation:

- Templates not advice. Every generated artifact is a *form*, populated
  from data the user supplies.
- `LEGAL_DISCLAIMER.md` is prominent and linked from every UI surface.
- Pre-filled regulator complaint forms are exactly that — form filling,
  the same UPL posture as TurboTax filling a 1040. No tool feature
  *recommends* litigation or settlement.
- `legal/attorney_referral_sources.md` points to NACA and state bar
  directories; **no specific firm endorsements** (also a UPL hazard and a
  referral-fee minefield).

## 2. PII liability

The tool's value depends on the user trusting it with name / DOB / address
history. Mitigation:

- **Tauri default** (Phase 4): PII stays on device; only signed/sealed
  letters egress. Tauri is the canonical install for non-technical users.
- **Docker self-host** (Phase 1): PII columns encrypted at rest with
  argon2id-derived key. Master key derived from operator passphrase;
  never persisted. `SECURITY.md` publishes the threat model day one.
- The Phase 0 CLI writes a `profile.json` to the working directory. It
  never transmits PII; if a future phase adds a network sender, the user
  must explicitly invoke it.

## 3. Abuse — weaponizing the tool against a third party

Someone could try to use `delete-me` to issue agent letters claiming to
represent a person who has not in fact authorized them. Mitigation:

- The authorized-agent designation requires the consumer's typed full legal
  name and an attestation under E-SIGN Act 15 USC §7001.
- Proof-of-address upload (hashed locally, raw image not stored) at the
  Tauri / docker layer. This is a Phase 1 add.
- One consumer profile per install / account.
- The hash of the schedule of brokers is embedded in the designation and
  in every outbound letter; the schedule cannot be silently broadened.

## 4. Registry rot

Broker contact details, opt-out URLs, and accepted methods change. A stale
registry sends letters to dead addresses. Mitigation:

- `last_verified` field on every broker.
- GitHub Action flags entries stale >180 days (Phase 1 add).
- `ADDING_A_BROKER.md` (and `CONTRIBUTING.md`) make broker updates a
  ~5-minute PR for non-coders.
- CI gates broker PRs with JSON Schema validation, so a non-coder cannot
  accidentally ship an unparseable YAML.

## 5. Broker retaliation / IP blocking on the audit pipeline

The audit pipeline does read-only public search on people-search sites. If
sites detect and block the audit, the user loses verification capability —
but not value. Mitigation:

- Audit is graceful-degrade. If a source blocks us, we log
  `audit_inconclusive` and the user still has their letter receipt.
- Per-source adapters in `core-py/delete_me/audit/sources/`. Community can
  fix one source without redeploying anything.
- Strict rate limits (1 req/min per source). Read-only — no CAPTCHA
  solving, no auth bypass, no form submission. Stays clearly within
  CFAA-safe public-data access.

---

If you add a feature, ask: *which of the above risks does it move?* If it
moves any of them in the wrong direction, the feature needs a mitigation
or it doesn't ship.
