import sqlite3
from datetime import datetime, timedelta

DB = "bot.db"

def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    db = con()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY,
            name      TEXT DEFAULT '',
            username  TEXT DEFAULT '',
            joined    TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS admins (
            id   INTEGER PRIMARY KEY,
            name TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS movies (
            code   TEXT PRIMARY KEY,
            msg_id TEXT NOT NULL,
            title  TEXT DEFAULT '',
            views  INTEGER DEFAULT 0,
            added  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS channels (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE NOT NULL,
            title      TEXT DEFAULT '',
            link       TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            amount     INTEGER,
            card_type  TEXT,
            file_id    TEXT,
            status     TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id    INTEGER PRIMARY KEY,
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
    """)
    defaults = [
        ("sub_price",    "15000"),
        ("sub_days",     "30"),
        ("card_uzcard",  "8600 0000 0000 0000"),
        ("card_humo",    "9860 0000 0000 0000"),
        ("card_visa",    "4111 0000 0000 0000"),
        ("card_owner",   "Admin"),
        ("movie_ch",     ""),
        ("welcome_text", "Kino kodini yuboring 🎬"),
    ]
    for k, v in defaults:
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
    db.commit()
    db.close()

def gs(key):
    db = con()
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    db.close()
    return r["value"] if r else ""

def ss(key, val):
    db = con()
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, val))
    db.commit()
    db.close()

def add_user(uid, name, uname):
    db = con()
    is_new = db.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone() is None
    db.execute("INSERT OR IGNORE INTO users(id,name,username) VALUES(?,?,?)",
               (uid, name or "", uname or ""))
    db.execute("UPDATE users SET last_seen=datetime('now') WHERE id=?", (uid,))
    db.commit()
    db.close()
    return is_new

def all_user_ids():
    db = con()
    r = db.execute("SELECT id FROM users").fetchall()
    db.close()
    return [x["id"] for x in r]

def user_stats():
    db = con()
    def q(sql): return db.execute(sql).fetchone()["c"]
    s = {
        "total": q("SELECT COUNT(*) as c FROM users"),
        "today": q("SELECT COUNT(*) as c FROM users WHERE date(joined)=date('now')"),
        "week":  q("SELECT COUNT(*) as c FROM users WHERE joined>=datetime('now','-7 days')"),
        "month": q("SELECT COUNT(*) as c FROM users WHERE joined>=datetime('now','-30 days')"),
        "act24": q("SELECT COUNT(*) as c FROM users WHERE last_seen>=datetime('now','-1 days')"),
        "act7":  q("SELECT COUNT(*) as c FROM users WHERE last_seen>=datetime('now','-7 days')"),
        "act30": q("SELECT COUNT(*) as c FROM users WHERE last_seen>=datetime('now','-30 days')"),
    }
    db.close()
    return s

def is_admin(uid):
    from config import ADMIN_IDS
    if uid in ADMIN_IDS: return True
    db = con()
    r = db.execute("SELECT id FROM admins WHERE id=?", (uid,)).fetchone()
    db.close()
    return r is not None

def add_admin(uid, name):
    db = con()
    db.execute("INSERT OR REPLACE INTO admins(id,name) VALUES(?,?)", (uid, name))
    db.commit()
    db.close()

def del_admin(uid):
    db = con()
    n = db.execute("DELETE FROM admins WHERE id=?", (uid,)).rowcount
    db.commit()
    db.close()
    return n > 0

def get_admins():
    db = con()
    r = db.execute("SELECT * FROM admins").fetchall()
    db.close()
    return r

def all_admin_ids():
    from config import ADMIN_IDS
    ids = list(ADMIN_IDS)
    for a in get_admins():
        if a["id"] not in ids:
            ids.append(a["id"])
    return ids

def save_movie(code, msg_id, title=""):
    db = con()
    db.execute("INSERT OR REPLACE INTO movies(code,msg_id,title) VALUES(?,?,?)",
               (str(code).strip(), str(msg_id).strip(), title))
    db.commit()
    db.close()

def get_movie(code):
    db = con()
    r = db.execute("SELECT * FROM movies WHERE code=?", (str(code).strip(),)).fetchone()
    if r:
        db.execute("UPDATE movies SET views=views+1 WHERE code=?", (str(code).strip(),))
        db.commit()
    db.close()
    return r

def update_movie(old, new_code, new_msgid, new_title):
    db = con()
    db.execute("DELETE FROM movies WHERE code=?", (old,))
    db.execute("INSERT INTO movies(code,msg_id,title) VALUES(?,?,?)",
               (new_code, new_msgid, new_title))
    db.commit()
    db.close()

def del_movie(code):
    db = con()
    n = db.execute("DELETE FROM movies WHERE code=?", (str(code).strip(),)).rowcount
    db.commit()
    db.close()
    return n > 0

def movie_count():
    db = con()
    c = db.execute("SELECT COUNT(*) as c FROM movies").fetchone()["c"]
    db.close()
    return c

def get_movies(limit=30, offset=0):
    db = con()
    r = db.execute("SELECT * FROM movies ORDER BY rowid DESC LIMIT ? OFFSET ?",
                   (limit, offset)).fetchall()
    db.close()
    return r

def add_channel(ch_id, title, link):
    db = con()
    db.execute("INSERT OR REPLACE INTO channels(channel_id,title,link) VALUES(?,?,?)",
               (ch_id, title, link))
    db.commit()
    db.close()

def get_channels():
    db = con()
    r = db.execute("SELECT * FROM channels").fetchall()
    db.close()
    return r

def del_channel(row_id):
    db = con()
    n = db.execute("DELETE FROM channels WHERE id=?", (row_id,)).rowcount
    db.commit()
    db.close()
    return n > 0

def add_payment(uid, amount, card_type, file_id):
    db = con()
    if db.execute("SELECT id FROM payments WHERE user_id=? AND status='pending'",
                  (uid,)).fetchone():
        db.close()
        return None
    c = db.execute(
        "INSERT INTO payments(user_id,amount,card_type,file_id) VALUES(?,?,?,?)",
        (uid, amount, card_type, file_id))
    pay_id = c.lastrowid
    db.commit()
    db.close()
    return pay_id

def get_payment(pay_id):
    db = con()
    r = db.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    db.close()
    return r

def resolve_payment(pay_id, status):
    db = con()
    db.execute("UPDATE payments SET status=? WHERE id=?", (status, pay_id))
    db.commit()
    db.close()

def give_sub(uid, days=30):
    db = con()
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    db.execute("INSERT OR REPLACE INTO subscriptions(user_id,expires_at) VALUES(?,?)",
               (uid, expires))
    db.commit()
    db.close()

def has_sub(uid):
    db = con()
    r = db.execute("SELECT expires_at FROM subscriptions WHERE user_id=?",
                   (uid,)).fetchone()
    db.close()
    if not r: return False
    return datetime.now() < datetime.fromisoformat(r["expires_at"])

def sub_info(uid):
    db = con()
    r = db.execute("SELECT * FROM subscriptions WHERE user_id=?", (uid,)).fetchone()
    db.close()
    return r
