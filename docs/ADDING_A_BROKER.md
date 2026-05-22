# Adding a broker to the registry

This is a 5-minute PR. You do not need to write code.

> Adding submission *automation* for a broker that's already in the
> registry? See [`ADDING_AN_AUTOMATION_SCRIPT.md`](ADDING_AN_AUTOMATION_SCRIPT.md)
> instead.

## 1. Copy this template

Save as `registry/brokers/<broker_slug>.yaml`. The filename's stem (without
`.yaml`) must match the `id` field.

```yaml
id: example_broker
name: Example Broker, Inc.
website: https://example.com
parent_company: ""                 # optional; omit if independent
tier: people_search                # one of: enterprise_aggregator, people_search, long_tail
opt_out:
  methods: [email, web_form]       # ordered by preference
  email: privacy@example.com       # required if "email" in methods
  web_form: https://example.com/optout  # required if "web_form" in methods
  postal: "Example Broker, 123 Main St, City, State ZIP"  # required if "postal"
  drop_registered: true            # is the broker registered with CalPrivacy DROP?
  calprivacy_id: "DB-XXXXXXX"      # optional; the CalPrivacy registration ID
  instructions_url: https://example.com/privacy
accepts_authorized_agent: true
agent_form_requirements:           # only if accepts_authorized_agent is true
  - signed_permission
  # one or more of: signed_permission, government_id_redacted, notarized, postal_only, company_letterhead
required_pii:
  - full_name
  - current_address
  # any of: full_name, current_address, prior_addresses, dob_year, dob_full, email, phone, ssn_last_4
optional_pii:
  - email
re_aggregation_days: 45            # observed days between removal and re-listing
audit_sources: []                  # leave empty unless you also ship an adapter
statutes:
  - ccpa_1798_105
  - ca_delete_act
  # slugs into legal/statute_citations.yaml
user_submit_only: false            # set to true if the broker won't accept agent letters
last_verified: 2026-05-18          # today's date
maintainer: "@your-github-handle"
notes: |
  Optional free-form notes. Include any quirks the user should know about.
```

## 2. Validate locally

```sh
uv run delete-me validate-registry
```

You should see a line like `ok   example_broker.yaml`. If it fails, the
error message points to the field that's wrong.

## 3. Open a PR

- Branch name: `add-broker-<broker_slug>`
- Commit message: `add broker: <broker_slug>`
- PR description: paste a link to the broker's privacy/opt-out page

CI runs the same validator. If your YAML parses and matches the schema,
you should see a green check.

## Common pitfalls

- **`id` doesn't match the filename.** The stem of the filename and the
  `id` field must be identical.
- **`email` is set but not in `methods`.** Every contact channel must be
  declared in `methods` first.
- **Statute slug typo.** The slugs live in `legal/statute_citations.yaml`.
  Copy-paste from there; don't invent new ones in your PR unless you also
  add the citation.
- **`last_verified` in the future.** Use today's date in ISO 8601
  (`YYYY-MM-DD`).

## When to set `user_submit_only: true`

If the broker has stated they reject authorized-agent letters, or if their
process requires the consumer to click a verification link in an email
only they receive. Examples in the existing registry: `fastpeoplesearch`,
`truepeoplesearch`.

## When to add an audit adapter

Only after Phase 2 lands. Until then, leave `audit_sources: []`.

## When to update an existing broker

Bump `last_verified` and adjust whatever changed. PRs that only update
`last_verified` (re-verification with no changes) are welcomed and merged
quickly — that's how we fight registry rot.
