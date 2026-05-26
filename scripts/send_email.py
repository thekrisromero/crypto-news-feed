#!/usr/bin/env python3
"""
Send a briefing HTML file via the Resend API.

Reads env:
  RESEND_API_KEY  (GitHub secret)
  EMAIL_FROM      (GitHub variable, e.g. "Crypto Briefing <briefing@yourdomain.com>"
                   or "onboarding@resend.dev" for testing)
  EMAIL_TO        (GitHub variable, recipient address)
  BRIEFING_FILE   (relative path to HTML)
  EMAIL_SUBJECT   (subject line)

Resend API docs: https://resend.com/docs/api-reference/emails/send-email
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

API_URL = "https://api.resend.com/emails"


def fail(msg: str) -> None:
    print(f"::error::{msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    api_key = os.environ.get("RESEND_API_KEY")
    email_from = os.environ.get("EMAIL_FROM")
    email_to = os.environ.get("EMAIL_TO")
    briefing_file = os.environ.get("BRIEFING_FILE")
    subject = os.environ.get("EMAIL_SUBJECT", "Crypto Custody & Treasury Briefing")

    if not api_key:
        fail("RESEND_API_KEY secret is not set on the repo.")
    if not email_from:
        fail("EMAIL_FROM variable is not set on the repo.")
    if not email_to:
        fail("EMAIL_TO variable is not set on the repo.")
    if not briefing_file:
        fail("BRIEFING_FILE env is not set.")

    path = Path(briefing_file)
    if not path.is_file():
        fail(f"Briefing file not found: {briefing_file}")

    html = path.read_text(encoding="utf-8")

    payload = {
        "from": email_from,
        "to": [email_to],
        "subject": subject,
        "html": html,
    }

    resp = requests.post(
        API_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    if resp.status_code >= 400:
        fail(f"Resend API error {resp.status_code}: {resp.text}")

    body = resp.json()
    print(f"Sent. Resend message id: {body.get('id')}")
    print(f"Subject: {subject}")
    print(f"To: {email_to}")
    print(f"File: {briefing_file} ({len(html):,} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
