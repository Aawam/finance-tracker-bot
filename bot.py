# -*- coding: utf-8 -*-
"""
Telegram Finance Tracker Bot — main entry.
Sistem Double-Entry Bookkeeping via Telegram.

Hybrid mode:
- /command untuk quick input
- Inline keyboard untuk step-by-step

Commands:
  /start, /help
  /income <nominal> <keterangan>   (catat pendapatan -> debit 1000, kredit 4000/4100)
  /expense <kategori> <nominal> <keterangan>
  /journal <DebitAcc> <KreditAcc> <nominal> <keterangan>   (transaksi manual)
  /balance                              (saldo semua akun)
  /cash                                  (kas masuk/keluar/saldo)
  /report                                (income statement bulan ini)
  /report monthly                        (income statement bulan lalu)
  /report neraca                         (balance sheet)
  /categories                            (daftar kategori)
  /list                                  (10 transaksi terakhir)
  /undo <jv_number>                      (hapus transaksi)
"""
import os
import logging
import re
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from functools import partial

# Load .env file (kalau ada) — utamakan env vars system
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv optional; kalau gak ada, pakai os.environ langsung

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    ReplyKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)

from db import make_engine, make_session, Account, Transaction, JournalLine
from accounts_seed import ACCOUNTS, EXPENSE_CATEGORIES, CATEGORY_LIST, INCOME_ACCOUNTS
from accounting import (
    post_transaction, next_jv_number, account_balance, all_balances,
    report_income_statement, report_balance_sheet, report_cash_flow,
    report_by_category, period_summary, parse_amount,
)
from budget import (
    seed_defaults as seed_budget_defaults,
    detect_category, add_keyword, remove_keyword, list_keywords,
    get_budget, set_budget, all_budgets, budget_status,
    progress_bar, fmt_rp as fmt_rp_budget,
)

# ============= CONFIG =============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "GANTI_DENGAN_TOKEN_KAMU")
DB_PATH = os.environ.get("DB_PATH")  # Render: /var/data/finance.db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bot")

# Conversation states (untuk input step-by-step)
(INPUT_INCOME_AMT, INPUT_INCOME_DESC, INPUT_INCOME_ACC,
 INPUT_EXP_CAT, INPUT_EXP_AMT, INPUT_EXP_DESC,
 INPUT_JOURNAL_D, INPUT_JOURNAL_K, INPUT_JOURNAL_AMT, INPUT_JOURNAL_DESC) = range(10)

# ============= INIT DB =============
engine = make_engine(DB_PATH)

def get_session():
    return make_session(engine)

def seed_accounts():
    """Isi chart of accounts kalau kosong."""
    session = get_session()
    if session.query(Account).count() == 0:
        for code, name, type_, normal in ACCOUNTS:
            session.add(Account(code=code, name=name, type=type_, normal_side=normal))
        session.commit()
        log.info("Chart of accounts seeded.")
    session.close()
    # Seed keywords + budgets
    session = get_session()
    seed_budget_defaults(session)
    session.close()
    log.info("Keywords & budgets seeded.")

# ============= FORMAT HELPERS =============
def fmt_rp(n) -> str:
    """Format Rupiah."""
    if n is None:
        return "Rp 0"
    n = Decimal(str(n))
    if n < 0:
        return f"-Rp {abs(n):,.0f}".replace(",", ".")
    return f"Rp {n:,.0f}".replace(",", ".")

def fmt_pct(n) -> str:
    return f"{float(n)*100:.1f}%"

# ============= KEYBOARDS =============
def main_menu_kb():
    """Reply keyboard (tombol di bawah chat)."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💰 + Pendapatan"), KeyboardButton("💸 - Pengeluaran")],
            [KeyboardButton("📝 Transaksi Manual"), KeyboardButton("📊 Saldo")],
            [KeyboardButton("💵 Kas"), KeyboardButton("📈 Laporan L/R")],
            [KeyboardButton("⚖️ Neraca"), KeyboardButton("📜 Riwayat")],
            [KeyboardButton("❓ Bantuan")],
        ],
        resize_keyboard=True,
    )

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Batal", callback_data="cancel")]])

def income_account_kb():
    """Pilih akun pendapatan: 4000 Penjualan atau 4100 Jasa."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Penjualan (4000)", callback_data="inc_acc_4000")],
        [InlineKeyboardButton("💼 Jasa (4100)", callback_data="inc_acc_4100")],
        [InlineKeyboardButton("❌ Batal", callback_data="cancel")],
    ])

