"""
╔══════════════════════════════════════════════════╗
║            KINO BOT v2.0 — main.py              ║
║  Barcha funksiyalar: user, admin, to'lov, kino  ║
╚══════════════════════════════════════════════════╝

FUNKSIYALAR:
✅ /start — kanal tekshirish, menyu
✅ Kino qidirish (kod yozsa → yashirin kanaldan yuboradi)
✅ Profil + oylik obuna sotib olish
✅ To'lov: UzCard / Humo / Visa — chek → admin tasdiqlash
✅ Admin panel — statistika, kino, kanal, admin, broadcast
✅ Kino yuklash / tahrirlash / o'chirish
✅ Majburiy obuna kanallar qo'shish/o'chirish
✅ Admin qo'shish/o'chirish
✅ Broadcast: oddiy matn + forward
✅ Sozlamalar: karta, narx, kino kanal, xush kelibsiz matni
✅ Render webhook + local polling
"""

import asyncio
import logging
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

import database as db
import keyboards as kb
from config import BOT_TOKEN, ADMIN_IDS, WEBHOOK_URL, PORT, MOVIE_CH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

H = ParseMode.HTML
END = ConversationHandler.END

# ══════════════════════════════════════════════════
# CONVERSATION STATES
# ══════════════════════════════════════════════════
(
    S_PAY,                          # To'lov screenshot
    S_MV_CODE, S_MV_MSGID, S_MV_TITLE,         # Kino qo'shish
    S_ED_OLD, S_ED_CODE, S_ED_MSGID, S_ED_TITLE, # Kino tahrirlash
    S_DEL,                          # Kino o'chirish
    S_CH_ID, S_CH_TITLE, S_CH_LINK, # Kanal qo'shish
    S_ADM_ADD, S_ADM_DEL,           # Admin boshqaruv
    S_BC_TEXT, S_BC_FWD,            # Broadcast
    S_ST_CARD, S_ST_PRICE, S_ST_MOVCH, S_ST_WELCOME, # Sozlamalar
) = range(20)

# ══════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════════════

async def check_subs(bot, uid):
    """Foydalanuvchi obuna bo'lmagan kanallarni qaytaradi"""
    result = []
    for ch in db.get_channels():
        try:
            m = await bot.get_chat_member(ch["channel_id"], uid)
            if m.status in ["left", "kicked"]:
                result.append(ch)
        except Exception:
            pass  # Kanal topilmasa o'tkazib yuboramiz
    return result

async def send_to_admins(ctx, text=None, photo=None, caption=None, markup=None):
    """Barcha adminlarga xabar yuborish"""
    for aid in db.all_admin_ids():
        try:
            if photo:
                await ctx.bot.send_photo(
                    aid, photo=photo, caption=caption,
                    parse_mode=H, reply_markup=markup
                )
            else:
                await ctx.bot.send_message(
                    aid, text, parse_mode=H, reply_markup=markup
                )
        except Exception:
            pass

def get_movie_ch():
    """Kino kanal ID — avval bazadan, keyin config dan"""
    ch = db.gs("movie_ch")
    return ch if ch else MOVIE_CH

async def cancel(update: Update, ctx):
    """Har qanday amaliyotni bekor qilish"""
    ctx.user_data.clear()
    if update.message:
        await update.message.reply_text("❌ Bekor qilindi.")
    return END

