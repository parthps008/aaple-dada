import os
import sys
import smtplib
import sqlite3
import random
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from pathlib import Path
from dotenv import load_dotenv

import streamlit as st

load_dotenv()

# Ensure UTF-8 console output
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ----------------------------------------------------
# 1. Page Configuration & Custom Theme
# ----------------------------------------------------
st.set_page_config(
    page_title="आपले दादा | नागरिक तक्रार निवारण पोर्टल",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------------------------------------------
# 2. Database Setup (SQLite)
# ----------------------------------------------------
DB_FILE = Path(__file__).parent / "complaints.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY,
        name TEXT,
        mobile TEXT,
        village TEXT,
        taluka TEXT,
        area TEXT,
        category TEXT,
        description TEXT,
        whatsapp_opt_in INTEGER,
        status TEXT,
        stage INTEGER,
        remark TEXT,
        created_at TEXT
    )
    """)
    conn.commit()

    # Seed demo records if empty
    cursor.execute("SELECT COUNT(*) FROM complaints")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO complaints (id, name, mobile, village, taluka, area, category, description, whatsapp_opt_in, status, stage, remark, created_at)
        VALUES 
        ('APD-2026-102450', 'श्री. विजय पाटील', '9822******', 'विटा शहर', 'खानापूर', 'शिवाजी चौक', 'रस्ते व वाहतूक समस्या', 
         'मुख्य रस्त्यावरील खड्डे बुजवून तातडीने डांबरीकरण करणेबाबत.', 1, 'प्रक्रियेत', 3, 
         'सदर समस्येबाबत सार्वजनिक बांधकाम विभाग (PWD) चे उपअभियंता यांच्याशी संपर्क साधण्यात आला असून प्रत्यक्ष पाहणीसाठी टीम रवाना झाली आहे.', '02/10/2026'),
        ('APD-2026-101180', 'श्री. मारुती माने', '9890******', 'भाळवणी', 'खानापूर', 'ग्रामपंचायत परिसर', 'पाणीपुरवठा जलवाहिनी दुरुस्ती', 
         'मुख्य पाईपलाईन लिकेज दुरुस्ती करून नियमित पाणीपुरवठा सुरू करणे.', 1, 'पूर्ण', 4, 
         'नवीन जलवाहिनी जोडणी व व्हॉल्व्ह दुरुस्तीचे काम पूर्ण झाले असून सुरळीत पाणीपुरवठा सुरू करण्यात आला आहे.', '28/09/2026')
        """)
        conn.commit()
    conn.close()

init_db()

def save_complaint_to_db(record):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO complaints (id, name, mobile, village, taluka, area, category, description, whatsapp_opt_in, status, stage, remark, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record['id'], record['name'], record['mobile'], record['village'], record['taluka'],
        record['area'], record['category'], record['description'],
        1 if record.get('whatsapp_opt_in') else 0,
        record.get('status', 'प्रक्रियेत'),
        record.get('stage', 2),
        record.get('remark', 'तक्रार जनसंपर्क कार्यालयात नोंदवली असून प्राथमिक छाननी सुरू आहे.'),
        datetime.now().strftime("%d/%m/%Y, %I:%M %p")
    ))
    conn.commit()
    conn.close()

