# 💼 Finance Tracker — Telegram Bot + Web Dashboard

Sistem pencatatan keuangan **Double-Entry Bookkeeping** lengkap via Telegram + Web Dashboard.

## ✨ Fitur

### 🤖 Telegram Bot
| Command | Fungsi |
|---|---|
| `/start`, `/help` | Mulai & panduan |
| `/income 8.5jt Keterangan` | Catat pendapatan (auto-pair Kas → 4000) |
| `/expense 750rb Beli ATK` | Catat pengeluaran — **auto-detect kategori** dari keyword! |
| `/journal 1100 4000 6jt Bayar piutang` | Transaksi manual (pilih akun Debit/Kredit) |
| `/balance` | Saldo semua akun |
| `/cash` | Arus kas |
| `/report` | Laporan L/R bulan ini |
| `/report neraca` | Neraca |
| `/budget` | **Budget vs aktual** (progress bar) |
| `/budget set gaji 0.30` | Set target 30% untuk kategori gaji |
| `/keyword` | **Lihat keyword auto-categorize** |
| `/keyword add operasional hosting` | Tambah keyword |
| `/keyword test Bayar listrik PLN` | Test deteksi |
| `/export` | **Export laporan ke Excel** (file dikirim via Telegram) |
| `/undo JV-005` | Hapus transaksi |
| `/list` | 10 transaksi terakhir |

### 🌐 Web Dashboard (http://localhost:5000)
- **Dashboard**: KPI cards, grafik tren 6 bulan, pie chart kategori, budget progress
- **Jurnal**: Daftar semua transaksi
- **Buku Besar**: Saldo semua akun (highlight merah untuk negatif)
- **L/R**: Income statement
- **Neraca**: Balance sheet + balance check
- **API**: `/api/kpis`, `/api/monthly` untuk auto-refresh JS

### 🧠 Smart Features
1. **Auto-categorization**: Tulis `Bayar listrik PLN` → otomatis `utilitas`. Tambah keyword sendiri dengan `/keyword add`.
2. **Budget tracking**: Set target % per kategori, lihat progress bar real-time, dapat warning kalau overbudget.
3. **Excel export**: Generate workbook 6-sheet via `/export`, langsung dikirim file via Telegram.

## 🗂 Struktur File

```
telegram-bot/
├── bot.py                 # Main Telegram bot
├── web.py                 # Flask web dashboard
├── start_all.py           # Launcher (bot + web paralel)
├── db.py                  # SQLAlchemy models
├── accounting.py          # Double-entry + laporan
├── budget.py              # Smart categorization + budget
├── excel_export.py        # Generate Excel report
├── accounts_seed.py       # Chart of accounts
├── templates/             # HTML templates
├── data/                  # SQLite database
├── exports/               # Excel reports output
└── start_bot.bat          # Windows shortcut
```

## 🚀 Cara Pakai

### 1. Bot Saja
Double-click `Start Bot Only.bat` di Desktop

### 2. Web Dashboard Saja
Double-click `Start Web Dashboard.bat` di Desktop
Akses di browser: **http://localhost:5000**

### 3. Bot + Web Bersamaan (Recommended)
Double-click `Start Finance Tracker.bat` di Desktop

## 📝 Contoh Percakapan Bot

```
User: /income 8.5jt Penjualan PT Maju Jaya
Bot:  ✅ Pendapatan dicatat!
      JV-001 — Penjualan PT Maju Jaya
      💰 Rp 8.500.000 → Kas & Bank (D)
      💼 Rp 8.500.000 → Pendapatan Penjualan (K)
      Saldo Kas: Rp 58.500.000

User: /expense 250rb Iklan Instagram
Bot:  ✅ Pengeluaran dicatat!
      JV-002 — Iklan Instagram
      📂 Kategori: pemasaran (auto-detected)
      💸 Beban (D): Rp 250.000
      💰 Kas (K): Rp 250.000

User: /budget
Bot:  🎯 BUDGET vs AKTUAL — Agustus 2026
      💰 Revenue bulan ini: Rp 8.500.000

      📋 Operasional
       🟢 ▓▓░░░░░░░░ 20% terpakai
       Realisasi: Rp 100.000 / Target: Rp 680.000 (8%)
      ...

User: /export
Bot:  📎 [mengirim file Finance_Report_20260830_0510.xlsx]
```

## 🔧 Setup

```bash
# Install dependencies
pip install python-telegram-bot==21.3 sqlalchemy aiohttp flask openpyxl python-dotenv

# Set environment
export BOT_TOKEN="..."
export DB_PATH="C:/Users/paijo/Documents/Finance/telegram-bot/data/finance.db"
export WEB_PORT=5000

# Run
python bot.py        # bot saja
python web.py        # dashboard saja
python start_all.py  # keduanya
```

## 📦 Deploy ke Render

Lihat `DEPLOY.md`. (Free tier, butuh kartu kredit untuk verifikasi saja.)

## 📜 Lisensi

MIT