async def cb_cancel(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    await q.edit_message_text("❌ Bekor qilindi.")

# ══════════════════════════════════════════════════
# /start — BOSHLASH
# ══════════════════════════════════════════════════

async def cmd_start(update: Update, ctx):
    u = update.effective_user
    db.add_user(u.id, u.first_name, u.username or "")

    # Majburiy obuna tekshirish
    unsubbed = await check_subs(ctx.bot, u.id)
    if unsubbed:
        await update.message.reply_text(
            "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            "Obuna bo'lgach, <b>✅ Tekshirish</b> tugmasini bosing.",
            parse_mode=H,
            reply_markup=kb.sub_kb(unsubbed)
        )
        return

    # Admin yoki oddiy user
    if db.is_admin(u.id):
        await update.message.reply_text(
            f"👑 <b>Salom, {u.first_name}!</b>\n\n"
            f"🤖 Admin paneliga xush kelibsiz.\n"
            f"Quyidagi menyudan foydalaning 👇",
            parse_mode=H,
            reply_markup=kb.admin_kb()
        )
    else:
        welcome = db.gs("welcome_text") or "Kino kodini yuboring 🎬"
        await update.message.reply_text(
            f"🎬 <b>Salom, {u.first_name}!</b>\n\n{welcome}",
            parse_mode=H,
            reply_markup=kb.user_kb()
        )

# ── Obuna tekshirish tugmasi ──────────────
async def cb_chk_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    unsubbed = await check_subs(ctx.bot, q.from_user.id)
    if unsubbed:
        await q.answer(
            "❌ Hali obuna bo'lmadingiz!\nYuqoridagi tugmalardan kanallarga o'ting.",
            show_alert=True
        )
        return
    u = q.from_user
    await q.edit_message_text(
        "✅ <b>Obuna tasdiqlandi!</b>\n\n🎬 Kino kodini yuboring:",
        parse_mode=H
    )
    if db.is_admin(u.id):
        await ctx.bot.send_message(u.id, "👇", reply_markup=kb.admin_kb())
    else:
        await ctx.bot.send_message(u.id, "👇", reply_markup=kb.user_kb())

# ══════════════════════════════════════════════════
# USER — KINO QIDIRISH
# ══════════════════════════════════════════════════

async def msg_find_movie(update: Update, ctx):
    u = update.effective_user
    code = update.message.text.strip()

    # Obuna tekshirish
    unsubbed = await check_subs(ctx.bot, u.id)
    if unsubbed:
        await update.message.reply_text(
            "📢 Avval kanallarga obuna bo'ling!",
            reply_markup=kb.sub_kb(unsubbed)
        )
        return

    # Kinoni bazadan topish
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text(
            f"❌ <b>{code}</b> kodli kino topilmadi.\n"
            f"<i>Kodni to'g'ri yozdingizmi?</i>",
            parse_mode=H
        )
        return

    # Kino kanalidan forward qilish
    ch = get_movie_ch()
    if not ch:
        await update.message.reply_text(
            "⚠️ Kino kanal hali sozlanmagan.\n"
            "Admin bilan bog'laning."
        )
        return

    try:
        await ctx.bot.forward_message(
            chat_id=u.id,
            from_chat_id=ch,
            message_id=int(movie["msg_id"])
        )
    except TelegramError as e:
        logging.error(f"Forward xato: {e}")
        await update.message.reply_text(
            "⚠️ Kinoni yuborishda xatolik yuz berdi.\n"
            "Admin bilan bog'laning."
        )

# ══════════════════════════════════════════════════
# USER — PROFIL
# ══════════════════════════════════════════════════

async def msg_profile(update: Update, ctx):
    u = update.effective_user
    sub = db.has_sub(u.id)
    info = db.sub_info(u.id)
    price = db.gs("sub_price") or "15000"
    days = db.gs("sub_days") or "30"

    if sub and info:
        sub_text = f"✅ Faol ({info['expires_at'][:10]} gacha)"
    else:
        sub_text = "❌ Obuna yo'q"

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 Obuna sotib olish", callback_data="buy_sub")
    ]])

    await update.message.reply_text(
        f"👤 <b>Mening profilim</b>\n\n"
        f"🆔 ID: <code>{u.id}</code>\n"
        f"👤 Ism: {u.first_name}\n"
        f"💎 Obuna holati: {sub_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 {days} kunlik obuna: <b>{int(price):,} so'm</b>",
        parse_mode=H,
        reply_markup=markup
    )

# ── Yordam ───────────────────────────────
async def msg_help(update: Update, ctx):
    await update.message.reply_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "🎬 <b>Kino qidirish:</b>\n"
        "Kino kodini yuboring — bot kinoni yuboradi.\n\n"
        "💳 <b>Obuna:</b>\n"
        "👤 Profilim → Obuna sotib olish\n\n"
        "❓ <b>Muammo bo'lsa:</b>\n"
        "Admin bilan bog'laning.",
        parse_mode=H
    )

# ══════════════════════════════════════════════════
# USER — TO'LOV TIZIMI
# ══════════════════════════════════════════════════

async def cb_buy_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price = db.gs("sub_price") or "15000"
    days = db.gs("sub_days") or "30"
    await q.edit_message_text(
        f"💳 <b>Obuna sotib olish</b>\n\n"
        f"📅 Muddat: <b>{days} kun</b>\n"
        f"💰 Narx: <b>{int(price):,} so'm</b>\n\n"
        f"To'lov usulini tanlang 👇",
        parse_mode=H,
        reply_markup=kb.buy_kb()
    )

async def cb_pay_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    card_type = q.data.replace("pay_", "")
    price = db.gs("sub_price") or "15000"
    card = db.gs(f"card_{card_type}") or "Sozlanmagan"
    owner = db.gs("card_owner") or "Admin"
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}

    # Pending to'lov tekshirish
    ctx.user_data["pay_card"] = card_type

    await q.edit_message_text(
        f"💳 <b>{names.get(card_type, '')} orqali to'lov</b>\n\n"
        f"💰 To'lov summasi: <b>{int(price):,} so'm</b>\n\n"
        f"🏦 Karta raqami:\n"
        f"<code>{card}</code>\n"
        f"👤 Karta egasi: <b>{owner}</b>\n\n"
        f"📌 Qadamlar:\n"
        f"1️⃣ Yuqoridagi kartaga pul o'tkazing\n"
        f"2️⃣ To'lov chekining rasmini yuboring 👇",
        parse_mode=H,
        reply_markup=kb.back_kb("x")
    )
    return S_PAY