def category_kb():
    rows = []
    cat_emoji = {"operasional":"📋","gaji":"👥","pemasaran":"📢","peralatan":"💻","utilitas":"💡","transport":"🚗"}
    for cat in CATEGORY_LIST:
        e = cat_emoji.get(cat, "•")
        rows.append([InlineKeyboardButton(f"{e} {cat.title()}", callback_data=f"cat_{cat}")])
    rows.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)

# ============= COMMAND HANDLERS =============
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Halo! Saya Finance Tracker Bot*\n\n"
        "Saya bisa bantu catat transaksi keuangan dengan sistem *Double-Entry* "
        "(Debit-Kredit otomatis seimbang).\n\n"
        "📌 *Cara cepat pakai command:*\n"
        "• `/income 8500000 Penjualan PT Maju` — catat pendapatan\n"
        "• `/expense operasional 750000 Beli ATK` — catat pengeluaran\n"
        "• `/balance` — lihat saldo semua akun\n"
        "• `/report` — laporan laba rugi\n\n"
        "📱 *Atau pakai tombol di bawah* untuk input step-by-step.\n\n"
        "Ketik /help untuk panduan lengkap.",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Panduan Lengkap*\n\n"
        "*QUICK COMMANDS:*\n"
        "• `/income <nominal> <keterangan>`\n"
        "  Contoh: `/income 8500000 Penjualan ke PT Maju`\n"
        "• `/expense <kategori> <nominal> <keterangan>`\n"
        "  Contoh: `/expense gaji 18000000 Bayar gaji Agustus`\n"
        "  Kategori: operasional, gaji, pemasaran, peralatan, utilitas, transport\n"
        "• `/journal <debit_acc> <kredit_acc> <nominal> <keterangan>`\n"
        "  Contoh: `/journal 1100 1000 6250000 Terima piutang`\n\n"
        "*LAPORAN:*\n"
        "• `/balance` — saldo semua akun\n"
        "• `/cash` — arus kas\n"
        "• `/report` — laba rugi bulan ini\n"
        "• `/report monthly` — laba rugi bulan lalu\n"
        "• `/report neraca` — neraca (balance sheet)\n\n"
        "*LAINNYA:*\n"
        "• `/list` — 10 transaksi terakhir\n"
        "• `/undo <jv_number>` — hapus transaksi\n"
        "• `/categories` — daftar kategori\n\n"
        "💡 *Tips nominal:* Bisa tulis `8.5jt`, `8500000`, atau `8,500,000`",
        parse_mode="Markdown",
    )

