"""
KINO BOT v3.0 — main.py
Professional kino bot — barcha funksiyalar
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

# ═══════════════════════════════
# YORDAMCHILAR
# ═══════════════════════════════

async def check_subs(bot, uid):
    result = []
    for ch in db.get_channels():
        try:
            m = await bot.get_chat_member(ch["channel_id"], uid)
            if m.status in ["left", "kicked"]:
                result.append(ch)
        except Exception:
            pass
    return result

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
        await update.message.reply_text("❌ Bekor qilindi.",
            reply_markup=kb.admin_kb() if db.is_admin(update.effective_user.id) else kb.user_kb())
    return END

async def cb_cancel(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    await q.edit_message_text("❌ Bekor qilindi.")

# ═══════════════════════════════
# START
# ═══════════════════════════════

async def cmd_start(update: Update, ctx):
    u = update.effective_user
    db.add_user(u.id, u.first_name, u.username or "")
    unsubbed = await check_subs(ctx.bot, u.id)
    if unsubbed:
        await update.message.reply_text(
            "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna boling:</b>\n\n"
            "Obuna bolgach <b>Tekshirish</b> tugmasini bosing.",
            parse_mode=H, reply_markup=kb.sub_kb(unsubbed)
        )
        return
    if db.is_admin(u.id):
        await update.message.reply_text(
            f"👑 <b>Salom, {u.first_name}!</b>\n\n"
            f"Admin paneliga xush kelibsiz. Quyidagi menyudan foydalaning 👇",
            parse_mode=H, reply_markup=kb.admin_kb()
        )
    else:
        welcome = db.gs("welcome_text") or "Kino kodini yuboring 🎬"
        await update.message.reply_text(
            f"🎬 <b>Salom, {u.first_name}!</b>\n\n{welcome}",
            parse_mode=H, reply_markup=kb.user_kb()
        )

async def cb_chk_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    unsubbed = await check_subs(ctx.bot, q.from_user.id)
    if unsubbed:
        await q.answer("Hali obuna bolmadingiz! Yuqoridagi tugmalardan kanallarga oting.",
                       show_alert=True)
        return
    u = q.from_user
    await q.edit_message_text(
        "Obuna tasdiqlandi!\n\n🎬 Kino kodini yuboring:", parse_mode=H
    )
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
        await update.message.reply_text(
            "📢 Avval kanallarga obuna boling!",
            reply_markup=kb.sub_kb(unsubbed)
        )
        return
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text(
            f"❌ <b>{code}</b> kodli kino topilmadi.\n"
            f"<i>Kodni togri yozdingizmi?</i>",
            parse_mode=H
        )
        return
    ch = get_movie_ch()
    if not ch:
        await update.message.reply_text(
            "Kino kanal hali sozlanmagan. Admin bilan boglanin."
        )
        return
    try:
        await ctx.bot.copy_message(
            chat_id=u.id, from_chat_id=ch, message_id=int(movie["msg_id"])
        )
    except TelegramError as e:
        logging.error(f"Copy xato: {e}")
        await update.message.reply_text(
            "Kinoni yuborishda xatolik yuz berdi. Admin bilan boglanin."
        )

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
        f"━━━━━━━━━━━━━━━\n"
        f"{days} kunlik obuna: <b>{int(price):,} som</b>",
        parse_mode=H, reply_markup=markup
    )

async def msg_help(update: Update, ctx):
    await update.message.reply_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "🎬 Kino kodini yuboring — bot kinoni yuboradi.\n\n"
        "Obuna sotib olish: Profilim tugmasi\n\n"
        "Muammo bolsa admin bilan boglanin.",
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
        f"Tolov summasi: <b>{int(price):,} som</b>\n\n"
        f"Karta raqami:\n<code>{card}</code>\n"
        f"Egasi: <b>{owner}</b>\n\n"
        f"1. Kartaga pul otkazing\n"
        f"2. Chek rasmini yuboring",
        parse_mode=H, reply_markup=kb.back_kb("x")
    )
    return S_PAY

async def rcv_screenshot(update: Update, ctx):
    u = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("Iltimos, chek rasmini yuboring!")
        return S_PAY
    card_type = ctx.user_data.get("pay_card", "uzcard")
    price = int(db.gs("sub_price") or "15000")
    fid = update.message.photo[-1].file_id
    pay_id = db.add_payment(u.id, price, card_type, fid)
    if not pay_id:
        await update.message.reply_text(
            "Sizda kutilayotgan tolov mavjud. Admin tasdiqlashini kuting.",
            reply_markup=kb.user_kb()
        )
        return END
    await update.message.reply_text(
        "Tolovingiz qabul qilindi! Admin tez orada korib chiqadi.",
        reply_markup=kb.user_kb()
    )
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}
    uname = u.username if u.username else "yoq"
    caption = (
        f"💳 <b>Yangi tolov sorovil</b>\n\n"
        f"Foydalanuvchi: <a href='tg://user?id={u.id}'>{u.first_name}</a>\n"
        f"ID: <code>{u.id}</code>\n"
        f"Username: @{uname}\n"
        f"Summa: <b>{price:,} som</b>\n"
        f"Karta: {names.get(card_type, card_type)}\n"
        f"Tolov raqami: {pay_id}"
    )
    await send_to_admins(ctx, photo=fid, caption=caption,
                         markup=kb.pay_confirm_kb(pay_id))
    ctx.user_data.clear()
    return END

async def cb_pay_ok(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id):
        return
    pay_id = int(q.data.replace("pok_", ""))
    pay = db.get_payment(pay_id)
    if not pay or pay["status"] != "pending":
        await q.answer("Bu tolov allaqachon hal qilingan!", show_alert=True)
        return
    days = int(db.gs("sub_days") or "30")
    db.resolve_payment(pay_id, "approved")
    db.give_sub(pay["user_id"], days)
    await q.edit_message_caption(
        f"TASDIQLANDI\n\n{q.message.caption}", parse_mode=H
    )
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            f"🎉 <b>Tolovingiz tasdiqlandi!</b>\n\n"
            f"{days} kunlik obuna faollashtirildi!\n"
            f"Endi kino kodini yuboring!",
            parse_mode=H, reply_markup=kb.user_kb()
        )
    except Exception:
        pass

async def cb_pay_no(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id):
        return
    pay_id = int(q.data.replace("pno_", ""))
    pay = db.get_payment(pay_id)
    if not pay or pay["status"] != "pending":
        await q.answer("Bu tolov allaqachon hal qilingan!", show_alert=True)
        return
    db.resolve_payment(pay_id, "rejected")
    await q.edit_message_caption(
        f"BEKOR QILINDI\n\n{q.message.caption}", parse_mode=H
    )
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            "Tolovingiz tasdiqlanmadi.\nNototgri chek yoki summa.\nQayta urinib koring.",
            reply_markup=kb.user_kb()
        )
    except Exception:
        pass

# ═══════════════════════════════
# ADMIN — STATISTIKA
# ═══════════════════════════════

async def msg_stats(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    s = db.user_stats()
    mc = db.movie_count()
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
        f"👤 Jami: <b>{s['total']} ta</b>",
        parse_mode=H
    )

# ═══════════════════════════════
# ADMIN — KINOLAR
# ═══════════════════════════════

async def msg_movies(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🎬 <b>Kinolar bomidasiz:</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )

async def cb_mv_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bomidasiz:</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "🎬 <b>Kino qoshish</b>\n\nKino kodini kiriting:\n"
        "<i>Masalan: 101, 202, 350</i>\n\nBekor: /cancel",
        parse_mode=H
    )
    return S_MV_CODE

async def st_mv_code(update: Update, ctx):
    code = update.message.text.strip()
    existing = db.get_movie(code)
    if existing:
        title = existing["title"] or "—"
        await update.message.reply_text(
            f"{code} kodi mavjud! Sarlavha: {title}\n\n"
            f"Davom etsangiz yangilanadi.\n\nMessage ID yuboring:",
        )
    else:
        await update.message.reply_text(
            f"Kod: <b>{code}</b>\n\n"
            f"Kino kanal Message ID sini yuboring:\n\n"
            f"Qanday olish: kanalda postga ong klik - Copy Link\n"
            f"Link oxiridagi raqam = Message ID\n"
            f"Masalan: .../45 - ID = 45",
            parse_mode=H
        )
    ctx.user_data["mv_code"] = code
    return S_MV_MSGID

async def st_mv_msgid(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam yuboring! Qayta:")
        return S_MV_MSGID
    ctx.user_data["mv_msgid"] = t
    await update.message.reply_text(
        "Kino sarlavhasini yuboring:\n<i>Otkazish uchun: - yuboring</i>",
        parse_mode=H
    )
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
                from_chat_id=ch,
                message_id=int(msgid)
            )
            test_text = "\n\nTest korinishi yuqorida:"
        except Exception as e:
            test_text = f"\n\nTest xato: {e}"
    await update.message.reply_text(
        f"Kino qoshildi!\n\n"
        f"Kod: <code>{code}</code>\n"
        f"Message ID: <code>{msgid}</code>\n"
        f"Sarlavha: {title or '—'}{test_text}",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    ctx.user_data.clear()
    return END

async def cb_mv_edit(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bomidasiz:</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Tahrirlash uchun kino kodini kiriting:\n\nBekor: /cancel"
    )
    return S_ED_OLD

async def st_ed_old(update: Update, ctx):
    code = update.message.text.strip()
    m = db.get_movie(code)
    if not m:
        await update.message.reply_text(f"{code} topilmadi! Qayta:")
        return S_ED_OLD
    ctx.user_data["ed_old"] = code
    await update.message.reply_text(
        f"Topildi: <b>{m['title'] or code}</b>\n"
        f"Hozirgi ID: <code>{m['msg_id']}</code>\n\nYangi kodni yuboring:",
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
        ctx.user_data["ed_old"],
        ctx.user_data["ed_code"],
        ctx.user_data["ed_msgid"],
        title
    )
    await update.message.reply_text("Kino yangilandi!", reply_markup=kb.movies_kb())
    ctx.user_data.clear()
    return END

async def cb_mv_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bomidasiz:</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Ochirmoqchi bolgan kino kodini kiriting:\n\nBekor: /cancel"
    )
    return S_DEL

async def st_del(update: Update, ctx):
    code = update.message.text.strip()
    if db.del_movie(code):
        await update.message.reply_text(
            f"<b>{code}</b> ochiriildi!", parse_mode=H,
            reply_markup=kb.movies_kb()
        )
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
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Orqaga", callback_data="mv_back")
        ]])
    )

async def cb_mv_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bomi</b>", parse_mode=H,
        reply_markup=kb.movies_kb()
    )

# ═══════════════════════════════
# ADMIN — KANALLAR
# ═══════════════════════════════

async def msg_channels(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    chs = db.get_channels()
    await update.message.reply_text(
        f"🔒 <b>Majburiy obuna kanallar</b>\n\nHozirda: <b>{len(chs)} ta</b>",
        parse_mode=H, reply_markup=kb.channels_kb()
    )

async def cb_ch_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Kanal ID yuboring:\n\n"
        "• Username: <code>@mykanal</code>\n"
        "• ID: <code>-1001234567890</code>\n\n"
        "Kanal ID olish: @JsonDumpBot ga forward qiling\n\n"
        "Botni kanalga admin qilib qoshing!\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    return S_CH_ID

async def st_ch_id(update: Update, ctx):
    text = update.message.text.strip()
    if not (text.startswith("@") or text.startswith("-100")):
        await update.message.reply_text(
            "Notogri format!\n\n"
            "Faqat Telegram kanal:\n"
            "• <code>@mykanal</code>\n"
            "• <code>-1001234567890</code>\n\n"
            "Qayta yuboring:",
            parse_mode=H
        )
        return S_CH_ID
    ctx.user_data["ch_id"] = text
    await update.message.reply_text(
        "Kanal nomini yuboring:\n<i>Bu nom tugmada korinadi</i>",
        parse_mode=H
    )
    return S_CH_TITLE

async def st_ch_title(update: Update, ctx):
    ctx.user_data["ch_title"] = update.message.text.strip()
    ch_id = ctx.user_data["ch_id"]
    if ch_id.startswith("@"):
        auto_link = "https://t.me/" + ch_id[1:]
    else:
        auto_link = ""
    ctx.user_data["ch_auto_link"] = auto_link
    hint = "Havola yuboring yoki - yuboring (avtomatik):" if auto_link else "Kanal havolasini yuboring:"
    await update.message.reply_text(
        f"{hint}\n<i>Masalan: https://t.me/mykanal</i>",
        parse_mode=H
    )
    return S_CH_LINK

async def st_ch_link(update: Update, ctx):
    text = update.message.text.strip()
    if text == "-":
        link = ctx.user_data.get("ch_auto_link", "")
    else:
        link = text
    db.add_channel(ctx.user_data["ch_id"], ctx.user_data["ch_title"], link)
    await update.message.reply_text(
        f"Kanal qoshildi!\n\n"
        f"ID: <code>{ctx.user_data['ch_id']}</code>\n"
        f"Nom: {ctx.user_data['ch_title']}",
        parse_mode=H, reply_markup=kb.channels_kb()
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
    lines = [f"📋 <b>Majburiy kanallar ({len(chs)} ta):</b>\n"]
    for c in chs:
        lines.append(f"• {c['title']} | <code>{c['channel_id']}</code>")
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
    lines = [f"📋 <b>Majburiy kanallar ({len(chs)} ta):</b>\n"]
    for c in chs:
        lines.append(f"• {c['title']} | <code>{c['channel_id']}</code>")
    await q.edit_message_text(
        "\n".join(lines), parse_mode=H,
        reply_markup=kb.channel_list_kb(chs)
    )

async def cb_dch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id):
        return
    ch_id = int(q.data.replace("dch_", ""))
    if db.del_channel(ch_id):
        await q.answer("Kanal ochirildi!", show_alert=True)
        chs = db.get_channels()
        if not chs:
            await q.edit_message_text(
                "Kanallar yoq.", reply_markup=kb.channels_kb()
            )
            return
        lines = [f"📋 <b>Majburiy kanallar ({len(chs)} ta):</b>\n"]
        for c in chs:
            lines.append(f"• {c['title']} | <code>{c['channel_id']}</code>")
        await q.edit_message_text(
            "\n".join(lines), parse_mode=H,
            reply_markup=kb.channel_list_kb(chs)
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
    if not db.is_admin(update.effective_user.id):
        return
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
    if not db.is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "👮 <b>Adminlar bomi</b>\n\nYangi admin qoshish yoki ochirish mumkin.",
        parse_mode=H, reply_markup=kb.admins_kb()
    )

async def cb_adm_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Yangi admin Telegram ID sini yuboring:\n\n"
        "ID olish: @userinfobot ga /start\n\nBekor: /cancel"
    )
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
    await update.message.reply_text(
        f"<code>{uid}</code> admin qoshildi!",
        parse_mode=H, reply_markup=kb.admins_kb()
    )
    try:
        await ctx.bot.send_message(uid, "Siz admin qilib tayinlandingiz!")
    except Exception:
        pass
    return END

async def cb_adm_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Admin Telegram ID sini yuboring:\n\nBekor: /cancel"
    )
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
        await update.message.reply_text(
            f"<code>{uid}</code> ochirildi!",
            parse_mode=H, reply_markup=kb.admins_kb()
        )
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
    if not db.is_admin(update.effective_user.id):
        return
    count = len(db.all_user_ids())
    await update.message.reply_text(
        f"📨 <b>Xabar yuborish</b>\n\nJami: <b>{count} ta</b>\n\nXabar turini tanlang:",
        parse_mode=H, reply_markup=kb.broadcast_kb()
    )

async def cb_bc_text(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Barcha userlarga yuboriladigan xabarni yozing:\n\nBekor: /cancel"
    )
    return S_BC_TEXT

async def cb_bc_fwd(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Forward qilinadigan xabarni yuboring:\n\nBekor: /cancel"
    )
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
            try:
                await msg.edit_text(f"Yuborilmoqda: {i+1}/{len(users)}")
            except Exception:
                pass
        await asyncio.sleep(0.04)
    await msg.edit_text(
        f"Broadcast tugadi!\n\nYuborildi: {sent} ta\nXatolik: {failed} ta"
    )
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
            try:
                await msg.edit_text(f"Forward: {i+1}/{len(users)}")
            except Exception:
                pass
        await asyncio.sleep(0.04)
    await msg.edit_text(
        f"Forward tugadi!\n\nYuborildi: {sent} ta\nXatolik: {failed} ta"
    )
    return END

# ═══════════════════════════════
# ADMIN — SOZLAMALAR
# ═══════════════════════════════

async def msg_settings(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
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
    await q.edit_message_text(
        "Qaysi kartani sozlamoqchisiz?",
        reply_markup=kb.cards_kb()
    )

async def cb_sc_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    key = q.data.replace("sc_", "")
    ctx.user_data["st_key"] = "card_" + key
    names = {
        "uzcard": "UzCard raqami",
        "humo":   "Humo raqami",
        "visa":   "Visa raqami",
        "owner":  "Karta egasi ismi"
    }
    await q.edit_message_text(
        f"Yangi {names.get(key, key)} ni yuboring:\n\nBekor: /cancel"
    )
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
        f"Yangi narxni yuboring (faqat raqam):\n\nBekor: /cancel",
        parse_mode=H
    )
    return S_ST_PRICE

async def st_save_price(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam! Masalan: 15000")
        return S_ST_PRICE
    db.ss("sub_price", t)
    await update.message.reply_text(
        f"Narx {int(t):,} som saqlandi!\n\n"
        f"Kunni ozgartirmoqchimisiz? (raqam yuboring, ozgarmasa - yuboring):",
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
                f"Muddat {t} kun saqlandi!", reply_markup=kb.settings_kb()
            )
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
        f"Hozirgi kino kanal: <code>{cur}</code>\n\n"
        f"Yangi kanal ID yuboring:\n"
        f"Masalan: -1001234567890\n\n"
        f"Kanal ID olish: @JsonDumpBot ga forward qiling\n\n"
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
        f"Hozirgi xush kelibsiz matni:\n<i>{cur}</i>\n\n"
        f"Yangi matnni yuboring:\n\nBekor: /cancel",
        parse_mode=H
    )
    return S_ST_WELCOME

async def st_save_welcome(update: Update, ctx):
    db.ss("welcome_text", update.message.text.strip())
    await update.message.reply_text("Saqlandi!", reply_markup=kb.settings_kb())
    return END

async def cmd_clear_cache(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    ctx.user_data.clear()
    ctx.chat_data.clear()
    await update.message.reply_text(
        "Kesh tozalandi!", reply_markup=kb.admin_kb()
    )

# ═══════════════════════════════
# UMUMIY
# ═══════════════════════════════

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
    # Kanal qoshish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_ch_add, pattern="^ch_add$")],
        states={
            S_CH_ID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_id)],
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

    # Start
    if os.environ.get("RENDER") == "true":
        logging.info("Webhook rejimida (Render)...")
        app.run_webhook(
            listen="0.0.0.0", port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        logging.info("Polling rejimida (local)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