async def rcv_screenshot(update: Update, ctx):
    u = update.effective_user

    if not update.message.photo:
        await update.message.reply_text(
            "📸 Iltimos, to'lov chekining <b>rasmini</b> yuboring!",
            parse_mode=H
        )
        return S_PAY

    card_type = ctx.user_data.get("pay_card", "uzcard")
    price = int(db.gs("sub_price") or "15000")
    fid = update.message.photo[-1].file_id

    pay_id = db.add_payment(u.id, price, card_type, fid)
    if not pay_id:
        await update.message.reply_text(
            "⚠️ <b>Sizda kutilayotgan to'lov mavjud!</b>\n\n"
            "Admin tasdiqlashini kuting.",
            parse_mode=H,
            reply_markup=kb.user_kb()
        )
        return END

    await update.message.reply_text(
        "⏳ <b>To'lovingiz qabul qilindi!</b>\n\n"
        "Admin tez orada ko'rib chiqadi.\n"
        "Tasdiqlangach sizga xabar keladi. ✅",
        parse_mode=H,
        reply_markup=kb.user_kb()
    )

    # Adminlarga chek + tasdiqlash tugmalari yuborish
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}
    caption = (
        f"💳 <b>Yangi to'lov so'rovi!</b>\n\n"
        f"👤 Foydalanuvchi: <a href='tg://user?id={u.id}'>{u.first_name}</a>\n"
        f"🆔 ID: <code>{u.id}</code>\n"
        f"🔖 Username: @{u.username or 'yo\\'q'}\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n"
        f"🏦 Karta: <b>{names.get(card_type, card_type)}</b>\n"
        f"🔢 To'lov #: <b>{pay_id}</b>"
    )
    await send_to_admins(ctx, photo=fid, caption=caption,
                         markup=kb.pay_confirm_kb(pay_id))
    ctx.user_data.clear()
    return END

# ── Admin to'lovni tasdiqlash ─────────────
async def cb_pay_ok(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id):
        return

    pay_id = int(q.data.replace("pok_", ""))
    pay = db.get_payment(pay_id)

    if not pay or pay["status"] != "pending":
        await q.answer("⚠️ Bu to'lov allaqachon hal qilingan!", show_alert=True)
        return

    days = int(db.gs("sub_days") or "30")
    db.resolve_payment(pay_id, "approved")
    db.give_sub(pay["user_id"], days)

    await q.edit_message_caption(
        f"✅ <b>TASDIQLANDI</b>\n\n{q.message.caption}",
        parse_mode=H
    )

    try:
        await ctx.bot.send_message(
            pay["user_id"],
            f"🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n"
            f"💎 <b>{days} kunlik obuna</b> faollashtirildi!\n\n"
            f"🎬 Endi kino kodini yuboring — kinolar sizniki!",
            parse_mode=H,
            reply_markup=kb.user_kb()
        )
    except Exception:
        pass

