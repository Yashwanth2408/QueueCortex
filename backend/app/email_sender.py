import asyncio
import smtplib
from email.mime.text import MIMEText

from app.config import Settings


class EmailSendError(Exception):
    pass


def _send_sync(settings: Settings, to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise EmailSendError("SMTP not configured (smtp_user/smtp_password blank)")
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to_email], msg.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(str(exc)) from exc


async def send_otp_email(settings: Settings, to_email: str, code: str) -> None:
    subject = "Your QueueCortex sign-in code"
    body = (
        f"Your QueueCortex verification code is: {code}\n\n"
        f"This code expires in {settings.otp_ttl_minutes} minutes.\n\n"
        "If you didn't request this, you can ignore this email."
    )
    await asyncio.to_thread(_send_sync, settings, to_email, subject, body)
