"""Postmark transactional-email transport.

Dry-run is the default. Real send requires:
  - POSTMARK_SERVER_TOKEN env var
  - explicit live=True passed to send()

Postmark was chosen over SendGrid for better DMARC/deliverability and a
cleaner threading model for replies (brokers' replies hit our inbound mailbox
in Phase 2). We avoid bundled-attachment APIs and just inline the letter +
agent designation as text — keeps the broker side simple.

API reference: https://postmarkapp.com/developer/api/email-api
"""

from __future__ import annotations

import base64
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from .base import SendResult, TransportError

LOG = logging.getLogger(__name__)
ENV_TOKEN = "POSTMARK_SERVER_TOKEN"
DEFAULT_FROM = "delete-me-agent@invalid.example"
POSTMARK_URL = "https://api.postmarkapp.com/email"


@dataclass(frozen=True)
class OutboundLetter:
    to: str
    subject: str
    body_markdown: str
    attachments: tuple[tuple[str, str], ...] = ()  # (filename, markdown)
    reply_to: str | None = None


class PostmarkTransport:
    def __init__(
        self,
        token: str | None = None,
        from_address: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token or os.environ.get(ENV_TOKEN)
        self.from_address = from_address or os.environ.get(
            "DELETE_ME_FROM_ADDRESS", DEFAULT_FROM
        )
        self.client = client or httpx.Client(timeout=10.0)

    def send(self, letter: OutboundLetter, live: bool = False) -> SendResult:
        """Send a letter via Postmark, or dry-run by default.

        Dry-run logs what would have been sent and returns a SendResult with
        dry_run=True. live=True requires POSTMARK_SERVER_TOKEN.
        """
        if not live:
            LOG.info(
                "DRY RUN: would send to=%s subject=%r bytes=%d",
                letter.to,
                letter.subject,
                len(letter.body_markdown),
            )
            return SendResult(
                dry_run=True,
                accepted_at=datetime.now(UTC),
                message_id=f"dry-run-{uuid.uuid4()}",
                to=letter.to,
                subject=letter.subject,
            )

        if not self.token:
            raise TransportError(
                f"POSTMARK_SERVER_TOKEN is required for live send (env var: {ENV_TOKEN})"
            )

        payload = {
            "From": self.from_address,
            "To": letter.to,
            "Subject": letter.subject,
            "TextBody": letter.body_markdown,
            "MessageStream": "outbound",
        }
        if letter.reply_to:
            payload["ReplyTo"] = letter.reply_to
        if letter.attachments:
            payload["Attachments"] = [
                {
                    "Name": filename,
                    "Content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
                    "ContentType": "text/markdown",
                }
                for filename, body in letter.attachments
            ]

        try:
            response = self.client.post(
                POSTMARK_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Postmark-Server-Token": self.token,
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise TransportError(f"Postmark request failed: {exc}") from exc

        if response.status_code >= 400:
            raise TransportError(
                f"Postmark returned {response.status_code}: {response.text[:500]}"
            )

        body = response.json()
        return SendResult(
            dry_run=False,
            accepted_at=datetime.now(UTC),
            message_id=body.get("MessageID"),
            to=letter.to,
            subject=letter.subject,
        )
