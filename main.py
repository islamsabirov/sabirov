"""
KINO BOT v4.0 — main.py
3 tur majburiy obuna tizimi bilan
"""
import asyncio
import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

import database as db
import keyboards as kb
from config import BOT_TOKEN, ADMIN_IDS, WEBHOOK_URL, PORT, MOVIE_CH

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
H = ParseMode.HTML
END = ConversationHandler.END

# ═══════════════════════════════
# STATES
# ═══════════════════════════════
(
    S_PAY,
    S_MV_CODE, S_MV_MSGID, S_MV_TITLE,
    S_ED_OLD, S_ED_CODE, S_ED_MSGID, S_ED_TITLE,
    S_DEL,
    S_CH_ID, S_CH_TITLE, S_CH_LINK,
    S_ADM_ADD, S_ADM_DEL,
    S_BC_TEXT, S_BC_FWD,
    S_ST_CARD, S_ST_PRICE, S_ST_MOVCH, S_ST_WELCOME,
) = range(20)

# Kanal turi saqlash uchun
CH_TYPE_KEY = "ch_type"

# ═══════════════════════════════
# YORDAMCHILAR
# ═══════════════════════════════

async def check_subs(bot, uid):
    """Faqat Telegram kanallarni tekshiradi"""
    result = []
    # Avval faqat Telegram kanallarni tekshir
    telegram_chs = db.get_telegram_channels()
    for ch in telegram_chs:
        try:
            m = await bot.get_chat_member(ch["channel_id"], uid)
            if m.status in ["left", "kicked"]:
                result.append(ch)
        except Exception:
            pass
    return result

async def get_all_unsub_channels(bot, uid):
    """Barcha ko'rinadigan kanallar (Telegram + private + link)"""
    unsubbed = await check_subs(bot, uid)
    # Private va link turlar har doim ko'rsatiladi (tekshirib bo'lmaydi)
    all_chs = db.get_channels()
    shown = list(unsubbed)
    shown_ids = [c["id"] for c in unsubbed]
    for ch in all_chs:
        if ch["type"] in ("private", "link") and ch["id"] not in shown_ids:
            shown.append(ch)
    return shown

async def send_to_admins(ctx, text=None, photo=None, caption=None, markup=None):
    for aid in db.all_admin_ids():
        try:
            if photo:
                await ctx.bot.send_photo(aid, photo=photo, caption=caption,
                                          parse_mode=H, reply_markup=markup)
            else:
                await ctx.bot.send_message(aid, text, parse_mode=H, reply_markup=markup)
        except Exception:
            pass

def get_movie_ch():
    ch = db.gs("movie_ch")
    return ch if ch else MOVIE_CH

async def cancel(update: Update, ctx):
    ctx.user_data.clear()
    if update.message:
        mkb = kb.admin_kb() if db.is_admin(update.effective_user.id) else kb.user_kb()
        await update.message.reply_text("Bekor qilindi.", reply_markup=mkb)
    return END

async def cb_cancel(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    await q.edit_message_text("Bekor qilindi.")

# ═══════════════════════════════
# START
# ═══════════════════════════════

async def cmd_start(update: Update, ctx):
    u = update.effective_user
    db.add_user(u.id, u.first_name, u.username or "")

    # Telegram kanallarni tekshir
    unsubbed = await check_subs(ctx.bot, u.id)

    if unsubbed or _has_non_telegram_channels():
        # Barcha kanallarni ko'rsat
        all_channels = await get_all_unsub_channels(ctx.bot, u.id)
        if all_channels:
            await update.message.reply_text(
                "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna boling:</b>\n\n"
                "Obuna bolgach Tekshirish tugmasini bosing.",
                parse_mode=H, reply_markup=kb.sub_kb(all_channels)
            )
            return

    if db.is_admin(u.id):
        await update.message.reply_text(
            f"👑 <b>Salom, {u.first_name}!</b>\n\n"
            f"Admin paneliga xush kelibsiz.",
            parse_mode=H, reply_markup=kb.admin_kb()
        )
    else:
        welcome = db.gs("welcome_text") or "Kino kodini yuboring"
        await update.message.reply_text(
            f"🎬 <b>Salom, {u.first_name}!</b>\n\n{welcome}",
            parse_mode=H, reply_markup=kb.user_kb()
        )

def _has_non_telegram_channels():
    """Private va link kanallar bormi"""
    chs = db.get_channels()
    return any(c["type"] in ("private", "link") for c in chs)

async def cb_chk_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    unsubbed = await check_subs(ctx.bot, q.from_user.id)
    if unsubbed:
        await q.answer(
            "Hali Telegram kanalga obuna bolmadingiz!",
            show_alert=True
        )
        return
    u = q.from_user
    await q.edit_message_text("Obuna tasdiqlandi! Kino kodini yuboring.")
    mkb = kb.admin_kb() if db.is_admin(u.id) else kb.user_kb()
    await ctx.bot.send_message(u.id, "👇", reply_markup=mkb)

# ═══════════════════════════════
# USER — KINO QIDIRISH
# ═══════════════════════════════

async def msg_find_movie(update: Update, ctx):
    u = update.effective_user
    code = update.message.text.strip()
    unsubbed = await check_subs(ctx.bot, u.id)
    if unsubbed:
        all_ch = await get_all_unsub_channels(ctx.bot, u.id)
        await update.message.reply_text(
            "📢 Avval kanallarga obuna boling!",
            reply_markup=kb.sub_kb(all_ch)
        )
        return
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text(
            f"❌ <b>{code}</b> kodli kino topilmadi.",
            parse_mode=H
        )
        return
    ch = get_movie_ch()
    if not ch:
        await update.message.reply_text("Kino kanal sozlanmagan. Admin bilan boglanin.")
        return
    try:
        await ctx.bot.copy_message(
            chat_id=u.id, from_chat_id=ch, message_id=int(movie["msg_id"])
        )
    except TelegramError as e:
        logging.error(f"Copy xato: {e}")
        await update.message.reply_text("Kinoni yuborishda xatolik. Admin bilan boglanin.")

# ═══════════════════════════════
# USER — PROFIL
# ═══════════════════════════════

async def msg_profile(update: Update, ctx):
    u = update.effective_user
    sub = db.has_sub(u.id)
    info = db.sub_info(u.id)
    price = db.gs("sub_price") or "15000"
    days = db.gs("sub_days") or "30"
    sub_text = f"Faol ({info['expires_at'][:10]} gacha)" if sub and info else "Obuna yoq"
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("Obuna sotib olish", callback_data="buy_sub")
    ]])
    await update.message.reply_text(
        f"👤 <b>Mening profilim</b>\n\n"
        f"ID: <code>{u.id}</code>\n"
        f"Ism: {u.first_name}\n"
        f"Obuna: {sub_text}\n\n"
        f"━━━━━━━━━━━━━\n"
        f"{days} kunlik obuna: <b>{int(price):,} som</b>",
        parse_mode=H, reply_markup=markup
    )

