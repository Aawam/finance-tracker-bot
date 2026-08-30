# -*- coding: utf-8 -*-
"""
Smart Categorization + Budget tracking.

Keyword engine: auto-detect kategori dari deskripsi transaksi.
Budget: target % alokasi per kategori vs realisasi bulan ini.
"""
import re
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from db import Keyword, Budget, Account, Transaction, JournalLine
from accounts_seed import EXPENSE_CATEGORIES, CATEGORY_LIST, INCOME_ACCOUNTS
from datetime import datetime

D = Decimal


# Default keywords per kategori (di-seed kalau table kosong)
DEFAULT_KEYWORDS = {
    "operasional": [
        "atk", "tinta", "kertas", "map", "ordner", "binder", "pulpen", "pensil",
        "stapler", "stempel", "amplop", "kalkulator", "memo", "sticker",
    ],
    "gaji": [
        "gaji", "thr", "bonus karyawan", "upah", "honor", "lembur", "tunjangan",
        "payroll", "salary",
    ],
    "pemasaran": [
        "iklan", "facebook ads", "instagram", "tiktok", "boost", "banner",
        "spanduk", "brosur", "promosi", "endorse", "kol", "marketplace",
        "google ads", "youtube",
    ],
    "peralatan": [
        "laptop", "komputer", "pc", "monitor", "printer", "hp ", "handphone",
        "keyboard", "mouse", "meja", "kursi", "rak", "lemari", "ac ", "kipas",
        "router", "modem",
    ],
    "utilitas": [
        "listrik", "pln", "token", "internet", "wifi", "pdam", "air", "telepon",
        "pulsa", "kuota", "sewa", "rent",
    ],
    "transport": [
        "bensin", "grab", "gojek", "ojol", "tol", "parkir", "taxi", "taksi",
        "kereta", "bus", "pesawat", "tiket", "hotel", "tiket pesawat",
        "bbm", "motor",
    ],
}

DEFAULT_BUDGETS = {
    # kategori -> target_pct (dari revenue)
    "operasional": D("0.08"),
    "gaji":        D("0.30"),
    "pemasaran":   D("0.10"),
    "peralatan":   D("0.05"),
    "utilitas":    D("0.08"),
    "transport":   D("0.05"),
}


# ============================================================
# KEYWORD ENGINE
# ============================================================

def seed_defaults(session):
    """Seed default keywords + budgets kalau table kosong."""
    # Keywords
    if session.query(Keyword).count() == 0:
        for cat, kws in DEFAULT_KEYWORDS.items():
            for kw in kws:
                session.add(Keyword(category=cat, keyword=kw.lower().strip()))
        session.commit()
    # Budgets
    if session.query(Budget).count() == 0:
        for cat, pct in DEFAULT_BUDGETS.items():
            session.add(Budget(category=cat, target_pct=pct))
        session.commit()


def detect_category(session, description: str) -> str | None:
    """
    Auto-detect kategori dari deskripsi.
    Return kategori name atau None kalau gak match.
    """
    desc_lower = description.lower()
    # Ambil semua keywords (di-cache sederhana)
    kws = session.query(Keyword).all()
    # Match per kategori, hitung score
    scores = {}
    for k in kws:
        if k.keyword in desc_lower:
            scores[k.category] = scores.get(k.category, 0) + 1
    if not scores:
        return None
    # Ambil kategori dengan score tertinggi
    return max(scores.items(), key=lambda x: x[1])[0]


def add_keyword(session, category: str, keyword: str) -> bool:
    """Tambah keyword baru. Return False kalau sudah ada."""
    keyword = keyword.lower().strip()
    existing = session.query(Keyword).filter_by(category=category, keyword=keyword).first()
    if existing:
        return False
    session.add(Keyword(category=category, keyword=keyword))
    session.commit()
    return True


def remove_keyword(session, category: str, keyword: str) -> bool:
    keyword = keyword.lower().strip()
    kw = session.query(Keyword).filter_by(category=category, keyword=keyword).first()
    if not kw:
        return False
    session.delete(kw)
    session.commit()
    return True


