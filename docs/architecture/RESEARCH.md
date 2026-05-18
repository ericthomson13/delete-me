# Research: Why `delete-me` is letter-based + audit, not full scraping

This document captures the landscape research that informed the project's
scope. It exists in the repo so that future contributors don't re-litigate
the "why aren't we automating opt-out forms?" question every six months.

## TL;DR

Building yet another per-broker form-scraper is a graveyard. Every prior
open-source attempt has died fighting Cloudflare bot detection and broker
page churn:

| Project | Lang | Stars | Last activity | Reality |
|---|---|---|---|---|
| PrivacyBot (Berkeley) | Python/Flask + React | 541 | 2021-09-28 | Deprecated; Google OAuth dropped |
| JustVanish (AnalogJ) | Go | 113 | ~2024 | Hardcoded NOT to send mail; "dev only" |
| BADBOOL (yaelwrites) | Markdown | ~2k | 2026-04-30 | Docs-only, ~60+ brokers, actively maintained |
| Auto-Identity-Remove | Node/Playwright | growing | May 2025 | macOS-only, 500 sites, "many heuristics fail" |
| YourDigitalRights.org | TS/Next | n/a | active 2025 | Opens user's mail client with GDPR/CCPA letter; no automation |

Meanwhile, the market shifted twice in ways that matter:

1. **California's DROP registry** (under SB 362, the Delete Act) went live
   **2026-01-01**, with enforcement and $200/request/day penalties beginning
   **2026-08-01**. 545+ brokers must honor a single bulk-delete request
   every 45 days. For California residents this collapses the per-broker
   problem to one form.
2. **EasyOptOuts** ($19.99/yr) automates 200+ people-search sites and
   was scored at parity with $200/yr services in Consumer Reports' Tall
   Poppy evaluation. The "minimally tech-savvy" market has cheap working
   commercial options.

## What `delete-me` does instead

Two niches existing tools don't fill:

1. **CCPA / state-DSAR / GDPR letter-sender** — generate and email
   authorized-agent deletion letters to brokers. Mirrors what Incogni does,
   productized for OSS. ~80% of the value of paid tools at ~5% of the
   engineering cost.
2. **DROP compliance audit** — genuinely novel. After a CA DROP request,
   wait ~60 days, then verify the user is actually gone from people-search
   sites. Generate a non-compliance evidence package the user can take to
   the CA AG, a private right of action (where available), or a state
   regulator. Nobody is building this. It doubles as the post-letter audit
   for non-CA users.

## Commercial baseline (May 2026)

| Service | Real coverage | $/yr | Mechanism |
|---|---|---|---|
| EasyOptOuts | 200+ | $19.99 | Fully bot-driven; 4-month rescans |
| Optery | 125–390 real | $99–$249 | Scripted browser + outsourced humans |
| DeleteMe | ~85 auto / "850+" claimed | $129+ | Large human team in the loop |
| Kanary | "1000+" claimed | ~$180 | Heavy human ops |
| Incogni | ~270 | $99 | CCPA authorized-agent letters at scale |
| Mozilla Monitor Plus | resold Onerep | $107 | (Onerep had a 2024 conflict-of-interest scandal) |
| Permission Slip Plus (CR) | ~100+ brokers + custom | $59.99 | Authorized-agent letters; 25 concierge custom/yr |

Even $200/yr services lean primarily on CCPA authorized-agent emails, not
browser automation. The "automation" is mail-merge + humans for hard cases.
That's exactly what `delete-me` automates in the open.

## Broker tiering used by the registry

- **Tier 0 (out of scope)**: Equifax/Experian/TransUnion — FCRA, not CCPA. ~3 entities.
- **Tier 1 — `enterprise_aggregator`**: Acxiom (LiveRamp/IPG), LexisNexis Risk
  Solutions, Epsilon, Oracle Data Cloud, CoreLogic, TransUnion TLO, Thomson
  Reuters CLEAR, Babel Street. ~15–25. Notarized ID, often postal mail only.
  Highest leverage.
- **Tier 2 — `people_search`**: Spokeo, Whitepages, BeenVerified, Intelius,
  MyLife, PeopleFinder, USPhonebook, Radaris, Pipl, ZabaSearch. ~30–60.
- **Tier 3 — `long_tail`**: FastPeopleSearch, TruePeopleSearch, ThatsThem,
  Radaris clones, PeopleConnect-family sites. ~150–500.

## Technical pitfalls by tier

| Pitfall | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| reCAPTCHA/hCaptcha/Turnstile | Rare | Near-universal | Common |
| Cloudflare bot fingerprinting | Sometimes | Very common | Common |
| Email/SMS loop | Almost always | Almost always | ~50% |
| Gov ID upload / notarization | **Required** | Optional (speeds it up) | Rare |
| Postal mail only | Some | Few | Few |
| Identity proofing (DOB, address history) | Always | Often | Sometimes |
| Re-aggregation | Slow (months/yrs) | **23-day median; 73% re-listed within 90 days** | Continuous |
| JS-heavy SPA | Static + email | Increasingly SPA | Mixed |

Cloudflare Turnstile + behavioral fingerprinting is the real wall. Headless
Playwright loses; patched browsers (camoufox, undetected-chromedriver) drift
constantly. This is why every prior project died.

## Legal context

- **CCPA authorized agent** (Cal. Civ. Code §1798.140(d), 11 CCR §7063):
  Consumer designates an agent via a signed written permission — NOT a
  Probate Code §4000 Power of Attorney. Business may verify the consumer
  directly, but cannot force the consumer to bypass the agent.
- **Delete Act / SB 362**: Signed Oct 2023. Registry Jan 2024. DROP launched
  2026-01-01. Brokers must check DROP every 45 days starting 2026-08-01.
  $200/request/day penalties. Triennial audits begin 2028.
- **State variation**: TX SB 4, OR, VT have registries (lighter). Other
  CCPA-lite states (CO/CT/VA/UT/IA/...) require per-company DSAR letters.
- **GDPR/UK**: Art. 17 erasure; smaller broker universe.

## Cited sources

- [BADBOOL](https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List)
- [PrivacyBot (deprecated)](https://github.com/privacybot-berkeley/privacybot)
- [JustVanish](https://github.com/AnalogJ/justvanish)
- [YourDigitalRights.org](https://yourdigitalrights.org/)
- [CalPrivacy DROP](https://privacy.ca.gov/drop/about-drop-and-the-delete-act/)
- [DataGrail on Delete Act/DROP](https://www.datagrail.io/blog/regulations/the-delete-act-and-drop-what-you-need-to-know/)
- [Permission Slip Plus](https://innovation.consumerreports.org/introducing-permission-slip-plus/)
- [Optery review](https://www.security.org/data-removal/optery/)
- [Kanary vs DeleteMe vs Optery](https://www.kanary.com/blog/deleteme-v-optery-v-kanary)
- [EasyOptOuts](https://easyoptouts.com/about)
- [Privacy Guides — data broker removals](https://www.privacyguides.org/en/data-broker-removals/)
- [Re-aggregation stats](https://internetprivacy.com/why-data-broker-re-listing-happens-every-60-90-days/)
- [Tom Kemp data broker taxonomy](https://www.tomkemp.ai/blog/2022/10/05/a-look-at-the-different-types-of-data-brokers)
- [CR authorized-agent study](https://advocacy.consumerreports.org/wp-content/uploads/2021/02/CR_AuthorizedAgentCCPA_022021_VF_.pdf)
- [Cloudflare bot detection in 2026](https://www.capsolver.com/blog/Cloudflare/solve-cloudflare-in-2026)
