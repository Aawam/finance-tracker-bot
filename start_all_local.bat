@echo off
title Finance Tracker - Bot & Dashboard
echo Starting Finance Tracker (Bot + Web Dashboard)...
echo.
echo Window ini menjalankan:
echo   - Telegram Bot (untuk command /income, /expense, dll)
echo   - Web Dashboard (http://localhost:5000)
echo.
echo JANGAN TUTUP window ini. Untuk stop: tutup window atau Ctrl+C.
echo.
cd /d "C:\Users\paijo\Documents\Finance\telegram-bot"
"C:\Users\paijo\finance-env\Scripts\python.exe" start_all.py
pause
