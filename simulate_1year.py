# -*- coding: utf-8 -*-
"""
Simulasi 1 tahun transaksi (Sept 2025 – Agust 2026).
Data REALISTIS untuk perusahaan kecil-menengah Indonesia.

Profil bisnis:
- Toko online + jasa (campuran)
- Pendapatan: 5-15 jt/bulan (naik bertahap)
- Pengeluaran: gaji 1 orang (5jt/bulan), sewa 2.5jt/bulan, utilitas, iklan, dll
- Modal awal 50jt

Hasil:
- Ngeprint ringkasan bulanan
- Generate laporan lengkap akhir tahun
"""
import os, sys, random
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))

# Pakai database terpisah khusus simulasi (supaya data riil tidak tercampur)
SIM_DB = os.path.join(os.path.dirname(__file__), "data", "sim_1year.db")
if os.path.exists(SIM_DB):
    os.remove(SIM_DB)

os.environ["DB_PATH"] = SIM_DB

from db import make_engine, make_session, Account, Transaction, JournalLine
from accounts_seed import ACCOUNTS, EXPENSE_CATEGORIES, CATEGORY_LIST
from accounting import (
    post_transaction, next_jv_number, account_balance, all_balances,
    report_income_statement, report_balance_sheet, report_cash_flow,
    report_by_category,
)

random.seed(42)  # reproducible

# ============================================================
# BANGUN TRANSAKSI
# ============================================================

