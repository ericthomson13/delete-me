"""Generate the scoped CCPA Authorized Agent Designation.

The form is rendered from legal/authorized_agent_template.md (the canonical
human-readable text) into a signed PDF/Markdown bundle. Signing is electronic
per E-SIGN Act 15 USC §7001: the consumer types their full legal name and
checks an attestation, the engine records a timestamp and audit identifier,
and the executed document is hashed.

We deliberately avoid any paid e-sign vendor. The audit log + content hash is
sufficient evidence under E-SIGN for the narrow purpose of authorizing
deletion requests.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Template

from delete_me.letters.engine import ConsumerProfile
from delete_me.paths import legal_dir


@dataclass(frozen=True)
class AgentDesignation:
    consumer_name: str
    signed_at: datetime
    audit_id: str
    schedule_a_hash: str
    document_sha256: str
    markdown: str

    def write(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "authorized_agent_designation.md"
        path.write_text(self.markdown, encoding="utf-8")
        return path


@dataclass
class SignatureContext:
    """Minimal evidence the consumer signed the form.

    audit_id is intentionally NOT a network IP — keeping this local-first.
    Callers (Tauri, docker service) may inject richer audit data later.
    """

    audit_id: str = field(default_factory=lambda: secrets.token_hex(8))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


def generate_designation(
    consumer: ConsumerProfile,
    schedule_a_broker_ids: list[str],
    signature: SignatureContext | None = None,
) -> AgentDesignation:
    """Render and "sign" the scoped agent designation.

    The signature is the consumer's typed full legal name (already captured in
    ConsumerProfile.full_legal_name) plus the attestation that the caller has
    confirmed in UI. This function does not verify the attestation; that
    happens in the calling UI layer (CLI prompt, Tauri form, docker web UI).
    """
    sig = signature or SignatureContext()

    template_text = (legal_dir() / "authorized_agent_template.md").read_text(encoding="utf-8")

    schedule_a_payload = "\n".join(sorted(schedule_a_broker_ids)).encode("utf-8")
    schedule_a_hash = hashlib.sha256(schedule_a_payload).hexdigest()[:16]

    rendered = Template(template_text).render(
        consumer={
            "full_legal_name": consumer.full_legal_name,
            "current_address": consumer.current_address,
        },
        schedule_a_hash=schedule_a_hash,
        signature={
            "timestamp_iso": sig.timestamp.isoformat(),
            "audit_id": sig.audit_id,
            "document_sha256": "<computed-below>",
        },
    )

    doc_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    rendered_final = rendered.replace("<computed-below>", doc_hash)

    return AgentDesignation(
        consumer_name=consumer.full_legal_name,
        signed_at=sig.timestamp,
        audit_id=sig.audit_id,
        schedule_a_hash=schedule_a_hash,
        document_sha256=doc_hash,
        markdown=rendered_final,
    )
