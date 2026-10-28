import html
import logging
import smtplib
from email.message import EmailMessage

from .config import settings

log = logging.getLogger("emailer")


def render_html(title: str, lines: list[str], button: tuple[str, str] | None = None, footer: str = "") -> str:
    """A small, clean HTML email. `lines` are plain strings (escaped here)."""
    body = "".join(
        f'<p style="margin:0 0 12px;line-height:1.55;color:#1f2a46">{html.escape(l)}</p>' for l in lines
    )
    btn = ""
    if button:
        btn = (f'<p style="margin:22px 0 6px"><a href="{html.escape(button[1])}" style="background:#1d3f91;'
               f'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">'
               f'{html.escape(button[0])}</a></p>')
    foot = f'<p style="margin:22px 0 0;font-size:12px;color:#6b778c">{html.escape(footer)}</p>' if footer else ""
    return (
        '<div style="background:#f6f4ee;padding:24px;font-family:Segoe UI,Arial,sans-serif">'
        '<div style="max-width:540px;margin:auto;background:#fff;border:1px solid #e3ded1;border-top:4px solid #c19a45;border-radius:12px;padding:26px">'
        f'<h2 style="margin:0 0 16px;font-size:19px;color:#101c3d">{html.escape(title)}</h2>{body}{btn}{foot}'
        '</div></div>'
    )


def send_email(to: str | list[str], subject: str, body: str, html_body: str | None = None) -> bool:
    """With no SMTP configured the email is written to the log (development). True = actually sent."""
    recipients = [to] if isinstance(to, str) else list(dict.fromkeys(to))
    if not recipients:
        return False
    if not settings.SMTP_HOST:
        log.warning("[DEV EMAIL] to=%s subject=%s\n%s", recipients, subject, body)
        return False
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception:
        log.exception("Email send failed")
        return False