async def msg_help(update: Update, ctx):
    await update.message.reply_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "Kino kodini yuboring — bot kinoni yuboradi.\n\n"
        "Obuna: Profilim → Obuna sotib olish",
        parse_mode=H
    )

# ═══════════════════════════════
# TOLOV
# ═══════════════════════════════

async def cb_buy_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price = db.gs("sub_price") or "15000"
    days = db.gs("sub_days") or "30"
    await q.edit_message_text(
        f"💳 <b>Obuna sotib olish</b>\n\n"
        f"Muddat: <b>{days} kun</b>\n"
        f"Narx: <b>{int(price):,} som</b>\n\n"
        f"Tolov usulini tanlang:",
        parse_mode=H, reply_markup=kb.buy_kb()
    )

async def cb_pay_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    card_type = q.data.replace("pay_", "")
    price = db.gs("sub_price") or "15000"
    card = db.gs(f"card_{card_type}") or "Sozlanmagan"
    owner = db.gs("card_owner") or "Admin"
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}
    ctx.user_data["pay_card"] = card_type
    await q.edit_message_text(
        f"💳 <b>{names.get(card_type, '')} orqali tolov</b>\n\n"
        f"Summa: <b>{int(price):,} som</b>\n\n"
        f"Karta: <code>{card}</code>\n"
        f"Egasi: <b>{owner}</b>\n\n"
        f"1. Kartaga pul otkazing\n"
        f"2. Chek rasmini yuboring",
        parse_mode=H, reply_markup=kb.back_kb("x")
    )
    return S_PAY

async def rcv_screenshot(update: Update, ctx):
    u = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("Chek rasmini yuboring!")
        return S_PAY
    card_type = ctx.user_data.get("pay_card", "uzcard")
    price = int(db.gs("sub_price") or "15000")
    fid = update.message.photo[-1].file_id
    pay_id = db.add_payment(u.id, price, card_type, fid)
    if not pay_id:
        await update.message.reply_text(
            "Kutilayotgan tolov mavjud. Admin tasdiqlashini kuting.",
            reply_markup=kb.user_kb()
        )
        return END
    await update.message.reply_text(
        "Tolovingiz qabul qilindi! Tez orada tasdiqlanadi.",
        reply_markup=kb.user_kb()
    )
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}
    uname = u.username if u.username else "yoq"
    caption = (
        f"💳 <b>Yangi tolov!</b>\n\n"
        f"Foydalanuvchi: <a href='tg://user?id={u.id}'>{u.first_name}</a>\n"
        f"ID: <code>{u.id}</code>\n"
        f"Username: @{uname}\n"
        f"Summa: <b>{price:,} som</b>\n"
        f"Karta: {names.get(card_type, card_type)}\n"
        f"Raqam: {pay_id}"
    )
    await send_to_admins(ctx, photo=fid, caption=caption,
                         markup=kb.pay_confirm_kb(pay_id))
    ctx.user_data.clear()
    return END