def build_year(start_date: datetime):
    """Generate 1 tahun transaksi."""
    txn_list = []
    jv_counter = 1

    def jv():
        nonlocal jv_counter
        n = f"JV-{jv_counter:03d}"
        jv_counter += 1
        return n

    cur = start_date
    for month_offset in range(12):
        # Setiap bulan: tren naik 5% MoM untuk revenue, gaji tetap 5jt
        growth = 1 + (0.05 * month_offset)
        revenue_base = 7_000_000 * growth
        cur_month = cur.replace(day=1) + timedelta(days=30*month_offset)

        # ----- PENDAPATAN (2-4 transaksi per bulan) -----
        n_sales = random.randint(3, 5)
        for i in range(n_sales):
            day = random.randint(1, 27)
            amount = int(revenue_base / n_sales * random.uniform(0.7, 1.3))
            description = random.choice([
                "Penjualan online Tokopedia",
                "Penjualan online Shopee",
                "Penjualan ke reseller Jakarta",
                "Penjualan ke toko offline",
                "Penjualan grosir",
            ])
            desc = f"{description} #{i+1}"
            date = cur_month.replace(day=day, hour=10+random.randint(0,8), minute=random.randint(0,59))
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": desc,
                "lines": [
                    {"account_code": "1000", "debit": amount, "credit": 0},
                    {"account_code": "4000", "debit": 0, "credit": amount},
                ],
                "category": "income",
            })

        # Pendapatan jasa (konsultasi / desain / programming)
        if random.random() > 0.3:  # 70% bulan ada jasa
            day = random.randint(1, 27)
            amount = int(revenue_base * random.uniform(0.3, 0.6))
            desc = random.choice([
                "Jasa desain logo klien",
                "Jasa instalasi software",
                "Konsultasi IT klien",
                "Jasa maintenance website",
                "Training klien",
            ])
            date = cur_month.replace(day=day, hour=14, minute=random.randint(0,59))
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": desc,
                "lines": [
                    {"account_code": "1000", "debit": amount, "credit": 0},
                    {"account_code": "4100", "debit": 0, "credit": amount},
                ],
                "category": "income",
            })

        # ----- BEBAN OPERASIONAL -----

        # Gaji karyawan (tiap bulan, tgl 5)
        gaji = 5_000_000
        date = cur_month.replace(day=5, hour=10)
        txn_list.append({
            "date": date,
            "jv": jv(),
            "desc": "Bayar gaji karyawan",
            "lines": [
                {"account_code": "5000", "debit": gaji, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": gaji},
            ],
            "category": "gaji",
        })

        # Sewa kantor (tiap bulan, tgl 1)
        sewa = 2_500_000
        date = cur_month.replace(day=1, hour=9)
        txn_list.append({
            "date": date,
            "jv": jv(),
            "desc": "Bayar sewa kantor",
            "lines": [
                {"account_code": "5100", "debit": sewa, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": sewa},
            ],
            "category": "utilitas",
        })

        # Listrik & internet (tiap bulan, tgl 10)
        utilitas = random.randint(450_000, 700_000)
        date = cur_month.replace(day=10, hour=11)
        txn_list.append({
            "date": date,
            "jv": jv(),
            "desc": "Bayar listrik & WiFi",
            "lines": [
                {"account_code": "5200", "debit": utilitas, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": utilitas},
            ],
            "category": "utilitas",
        })

        # ATK / supplies (1-2x sebulan)
        for _ in range(random.randint(1, 2)):
            day = random.randint(5, 25)
            amount = random.randint(50_000, 250_000)
            desc = random.choice(["Beli ATK", "Tinta printer", "Kertas", "Map & ordner"])
            date = cur_month.replace(day=day, hour=random.randint(9,16))
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": desc,
                "lines": [
                    {"account_code": "5300", "debit": amount, "credit": 0},
                    {"account_code": "1000", "debit": 0, "credit": amount},
                ],
                "category": "operasional",
            })

        # Transportasi (2-4x sebulan)
        for _ in range(random.randint(2, 4)):
            day = random.randint(1, 28)
            amount = random.randint(30_000, 200_000)
            desc = random.choice([
                "Bensin motor ke bank",
                "Grab ke supplier",
                "Ojol ke klien",
                "Parkir & tol",
            ])
            date = cur_month.replace(day=day, hour=random.randint(8,18))
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": desc,
                "lines": [
                    {"account_code": "5400", "debit": amount, "credit": 0},
                    {"account_code": "1000", "debit": 0, "credit": amount},
                ],
                "category": "transport",
            })

        # Iklan / pemasaran (1-3x sebulan)
        for _ in range(random.randint(1, 3)):
            day = random.randint(1, 28)
            amount = random.randint(100_000, 800_000)
            desc = random.choice([
                "Iklan Instagram",
                "Iklan Facebook",
                "Iklan TikTok",
                "Boost post marketplace",
                "Banner offline",
            ])
            date = cur_month.replace(day=day, hour=random.randint(9,21))
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": desc,
                "lines": [
                    {"account_code": "5500", "debit": amount, "credit": 0},
                    {"account_code": "1000", "debit": 0, "credit": amount},
                ],
                "category": "pemasaran",
            })

        # ----- TRANSAKSI SPESIAL -----

        # Pembelian aset (1-2x setahun — laptop/HP/komputer)
        if month_offset in (2, 7):
            day = random.randint(5, 25)
            amount = random.choice([8_000_000, 12_000_000, 15_000_000])
            date = cur_month.replace(day=day, hour=13)
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": random.choice(["Beli laptop baru", "Beli printer", "Beli HP untuk operasional"]),
                "lines": [
                    {"account_code": "1500", "debit": amount, "credit": 0},
                    {"account_code": "1000", "debit": 0, "credit": amount},
                ],
                "category": "peralatan",
            })

        # Stok barang dagangan (3-4x setahun)
        if month_offset in (3, 6, 9, 11):
            day = random.randint(5, 25)
            amount = random.randint(2_000_000, 5_000_000)
            date = cur_month.replace(day=day, hour=11)
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": "Beli stok barang dagangan",
                "lines": [
                    {"account_code": "1200", "debit": amount, "credit": 0},
                    {"account_code": "1000", "debit": 0, "credit": amount},
                ],
                "category": None,
            })

        # Dividen pemilik (setiap 3 bulan)
        if month_offset % 3 == 2:
            day = random.randint(20, 28)
            amount = 1_500_000
            date = cur_month.replace(day=day, hour=15)
            txn_list.append({
                "date": date,
                "jv": jv(),
                "desc": "Pengambilan dividen pemilik",
                "lines": [
                    {"account_code": "3000", "debit": amount, "credit": 0},
                    {"account_code": "1000", "debit": 0, "credit": amount},
                ],
                "category": None,
            })

    # Sort by date
    txn_list.sort(key=lambda x: x["date"])

    # Re-assign JV numbers sequential
    for i, t in enumerate(txn_list, 1):
        t["jv"] = f"JV-{i:04d}"

    return txn_list