def list_keywords(session, category: str = None) -> list[tuple[str, list[str]]]:
    """Return dict kategori -> list keywords."""
    q = session.query(Keyword)
    if category:
        q = q.filter_by(category=category)
    result = {}
    for k in q.all():
        result.setdefault(k.category, []).append(k.keyword)
    return sorted(result.items())


# ============================================================
# BUDGET ENGINE
# ============================================================

def get_budget(session, category: str) -> Decimal:
    """Return target % untuk kategori (0 kalau gak ada)."""
    b = session.query(Budget).filter_by(category=category).first()
    if not b:
        return D(0)
    return Decimal(str(b.target_pct))


def set_budget(session, category: str, target_pct: Decimal) -> None:
    b = session.query(Budget).filter_by(category=category).first()
    if b:
        b.target_pct = target_pct
    else:
        session.add(Budget(category=category, target_pct=target_pct))
    session.commit()


def all_budgets(session) -> dict[str, Decimal]:
    return {b.category: Decimal(str(b.target_pct)) for b in session.query(Budget).all()}


def current_month_revenue(session) -> Decimal:
    """Hitung total pendapatan bulan ini."""
    today = datetime.utcnow()
    first = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q = session.query(JournalLine).join(Account).join(Transaction).filter(
        Account.type == "Pendapatan",
        Transaction.txn_date >= first,
    )
    total = D(0)
    for ln in q.all():
        total += (ln.credit or 0) - (ln.debit or 0)
    return total


def category_realisasi_bulan_ini(session, category: str) -> Decimal:
    """Total debit bulan ini untuk kategori (semua akun dalam kategori)."""
    today = datetime.utcnow()
    first = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    akun_list = EXPENSE_CATEGORIES.get(category, [])
    if not akun_list:
        return D(0)
    q = session.query(JournalLine).join(Transaction).filter(
        JournalLine.account_code.in_(akun_list),
        Transaction.txn_date >= first,
    )
    total = D(0)
    for ln in q.all():
        total += (ln.debit or 0) - (ln.credit or 0)
    return total


def budget_status(session) -> list[dict]:
    """
    Return list of dict per kategori:
    {category, target_pct, target_rp, realisasi_rp, pct_realized, status}
    status: 'under' | 'over' | 'on_track'
    """
    revenue = current_month_revenue(session)
    budgets = all_budgets(session)
    result = []
    for cat in CATEGORY_LIST:
        target_pct = budgets.get(cat, D(0))
        target_rp = target_pct * revenue
        realisasi = category_realisasi_bulan_ini(session, cat)
        pct_realized = (realisasi / target_rp) if target_rp > 0 else D(0)
        # Status
        if target_rp == 0:
            status = "no_target"
            emoji = "⚪"
        elif pct_realized < D("0.85"):
            status = "under"; emoji = "🟢"
        elif pct_realized <= D("1.0"):
            status = "on_track"; emoji = "🟡"
        else:
            status = "over"; emoji = "🔴"
        result.append({
            "category": cat,
            "target_pct": target_pct,
            "target_rp": target_rp,
            "realisasi_rp": realisasi,
            "pct_realized": pct_realized,
            "status": status,
            "emoji": emoji,
        })
    # Tambah total revenue
    return {"revenue": revenue, "items": result}


def progress_bar(pct: Decimal, width: int = 10) -> str:
    """ASCII progress bar. pct 0..2 (200% overbudget = full)."""
    p = float(pct)
    p = max(0, min(1.0, p))
    filled = int(p * width)
    return "▓" * filled + "░" * (width - filled)


def fmt_rp(n) -> str:
    """Format Rupiah (untuk dipakai di modul ini juga)."""
    if n is None: return "Rp 0"
    n = Decimal(str(n))
    if n < 0:
        return f"-Rp {abs(n):,.0f}".replace(",",".")
    return f"Rp {n:,.0f}".replace(",",".")