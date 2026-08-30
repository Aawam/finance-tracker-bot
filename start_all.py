# -*- coding: utf-8 -*-
"""
Jalankan Bot Telegram + Web Dashboard secara paralel dalam satu proses.
"""
import threading
import subprocess
import sys
import os
import time
from pathlib import Path

if __name__ == "__main__":
    bot_dir = Path(__file__).parent
    py = Path("C:/Users/paijo/finance-env/Scripts/python.exe")

    print("=" * 60)
    print("💼 FINANCE TRACKER — All-in-One Launcher")
    print("=" * 60)
    print()

    def run_bot():
        print("🤖 Starting Telegram Bot...")
        subprocess.run([str(py), str(bot_dir / "bot.py")])

    def run_web():
        time.sleep(2)  # kasih bot duluan
        print("🌐 Starting Web Dashboard at http://localhost:5000 ...")
        env = os.environ.copy()
        env.setdefault("WEB_PORT", "5000")
        subprocess.run([str(py), str(bot_dir / "web.py")], env=env)

    t1 = threading.Thread(target=run_bot, daemon=True)
    t2 = threading.Thread(target=run_web, daemon=True)
    t1.start()
    t2.start()

    try:
        while t1.is_alive() or t2.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")