async def cmd_income(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick command: /income 8500000 keterangan"""
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "⚠️ Format: `/income <nominal> <keterangan>`\n"
            "Contoh: `/income 8500000 Penjualan PT Maju`",
            parse_mode="Markdown",
        )
        return
    try:
        amount = parse_amount(ctx.args[0])
    except (InvalidOperation, ValueError):
        await update.message.reply_text(f"⚠️ Nominal tidak valid: `{ctx.args[0]}`", parse_mode="Markdown")
        return
    description = " ".join(ctx.args[1:])

    session = get_session()
    try:
        jv = next_jv_number(session)
        # Default income ke 4000 (Penjualan). User bisa ganti pakai /journal manual.
        err = post_transaction(session, jv, description, [
            {"account_code": "1000", "debit": amount, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": amount},
        ], category="income")
        if err[1]:
            await update.message.reply_text(f"❌ {err[1]}")
            return
        await update.message.reply_text(
            f"✅ *Pendapatan dicatat!*\n"
            f"📌 `{jv}` — {description}\n"
            f"💰 {fmt_rp(amount)} → Kas & Bank (D)\n"
            f"💼 {fmt_rp(amount)} → Pendapatan Penjualan (K)\n\n"
            f"Debit = Kredit ✓\n"
            f"Saldo Kas sekarang: {fmt_rp(account_balance(session, '1000'))}",
            parse_mode="Markdown",
        )
    finally:
        session.close()

async def cmd_expense(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick command: /expense <kategori> <nominal> <keterangan>
    Atau /expense <nominal> <keterangan> — auto-detect kategori."""
    session = get_session()
    try:
        if not ctx.args or len(ctx.args) < 2:
            await update.message.reply_text(
                "⚠️ Format:\n"
                "`/expense <kategori> <nominal> <keterangan>`\n"
                "`/expense <nominal> <keterangan>` (auto-detect)\n\n"
                "Kategori: " + ", ".join(CATEGORY_LIST),
                parse_mode="Markdown",
            )
            return

        # Deteksi: kalau arg[0] adalah kategori valid -> explicit
        if ctx.args[0].lower() in EXPENSE_CATEGORIES and len(ctx.args) >= 3:
            cat = ctx.args[0].lower()
            try:
                amount = parse_amount(ctx.args[1])
            except (InvalidOperation, ValueError):
                await update.message.reply_text(f"⚠️ Nominal tidak valid: `{ctx.args[1]}`", parse_mode="Markdown")
                return
            description = " ".join(ctx.args[2:])
        else:
            # Auto-detect mode: /expense <nominal> <keterangan>
            try:
                amount = parse_amount(ctx.args[0])
            except (InvalidOperation, ValueError):
                await update.message.reply_text(f"⚠️ Nominal tidak valid: `{ctx.args[0]}`", parse_mode="Markdown")
                return
            description = " ".join(ctx.args[1:])
            cat = detect_category(session, description)
            if not cat:
                cat = "operasional"  # fallback
        akun_list = EXPENSE_CATEGORIES[cat]
        acc = akun_list[0]

        jv = next_jv_number(session)
        _, err = post_transaction(session, jv, description, [
            {"account_code": acc, "debit": amount, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": amount},
        ], category=cat)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return
        await update.message.reply_text(
            f"✅ *Pengeluaran dicatat!*\n"
            f"📌 `{jv}` — {description}\n"
            f"📂 Kategori: {cat.title()}\n"
            f"💸 {fmt_rp(amount)} → Beban (D)\n"
            f"💰 {fmt_rp(amount)} → Kas & Bank (K)\n\n"
            f"Saldo Kas sekarang: {fmt_rp(account_balance(session, '1000'))}",
            parse_mode="Markdown",
        )
    finally:
        session.close()

async def cmd_journal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Manual: /journal <debit_acc> <kredit_acc> <nominal> <keterangan>"""
    if not ctx.args or len(ctx.args) < 4:
        await update.message.reply_text(
            "⚠️ Format: `/journal <akun_debit> <akun_kredit> <nominal> <keterangan>`\n"
            "Contoh: `/journal 1100 1000 6250000 Terima piutang`\n\n"
            "Kode akun: 1000 Kas, 1100 Piutang, 1500 Peralatan, "
            "3000 Modal, 4000 Penjualan, 4100 Jasa, "
            "5000-5800 Beban-beban, 2000-2200 Utang",
            parse_mode="Markdown",
        )
        return
    d_acc = ctx.args[0]
    k_acc = ctx.args[1]
    try:
        amount = parse_amount(ctx.args[2])
    except (InvalidOperation, ValueError):
        await update.message.reply_text(f"⚠️ Nominal tidak valid: `{ctx.args[2]}`", parse_mode="Markdown")
        return
    description = " ".join(ctx.args[3:])

    session = get_session()
    try:
        # Validasi akun exists
        for code in (d_acc, k_acc):
            if not session.query(Account).filter_by(code=code).first():
                await update.message.reply_text(f"❌ Akun `{code}` tidak ditemukan di chart of accounts.")
                return
        jv = next_jv_number(session)
        _, err = post_transaction(session, jv, description, [
            {"account_code": d_acc, "debit": amount, "credit": 0},
            {"account_code": k_acc, "debit": 0, "credit": amount},
        ])
        if err:
            await update.message.reply_text(f"❌ {err}")
            return
        d_name = session.query(Account).filter_by(code=d_acc).first().name
        k_name = session.query(Account).filter_by(code=k_acc).first().name
        await update.message.reply_text(
            f"✅ *Transaksi manual dicatat!*\n"
            f"📌 `{jv}` — {description}\n"
            f"📒 Debit  {d_acc} {d_name}: {fmt_rp(amount)}\n"
            f"📕 Kredit {k_acc} {k_name}: {fmt_rp(amount)}",
            parse_mode="Markdown",
        )
    finally:
        session.close()

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tampilkan saldo semua akun."""
    session = get_session()
    try:
        rows = all_balances(session)
        if not rows:
            await update.message.reply_text("Belum ada akun. Coba /help")
            return
        lines = ["⚖️ *Saldo Semua Akun*\n"]
        total_d = total_k = Decimal(0)
        for acc, d, k, saldo in rows:
            if d == 0 and k == 0 and saldo == 0:
                continue
            total_d += d
            total_k += k
            sign = "🟢" if saldo > 0 else ("🔴" if saldo < 0 else "⚪")
            lines.append(
                f"`{acc.code}` {acc.name[:24]:<24} {sign} {fmt_rp(saldo):>14}"
            )
        lines.append("")
        lines.append(f"📊 Total Debit : {fmt_rp(total_d)}")
        lines.append(f"📊 Total Kredit: {fmt_rp(total_k)}")
        lines.append(f"{'✓ Balanced' if total_d == total_k else '⚠ TIDAK balanced!'}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    finally:
        session.close()

async def cmd_cash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Arus kas."""
    session = get_session()
    try:
        cf = report_cash_flow(session)
        text = (
            "💵 *Arus Kas*\n\n"
            f"⬇️ Kas Masuk   : {fmt_rp(cf['in'])}\n"
            f"⬆️ Kas Keluar  : {fmt_rp(cf['out'])}\n"
            f"📊 Net Cash    : {fmt_rp(cf['net'])}\n"
            f"💰 Saldo Akhir : {fmt_rp(cf['saldo_akhir'])}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Laporan L/R atau neraca."""
    arg = (ctx.args[0].lower() if ctx.args else "")

    session = get_session()
    try:
        if arg == "neraca":
            bs = report_balance_sheet(session)
            text = (
                "⚖️ *NERACA (Balance Sheet)*\n\n"
                f"💰 Total Aset       : {fmt_rp(bs['aset'])}\n"
                f"📌 Total Liabilitas : {fmt_rp(bs['liabilitas'])}\n"
                f"📈 Ekuitas (pre-LR) : {fmt_rp(bs['ekuitas'])}\n"
                f"📊 Laba Tahun Ini   : {fmt_rp(bs['laba'])}\n"
                f"💎 Total Ekuitas    : {fmt_rp(bs['total_ekuitas'])}\n"
                f"📋 Total Liab+Ek    : {fmt_rp(bs['liabilitas'] + bs['total_ekuitas'])}\n\n"
                f"{'✓ BALANCE SHEET SEIMBANG' if bs['balance'] else '⚠ TIDAK SEIMBANG'}"
            )
        elif arg == "monthly":
            # Bulan lalu
            today = datetime.utcnow()
            first_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_prev = first_this_month - timedelta(seconds=1)
            first_prev = last_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            r = report_income_statement(session, first_prev, last_prev)
            text = _format_income_statement(r, f"{first_prev:%B %Y}")
        elif arg == "30":
            r = report_income_statement(session, datetime.utcnow() - timedelta(days=30))
            text = _format_income_statement(r, "30 hari terakhir")
        else:
            # Default: bulan ini
            today = datetime.utcnow()
            first = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            r = report_income_statement(session, first)
            text = _format_income_statement(r, f"{today:%B %Y}")
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()

def _format_income_statement(r, period_label):
    lines = [f"📈 *LAPORAN LABA RUGI*\n📅 Periode: {period_label}\n"]
    lines.append("*PENDAPATAN:*")
    for name, amt in r["income_items"]:
        if amt != 0:
            lines.append(f"  • {name[:30]:<30} {fmt_rp(amt):>14}")
    lines.append(f"  *Total Pendapatan*: {fmt_rp(r['income'])}\n")

    lines.append("*BEBAN:*")
    for name, amt in r["expense_items"]:
        if amt != 0:
            lines.append(f"  • {name[:30]:<30} {fmt_rp(amt):>14}")
    lines.append(f"  *Total Beban*: {fmt_rp(r['expense'])}\n")

    net = r["net"]
    sign = "📊 LABA BERSIH" if net >= 0 else "📊 RUGI BERSIH"
    lines.append(f"*{sign}*: {fmt_rp(net)}")
    if r["income"] > 0:
        margin = float(net / r["income"]) * 100
        lines.append(f"📈 Margin: {margin:.1f}%")
    return "\n".join(lines)

async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """10 transaksi terakhir."""
    session = get_session()
    try:
        txns = session.query(Transaction).order_by(Transaction.id.desc()).limit(10).all()
        if not txns:
            await update.message.reply_text("Belum ada transaksi.")
            return
        lines = ["📜 *10 Transaksi Terakhir*\n"]
        for t in txns:
            total_d = sum((l.debit or 0) for l in t.lines)
            lines.append(
                f"`{t.jv_number}` ({t.txn_date.strftime('%d/%m')}) — {t.description[:30]}\n"
                f"   {fmt_rp(total_d)} {(' ['+t.category+']') if t.category else ''}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    finally:
        session.close()

async def cmd_undo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Hapus transaksi."""
    if not ctx.args:
        await update.message.reply_text("⚠️ Format: `/undo <jv_number>`\nContoh: `/undo JV-005`", parse_mode="Markdown")
        return
    jv = ctx.args[0].upper()
    session = get_session()
    try:
        txn = session.query(Transaction).filter_by(jv_number=jv).first()
        if not txn:
            await update.message.reply_text(f"❌ `{jv}` tidak ditemukan.")
            return
        desc = txn.description
        session.delete(txn)
        session.commit()
        await update.message.reply_text(f"🗑️ *{jv}* ({desc}) telah dihapus.", parse_mode="Markdown")
    finally:
        session.close()

async def cmd_categories(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Daftar kategori + target alokasi."""
    session = get_session()
    try:
        cat_totals = report_by_category(session)
        income = sum(cat_totals.values(), Decimal(0))  # bukan income sih, total expense
        text = "📂 *Kategori & Realisasi*\n\n"
        cat_label = {
            "operasional": "Operasional",
            "gaji": "Gaji & Tunjangan",
            "pemasaran": "Pemasaran & Iklan",
            "peralatan": "Peralatan & Aset",
            "utilitas": "Utilitas & Sewa",
            "transport": "Transportasi",
        }
        for cat in CATEGORY_LIST:
            text += f"• *{cat_label.get(cat, cat)}*: {fmt_rp(cat_totals[cat])}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()

# ===== SMART CATEGORIZATION + BUDGET COMMANDS =====

async def cmd_keyword(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /keyword                                → list semua keywords
    /keyword add <kategori> <kata>          → tambah keyword
    /keyword remove <kategori> <kata>       → hapus keyword
    /keyword test <deskripsi>               → test deteksi
    """
    args = ctx.args
    session = get_session()
    try:
        if not args:
            # List semua
            kws = list_keywords(session)
            if not kws:
                await update.message.reply_text("Belum ada keyword.")
                return
            lines = ["🔑 *DAFTAR KEYWORD AUTO-CATEGORIZE*\n"]
            for cat, kw_list in kws:
                lines.append(f"*{cat}*: {', '.join(kw_list)}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            return

        if args[0] == "add" and len(args) >= 3:
            cat = args[1].lower()
            if cat not in CATEGORY_LIST:
                await update.message.reply_text(f"❌ Kategori `{cat}` tidak dikenal.")
                return
            kw = " ".join(args[2:])
            ok = add_keyword(session, cat, kw)
            if ok:
                await update.message.reply_text(f"✅ Keyword `{kw}` ditambah ke kategori `{cat}`.")
            else:
                await update.message.reply_text(f"⚠️ Keyword `{kw}` sudah ada di kategori `{cat}`.")
            return

        if args[0] == "remove" and len(args) >= 3:
            cat = args[1].lower()
            kw = " ".join(args[2:])
            ok = remove_keyword(session, cat, kw)
            if ok:
                await update.message.reply_text(f"✅ Keyword `{kw}` dihapus dari `{cat}`.")
            else:
                await update.message.reply_text(f"⚠️ Keyword `{kw}` tidak ditemukan di `{cat}`.")
            return

        if args[0] == "test" and len(args) >= 2:
            desc = " ".join(args[1:])
            cat = detect_category(session, desc)
            if cat:
                await update.message.reply_text(f"🧪 `{desc}`\n→ terdeteksi: *{cat}*", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"🧪 `{desc}`\n→ tidak ada kategori yang match.")
            return

        await update.message.reply_text(
            "⚠️ Format salah.\n"
            "`/keyword` — list\n"
            "`/keyword add <kategori> <kata>`\n"
            "`/keyword remove <kategori> <kata>`\n"
            "`/keyword test <deskripsi>`",
            parse_mode="Markdown",
        )
    finally:
        session.close()


async def cmd_budget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /budget               → tampilkan status budget vs aktual
    /budget set <kat> <pct>   → set target % (mis. 0.30 = 30%)
    """
    args = ctx.args
    session = get_session()
    try:
        if not args:
            # Tampilkan status
            status = budget_status(session)
            rev = status["revenue"]
            lines = [
                f"🎯 *BUDGET vs AKTUAL — {datetime.utcnow():%B %Y}*\n",
                f"💰 Revenue bulan ini: {fmt_rp(rev)}\n",
            ]
            cat_label = {
                "operasional":"📋 Operasional","gaji":"👥 Gaji","pemasaran":"📢 Pemasaran",
                "peralatan":"💻 Peralatan","utilitas":"💡 Utilitas","transport":"🚗 Transport",
            }
            for item in status["items"]:
                cat = item["category"]
                pct = item["target_pct"] * 100
                tg = item["target_rp"]
                real = item["realisasi_rp"]
                p_used = item["pct_realized"]
                bar = progress_bar(p_used)
                lines.append(
                    f"{cat_label.get(cat, cat)}\n"
                    f" {item['emoji']} `{bar}` {float(p_used)*100:.0f}% terpakai\n"
                    f" Realisasi: {fmt_rp(real)} / Target: {fmt_rp(tg)} ({float(pct):.0f}%)\n"
                )
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            return

        if args[0] == "set" and len(args) >= 3:
            cat = args[1].lower()
            if cat not in CATEGORY_LIST:
                await update.message.reply_text(f"❌ Kategori `{cat}` tidak dikenal.")
                return
            try:
                pct = Decimal(args[2])
                if pct < 0 or pct > 5:  # max 500%
                    raise ValueError
            except (InvalidOperation, ValueError):
                await update.message.reply_text("⚠️ Persentase tidak valid. Contoh: `0.30` = 30%")
                return
            set_budget(session, cat, pct)
            await update.message.reply_text(
                f"✅ Target `{cat}` diset ke *{float(pct)*100:.0f}%* dari revenue.",
                parse_mode="Markdown",
            )
            return

        await update.message.reply_text(
            "⚠️ Format: `/budget` atau `/budget set <kategori> <persen>`\n"
            "Contoh: `/budget set operasional 0.10` (10%)",
            parse_mode="Markdown",
        )
    finally:
        session.close()


async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Generate & kirim Excel report via Telegram."""
    msg = await update.message.reply_text("⏳ Generating Excel report...")
    session = get_session()
    try:
        from excel_export import export_to_excel
        path = export_to_excel(session)
        size_kb = os.path.getsize(path) / 1024
        # Kirim file
        with open(path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(path),
                caption=f"📊 *Finance Report*\n\n"
                        f"📅 {datetime.utcnow():%d %B %Y %H:%M} UTC\n"
                        f"💾 {size_kb:.1f} KB\n"
                        f"📑 6 sheet: Dashboard, Jurnal, Buku Besar, L/R, Neraca, Kategori",
                parse_mode="Markdown",
            )
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Gagal export: {e}")
    finally:
        session.close()

# ============= INLINE KEYBOARD HANDLERS =============

async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("❌ Dibatalkan.")
    return ConversationHandler.END

# ---- Income flow ----
async def inc_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 *Pendapatan Baru*\nMasukkan nominal (contoh: 8500000 atau 8.5jt):",
        parse_mode="Markdown",
        reply_markup=cancel_kb(),
    )
    return INPUT_INCOME_AMT

async def inc_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
    except (InvalidOperation, ValueError):
        await update.message.reply_text("⚠️ Nominal tidak valid. Coba lagi:")
        return INPUT_INCOME_AMT
    ctx.user_data["inc_amount"] = amount
    await update.message.reply_text(
        f"💰 Nominal: {fmt_rp(amount)}\n\nKeterangan / deskripsi:",
        parse_mode="Markdown",
    )
    return INPUT_INCOME_DESC

async def inc_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["inc_desc"] = update.message.text
    await update.message.reply_text(
        "Pilih akun pendapatan:",
        reply_markup=income_account_kb(),
    )
    return INPUT_INCOME_ACC

async def inc_acc_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    acc_code = update.callback_query.data.split("_")[-1]
    acc_name = "Penjualan" if acc_code == "4000" else "Jasa"
    amount = ctx.user_data["inc_amount"]
    desc   = ctx.user_data["inc_desc"]

    session = get_session()
    try:
        jv = next_jv_number(session)
        _, err = post_transaction(session, jv, desc, [
            {"account_code": "1000", "debit": amount, "credit": 0},
            {"account_code": acc_code, "debit": 0, "credit": amount},
        ], category="income")
        if err:
            await update.callback_query.edit_message_text(f"❌ {err}")
            return ConversationHandler.END
        saldo = account_balance(session, "1000")
        await update.callback_query.edit_message_text(
            f"✅ *Pendapatan dicatat!*\n\n"
            f"📌 `{jv}` — {desc}\n"
            f"💰 Kas (D): {fmt_rp(amount)}\n"
            f"💼 {acc_name} (K): {fmt_rp(amount)}\n\n"
            f"💵 Saldo Kas: {fmt_rp(saldo)}",
            parse_mode="Markdown",
        )
    finally:
        session.close()
    return ConversationHandler.END

# ---- Expense flow ----
async def exp_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💸 *Pengeluaran Baru*\nPilih kategori:",
        parse_mode="Markdown",
        reply_markup=category_kb(),
    )
    return INPUT_EXP_CAT

async def exp_cat_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    cat = update.callback_query.data.split("_", 1)[1]
    ctx.user_data["exp_cat"] = cat
    await update.callback_query.edit_message_text(
        f"Kategori: *{cat.title()}*\n\nMasukkan nominal (contoh: 750000 atau 750rb):",
        parse_mode="Markdown",
    )
    return INPUT_EXP_AMT

async def exp_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
    except (InvalidOperation, ValueError):
        await update.message.reply_text("⚠️ Nominal tidak valid. Coba lagi:")
        return INPUT_EXP_AMT
    ctx.user_data["exp_amount"] = amount
    await update.message.reply_text(
        f"💸 Nominal: {fmt_rp(amount)}\n\nKeterangan / deskripsi:",
        parse_mode="Markdown",
    )
    return INPUT_EXP_DESC

async def exp_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cat = ctx.user_data["exp_cat"]
    amount = ctx.user_data["exp_amount"]
    desc = update.message.text
    akun_list = EXPENSE_CATEGORIES[cat]
    acc = akun_list[0]

    session = get_session()
    try:
        jv = next_jv_number(session)
        _, err = post_transaction(session, jv, desc, [
            {"account_code": acc, "debit": amount, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": amount},
        ], category=cat)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return ConversationHandler.END
        saldo = account_balance(session, "1000")
        await update.message.reply_text(
            f"✅ *Pengeluaran dicatat!*\n\n"
            f"📌 `{jv}` — {desc}\n"
            f"📂 Kategori: {cat.title()}\n"
            f"💸 Beban (D): {fmt_rp(amount)}\n"
            f"💰 Kas (K): {fmt_rp(amount)}\n\n"
            f"💵 Saldo Kas: {fmt_rp(saldo)}",
            parse_mode="Markdown",
        )
    finally:
        session.close()
    return ConversationHandler.END

# ---- Manual journal flow ----
async def jrn_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 *Transaksi Manual (Double-Entry)*\n\n"
        "Masukkan *kode akun Debit* (4 digit):\n"
        "Contoh: `1100` (Piutang), `1500` (Peralatan), `5000` (Beban Gaji)\n\n"
        "Lihat semua kode: `/help` atau ketik 'list'",
        parse_mode="Markdown",
        reply_markup=cancel_kb(),
    )
    return INPUT_JOURNAL_D

async def jrn_d(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    session = get_session()
    try:
        acc = session.query(Account).filter_by(code=code).first()
        if not acc:
            await update.message.reply_text(f"❌ Akun `{code}` tidak ada. Coba lagi:")
            return INPUT_JOURNAL_D
    finally:
        session.close()
    ctx.user_data["jrn_d"] = code
    await update.message.reply_text(
        f"Debit: `{code}` — {acc.name}\n\nSekarang *kode akun Kredit*:",
        parse_mode="Markdown",
    )
    return INPUT_JOURNAL_K

async def jrn_k(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    d_code = ctx.user_data["jrn_d"]
    if code == d_code:
        await update.message.reply_text("⚠️ Debit dan Kredit tidak boleh akun sama. Coba lagi:")
        return INPUT_JOURNAL_K
    session = get_session()
    try:
        acc = session.query(Account).filter_by(code=code).first()
        if not acc:
            await update.message.reply_text(f"❌ Akun `{code}` tidak ada. Coba lagi:")
            return INPUT_JOURNAL_K
    finally:
        session.close()
    ctx.user_data["jrn_k"] = code
    await update.message.reply_text(
        f"Kredit: `{code}` — {acc.name}\n\nMasukkan *nominal*:",
        parse_mode="Markdown",
    )
    return INPUT_JOURNAL_AMT

async def jrn_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
    except (InvalidOperation, ValueError):
        await update.message.reply_text("⚠️ Nominal tidak valid. Coba lagi:")
        return INPUT_JOURNAL_AMT
    ctx.user_data["jrn_amount"] = amount
    await update.message.reply_text(
        f"Nominal: {fmt_rp(amount)}\n\nKeterangan:",
        parse_mode="Markdown",
    )
    return INPUT_JOURNAL_DESC

async def jrn_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d_code = ctx.user_data["jrn_d"]
    k_code = ctx.user_data["jrn_k"]
    amount = ctx.user_data["jrn_amount"]
    desc = update.message.text
    session = get_session()
    try:
        jv = next_jv_number(session)
        _, err = post_transaction(session, jv, desc, [
            {"account_code": d_code, "debit": amount, "credit": 0},
            {"account_code": k_code, "debit": 0, "credit": amount},
        ])
        if err:
            await update.message.reply_text(f"❌ {err}")
            return ConversationHandler.END
        d_name = session.query(Account).filter_by(code=d_code).first().name
        k_name = session.query(Account).filter_by(code=k_code).first().name
        await update.message.reply_text(
            f"✅ *Transaksi manual dicatat!*\n\n"
            f"📌 `{jv}` — {desc}\n"
            f"📒 Debit  {d_code} {d_name}: {fmt_rp(amount)}\n"
            f"📕 Kredit {k_code} {k_name}: {fmt_rp(amount)}",
            parse_mode="Markdown",
        )
    finally:
        session.close()
    return ConversationHandler.END

# ============= MAIN KEYBOARD MAPPING =============
async def on_text_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if "Pendapatan" in t:
        return await inc_start(update, ctx)
    elif "Pengeluaran" in t:
        return await exp_start(update, ctx)
    elif "Transaksi Manual" in t:
        return await jrn_start(update, ctx)
    elif "Saldo" in t:
        return await cmd_balance(update, ctx)
    elif "Kas" in t:
        return await cmd_cash(update, ctx)
    elif "Laporan L/R" in t:
        return await cmd_report(update, ctx)
    elif "Neraca" in t:
        ctx.args = ["neraca"]
        return await cmd_report(update, ctx)
    elif "Riwayat" in t:
        return await cmd_list(update, ctx)
    elif "Bantuan" in t:
        return await cmd_help(update, ctx)
    # Default: anggap user ketik nominal tanpa command
    await update.message.reply_text(
        "💡 Gunakan menu atau command:\n"
        "/income, /expense, /balance, /report, /help",
    )

# ============= ERROR HANDLER =============
async def on_error(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.exception("Update %s caused error", update)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Maaf, ada error. Coba lagi atau /help."
            )
        except Exception:
            pass

# ============= BOOTSTRAP =============
async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Mulai"),
        BotCommand("help", "Panduan lengkap"),
        BotCommand("income", "Catat pendapatan (quick)"),
        BotCommand("expense", "Catat pengeluaran (auto-kategori)"),
        BotCommand("journal", "Transaksi manual (debit/kredit)"),
        BotCommand("balance", "Saldo semua akun"),
        BotCommand("cash", "Arus kas"),
        BotCommand("report", "Laporan L/R"),
        BotCommand("list", "10 transaksi terakhir"),
        BotCommand("undo", "Hapus transaksi (JV-XXX)"),
        BotCommand("budget", "Budget vs aktual"),
        BotCommand("keyword", "Kelola keyword auto-kategori"),
        BotCommand("export", "Export laporan ke Excel"),
    ])

def main():
    if BOT_TOKEN == "GANTI_DENGAN_TOKEN_KAMU":
        print("=" * 60)
        print("ERROR: BOT_TOKEN belum di-set!")
        print("Set environment variable BOT_TOKEN, atau edit file bot.py")
        print("=" * 60)
        return

    seed_accounts()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Conversation handler untuk income
    inc_handler = ConversationHandler(
        entry_points=[CommandHandler("income_btn", inc_start)],
        states={
            INPUT_INCOME_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, inc_amt)],
            INPUT_INCOME_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, inc_desc)],
            INPUT_INCOME_ACC: [CallbackQueryHandler(inc_acc_cb, pattern=r"^inc_acc_")],
        },
        fallbacks=[CallbackQueryHandler(cb_cancel, pattern=r"^cancel$")],
    )

    # Conversation handler untuk expense
    exp_handler = ConversationHandler(
        entry_points=[CommandHandler("expense_btn", exp_start)],
        states={
            INPUT_EXP_CAT: [CallbackQueryHandler(exp_cat_cb, pattern=r"^cat_")],
            INPUT_EXP_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_amt)],
            INPUT_EXP_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_desc)],
        },
        fallbacks=[CallbackQueryHandler(cb_cancel, pattern=r"^cancel$")],
    )

    # Conversation handler untuk journal manual
    jrn_handler = ConversationHandler(
        entry_points=[CommandHandler("journal_btn", jrn_start)],
        states={
            INPUT_JOURNAL_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, jrn_d)],
            INPUT_JOURNAL_K: [MessageHandler(filters.TEXT & ~filters.COMMAND, jrn_k)],
            INPUT_JOURNAL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, jrn_amt)],
            INPUT_JOURNAL_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, jrn_desc)],
        },
        fallbacks=[CallbackQueryHandler(cb_cancel, pattern=r"^cancel$")],
    )

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("income", cmd_income))
    app.add_handler(CommandHandler("expense", cmd_expense))
    app.add_handler(CommandHandler("journal", cmd_journal))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("cash", cmd_cash))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("categories", cmd_categories))
    app.add_handler(CommandHandler("keyword", cmd_keyword))
    app.add_handler(CommandHandler("budget", cmd_budget))
    app.add_handler(CommandHandler("export", cmd_export))

    # Conversation handlers
    app.add_handler(inc_handler)
    app.add_handler(exp_handler)
    app.add_handler(jrn_handler)

    # Fallback untuk tombol menu di keyboard
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_button))

    # Cancel button (top-level)
    app.add_handler(CallbackQueryHandler(cb_cancel, pattern=r"^cancel$"))

    # Error
    app.add_error_handler(on_error)

    log.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()