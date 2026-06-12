"""
UPSC Daily Digest — Email Delivery Service
============================================
SMTP email sender for delivering the daily PDF digest.
"""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from app.utils.logging import get_logger

log = get_logger(__name__)


class MailerService:
    """SMTP email sender with PDF attachment support."""

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_pass: str = "",
        email_from: str = "",
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.email_from = email_from

    def send_digest(
        self,
        recipients: list[str],
        pdf_path: Path,
        date_str: str,
        article_count: int = 0,
        page_count: int = 0,
        themes: list[str] | None = None,
    ) -> dict:
        """Send the daily digest PDF via email.

        Returns:
            dict with 'delivered', 'error', 'smtp_response' keys.
        """
        result = {
            "delivered": False,
            "recipient": ", ".join(recipients),
            "timestamp": datetime.now().isoformat(),
            "smtp_response": None,
            "error": None,
        }

        if not recipients:
            result["error"] = "No recipients configured"
            return result

        if not pdf_path.exists():
            result["error"] = f"PDF not found: {pdf_path}"
            return result

        try:
            msg = MIMEMultipart()
            msg["From"] = self.email_from
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = (
                f"UPSC Daily Digest — {date_str} | "
                f"{article_count} articles | {page_count} pages"
            )

            # HTML body
            theme_html = ""
            if themes:
                theme_items = "".join(f"<li>{t}</li>" for t in themes[:8])
                theme_html = f"<h3>Key Themes Today</h3><ul>{theme_items}</ul>"

            body = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px;">
                <h2 style="color: #1a237e;">UPSC Daily Newspaper Digest</h2>
                <p style="font-size: 16px; color: #555;">Date: <strong>{date_str}</strong></p>
                <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
                    <tr style="background: #e8eaf6;">
                        <td style="padding: 8px 12px; border: 1px solid #c5cae9;">Articles Analyzed</td>
                        <td style="padding: 8px 12px; border: 1px solid #c5cae9; font-weight: bold;">{article_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 12px; border: 1px solid #c5cae9;">Pages</td>
                        <td style="padding: 8px 12px; border: 1px solid #c5cae9; font-weight: bold;">{page_count}</td>
                    </tr>
                </table>
                {theme_html}
                <p style="color: #888; font-size: 12px; margin-top: 24px;">
                    Generated automatically by UPSC Daily Digest AI System.
                </p>
            </body>
            </html>
            """

            msg.attach(MIMEText(body, "html"))

            # Attach PDF or HTML
            is_html = pdf_path.suffix.lower() == ".html"
            subtype = "html" if is_html else "pdf"
            filename = f"UPSC_Digest_{date_str}.html" if is_html else f"UPSC_Digest_{date_str}.pdf"

            with open(pdf_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype=subtype)
                attachment.add_header(
                    "Content-Disposition", "attachment", filename=filename
                )
                msg.attach(attachment)

            # Send
            log.info("sending_email", recipients=recipients, pdf=str(pdf_path))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                resp = server.sendmail(
                    self.email_from, recipients, msg.as_string()
                )
                result["delivered"] = True
                result["smtp_response"] = str(resp) if resp else "OK"
                log.info("email_sent", recipients=recipients)

        except Exception as e:
            result["error"] = str(e)
            log.error("email_failed", error=str(e), recipients=recipients)

        return result
