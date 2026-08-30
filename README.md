# Telegram Finance Tracker Bot

Bot pencatat keuangan perusahaan/pribadi dengan sistem **Double-Entry Bookkeeping**.

## Stack
- Python 3.11
- python-telegram-bot 21.x
- SQLAlchemy + SQLite
- Deploy: Render.com free tier

## Setup Lokal

```bash
pip install python-telegram-bot sqlalchemy aiohttp
export BOT_TOKEN="..."  # atau pakai .env
python bot.py
```

## Deploy ke Render

Lihat `DEPLOY.md`.

## Struktur

- `bot.py` — entry point, handler command & callback
- `db.py` — SQLAlchemy models & init
- `accounting.py` — logika double-entry & laporan
- `accounts_seed.py` — chart of accounts default