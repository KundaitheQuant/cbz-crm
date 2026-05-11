"""
CBZ Corporate Banking CRM
Phase 1 - Database Setup & Seed Data
Run: python setup_database.py
Creates: cbz_crm.db in the same folder
"""

import sqlite3
import os
from datetime import datetime, timedelta
import random

DB_PATH = "cbz_crm.db"

# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────
SCHEMA = """

-- Relationship Managers
CREATE TABLE IF NOT EXISTS relationship_managers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,          -- CA, CC, CE, CK
    full_name   TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT,
    role        TEXT DEFAULT 'RM',             -- RM | HEAD | COVER
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Clients
CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_code     TEXT NOT NULL UNIQUE,      -- e.g. CBZ-001
    company_name    TEXT NOT NULL,
    sector          TEXT,                      -- Agriculture, Manufacturing, etc.
    annual_turnover REAL,
    currency        TEXT DEFAULT 'USD',        -- USD | ZiG | ZAR
    rm_id           INTEGER NOT NULL,
    credit_rating   TEXT,                      -- A | B | C | D | NPL
    relationship_health INTEGER DEFAULT 100,  -- 0-100 score
    onboarded_date  TEXT,
    last_contact    TEXT,
    notes           TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (rm_id) REFERENCES relationship_managers(id)
);

-- Contacts (key people at each client)
CREATE TABLE IF NOT EXISTS contacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER NOT NULL,
    full_name   TEXT NOT NULL,
    title       TEXT,                          -- CFO | CEO | Finance Manager
    email       TEXT,
    phone       TEXT,
    is_primary  INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

-- Facilities (credit lines per client)
CREATE TABLE IF NOT EXISTS facilities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL,
    facility_type   TEXT NOT NULL,             -- RCF | OD | TL | LC | Guarantee
    currency        TEXT DEFAULT 'USD',
    limit_amount    REAL NOT NULL,
    utilisation     REAL DEFAULT 0,
    interest_rate   REAL,
    expiry_date     TEXT,
    status          TEXT DEFAULT 'Active',     -- Active | Expired | NPL | Watch
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

-- Interaction Log (every call, meeting, email)
CREATE TABLE IF NOT EXISTS interactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL,
    rm_id           INTEGER NOT NULL,
    interaction_type TEXT NOT NULL,            -- Call | Meeting | Email | Site Visit
    subject         TEXT NOT NULL,
    notes           TEXT,
    action_items    TEXT,                      -- pipe-delimited list of actions
    interaction_date TEXT NOT NULL,
    follow_up_date  TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (rm_id) REFERENCES relationship_managers(id)
);

-- Tasks & Pipeline
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER,
    rm_id       INTEGER NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    priority    TEXT DEFAULT 'Medium',         -- High | Medium | Low
    status      TEXT DEFAULT 'Open',           -- Open | In Progress | Done | Overdue
    due_date    TEXT,
    completed_at TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (rm_id) REFERENCES relationship_managers(id)
);

-- Covenants
CREATE TABLE IF NOT EXISTS covenants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL,
    facility_id     INTEGER,
    covenant_type   TEXT NOT NULL,             -- Debt/EBITDA | Current Ratio | Insurance | Audited Financials
    description     TEXT,
    threshold       TEXT,                      -- e.g. "< 3.5x" or "Submit by 31 Mar"
    last_value      TEXT,                      -- last reported value
    last_checked    TEXT,
    next_due        TEXT,
    status          TEXT DEFAULT 'Compliant',  -- Compliant | Breach | Waived | Pending
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (facility_id) REFERENCES facilities(id)
);

-- Handovers (when an RM goes on leave)
CREATE TABLE IF NOT EXISTS handovers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_rm_id      INTEGER NOT NULL,
    to_rm_id        INTEGER NOT NULL,
    start_date      TEXT NOT NULL,
    end_date        TEXT,
    status          TEXT DEFAULT 'Active',     -- Active | Completed | Cancelled
    brief_text      TEXT,                      -- AI-generated or manual handover brief
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (from_rm_id) REFERENCES relationship_managers(id),
    FOREIGN KEY (to_rm_id) REFERENCES relationship_managers(id)
);

-- Handover scope (which clients are covered)
CREATE TABLE IF NOT EXISTS handover_clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    handover_id     INTEGER NOT NULL,
    client_id       INTEGER NOT NULL,
    FOREIGN KEY (handover_id) REFERENCES handovers(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

-- Documents
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL,
    doc_type        TEXT NOT NULL,             -- Audited Financials | Board Resolution | Facility Letter | KYC
    doc_name        TEXT NOT NULL,
    file_path       TEXT,
    year            INTEGER,
    uploaded_by_rm  INTEGER,
    uploaded_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (uploaded_by_rm) REFERENCES relationship_managers(id)
);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER,
    rm_id       INTEGER NOT NULL,
    alert_type  TEXT NOT NULL,                 -- Covenant Breach | Facility Expiry | Cold Relationship | Task Overdue
    message     TEXT NOT NULL,
    severity    TEXT DEFAULT 'Medium',         -- High | Medium | Low
    is_read     INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (rm_id) REFERENCES relationship_managers(id)
);
"""

