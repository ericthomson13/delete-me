# Legal Disclaimer

`delete-me` is software, not a law firm. The documents it generates are
templates populated from data you supply, in the same way TurboTax fills a
1040.

## Not legal advice

Nothing the tool produces, prints, or transmits constitutes legal advice.
No attorney-client relationship is formed by your use of the software, by
running it, by reading its documentation, or by submitting an issue or PR.

If you have a specific legal question — including whether to send any of
the letters the tool generates, whether to escalate to a complaint or
lawsuit, or how a specific state's privacy law applies to your situation
— consult a licensed attorney. See
[`legal/attorney_referral_sources.md`](../legal/attorney_referral_sources.md)
for neutral directories you can use to find one.

## Jurisdiction-specific caveats

- The tool's primary templates are written for California residents
  exercising CCPA rights. Residents of other US states have analogous but
  not identical rights; the citations in the registry try to track this,
  but the tool's authors are not lawyers in your state.
- The tool does not currently support European-style GDPR Article 17
  erasure requests. Phase 7 adds this; until then, do not assume the
  generated letters will satisfy GDPR-specific requirements.
- The authorized-agent designation is drafted to be sufficient under CCPA
  §1798.140(d) and 11 CCR §7063. It is **not** a Power of Attorney; it is
  a scoped written permission with a 12-month term.

## E-SIGN attestation

When you sign the agent designation electronically in the tool, you are
making an attestation under penalty of perjury that the statements in
the document are true. False statements may have civil or criminal
consequences. **Sign only on behalf of yourself.** Do not use the tool to
submit deletion requests for any other person.

## Limitations of liability

The software is provided AS IS, without warranty of any kind. The authors
and contributors are not liable for any damages arising from your use of
the software, including but not limited to (a) a broker's failure to
delete your information after you send a letter, (b) errors in the
generated letter or agent designation, (c) any consequences of you
sending a letter the recipient considers frivolous or improper. See the
[LICENSE](../LICENSE) for the full text.

## If you are an attorney reading this

We would welcome PRs that improve the accuracy of the citations in
`legal/statute_citations.yaml`, that flag jurisdictional traps in the
templates, or that propose more defensible language for the authorized-
agent designation. Please do not represent the tool as a service of any
firm.
