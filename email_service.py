import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DEFAULT_RECEIVER = os.getenv("NOTIFICATION_RECEIVER", "sagareparth@gmail.com")

def send_complaint_email(
    complaint_id: str,
    name: str,
    mobile: str,
    village: str,
    taluka: str,
    area: str,
    category: str,
    description: str,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    whatsapp_opt_in: bool = True,
    photo_paths: list[str] = None,
    receiver_email: str = DEFAULT_RECEIVER
) -> bool:
    """
    Sends a formatted HTML email notification with complaint details and attachments.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[WARNING] SMTP_USER or SMTP_PASSWORD is not configured in .env file.")
        print(f"[DEMO SIMULATION] Target recipient: {receiver_email}")
        print(f"[DEMO SIMULATION] Complaint {complaint_id} saved successfully in database.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"🚨 [नवीन तक्रार दाखल] {category} - {village} ({complaint_id})"
    msg["From"] = f"आपले दादा जनसंपर्क पोर्टल <{SMTP_USER}>"
    msg["To"] = receiver_email

    # Google Maps link if GPS available
    maps_link = ""
    if gps_lat is not None and gps_lng is not None:
        maps_link = f'<a href="https://www.google.com/maps?q={gps_lat},{gps_lng}" target="_blank" style="color:#ea580c;font-weight:bold;">📍 Google Maps वर ठिकाण पहा ({gps_lat:.4f}, {gps_lng:.4f})</a>'
    else:
        maps_link = '<span style="color:#64748b;">स्थान उपलब्ध नाही</span>'

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
        .email-container {{ max-width: 650px; margin: auto; background: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 10px 25px rgba(0,0,0,0.06); }}
        .header {{ background: linear-gradient(135deg, #f97316, #ea580c); color: #ffffff; padding: 26px 24px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 800; }}
        .header p {{ margin: 6px 0 0; font-size: 13px; opacity: 0.95; }}
        .badge {{ display: inline-block; background: #ffffff; color: #ea580c; font-weight: bold; padding: 6px 14px; border-radius: 999px; font-size: 14px; margin-top: 12px; }}
        .content {{ padding: 24px; color: #1e293b; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        .info-table td {{ padding: 12px 14px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
        .info-table td.label {{ font-weight: bold; color: #475569; width: 34%; background: #f8fafc; border-radius: 6px; }}
        .desc-box {{ background: #fffaf5; border: 1px solid #fed7aa; border-radius: 12px; padding: 16px; margin: 20px 0; font-size: 14.5px; line-height: 1.6; color: #334155; }}
        .footer {{ background: #0f172a; color: #94a3b8; padding: 18px 24px; text-align: center; font-size: 12px; }}
        .whatsapp-tag {{ background: #ecfdf5; color: #059669; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; border: 1px solid #a7f3d0; }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="header">
          <h1>🏛️ आपले दादा जनसंपर्क कक्ष</h1>
          <p>विटा–खानापूर विधानसभा मतदारसंघ • तक्रार निवारण कक्ष</p>
          <div class="badge">तक्रार क्रमांक: {complaint_id}</div>
        </div>

        <div class="content">
          <h2 style="font-size: 18px; color: #0f172a; margin-top: 0; border-bottom: 2px solid #f97316; padding-bottom: 8px;">
            📋 नवीन तक्रारीचा तपशील
          </h2>

          <table class="info-table">
            <tr>
              <td class="label">नागरिकाचे नाव:</td>
              <td><strong>{name}</strong></td>
            </tr>
            <tr>
              <td class="label">मोबाईल क्रमांक:</td>
              <td>
                <a href="tel:{mobile}" style="color: #0f172a; font-weight: bold;">{mobile}</a>
                {' <span class="whatsapp-tag">🟢 WhatsApp उपलब्ध</span>' if whatsapp_opt_in else ''}
              </td>
            </tr>
            <tr>
              <td class="label">समस्येचा प्रकार:</td>
              <td><span style="color:#ea580c; font-weight:800;">{category}</span></td>
            </tr>
            <tr>
              <td class="label">गाव / शहर:</td>
              <td><strong>{village}</strong> (ता. {taluka})</td>
            </tr>
            <tr>
              <td class="label">प्रभाग / परिसर:</td>
              <td>{area if area else 'स्थानिक परिसर'}</td>
            </tr>
            <tr>
              <td class="label">GPS स्थान:</td>
              <td>{maps_link}</td>
            </tr>
          </table>

          <div style="margin-top: 20px;">
            <strong style="color: #334155; font-size: 14px;">📝 समस्येचे सविस्तर वर्णन:</strong>
            <div class="desc-box">
              {description.replace('\\n', '<br>')}
            </div>
          </div>

          <div style="background: #f1f5f9; border-radius: 10px; padding: 12px 14px; font-size: 12.5px; color: #475569;">
            ⚡ <strong>कार्यालयीन टीप:</strong> ही तक्रार 'आपले दादा' डिजिटल पोर्टलवरून थेट पाठवण्यात आली आहे. कृपया संबंधित विभागाच्या (PWD / महावितरण / नगरपरिषद) अधिकाऱ्यांशी संपर्क साधून पाठपुरावा सुरू करावा.
          </div>
        </div>

        <div class="footer">
          © २०२६ आपले दादा जनसंपर्क कक्ष • विटा–खानापूर, सांगली<br>
          नागरिक तक्रार निवारण ईमेल सूचना सेवा
        </div>
      </div>
    </body>
    </html>
    """

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(alt_part)

    # Attach photos if any
    if photo_paths:
        for path_str in photo_paths:
            p = Path(path_str)
            if p.exists():
                try:
                    with open(p, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={p.name}",
                        )
                        msg.attach(part)
                except Exception as e:
                    print(f"[ERROR] Could not attach file {p}: {e}")

    try:
        print(f"[INFO] Connecting to SMTP server {SMTP_HOST}:{SMTP_PORT}...")
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, [receiver_email], msg.as_string())
        server.quit()
        print(f"[SUCCESS] Complaint email successfully sent to {receiver_email}!")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email via SMTP: {e}")
        return False
