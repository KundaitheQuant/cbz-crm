"""
CBZ Corporate Banking CRM
Phase 2 - Flask Backend API
Run: python app.py
API runs at: http://localhost:5000
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "cbz_crm.db")


# ─────────────────────────────────────────────
# DB HELPER
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def rows_to_list(rows):
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# ROOT
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory('.', 'index.html')

@app.route("/handover")
def handover():
    return send_from_directory('.', 'handover.html')

@app.route("/ai")
def ai():
    return send_from_directory('.', 'ai.html')

@app.route("/api")
def api_index():
    return jsonify({
        "system": "CBZ Corporate Banking CRM",
        "version": "1.0",
        "status": "running",
        "endpoints": [
            "GET  /api/rms",
            "GET  /api/rms/<id>/dashboard",
            "GET  /api/clients",
            "GET  /api/clients/<id>",
            "POST /api/clients",
            "GET  /api/clients/<id>/interactions",
            "POST /api/clients/<id>/interactions",
            "GET  /api/clients/<id>/facilities",
            "GET  /api/clients/<id>/covenants",
            "GET  /api/clients/<id>/tasks",
            "GET  /api/tasks",
            "POST /api/tasks",
            "PUT  /api/tasks/<id>",
            "GET  /api/alerts",
            "PUT  /api/alerts/<id>/read",
            "POST /api/handovers",
            "GET  /api/handovers",
            "GET  /api/portfolio/summary",
        ]
    })


# ─────────────────────────────────────────────
# RELATIONSHIP MANAGERS
# ─────────────────────────────────────────────

@app.route("/api/rms")
def get_rms():
    db = get_db()
    rms = rows_to_list(db.execute("SELECT * FROM relationship_managers").fetchall())
    db.close()
    return jsonify(rms)


@app.route("/api/rms/<int:rm_id>/dashboard")
def rm_dashboard(rm_id):
    """Full dashboard summary for a single RM."""
    db = get_db()

    rm = dict(db.execute(
        "SELECT * FROM relationship_managers WHERE id = ?", (rm_id,)
    ).fetchone())

    clients = rows_to_list(db.execute(
        "SELECT * FROM clients WHERE rm_id = ? AND is_active = 1 ORDER BY company_name",
        (rm_id,)
    ).fetchall())

    # facility totals
    facility_totals = dict(db.execute("""
        SELECT
            SUM(f.limit_amount)   AS total_limit,
            SUM(f.utilisation)    AS total_utilised,
            COUNT(*)              AS facility_count
        FROM facilities f
        JOIN clients c ON f.client_id = c.id
        WHERE c.rm_id = ? AND c.is_active = 1
    """, (rm_id,)).fetchone())

    open_tasks = rows_to_list(db.execute("""
        SELECT t.*, c.company_name
        FROM tasks t
        LEFT JOIN clients c ON t.client_id = c.id
        WHERE t.rm_id = ? AND t.status != 'Done'
        ORDER BY t.due_date ASC
    """, (rm_id,)).fetchall())

    unread_alerts = rows_to_list(db.execute("""
        SELECT a.*, c.company_name
        FROM alerts a
        LEFT JOIN clients c ON a.client_id = c.id
        WHERE a.rm_id = ? AND a.is_read = 0
        ORDER BY a.created_at DESC
    """, (rm_id,)).fetchall())

    covenant_breaches = rows_to_list(db.execute("""
        SELECT cv.*, c.company_name
        FROM covenants cv
        JOIN clients c ON cv.client_id = c.id
        WHERE c.rm_id = ? AND cv.status = 'Breach'
    """, (rm_id,)).fetchall())

    recent_interactions = rows_to_list(db.execute("""
        SELECT i.*, c.company_name
        FROM interactions i
        JOIN clients c ON i.client_id = c.id
        WHERE i.rm_id = ?
        ORDER BY i.interaction_date DESC
        LIMIT 5
    """, (rm_id,)).fetchall())

    db.close()

    util_pct = 0
    if facility_totals["total_limit"] and facility_totals["total_limit"] > 0:
        util_pct = round(facility_totals["total_utilised"] / facility_totals["total_limit"] * 100, 1)

    return jsonify({
        "rm": rm,
        "summary": {
            "client_count":      len(clients),
            "total_limit_usd":   facility_totals["total_limit"],
            "total_utilised_usd":facility_totals["total_utilised"],
            "utilisation_pct":   util_pct,
            "open_tasks":        len(open_tasks),
            "unread_alerts":     len(unread_alerts),
            "covenant_breaches": len(covenant_breaches),
        },
        "clients":              clients,
        "open_tasks":           open_tasks,
        "unread_alerts":        unread_alerts,
        "covenant_breaches":    covenant_breaches,
        "recent_interactions":  recent_interactions,
    })


# ─────────────────────────────────────────────
# CLIENTS
# ─────────────────────────────────────────────

@app.route("/api/clients")
def get_clients():
    db = get_db()
    rm_id  = request.args.get("rm_id")
    sector = request.args.get("sector")
    rating = request.args.get("rating")

    query  = "SELECT c.*, r.full_name as rm_name, r.code as rm_code FROM clients c JOIN relationship_managers r ON c.rm_id = r.id WHERE c.is_active = 1"
    params = []

    if rm_id:
        query += " AND c.rm_id = ?"
        params.append(rm_id)
    if sector:
        query += " AND c.sector = ?"
        params.append(sector)
    if rating:
        query += " AND c.credit_rating = ?"
        params.append(rating)

    query += " ORDER BY c.company_name"
    clients = rows_to_list(db.execute(query, params).fetchall())
    db.close()
    return jsonify(clients)


@app.route("/api/clients/<int:client_id>")
def get_client(client_id):
    """Full client 360 profile."""
    db = get_db()

    client = db.execute("""
        SELECT c.*, r.full_name as rm_name, r.code as rm_code, r.email as rm_email
        FROM clients c
        JOIN relationship_managers r ON c.rm_id = r.id
        WHERE c.id = ?
    """, (client_id,)).fetchone()

    if not client:
        return jsonify({"error": "Client not found"}), 404

    contacts     = rows_to_list(db.execute("SELECT * FROM contacts WHERE client_id = ?", (client_id,)).fetchall())
    facilities   = rows_to_list(db.execute("SELECT * FROM facilities WHERE client_id = ?", (client_id,)).fetchall())
    covenants    = rows_to_list(db.execute("SELECT * FROM covenants WHERE client_id = ?", (client_id,)).fetchall())
    tasks        = rows_to_list(db.execute("SELECT * FROM tasks WHERE client_id = ? ORDER BY due_date ASC", (client_id,)).fetchall())
    interactions = rows_to_list(db.execute("""
        SELECT i.*, r.full_name as rm_name
        FROM interactions i
        JOIN relationship_managers r ON i.rm_id = r.id
        WHERE i.client_id = ?
        ORDER BY i.interaction_date DESC
    """, (client_id,)).fetchall())
    documents    = rows_to_list(db.execute("SELECT * FROM documents WHERE client_id = ?", (client_id,)).fetchall())
    alerts       = rows_to_list(db.execute("SELECT * FROM alerts WHERE client_id = ? ORDER BY created_at DESC", (client_id,)).fetchall())

    db.close()
    return jsonify({
        "client":       dict(client),
        "contacts":     contacts,
        "facilities":   facilities,
        "covenants":    covenants,
        "tasks":        tasks,
        "interactions": interactions,
        "documents":    documents,
        "alerts":       alerts,
    })


@app.route("/api/clients", methods=["POST"])
def create_client():
    data = request.json
    required = ["company_name", "rm_id", "sector"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    db = get_db()
    # auto-generate client code
    count = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    client_code = f"CBZ-{str(count + 1).zfill(3)}"

    db.execute("""
        INSERT INTO clients (client_code, company_name, sector, annual_turnover,
            currency, rm_id, credit_rating, onboarded_date)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        client_code,
        data["company_name"],
        data["sector"],
        data.get("annual_turnover"),
        data.get("currency", "USD"),
        data["rm_id"],
        data.get("credit_rating", "B"),
        datetime.today().strftime("%Y-%m-%d"),
    ))
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return jsonify({"message": "Client created", "client_id": new_id, "client_code": client_code}), 201