# ── Admin to'lovni rad etish ──────────────
async def cb_pay_no(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id):
        return

    pay_id = int(q.data.replace("pno_", ""))
    pay = db.get_payment(pay_id)

    if not pay or pay["status"] != "pending":
        await q.answer("⚠️ Bu to'lov allaqachon hal qilingan!", show_alert=True)
        return

    db.resolve_payment(pay_id, "rejected")
    await q.edit_message_caption(
        f"❌ <b>BEKOR QILINDI</b>\n\n{q.message.caption}",
        parse_mode=H
    )

    try:
        await ctx.bot.send_message(
            pay["user_id"],
            "❌ <b>To'lovingiz tasdiqlanmadi.</b>\n\n"
            "Sabab: Noto'g'ri chek yoki summa.\n\n"
            "Qayta urinib ko'ring yoki admin bilan bog'laning.",
            parse_mode=H,
            reply_markup=kb.user_kb()
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════
# ADMIN — STATISTIKA
# ══════════════════════════════════════════════════

async def msg_stats(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    s = db.user_stats()
    mc = db.movie_count()
    await update.message.reply_text(
        f"📊 <b>Bot statistikasi</b>\n\n"
        f"👥 <b>Yangi foydalanuvchilar:</b>\n"
        f"• Bugun: +{s['today']} ta\n"
        f"• 7 kun: +{s['week']} ta\n"
        f"• 30 kun: +{s['month']} ta\n\n"
        f"📈 <b>Faollik:</b>\n"
        f"• Oxirgi 24 soat: {s['act24']} ta\n"
        f"• Oxirgi 7 kun: {s['act7']} ta\n"
        f"• Oxirgi 30 kun: {s['act30']} ta\n\n"
        f"🎬 <b>Kinolar soni: {mc} ta</b>\n"
        f"👤 <b>Jami foydalanuvchilar: {s['total']} ta</b>",
        parse_mode=H
    )

# ══════════════════════════════════════════════════
# ADMIN — KINOLAR BO'LIMI
# ══════════════════════════════════════════════════

async def msg_movies(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🎬 <b>Kinolar bo'limi</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H,
        reply_markup=kb.movies_kb()
    )

# ── Kino qo'shish ─────────────────────────
async def cb_mv_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kino qo'shish — 1/3</b>\n\n"
        "Kino kodini yuboring:\n"
        "<i>Masalan: 101, 202, 350</i>\n\n"
        "❌ Bekor qilish: /cancel",
        parse_mode=H
    )
    return S_MV_CODE

async def st_mv_code(update: Update, ctx):
    code = update.message.text.strip()
    existing = db.get_movie(code)
    if existing:
        await update.message.reply_text(
            f"⚠️ <b>{code}</b> kodi allaqachon mavjud!\n"
            f"Sarlavha: {existing['title'] or '—'}\n\n"
            f"Davom etsangiz, yangilanadi.\n\n"
            f"<b>Kino kanal Message ID</b> sini yuboring — 2/3:",
            parse_mode=H
        )
    else:
        await update.message.reply_text(
            f"✅ Kod: <b>{code}</b>\n\n"
            f"<b>Kino kanal Message ID</b> sini yuboring — 2/3:\n\n"
            f"💡 <i>Message ID qanday olish:</i>\n"
            f"Kino kanalida postga o'ng klik → Copy Link\n"
            f"Link oxiridagi raqam = Message ID\n"
            f"Masalan: t.me/c/1234567890/<b>45</b> → ID = <b>45</b>",
            parse_mode=H
        )
    ctx.user_data["mv_code"] = code
    return S_MV_MSGID

async def st_mv_msgid(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text(
            "❌ Message ID faqat raqamdan iborat bo'lishi kerak!\n"
            "Qayta yuboring:"
        )
        return S_MV_MSGID
    ctx.user_data["mv_msgid"] = t
    await update.message.reply_text(
        "📝 Kino sarlavhasini yuboring — 3/3:\n\n"
        "<i>O'tkazish uchun: - (tire) yuboring</i>",
        parse_mode=H
    )
    return S_MV_TITLE

async def st_mv_title(update: Update, ctx):
    title = "" if update.message.text.strip() == "-" else update.message.text.strip()
    code = ctx.user_data["mv_code"]
    msgid = ctx.user_data["mv_msgid"]
    db.save_movie(code, msgid, title)

    # Test uchun forward qilib ko'ramiz
    ch = get_movie_ch()
    test_text = ""
    if ch:
        try:
            await ctx.bot.forward_message(
                chat_id=update.effective_user.id,
                from_chat_id=ch,
                message_id=int(msgid)
            )
            test_text = "\n\n✅ Yuqorida test ko'rinishi:"
        except Exception as e:
            test_text = f"\n\n⚠️ Test xato: {e}"

    await update.message.reply_text(
        f"✅ <b>Kino qo'shildi!</b>\n\n"
        f"🔢 Kod: <code>{code}</code>\n"
        f"🆔 Message ID: <code>{msgid}</code>\n"
        f"📌 Sarlavha: {title or '—'}"
        f"{test_text}",
        parse_mode=H,
        reply_markup=kb.movies_kb()
    )
    ctx.user_data.clear()
    return END

# ── Kino tahrirlash ───────────────────────
async def cb_mv_edit(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📝 <b>Kino tahrirlash</b>\n\n"
        "Tahrirlash uchun <b>eski kino kodini</b> yuboring:\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ED_OLD

async def st_ed_old(update: Update, ctx):
    code = update.message.text.strip()
    m = db.get_movie(code)
    if not m:
        await update.message.reply_text(
            f"❌ <b>{code}</b> kodli kino topilmadi!\n"
            f"Qayta yuboring:", parse_mode=H
        )
        return S_ED_OLD
    ctx.user_data["ed_old"] = code
    await update.message.reply_text(
        f"✅ Topildi: <b>{m['title'] or code}</b>\n"
        f"Hozirgi ID: <code>{m['msg_id']}</code>\n\n"
        f"Yangi kodni yuboring (o'zgarmasa eskinisini yozing):",
        parse_mode=H
    )
    return S_ED_CODE

async def st_ed_code(update: Update, ctx):
    ctx.user_data["ed_code"] = update.message.text.strip()
    await update.message.reply_text("Yangi Message ID yuboring:")
    return S_ED_MSGID

async def st_ed_msgid(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam!")
        return S_ED_MSGID
    ctx.user_data["ed_msgid"] = t
    await update.message.reply_text("Yangi sarlavha yuboring (o'zgarmasa - yuboring):")
    return S_ED_TITLE

async def st_ed_title(update: Update, ctx):
    title = "" if update.message.text.strip() == "-" else update.message.text.strip()
    db.update_movie(
        ctx.user_data["ed_old"],
        ctx.user_data["ed_code"],
        ctx.user_data["ed_msgid"],
        title
    )
    await update.message.reply_text(
        "✅ <b>Kino yangilandi!</b>", parse_mode=H,
        reply_markup=kb.movies_kb()
    )
    ctx.user_data.clear()
    return END

# ── Kino o'chirish ────────────────────────
async def cb_mv_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🗑 <b>Kino o'chirish</b>\n\n"
        "O'chiriladigan kino kodini yuboring:\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_DEL

async def st_del(update: Update, ctx):
    code = update.message.text.strip()
    if db.del_movie(code):
        await update.message.reply_text(
            f"✅ <b>{code}</b> kodli kino o'chirildi!",
            parse_mode=H, reply_markup=kb.movies_kb()
        )
    else:
        await update.message.reply_text(
            f"❌ <b>{code}</b> kodli kino topilmadi!\n"
            f"Qayta yuboring:", parse_mode=H
        )
        return S_DEL
    return END

# ── Kinolar ro'yxati ──────────────────────
async def cb_mv_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    movies = db.get_movies(30)
    if not movies:
        await q.edit_message_text(
            "🎬 Kino bazasi hozircha bo'sh.\n"
            "Kino yuklash tugmasini bosing.",
            reply_markup=kb.movies_kb()
        )
        return
    lines = [f"📋 <b>Kinolar ro'yxati ({len(movies)} ta):</b>\n"]
    for m in movies:
        lines.append(f"🔢 <code>{m['code']}</code> | {m['title'] or '—'} | 👁 {m['views']} marta")
    await q.edit_message_text(
        "\n".join(lines), parse_mode=H,
        reply_markup=kb.back_kb("mv_back")
    )

async def cb_mv_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bo'limi</b>", parse_mode=H,
        reply_markup=kb.movies_kb()
    )

# ══════════════════════════════════════════════════
# ADMIN — KANALLAR BO'LIMI
# ══════════════════════════════════════════════════

async def msg_channels(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    chs = db.get_channels()
    count = len(chs)
    await update.message.reply_text(
        f"🔒 <b>Majburiy obuna kanallar</b>\n\n"
        f"Hozirda: <b>{count} ta</b> kanal\n\n"
        f"Quyidagi amallardan birini tanlang:",
        parse_mode=H,
        reply_markup=kb.channels_kb()
    )

async def cb_ch_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "➕ <b>Kanal qo'shish — 1/3</b>\n\n"
        "Kanal ID yuboring:\n"
        "<i>• Username: @mykanal\n"
        "• ID: -1001234567890</i>\n\n"
        "⚠️ Botni kanalga <b>admin</b> qilib qo'shishni unutmang!\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_CH_ID

async def st_ch_id(update: Update, ctx):
    ctx.user_data["ch_id"] = update.message.text.strip()
    await update.message.reply_text(
        "📌 Kanal nomini yuboring — 2/3:\n"
        "<i>Bu nom tugmada ko'rinadi</i>",
        parse_mode=H
    )
    return S_CH_TITLE

async def st_ch_title(update: Update, ctx):
    ctx.user_data["ch_title"] = update.message.text.strip()
    await update.message.reply_text(
        "🔗 Kanal havolasini yuboring — 3/3:\n"
        "<i>Masalan: https://t.me/mykanal</i>",
        parse_mode=H
    )
    return S_CH_LINK

async def st_ch_link(update: Update, ctx):
    db.add_channel(
        ctx.user_data["ch_id"],
        ctx.user_data["ch_title"],
        update.message.text.strip()
    )
    await update.message.reply_text(
        f"✅ <b>Kanal qo'shildi!</b>\n\n"
        f"🆔 ID: <code>{ctx.user_data['ch_id']}</code>\n"
        f"📌 Nom: {ctx.user_data['ch_title']}",
        parse_mode=H,
        reply_markup=kb.channels_kb()
    )
    ctx.user_data.clear()
    return END

async def cb_ch_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await q.edit_message_text(
            "📋 Hozircha kanallar yo'q.",
            reply_markup=kb.channels_kb()
        )
        return
    lines = ["📋 <b>Majburiy kanallar:</b>\n"]
    for c in chs:
        lines.append(f"🔢 <b>{c['id']}</b> | {c['title']} | <code>{c['channel_id']}</code>")
    lines.append("\n<i>O'chirish uchun: /delch [raqam]</i>")
    lines.append("<i>Masalan: /delch 1</i>")
    await q.edit_message_text(
        "\n".join(lines), parse_mode=H,
        reply_markup=kb.channels_kb()
    )

async def cb_ch_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await q.edit_message_text("❌ O'chirish uchun kanallar yo'q.", reply_markup=kb.channels_kb())
        return
    lines = ["🗑 <b>Qaysi kanalni o'chirish?</b>\n"]
    for c in chs:
        lines.append(f"🔢 <b>{c['id']}</b> | {c['title']}")
    lines.append("\n<i>/delch [raqam] yuboring\nMasalan: /delch 1</i>")
    await q.edit_message_text("\n".join(lines), parse_mode=H, reply_markup=kb.channels_kb())

async def cmd_delch(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text(
            "❌ Format: /delch 1\n"
            "<i>Raqamni /kanallar ro'yxatidan ko'ring</i>",
            parse_mode=H
        )
        return
    if db.del_channel(int(ctx.args[0])):
        await update.message.reply_text("✅ Kanal o'chirildi!", reply_markup=kb.channels_kb())
    else:
        await update.message.reply_text("❌ Kanal topilmadi. Raqamni tekshiring.")

# ══════════════════════════════════════════════════
# ADMIN — ADMINLAR BO'LIMI
# ══════════════════════════════════════════════════

async def msg_admins(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "👮 <b>Adminlar bo'limi</b>\n\n"
        "Bu yerda yangi admin qo'shish yoki\n"
        "mavjud adminlarni boshqarish mumkin.",
        parse_mode=H,
        reply_markup=kb.admins_kb()
    )

async def cb_adm_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "➕ <b>Admin qo'shish</b>\n\n"
        "Yangi admin <b>Telegram ID</b> sini yuboring:\n\n"
        "💡 ID olish usuli:\n"
        "1. @userinfobot ga /start yuboring\n"
        "2. Yoki @JsonDumpBot ga forward qiling\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ADM_ADD

async def st_adm_add(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam (Telegram ID)!\nQayta yuboring:")
        return S_ADM_ADD
    uid = int(t)
    if uid in ADMIN_IDS:
        await update.message.reply_text("⚠️ Bu asosiy admin — o'zgartirish mumkin emas!")
        return END
    db.add_admin(uid, f"Admin {uid}")
    await update.message.reply_text(
        f"✅ <code>{uid}</code> admin sifatida qo'shildi!",
        parse_mode=H, reply_markup=kb.admins_kb()
    )
    try:
        await ctx.bot.send_message(uid, "👑 Siz admin qilib tayinlandingiz!")
    except Exception:
        pass
    return END

async def cb_adm_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "➖ <b>Adminni o'chirish</b>\n\n"
        "O'chiriladigan admin <b>Telegram ID</b> sini yuboring:\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ADM_DEL

async def st_adm_del(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam!\nQayta yuboring:")
        return S_ADM_DEL
    uid = int(t)
    if uid in ADMIN_IDS:
        await update.message.reply_text("❌ Asosiy adminni o'chirib bo'lmaydi!")
        return END
    if db.del_admin(uid):
        await update.message.reply_text(
            f"✅ <code>{uid}</code> admin o'chirildi!",
            parse_mode=H, reply_markup=kb.admins_kb()
        )
    else:
        await update.message.reply_text("❌ Bu ID admin ro'yxatida yo'q.")
    return END

async def cb_adm_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    lines = ["📋 <b>Adminlar ro'yxati:</b>\n"]
    for aid in ADMIN_IDS:
        lines.append(f"👑 <code>{aid}</code> — Asosiy admin")
    for a in db.get_admins():
        lines.append(f"👮 <code>{a['id']}</code> — {a['name']}")
    await q.edit_message_text("\n".join(lines), parse_mode=H, reply_markup=kb.admins_kb())

# ══════════════════════════════════════════════════
# ADMIN — BROADCAST
# ══════════════════════════════════════════════════

async def msg_broadcast(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    users_count = len(db.all_user_ids())
    await update.message.reply_text(
        f"📨 <b>Xabar yuborish</b>\n\n"
        f"👤 Jami foydalanuvchilar: <b>{users_count} ta</b>\n\n"
        f"Xabar turini tanlang:",
        parse_mode=H,
        reply_markup=kb.broadcast_kb()
    )

async def cb_bc_text(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💬 <b>Oddiy matn broadcast</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan\n"
        "xabarni yozing:\n\n"
        "<i>HTML formatting ishlaydi:\n"
        "<b>qalin</b>, <i>kursiv</i>, <code>kod</code></i>\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_BC_TEXT

async def cb_bc_fwd(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📨 <b>Forward broadcast</b>\n\n"
        "Forward qilinadigan xabarni yuboring:\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_BC_FWD

async def st_bc_text(update: Update, ctx):
    text = update.message.text
    users = db.all_user_ids()
    sent = failed = 0
    msg = await update.message.reply_text(f"📨 Yuborilmoqda: 0/{len(users)}")
    for i, uid in enumerate(users):
        try:
            await ctx.bot.send_message(uid, text, parse_mode=H)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try:
                await msg.edit_text(f"📨 Yuborilmoqda: {i+1}/{len(users)}")
            except Exception:
                pass
        await asyncio.sleep(0.04)
    await msg.edit_text(
        f"✅ <b>Broadcast tugadi!</b>\n\n"
        f"📨 Yuborildi: {sent} ta\n"
        f"❌ Xatolik: {failed} ta",
        parse_mode=H
    )
    return END

async def st_bc_fwd(update: Update, ctx):
    users = db.all_user_ids()
    sent = failed = 0
    msg = await update.message.reply_text(f"📨 Forward: 0/{len(users)}")
    for i, uid in enumerate(users):
        try:
            await update.message.forward(uid)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try:
                await msg.edit_text(f"📨 Forward: {i+1}/{len(users)}")
            except Exception:
                pass
        await asyncio.sleep(0.04)
    await msg.edit_text(
        f"✅ <b>Forward tugadi!</b>\n\n"
        f"📨 Yuborildi: {sent} ta\n"
        f"❌ Xatolik: {failed} ta",
        parse_mode=H
    )
    return END

# ══════════════════════════════════════════════════
# ADMIN — SOZLAMALAR
# ══════════════════════════════════════════════════

async def msg_settings(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    price   = db.gs("sub_price") or "15000"
    days    = db.gs("sub_days")  or "30"
    movch   = db.gs("movie_ch")  or MOVIE_CH or "❌ Sozlanmagan"
    uzcard  = db.gs("card_uzcard") or "❌ Sozlanmagan"
    humo    = db.gs("card_humo")   or "❌ Sozlanmagan"
    visa    = db.gs("card_visa")   or "❌ Sozlanmagan"
    owner   = db.gs("card_owner")  or "❌ Sozlanmagan"
    welcome = db.gs("welcome_text") or "—"

    await update.message.reply_text(
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"💰 <b>Obuna:</b> {int(price):,} so'm / {days} kun\n"
        f"🎬 <b>Kino kanal:</b> <code>{movch}</code>\n\n"
        f"💳 <b>UzCard:</b> <code>{uzcard}</code>\n"
        f"💳 <b>Humo:</b> <code>{humo}</code>\n"
        f"💳 <b>Visa:</b> <code>{visa}</code>\n"
        f"👤 <b>Karta egasi:</b> {owner}\n\n"
        f"📝 <b>Xush kelibsiz:</b>\n<i>{welcome}</i>",
        parse_mode=H,
        reply_markup=kb.settings_kb()
    )

# ── Karta sozlamalari ─────────────────────
async def cb_st_cards(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💳 <b>Karta sozlamalari</b>\n\nQaysi kartani sozlamoqchisiz?",
        parse_mode=H,
        reply_markup=kb.cards_kb()
    )

async def cb_sc_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    key = q.data.replace("sc_", "")
    ctx.user_data["st_key"] = f"card_{key}"
    names = {
        "uzcard": "UzCard raqami (16 raqam)",
        "humo":   "Humo raqami (16 raqam)",
        "visa":   "Visa raqami (16 raqam)",
        "owner":  "Karta egasining ismi"
    }
    await q.edit_message_text(
        f"✏️ <b>Yangi {names.get(key, key)} ni yuboring:</b>\n\n"
        f"❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_CARD

async def st_save_card(update: Update, ctx):
    db.ss(ctx.user_data["st_key"], update.message.text.strip())
    await update.message.reply_text("✅ Saqlandi!", reply_markup=kb.settings_kb())
    ctx.user_data.clear()
    return END

async def cb_st_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💳 <b>Karta sozlamalari</b>",
        parse_mode=H, reply_markup=kb.cards_kb()
    )

# ── Obuna narxi ───────────────────────────
async def cb_st_price(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price = db.gs("sub_price") or "15000"
    days  = db.gs("sub_days")  or "30"
    await q.edit_message_text(
        f"💰 <b>Obuna narxi/muddat</b>\n\n"
        f"Hozirgi: <b>{int(price):,} so'm / {days} kun</b>\n\n"
        f"Yangi narxni yuboring (faqat raqam, so'mda):\n"
        f"<i>Masalan: 15000</i>\n\n"
        f"❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_PRICE

async def st_save_price(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam yuboring!\nMasalan: 15000")
        return S_ST_PRICE
    db.ss("sub_price", t)
    await update.message.reply_text(
        f"✅ Narx <b>{int(t):,} so'm</b> qilib saqlandi!\n\n"
        f"Kunni ham o'zgartirasizmi? (raqam yuboring, o'zgarmasa - yuboring):",
        parse_mode=H
    )
    ctx.user_data["wait_days"] = True
    return S_ST_PRICE

async def st_save_days(update: Update, ctx):
    t = update.message.text.strip()
    if ctx.user_data.get("wait_days"):
        if t != "-" and t.isdigit():
            db.ss("sub_days", t)
            await update.message.reply_text(
                f"✅ Muddat <b>{t} kun</b> qilib saqlandi!",
                parse_mode=H, reply_markup=kb.settings_kb()
            )
        else:
            await update.message.reply_text("✅ Muddat o'zgarmadi.", reply_markup=kb.settings_kb())
        ctx.user_data.clear()
        return END
    return END

# ── Kino kanal ────────────────────────────
async def cb_st_movch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("movie_ch") or MOVIE_CH or "Sozlanmagan"
    await q.edit_message_text(
        f"🎬 <b>Kino kanal ID</b>\n\n"
        f"Hozirgi: <code>{cur}</code>\n\n"
        f"Yangi kanal ID yuboring:\n"
        f"<i>Masalan: -1001234567890</i>\n\n"
        f"💡 Kanal ID olish:\n"
        f"@JsonDumpBot ga kanaldan forward qiling\n\n"
        f"⚠️ Botni kanalga <b>admin</b> qilib qo'shing!\n\n"
        f"❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_MOVCH

async def st_save_movch(update: Update, ctx):
    val = update.message.text.strip()
    db.ss("movie_ch", val)
    await update.message.reply_text(
        f"✅ Kino kanal saqlandi!\n<code>{val}</code>",
        parse_mode=H, reply_markup=kb.settings_kb()
    )
    return END

# ── Xush kelibsiz matni ───────────────────
async def cb_st_welcome(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("welcome_text") or "—"
    await q.edit_message_text(
        f"📝 <b>Xush kelibsiz matni</b>\n\n"
        f"Hozirgi:\n<i>{cur}</i>\n\n"
        f"Yangi matnni yuboring:\n"
        f"<i>(HTML formatting ishlaydi)</i>\n\n"
        f"❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_WELCOME

async def st_save_welcome(update: Update, ctx):
    db.ss("welcome_text", update.message.text.strip())
    await update.message.reply_text("✅ Xush kelibsiz matni saqlandi!", reply_markup=kb.settings_kb())
    return END

# ══════════════════════════════════════════════════
# UMUMIY
# ══════════════════════════════════════════════════

async def msg_orqaga(update: Update, ctx):
    await cmd_start(update, ctx)

# ══════════════════════════════════════════════════
# MAIN — BOT ISHGA TUSHIRISH
# ══════════════════════════════════════════════════

def main():
    db.init_db()
    logging.info("✅ Database tayyor")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Conversations ──────────────────────────────
    # To'lov
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_pay_card, pattern="^pay_(uzcard|humo|visa)$")],
        states={S_PAY: [MessageHandler(filters.PHOTO, rcv_screenshot)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # Kino qo'shish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mv_add, pattern="^mv_add$")],
        states={
            S_MV_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_code)],
            S_MV_MSGID: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_msgid)],
            S_MV_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # Kino tahrirlash
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mv_edit, pattern="^mv_edit$")],
        states={
            S_ED_OLD:   [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ed_old)],
            S_ED_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ed_code)],
            S_ED_MSGID: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ed_msgid)],
            S_ED_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ed_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # Kino o'chirish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mv_del, pattern="^mv_del$")],
        states={S_DEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_del)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # Kanal qo'shish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_ch_add, pattern="^ch_add$")],
        states={
            S_CH_ID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_id)],
            S_CH_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_title)],
            S_CH_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # Admin qo'shish/o'chirish
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_adm_add, pattern="^adm_add$"),
            CallbackQueryHandler(cb_adm_del, pattern="^adm_del$"),
        ],
        states={
            S_ADM_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_adm_add)],
            S_ADM_DEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_adm_del)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # Broadcast
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_bc_text, pattern="^bc_text$"),
            CallbackQueryHandler(cb_bc_fwd,  pattern="^bc_fwd$"),
        ],
        states={
            S_BC_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_bc_text)],
            S_BC_FWD:  [MessageHandler(filters.ALL  & ~filters.COMMAND, st_bc_fwd)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # Sozlamalar
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_sc_card,    pattern="^sc_(uzcard|humo|visa|owner)$"),
            CallbackQueryHandler(cb_st_price,   pattern="^st_price$"),
            CallbackQueryHandler(cb_st_movch,   pattern="^st_movch$"),
            CallbackQueryHandler(cb_st_welcome, pattern="^st_welcome$"),
        ],
        states={
            S_ST_CARD:    [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_card)],
            S_ST_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_price),
                           MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_days)],
            S_ST_MOVCH:   [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_movch)],
            S_ST_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_welcome)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    ))

    # ── Commands ───────────────────────────────────
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("admin",  cmd_start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("delch",  cmd_delch))

    # ── Callback queries ───────────────────────────
    app.add_handler(CallbackQueryHandler(cb_chk_sub,  pattern="^chk_sub$"))
    app.add_handler(CallbackQueryHandler(cb_buy_sub,  pattern="^buy_sub$"))
    app.add_handler(CallbackQueryHandler(cb_pay_ok,   pattern=r"^pok_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_no,   pattern=r"^pno_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mv_list,  pattern="^mv_list$"))
    app.add_handler(CallbackQueryHandler(cb_mv_back,  pattern="^mv_back$"))
    app.add_handler(CallbackQueryHandler(cb_ch_list,  pattern="^ch_list$"))
    app.add_handler(CallbackQueryHandler(cb_ch_del,   pattern="^ch_del$"))
    app.add_handler(CallbackQueryHandler(cb_adm_list, pattern="^adm_list$"))
    app.add_handler(CallbackQueryHandler(cb_st_cards, pattern="^st_cards$"))
    app.add_handler(CallbackQueryHandler(cb_st_back,  pattern="^st_back$"))
    app.add_handler(CallbackQueryHandler(cb_cancel,   pattern="^x$"))

    # ── Admin menyu tugmalari ──────────────────────
    app.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"),      msg_stats))
    app.add_handler(MessageHandler(filters.Regex("^📨 Xabar yuborish$"),  msg_broadcast))
    app.add_handler(MessageHandler(filters.Regex("^🎬 Kinolar$"),          msg_movies))
    app.add_handler(MessageHandler(filters.Regex("^🔒 Kanallar$"),         msg_channels))
    app.add_handler(MessageHandler(filters.Regex("^👮 Adminlar$"),         msg_admins))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Sozlamalar$"),       msg_settings))
    app.add_handler(MessageHandler(filters.Regex("^◀️ Orqaga$"),           msg_orqaga))

    # ── User tugmalari ─────────────────────────────
    app.add_handler(MessageHandler(filters.Regex("^👤 Profilim$"),         msg_profile))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yordam$"),           msg_help))
    app.add_handler(MessageHandler(filters.Regex("^🎬 Kino qidirish$"),
        lambda u, c: u.message.reply_text("🎬 Kino kodini yuboring:")))

    # ── Raqam yuborganda kino qidirish ────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d+$"),
        msg_find_movie
    ))

    # ── Ishga tushirish ────────────────────────────
    if os.environ.get("RENDER") == "true":
        logging.info("🚀 Webhook rejimida (Render)...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        logging.info("🔄 Polling rejimida (local test)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
