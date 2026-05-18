# Authorized Agent Designation — Scoped Written Permission

> **This is NOT a Power of Attorney.** This document grants narrow, time-limited
> authority for one specific purpose: submitting privacy-law deletion requests
> to data brokers on your behalf. It does not grant authority over your money,
> property, medical decisions, or any other matter.

---

## Statement of Designation

I, **{{ consumer.full_legal_name }}**, residing at **{{ consumer.current_address }}**,
hereby designate the software application **delete-me**
(operated under my own control on my own device, or self-hosted by me) as my
"authorized agent" for the limited purposes set forth below, pursuant to:

- California Consumer Privacy Act (CCPA), Cal. Civ. Code §1798.140(d) and
  the implementing regulations at 11 CCR §7063;
- the analogous "authorized agent" provisions of each US state privacy law
  identified in Schedule A; and
- the Electronic Signatures in Global and National Commerce Act,
  15 U.S.C. §7001.

## Scope of Authority

The agent's authority is **strictly limited** to the following actions, and no
others:

1. Preparing, signing, and transmitting on my behalf written requests to
   data brokers identified in **Schedule A** asserting my rights to:
   - delete personal information about me (e.g., Cal. Civ. Code §1798.105);
   - opt out of the sale or sharing of personal information about me
     (e.g., Cal. Civ. Code §1798.120);
   - correct inaccurate personal information about me; and
   - the analogous rights under any other applicable state, federal, or
     foreign privacy law identified in the request.
2. Receiving the broker's acknowledgement and confirmation of action taken,
   solely for the purpose of recording compliance.

The agent has **no authority** to:

- modify, close, or open any account in my name;
- receive a copy of personal information disclosed by the broker on my behalf
  (such disclosures must go directly to me);
- pay, demand, settle, or compromise any claim;
- represent me in any administrative, regulatory, or judicial proceeding;
- enter into any contract, waiver, or release; or
- take any action not listed above.

## Term and Revocation

This designation is effective on the date signed below and **automatically
expires twelve (12) months thereafter**. I may revoke it at any time before
expiration by sending notice to the address published in the project's
SECURITY.md. Brokers receiving this designation may rely on its validity until
they receive notice of revocation.

## Schedule A — Brokers in Scope

The brokers identified in the attached machine-readable list
(`registry/brokers/*.yaml`, hash `{{ schedule_a_hash }}`) and any subset
thereof that the consumer selects within the application. The schedule may be
narrowed but not broadened by the application without a new designation.

## Identity Verification

The business receiving this designation may verify my identity directly using
the contact information I have provided in the accompanying request. I agree
to respond reasonably to such verification within the time permitted by
applicable law.

## Signature (Electronic, per 15 U.S.C. §7001)

By typing my full legal name below and checking the attestation box in the
application, I intend to sign this document electronically and I attest that
all of the following are true:

- I am the person named above.
- I am at least 18 years of age.
- I have read and understood this designation.
- I have not been induced to sign by any misrepresentation by the agent.

Signed: **{{ consumer.full_legal_name }}**
Date: **{{ signature.timestamp_iso }}**
Device fingerprint / IP (audit log only): **{{ signature.audit_id }}**
SHA-256 of executed document: **{{ signature.document_sha256 }}**
