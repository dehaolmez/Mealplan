import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger(__name__)


def send(to: str, subject: str, body: str) -> None:
    """SMTP yapılandırılmamışsa (geliştirme) e-posta içeriği günlüğe yazılır.

    Not: KVKK Kurulu'nun 2025/1072 sayılı ilke kararı doğrultusunda doğrulama/şifre e-postalarına
    reklam veya kampanya içeriği eklenmez.
    """
    s = get_settings()
    if not s.smtp_host:
        log.warning("SMTP yok; e-posta gönderilmedi. Alıcı=%s Konu=%s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)
