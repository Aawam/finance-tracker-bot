# Default Chart of Accounts (sama dengan file Excel)

ACCOUNTS = [
    # (code, name, type, normal_balance)
    ("1000", "Kas & Bank",                  "Aset",       "Debit"),
    ("1100", "Piutang Usaha",               "Aset",       "Debit"),
    ("1200", "Persediaan",                  "Aset",       "Debit"),
    ("1500", "Peralatan",                   "Aset",       "Debit"),
    ("2000", "Utang Usaha",                 "Liabilitas", "Kredit"),
    ("2100", "Utang Gaji",                  "Liabilitas", "Kredit"),
    ("2200", "Utang Pajak",                 "Liabilitas", "Kredit"),
    ("3000", "Modal Pemilik",               "Ekuitas",    "Kredit"),
    ("3100", "Laba Ditahan",                "Ekuitas",    "Kredit"),
    ("4000", "Pendapatan Penjualan",        "Pendapatan", "Kredit"),
    ("4100", "Pendapatan Jasa",             "Pendapatan", "Kredit"),
    ("5000", "Beban Gaji",                  "Beban",      "Debit"),
    ("5100", "Beban Sewa",                  "Beban",      "Debit"),
    ("5200", "Beban Utilitas",              "Beban",      "Debit"),
    ("5300", "Beban Perlengkapan Kantor",   "Beban",      "Debit"),
    ("5400", "Beban Transportasi",          "Beban",      "Debit"),
    ("5500", "Beban Pemasaran",             "Beban",      "Debit"),
    ("5600", "Beban Penyusutan",            "Beban",      "Debit"),
    ("5700", "Beban Bunga",                 "Beban",      "Debit"),
    ("5800", "Beban Lain-lain",             "Beban",      "Debit"),
]

# Mapping kategori (untuk /expense) ke akun beban
EXPENSE_CATEGORIES = {
    "operasional":   ["5300", "5600", "5700", "5800"],
    "gaji":          ["5000"],
    "pemasaran":     ["5500"],
    "peralatan":     ["1500"],
    "utilitas":      ["5100", "5200"],
    "transport":     ["5400"],
}

CATEGORY_LIST = list(EXPENSE_CATEGORIES.keys())

INCOME_ACCOUNTS = ["4000", "4100"]
ASSET_ACCOUNTS  = ["1000", "1100", "1200", "1500"]
LIAB_ACCOUNTS   = ["2000", "2100", "2200"]
EQUITY_ACCOUNTS = ["3000", "3100"]
EXPENSE_ACCOUNTS= ["5000", "5100", "5200", "5300", "5400", "5500", "5600", "5700", "5800"]