# ─────────────────────────────────────────────
# SEED DATA
# ─────────────────────────────────────────────

def seed(conn):
    c = conn.cursor()

    # ── Relationship Managers ──
    rms = [
        ("CA", "Chiedza Mawere",     "c.mawere@cbz.co.zw",    "+263 77 210 0001"),
        ("CC", "Courage Chikwanda",  "c.chikwanda@cbz.co.zw", "+263 77 210 0002"),
        ("CE", "Chipo Edzai",        "c.edzai@cbz.co.zw",     "+263 77 210 0003"),
        ("CK", "Chaka Kamba",        "c.kamba@cbz.co.zw",     "+263 77 210 0004"),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO relationship_managers (code, full_name, email, phone) VALUES (?,?,?,?)",
        rms
    )
    conn.commit()

    # get RM ids
    rm = {row[0]: row[1] for row in c.execute("SELECT code, id FROM relationship_managers")}

    # ── Clients ──
    today = datetime.today()
    def daysago(n): return (today - timedelta(days=n)).strftime("%Y-%m-%d")
    def daysfrom(n): return (today + timedelta(days=n)).strftime("%Y-%m-%d")

    clients_data = [
        # (client_code, company_name, sector, turnover, currency, rm_code, rating, health, onboarded, last_contact)
        # ── CA portfolio ──
        ("CBZ-001", "Quton Seed Company (Pvt) Ltd",      "Agriculture",    18_500_000, "USD", "CA", "B", 78, daysago(900), daysago(12)),
        ("CBZ-002", "Dendairy (Pvt) Ltd",                "Agriculture",    22_000_000, "USD", "CA", "A", 91, daysago(1200), daysago(5)),
        ("CBZ-003", "Ariston Holdings Ltd",              "Agriculture",     9_800_000, "USD", "CA", "B", 65, daysago(800), daysago(34)),
        ("CBZ-004", "Starafrica Corporation Ltd",        "FMCG",           31_000_000, "USD", "CA", "B", 82, daysago(1100), daysago(8)),

        # ── CC portfolio ──
        ("CBZ-005", "Innscor Africa Ltd",                "FMCG",           95_000_000, "USD", "CC", "A", 95, daysago(1500), daysago(3)),
        ("CBZ-006", "Padenga Holdings Ltd",              "Agriculture",    14_000_000, "USD", "CC", "A", 88, daysago(950), daysago(9)),
        ("CBZ-007", "Hwange Colliery Company Ltd",       "Mining",         27_000_000, "USD", "CC", "C", 42, daysago(700), daysago(68)),
        ("CBZ-008", "Zimbabwe Consolidated Diamond Co",  "Mining",         55_000_000, "USD", "CC", "B", 71, daysago(1000), daysago(21)),

        # ── CE portfolio ──
        ("CBZ-009", "Econet Wireless Zimbabwe Ltd",      "Telecoms",      180_000_000, "USD", "CE", "A", 97, daysago(1800), daysago(2)),
        ("CBZ-010", "NetOne Cellular (Pvt) Ltd",         "Telecoms",       62_000_000, "USD", "CE", "B", 74, daysago(1100), daysago(15)),
        ("CBZ-011", "Zimplats Holdings Ltd",             "Mining",        310_000_000, "USD", "CE", "A", 93, daysago(2000), daysago(7)),
        ("CBZ-012", "Bindura Nickel Corporation Ltd",    "Mining",         38_000_000, "USD", "CE", "C", 55, daysago(600), daysago(45)),

        # ── CK portfolio ──
        ("CBZ-013", "OK Zimbabwe Ltd",                   "Retail",         74_000_000, "USD", "CK", "A", 89, daysago(1300), daysago(6)),
        ("CBZ-014", "Edgars Stores Ltd",                 "Retail",         18_000_000, "ZiG", "CK", "C", 48, daysago(500), daysago(72)),
        ("CBZ-015", "Delta Beverages (Pvt) Ltd",         "Manufacturing",  88_000_000, "USD", "CK", "A", 96, daysago(1600), daysago(4)),
        ("CBZ-016", "Cairns Holdings Ltd",               "Manufacturing",  11_500_000, "ZiG", "CK", "B", 61, daysago(750), daysago(28)),
    ]

    for row in clients_data:
        code, name, sector, turnover, currency, rm_code, rating, health, onboarded, last_contact = row
        c.execute("""
            INSERT OR IGNORE INTO clients
            (client_code, company_name, sector, annual_turnover, currency, rm_id,
             credit_rating, relationship_health, onboarded_date, last_contact)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (code, name, sector, turnover, currency, rm[rm_code], rating, health, onboarded, last_contact))
    conn.commit()

    # get client ids
    cl = {row[0]: row[1] for row in c.execute("SELECT client_code, id FROM clients")}

    # ── Contacts ──
    contacts_data = [
        (cl["CBZ-001"], "Tendai Moyo",      "CFO",             "t.moyo@quton.co.zw",    "+263 77 300 1001", 1),
        (cl["CBZ-001"], "Rudo Chigumba",    "Finance Manager", "r.chigumba@quton.co.zw","+263 77 300 1002", 0),
        (cl["CBZ-002"], "Blessing Mlambo",  "CFO",             "b.mlambo@dendairy.co.zw","+263 77 300 2001",1),
        (cl["CBZ-005"], "Farai Matsika",    "Group CFO",       "f.matsika@innscor.co.zw","+263 77 300 5001",1),
        (cl["CBZ-007"], "Mthokozisi Dube",  "Finance Director","m.dube@hwange.co.zw",   "+263 29 230 0100", 1),
        (cl["CBZ-009"], "Nyasha Mupfururi", "CFO",             "n.mupfururi@econet.co.zw","+263 77 300 9001",1),
        (cl["CBZ-011"], "Portia Sibanda",   "Treasurer",       "p.sibanda@zimplats.co.zw","+263 77 300 1101",1),
        (cl["CBZ-013"], "Takudzwa Zvobgo",  "CFO",             "t.zvobgo@okzim.co.zw",  "+263 77 300 1301", 1),
        (cl["CBZ-015"], "Simbarashe Nhete", "Group Treasurer", "s.nhete@delta.co.zw",   "+263 77 300 1501", 1),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO contacts (client_id, full_name, title, email, phone, is_primary) VALUES (?,?,?,?,?,?)",
        contacts_data
    )
    conn.commit()

    # ── Facilities ──
    facilities_data = [
        # (client_code, type, currency, limit, utilisation, rate, expiry, status)
        ("CBZ-001", "RCF",       "USD",  5_000_000,  3_800_000, 8.5,  daysfrom(120), "Active"),
        ("CBZ-001", "LC",        "USD",  1_500_000,  1_200_000, 2.5,  daysfrom(60),  "Active"),
        ("CBZ-002", "OD",        "USD",  2_000_000,    800_000, 7.0,  daysfrom(210), "Active"),
        ("CBZ-002", "TL",        "USD", 10_000_000,  7_500_000, 9.0,  daysfrom(730), "Active"),
        ("CBZ-003", "RCF",       "USD",  3_000_000,  2_900_000, 9.5,  daysfrom(30),  "Active"),
        ("CBZ-005", "RCF",       "USD", 15_000_000, 12_000_000, 7.5,  daysfrom(365), "Active"),
        ("CBZ-005", "Guarantee", "USD",  5_000_000,  5_000_000, 1.5,  daysfrom(180), "Active"),
        ("CBZ-007", "OD",        "USD",  2_500_000,  2_500_000, 11.0, daysfrom(14),  "Watch"),
        ("CBZ-007", "TL",        "USD",  8_000_000,  8_000_000, 10.5, daysago(30),   "NPL"),
        ("CBZ-009", "RCF",       "USD", 30_000_000, 18_000_000, 6.5,  daysfrom(540), "Active"),
        ("CBZ-011", "TL",        "USD", 50_000_000, 42_000_000, 7.0,  daysfrom(1095),"Active"),
        ("CBZ-013", "OD",        "USD",  8_000_000,  3_200_000, 8.0,  daysfrom(365), "Active"),
        ("CBZ-014", "RCF",       "ZiG", 10_000_000,  9_800_000, 12.0, daysfrom(45),  "Watch"),
        ("CBZ-015", "RCF",       "USD", 20_000_000, 11_000_000, 7.0,  daysfrom(730), "Active"),
        ("CBZ-015", "LC",        "USD",  5_000_000,  2_500_000, 2.0,  daysfrom(180), "Active"),
        ("CBZ-016", "OD",        "ZiG",  3_000_000,  2_800_000, 13.0, daysfrom(90),  "Active"),
    ]
    fac_ids = {}
    for row in facilities_data:
        code, ftype, curr, lim, util, rate, expiry, status = row
        cur2 = conn.cursor()
        cur2.execute("""
            INSERT INTO facilities (client_id, facility_type, currency, limit_amount, utilisation, interest_rate, expiry_date, status)
            VALUES (?,?,?,?,?,?,?,?)
        """, (cl[code], ftype, curr, lim, util, rate, expiry, status))
        fac_ids[(code, ftype)] = cur2.lastrowid
    conn.commit()

    # ── Interactions ──
    interactions_data = [
        (cl["CBZ-001"], rm["CA"], "Meeting",    "Quarterly review Q1 2026",
         "Discussed RCF utilisation at 76%. Client flagged upcoming capex for irrigation. No covenant concerns.",
         "Send updated facility letter|Follow up on audited financials by 30 Apr",
         daysago(12), daysago(2)),

        (cl["CBZ-002"], rm["CA"], "Call",       "Annual review prep call",
         "CFO confirmed financials ready. EBITDA up 14% YoY. Debt/EBITDA at 1.8x — well within covenant.",
         "Schedule formal annual review meeting",
         daysago(5), daysfrom(7)),

        (cl["CBZ-003"], rm["CA"], "Email",      "RCF renewal discussion",
         "Client requested 6-month extension on RCF. Current utilisation near limit. Monitoring closely.",
         "Prepare renewal credit paper|Escalate to credit committee",
         daysago(34), daysago(20)),

        (cl["CBZ-005"], rm["CC"], "Meeting",    "Group treasury strategy meeting",
         "Innscor expanding into Zambia. Discussed trade finance requirements for cross-border ops.",
         "Prepare trade finance proposal|Loop in trade team",
         daysago(3), daysfrom(14)),

        (cl["CBZ-007"], rm["CC"], "Site Visit", "Hwange operational review",
         "Production down 30% due to equipment failure. Cash flow severely constrained. TL in arrears 45 days.",
         "Escalate NPL classification|Request restructure proposal from client",
         daysago(68), daysago(50)),

        (cl["CBZ-009"], rm["CE"], "Meeting",    "RCF drawdown discussion",
         "Econet drawing down for network expansion in rural areas. Strong cash flow. No concerns.",
         "Confirm drawdown instructions|Update utilisation in system",
         daysago(2), daysfrom(5)),

        (cl["CBZ-011"], rm["CE"], "Call",       "Term loan repayment schedule confirmation",
         "Zimplats confirmed Q2 repayment on schedule. Platinum prices stable. Good visibility on cash.",
         "Send repayment confirmation letter",
         daysago(7), daysfrom(3)),

        (cl["CBZ-012"], rm["CE"], "Email",      "Covenant compliance — current ratio",
         "Client submitted management accounts. Current ratio at 0.98 — below 1.2x threshold. Breach.",
         "Issue covenant breach notice|Schedule call with CFO",
         daysago(45), daysago(30)),

        (cl["CBZ-013"], rm["CK"], "Meeting",    "Overdraft review and Q1 performance",
         "OK Zim Q1 revenue up 8%. OD utilisation at 40% — comfortable. Discussed possible TL for new stores.",
         "Prepare TL indicative terms|Send to credit for pre-approval",
         daysago(6), daysfrom(10)),

        (cl["CBZ-014"], rm["CK"], "Call",       "Edgars liquidity concern",
         "CFO flagged difficulty meeting RCF repayment due in 45 days. Retail environment tough. Monitor closely.",
         "Request updated cash flow forecast|Escalate to watch list",
         daysago(72), daysago(60)),

        (cl["CBZ-015"], rm["CK"], "Meeting",    "Annual review Delta Beverages",
         "Excellent performance. Sorghum volumes up, export revenues strong. Keen on green bond facility.",
         "Research green bond structuring|Involve DCM team",
         daysago(4), daysfrom(7)),
    ]
    for row in interactions_data:
        c.execute("""
            INSERT INTO interactions
            (client_id, rm_id, interaction_type, subject, notes, action_items, interaction_date, follow_up_date)
            VALUES (?,?,?,?,?,?,?,?)
        """, row)
    conn.commit()

    # ── Tasks ──
    tasks_data = [
        (cl["CBZ-001"], rm["CA"], "Submit renewal credit paper — Quton RCF",   "RCF expires in 120 days. Paper due to credit committee.", "High",   "In Progress", daysfrom(14)),
        (cl["CBZ-003"], rm["CA"], "Escalate Ariston RCF to credit committee",  "Near-limit utilisation. Extension requested.",             "High",   "Open",        daysfrom(5)),
        (cl["CBZ-007"], rm["CC"], "Hwange NPL restructure proposal",            "Obtain restructure terms from client. Arrears 45 days.",  "High",   "Open",        daysfrom(7)),
        (cl["CBZ-012"], rm["CE"], "Issue covenant breach notice — Bindura",     "Current ratio breach. Formal notice required.",           "High",   "Overdue",     daysago(15)),
        (cl["CBZ-014"], rm["CK"], "Edgars watch list memo",                     "Prepare internal watch list memo for credit team.",       "High",   "Open",        daysfrom(3)),
        (cl["CBZ-002"], rm["CA"], "Schedule Dendairy annual review meeting",    "CFO confirmed financials ready.",                         "Medium", "Open",        daysfrom(7)),
        (cl["CBZ-009"], rm["CE"], "Confirm Econet drawdown instructions",       "Drawdown for rural network expansion.",                   "Medium", "Open",        daysfrom(5)),
        (cl["CBZ-015"], rm["CK"], "Involve DCM for Delta green bond",           "Delta keen on green bond. Loop in DCM team.",             "Medium", "Open",        daysfrom(14)),
        (cl["CBZ-005"], rm["CC"], "Prepare Innscor trade finance proposal",     "Cross-border Zambia expansion.",                         "Medium", "In Progress", daysfrom(14)),
        (cl["CBZ-013"], rm["CK"], "OK Zim TL indicative terms",                "New stores TL. Get pre-approval from credit.",            "Low",    "Open",        daysfrom(21)),
    ]
    for row in tasks_data:
        c.execute("""
            INSERT INTO tasks (client_id, rm_id, title, description, priority, status, due_date)
            VALUES (?,?,?,?,?,?,?)
        """, row)
    conn.commit()

    # ── Covenants ──
    covenants_data = [
        (cl["CBZ-001"], fac_ids.get(("CBZ-001","RCF")), "Debt/EBITDA",         "Net debt to EBITDA must remain below 3.5x", "< 3.5x",  "2.9x",  daysago(60),  daysfrom(90),  "Compliant"),
        (cl["CBZ-001"], None,                            "Audited Financials",  "Submit audited financials by 30 April",     "30 Apr",  None,    None,          daysfrom(21),  "Pending"),
        (cl["CBZ-002"], fac_ids.get(("CBZ-002","TL")),  "Debt/EBITDA",         "Net debt to EBITDA < 3.0x",                "< 3.0x",  "1.8x",  daysago(30),  daysfrom(120), "Compliant"),
        (cl["CBZ-007"], fac_ids.get(("CBZ-007","OD")),  "Current Ratio",       "Current ratio must remain above 1.1x",     "> 1.1x",  "0.85x", daysago(14),  daysfrom(30),  "Breach"),
        (cl["CBZ-007"], None,                            "Insurance",           "All plant and equipment insured",           "Annual",  None,    daysago(180), daysago(1),    "Breach"),
        (cl["CBZ-012"], None,                            "Current Ratio",       "Current ratio must remain above 1.2x",     "> 1.2x",  "0.98x", daysago(45),  daysfrom(45),  "Breach"),
        (cl["CBZ-014"], None,                            "Debt/EBITDA",         "Net debt to EBITDA < 4.0x",                "< 4.0x",  "3.8x",  daysago(90),  daysfrom(30),  "Compliant"),
        (cl["CBZ-003"], fac_ids.get(("CBZ-003","RCF")), "Audited Financials",  "Submit audited financials by 31 March",    "31 Mar",  None,    None,          daysago(40),   "Breach"),
        (cl["CBZ-009"], None,                            "Debt/EBITDA",         "Net debt to EBITDA < 2.5x",                "< 2.5x",  "1.2x",  daysago(20),  daysfrom(160), "Compliant"),
        (cl["CBZ-015"], None,                            "Debt/EBITDA",         "Net debt to EBITDA < 2.0x",                "< 2.0x",  "0.9x",  daysago(10),  daysfrom(180), "Compliant"),
    ]
    for row in covenants_data:
        c.execute("""
            INSERT INTO covenants
            (client_id, facility_id, covenant_type, description, threshold, last_value, last_checked, next_due, status)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, row)
    conn.commit()

    # ── Alerts ──
    alerts_data = [
        (cl["CBZ-007"], rm["CC"], "Covenant Breach",    "Hwange Colliery: Current ratio at 0.85x — below 1.1x threshold. Immediate action required.", "High"),
        (cl["CBZ-007"], rm["CC"], "Covenant Breach",    "Hwange Colliery: Insurance covenant overdue. Policy renewal not confirmed.", "High"),
        (cl["CBZ-012"], rm["CE"], "Covenant Breach",    "Bindura Nickel: Current ratio at 0.98x — below 1.2x threshold.", "High"),
        (cl["CBZ-003"], rm["CA"], "Covenant Breach",    "Ariston Holdings: Audited financials not submitted by 31 March deadline.", "High"),
        (cl["CBZ-003"], rm["CA"], "Facility Expiry",    "Ariston Holdings RCF expires in 30 days. Renewal paper not yet submitted.", "High"),
        (cl["CBZ-014"], rm["CK"], "Cold Relationship",  "Edgars Stores: Last contact was 72 days ago. Relationship health at 48%.", "Medium"),
        (cl["CBZ-007"], rm["CC"], "Cold Relationship",  "Hwange Colliery: Last contact was 68 days ago. Account in NPL status.", "Medium"),
        (cl["CBZ-012"], rm["CE"], "Cold Relationship",  "Bindura Nickel: Last contact was 45 days ago. Covenant breach unresolved.", "Medium"),
        (cl["CBZ-007"], rm["CC"], "Facility Expiry",    "Hwange Colliery OD expires in 14 days. Account on watch list.", "High"),
    ]
    for row in alerts_data:
        c.execute("""
            INSERT INTO alerts (client_id, rm_id, alert_type, message, severity)
            VALUES (?,?,?,?,?)
        """, row)
    conn.commit()

    print("\n✅ Seed data inserted successfully.")
    print(f"   Relationship Managers : {c.execute('SELECT COUNT(*) FROM relationship_managers').fetchone()[0]}")
    print(f"   Clients               : {c.execute('SELECT COUNT(*) FROM clients').fetchone()[0]}")
    print(f"   Contacts              : {c.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]}")
    print(f"   Facilities            : {c.execute('SELECT COUNT(*) FROM facilities').fetchone()[0]}")
    print(f"   Interactions          : {c.execute('SELECT COUNT(*) FROM interactions').fetchone()[0]}")
    print(f"   Tasks                 : {c.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]}")
    print(f"   Covenants             : {c.execute('SELECT COUNT(*) FROM covenants').fetchone()[0]}")
    print(f"   Alerts                : {c.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"🗑  Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    print(f"✅ Schema created — {DB_PATH}")
    seed(conn)
    conn.close()
    print(f"\n🏦 CBZ CRM database ready: {DB_PATH}")
    print("   Next step → run the Phase 2 Flask API (app.py)")
