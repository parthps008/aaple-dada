import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "complaints.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        village TEXT NOT NULL,
        taluka TEXT NOT NULL,
        area TEXT,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        gps_lat REAL,
        gps_lng REAL,
        photos TEXT,
        whatsapp_opt_in INTEGER DEFAULT 1,
        status TEXT DEFAULT 'प्रक्रियेत',
        stage INTEGER DEFAULT 2,
        remark TEXT,
        created_at TEXT
    )
    """)
    conn.commit()

    # Pre-seed demo complaints if empty
    cursor.execute("SELECT COUNT(*) FROM complaints")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute("""
        INSERT INTO complaints (id, name, mobile, village, taluka, area, category, description, status, stage, remark, created_at)
        VALUES 
        ('APD-2026-102450', 'श्री. विजय पाटील', '9822******', 'विटा शहर', 'खानापूर', 'शिवाजी चौक', 'रस्ते व वाहतूक समस्या', 
         'मुख्य रस्त्यावरील खड्डे बुजवून तातडीने डांबरीकरण करणेबाबत.', 'प्रक्रियेत', 3, 
         'सदर समस्येबाबत सार्वजनिक बांधकाम विभाग (PWD) चे उपअभियंता यांच्याशी संपर्क साधण्यात आला असून प्रत्यक्ष पाहणीसाठी टीम रवाना झाली आहे.', '02/10/2026'),
        ('APD-2026-101180', 'श्री. मारुती माने', '9890******', 'भाळवणी', 'खानापूर', 'ग्रामपंचायत परिसर', 'पाणीपुरवठा जलवाहिनी दुरुस्ती', 
         'मुख्य पाईपलाईन लिकेज दुरुस्ती करून नियमित पाणीपुरवठा सुरू करणे.', 'पूर्ण', 4, 
         'नवीन जलवाहिनी जोडणी व व्हॉल्व्ह दुरुस्तीचे काम पूर्ण झाले असून सुरळीत पाणीपुरवठा सुरू करण्यात आला आहे.', '28/09/2026')
        """)
        conn.commit()
    conn.close()

def insert_complaint(data: dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO complaints (
        id, name, mobile, village, taluka, area, category, description,
        gps_lat, gps_lng, photos, whatsapp_opt_in, status, stage, remark, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['id'], data['name'], data['mobile'], data['village'], data['taluka'],
        data.get('area', ''), data['category'], data['description'],
        data.get('gps_lat'), data.get('gps_lng'),
        json.dumps(data.get('photos', [])),
        1 if data.get('whatsapp_opt_in', True) else 0,
        data.get('status', 'प्रक्रियेत'),
        data.get('stage', 2),
        data.get('remark', 'तक्रार जनसंपर्क कार्यालयात नोंदवली असून प्राथमिक छाननी सुरू आहे.'),
        datetime.now().strftime("%d/%m/%Y, %I:%M %p")
    ))
    conn.commit()
    conn.close()

def get_complaint(complaint_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE UPPER(id) = UPPER(?)", (complaint_id.strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d['photos'] = json.loads(d['photos']) if d['photos'] else []
        except Exception:
            d['photos'] = []
        return d
    return None

def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE stage >= 4")
    resolved = cursor.fetchone()[0]
    conn.close()
    return {"total": total + 1480, "resolved": resolved + 1220}  # Add base benchmark count