# ─────────────────────────────────────────────
# INTERACTIONS
# ─────────────────────────────────────────────

@app.route("/api/clients/<int:client_id>/interactions")
def get_interactions(client_id):
    db = get_db()
    rows = rows_to_list(db.execute("""
        SELECT i.*, r.full_name as rm_name
        FROM interactions i
        JOIN relationship_managers r ON i.rm_id = r.id
        WHERE i.client_id = ?
        ORDER BY i.interaction_date DESC
    """, (client_id,)).fetchall())
    db.close()
    return jsonify(rows)


@app.route("/api/clients/<int:client_id>/interactions", methods=["POST"])
def log_interaction(client_id):
    data = request.json
    required = ["rm_id", "interaction_type", "subject", "interaction_date"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    db = get_db()
    db.execute("""
        INSERT INTO interactions
            (client_id, rm_id, interaction_type, subject, notes, action_items, interaction_date, follow_up_date)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        client_id,
        data["rm_id"],
        data["interaction_type"],
        data["subject"],
        data.get("notes", ""),
        data.get("action_items", ""),
        data["interaction_date"],
        data.get("follow_up_date"),
    ))
    # update last_contact on client
    db.execute("UPDATE clients SET last_contact = ? WHERE id = ?",
               (data["interaction_date"], client_id))
    db.commit()
    db.close()
    return jsonify({"message": "Interaction logged"}), 201


# ─────────────────────────────────────────────
# FACILITIES
# ─────────────────────────────────────────────

@app.route("/api/clients/<int:client_id>/facilities")
def get_facilities(client_id):
    db = get_db()
    rows = rows_to_list(db.execute(
        "SELECT * FROM facilities WHERE client_id = ?", (client_id,)
    ).fetchall())
    db.close()
    return jsonify(rows)


# ─────────────────────────────────────────────
# COVENANTS
# ─────────────────────────────────────────────

@app.route("/api/clients/<int:client_id>/covenants")
def get_covenants(client_id):
    db = get_db()
    rows = rows_to_list(db.execute(
        "SELECT * FROM covenants WHERE client_id = ? ORDER BY next_due ASC", (client_id,)
    ).fetchall())
    db.close()
    return jsonify(rows)


# ─────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────

@app.route("/api/tasks")
def get_tasks():
    db = get_db()
    rm_id  = request.args.get("rm_id")
    status = request.args.get("status")

    query  = """
        SELECT t.*, c.company_name, r.full_name as rm_name
        FROM tasks t
        LEFT JOIN clients c ON t.client_id = c.id
        JOIN relationship_managers r ON t.rm_id = r.id
        WHERE 1=1
    """
    params = []
    if rm_id:
        query += " AND t.rm_id = ?"
        params.append(rm_id)
    if status:
        query += " AND t.status = ?"
        params.append(status)

    query += " ORDER BY t.due_date ASC"
    rows = rows_to_list(db.execute(query, params).fetchall())
    db.close()
    return jsonify(rows)


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.json
    required = ["rm_id", "title"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    db = get_db()
    db.execute("""
        INSERT INTO tasks (client_id, rm_id, title, description, priority, status, due_date)
        VALUES (?,?,?,?,?,?,?)
    """, (
        data.get("client_id"),
        data["rm_id"],
        data["title"],
        data.get("description", ""),
        data.get("priority", "Medium"),
        "Open",
        data.get("due_date"),
    ))
    db.commit()
    db.close()
    return jsonify({"message": "Task created"}), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.json
    db = get_db()

    if "status" in data:
        completed_at = datetime.today().strftime("%Y-%m-%d") if data["status"] == "Done" else None
        db.execute(
            "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
            (data["status"], completed_at, task_id)
        )
    if "priority" in data:
        db.execute("UPDATE tasks SET priority = ? WHERE id = ?", (data["priority"], task_id))

    db.commit()
    db.close()
    return jsonify({"message": "Task updated"})


# ─────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────

@app.route("/api/alerts")
def get_alerts():
    db = get_db()
    rm_id = request.args.get("rm_id")

    query = """
        SELECT a.*, c.company_name
        FROM alerts a
        LEFT JOIN clients c ON a.client_id = c.id
        WHERE 1=1
    """
    params = []
    if rm_id:
        query += " AND a.rm_id = ?"
        params.append(rm_id)

    query += " ORDER BY a.created_at DESC"
    rows = rows_to_list(db.execute(query, params).fetchall())
    db.close()
    return jsonify(rows)


@app.route("/api/alerts/<int:alert_id>/read", methods=["PUT"])
def mark_alert_read(alert_id):
    db = get_db()
    db.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Alert marked as read"})


# ─────────────────────────────────────────────
# HANDOVERS
# ─────────────────────────────────────────────

@app.route("/api/handovers", methods=["POST"])
def create_handover():
    data = request.json
    required = ["from_rm_id", "to_rm_id", "start_date", "client_ids"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    db = get_db()

    # build a basic handover brief from recent interactions
    client_ids = data["client_ids"]
    brief_lines = [f"Handover brief — generated {datetime.today().strftime('%d %b %Y')}\n"]

    for cid in client_ids:
        client = db.execute("SELECT company_name FROM clients WHERE id = ?", (cid,)).fetchone()
        if not client:
            continue
        last = db.execute("""
            SELECT subject, notes, action_items, interaction_date
            FROM interactions WHERE client_id = ?
            ORDER BY interaction_date DESC LIMIT 1
        """, (cid,)).fetchone()
        tasks = rows_to_list(db.execute(
            "SELECT title, priority, due_date, status FROM tasks WHERE client_id = ? AND status != 'Done'",
            (cid,)
        ).fetchall())
        covenants = rows_to_list(db.execute(
            "SELECT covenant_type, status, next_due FROM covenants WHERE client_id = ? AND status != 'Compliant'",
            (cid,)
        ).fetchall())

        brief_lines.append(f"\n── {client['company_name']} ──")
        if last:
            brief_lines.append(f"Last contact ({last['interaction_date']}): {last['subject']}")
            if last["action_items"]:
                brief_lines.append(f"Open actions: {last['action_items']}")
        if tasks:
            brief_lines.append("Pending tasks: " + ", ".join([f"{t['title']} [{t['priority']}]" for t in tasks]))
        if covenants:
            brief_lines.append("Covenant issues: " + ", ".join([f"{cv['covenant_type']} — {cv['status']}" for cv in covenants]))

    brief_text = "\n".join(brief_lines)

    db.execute("""
        INSERT INTO handovers (from_rm_id, to_rm_id, start_date, end_date, status, brief_text)
        VALUES (?,?,?,?,?,?)
    """, (
        data["from_rm_id"],
        data["to_rm_id"],
        data["start_date"],
        data.get("end_date"),
        "Active",
        brief_text,
    ))
    handover_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    for cid in client_ids:
        db.execute("INSERT INTO handover_clients (handover_id, client_id) VALUES (?,?)", (handover_id, cid))

    db.commit()
    db.close()
    return jsonify({"message": "Handover created", "handover_id": handover_id, "brief": brief_text}), 201


@app.route("/api/handovers")
def get_handovers():
    db = get_db()
    rm_id = request.args.get("rm_id")

    query = """
        SELECT h.*,
               f.full_name as from_rm_name,
               t.full_name as to_rm_name
        FROM handovers h
        JOIN relationship_managers f ON h.from_rm_id = f.id
        JOIN relationship_managers t ON h.to_rm_id = t.id
        WHERE 1=1
    """
    params = []
    if rm_id:
        query += " AND (h.from_rm_id = ? OR h.to_rm_id = ?)"
        params.extend([rm_id, rm_id])

    rows = rows_to_list(db.execute(query, params).fetchall())
    db.close()
    return jsonify(rows)


# ─────────────────────────────────────────────
# PORTFOLIO SUMMARY (management view)
# ─────────────────────────────────────────────

@app.route("/api/portfolio/summary")
def portfolio_summary():
    db = get_db()

    rms = rows_to_list(db.execute("SELECT * FROM relationship_managers").fetchall())
    summary = []

    for rm in rms:
        rid = rm["id"]

        clients = db.execute(
            "SELECT COUNT(*) FROM clients WHERE rm_id = ? AND is_active = 1", (rid,)
        ).fetchone()[0]

        totals = dict(db.execute("""
            SELECT SUM(f.limit_amount) as lim, SUM(f.utilisation) as util
            FROM facilities f JOIN clients c ON f.client_id = c.id
            WHERE c.rm_id = ?
        """, (rid,)).fetchone())

        npl = db.execute("""
            SELECT COUNT(*) FROM facilities f JOIN clients c ON f.client_id = c.id
            WHERE c.rm_id = ? AND f.status = 'NPL'
        """, (rid,)).fetchone()[0]

        breaches = db.execute("""
            SELECT COUNT(*) FROM covenants cv JOIN clients c ON cv.client_id = c.id
            WHERE c.rm_id = ? AND cv.status = 'Breach'
        """, (rid,)).fetchone()[0]

        open_tasks = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE rm_id = ? AND status != 'Done'", (rid,)
        ).fetchone()[0]

        unread_alerts = db.execute(
            "SELECT COUNT(*) FROM alerts WHERE rm_id = ? AND is_read = 0", (rid,)
        ).fetchone()[0]

        util_pct = 0
        if totals["lim"] and totals["lim"] > 0:
            util_pct = round((totals["util"] or 0) / totals["lim"] * 100, 1)

        summary.append({
            "rm_id":           rid,
            "rm_code":         rm["code"],
            "rm_name":         rm["full_name"],
            "client_count":    clients,
            "total_limit":     totals["lim"] or 0,
            "total_utilised":  totals["util"] or 0,
            "utilisation_pct": util_pct,
            "npl_count":       npl,
            "covenant_breaches": breaches,
            "open_tasks":      open_tasks,
            "unread_alerts":   unread_alerts,
        })

    db.close()
    return jsonify(summary)


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("❌  cbz_crm.db not found. Run setup_database.py first.")
    else:
        print("🏦  CBZ Corporate Banking CRM — API starting...")
        print("    URL : http://localhost:5000")
        print("    Docs: http://localhost:5000/")
        print("    Stop: Ctrl + C\n")
        app.run(debug=True, port=5000)



# ─────────────────────────────────────────────
# USER MANAGEMENT
# ─────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
def get_users():
    db = get_db()
    users = rows_to_list(db.execute("SELECT id, username, full_name, role, created_at FROM crm_users").fetchall())
    db.close()
    return jsonify(users)

@app.route("/api/users", methods=["POST"])
def create_user():
    data = request.json
    required = ["username", "password", "full_name"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    db = get_db()
    existing = db.execute("SELECT id FROM crm_users WHERE username = ?", (data["username"].lower(),)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Username already exists"}), 400
    db.execute("""
        INSERT INTO crm_users (username, password, full_name, role)
        VALUES (?,?,?,?)
    """, (data["username"].lower(), data["password"], data["full_name"], data.get("role", "RM")))
    db.commit()
    db.close()
    return jsonify({"message": "User created successfully"}), 201

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    db = get_db()
    db.execute("DELETE FROM crm_users WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    return jsonify({"message": "User deleted"})

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "").lower()
    password = data.get("password", "")
    db = get_db()
    user = db.execute(
        "SELECT * FROM crm_users WHERE username = ? AND password = ?",
        (username, password)
    ).fetchone()
    db.close()
    if user:
        return jsonify({"success": True, "user": dict(user)})
    return jsonify({"success": False, "error": "Invalid credentials"}), 401

# ─────────────────────────────────────────────
# AI PROXY — routes Gemini calls through Flask
# so the browser doesn't hit CORS errors
# ─────────────────────────────────────────────
import urllib.request
import json as _json

GEMINI_KEY = "AIzaSyAigtgdR3GxHUOJBLuJiKfD7b-wLV1Rmqc"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

@app.route("/api/ai/generate", methods=["POST"])
def ai_generate():
    data = request.json
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    payload = _json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 1500}
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
