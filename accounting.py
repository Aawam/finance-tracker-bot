# -*- coding: utf-8 -*-
"""
Logika double-entry & laporan keuangan.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func
from db import Transaction, JournalLine, Account
from accounts_seed import EXPENSE_CATEGORIES

D = Decimal  # alias

# ---------- PARSER NOMINAL ----------

def parse_amount(text: str) -> Decimal:
    """Parse '8500000', '8.5jt', '8,500,000', '8.500.000' jadi Decimal."""
    t = text.strip().lower().replace(" ", "").replace(".", "").replace(",", "")
    mult = Decimal(1)
    if t.endswith("jt"):
        mult = Decimal(1000000); t = t[:-2]
    elif t.endswith("rb"):
        mult = Decimal(1000); t = t[:-2]
    elif t.endswith("k"):
        mult = Decimal(1000); t = t[:-1]
    elif t.endswith("m"):
        mult = Decimal(1000000); t = t[:-1]
    if not t:
        raise InvalidOperation("empty")
    return Decimal(t) * mult

# ---------- JURNAL ----------

def post_transaction(session, jv_number, description, lines, txn_date=None, category=None):
    """
    Post transaksi double-entry.
    lines: list of dict {account_code, debit, credit}
    Validasi: sum(debit) == sum(credit)
    Returns (Transaction, error_message).
    """
    total_d = sum((l.get("debit", 0) or 0) for l in lines)
    total_k = sum((l.get("credit", 0) or 0) for l in lines)
    if total_d != total_k:
        return None, f"Tidak seimbang! Debit={total_d:,} Kredit={total_k:,}"
    if total_d == 0:
        return None, "Nominal tidak boleh 0."

    txn = Transaction(
        jv_number = jv_number,
        description = description,
        txn_date = txn_date or datetime.utcnow(),
        category = category,
    )
    for l in lines:
        txn.lines.append(JournalLine(
            account_code = l["account_code"],
            debit = Decimal(str(l.get("debit", 0) or 0)),
            credit = Decimal(str(l.get("credit", 0) or 0)),
        ))
    session.add(txn)
    session.commit()
    return txn, None

def next_jv_number(session):
    last = session.query(Transaction).order_by(Transaction.id.desc()).first()
    if not last:
        return "JV-001"
    n = int(last.jv_number.split("-")[-1]) + 1
    return f"JV-{n:03d}"

def get_accounts(session):
    return {a.code: a for a in session.query(Account).all()}

# ---------- SALDO AKUN ----------

def account_balance(session, code):
    """Hitung saldo akun (normal side-aware). Returns Decimal."""
    acc = session.query(Account).filter_by(code=code).first()
    if not acc:
        return D(0)
    d = session.query(func.coalesce(func.sum(JournalLine.debit), 0)).filter_by(account_code=code).scalar() or 0
    k = session.query(func.coalesce(func.sum(JournalLine.credit), 0)).filter_by(account_code=code).scalar() or 0
    d, k = Decimal(str(d)), Decimal(str(k))
    if acc.normal_side == "Debit":
        return d - k
    else:
        return k - d

def all_balances(session):
    """Return list of (account, debit, credit, saldo)."""
    accounts = session.query(Account).order_by(Account.code).all()
    rows = []
    for acc in accounts:
        d = session.query(func.coalesce(func.sum(JournalLine.debit), 0)).filter_by(account_code=acc.code).scalar() or 0
        k = session.query(func.coalesce(func.sum(JournalLine.credit), 0)).filter_by(account_code=acc.code).scalar() or 0
        d, k = Decimal(str(d)), Decimal(str(k))
        saldo = (d - k) if acc.normal_side == "Debit" else (k - d)
        rows.append((acc, d, k, saldo))
    return rows

# ---------- LAPORAN ----------

def report_income_statement(session, period_start=None, period_end=None):
    """
    Laporan Laba Rugi untuk periode (default: semua waktu).
    Returns dict {income: Decimal, expense: Decimal, net: Decimal, items: [(name, amount)]}
    """
    from db import Transaction
    q = session.query(JournalLine).join(Account).join(Transaction)
    if period_start:
        q = q.filter(Transaction.txn_date >= period_start)
    if period_end:
        q = q.filter(Transaction.txn_date <= period_end)
    lines = q.all()

    income_items  = defaultdict(lambda: D(0))   # name -> total
    expense_items = defaultdict(lambda: D(0))

    for ln in lines:
        acc = ln.account
        if acc.type == "Pendapatan":
            # Normal Kredit, jadi credit-debit
            income_items[acc.name] += (ln.credit or 0) - (ln.debit or 0)
        elif acc.type == "Beban":
            expense_items[acc.name] += (ln.debit or 0) - (ln.credit or 0)

    total_income  = sum(income_items.values(),  D(0))
    total_expense = sum(expense_items.values(), D(0))
    net = total_income - total_expense
    return {
        "income":  total_income,
        "expense": total_expense,
        "net":     net,
        "income_items":  list(income_items.items()),
        "expense_items": list(expense_items.items()),
    }

def report_balance_sheet(session):
    """Return dict dengan total aset/liabilitas/ekuitas/laba."""
    rows = all_balances(session)
    aset = liab = ekuitas_pre = D(0)
    income = expense = D(0)
    for acc, d, k, saldo in rows:
        if acc.type == "Aset":
            aset += saldo
        elif acc.type == "Liabilitas":
            liab += saldo
        elif acc.type == "Ekuitas":
            ekuitas_pre += saldo
        elif acc.type == "Pendapatan":
            income += saldo
        elif acc.type == "Beban":
            expense += saldo
    net = income - expense
    return {
        "aset":        aset,
        "liabilitas":  liab,
        "ekuitas":     ekuitas_pre,
        "laba":        net,
        "total_ekuitas": ekuitas_pre + net,
        "balance":     (aset == liab + ekuitas_pre + net),
    }

def report_cash_flow(session):
    """Return kas masuk, keluar, neto."""
    acc_kas = session.query(Account).filter_by(code="1000").first()
    if not acc_kas:
        return {"in": D(0), "out": D(0), "net": D(0), "saldo_akhir": D(0)}
    d = session.query(func.coalesce(func.sum(JournalLine.debit), 0)).filter_by(account_code="1000").scalar() or 0
    k = session.query(func.coalesce(func.sum(JournalLine.credit), 0)).filter_by(account_code="1000").scalar() or 0
    kas_in  = Decimal(str(d))
    kas_out = Decimal(str(k))
    net = kas_in - kas_out
    return {"in": kas_in, "out": kas_out, "net": net, "saldo_akhir": net}

def report_by_category(session):
    """Return dict kategori -> total debit (pengeluaran)."""
    cat_totals = {cat: D(0) for cat in EXPENSE_CATEGORIES}
    for cat, akun_list in EXPENSE_CATEGORIES.items():
        for akun in akun_list:
            d = session.query(func.coalesce(func.sum(JournalLine.debit), 0)).filter_by(account_code=akun).scalar() or 0
            k = session.query(func.coalesce(func.sum(JournalLine.credit), 0)).filter_by(account_code=akun).scalar() or 0
            cat_totals[cat] += Decimal(str(d)) - Decimal(str(k))
    return cat_totals

def period_summary(session, days=30):
    """Ringkasan N hari ke belakang."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = session.query(Transaction).filter(Transaction.txn_date >= cutoff)
    txns = q.all()
    income = expense = D(0)
    for t in txns:
        for ln in t.lines:
            if ln.account.type == "Pendapatan":
                income += (ln.credit or 0) - (ln.debit or 0)
            elif ln.account.type == "Beban":
                expense += (ln.debit or 0) - (ln.credit or 0)
    return {"income": income, "expense": expense, "net": income - expense, "count": len(txns)}