async def cb_pay_ok(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id): return
    pay_id = int(q.data.replace("pok_", ""))
    pay = db.get_payment(pay_id)
    if not pay or pay["status"] != "pending":
        await q.answer("Allaqachon hal qilingan!", show_alert=True); return
    days = int(db.gs("sub_days") or "30")
    db.resolve_payment(pay_id, "approved")
    db.give_sub(pay["user_id"], days)
    await q.edit_message_caption(f"TASDIQLANDI\n\n{q.message.caption}", parse_mode=H)
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            f"Tolovingiz tasdiqlandi!\n{days} kunlik obuna faollashtirildi!",
            reply_markup=kb.user_kb()
        )
    except Exception: pass

async def cb_pay_no(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id): return
    pay_id = int(q.data.replace("pno_", ""))
    pay = db.get_payment(pay_id)
    if not pay or pay["status"] != "pending":
        await q.answer("Allaqachon hal qilingan!", show_alert=True); return
    db.resolve_payment(pay_id, "rejected")
    await q.edit_message_caption(f"BEKOR QILINDI\n\n{q.message.caption}", parse_mode=H)
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            "Tolovingiz tasdiqlanmadi. Qayta urinib koring.",
            reply_markup=kb.user_kb()
        )
    except Exception: pass

# ═══════════════════════════════
# ADMIN — STATISTIKA
# ═══════════════════════════════

