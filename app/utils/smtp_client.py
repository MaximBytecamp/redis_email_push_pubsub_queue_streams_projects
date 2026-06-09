import smtplib
from collections.abc import Iterator
from contextlib import contextmanager
from email.message import EmailMessage

from app.config import settings


@contextmanager
def _smtp_connection() -> Iterator[smtplib.SMTP]:
    if settings.smtp_use_tls and settings.smtp_use_ssl:
        raise ValueError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be true")

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        yield smtp


def send_email(recipient: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with _smtp_connection() as smtp:
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
