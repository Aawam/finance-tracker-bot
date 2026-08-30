# -*- coding: utf-8 -*-
"""
Web Dashboard untuk Finance Tracker Bot.
Jalan di http://localhost:5000 — read-only view dari database SQLite.

Halaman:
- /        : Dashboard ringkasan
- /journal : Jurnal umum
- /ledger  : Buku besar (saldo semua akun)
- /report  : Laporan L/R
- /balance : Neraca
- /api/kpis    : JSON endpoint untuk grafik/auto-refresh
"""
import os
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta

from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.dirname(__file__))

from db import make_engine, make_session, Transaction, JournalLine, Account
from accounting import (
    account_balance, all_balances,
    report_income_statement, report_balance_sheet, report_cash_flow,
    report_by_category,
)
from budget import budget_status, all_budgets


DB_PATH = os.environ.get("DB_PATH") or os.path.join(
    os.path.dirname(__file__), "data", "finance.db"
)

app = Flask(__name__,
            template_folder=str(Path(__file__).parent / "templates"),
            static_folder=str(Path(__file__).parent / "static"))


def get_session():
    return make_session(make_engine(DB_PATH))


def to_float(x):
    if x is None: return 0.0
    return float(x)


@app.route("/")
def dashboard():
    session = get_session()
    try:
        r = report_income_statement(session)
        bs = report_balance_sheet(session)
        cf = report_cash_flow(session)
        cats = report_by_category(session)

        # 6 bulan terakhir — ringkasan
        monthly = []
        today = datetime.utcnow()
        for i in range(5, -1, -1):
            t = today - timedelta(days=30*i)
            first = t.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if first.month == 12:
                last = first.replace(year=first.year+1, month=1) - timedelta(seconds=1)
            else:
                last = first.replace(month=first.month+1) - timedelta(seconds=1)
            rep = report_income_statement(session, first, last)
            monthly.append({
                "label": first.strftime("%b %Y"),
                "income": to_float(rep["income"]),
                "expense": to_float(rep["expense"]),
                "net": to_float(rep["net"]),
            })

        # Budget status
        bstat = budget_status(session)
        budget_items = []
        for item in bstat["items"]:
            budget_items.append({
                "category": item["category"],
                "emoji": item["emoji"],
                "target_pct": to_float(item["target_pct"]),
                "target_rp": to_float(item["target_rp"]),
                "realisasi_rp": to_float(item["realisasi_rp"]),
                "pct_realized": to_float(item["pct_realized"]),
                "status": item["status"],
            })

        # Top 5 transaksi terakhir
        txns = session.query(Transaction).order_by(Transaction.id.desc()).limit(5).all()
        recent = []
        for t in txns:
            total_d = sum((l.debit or 0) for l in t.lines)
            recent.append({
                "jv": t.jv_number,
                "date": t.txn_date.strftime("%d/%m/%Y"),
                "description": t.description[:50],
                "amount": to_float(total_d),
                "category": t.category or "",
            })

        return render_template("dashboard.html",
            kpi={
                "income": to_float(r["income"]),
                "expense": to_float(r["expense"]),
                "net": to_float(r["net"]),
                "kas": to_float(cf["saldo_akhir"]),
                "aset": to_float(bs["aset"]),
                "ekuitas": to_float(bs["total_ekuitas"]),
                "balance": bs["balance"],
                "margin": to_float(r["net"]/r["income"]) if r["income"] else 0,
            },
            monthly=monthly,
            categories=[{"name": k, "amount": to_float(v)} for k, v in cats.items() if v > 0],
            budget_items=budget_items,
            revenue=to_float(bstat["revenue"]),
            recent=recent,
            generated_at=datetime.utcnow().strftime("%d %b %Y %H:%M UTC"),
        )
    finally:
        session.close()