def get_complaint_from_db(complaint_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE UPPER(id) = UPPER(?)", (complaint_id.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ----------------------------------------------------
# 3. SMTP Email Configuration & Dispatcher
# ----------------------------------------------------
def get_smtp_credentials():
    smtp_host = "smtp.gmail.com"
    smtp_port = 587
    smtp_user = "sagareparth@gmail.com"
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    receiver = "sagareparth@gmail.com"

    try:
        if hasattr(st, "secrets") and len(st.secrets) > 0:
            smtp_host = st.secrets.get("SMTP_HOST", smtp_host)
            smtp_port = int(st.secrets.get("SMTP_PORT", smtp_port))
            smtp_user = st.secrets.get("SMTP_USER", smtp_user)
            smtp_pass = st.secrets.get("SMTP_PASSWORD", smtp_pass)
            receiver = st.secrets.get("NOTIFICATION_RECEIVER", receiver)
    except Exception:
        pass

    return smtp_host, smtp_port, smtp_user, smtp_pass, receiver

def send_email_notification(record, uploaded_files=None):
    host, port, user, pwd, receiver = get_smtp_credentials()

    if not user or not pwd:
        # Running in demo mode without credentials
        return False, "SMTP_USER किंवा SMTP_PASSWORD सेट केलेले नाही (डेमो मोड)."

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"🚨 [नवीन तक्रार] {record['category']} - {record['village']} ({record['id']})"
        msg["From"] = f"आपले दादा जनसंपर्क पोर्टल <{user}>"
        msg["To"] = receiver

        # Attach Vaibhav Dada photo inline for the email header
        dada_photo_path = Path(__file__).parent / "dada.jpg"
        if dada_photo_path.exists():
            try:
                with open(dada_photo_path, "rb") as df:
                    img_mime = MIMEImage(df.read())
                    img_mime.add_header("Content-ID", "<dada_photo>")
                    img_mime.add_header("Content-Disposition", "inline; filename=dada.jpg")
                    msg.attach(img_mime)
            except Exception as err:
                print("Could not attach dada_photo:", err)

        whatsapp_tag = "🟢 WhatsApp उपलब्ध" if record.get('whatsapp_opt_in') else ""

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background:#f8fafc; padding:20px; color:#1e293b;">
          <div style="max-width:620px; margin:auto; background:#fff; border-radius:16px; border:1px solid #e2e8f0; overflow:hidden; box-shadow:0 8px 24px rgba(0,0,0,0.06);">
            <div style="background:linear-gradient(135deg,#f97316,#ea580c); color:#fff; padding:24px 20px; text-align:center;">
              <div style="margin-bottom:10px;">
                <img src="cid:dada_photo" onerror="this.src='https://raw.githubusercontent.com/parthps008/aaple-dada/main/dada.jpg'" 
                     alt="मा. श्री. वैभव दादा" 
                     style="width:90px; height:90px; border-radius:50%; border:3px solid #ffffff; box-shadow:0 6px 16px rgba(0,0,0,0.22); object-fit:cover; display:inline-block;" />
              </div>
              <h2 style="margin:0; font-size:23px; font-weight:800;">मा. श्री. वैभव (दादा) जनसंपर्क कक्ष</h2>
              <p style="margin:4px 0 0; font-size:13px; opacity:0.95;">विटा–खानापूर विधानसभा मतदारसंघ • तक्रार निवारण विभाग</p>
              <div style="display:inline-block; background:#fff; color:#ea580c; font-weight:bold; padding:5px 14px; border-radius:999px; margin-top:12px; font-size:13px;">
                तक्रार क्रमांक: {record['id']}
              </div>
            </div>
            <div style="padding:24px;">
              <h3 style="margin-top:0; border-bottom:2px solid #f97316; padding-bottom:8px; color:#0f172a;">📋 तक्रारदार व समस्येचा तपशील</h3>
              <table style="width:100%; border-collapse:collapse; font-size:14px; margin-top:10px;">
                <tr><td style="padding:9px 6px; font-weight:bold; width:35%;">नागरिकाचे नाव:</td><td><strong>{record['name']}</strong></td></tr>
                <tr><td style="padding:9px 6px; font-weight:bold;">मोबाईल नंबर:</td><td><a href="tel:{record['mobile']}" style="color:#0f172a;font-weight:bold;">{record['mobile']}</a> {whatsapp_tag}</td></tr>
                <tr><td style="padding:9px 6px; font-weight:bold;">समस्येचा प्रकार:</td><td><span style="color:#ea580c; font-weight:bold;">{record['category']}</span></td></tr>
                <tr><td style="padding:9px 6px; font-weight:bold;">गाव / शहर:</td><td><strong>{record['village']}</strong> (ता. {record['taluka']})</td></tr>
                <tr><td style="padding:9px 6px; font-weight:bold;">प्रभाग / परिसर:</td><td>{record.get('area', 'परिसर')}</td></tr>
              </table>

              <div style="margin-top:18px;">
                <strong>📝 समस्येचे सविस्तर वर्णन:</strong>
                <div style="background:#fffaf5; border:1px solid #fed7aa; border-radius:10px; padding:14px; margin-top:6px; font-size:14px; line-height:1.6; color:#334155;">
                  {record['description']}
                </div>
              </div>
            </div>
            <div style="background:#0f172a; color:#94a3b8; padding:16px; text-align:center; font-size:12px;">
              © २०२६ आपले दादा जनसंपर्क कक्ष • विटा–खानापूर<br>
              सूचना ईमेल: {receiver}
            </div>
          </div>
        </body>
        </html>
        """
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt_part)

        # Attach uploaded files if any
        if uploaded_files:
            for up_file in uploaded_files:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(up_file.getvalue())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={up_file.name}")
                msg.attach(part)

        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=12)
        else:
            server = smtplib.SMTP(host, port, timeout=12)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(user, pwd)
        server.sendmail(user, [receiver], msg.as_string())
        server.quit()
        return True, f"ईमेल यशस्वीरित्या {receiver} वर पाठवला गेला!"
    except Exception as e:
        return False, f"SMTP त्रुटी: {str(e)}"

# ----------------------------------------------------
# 4. Custom Styling (CSS Injection)
# ----------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Mukta:wght@400;600;700;800&display=swap');
  
  html, body, [class*="css"] {
    font-family: 'Mukta', sans-serif !important;
  }
  
  /* Top Indian Flag Colors Bar */
  .tricolor-bar {
    height: 6px;
    background: linear-gradient(90deg, #f97316 0%, #f97316 33.3%, #ffffff 33.3%, #ffffff 66.6%, #10b981 66.6%, #10b981 100%);
    border-radius: 4px;
    margin-bottom: 12px;
  }

  /* Header Box */
  .hero-box {
    background: linear-gradient(135deg, #ffffff, #fffaf5);
    border: 1px solid #fed7aa;
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(249,115,22,0.08);
  }

  .stat-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 14px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }
  .stat-number {
    font-size: 26px;
    font-weight: 800;
    color: #ea580c;
  }

  /* Stepper Progress Box */
  .tracker-step-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px;
    margin-top: 15px;
  }
  
  .remark-box {
    background: #fffaf5;
    border-left: 4px solid #f97316;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
    color: #475569;
    margin-top: 14px;
  }
</style>
<div class="tricolor-bar"></div>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 5. Header & Leader Presentation
# ----------------------------------------------------
col_hero_left, col_hero_right = st.columns([1.6, 1.0], gap="medium")

with col_hero_left:
    st.markdown("""
    <div style="display:inline-block; background:#fff7ed; color:#c2410c; border:1px solid #fed7aa; padding:4px 14px; border-radius:999px; font-weight:700; font-size:13px; margin-bottom:8px;">
      📍 विटा • खानापूर विधानसभा मतदारसंघ • सांगली
    </div>
    <h1 style="font-size:38px; font-weight:800; color:#0f172a; line-height:1.2; margin:0 0 10px;">
      आपली समस्या, <span style="color:#ea580c;">थेट दादांच्या दरबारात.</span>
    </h1>
    <p style="font-size:16px; color:#475569; line-height:1.6;">
      स्थानिक अडचणी मांडण्यासाठी, प्रशासकीय पाठपुरावा करण्यासाठी आणि प्रत्येक समस्येचे जलद निवारण करण्यासाठी विटा-खानापूरचे अधिकृत जनसंपर्क डिजिटल व्यासपीठ.
    </p>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="stat-card"><div class="stat-number">१,४८०+</div><div style="font-size:12px;color:#64748b;font-weight:bold;">नोंदवलेल्या तक्रारी</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="stat-card"><div class="stat-number">१,२२०+</div><div style="font-size:12px;color:#64748b;font-weight:bold;">मार्गी लागलेली कामे</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="stat-card"><div class="stat-number">२४×७</div><div style="font-size:12px;color:#64748b;font-weight:bold;">डिजिटल सेवा</div></div>', unsafe_allow_html=True)

with col_hero_right:
    img_path = Path(__file__).parent / "dada.jpg"
    if img_path.exists():
        st.image(str(img_path), width=230, caption="मा. श्री. वैभव (दादा) • लोकनेते, विटा–खानापूर")
    else:
        st.info("🏛️ मा. श्री. वैभव (दादा) जनसंपर्क कक्ष")

st.markdown("---")

# ----------------------------------------------------
# 6. Main Navigation Tabs
# ----------------------------------------------------
tab_complaint, tab_track, tab_works, tab_ai, tab_contact = st.tabs([
    "📝 नवीन तक्रार नोंदवा",
    "🔎 तक्रारीचा मागोवा (Track)",
    "🏆 मार्गी लागलेली कामे",
    "🤖 AI नागरिक सहाय्यक",
    "🏢 जनसंपर्क कार्यालय व माहिती"
])

# ====================================================
# TAB 1: तक्रार नोंदणी फॉर्म
# ====================================================
with tab_complaint:
    st.subheader("📋 आपली तक्रार किंवा मागणी नोंदवा")
    st.caption("कृपया योग्य व अचूक माहिती भरा जेणेकरून दादांच्या कार्यालयातून तातडीने पाठपुरावा करता येईल.")

    with st.form("citizen_complaint_form", clear_on_submit=False):
        # Category Selector
        category_options = [
            "🛣️ रस्ते व वाहतूक समस्या",
            "💧 पाणीपुरवठा व जलवाहिनी",
            "⚡ वीज, ट्रान्सफॉर्मर व पथदिवे",
            "🚜 शेती, सिंचन व नुकसानभरपाई",
            "🏥 आरोग्य व शासकीय रुग्णालय",
            "🗑️ स्वच्छता व सांडपाणी ड्रेनेज",
            "🏫 शिक्षण व शाळा दुरुस्ती",
            "⚖️ इतर सामाजिक समस्या"
        ]
        selected_category = st.selectbox("१. समस्येचा प्रकार निवडा *", category_options)

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            name = st.text_input("२. आपले पूर्ण नाव *", placeholder="उदा. रमेश मारुती पाटील")
            village = st.text_input("४. गाव किंवा शहर *", placeholder="उदा. विटा / भाळवणी / लेंगरे")
            area = st.text_input("६. प्रभाग / परिसर / वस्ती", placeholder="उदा. शिवाजी चौक, प्रभाग क्र. ३")

        with f_col2:
            mobile = st.text_input("३. मोबाईल क्रमांक (WhatsApp) *", placeholder="१० अंकी मोबाईल नंबर", max_chars=10)
            taluka = st.selectbox("५. तालुका *", ["खानापूर तालुका", "विटा नगरपालिका क्षेत्र", "आटपाडी परिसर"])
            whatsapp_opt = st.checkbox("तक्रारीचे सर्व अपडेट्स मला थेट WhatsApp वर मिळावेत", value=True)

        description = st.text_area(
            "७. समस्येचे सविस्तर वर्णन *",
            placeholder="समस्या कुठे आहे? किती दिवसांपासून प्रलंबित आहे? नेमकी काय अडचण होत आहे ते सविस्तर लिहा...",
            height=120
        )

        uploaded_photos = st.file_uploader(
            "८. समस्येचा फोटो जोडा (ऐच्छिक, कमाल ३ फोटो)",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True
        )

        consent = st.checkbox("मी दिलेली वरील सर्व माहिती सत्य असून ती समस्या निवारणासाठी वापरण्यास सहमती देत आहे.", value=True)

        submit_btn = st.form_submit_button("🚀 तक्रार कार्यालयाकडे दाखल करा", use_container_width=True, type="primary")

    if submit_btn:
        if not name.strip() or not mobile.strip() or not village.strip() or not description.strip():
            st.error("कृपया आवश्यक असलेली सर्व माहिती (*) पूर्ण भरा.")
        elif len(mobile.strip()) < 10 or not mobile.strip().isdigit():
            st.error("कृपया वैध १० अंकी मोबाईल क्रमांक प्रविष्ट करा.")
        elif not consent:
            st.warning("कृपया सहमतीच्या पर्यायावर टिक करा.")
        else:
            complaint_id = f"APD-{datetime.now().year}-{random.randint(100000, 999999)}"
            record = {
                "id": complaint_id,
                "name": name.strip(),
                "mobile": mobile.strip(),
                "village": village.strip(),
                "taluka": taluka,
                "area": area.strip() if area else "परिसर",
                "category": selected_category,
                "description": description.strip(),
                "whatsapp_opt_in": whatsapp_opt,
                "status": "प्रक्रियेत",
                "stage": 2,
                "remark": "तक्रार जनसंपर्क कार्यालयात नोंदवली असून प्राथमिक छाननी सुरू आहे."
            }

            # 1. Save to Database
            save_complaint_to_db(record)

            # 2. Dispatch Email to sagareparth@gmail.com
            with st.spinner("तक्रार नोंदवली जात आहे आणि कार्यालयाकडे ईमेल पाठवला जात आहे..."):
                email_sent, email_msg = send_email_notification(record, uploaded_photos)

            st.balloons()
            st.success(f"✓ तक्रार यशस्वीरित्या नोंदवली गेली आहे! आपला तक्रार क्रमांक: **{complaint_id}**")
            
            if email_sent:
                st.info(f"📧 **ईमेल सूचना:** {email_msg}")
            else:
                st.warning(f"📧 **ईमेल स्थिती:** {email_msg}\n*(तक्रार डेटाबेसमध्ये सुरक्षित सेव्ह झाली आहे.)*")

            st.markdown(f"""
            > **महत्त्वाची नोंद:** कृपया हा तक्रार क्रमांक **`{complaint_id}`** जतन करून ठेवा.  
            > आपण वरील **'🔎 तक्रारीचा मागोवा'** टॅबमध्ये हा क्रमांक टाकून कामाची थेट प्रगती पाहू शकता.
            """)

# ====================================================
# TAB 2: तक्रारीचा मागोवा (Tracking)
# ====================================================
with tab_track:
    st.subheader("🔎 तक्रारीची सद्यस्थिती तपासा")
    st.caption("आपला तक्रार क्रमांक टाकून कामाची प्रगती आणि अधिकाऱ्यांचा रिमार्क तपासा.")

    # Demo Buttons
    d_col1, d_col2 = st.columns([1, 1])
    with d_col1:
        if st.button("🔹 डेमो १: प्रक्रियेत असलेली तक्रार (रस्ते)"):
            st.session_state["track_input"] = "APD-2026-102450"
    with d_col2:
        if st.button("🟢 डेमो २: पूर्ण झालेली तक्रार (पाणीपुरवठा)"):
            st.session_state["track_input"] = "APD-2026-101180"

    current_val = st.session_state.get("track_input", "APD-2026-102450")
    track_query = st.text_input("तक्रार क्रमांक टाका:", value=current_val, placeholder="उदा. APD-2026-102450")

    if st.button("🔎 मागोवा तपासा", type="primary"):
        data = get_complaint_from_db(track_query)
        if not data:
            st.error("सदर तक्रार क्रमांक सापडला नाही. कृपया योग्य क्रमांक टाका.")
        else:
            stage = data.get("stage", 2)
            is_resolved = stage >= 4

            badge_color = "🟢" if is_resolved else "⚙️"
            status_text = "काम पूर्ण झाले" if is_resolved else "प्रक्रियेत / कारवाई सुरू आहे"

            st.markdown(f"""
            <div class="tracker-step-box">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <span style="background:#fff7ed; color:#ea580c; border:1px solid #fed7aa; padding:4px 10px; border-radius:6px; font-weight:800; font-size:13px;">
                    {data['id']}
                  </span>
                  <h3 style="margin:8px 0 2px; color:#0f172a;">{data['category']}</h3>
                  <p style="font-size:13px; color:#64748b; margin:0;">
                    {data['area']}, {data['village']} (ता. {data['taluka']}) • तक्रारदार: {data['name']}
                  </p>
                </div>
                <div style="font-size:15px; font-weight:bold; color:{'#059669' if is_resolved else '#2563eb'};">
                  {badge_color} {status_text}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Stepper Progress Bar
            step_cols = st.columns(4)
            with step_cols[0]:
                st.success("१. तक्रार प्राप्त ✓")
            with step_cols[1]:
                if stage >= 2:
                    st.success("२. कार्यालय पडताळणी ✓")
                else:
                    st.info("२. कार्यालय पडताळणी")
            with step_cols[2]:
                if stage >= 3:
                    st.success("३. अधिकारी पाठपुरावा ✓")
                else:
                    st.warning("३. अधिकारी पाठपुरावा")
            with step_cols[3]:
                if stage >= 4:
                    st.success("४. निवारण पूर्ण ✓")
                else:
                    st.write("४. निवारण प्रलंबित")

            st.markdown(f"""
            <div class="remark-box">
              <strong>📌 जनसंपर्क कार्यालयाची अधिकृत नोंद:</strong><br>
              {data.get('remark', 'तक्रार तपासणी व संबंधित विभागाशी पत्रव्यवहार सुरू आहे.')}
            </div>
            """, unsafe_allow_html=True)

# ====================================================
# TAB 3: मार्गी लागलेली कामे (Showcase)
# ====================================================
with tab_works:
    st.subheader("🏆 दादांच्या प्रयत्नातून मार्गी लागलेली प्रमुख कामे")
    st.caption("नागरिकांच्या तक्रारी व मागण्यांवर प्रत्यक्ष पूर्ण झालेल्या कामांचा संक्षिप्त अहवाल.")

    w1, w2, w3 = st.columns(3)
    with w1:
        st.image("https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?auto=format&fit=crop&w=600&q=80", use_column_width=True)
        st.markdown("**✓ विटा–भाळवणी मुख्य रस्ता डांबरीकरण**")
        st.caption("खड्ड्यांच्या तक्रारीनंतर तातडीने निधी उपलब्ध करून २.५ किमी रस्त्याचे डांबरीकरण यशस्वीरित्या पूर्ण.")

    with w2:
        st.image("https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80", use_column_width=True)
        st.markdown("**✓ खानापूर शेतीसाठी नवीन ट्रान्सफॉर्मर मंजूर**")
        st.caption("वारंवार वीज खंडित होणाऱ्या शेतकऱ्यांच्या तक्रारीवरून महावितरणकडून नवीन १०० KVA ट्रान्सफॉर्मर बसवला.")

    with w3:
        st.image("https://images.unsplash.com/photo-1541888946425-d0fbb1861593?auto=format&fit=crop&w=600&q=80", use_column_width=True)
        st.markdown("**✓ लेंगरे ग्रामीण पाणीपुरवठा पाईपलाईन दुरुस्ती**")
        st.caption("नादुरुस्त मुख्य जलवाहिनी अवघ्या ४८ तासांत दुरुस्त करून गावातील पिण्याच्या पाण्याचा प्रश्न मार्गी लावला.")

# ====================================================
# TAB 4: AI नागरिक सहाय्यक (Chatbot)
# ====================================================
with tab_ai:
    st.subheader("🤖 आपले दादा डिजिटल नागरिक सहाय्यक")
    st.caption("विटा–खानापूर परिसरातील नागरिक समस्या, योजना व तक्रार प्रक्रियेबाबत २४×७ डिजिटल मार्गदर्शन.")

    # Quick prompt buttons
    st.markdown("**💡 वारंवार विचारले जाणारे प्रश्न (क्लिक करा):**")
    q_col1, q_col2, q_col3, q_col4 = st.columns(4)
    with q_col1:
        if st.button("🛣️ रस्त्याची तक्रार कशी करावी?"):
            st.session_state["ai_query"] = "रस्त्यावरील खड्ड्यांची किंवा डांबरीकरणाची तक्रार कशी करावी?"
    with q_col2:
        if st.button("💧 पाणीपुरवठा समस्या"):
            st.session_state["ai_query"] = "पाणीपुरवठा खंडित झाला असल्यास काय करावे?"
    with q_col3:
        if st.button("🔎 तक्रारीचा मागोवा कसा घ्यायचा?"):
            st.session_state["ai_query"] = "तक्रारीचा मागोवा कसा घ्यायचा?"
    with q_col4:
        if st.button("📍 कार्यालयाचा पत्ता काय?"):
            st.session_state["ai_query"] = "जनसंपर्क कार्यालयाचा पत्ता आणि वेळ काय आहे?"

    # Chat history state
    if "ai_messages" not in st.session_state:
        st.session_state["ai_messages"] = [
            {"role": "assistant", "content": "नमस्कार! 🙏 मी आपले दादा डिजिटल नागरिक सहाय्यक आहे. विटा-खानापूर परिसरातील रस्ते, पाणी, वीज, शेती किंवा तक्रार प्रक्रियेबद्दल आपला प्रश्न खाली विचारा."}
        ]

    for m in st.session_state["ai_messages"]:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # Chat input
    user_prompt = st.chat_input("तुमचा प्रश्न येथे विचारा...")
    if "ai_query" in st.session_state and st.session_state["ai_query"]:
        user_prompt = st.session_state.pop("ai_query")

    if user_prompt:
        st.session_state["ai_messages"].append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)

        # Smart Heuristic Response
        lower_p = user_prompt.lower()
        if "रस्त" in lower_p or "खड्ड" in lower_p:
            reply = "रस्त्यावरील खड्डे किंवा डांबरीकरणाच्या तक्रारीसाठी वरील '📝 नवीन तक्रार नोंदवा' टॅबमध्ये जाऊन 'रस्ते व वाहतूक समस्या' निवडा. रस्त्याचे नाव व शक्य असल्यास फोटो अपलोड करा. सार्वजनिक बांधकाम विभाग व दादांच्या कार्यालयाकडून तत्काळ दखल घेतली जाईल."
        elif "पाणी" in lower_p or "नळ" in lower_p or "पाईप" in lower_p:
            reply = "पाणीपुरवठा किंवा जलवाहिनी गळतीची समस्या असल्यास फॉर्ममध्ये 'पाणीपुरवठा व जलवाहिनी' निवडा. आपत्कालीन टँकर किंवा व्हॉल्व्ह दुरुस्तीसाठी जनसंपर्क कार्यालयाची टीम संबंधित ग्रामपंचायतीशी समन्वय साधून काम तातडीने मार्गी लावेल."
        elif "मागोवा" in lower_p or "ट्रॅक" in lower_p or "नंबर" in lower_p:
            reply = "तक्रार नोंदवल्यावर मिळालेला APD-2026-XXXXXX हा क्रमांक वरील '🔎 तक्रारीचा मागोवा' टॅबमध्ये टाका. तिथे तुम्हाला १ ते ४ पायऱ्यांमध्ये कामाची सद्यस्थिती आणि अधिकाऱ्यांची नोंद दिसेल."
        elif "पत्ता" in lower_p or "वेळ" in lower_p or "कार्यालय" in lower_p:
            reply = "मा. श्री. वैभव दादा मुख्य जनसंपर्क कार्यालय: शिवाजी चौक, विटा, ता. खानापूर, जि. सांगली. कार्यालयीन वेळ: दररोज सकाळी ९:०० ते सायं. ७:००. दूरध्वनी: ०२३४७-२७२०००."
        elif "वीज" in lower_p or "ट्रान्सफॉर्मर" in lower_p or "डीपी" in lower_p:
            reply = "वीज खंडित होणे किंवा नवीन शेती ट्रान्सफॉर्मरसाठी फॉर्ममध्ये 'वीज, ट्रान्सफॉर्मर व पथदिवे' निवडा. महावितरणच्या (MSEDCL) कार्यकारी अभियंत्यांशी थेट पाठपुरावा केला जाईल."
        else:
            reply = f"धन्यवाद! आपला प्रश्न '{user_prompt}' नोंदवला आहे. विटा-खानापूर जनसंपर्क कार्यालय नागरिकांच्या सेवेसाठी सदैव तत्पर आहे. अधिक मदतीसाठी आपण वरील फॉर्मद्वारे थेट तक्रार दाखल करू शकता किंवा ०२३४७-२७२००० वर संपर्क साधू शकता."

        st.session_state["ai_messages"].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)

# ====================================================
# TAB 5: जनसंपर्क कार्यालय संपर्क
# ====================================================
with tab_contact:
    st.subheader("🏢 जनसंपर्क कार्यालय पत्ता व थेट संपर्क")
    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.markdown("""
        **मा. श्री. वैभव दादा जनसंपर्क कक्ष**  
        📍 **पत्ता:** मुख्य जनसंपर्क कार्यालय, शिवाजी चौक, विटा, ता. खानापूर, जि. सांगली - ४१५३११  
        📞 **दूरध्वनी:** ०२३४७-२७२००० / ९८२२००००००  
        ⏰ **कार्यालयीन वेळ:** दररोज सकाळी ९:०० ते सायं. ७:००  
        ✉️ **ईमेल:** `sagareparth@gmail.com`
        """)

    with info_col2:
        st.info("""
        **📌 नागरिकांसाठी महत्त्वाची सूचना:**  
        हे पोर्टल स्थानिक नागरिक व लोकप्रतिनिधी यांच्यातील संवादासाठी तयार केलेले डिजिटल साधन आहे. 
        शासकीय आपत्कालीन मदतीसाठी (उदा. पोलीस १००, रुग्णवाहिका १०८) नागरिकांनी थेट अधिकृत शासकीय क्रमांकांवर संपर्क करावा.
        """)

# ----------------------------------------------------
# 7. Footer
# ----------------------------------------------------
st.markdown("""
<div style="text-align:center; padding:20px 0; color:#94a3b8; font-size:13px; border-top:1px solid #e2e8f0; margin-top:40px;">
  © २०२६ <strong>आपले दादा जनसंपर्क कक्ष</strong> • विटा–खानापूर विधानसभा मतदारसंघ • सर्व हक्क राखीव
</div>
""", unsafe_allow_html=True)