async def msg_stats(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    s = db.user_stats()
    mc = db.movie_count()
    chs = db.get_channels()
    await update.message.reply_text(
        f"📊 <b>Bot statistikasi</b>\n\n"
        f"Yangi foydalanuvchilar:\n"
        f"• Bugun: +{s['today']} ta\n"
        f"• 7 kun: +{s['week']} ta\n"
        f"• 30 kun: +{s['month']} ta\n\n"
        f"Faollik:\n"
        f"• 24 soat: {s['act24']} ta\n"
        f"• 7 kun: {s['act7']} ta\n"
        f"• 30 kun: {s['act30']} ta\n\n"
        f"🎬 Kinolar: <b>{mc} ta</b>\n"
        f"🔒 Kanallar: <b>{len(chs)} ta</b>\n"
        f"👤 Jami: <b>{s['total']} ta</b>",
        parse_mode=H
    )

# ═══════════════════════════════
# ADMIN — KINOLAR
# ═══════════════════════════════

async def msg_movies(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    await update.message.reply_text(
        "🎬 <b>Kinolar bomi</b>",
        parse_mode=H, reply_markup=kb.movies_kb()
    )

async def cb_mv_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🎬 <b>Kinolar bomi</b>", parse_mode=H, reply_markup=kb.movies_kb())
    await ctx.bot.send_message(
        q.from_user.id,
        "Kino kodini kiriting:\nMasalan: 101, 202, 350\n\nBekor: /cancel"
    )
    return S_MV_CODE

async def st_mv_code(update: Update, ctx):
    code = update.message.text.strip()
    existing = db.get_movie(code)
    if existing:
        await update.message.reply_text(
            f"{code} kodi mavjud! Sarlavha: {existing['title'] or '—'}\n\n"
            f"Davom etsangiz yangilanadi.\nMessage ID yuboring:"
        )
    else:
        await update.message.reply_text(
            f"Kod: <b>{code}</b>\n\nMessage ID yuboring:\n\n"
            f"Kanalda postga ong klik - Copy Link\n"
            f"Link oxiridagi raqam = Message ID",
            parse_mode=H
        )
    ctx.user_data["mv_code"] = code
    return S_MV_MSGID

async def st_mv_msgid(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam! Qayta:")
        return S_MV_MSGID
    ctx.user_data["mv_msgid"] = t
    await update.message.reply_text("Kino sarlavhasini yuboring:\nO'tkazish uchun: - yuboring")
    return S_MV_TITLE

async def st_mv_title(update: Update, ctx):
    title = "" if update.message.text.strip() == "-" else update.message.text.strip()
    code = ctx.user_data["mv_code"]
    msgid = ctx.user_data["mv_msgid"]
    db.save_movie(code, msgid, title)
    ch = get_movie_ch()
    test_text = ""
    if ch:
        try:
            await ctx.bot.copy_message(
                chat_id=update.effective_user.id,
                from_chat_id=ch, message_id=int(msgid)
            )
            test_text = "\n\nTest korinishi yuqorida:"
        except Exception as e:
            test_text = f"\n\nTest xato: {e}"
    await update.message.reply_text(
        f"Kino qoshildi!\nKod: <code>{code}</code>\n"
        f"MsgID: <code>{msgid}</code>\n"
        f"Sarlavha: {title or '—'}{test_text}",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    ctx.user_data.clear()
    return END

async def cb_mv_edit(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🎬 <b>Kinolar bomi</b>", parse_mode=H, reply_markup=kb.movies_kb())
    await ctx.bot.send_message(q.from_user.id, "Tahrirlash uchun kino kodini kiriting:\n\nBekor: /cancel")
    return S_ED_OLD

async def st_ed_old(update: Update, ctx):
    code = update.message.text.strip()
    m = db.get_movie(code)
    if not m:
        await update.message.reply_text(f"{code} topilmadi! Qayta:")
        return S_ED_OLD
    ctx.user_data["ed_old"] = code
    await update.message.reply_text(
        f"Topildi: <b>{m['title'] or code}</b>\nID: <code>{m['msg_id']}</code>\n\nYangi kodni yuboring:",
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
        await update.message.reply_text("Faqat raqam!")
        return S_ED_MSGID
    ctx.user_data["ed_msgid"] = t
    await update.message.reply_text("Yangi sarlavha yuboring (ozgarmasa - yuboring):")
    return S_ED_TITLE

async def st_ed_title(update: Update, ctx):
    title = "" if update.message.text.strip() == "-" else update.message.text.strip()
    db.update_movie(
        ctx.user_data["ed_old"], ctx.user_data["ed_code"],
        ctx.user_data["ed_msgid"], title
    )
    await update.message.reply_text("Kino yangilandi!", reply_markup=kb.movies_kb())
    ctx.user_data.clear()
    return END

async def cb_mv_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🎬 <b>Kinolar bomi</b>", parse_mode=H, reply_markup=kb.movies_kb())
    await ctx.bot.send_message(q.from_user.id, "Ochirmoqchi bolgan kino kodini kiriting:\n\nBekor: /cancel")
    return S_DEL

async def st_del(update: Update, ctx):
    code = update.message.text.strip()
    if db.del_movie(code):
        await update.message.reply_text(f"<b>{code}</b> ochirildi!", parse_mode=H, reply_markup=kb.movies_kb())
    else:
        await update.message.reply_text(f"{code} topilmadi! Qayta:")
        return S_DEL
    return END

async def cb_mv_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    movies = db.get_movies(30)
    if not movies:
        await q.edit_message_text("Kino bazasi bosh.", reply_markup=kb.movies_kb())
        return
    lines = [f"📋 <b>Kinolar ({len(movies)} ta):</b>\n"]
    for m in movies:
        lines.append(f"<code>{m['code']}</code> | {m['title'] or '—'} | {m['views']} marta")
    await q.edit_message_text(
        "\n".join(lines), parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="mv_back")]])
    )

async def cb_mv_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🎬 <b>Kinolar bomi</b>", parse_mode=H, reply_markup=kb.movies_kb())

# ═══════════════════════════════
# ADMIN — KANALLAR (3 TUR)
# ═══════════════════════════════

async def msg_channels(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    chs = db.get_channels()
    await update.message.reply_text(
        f"🔒 <b>Majburiy obuna kanallar</b>\n\nHozirda: <b>{len(chs)} ta</b>",
        parse_mode=H, reply_markup=kb.channels_kb()
    )

async def cb_ch_add(update: Update, ctx):
    """Kanal turi tanlash"""
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🔒 <b>Majburiy obuna turini tanlang:</b>\n\n"
        "Quyida majburiy obunani qoshishning 3 ta turi mavjud:\n\n"
        "<b>📢 Ommaviy / Shaxsiy (Kanal / Guruh)</b>\n"
        "Har qanday kanal yoki guruhni majburiy obunaga ulash.\n\n"
        "<b>🔒 Shaxsiy / Sorovli havola</b>\n"
        "Shaxsiy yoki sorovli kanal/guruh havolasi orqali\n"
        "otganlarni kuzatish.\n\n"
        "<b>🌐 Oddiy havola</b>\n"
        "Majburiy tekshiruvsiz oddiy havolani korsatish\n"
        "(Instagram, sayt va boshqalar).",
        parse_mode=H, reply_markup=kb.channel_type_kb()
    )

async def cb_cht_telegram(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "telegram"
    await q.edit_message_text(
        "📢 <b>Ommaviy / Shaxsiy (Kanal · Guruh) - ulash</b>\n\n"
        "Quyida kanal/guruhni ulashning 3 ta oddiy usuli mavjud:\n\n"
        "<b>1. ID orqali ulash</b>\n"
        "Kanal yoki guruh ID raqamini kiriting.\n"
        "ID odatda -100... shaklida boladi.\n\n"
        "<b>2. Havola orqali ulash</b>\n"
        "Kanal/guruh havolasini yuboring.\n"
        "Masalan: @kanal_nomi yoki https://t.me/kanal\n\n"
        "<b>3. Postni ulash orqali</b>\n"
        "Kanal yoki guruhdan bitta postni ulashing va shu\n"
        "xabarni botga yuboring.\n"
        "Bot avtomatik ravishda kanalni taniydi.",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="ch_add")
        ]])
    )
    return S_CH_ID

