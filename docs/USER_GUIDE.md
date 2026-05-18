# User Guide

This is the plain-English walkthrough. If a step sounds confusing, that's a
documentation bug — please open an issue.

## What you'll end up with

After ~20 minutes you'll have:

- A signed Authorized Agent Designation — a one-page document that says
  "the delete-me tool may submit deletion requests to data brokers on my
  behalf for the next 12 months." This is **not** a Power of Attorney.
- One letter per broker you selected, addressed to that broker.
- A list of brokers that don't accept agent letters; you'll send those
  letters yourself under your own signature.

## Step 1 — Install

Follow [INSTALL.md](INSTALL.md). The rest of this guide assumes
`uv run delete-me --help` prints help text.

## Step 2 — Capture your profile

The tool needs your basic identifying info so the letters can be matched
to your records inside each broker. It writes a `profile.json` to whatever
directory you run the command in. Nothing leaves your machine.

```sh
uv run delete-me init \
    --name "Your Full Legal Name" \
    --address "Your current street address, city, state, ZIP" \
    --dob-year 1985 \
    --email "you@example.com" \
    --phone "+1-555-555-5555" \
    --prior-address "Old street address, city, state, ZIP"
```

You can repeat `--prior-address` for each prior address. Brokers match on
addresses, so including a few extras helps catch all your records.

## Step 3 — See the broker list

```sh
uv run delete-me list-brokers
```

Each line shows the broker ID, tier, whether the broker accepts authorized-
agent letters, and the broker's legal name.

## Step 4 — Generate letters

```sh
uv run delete-me letters \
    --brokers spokeo,whitepages,intelius,beenverified \
    --output ./out
```

Or for everything:

```sh
uv run delete-me letters --brokers all --output ./out
```

The output directory will contain:

- `authorized_agent_designation.md` — your scoped agent designation
- one `*.md` per broker — the actual letter
- (if you passed `--pdf`) a `*.pdf` for each

## Step 5 — Review and sign

Open `authorized_agent_designation.md` in any text editor or markdown viewer.
Read it. The form was filled in with your typed name as the electronic
signature under the E-SIGN Act, but **you should re-read every word and
confirm you are comfortable with what you're authorizing.** The scope is
deliberately narrow — only deletion and opt-out requests, not any other
authority — but you should verify that for yourself.

## Step 6 — Send

For each broker letter:

- If the broker accepts email (most do): forward the letter to the email
  in the broker's `opt_out.email` field. Attach the
  `authorized_agent_designation.md` so the broker can verify the agent
  relationship.
- If the broker is `user-submit only` (e.g., FastPeopleSearch): you will
  need to visit the broker's web form yourself and paste the relevant
  information from the letter. The tool tells you which ones at the end of
  `letters`.

## Step 7 — Wait

Most brokers must respond within 45 days under CCPA. You should save the
date you sent the letter.

## Step 8 — Audit (Phase 2+ feature)

In a later phase (`Phase 2 — Audit MVP`) the tool will check ~60 days after
your request whether you still appear in the broker's public people-search
results. If you do, it builds an evidence package you can use to file a
complaint with the California AG or contact an attorney via the directories
in [`../legal/attorney_referral_sources.md`](../legal/attorney_referral_sources.md).

## What `delete-me` won't do

- It won't fill out broker opt-out web forms for you. See
  [`architecture/RESEARCH.md`](architecture/RESEARCH.md) for why.
- It won't give you legal advice. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md).
- It won't send your PII anywhere unless you explicitly invoke a send
  command in a later phase, and even then only to the broker contact in
  the registry.