# ============================================================
# EKSEKUSI
# ============================================================

def main():
    print("="*70)
    print("SIMULASI 1 TAHUN — Sept 2025 s/d Agust 2026")
    print("="*70)

    # Init DB
    engine = make_engine(SIM_DB)
    session = make_session(engine)

    # Seed accounts
    if session.query(Account).count() == 0:
        for code, name, type_, normal in ACCOUNTS:
            session.add(Account(code=code, name=name, type=type_, normal_side=normal))
        session.commit()
        print(f"✓ Seeded {len(ACCOUNTS)} akun\n")

    # Modal awal (1 Sept 2025)
    start = datetime(2025, 9, 1, 9, 0, 0)
    modal = 50_000_000
    _, err = post_transaction(session, "JV-0001", "Setoran modal awal pemilik",
        [{"account_code":"1000","debit":modal,"credit":0},
         {"account_code":"3000","debit":0,"credit":modal}],
        txn_date=start, category=None)
    print(f"✓ Modal awal disetor: Rp {modal:,} pada {start:%d %b %Y}")

    # Generate & post transaksi
    txns = build_year(start.replace(day=1))
    print(f"✓ Generate {len(txns)} transaksi simulasi")
    print(f"⏳ Posting ke database...")

    for t in txns:
        _, err = post_transaction(session, t["jv"], t["desc"], t["lines"],
                                  txn_date=t["date"], category=t["category"])
        if err:
            print(f"❌ {t['jv']}: {err}")
            return
    print(f"✓ Semua transaksi berhasil dicatat\n")

    # ============================================================
    # TAMPILKAN LAPORAN
    # ============================================================

    print("="*70)
    print("LAPORAN PER BULAN")
    print("="*70)

    monthly_data = []
    for m in range(12):
        # Hitung range bulan
        year = 2025 if m < 4 else 2026
        month = 9 + m if m < 4 else m - 3
        first = datetime(year, month, 1)
        if month == 12:
            last = datetime(year+1, 1, 1) - timedelta(seconds=1)
        else:
            last = datetime(year, month+1, 1) - timedelta(seconds=1)
        r = report_income_statement(session, first, last)
        monthly_data.append((first, r))
        print(f"  {first:%b %Y}  Pendapatan: Rp {r['income']:>14,.0f}   "
              f"Beban: Rp {r['expense']:>13,.0f}   "
              f"{'Laba' if r['net']>=0 else 'Rugi'}: Rp {abs(r['net']):>11,.0f}")

    # Tahun penuh
    print("\n" + "="*70)
    print("LAPORAN TAHUNAN (Sept 2025 – Agust 2026)")
    print("="*70)
    r = report_income_statement(session)
    print(f"\n💰 PENDAPATAN:")
    print(f"  Total: Rp {r['income']:,.0f}")
    print(f"  Rata-rata/bulan: Rp {r['income']/12:,.0f}")
    print(f"\n💸 BEBAN:")
    for name, amt in r["expense_items"]:
        if amt > 0:
            print(f"  {name:30s} Rp {amt:>13,.0f}")
    print(f"  Total: Rp {r['expense']:,.0f}")
    print(f"  Rata-rata/bulan: Rp {r['expense']/12:,.0f}")
    print(f"\n📊 LABA BERSIH TAHUNAN: Rp {r['net']:,.0f}")
    if r["income"] > 0:
        print(f"📈 Margin: {float(r['net']/r['income'])*100:.1f}%")

    # Neraca akhir tahun
    print("\n" + "="*70)
    print("NERACA AKHIR (per 31 Agustus 2026)")
    print("="*70)
    bs = report_balance_sheet(session)
    print(f"\n💎 ASET:")
    print(f"  Kas & Bank:     Rp {account_balance(session, '1000'):,.0f}")
    print(f"  Piutang:        Rp {account_balance(session, '1100'):,.0f}")
    print(f"  Persediaan:     Rp {account_balance(session, '1200'):,.0f}")
    print(f"  Peralatan:      Rp {account_balance(session, '1500'):,.0f}")
    print(f"  TOTAL ASET:     Rp {bs['aset']:,.0f}")
    print(f"\n📌 LIABILITAS:     Rp {bs['liabilitas']:,.0f}")
    print(f"\n💼 EKUITAS:")
    print(f"  Modal Pemilik:  Rp {account_balance(session, '3000'):,.0f}")
    print(f"  Laba Ditahan:   Rp {account_balance(session, '3100'):,.0f}")
    print(f"  Laba Tahun Ini: Rp {bs['laba']:,.0f}")
    print(f"  TOTAL EKUITAS:  Rp {bs['total_ekuitas']:,.0f}")
    print(f"\n{'✓ BALANCE SHEET SEIMBANG' if bs['balance'] else '⚠ TIDAK SEIMBANG'}")

    # Cash flow
    print("\n" + "="*70)
    print("ARUS KAS TAHUNAN")
    print("="*70)
    cf = report_cash_flow(session)
    print(f"\n⬇️  Total Kas Masuk:   Rp {cf['in']:,.0f}")
    print(f"⬆️  Total Kas Keluar:  Rp {cf['out']:,.0f}")
    print(f"📊 Net Cash Flow:     Rp {cf['net']:,.0f}")
    print(f"💰 Saldo Akhir Kas:   Rp {cf['saldo_akhir']:,.0f}")

    # By category
    print("\n" + "="*70)
    print("PENGELUARAN PER KATEGORI")
    print("="*70)
    cats = report_by_category(session)
    total_exp = sum(cats.values())
    print(f"\n{'Kategori':<25} {'Nominal':>16} {'%':>8}")
    print("-"*70)
    for cat, amt in cats.items():
        if amt > 0:
            pct = float(amt/total_exp)*100 if total_exp else 0
            print(f"  {cat.title():<23} Rp {amt:>13,.0f} {pct:>7.1f}%")
    print("-"*70)
    print(f"  {'TOTAL':<23} Rp {total_exp:>13,.0f} 100.0%")

    # Statistik
    print("\n" + "="*70)
    print("STATISTIK")
    print("="*70)
    total_txns = session.query(Transaction).count()
    first_txn = session.query(Transaction).order_by(Transaction.id).first()
    last_txn  = session.query(Transaction).order_by(Transaction.id.desc()).first()
    print(f"  Total transaksi : {total_txns}")
    print(f"  Transaksi pertama: {first_txn.jv_number} — {first_txn.description[:40]} ({first_txn.txn_date:%d %b %Y})")
    print(f"  Transaksi terakhir: {last_txn.jv_number} — {last_txn.description[:40]} ({last_txn.txn_date:%d %b %Y})")

    print(f"\n📂 Database simulasi tersimpan di:")
    print(f"  {SIM_DB}")
    print(f"  Ukuran: {os.path.getsize(SIM_DB)/1024:.1f} KB")

    session.close()
    print("\n✅ Simulasi selesai!")


if __name__ == "__main__":
    main()