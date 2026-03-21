from telegram import (
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as IKM,
    ReplyKeyboardMarkup as RKM,
    KeyboardButton as KB
)

# ═══════════════════════════════
# USER
# ═══════════════════════════════

def user_kb():
    return RKM([
        [KB("🎬 Kino qidirish")],
        [KB("👤 Profilim"), KB("ℹ️ Yordam")],
    ], resize_keyboard=True)

def sub_kb(channels):
    """Obuna bo'lmagan kanallar uchun tugmalar"""
    btns = []
    for c in channels:
        ch_type = c.get("type", "telegram")
        if ch_type == "link":
            # Oddiy havola — faqat tugma
            btns.append([Btn(f"🌐 {c['title']}", url=c["link"])])
        elif ch_type == "private":
            btns.append([Btn(f"🔒 {c['title']}", url=c["link"])])
        else:
            # Telegram kanal/guruh
            btns.append([Btn(f"📢 {c['title']}", url=c["link"])])
    btns.append([Btn("✅ Obuna boldim — Tekshirish", callback_data="chk_sub")])
    return IKM(btns)

def buy_kb():
    return IKM([
        [Btn("💳 UzCard", callback_data="pay_uzcard"),
         Btn("💳 Humo",   callback_data="pay_humo")],
        [Btn("💳 Visa/MasterCard", callback_data="pay_visa")],
        [Btn("❌ Bekor", callback_data="x")],
    ])

# ═══════════════════════════════
# ADMIN
# ═══════════════════════════════

def admin_kb():
    return RKM([
        [KB("📊 Statistika"),     KB("📨 Xabar yuborish")],
        [KB("🎬 Kinolar"),        KB("🔒 Kanallar")],
        [KB("👮 Adminlar"),       KB("⚙️ Sozlamalar")],
        [KB("◀️ Orqaga")],
    ], resize_keyboard=True)

def movies_kb():
    return IKM([
        [Btn("🎬 Kino yuklash",    callback_data="mv_add")],
        [Btn("📝 Kino tahrirlash", callback_data="mv_edit"),
         Btn("🗑 Kino ochirish",   callback_data="mv_del")],
        [Btn("📋 Kinolar royxati", callback_data="mv_list")],
    ])

def channels_kb():
    return IKM([
        [Btn("➕ Kanal qoshish",    callback_data="ch_add")],
        [Btn("📋 Royxatni korish",  callback_data="ch_list")],
        [Btn("🗑 Kanalni ochirish", callback_data="ch_del")],
    ])

def channel_type_kb():
    """Kanal turi tanlash"""
    return IKM([
        [Btn("📢 Ommaviy / Shaxsiy (Kanal · Guruh)", callback_data="cht_telegram")],
        [Btn("🔒 Shaxsiy / Sorovli havola",           callback_data="cht_private")],
        [Btn("🌐 Oddiy havola",                        callback_data="cht_link")],
        [Btn("◀️ Orqaga",                              callback_data="ch_back")],
    ])

def channel_add_method_kb():
    """Kanal qoshish usuli"""
    return IKM([
        [Btn("1️⃣ ID orqali ulash",    callback_data="chm_id")],
        [Btn("2️⃣ Havola orqali ulash", callback_data="chm_link")],
        [Btn("3️⃣ Postni ulash orqali", callback_data="chm_post")],
        [Btn("◀️ Orqaga",              callback_data="ch_add")],
    ])

def channel_list_kb(channels):
    """Kanallar royxati — har birini ochirish tugmasi bilan"""
    btns = []
    icons = {"telegram": "📢", "private": "🔒", "link": "🌐"}
    for c in channels:
        icon = icons.get(c.get("type", "telegram"), "📢")
        btns.append([Btn(f"{icon} {c['title']}", callback_data=f"dch_{c['id']}")])
    btns.append([Btn("◀️ Orqaga", callback_data="ch_back")])
    return IKM(btns)

def channel_del_list_kb(channels):
    """O'chirish uchun ro'yxat"""
    btns = []
    icons = {"telegram": "📢", "private": "🔒", "link": "🌐"}
    for c in channels:
        icon = icons.get(c.get("type", "telegram"), "📢")
        btns.append([Btn(f"🗑 {icon} {c['title']}", callback_data=f"dch_{c['id']}")])
    btns.append([Btn("◀️ Orqaga", callback_data="ch_back")])
    return IKM(btns)

def admins_kb():
    return IKM([
        [Btn("➕ Admin qoshish",    callback_data="adm_add")],
        [Btn("➖ Adminni ochirish", callback_data="adm_del")],
        [Btn("📋 Adminlar royxati", callback_data="adm_list")],
    ])

def settings_kb():
    return IKM([
        [Btn("💳 Karta sozlamalari",  callback_data="st_cards")],
        [Btn("💰 Obuna narxi/muddat", callback_data="st_price")],
        [Btn("🎬 Kino kanal ID",      callback_data="st_movch")],
        [Btn("📝 Xush kelibsiz matni",callback_data="st_welcome")],
    ])

def cards_kb():
    return IKM([
        [Btn("💳 UzCard raqami", callback_data="sc_uzcard")],
        [Btn("💳 Humo raqami",   callback_data="sc_humo")],
        [Btn("💳 Visa raqami",   callback_data="sc_visa")],
        [Btn("👤 Karta egasi",   callback_data="sc_owner")],
        [Btn("◀️ Orqaga",        callback_data="st_back")],
    ])

def broadcast_kb():
    return IKM([
        [Btn("💬 Oddiy matn", callback_data="bc_text"),
         Btn("📨 Forward",    callback_data="bc_fwd")],
        [Btn("❌ Bekor",       callback_data="x")],
    ])

def pay_confirm_kb(pay_id):
    return IKM([[
        Btn("✅ Tasdiqlash",   callback_data=f"pok_{pay_id}"),
        Btn("❌ Bekor qilish", callback_data=f"pno_{pay_id}"),
    ]])

def back_kb(cb="x"):
    return IKM([[Btn("◀️ Orqaga", callback_data=cb)]])