async def cb_cht_private(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "private"
    await q.edit_message_text(
        "🔒 <b>Shaxsiy / Sorovli havola - ulash</b>\n\n"
        "Quyida kanal/guruhni ulashning 3 ta oddiy usuli mavjud:\n\n"
        "<b>1. ID orqali ulash</b>\n"
        "Kanal yoki guruh ID raqamini kiriting.\n"
        "ID odatda -100... shaklida boladi.\n\n"
        "<b>2. Havola orqali ulash</b>\n"
        "Kanal/guruh havolasini yuboring.\n"
        "Masalan: @kanal_nomi yoki https://t.me/kanal\n\n"
        "<b>3. Postni ulash orqali</b>\n"
        "Kanal yoki guruhdan bitta postni ulashing va shu\n"
        "xabarni botga yuboring.\n"
        "Bot avtomatik ravishda kanalni taniydi.",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="ch_add")
        ]])
    )
    return S_CH_ID

async def cb_cht_link(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "link"
    ctx.user_data["ch_id"] = ""
    await q.edit_message_text(
        "🔗 <b>Havola kiriting:</b>\n\n"
        "<i>Masalan: https://site.com yoki https://t.me/kanal</i>\n\n"
        "Iltimos, yuqoridagi kabi togri formatda havolani kiriting.",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="ch_add")
        ]])
    )
    return S_CH_LINK

async def st_ch_id(update: Update, ctx):
    text = update.message.text.strip()
    ch_type = ctx.user_data.get(CH_TYPE_KEY, "telegram")

    # Forward qilingan post orqali kanal ID olish
    if update.message.forward_from_chat:
        chat = update.message.forward_from_chat
        ch_id = str(chat.id)
        title = chat.title or chat.username or ch_id
        if ch_id.startswith("-100"):
            link = f"https://t.me/{chat.username}" if chat.username else ""
        else:
            link = ""
        db.add_channel(ch_id, title, link, ch_type)
        await update.message.reply_text(
            f"Kanal qoshildi!\n\nNom: {title}\nID: <code>{ch_id}</code>",
            parse_mode=H, reply_markup=kb.channels_kb()
        )
        ctx.user_data.clear()
        return END

    # ID yoki username
    if text.startswith("@"):
        ch_id = text
        title = text[1:]  # @ ni olib tashlash
        link = f"https://t.me/{text[1:]}"
    elif text.startswith("-100"):
        ch_id = text
        title = f"Kanal {text[-6:]}"  # Oxirgi raqamlar
        link = ""
    elif text.startswith("http"):
        # Havola yuborilgan — bu S_CH_LINK ga mos
        ch_id = text
        title = text.split("/")[-1] or text
        link = text
    else:
        await update.message.reply_text(
            "Notogri format!\n\n"
            "• @mykanal\n"
            "• -1001234567890\n"
            "• Yoki kanaldan post forward qiling\n\nQayta:"
        )
        return S_CH_ID

    ctx.user_data["ch_id"] = ch_id
    ctx.user_data["ch_title"] = title
    ctx.user_data["ch_auto_link"] = link
    ctx.user_data["ch_auto_saved"] = False

    # Telegram uchun tasdiqlash so'rash
    if ch_type == "telegram":
        await update.message.reply_text(
            f"Kanal: <b>{title}</b>\n\n"
            f"Botni kanalga admin qilib qoshing!\n\n"
            f"Havola (ozgartirish uchun yuboring, aks holda - yuboring):\n"
            f"{link if link else 'Havola yoq — qoshing'}",
            parse_mode=H
        )
        return S_CH_LINK
    else:
        # Private uchun havola so'rash
        await update.message.reply_text(
            f"Nom: <b>{title}</b>\n\nHavolani yuboring (yoki - yuboring):",
            parse_mode=H
        )
        return S_CH_LINK


async def st_ch_title(update: Update, ctx):
    # Bu endi ishlatilmaydi, lekin fallback sifatida qoladi
    ctx.user_data["ch_title"] = update.message.text.strip()
    await update.message.reply_text("Havolani kiriting:")
    return S_CH_LINK


async def st_ch_link(update: Update, ctx):
    text = update.message.text.strip()
    ch_type = ctx.user_data.get(CH_TYPE_KEY, "telegram")

    if ch_type == "link":
        # Faqat havola — nomni havoladan olamiz
        link = text
        # Nomni avtomatik olish
        if "instagram.com/" in link:
            title = "Instagram"
        elif "youtube.com/" in link or "youtu.be/" in link:
            title = "YouTube"
        elif "t.me/" in link:
            title = link.split("t.me/")[-1].split("/")[0]
        else:
            title = link.split("/")[2] if "//" in link else link
        db.add_channel("", title, link, ch_type)
        await update.message.reply_text(
            f"Havola qoshildi!\n\nNom: {title}\nHavola: {link}",
            reply_markup=kb.channels_kb()
        )
        ctx.user_data.clear()
        return END

    # Telegram / private
    if text == "-":
        link = ctx.user_data.get("ch_auto_link", "")
    else:
        link = text

    ch_id = ctx.user_data.get("ch_id", "")
    title = ctx.user_data.get("ch_title", "Kanal")

    db.add_channel(ch_id, title, link, ch_type)
    type_names = {"telegram": "Telegram kanal", "private": "Shaxsiy havola"}
    await update.message.reply_text(
        f"Kanal qoshildi!\n\nTur: {type_names.get(ch_type, ch_type)}\nNom: {title}",
        reply_markup=kb.channels_kb()
    )
    ctx.user_data.clear()
    return END

