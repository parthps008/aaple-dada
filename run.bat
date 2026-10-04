@echo off
title Aaple Dada Portal - FastAPI Server
echo ========================================================
echo   आपले दादा नागरिक तक्रार पोर्टल (FastAPI + SMTP)
echo ========================================================
echo.
echo Server सुरू होत आहे: http://127.0.0.1:8000
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
