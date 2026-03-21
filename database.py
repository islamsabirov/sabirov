"""
database.py — PostgreSQL (psycopg2)
Render.com: DATABASE_URL environment variable ishlatiladi
"""
import os
import logging
from datetime import datetime, timedelta
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL", "")

PLANS = {
    "1_month": {"days": 30,  "label": "1 Oy",  "key": "sub_price_1m"},
    "3_month": {"days": 90,  "label": "3 Oy",  "key": "sub_price_3m"},
    "1_year":  {"days": 365, "label": "1 Yil", "key": "sub_price_1y"},
}


def con():
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url)
    return conn


def init_db():
    db = con()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id             BIGINT PRIMARY KEY,
            name           TEXT DEFAULT '',
            username       TEXT DEFAULT '',
            joined         TIMESTAMP DEFAULT NOW(),
            last_seen      TIMESTAMP DEFAULT NOW(),
            referral_by    BIGINT DEFAULT NULL,
            referral_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS admins (
            id   BIGINT PRIMARY KEY,
            name TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS movies (
            code   TEXT PRIMARY KEY,
            msg_id TEXT NOT NULL,
            title  TEXT DEFAULT '',
            views  INTEGER DEFAULT 0,
            is_pro INTEGER DEFAULT 0,
            added  TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS channels (
            id         SERIAL PRIMARY KEY,
            channel_id TEXT DEFAULT '',
            title      TEXT DEFAULT '',
            link       TEXT DEFAULT '',
            type       TEXT DEFAULT 'telegram'
        );
        CREATE TABLE IF NOT EXISTS payments (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT,
            amount     INTEGER,
            card_type  TEXT,
            file_id    TEXT,
            plan       TEXT DEFAULT '1_month',
            status     TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id    BIGINT PRIMARY KEY,
            expires_at TIMESTAMP NOT NULL,
            plan       TEXT DEFAULT '1_month'
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
    """)
    db.commit()

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
        cur.execute(
            "INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING",
            (k, v)
        )
    db.commit()
    cur.close()
    db.close()
    logging.info("PostgreSQL database tayyor")


# ═══════ SETTINGS ════════════════════════

def gs(key):
    db = con()
    cur = db.cursor()
    cur.execute("SELECT value FROM settings WHERE key=%s", (key,))
    row = cur.fetchone()
    cur.close()
    db.close()
    return row[0] if row else ""


def ss(key, val):
    db = con()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=%s",
        (key, val, val)
    )
    db.commit()
    cur.close()
    db.close()


# ═══════ USERS ═══════════════════════════

def add_user(uid, name, uname, referral_by=None):
    db = con()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE id=%s", (uid,))
    is_new = cur.fetchone() is None

    if is_new:
        cur.execute(
            "INSERT INTO users(id,name,username,referral_by) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
            (uid, name or "", uname or "", referral_by)
        )
        if referral_by:
            cur.execute(
                "UPDATE users SET referral_count=referral_count+1 WHERE id=%s",
                (referral_by,)
            )
            cur.execute("SELECT value FROM settings WHERE key='referral_bonus'")
            bonus_row = cur.fetchone()
            bonus = int(bonus_row[0]) if bonus_row else 5
            cur.execute("SELECT referral_count FROM users WHERE id=%s", (referral_by,))
            ref_row = cur.fetchone()
            if ref_row and ref_row[0] % bonus == 0:
                expires = (datetime.now() + timedelta(days=30)).isoformat()
                cur.execute(
                    "INSERT INTO subscriptions(user_id,expires_at,plan) VALUES(%s,%s,%s) "
                    "ON CONFLICT(user_id) DO UPDATE SET expires_at=%s, plan=%s",
                    (referral_by, expires, "referral_bonus", expires, "referral_bonus")
                )
    cur.execute("UPDATE users SET last_seen=NOW() WHERE id=%s", (uid,))
    db.commit()
    cur.close()
    db.close()
    return is_new


def get_user(uid):
    db = con()
    cur = db.cursor()
    cur.execute("SELECT id,name,username,referral_by,referral_count FROM users WHERE id=%s", (uid,))
    row = cur.fetchone()
    cur.close()
    db.close()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "username": row[2],
            "referral_by": row[3], "referral_count": row[4]}


def all_user_ids():
    db = con()
    cur = db.cursor()
    cur.execute("SELECT id FROM users")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [r[0] for r in rows]


def user_stats():
    db = con()
    cur = db.cursor()

    def q(sql):
        cur.execute(sql)
        return cur.fetchone()[0]

    s = {
        "total":        q("SELECT COUNT(*) FROM users"),
        "today":        q("SELECT COUNT(*) FROM users WHERE joined::date=NOW()::date"),
        "week":         q("SELECT COUNT(*) FROM users WHERE joined>=NOW()-INTERVAL'7 days'"),
        "month":        q("SELECT COUNT(*) FROM users WHERE joined>=NOW()-INTERVAL'30 days'"),
        "act24":        q("SELECT COUNT(*) FROM users WHERE last_seen>=NOW()-INTERVAL'1 day'"),
        "act7":         q("SELECT COUNT(*) FROM users WHERE last_seen>=NOW()-INTERVAL'7 days'"),
        "act30":        q("SELECT COUNT(*) FROM users WHERE last_seen>=NOW()-INTERVAL'30 days'"),
        "premium":      q("SELECT COUNT(*) FROM subscriptions WHERE expires_at>NOW()"),
        "referrals":    q("SELECT COALESCE(SUM(referral_count),0) FROM users"),
        "pending":      q("SELECT COUNT(*) FROM payments WHERE status='pending'"),
        "approved":     q("SELECT COUNT(*) FROM payments WHERE status='approved'"),
        "pro_movies":   q("SELECT COUNT(*) FROM movies WHERE is_pro=1"),
        "total_movies": q("SELECT COUNT(*) FROM movies"),
    }
    cur.close()
    db.close()
    return s


# ═══════ ADMINS ══════════════════════════

def is_admin(uid):
    from config import ADMIN_IDS
    if uid in ADMIN_IDS:
        return True
    db = con()
    cur = db.cursor()
    cur.execute("SELECT id FROM admins WHERE id=%s", (uid,))
    row = cur.fetchone()
    cur.close()
    db.close()
    return row is not None


def add_admin(uid, name):
    db = con()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO admins(id,name) VALUES(%s,%s) ON CONFLICT(id) DO UPDATE SET name=%s",
        (uid, name, name)
    )
    db.commit()
    cur.close()
    db.close()


def del_admin(uid):
    db = con()
    cur = db.cursor()
    cur.execute("DELETE FROM admins WHERE id=%s", (uid,))
    n = cur.rowcount
    db.commit()
    cur.close()
    db.close()
    return n > 0


def get_admins():
    db = con()
    cur = db.cursor()
    cur.execute("SELECT id, name FROM admins")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [{"id": r[0], "name": r[1]} for r in rows]


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
    cur = db.cursor()
    cur.execute(
        "INSERT INTO movies(code,msg_id,title,is_pro) VALUES(%s,%s,%s,%s) "
        "ON CONFLICT(code) DO UPDATE SET msg_id=%s, title=%s, is_pro=%s",
        (str(code).strip(), str(msg_id).strip(), title, is_pro,
         str(msg_id).strip(), title, is_pro)
    )
    db.commit()
    cur.close()
    db.close()


def get_movie(code):
    db = con()
    cur = db.cursor()
    cur.execute(
        "SELECT code,msg_id,title,views,is_pro FROM movies WHERE code=%s",
        (str(code).strip(),)
    )
    row = cur.fetchone()
    cur.close()
    db.close()
    if not row:
        return None
    return {"code": row[0], "msg_id": row[1], "title": row[2],
            "views": row[3], "is_pro": row[4]}


def increment_views(code):
    db = con()
    cur = db.cursor()
    cur.execute("UPDATE movies SET views=views+1 WHERE code=%s", (str(code).strip(),))
    db.commit()
    cur.close()
    db.close()


def set_movie_pro(code, is_pro):
    db = con()
    cur = db.cursor()
    cur.execute(
        "UPDATE movies SET is_pro=%s WHERE code=%s",
        (1 if is_pro else 0, str(code).strip())
    )
    db.commit()
    cur.close()
    db.close()


def update_movie(old, new_code, new_msgid, new_title):
    db = con()
    cur = db.cursor()
    cur.execute("SELECT is_pro FROM movies WHERE code=%s", (old,))
    row = cur.fetchone()
    is_pro = row[0] if row else 0
    cur.execute("DELETE FROM movies WHERE code=%s", (old,))
    cur.execute(
        "INSERT INTO movies(code,msg_id,title,is_pro) VALUES(%s,%s,%s,%s) "
        "ON CONFLICT(code) DO UPDATE SET msg_id=%s, title=%s, is_pro=%s",
        (new_code, new_msgid, new_title, is_pro,
         new_msgid, new_title, is_pro)
    )
    db.commit()
    cur.close()
    db.close()


def del_movie(code):
    db = con()
    cur = db.cursor()
    cur.execute("DELETE FROM movies WHERE code=%s", (str(code).strip(),))
    n = cur.rowcount
    db.commit()
    cur.close()
    db.close()
    return n > 0


def get_movies(limit=50, offset=0):
    db = con()
    cur = db.cursor()
    cur.execute(
        "SELECT code,msg_id,title,views,is_pro FROM movies ORDER BY added DESC LIMIT %s OFFSET %s",
        (limit, offset)
    )
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [{"code": r[0], "msg_id": r[1], "title": r[2],
             "views": r[3], "is_pro": r[4]} for r in rows]


# ═══════ CHANNELS ════════════════════════

def add_channel(channel_id, title, link, ch_type="telegram"):
    db = con()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO channels(channel_id,title,link,type) VALUES(%s,%s,%s,%s)",
        (channel_id, title, link, ch_type)
    )
    db.commit()
    cur.close()
    db.close()


def get_channels():
    db = con()
    cur = db.cursor()
    cur.execute("SELECT id,channel_id,title,link,type FROM channels")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [{"id": r[0], "channel_id": r[1], "title": r[2],
             "link": r[3], "type": r[4]} for r in rows]


def get_telegram_channels():
    db = con()
    cur = db.cursor()
    cur.execute("SELECT id,channel_id,title,link,type FROM channels WHERE type='telegram'")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [{"id": r[0], "channel_id": r[1], "title": r[2],
             "link": r[3], "type": r[4]} for r in rows]


def del_channel(row_id):
    db = con()
    cur = db.cursor()
    cur.execute("DELETE FROM channels WHERE id=%s", (row_id,))
    n = cur.rowcount
    db.commit()
    cur.close()
    db.close()
    return n > 0


# ═══════ PAYMENTS ════════════════════════

def add_payment(uid, amount, card_type, file_id, plan="1_month"):
    db = con()
    cur = db.cursor()
    cur.execute(
        "SELECT id FROM payments WHERE user_id=%s AND status='pending'", (uid,)
    )
    if cur.fetchone():
        cur.close()
        db.close()
        return None
    cur.execute(
        "INSERT INTO payments(user_id,amount,card_type,file_id,plan) VALUES(%s,%s,%s,%s,%s) RETURNING id",
        (uid, amount, card_type, file_id, plan)
    )
    pay_id = cur.fetchone()[0]
    db.commit()
    cur.close()
    db.close()
    return pay_id


def get_payment(pay_id):
    db = con()
    cur = db.cursor()
    cur.execute(
        "SELECT id,user_id,amount,card_type,file_id,plan,status FROM payments WHERE id=%s",
        (pay_id,)
    )
    row = cur.fetchone()
    cur.close()
    db.close()
    if not row:
        return None
    return {"id": row[0], "user_id": row[1], "amount": row[2],
            "card_type": row[3], "file_id": row[4],
            "plan": row[5], "status": row[6]}


def resolve_payment(pay_id, status):
    db = con()
    cur = db.cursor()
    cur.execute("UPDATE payments SET status=%s WHERE id=%s", (status, pay_id))
    db.commit()
    cur.close()
    db.close()


# ═══════ SUBSCRIPTION ════════════════════

def give_sub(uid, plan="1_month"):
    days = PLANS.get(plan, {"days": 30})["days"]
    db = con()
    cur = db.cursor()
    cur.execute("SELECT expires_at FROM subscriptions WHERE user_id=%s", (uid,))
    row = cur.fetchone()
    if row:
        current = row[0] if isinstance(row[0], datetime) else datetime.fromisoformat(str(row[0]))
        base = max(current, datetime.now())
    else:
        base = datetime.now()
    expires = (base + timedelta(days=days)).isoformat()
    cur.execute(
        "INSERT INTO subscriptions(user_id,expires_at,plan) VALUES(%s,%s,%s) "
        "ON CONFLICT(user_id) DO UPDATE SET expires_at=%s, plan=%s",
        (uid, expires, plan, expires, plan)
    )
    db.commit()
    cur.close()
    db.close()


def has_sub(uid):
    db = con()
    cur = db.cursor()
    cur.execute("SELECT expires_at FROM subscriptions WHERE user_id=%s", (uid,))
    row = cur.fetchone()
    cur.close()
    db.close()
    if not row:
        return False
    expires = row[0] if isinstance(row[0], datetime) else datetime.fromisoformat(str(row[0]))
    return datetime.now() < expires


def sub_info(uid):
    db = con()
    cur = db.cursor()
    cur.execute("SELECT user_id,expires_at,plan FROM subscriptions WHERE user_id=%s", (uid,))
    row = cur.fetchone()
    cur.close()
    db.close()
    if not row:
        return None
    return {"user_id": row[0], "expires_at": str(row[1]), "plan": row[2]}
