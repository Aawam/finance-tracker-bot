# Deploy ke Render.com (Gratis)

> Render free tier: bot tidur setelah 15 menit idle, butuh 30-60 detik untuk bangun saat command pertama. Karena kamu pakai **on-demand**, ini bukan masalah.

---

## Langkah 1: Push kode ke GitHub

Buka terminal di folder `telegram-bot`:

```bash
cd C:/Users/paijo/Documents/Finance/telegram-bot

# Inisialisasi git
git init
git add .
git commit -m "Initial bot"

# Buat repo baru di GitHub
# (https://github.com/new — nama: finance-tracker-bot, visibility: Public atau Private)

# Hubungkan & push
git remote add origin https://github.com/USERNAME/finance-tracker-bot.git
git branch -M main
git push -u origin main
```

> **Belum punya akun GitHub?** Daftar gratis di https://github.com/signup

---

## Langkah 2: Buat akun Render.com

1. Buka https://render.com
2. Klik **Get Started for Free**
3. Sign up pakai **GitHub** (paling gampang — otomatis ter-link)
4. Verifikasi email jika diminta

---

## Langkah 3: Deploy Bot

1. Di Render dashboard, klik **New +** → **Web Service** (bukan Background Worker — bot Telegram pakai polling, jadi butuh web service)

2. Pilih **"Build and deploy from a Git repository"** → klik **Next**

3. Cari & pilih repo `finance-tracker-bot` yang baru kamu push

4. Isi form:

   | Field | Isi |
   |---|---|
   | **Name** | `finance-tracker-bot` (atau nama lain) |
   | **Region** | Singapore (dekat Indonesia) atau Oregon |
   | **Branch** | `main` |
   | **Root Directory** | (kosongkan) |
   | **Runtime** | `Docker` |
   | **Instance Type** | `Free` |

5. Klik **Advanced** → **Add Environment Variable**:

   | Key | Value |
   |---|---|
   | `BOT_TOKEN` | `8927162715:AAG5CZm-sgpz9W538VjpKdAQ17THXK-fQV8` |
   | `DB_PATH` | `/var/data/finance.db` |

6. Klik **Create Web Service**

---

## Langkah 4: Tunggu Build Selesai

- Render akan build Docker image (~2-5 menit pertama kali)
- Log akan muncul di layar
- Tunggu sampai muncul: `Bot started. Polling...`
- Kalau ada error merah, lihat log detail

---

## Langkah 5: Setup Persistent Disk (Penting!)

Supaya database SQLite tidak hilang saat restart:

1. Di halaman service kamu, klik tab **Disks** (kiri)
2. Klik **Add Disk**
   - **Name**: `finance-data`
   - **Mount Path**: `/var/data`
   - **Size**: 1 GB (gratis)
3. Klik **Save** → Render akan redeploy otomatis

> ⚠️ **WAJIB**: Tanpa disk ini, semua data hilang setiap restart.

---

## Langkah 6: Test Bot

1. Buka Telegram
2. Cari bot kamu (username yang kamu daftarkan di BotFather)
3. Kirim `/start`
4. Coba `/income 8500000 Test transaksi`
5. Cek `/balance`

Kalau ada error atau bot tidak merespon, lihat log di Render dashboard (tab **Logs**).

---

## ⚠️ Catatan Penting tentang Free Tier

1. **Cold start**: Setelah 15 menit tidak ada chat, bot tidur. Command pertama butuh 30-60 detik (tapi on-demand jadi tidak masalah).

2. **Build credit**: Free tier kasih 500 menit build/bulan. Setiap push ke GitHub = 1 build ~3 menit. Cukup untuk ~150 push/bulan.

3. **Auto-deploy**: Setiap kali kamu `git push`, Render otomatis deploy ulang. Bisa di-disable di Settings → Auto-Deploy.

---

## 🔧 Update Bot (Nanti)

Kalau mau ubah kode bot:

```bash
# Edit file bot.py / yang lain
git add .
git commit -m "Update fitur X"
git push
```

Render otomatis rebuild & restart. Database **tidak hilang** karena ada di disk.

---

## 🆘 Troubleshooting

### Bot tidak merespon
- Cek tab **Logs** di Render — cari error merah
- Pastikan `BOT_TOKEN` env var benar (cek di tab Environment)
- Cek `/start` di Telegram — kalau gak ada reply, bot crash

### "ModuleNotFoundError: No module named 'telegram'"
- Pastikan `requirements.txt` ada di repo dan ter-push
- Cek Dockerfile sudah `COPY requirements.txt .`

### Database hilang
- Pastikan Disk ter-setup (Step 5)
- Cek `DB_PATH=/var/data/finance.db` di env var
- Cek mount path disk sama (`/var/data`)

### Mau lihat log real-time
- Tab **Logs** di Render dashboard → auto-refresh tiap beberapa detik

---

## 🎉 Selesai!

Bot kamu online 24/7 (dengan jeda cold start). Buka Telegram, chat bot, mulai catat keuangan!