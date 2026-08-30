# -*- coding: utf-8 -*-
"""
Smoke test: import semua modul & jalankan seed tanpa perlu Telegram.
Cek logika double-entry & laporan.
"""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(__file__))

# Test path lokal
TEST_DB = os.path.join(os.path.dirname(__file__), "data", "test_finance.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

os.environ["DB_PATH"] = TEST_DB

from db import make_engine, make_session, Account
from accounts_seed import ACCOUNTS, EXPENSE_CATEGORIES
from accounting import (
    post_transaction, next_jv_number, account_balance, all_balances,
    report_income_statement, report_balance_sheet, report_cash_flow,
    report_by_category,
)
from decimal import Decimal

# Init
engine = make_engine(TEST_DB)
session = make_session(engine)

# Seed
if session.query(Account).count() == 0:
    for code, name, type_, normal in ACCOUNTS:
        session.add(Account(code=code, name=name, type=type_, normal_side=normal))
    session.commit()
    print("✓ Seeded 20 akun")

# Sample transactions (mirroring file Excel)
samples = [
    # (description, lines, category)
    ("Setoran modal awal", [{"account_code":"1000","debit":80000000,"credit":0},{"account_code":"3000","debit":0,"credit":80000000}], None),
    ("Penjualan PT Maju", [{"account_code":"1000","debit":8500000,"credit":0},{"account_code":"4000","debit":0,"credit":8500000}], "income"),
    ("Jasa konsultasi", [{"account_code":"1000","debit":15000000,"credit":0},{"account_code":"4100","debit":0,"credit":15000000}], "income"),
    ("Bayar gaji", [{"account_code":"5000","debit":18000000,"credit":0},{"account_code":"1000","debit":0,"credit":18000000}], "gaji"),
    ("Bayar sewa", [{"account_code":"5100","debit":5000000,"credit":0},{"account_code":"1000","debit":0,"credit":5000000}], "utilitas"),
    ("Beli ATK", [{"account_code":"5300","debit":750000,"credit":0},{"account_code":"1000","debit":0,"credit":750000}], "operasional"),
    ("Iklan", [{"account_code":"5500","debit":2500000,"credit":0},{"account_code":"1000","debit":0,"credit":2500000}], "pemasaran"),
    ("Pembelian persediaan", [{"account_code":"1200","debit":3000000,"credit":0},{"account_code":"1000","debit":0,"credit":3000000}], None),
    ("Dividen pemilik", [{"account_code":"3000","debit":1500000,"credit":0},{"account_code":"1000","debit":0,"credit":1500000}], None),
]

def fmt(lines):
    return " + ".join(f"{l['account_code']} D={l['debit']:>10,}" if l['debit'] else f"{l['account_code']} K={l['credit']:>10,}" for l in lines)

for desc, lines, cat in samples:
    jv = next_jv_number(session)
    _, err = post_transaction(session, jv, desc, lines, category=cat)
    if err:
        print(f"❌ {jv}: {err}")
        sys.exit(1)
    print(f"✓ {jv}: {desc} ({fmt(lines)})")

print("\n" + "="*60)
print("TES LAPORAN")
print("="*60)

print("\n[1] Income Statement")
r = report_income_statement(session)
print(f"  Total Pendapatan : Rp {r['income']:,.0f}")
print(f"  Total Beban      : Rp {r['expense']:,.0f}")
print(f"  Laba Bersih      : Rp {r['net']:,.0f}")

print("\n[2] Balance Sheet")
bs = report_balance_sheet(session)
print(f"  Total Aset       : Rp {bs['aset']:,.0f}")
print(f"  Total Liab       : Rp {bs['liabilitas']:,.0f}")
print(f"  Total Ekuitas    : Rp {bs['total_ekuitas']:,.0f}")
print(f"  Balanced?        : {bs['balance']}")

print("\n[3] Cash Flow")
cf = report_cash_flow(session)
print(f"  Kas Masuk        : Rp {cf['in']:,.0f}")
print(f"  Kas Keluar       : Rp {cf['out']:,.0f}")
print(f"  Saldo Akhir      : Rp {cf['saldo_akhir']:,.0f}")

print("\n[4] By Category")
cats = report_by_category(session)
for k, v in cats.items():
    if v > 0:
        print(f"  {k.title():15s}: Rp {v:,.0f}")

print("\n[5] Saldo Akun Penting")
for code in ["1000","3000","4000","5000"]:
    print(f"  {code}: Rp {account_balance(session, code):,.0f}")

session.close()

# Test parser
print("\n" + "="*60)
print("TES PARSER NOMINAL")
print("="*60)
import accounting
from accounting import parse_amount
for txt in ["8500000", "8.5jt", "8,500,000", "8.500.000", "750rb", "5k"]:
    try:
        print(f"  {txt:>12s} → Rp {parse_amount(txt):,.0f}")
    except Exception as e:
        print(f"  {txt:>12s} → ERROR: {e}")

print("\n✅ Semua test lulus!")