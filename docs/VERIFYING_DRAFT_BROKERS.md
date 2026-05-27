# Verifying a draft broker

This is a focused 15–30 minute task. You take one draft YAML out of
`registry/brokers_draft/`, verify its opt-out path against the live
broker site, and promote it to `registry/brokers/`.

Why this is its own workflow: draft YAMLs are deliberately schema-invalid
(no `opt_out.methods` populated). They can't ship until a human fills in
the parts that change every six months and tend to be wrong when
written from memory.

## What you need

- The draft YAML open in your editor.
- A clean browser session (private window is fine, but not strictly
  required — some brokers gate flows on a logged-in account).
- About 15–30 minutes for a single broker. Longer for credit bureaus
  (separate flows for credit / marketing / prescreened-offer
  suppression).

## The checklist

For each draft broker:

### 1. Locate the privacy or opt-out page
- Search the broker's site for "privacy", "opt-out", "opt out",
  "delete my information", "do not sell my information".
- Common locations: footer link, `/privacy`, `/opt-out`,
  `/privacy-policy`, `/ccpa`, `/california`, `/your-privacy-choices`.
- Note the URL → goes in `opt_out.instructions_url`.

### 2. Identify which opt-out methods are actually offered
- Web form? Note the form URL → `opt_out.web_form`.
- Email address? Note it → `opt_out.email`. Check the address is on
  the broker's *own* domain — a Gmail address is a red flag for a
  spoofed opt-out page.
- Postal address? Note the full address as a single line →
  `opt_out.postal`.
- Phone number? Note it → `opt_out.phone`. (Phone-only opt-outs are
  rare and not yet supported by `delete-me send`; flag in `notes`.)
- DROP-registered? Check the
  [CalPrivacy DROP registry](https://cppa.ca.gov/data_broker_registry/)
  — if the broker is there, set `opt_out.drop_registered: true` and
  populate `opt_out.calprivacy_id` if it's published per-broker.
- Update `opt_out.methods` to list every method you populated, ordered
  by preference (email > web_form > postal > phone is the typical order).

### 3. Confirm authorized-agent acceptance
- Look for language about "authorized agent" or "submit on behalf of"
  in the privacy page or the opt-out form itself.
- CCPA-covered businesses are required to accept agents; if the page
  says otherwise, set `accepts_authorized_agent: false` and add a note
  explaining what the broker actually requires (notarized form, ID
  copy, etc.).
- If the broker imposes extra requirements, populate
  `agent_form_requirements` with the matching enum values
  (`signed_permission`, `government_id_redacted`, `notarized`,
  `postal_only`, `company_letterhead`).

### 4. Confirm required vs optional PII
- The opt-out form will ask for some fields and offer others. Update
  `required_pii` to match the form's required fields and `optional_pii`
  to match the optional ones. Use the enum values listed in the
  [schema](../registry/schemas/broker.schema.json).

### 5. Bump the verification metadata
- `last_verified`: today's date, UTC, ISO format (e.g. `2026-05-27`).
- `maintainer`: your GitHub `@handle`.

### 6. Confirm the schema accepts it
```sh
mv registry/brokers_draft/<broker>.yaml registry/brokers/<broker>.yaml
uv run delete-me validate-registry
```
If validation fails, fix the YAML and re-run. If you have to roll back,
move the file back to `brokers_draft/`.

### 7. Optional — wire an audit adapter
If the broker has a consumer-facing public search (most "people search"
tier brokers do), see [`ADDING_A_BROKER.md`](ADDING_A_BROKER.md#when-to-add-an-audit-adapter)
for the adapter pattern. Adds presence-check and post-send audit
coverage. Skippable for `enterprise_aggregator` brokers (credit
bureaus, CDPs, etc.) — they don't expose searchable consumer
indexes.

### 8. Open the PR
```
git mv registry/brokers_draft/<broker>.yaml registry/brokers/<broker>.yaml
# (edit fields per steps 1-5)
git add registry/brokers/<broker>.yaml
git commit -m "registry: promote <broker_id> from draft"
gh pr create --title "registry: promote <broker_id> from draft" --body "..."
```

Body should include: which site you verified against, screenshots of
the opt-out form (or a description), and any non-obvious quirks.

## Special cases

### Credit bureaus (Equifax / Experian / TransUnion)
- CCPA has FCRA carve-outs; the deletion scope is narrower than for
  non-credit brokers. Document in `notes` which categories of data are
  actually deletable vs. which require an FCRA dispute instead.
- Each bureau typically has THREE distinct opt-out paths: credit file
  (FCRA dispute), marketing data (CCPA), prescreened-offer suppression
  (FCRA — go through OptOutPrescreen.com or call 1-888-5-OPT-OUT).
  You're documenting the CCPA marketing-data path for `delete-me`;
  mention the other two in `notes` so users don't expect more than
  they'll get.

### Customer Data Platforms (Segment / mParticle / similar)
- CDPs typically act as **service-providers** to their business
  customers under CCPA, not as **businesses**. That means the consumer
  can't make a deletion request directly to the CDP — they have to go
  to the underlying business that shipped their data into the CDP.
- If verification confirms this, set `user_submit_only: true` and use
  `notes` to explain that the letter generator will produce a draft but
  the consumer needs to identify which business is the responsible
  party.

### PeopleConnect family (BeenVerified / Intelius / PeopleLooker / etc.)
- Many sites in this family share a single opt-out portal. Verify
  whether one form covers all sister sites. If so, the sister-site
  draft can reuse the same `opt_out.web_form` URL; cross-reference in
  `notes`.
