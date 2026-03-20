from telegram import (InlineKeyboardButton as Btn, InlineKeyboardMarkup as IKM,
                      ReplyKeyboardMarkup as RKM, KeyboardButton as KB)

# ══════ USER ══════════════════════════════
def user_kb():
    return RKM([
        [KB("🎬 Kino qidirish")],
        [KB("👤 Profilim"), KB("ℹ️ Yordam")],
    ], resize_keyboard=True)

def sub_kb(channels):
    btns = [[Btn(f"📢 {c['title']}", url=c["link"])] for c in channels]
    btns.append([Btn("✅ Obuna bo'ldim — Tekshirish", callback_data="chk_sub")])
    return IKM(btns)

def buy_kb():
    return IKM([
        [Btn("💳 UzCard",          callback_data="pay_uzcard"),
         Btn("💳 Humo",            callback_data="pay_humo")],
        [Btn("💳 Visa/MasterCard", callback_data="pay_visa")],
        [Btn("❌ Bekor",            callback_data="x")],
    ])

# ══════ ADMIN ═════════════════════════════
def admin_kb():
    return RKM([
        [KB("📊 Statistika"),      KB("📨 Xabar yuborish")],
        [KB("🎬 Kinolar"),         KB("🔒 Kanallar")],
        [KB("👮 Adminlar"),        KB("⚙️ Sozlamalar")],
        [KB("◀️ Orqaga")],
    ], resize_keyboard=True)

def movies_kb():
    return IKM([
        [Btn("🎬 Kino yuklash",     callback_data="mv_add")],
        [Btn("📝 Kino tahrirlash",  callback_data="mv_edit"),
         Btn("🗑 Kino o'chirish",   callback_data="mv_del")],
        [Btn("📋 Kinolar ro'yxati", callback_data="mv_list")],
    ])

def channels_kb():
    return IKM([
        [Btn("➕ Kanal qo'shish",    callback_data="ch_add")],
        [Btn("📋 Ro'yxatni ko'rish", callback_data="ch_list")],
        [Btn("🗑 Kanalni o'chirish",  callback_data="ch_del")],
    ])

def admins_kb():
    return IKM([
        [Btn("➕ Admin qo'shish",    callback_data="adm_add")],
        [Btn("➖ Adminni o'chirish",  callback_data="adm_del")],
        [Btn("📋 Adminlar ro'yxati", callback_data="adm_list")],
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
        [Btn("🔙 Orqaga",        callback_data="st_back")],
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
    return IKM([[Btn("🔙 Orqaga", callback_data=cb)]])