async def cb_ch_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await q.edit_message_text("Hozircha kanallar yoq.", reply_markup=kb.channels_kb())
        return
    icons = {"telegram": "📢", "private": "🔒", "link": "🌐"}
    lines = [f"📋 <b>Majburiy obuna kanallari royxati:</b>\n\n"
             f"Jami: {len(chs)} ta\n\n"
             f"Kerakli kanal ustiga bosib ma'lumotlarni ko'rishingiz mumkin."]
    await q.edit_message_text(
        "\n".join(lines), parse_mode=H,
        reply_markup=kb.channel_list_kb(chs)
    )

async def cb_ch_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await q.edit_message_text("Ochirish uchun kanallar yoq.", reply_markup=kb.channels_kb())
        return
    await q.edit_message_text(
        "Majburiy obuna kanallar royxati:\n\nOchirish uchun kerakli kanal nomini bosing.",
        reply_markup=kb.channel_del_list_kb(chs)
    )

async def cb_dch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id): return
    ch_id = int(q.data.replace("dch_", ""))
    if db.del_channel(ch_id):
        await q.answer("Kanal ochirildi!", show_alert=True)
        chs = db.get_channels()
        if not chs:
            await q.edit_message_text("Kanallar yoq.", reply_markup=kb.channels_kb())
            return
        await q.edit_message_text(
            "Majburiy obuna kanallar royxati:\n\nOchirish uchun kerakli kanal nomini bosing.",
            reply_markup=kb.channel_del_list_kb(chs)
        )
    else:
        await q.answer("Topilmadi.", show_alert=True)

async def cb_ch_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    await q.edit_message_text(
        f"🔒 <b>Majburiy obuna kanallar</b>\n\nHozirda: <b>{len(chs)} ta</b>",
        parse_mode=H, reply_markup=kb.channels_kb()
    )

