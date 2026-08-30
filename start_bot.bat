@echo off
title Finance Tracker Bot
echo Starting Finance Tracker Bot...
echo Bot akan jalan di window ini. JANGAN TUTUP window ini.
echo Untuk stop: tutup window ini atau tekan Ctrl+C.
echo.
cd /d "C:\Users\paijo\Documents\Finance\telegram-bot"
"C:\Users\paijo\finance-env\Scripts\python.exe" bot.py
pause