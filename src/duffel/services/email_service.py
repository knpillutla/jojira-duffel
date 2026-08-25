"""
Email Service for Duffel Flight Order Confirmations.
Constructs responsive HTML email notifications and delivers via SMTP or dry-run file exporter.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import smtplib
from typing import Any, Optional

from ..config import DuffelConfig

logger = logging.getLogger(__name__)


class EmailService:
    """Service for composing and sending flight booking confirmation emails."""

    def __init__(self, config: Optional[DuffelConfig] = None):
        self.config = config or DuffelConfig()
        self.enabled = getattr(self.config, "email_confirmation_enabled", True)
        self.smtp_host = getattr(self.config, "smtp_host", "smtp.gmail.com")
        self.smtp_port = getattr(self.config, "smtp_port", 587)
        self.smtp_username = getattr(self.config, "smtp_username", "")
        self.smtp_password = getattr(self.config, "smtp_password", "")
        self.from_email = getattr(self.config, "smtp_from_email", "no-reply@jojira.com")
        self.use_tls = getattr(self.config, "smtp_use_tls", True)
        self.output_dir = os.path.join("outputs", "email_confirmations")
        os.makedirs(self.output_dir, exist_ok=True)

    def _render_html_template(
        self,
        order_id: str,
        booking_reference: str,
        total_amount: str,
        total_currency: str,
        passengers: list[dict[str, Any]],
        slices: list[dict[str, Any]],
    ) -> str:
        passengers_html = ""
        for p in passengers:
            p_name = p.get("name") or f"{p.get('given_name', '')} {p.get('family_name', '')}".strip() or "Passenger"
            p_type = p.get("type", "adult").capitalize()
            passengers_html += f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;'><strong>{p_name}</strong></td><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;'>{p_type}</td></tr>"

        slices_html = ""
        for i, s in enumerate(slices, 1):
            orig = s.get("origin", "N/A")
            dest = s.get("destination", "N/A")
            dur = s.get("duration", "N/A")
            slices_html += f"""
            <div style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;margin-bottom:12px;'>
                <div style='font-size:14px;color:#6b7280;text-transform:uppercase;font-weight:600;margin-bottom:4px;'>Flight Segment #{i}</div>
                <div style='font-size:18px;font-weight:700;color:#111827;'>{orig} &rarr; {dest}</div>
                <div style='font-size:13px;color:#4b5563;margin-top:4px;'>Estimated Duration: <strong>{dur}</strong></div>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Flight Booking Confirmation - {booking_reference}</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background-color:#f3f4f6;margin:0;padding:24px;">
    <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.08);">
        <!-- Header -->
        <div style="background:linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);padding:28px 24px;text-align:center;color:#ffffff;">
            <h1 style="margin:0;font-size:24px;font-weight:800;letter-spacing:-0.5px;">Jojira Flights Confirmation</h1>
            <p style="margin:6px 0 0 0;font-size:14px;opacity:0.9;">Your airline reservation is confirmed & ticketed!</p>
        </div>

        <!-- Body Content -->
        <div style="padding:24px;">
            <!-- Booking Ref Pill -->
            <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;text-align:center;margin-bottom:20px;">
                <div style="font-size:12px;color:#1e40af;text-transform:uppercase;font-weight:700;letter-spacing:0.5px;">Airline Booking Reference (PNR)</div>
                <div style="font-size:28px;font-weight:900;color:#1e3a8a;margin-top:4px;letter-spacing:1.5px;">{booking_reference}</div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">Duffel Order ID: {order_id}</div>
            </div>

            <!-- Passengers Section -->
            <h3 style="font-size:16px;color:#111827;margin:20px 0 10px 0;border-bottom:2px solid #3b82f6;padding-bottom:6px;display:inline-block;">Passenger Information</h3>
            <table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:14px;color:#374151;">
                <thead>
                    <tr style="background:#f3f4f6;text-align:left;">
                        <th style="padding:8px 12px;border-bottom:2px solid #d1d5db;">Passenger Name</th>
                        <th style="padding:8px 12px;border-bottom:2px solid #d1d5db;">Type</th>
                    </tr>
                </thead>
                <tbody>
                    {passengers_html}
                </tbody>
            </table>

            <!-- Flight Itinerary -->
            <h3 style="font-size:16px;color:#111827;margin:20px 0 10px 0;border-bottom:2px solid #3b82f6;padding-bottom:6px;display:inline-block;">Flight Itinerary</h3>
            {slices_html}

            <!-- Price Summary -->
            <div style="background:#f9fafb;border-radius:8px;padding:16px;margin-top:20px;display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:16px;font-weight:600;color:#374151;">Total Amount Paid:</span>
                <span style="font-size:22px;font-weight:800;color:#059669;">{total_currency} {total_amount}</span>
            </div>
        </div>

        <!-- Footer -->
        <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 24px;text-align:center;font-size:12px;color:#9ca3af;">
            Thank you for booking with Jojira Flights & Duffel API Integration.<br>
            If you need assistance, please contact customer support with your PNR: <strong>{booking_reference}</strong>.
        </div>
    </div>
</body>
</html>"""
        return html

    def send_booking_confirmation(
        self,
        order_id: str,
        booking_reference: str,
        total_amount: str,
        total_currency: str,
        passengers: list[dict[str, Any]],
        slices: list[dict[str, Any]],
        recipient_email: str = "customer@example.com",
    ) -> dict[str, Any]:
        """
        Compose and send booking confirmation email or write to dry-run output file.
        """
        html_content = self._render_html_template(
            order_id=order_id,
            booking_reference=booking_reference,
            total_amount=total_amount,
            total_currency=total_currency,
            passengers=passengers,
            slices=slices,
        )

        file_name = f"{order_id}_confirmation.html"
        file_path = os.path.join(self.output_dir, file_name)

        # Save HTML email artifact to disk for verification & offline inspection
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
        except Exception as file_err:
            logger.warning(f"Failed to write confirmation HTML file: {file_err}")

        status = "exported_to_file"
        sent_smtp = False

        if self.enabled and self.smtp_username and self.smtp_host:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"✈️ Flight Booking Confirmed - PNR: {booking_reference}"
                msg["From"] = self.from_email
                msg["To"] = recipient_email

                plain_text = f"Flight Confirmation\nBooking Reference (PNR): {booking_reference}\nOrder ID: {order_id}\nTotal Paid: {total_currency} {total_amount}\n"
                msg.attach(MIMEText(plain_text, "plain"))
                msg.attach(MIMEText(html_content, "html"))

                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.use_tls:
                        server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(self.from_email, [recipient_email], msg.as_string())

                status = "sent_via_smtp"
                sent_smtp = True
                print(f"[EMAIL SERVICE] Booking confirmation email successfully sent to '{recipient_email}' for PNR '{booking_reference}'.")
            except Exception as err:
                print(f"[EMAIL SERVICE WARNING] SMTP email delivery failed: {err}. Saved HTML copy to '{file_path}'.")

        if not sent_smtp:
            print(f"[EMAIL SERVICE] Confirmation email generated & saved to '{file_path}' (Recipient: '{recipient_email}').")

        return {
            "status": status,
            "order_id": order_id,
            "booking_reference": booking_reference,
            "recipient": recipient_email,
            "html_file_path": file_path,
            "sent_via_smtp": sent_smtp,
        }
