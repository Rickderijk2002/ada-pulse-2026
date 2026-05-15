from __future__ import annotations

import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent


def send() -> None:
    load_dotenv(HERE / ".env")

    sender = os.getenv("GMAIL_SENDER")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("REPORT_RECIPIENT")

    missing = [name for name, val in (
        ("GMAIL_SENDER", sender),
        ("GMAIL_APP_PASSWORD", app_password),
        ("REPORT_RECIPIENT", recipient),
    ) if not val]
    if missing:
        raise RuntimeError(
            f"Missing required env vars in {HERE / '.env'}: {', '.join(missing)}"
        )

    report_path = HERE / "report.html"
    if not report_path.exists():
        raise FileNotFoundError(
            f"{report_path} not found — run renderer.py first to generate the report."
        )
    html = report_path.read_text(encoding="utf-8")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Pulse Operational Intelligence Report — {date.today().isoformat()}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(sender, app_password)
        smtp.sendmail(sender, recipient, msg.as_string())

    print(f"Report sent to {recipient}")


if __name__ == "__main__":
    send()
