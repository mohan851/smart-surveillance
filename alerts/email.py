"""
Email sender for Agent Eye.
- Uses Gmail SMTP if SMTP_USER + SMTP_PASS env vars are set.
- Otherwise logs the email body to the application log (dev/demo mode).

To enable real email sending on Railway:
  1. Go to https://myaccount.google.com/apppasswords
  2. Create an App Password for "Mail" / "Other" / "Agent Eye"
  3. In Railway dashboard → your service → Variables, add:
       SMTP_HOST = smtp.gmail.com
       SMTP_PORT = 587
       SMTP_USER = satwikmohan8@gmail.com
       SMTP_PASS = <the 16-char app password>
       SMTP_FROM_NAME = Agent Eye
"""
import os
import logging
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("agent_eye.email")


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success, False otherwise.
    Falls back to logging the email body if SMTP is not configured."""
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    from_name = os.getenv("SMTP_FROM_NAME", "Agent Eye")
    from_addr = user or "noreply@agent-eye.local"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{from_addr}>"
    msg["To"]      = to
    msg.set_content(body)

    if not host or not user or not pwd:
        # Dev/demo mode — just log it
        log.warning("=" * 60)
        log.warning("EMAIL (SMTP not configured, logging instead)")
        log.warning(f"To:      {to}")
        log.warning(f"Subject: {subject}")
        log.warning("Body:")
        for line in body.split("\n"):
            log.warning(f"  {line}")
        log.warning("=" * 60)
        return False

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(user, pwd)
            s.send_message(msg)
        log.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        log.error("Email send failed to %s: %s", to, e)
        # Still log so we can recover the content
        log.warning("FALLBACK LOG: To=%s Subject=%s Body=%s", to, subject, body)
        return False
