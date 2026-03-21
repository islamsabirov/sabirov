from telegram import (
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as IKM,
    ReplyKeyboardMarkup as RKM,
    KeyboardButton as KB
)

# ═══════ USER ════════════════════════════

def user_kb():
    return RKM([
        [KB("🎬 Kino qidirish")],
        [KB("👤 Profilim"), KB("👥 Referral")],
        [KB("ℹ️ Yordam")],
    ], resize_keyboard=True)

def sub_kb(channels):
    btns = []
    for c in channels:
        ch_type = c.get("type", "telegram")
        if ch_type == "link":
            btns.append([Btn(f"🌐 {c['title']}", url=c["link"])])
        elif ch_type == "private":
            btns.append([Btn(f"🔒 {c['title']}", url=c["link"])])
        else:
            btns.append([Btn(f"📢 {c['title']}", url=c["link"])])
    btns.append([Btn("Obuna boldim — Tekshirish", callback_data="chk_sub")])
    return IKM(btns)

def plan_kb():
    """Premium tariflar"""
    return IKM([
        [Btn("📅 1 Oy",  callback_data="plan_1_month")],
        [Btn("📅 3 Oy",  callback_data="plan_3_month")],
        [Btn("📅 1 Yil", callback_data="plan_1_year")],
        [Btn("Bekor", callback_data="x")],
    ])

def buy_kb():
    return IKM([
        [Btn("UzCard", callback_data="pay_uzcard"),
         Btn("Humo",   callback_data="pay_humo")],
        [Btn("Visa/MasterCard", callback_data="pay_visa")],
        [Btn("Orqaga", callback_data="back_to_plans")],
    ])

# ═══════ ADMIN ════════════════════════════

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
        [Btn("💎 Pro boshqaruv",   callback_data="mv_pro")],
        [Btn("📋 Kinolar royxati", callback_data="mv_list")],
    ])

def pro_manage_kb():
    return IKM([
        [Btn("Pro qilish",    callback_data="mv_set_pro")],
        [Btn("Oddiy qilish",  callback_data="mv_unset_pro")],
        [Btn("Orqaga",        callback_data="mv_back")],
    ])

def channels_kb():
    return IKM([
        [Btn("Kanal qoshish",    callback_data="ch_add")],
        [Btn("Royxatni korish",  callback_data="ch_list")],
        [Btn("Kanalni ochirish", callback_data="ch_del")],
    ])

def channel_type_kb():
    return IKM([
        [Btn("📢 Ommaviy / Shaxsiy (Kanal / Guruh)", callback_data="cht_telegram")],
        [Btn("🔒 Shaxsiy / Sorovli havola",           callback_data="cht_private")],
        [Btn("🌐 Oddiy havola",                        callback_data="cht_link")],
        [Btn("Orqaga",                                 callback_data="ch_back")],
    ])

def channel_list_kb(channels):
    icons = {"telegram": "📢", "private": "🔒", "link": "🌐"}
    btns = []
    for c in channels:
        icon = icons.get(c.get("type", "telegram"), "📢")
        btns.append([Btn(f"{icon} {c['title']}", callback_data=f"dch_{c['id']}")])
    btns.append([Btn("Orqaga", callback_data="ch_back")])
    return IKM(btns)

def channel_del_list_kb(channels):
    icons = {"telegram": "📢", "private": "🔒", "link": "🌐"}
    btns = []
    for c in channels:
        icon = icons.get(c.get("type", "telegram"), "📢")
        btns.append([Btn(f"🗑 {icon} {c['title']}", callback_data=f"dch_{c['id']}")])
    btns.append([Btn("Orqaga", callback_data="ch_back")])
    return IKM(btns)

def admins_kb():
    return IKM([
        [Btn("Admin qoshish",    callback_data="adm_add")],
        [Btn("Adminni ochirish", callback_data="adm_del")],
        [Btn("Adminlar royxati", callback_data="adm_list")],
    ])

def settings_kb():
    return IKM([
        [Btn("Karta sozlamalari",   callback_data="st_cards")],
        [Btn("Obuna narxlari",      callback_data="st_prices")],
        [Btn("Kino kanal ID",       callback_data="st_movch")],
        [Btn("Xush kelibsiz matni", callback_data="st_welcome")],
        [Btn("Referral bonus",      callback_data="st_refbonus")],
    ])

def cards_kb():
    return IKM([
        [Btn("UzCard raqami", callback_data="sc_uzcard")],
        [Btn("Humo raqami",   callback_data="sc_humo")],
        [Btn("Visa raqami",   callback_data="sc_visa")],
        [Btn("Karta egasi",   callback_data="sc_owner")],
        [Btn("Orqaga",        callback_data="st_back")],
    ])

def prices_kb():
    return IKM([
        [Btn("1 Oy narxi",  callback_data="sp_1_month")],
        [Btn("3 Oy narxi",  callback_data="sp_3_month")],
        [Btn("1 Yil narxi", callback_data="sp_1_year")],
        [Btn("Orqaga",      callback_data="st_back")],
    ])

def broadcast_kb():
    return IKM([
        [Btn("Oddiy matn", callback_data="bc_text"),
         Btn("Forward",    callback_data="bc_fwd")],
        [Btn("Bekor",      callback_data="x")],
    ])

def pay_confirm_kb(pay_id):
    return IKM([[
        Btn("Tasdiqlash",   callback_data=f"pok_{pay_id}"),
        Btn("Bekor qilish", callback_data=f"pno_{pay_id}"),
    ]])

def back_kb(cb="x"):
    return IKM([[Btn("Orqaga", callback_data=cb)]])
