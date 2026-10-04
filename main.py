import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import init_db, insert_complaint, get_complaint, get_stats
from email_service import send_complaint_email, DEFAULT_RECEIVER

load_dotenv()

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database
    init_db()
    print("✓ SQLite database initialized.")
    yield

app = FastAPI(title="आपले दादा नागरिक तक्रार पोर्टल API", lifespan=lifespan)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_complaint_id() -> str:
    year = datetime.now().year
    rand_num = random.randint(100000, 999999)
    return f"APD-{year}-{rand_num}"

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "Aaple Dada Portal", "target_email": DEFAULT_RECEIVER}

@app.get("/api/stats")
async def fetch_stats():
    return get_stats()

@app.get("/api/complaints/{complaint_id}")
async def fetch_complaint(complaint_id: str):
    record = get_complaint(complaint_id)
    if not record:
        raise HTTPException(status_code=404, detail="तक्रार क्रमांक सापडला नाही.")
    return record

@app.post("/api/complaints")
async def submit_complaint(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    mobile: str = Form(...),
    village: str = Form(...),
    taluka: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    area: Optional[str] = Form(None),
    gps_lat: Optional[float] = Form(None),
    gps_lng: Optional[float] = Form(None),
    whatsapp_opt_in: bool = Form(True),
    photos: List[UploadFile] = File(default=[])
):
    complaint_id = generate_complaint_id()
    saved_photo_paths: List[str] = []

    # Handle photo uploads
    if photos:
        for idx, file in enumerate(photos):
            if file and file.filename:
                # Get clean extension
                ext = Path(file.filename).suffix or ".jpg"
                save_filename = f"{complaint_id}_{idx+1}{ext}"
                dest_path = UPLOAD_DIR / save_filename
                content = await file.read()
                with open(dest_path, "wb") as f:
                    f.write(content)
                saved_photo_paths.append(str(dest_path))

    # Save to SQLite database
    complaint_data = {
        "id": complaint_id,
        "name": name.strip(),
        "mobile": mobile.strip(),
        "village": village.strip(),
        "taluka": taluka.strip(),
        "area": area.strip() if area else "",
        "category": category.strip(),
        "description": description.strip(),
        "gps_lat": gps_lat,
        "gps_lng": gps_lng,
        "photos": [Path(p).name for p in saved_photo_paths],
        "whatsapp_opt_in": whatsapp_opt_in,
        "status": "प्रक्रियेत",
        "stage": 2,
        "remark": "तक्रार जनसंपर्क कार्यालयात नोंदवली असून प्राथमिक छाननी सुरू आहे."
    }
    insert_complaint(complaint_data)

    # Dispatch email in background task to sagareparth@gmail.com
    background_tasks.add_task(
        send_complaint_email,
        complaint_id=complaint_id,
        name=name.strip(),
        mobile=mobile.strip(),
        village=village.strip(),
        taluka=taluka.strip(),
        area=area.strip() if area else "",
        category=category.strip(),
        description=description.strip(),
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        whatsapp_opt_in=whatsapp_opt_in,
        photo_paths=saved_photo_paths,
        receiver_email=DEFAULT_RECEIVER
    )

    return JSONResponse(content={
        "success": True,
        "id": complaint_id,
        "message": f"तक्रार यशस्वीरित्या नोंदवली गेली आहे. ईमेल द्वारे {DEFAULT_RECEIVER} वर सूचना पाठवली आहे.",
        "details": complaint_data
    })

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Serve frontend static assets (HTML, CSS, Images)
@app.get("/")
async def serve_index():
    return FileResponse(BASE_DIR / "index.html")

# Fallback mount for other files like dada.jpg
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