@app.route("/journal")
def journal():
    session = get_session()
    try:
        txns = session.query(Transaction).order_by(Transaction.id.desc()).limit(100).all()
        data = []
        for t in txns:
            total_d = sum((l.debit or 0) for l in t.lines)
            data.append({
                "id": t.id,
                "jv": t.jv_number,
                "date": t.txn_date.strftime("%Y-%m-%d"),
                "description": t.description,
                "category": t.category or "",
                "amount": to_float(total_d),
            })
        return render_template("journal.html", txns=data, count=len(data))
    finally:
        session.close()


@app.route("/ledger")
def ledger():
    session = get_session()
    try:
        rows = all_balances(session)
        data = []
        for acc, d, k, saldo in rows:
            data.append({
                "code": acc.code,
                "name": acc.name,
                "type": acc.type,
                "normal": acc.normal_side,
                "debit": to_float(d),
                "credit": to_float(k),
                "saldo": to_float(saldo),
            })
        return render_template("ledger.html", accounts=data)
    finally:
        session.close()


@app.route("/report")
def report():
    session = get_session()
    try:
        r = report_income_statement(session)
        return render_template("report.html",
            income_items=[(n, to_float(a)) for n, a in r["income_items"] if a != 0],
            expense_items=[(n, to_float(a)) for n, a in r["expense_items"] if a != 0],
            total_income=to_float(r["income"]),
            total_expense=to_float(r["expense"]),
            net=to_float(r["net"]),
            margin=to_float(r["net"]/r["income"]) if r["income"] else 0,
        )
    finally:
        session.close()


@app.route("/balance")
def balance():
    session = get_session()
    try:
        bs = report_balance_sheet(session)
        return render_template("balance.html",
            aset=to_float(bs["aset"]),
            liabilitas=to_float(bs["liabilitas"]),
            ekuitas=to_float(bs["ekuitas"]),
            laba=to_float(bs["laba"]),
            total_ekuitas=to_float(bs["total_ekuitas"]),
            balance=bs["balance"],
        )
    finally:
        session.close()


# ---- API endpoints untuk auto-refresh / chart JS ----
@app.route("/api/kpis")
def api_kpis():
    session = get_session()
    try:
        r = report_income_statement(session)
        bs = report_balance_sheet(session)
        cf = report_cash_flow(session)
        return jsonify({
            "income": to_float(r["income"]),
            "expense": to_float(r["expense"]),
            "net": to_float(r["net"]),
            "kas": to_float(cf["saldo_akhir"]),
            "aset": to_float(bs["aset"]),
            "ekuitas": to_float(bs["total_ekuitas"]),
            "balance_sheet_ok": bs["balance"],
            "updated_at": datetime.utcnow().isoformat(),
        })
    finally:
        session.close()


@app.route("/api/monthly")
def api_monthly():
    """Return 12 bulan terakhir income/expense."""
    session = get_session()
    try:
        result = []
        today = datetime.utcnow()
        for i in range(11, -1, -1):
            t = today - timedelta(days=30*i)
            first = t.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if first.month == 12:
                last = first.replace(year=first.year+1, month=1) - timedelta(seconds=1)
            else:
                last = first.replace(month=first.month+1) - timedelta(seconds=1)
            rep = report_income_statement(session, first, last)
            result.append({
                "label": first.strftime("%b %y"),
                "income": to_float(rep["income"]),
                "expense": to_float(rep["expense"]),
                "net": to_float(rep["net"]),
            })
        return jsonify(result)
    finally:
        session.close()


@app.route("/health")
def health():
    return jsonify({"status": "ok", "ts": datetime.utcnow().isoformat()})


if __name__ == "__main__":
    port = int(os.environ.get("WEB_PORT", 5000))
    debug = os.environ.get("WEB_DEBUG", "0") == "1"
    print(f"🌐 Dashboard running at http://localhost:{port}")
    print(f"   Database: {DB_PATH}")
    app.run(host="127.0.0.1", port=port, debug=debug)