async def cmd_delch(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Format: /delch 1")
        return
    if db.del_channel(int(ctx.args[0])):
        await update.message.reply_text("Kanal ochirildi!")
    else:
        await update.message.reply_text("Topilmadi.")

# ═══════════════════════════════
# ADMIN — ADMINLAR
# ═══════════════════════════════

async def msg_admins(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    await update.message.reply_text(
        "👮 <b>Adminlar bomi</b>",
        parse_mode=H, reply_markup=kb.admins_kb()
    )

async def cb_adm_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Yangi admin Telegram ID sini yuboring:\n\nID olish: @userinfobot ga /start\n\nBekor: /cancel")
    return S_ADM_ADD

async def st_adm_add(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam! Qayta:")
        return S_ADM_ADD
    uid = int(t)
    if uid in ADMIN_IDS:
        await update.message.reply_text("Bu asosiy admin!")
        return END
    db.add_admin(uid, f"Admin {uid}")
    await update.message.reply_text(f"<code>{uid}</code> admin qoshildi!", parse_mode=H, reply_markup=kb.admins_kb())
    try:
        await ctx.bot.send_message(uid, "Siz admin qilib tayinlandingiz!")
    except Exception: pass
    return END

async def cb_adm_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Admin Telegram ID sini yuboring:\n\nBekor: /cancel")
    return S_ADM_DEL

async def st_adm_del(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam! Qayta:")
        return S_ADM_DEL
    uid = int(t)
    if uid in ADMIN_IDS:
        await update.message.reply_text("Asosiy adminni ochirib bolmaydi!")
        return END
    if db.del_admin(uid):
        await update.message.reply_text(f"<code>{uid}</code> ochirildi!", parse_mode=H, reply_markup=kb.admins_kb())
    else:
        await update.message.reply_text("Bu ID topilmadi.")
    return END

async def cb_adm_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    total = len(ADMIN_IDS) + len(db.get_admins())
    await q.edit_message_text(
        f"📋 <b>Adminlar royxati</b>\n\nJami: <b>{total} ta</b> admin",
        parse_mode=H, reply_markup=kb.admins_kb()
    )

# ═══════════════════════════════
# ADMIN — BROADCAST
# ═══════════════════════════════

async def msg_broadcast(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    count = len(db.all_user_ids())
    await update.message.reply_text(
        f"📨 <b>Xabar yuborish</b>\n\nJami: <b>{count} ta</b>",
        parse_mode=H, reply_markup=kb.broadcast_kb()
    )

async def cb_bc_text(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Barcha userlarga yuboriladigan xabarni yozing:\n\nBekor: /cancel")
    return S_BC_TEXT

async def cb_bc_fwd(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Forward qilinadigan xabarni yuboring:\n\nBekor: /cancel")
    return S_BC_FWD

async def st_bc_text(update: Update, ctx):
    text = update.message.text
    users = db.all_user_ids()
    sent = failed = 0
    msg = await update.message.reply_text(f"Yuborilmoqda: 0/{len(users)}")
    for i, uid in enumerate(users):
        try:
            await ctx.bot.send_message(uid, text, parse_mode=H)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try: await msg.edit_text(f"Yuborilmoqda: {i+1}/{len(users)}")
            except Exception: pass
        await asyncio.sleep(0.04)
    await msg.edit_text(f"Broadcast tugadi!\n\nYuborildi: {sent}\nXatolik: {failed}")
    return END

async def st_bc_fwd(update: Update, ctx):
    users = db.all_user_ids()
    sent = failed = 0
    msg = await update.message.reply_text(f"Forward: 0/{len(users)}")
    for i, uid in enumerate(users):
        try:
            await update.message.forward(uid)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try: await msg.edit_text(f"Forward: {i+1}/{len(users)}")
            except Exception: pass
        await asyncio.sleep(0.04)
    await msg.edit_text(f"Forward tugadi!\n\nYuborildi: {sent}\nXatolik: {failed}")
    return END

# ═══════════════════════════════
# ADMIN — SOZLAMALAR
# ═══════════════════════════════

async def msg_settings(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    price   = db.gs("sub_price") or "15000"
    days    = db.gs("sub_days")  or "30"
    movch   = db.gs("movie_ch")  or MOVIE_CH or "Sozlanmagan"
    uzcard  = db.gs("card_uzcard") or "Sozlanmagan"
    humo    = db.gs("card_humo")   or "Sozlanmagan"
    visa    = db.gs("card_visa")   or "Sozlanmagan"
    owner   = db.gs("card_owner")  or "Sozlanmagan"
    welcome = db.gs("welcome_text") or "—"
    await update.message.reply_text(
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"Obuna: {int(price):,} som / {days} kun\n"
        f"Kino kanal: <code>{movch}</code>\n\n"
        f"UzCard: <code>{uzcard}</code>\n"
        f"Humo: <code>{humo}</code>\n"
        f"Visa: <code>{visa}</code>\n"
        f"Egasi: {owner}\n\n"
        f"Xush kelibsiz:\n<i>{welcome}</i>",
        parse_mode=H, reply_markup=kb.settings_kb()
    )

async def cb_st_cards(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Qaysi kartani sozlamoqchisiz?", reply_markup=kb.cards_kb())

async def cb_sc_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    key = q.data.replace("sc_", "")
    ctx.user_data["st_key"] = "card_" + key
    names = {"uzcard": "UzCard raqami", "humo": "Humo raqami",
             "visa": "Visa raqami", "owner": "Karta egasi ismi"}
    await q.edit_message_text(f"Yangi {names.get(key, key)} ni yuboring:\n\nBekor: /cancel")
    return S_ST_CARD

async def st_save_card(update: Update, ctx):
    db.ss(ctx.user_data["st_key"], update.message.text.strip())
    await update.message.reply_text("Saqlandi!", reply_markup=kb.settings_kb())
    ctx.user_data.clear()
    return END

async def cb_st_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Karta sozlamalari:", reply_markup=kb.cards_kb())

async def cb_st_price(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price = db.gs("sub_price") or "15000"
    days  = db.gs("sub_days")  or "30"
    await q.edit_message_text(
        f"Hozirgi: <b>{int(price):,} som / {days} kun</b>\n\n"
        f"Yangi narxni yuboring:\n\nBekor: /cancel",
        parse_mode=H
    )
    return S_ST_PRICE

async def st_save_price(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam!")
        return S_ST_PRICE
    db.ss("sub_price", t)
    await update.message.reply_text(
        f"Narx {int(t):,} som saqlandi!\n\n"
        f"Kunni ozgartirmoqchimisiz? (raqam yoki - ):"
    )
    ctx.user_data["wait_days"] = True
    return S_ST_PRICE

async def st_save_days(update: Update, ctx):
    t = update.message.text.strip()
    if ctx.user_data.get("wait_days"):
        if t != "-" and t.isdigit():
            db.ss("sub_days", t)
            await update.message.reply_text(f"Muddat {t} kun saqlandi!", reply_markup=kb.settings_kb())
        else:
            await update.message.reply_text("Muddat ozgarmadi.", reply_markup=kb.settings_kb())
        ctx.user_data.clear()
        return END
    return END

async def cb_st_movch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("movie_ch") or MOVIE_CH or "Sozlanmagan"
    await q.edit_message_text(
        f"Hozirgi: <code>{cur}</code>\n\n"
        f"Yangi kino kanal ID yuboring:\n"
        f"Masalan: -1001234567890\n\n"
        f"@JsonDumpBot ga forward qiling\n\n"
        f"Botni kanalga admin qilib qoshing!\n\n"
        f"Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_MOVCH

async def st_save_movch(update: Update, ctx):
    val = update.message.text.strip()
    db.ss("movie_ch", val)
    await update.message.reply_text(
        f"Kino kanal saqlandi: <code>{val}</code>",
        parse_mode=H, reply_markup=kb.settings_kb()
    )
    return END

async def cb_st_welcome(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("welcome_text") or "—"
    await q.edit_message_text(
        f"Hozirgi:\n<i>{cur}</i>\n\nYangi matnni yuboring:\n\nBekor: /cancel",
        parse_mode=H
    )
    return S_ST_WELCOME

async def st_save_welcome(update: Update, ctx):
    db.ss("welcome_text", update.message.text.strip())
    await update.message.reply_text("Saqlandi!", reply_markup=kb.settings_kb())
    return END

async def cmd_clear_cache(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    ctx.user_data.clear()
    ctx.chat_data.clear()
    await update.message.reply_text("Kesh tozalandi!", reply_markup=kb.admin_kb())

async def msg_orqaga(update: Update, ctx):
    ctx.user_data.clear()
    await cmd_start(update, ctx)

# ═══════════════════════════════
# MAIN
# ═══════════════════════════════

def main():
    db.init_db()
    logging.info("Database tayyor")
    app = Application.builder().token(BOT_TOKEN).build()

    # Tolov
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_pay_card, pattern="^pay_(uzcard|humo|visa)$")],
        states={S_PAY: [MessageHandler(filters.PHOTO, rcv_screenshot)]},
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
    # Kino qoshish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mv_add, pattern="^mv_add$")],
        states={
            S_MV_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_code)],
            S_MV_MSGID: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_msgid)],
            S_MV_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
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
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
    # Kino ochirish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mv_del, pattern="^mv_del$")],
        states={S_DEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_del)]},
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
    # Kanal qoshish (3 tur)
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_cht_telegram, pattern="^cht_telegram$"),
            CallbackQueryHandler(cb_cht_private,  pattern="^cht_private$"),
            CallbackQueryHandler(cb_cht_link,     pattern="^cht_link$"),
        ],
        states={
            S_CH_ID:    [
                MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_id),
                MessageHandler(filters.ALL & ~filters.COMMAND, st_ch_id),  # forward uchun
            ],
            S_CH_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_title)],
            S_CH_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
    # Admin qoshish/ochirish
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_adm_add, pattern="^adm_add$"),
            CallbackQueryHandler(cb_adm_del, pattern="^adm_del$"),
        ],
        states={
            S_ADM_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_adm_add)],
            S_ADM_DEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_adm_del)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
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
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
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
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))

    # Commands
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("admin",      cmd_start))
    app.add_handler(CommandHandler("cancel",     cancel))
    app.add_handler(CommandHandler("delch",      cmd_delch))
    app.add_handler(CommandHandler("clearcache", cmd_clear_cache))

    # Callbacks
    app.add_handler(CallbackQueryHandler(cb_chk_sub,  pattern="^chk_sub$"))
    app.add_handler(CallbackQueryHandler(cb_buy_sub,  pattern="^buy_sub$"))
    app.add_handler(CallbackQueryHandler(cb_pay_ok,   pattern=r"^pok_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_no,   pattern=r"^pno_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mv_list,  pattern="^mv_list$"))
    app.add_handler(CallbackQueryHandler(cb_mv_back,  pattern="^mv_back$"))
    app.add_handler(CallbackQueryHandler(cb_ch_add,   pattern="^ch_add$"))
    app.add_handler(CallbackQueryHandler(cb_ch_list,  pattern="^ch_list$"))
    app.add_handler(CallbackQueryHandler(cb_ch_del,   pattern="^ch_del$"))
    app.add_handler(CallbackQueryHandler(cb_dch,      pattern=r"^dch_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_ch_back,  pattern="^ch_back$"))
    app.add_handler(CallbackQueryHandler(cb_adm_list, pattern="^adm_list$"))
    app.add_handler(CallbackQueryHandler(cb_st_cards, pattern="^st_cards$"))
    app.add_handler(CallbackQueryHandler(cb_st_back,  pattern="^st_back$"))
    app.add_handler(CallbackQueryHandler(cb_cancel,   pattern="^x$"))

    # Admin menyu
    app.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"),     msg_stats))
    app.add_handler(MessageHandler(filters.Regex("^📨 Xabar yuborish$"), msg_broadcast))
    app.add_handler(MessageHandler(filters.Regex("^🎬 Kinolar$"),         msg_movies))
    app.add_handler(MessageHandler(filters.Regex("^🔒 Kanallar$"),        msg_channels))
    app.add_handler(MessageHandler(filters.Regex("^👮 Adminlar$"),        msg_admins))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Sozlamalar$"),      msg_settings))
    app.add_handler(MessageHandler(filters.Regex("^◀️ Orqaga$"),          msg_orqaga))

    # User menyu
    app.add_handler(MessageHandler(filters.Regex("^👤 Profilim$"),        msg_profile))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yordam$"),          msg_help))
    app.add_handler(MessageHandler(filters.Regex("^🎬 Kino qidirish$"),
        lambda u, c: u.message.reply_text("Kino kodini yuboring:")))

    # Raqam = kino qidirish
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d+$"),
        msg_find_movie
    ))

    if os.environ.get("RENDER") == "true":
        logging.info("Webhook (Render)...")
        app.run_webhook(
            listen="0.0.0.0", port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        logging.info("Polling (local)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
