import os
import smtplib
from email.message import EmailMessage

import resend
from dotenv import load_dotenv

load_dotenv()

MAIL_MODE = os.getenv("MAIL_MODE", "dev")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

resend.api_key = RESEND_API_KEY  # Always set it


async def send_verification_code(to_email: str, code: str) -> dict:
    if MAIL_MODE == "prod":
        params = {
            "from": "onboarding@resend.dev",
            "to": [to_email],
            "subject": "Your SmartPay Verification Code",
            "html": f"<p>Your verification code is: <strong>{code}</strong></p>",
        }
        return resend.Emails.send(params).__dict__  # type: ignore[arg-type]

    else:
        msg = EmailMessage()
        msg["Subject"] = "Your SmartPay Verification Code"
        msg["From"] = "noreply@smartpay.local"
        msg["To"] = to_email
        msg.set_content(f"Your verification code is: {code}")
        msg.add_alternative(f"<p>Your verification code is: <strong>{code}</strong></p>", subtype="html")

        try:
            with smtplib.SMTP("mailpit", 1025) as smtp:
                smtp.send_message(msg)
            return {"status": "sent", "mode": "mailpit", "to": to_email}
        except Exception as e:
            return {"status": "error", "error": str(e)}
