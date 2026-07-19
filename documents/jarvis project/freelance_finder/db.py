"""SQLite database layer for storing job leads and generated proposals."""
import sqlite3
from datetime import datetime

DB_PATH = "leads.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            title TEXT,
            link TEXT UNIQUE,
            summary TEXT,
            fetched_at TEXT,
            proposal TEXT,
            status TEXT DEFAULT 'new'
        )
    """)
    conn.commit()
    conn.close()


def add_lead(source, title, link, summary):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO leads (source, title, link, summary, fetched_at) VALUES (?, ?, ?, ?, ?)",
            (source, title, link, summary, datetime.utcnow().isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # already exists (duplicate link)
    finally:
        conn.close()


def get_leads(status=None):
    conn = get_conn()
    if status:
        rows = conn.execute("SELECT * FROM leads WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def update_proposal(lead_id, proposal_text):
    conn = get_conn()
    conn.execute("UPDATE leads SET proposal = ? WHERE id = ?", (proposal_text, lead_id))
    conn.commit()
    conn.close()


def update_status(lead_id, status):
    conn = get_conn()
    conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
    conn.commit()
    conn.close()
