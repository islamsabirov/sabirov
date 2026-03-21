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
            id             INTEGER PRIMARY KEY,
            name           TEXT DEFAULT '',
            username       TEXT DEFAULT '',
            joined         TEXT DEFAULT (datetime('now')),
            last_seen      TEXT DEFAULT (datetime('now')),
            referral_by    INTEGER DEFAULT NULL,
            referral_count INTEGER DEFAULT 0
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
            is_pro INTEGER DEFAULT 0,
            added  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS channels (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT DEFAULT '',
            title      TEXT DEFAULT '',
            link       TEXT DEFAULT '',
            type       TEXT DEFAULT 'telegram'
        );
        CREATE TABLE IF NOT EXISTS payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            amount     INTEGER,
            card_type  TEXT,
            file_id    TEXT,
            plan       TEXT DEFAULT '1_month',
            status     TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id    INTEGER PRIMARY KEY,
            expires_at TEXT NOT NULL,
            plan       TEXT DEFAULT '1_month'
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
    """)

    # Eski DB ga yangi ustunlar qo'shish
    for sql in [
        "ALTER TABLE movies ADD COLUMN is_pro INTEGER DEFAULT 0",
        "ALTER TABLE channels ADD COLUMN type TEXT DEFAULT 'telegram'",
        "ALTER TABLE users ADD COLUMN referral_by INTEGER DEFAULT NULL",
        "ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0",
        "ALTER TABLE payments ADD COLUMN plan TEXT DEFAULT '1_month'",
        "ALTER TABLE subscriptions ADD COLUMN plan TEXT DEFAULT '1_month'",
    ]:
        try:
            db.execute(sql)
            db.commit()
        except Exception:
            pass

    defaults = [
        ("sub_price_1m",   "15000"),
        ("sub_price_3m",   "40000"),
        ("sub_price_1y",   "120000"),
        ("card_uzcard",    "8600 0000 0000 0000"),
        ("card_humo",      "9860 0000 0000 0000"),
        ("card_visa",      "4111 0000 0000 0000"),
        ("card_owner",     "Admin"),
        ("movie_ch",       ""),
        ("welcome_text",   "Kino kodini yuboring"),
        ("referral_bonus", "5"),
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

# ═══════ USERS ═══════════════════════════

def add_user(uid, name, uname, referral_by=None):
    db = con()
    is_new = db.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone() is None
    if is_new:
        db.execute(
            "INSERT OR IGNORE INTO users(id,name,username,referral_by) VALUES(?,?,?,?)",
            (uid, name or "", uname or "", referral_by)
        )
        if referral_by:
            db.execute(
                "UPDATE users SET referral_count=referral_count+1 WHERE id=?",
                (referral_by,)
            )
            # Referral bonus tekshirish
            bonus = int(db.execute(
                "SELECT value FROM settings WHERE key='referral_bonus'"
            ).fetchone()["value"] or "5")
            user = db.execute(
                "SELECT referral_count FROM users WHERE id=?", (referral_by,)
            ).fetchone()
            if user and user["referral_count"] % bonus == 0:
                expires = (datetime.now() + timedelta(days=30)).isoformat()
                db.execute(
                    "INSERT OR REPLACE INTO subscriptions(user_id,expires_at,plan) VALUES(?,?,?)",
                    (referral_by, expires, "referral_bonus")
                )
    db.execute("UPDATE users SET last_seen=datetime('now') WHERE id=?", (uid,))
    db.commit()
    db.close()
    return is_new

def get_user(uid):
    db = con()
    r = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return dict(r) if r else None

def all_user_ids():
    db = con()
    r = db.execute("SELECT id FROM users").fetchall()
    db.close()
    return [x["id"] for x in r]

def user_stats():
    db = con()
    def q(sql): return db.execute(sql).fetchone()["c"]
    s = {
        "total":        q("SELECT COUNT(*) as c FROM users"),
        "today":        q("SELECT COUNT(*) as c FROM users WHERE date(joined)=date('now')"),
        "week":         q("SELECT COUNT(*) as c FROM users WHERE joined>=datetime('now','-7 days')"),
        "month":        q("SELECT COUNT(*) as c FROM users WHERE joined>=datetime('now','-30 days')"),
        "act24":        q("SELECT COUNT(*) as c FROM users WHERE last_seen>=datetime('now','-1 days')"),
        "act7":         q("SELECT COUNT(*) as c FROM users WHERE last_seen>=datetime('now','-7 days')"),
        "act30":        q("SELECT COUNT(*) as c FROM users WHERE last_seen>=datetime('now','-30 days')"),
        "premium":      q("SELECT COUNT(*) as c FROM subscriptions WHERE expires_at>datetime('now')"),
        "referrals":    q("SELECT COALESCE(SUM(referral_count),0) as c FROM users"),
        "pending":      q("SELECT COUNT(*) as c FROM payments WHERE status='pending'"),
        "approved":     q("SELECT COUNT(*) as c FROM payments WHERE status='approved'"),
        "pro_movies":   q("SELECT COUNT(*) as c FROM movies WHERE is_pro=1"),
        "total_movies": q("SELECT COUNT(*) as c FROM movies"),
    }
    db.close()
    return s

# ═══════ ADMINS ══════════════════════════

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

# ═══════ MOVIES ══════════════════════════

def save_movie(code, msg_id, title="", is_pro=0):
    db = con()
    db.execute(
        "INSERT OR REPLACE INTO movies(code,msg_id,title,is_pro) VALUES(?,?,?,?)",
        (str(code).strip(), str(msg_id).strip(), title, is_pro)
    )
    db.commit()
    db.close()

def get_movie(code):
    db = con()
    r = db.execute("SELECT * FROM movies WHERE code=?", (str(code).strip(),)).fetchone()
    if r:
        db.execute("UPDATE movies SET views=views+1 WHERE code=?", (str(code).strip(),))
        db.commit()
    db.close()
    return dict(r) if r else None

def set_movie_pro(code, is_pro):
    db = con()
    db.execute("UPDATE movies SET is_pro=? WHERE code=?",
               (1 if is_pro else 0, str(code).strip()))
    db.commit()
    db.close()

def update_movie(old, new_code, new_msgid, new_title):
    db = con()
    old_m = db.execute("SELECT is_pro FROM movies WHERE code=?", (old,)).fetchone()
    is_pro = old_m["is_pro"] if old_m else 0
    db.execute("DELETE FROM movies WHERE code=?", (old,))
    db.execute("INSERT INTO movies(code,msg_id,title,is_pro) VALUES(?,?,?,?)",
               (new_code, new_msgid, new_title, is_pro))
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
    return [dict(x) for x in r]

# ═══════ CHANNELS ════════════════════════

def add_channel(channel_id, title, link, ch_type="telegram"):
    db = con()
    db.execute(
        "INSERT INTO channels(channel_id,title,link,type) VALUES(?,?,?,?)",
        (channel_id, title, link, ch_type)
    )
    db.commit()
    db.close()

def get_channels():
    db = con()
    r = db.execute("SELECT * FROM channels").fetchall()
    db.close()
    return [dict(x) for x in r]

def get_telegram_channels():
    db = con()
    r = db.execute("SELECT * FROM channels WHERE type='telegram'").fetchall()
    db.close()
    return [dict(x) for x in r]

def del_channel(row_id):
    db = con()
    n = db.execute("DELETE FROM channels WHERE id=?", (row_id,)).rowcount
    db.commit()
    db.close()
    return n > 0

# ═══════ PAYMENTS ════════════════════════

PLANS = {
    "1_month": {"days": 30,  "label": "1 Oy",  "key": "sub_price_1m"},
    "3_month": {"days": 90,  "label": "3 Oy",  "key": "sub_price_3m"},
    "1_year":  {"days": 365, "label": "1 Yil", "key": "sub_price_1y"},
}

def add_payment(uid, amount, card_type, file_id, plan="1_month"):
    db = con()
    if db.execute("SELECT id FROM payments WHERE user_id=? AND status='pending'",
                  (uid,)).fetchone():
        db.close()
        return None
    c = db.execute(
        "INSERT INTO payments(user_id,amount,card_type,file_id,plan) VALUES(?,?,?,?,?)",
        (uid, amount, card_type, file_id, plan)
    )
    pay_id = c.lastrowid
    db.commit()
    db.close()
    return pay_id

def get_payment(pay_id):
    db = con()
    r = db.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    db.close()
    return dict(r) if r else None

def resolve_payment(pay_id, status):
    db = con()
    db.execute("UPDATE payments SET status=? WHERE id=?", (status, pay_id))
    db.commit()
    db.close()

# ═══════ SUBSCRIPTION ════════════════════

def give_sub(uid, plan="1_month"):
    days = PLANS.get(plan, {"days": 30})["days"]
    db = con()
    existing = db.execute(
        "SELECT expires_at FROM subscriptions WHERE user_id=?", (uid,)
    ).fetchone()
    if existing:
        current = datetime.fromisoformat(existing["expires_at"])
        base = max(current, datetime.now())
    else:
        base = datetime.now()
    expires = (base + timedelta(days=days)).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO subscriptions(user_id,expires_at,plan) VALUES(?,?,?)",
        (uid, expires, plan)
    )
    db.commit()
    db.close()

def has_sub(uid):
    db = con()
    r = db.execute(
        "SELECT expires_at FROM subscriptions WHERE user_id=?", (uid,)
    ).fetchone()
    db.close()
    if not r: return False
    return datetime.now() < datetime.fromisoformat(r["expires_at"])

def sub_info(uid):
    db = con()
    r = db.execute("SELECT * FROM subscriptions WHERE user_id=?", (uid,)).fetchone()
    db.close()
    return dict(r) if r else None
