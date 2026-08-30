# -*- coding: utf-8 -*-
"""
Database models & init (SQLite + SQLAlchemy).
Skema:
- Account: chart of accounts
- Transaction: header jurnal (1 transaksi = N baris debit/kredit)
- JournalLine: baris debit/kredit (FK ke Transaction)
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from pathlib import Path

Base = declarative_base()

class Account(Base):
    __tablename__ = "accounts"
    code        = Column(String(4), primary_key=True)
    name        = Column(String(80), nullable=False)
    type        = Column(String(20), nullable=False)  # Aset/Liabilitas/Ekuitas/Pendapatan/Beban
    normal_side = Column(String(10), nullable=False)  # Debit/Kredit

class Transaction(Base):
    __tablename__ = "transactions"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    jv_number   = Column(String(20), nullable=False, index=True)
    txn_date    = Column(DateTime, nullable=False, default=datetime.utcnow)
    description = Column(String(255), nullable=False)
    category    = Column(String(30), nullable=True)   # untuk /expense, opsional
    created_at  = Column(DateTime, default=datetime.utcnow)

    lines = relationship("JournalLine", back_populates="transaction", cascade="all, delete-orphan")

class JournalLine(Base):
    __tablename__ = "journal_lines"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    account_code = Column(String(4), ForeignKey("accounts.code"), nullable=False)
    debit      = Column(Numeric(15, 2), nullable=False, default=0)
    credit     = Column(Numeric(15, 2), nullable=False, default=0)

    transaction = relationship("Transaction", back_populates="lines")
    account     = relationship("Account")

class Budget(Base):
    __tablename__ = "budgets"
    category    = Column(String(30), primary_key=True)   # operasional/gaji/dll
    target_pct  = Column(Numeric(5, 4), nullable=False)  # 0.30 = 30%
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Keyword(Base):
    __tablename__ = "keywords"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    category    = Column(String(30), nullable=False, index=True)
    keyword     = Column(String(50), nullable=False)

# ----- Engine & session -----
def make_engine(db_path: str = None):
    if db_path is None:
        # Default: data/finance.db relative to script
        base = Path(__file__).parent
        data_dir = base / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(data_dir / "finance.db")
    else:
        # Pastikan parent dir exists kalau user specify custom path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
    Base.metadata.create_all(engine)
    return engine

def make_session(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()