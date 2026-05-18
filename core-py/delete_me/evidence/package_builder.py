"""Build a non-compliance evidence package for one case.

The package is a directory of human-readable artifacts the user can attach
to a CA AG complaint, hand to an attorney, or archive for their own
records. The contents are:

  01-original-letter.md          — the deletion letter we sent
  02-agent-designation.md        — the scoped authorized-agent designation
  03-send-receipt.json           — when we sent, message ID, etc.
  04-audit-evidence/             — per-source audit findings
       <source>.json             — structured result
       <source>.html             — captured HTML (if the adapter saved it)
       <source>.png              — screenshot (if the adapter saved one)
  05-statute-citations.md        — the statutes invoked by the letter
  06-ca-ag-complaint-DRAFT.md    — pre-filled draft of the CA AG complaint
  07-attorney-referrals.md       — copy of legal/attorney_referral_sources.md
  MANIFEST.json                  — machine-readable index

Plus a sibling .zip of the directory for convenient attachment.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Template
from sqlmodel import Session, select

from delete_me.agent_form import generate_designation
from delete_me.cases import broker_for_case, profile_to_consumer
from delete_me.db import AuditResult, Case, Profile
from delete_me.paths import legal_dir
from delete_me.registry import Statute, load_statutes


@dataclass(frozen=True)
class EvidencePackage:
    case_id: int
    directory: Path
    zip_path: Path
    manifest_path: Path
    files: tuple[Path, ...]


@dataclass
class PackageBuilder:
    """Stateless-ish builder. Inject session + writes to disk.

    Each build() invocation produces a fresh directory at out_dir/case-<id>/
    and a sibling zip. Re-running for the same case is idempotent (existing
    directory is overwritten).
    """

    out_dir: Path
    written: list[Path] = field(default_factory=list, init=False)

    def build(self, session: Session, case: Case) -> EvidencePackage:
        if not case.id:
            raise ValueError("case must be persisted before building evidence")

        broker = broker_for_case(case)
        statutes = load_statutes()
        profile = session.get(Profile, case.profile_id)
        if profile is None:
            raise ValueError(f"case {case.id} has no profile")
        consumer = profile_to_consumer(profile)

        case_dir = self.out_dir / f"case-{case.id}"
        if case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True)
        self.written = []

        # 01 — original letter
        self._write(case_dir / "01-original-letter.md", case.letter_markdown)

        # 02 — agent designation (re-render from current data; hash matches case)
        if case.agent_designation_sha256:
            designation = generate_designation(consumer, [broker.id])
            self._write(case_dir / "02-agent-designation.md", designation.markdown)

        # 03 — send receipt
        receipt = {
            "case_id": case.id,
            "broker_id": case.broker_id,
            "sent_at": case.sent_at.isoformat() if case.sent_at else None,
            "transport_message_id": case.transport_message_id,
            "status": case.status.value,
            "agent_designation_sha256": case.agent_designation_sha256,
            "schedule_a_hash": case.schedule_a_hash,
        }
        self._write(case_dir / "03-send-receipt.json", json.dumps(receipt, indent=2))

        # 04 — audit evidence
        audits_dir = case_dir / "04-audit-evidence"
        audits_dir.mkdir()
        audits = session.exec(
            select(AuditResult).where(AuditResult.case_id == case.id)
        ).all()
        for r in audits:
            payload = {
                "id": r.id,
                "source": r.source,
                "checked_at": r.checked_at.isoformat(),
                "found": r.found,
                "inconclusive": r.inconclusive,
                "listings_url": r.listings_url,
                "notes": r.notes,
            }
            self._write(
                audits_dir / f"{r.source}.json", json.dumps(payload, indent=2)
            )
            if r.evidence_html_path and Path(r.evidence_html_path).exists():
                dest = audits_dir / f"{r.source}.html"
                shutil.copy2(r.evidence_html_path, dest)
                self.written.append(dest)
            if r.screenshot_path and Path(r.screenshot_path).exists():
                dest = audits_dir / f"{r.source}.png"
                shutil.copy2(r.screenshot_path, dest)
                self.written.append(dest)

        # 05 — statute citations
        cited = [statutes[s] for s in broker.statutes if s in statutes]
        self._write(
            case_dir / "05-statute-citations.md",
            _render_statutes(cited),
        )

        # 06 — pre-filled CA AG complaint draft
        complaint_md = _render_complaint(
            consumer=consumer,
            broker=broker,
            case=case,
            audit=_latest_audit(audits),
            statutes=cited,
        )
        self._write(case_dir / "06-ca-ag-complaint-DRAFT.md", complaint_md)

        # 07 — attorney referral sources (copied verbatim)
        referrals_src = legal_dir() / "attorney_referral_sources.md"
        if referrals_src.exists():
            shutil.copy2(referrals_src, case_dir / "07-attorney-referrals.md")
            self.written.append(case_dir / "07-attorney-referrals.md")

        # MANIFEST.json
        manifest = {
            "case_id": case.id,
            "broker_id": case.broker_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "case_status": case.status.value,
            "files": [str(p.relative_to(case_dir)) for p in self.written],
        }
        manifest_path = case_dir / "MANIFEST.json"
        self._write(manifest_path, json.dumps(manifest, indent=2))

        # Sibling zip
        zip_path = self.out_dir / f"case-{case.id}.zip"
        if zip_path.exists():
            zip_path.unlink()
        _zip_directory(case_dir, zip_path)

        case.evidence_path = str(zip_path)
        session.add(case)
        session.commit()

        return EvidencePackage(
            case_id=case.id,
            directory=case_dir,
            zip_path=zip_path,
            manifest_path=manifest_path,
            files=tuple(self.written),
        )

    def _write(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        self.written.append(path)


def _render_statutes(statutes: list[Statute]) -> str:
    lines = ["# Statutes invoked", ""]
    for s in statutes:
        lines.extend(
            [
                f"## {s.short_name}",
                f"- **Citation:** {s.citation}",
                f"- **Jurisdiction:** {s.jurisdiction}",
                "",
                s.right_description.strip(),
                "",
            ]
        )
        if s.penalty:
            lines.extend([f"**Penalty:** {s.penalty.strip()}", ""])
        if s.url:
            lines.extend([f"**URL:** {s.url}", ""])
    return "\n".join(lines)


def _render_complaint(*, consumer, broker, case, audit: AuditResult | None, statutes) -> str:
    template_text = (
        legal_dir() / "templates" / "ca_ag_complaint.md.j2"
    ).read_text(encoding="utf-8")
    now = datetime.now(UTC)
    return Template(template_text).render(
        consumer={
            "full_legal_name": consumer.full_legal_name,
            "current_address": consumer.current_address,
            "email": consumer.email,
            "phone": consumer.phone,
        },
        broker=broker,
        case={
            "sent_at_str": case.sent_at.strftime("%B %d, %Y") if case.sent_at else "—",
            "send_channel": "email",
            "agent_designation_sha256": case.agent_designation_sha256,
        },
        audit={
            "checked_at_str": audit.checked_at.strftime("%B %d, %Y") if audit else "—",
        },
        statutes=statutes,
        today_str=now.strftime("%B %d, %Y"),
    )


def _latest_audit(audits) -> AuditResult | None:
    audits_list = list(audits)
    if not audits_list:
        return None
    return max(audits_list, key=lambda r: r.checked_at)


def _zip_directory(src: Path, dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in src.rglob("*"):
            zf.write(path, arcname=path.relative_to(src.parent))
