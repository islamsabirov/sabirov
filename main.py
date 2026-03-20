"""
KINO BOT v2.0 — main.py
Barcha funksiyalar: user, admin, to'lov, kino
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

H = ParseMode.HTML
END = ConversationHandler.END

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
                await ctx.bot.send_photo(aid, photo=photo, caption=caption, parse_mode=H, reply_markup=markup)
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
        await update.message.reply_text("❌ Bekor qilindi.")
    return END


async def cb_cancel(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    await q.edit_message_text("❌ Bekor qilindi.")


# ══════════ /start ══════════

async def cmd_start(update: Update, ctx):
    u = update.effective_user
    db.add_user(u.id, u.first_name, u.username or "")
    unsubbed = await check_subs(ctx.bot, u.id)
    if unsubbed:
        await update.message.reply_text(
            "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            "Obuna bo'lgach, <b>✅ Tekshirish</b> tugmasini bosing.",
            parse_mode=H, reply_markup=kb.sub_kb(unsubbed)
        )
        return
    if db.is_admin(u.id):
        await update.message.reply_text(
            f"👑 <b>Salom, {u.first_name}!</b>\n\n🤖 Admin paneliga xush kelibsiz.\nQuyidagi menyudan foydalaning 👇",
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
        await q.answer("❌ Hali obuna bo'lmadingiz!\nYuqoridagi tugmalardan kanallarga o'ting.", show_alert=True)
        return
    u = q.from_user
    await q.edit_message_text("✅ <b>Obuna tasdiqlandi!</b>\n\n🎬 Kino kodini yuboring:", parse_mode=H)
    if db.is_admin(u.id):
        await ctx.bot.send_message(u.id, "👇", reply_markup=kb.admin_kb())
    else:
        await ctx.bot.send_message(u.id, "👇", reply_markup=kb.user_kb())


# ══════════ KINO QIDIRISH ══════════

async def msg_find_movie(update: Update, ctx):
    u = update.effective_user
    code = update.message.text.strip()
    unsubbed = await check_subs(ctx.bot, u.id)
    if unsubbed:
        await update.message.reply_text("📢 Avval kanallarga obuna bo'ling!", reply_markup=kb.sub_kb(unsubbed))
        return
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text(
            f"❌ <b>{code}</b> kodli kino topilmadi.\n<i>Kodni to'g'ri yozdingizmi?</i>",
            parse_mode=H
        )
        return
    ch = get_movie_ch()
    if not ch:
        await update.message.reply_text("⚠️ Kino kanal hali sozlanmagan.\nAdmin bilan bog'laning.")
        return
    try:
        await ctx.bot.copy_message(chat_id=u.id, from_chat_id=ch, message_id=int(movie["msg_id"]))
    except TelegramError as e:
        logging.error(f"Copy xato: {e}")
        await update.message.reply_text("⚠️ Kinoni yuborishda xatolik yuz berdi.\nAdmin bilan bog'laning.")


# ══════════ PROFIL ══════════

async def msg_profile(update: Update, ctx):
    u = update.effective_user
    sub = db.has_sub(u.id)
    info = db.sub_info(u.id)
    price = db.gs("sub_price") or "15000"
    days = db.gs("sub_days") or "30"
    sub_text = f"✅ Faol ({info['expires_at'][:10]} gacha)" if sub and info else "❌ Obuna yo'q"
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Obuna sotib olish", callback_data="buy_sub")]])
    await update.message.reply_text(
        f"👤 <b>Mening profilim</b>\n\n"
        f"🆔 ID: <code>{u.id}</code>\n"
        f"👤 Ism: {u.first_name}\n"
        f"💎 Obuna holati: {sub_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 {days} kunlik obuna: <b>{int(price):,} so'm</b>",
        parse_mode=H, reply_markup=markup
    )


async def msg_help(update: Update, ctx):
    await update.message.reply_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "🎬 <b>Kino qidirish:</b>\nKino kodini yuboring — bot kinoni yuboradi.\n\n"
        "💳 <b>Obuna:</b>\n👤 Profilim → Obuna sotib olish\n\n"
        "❓ <b>Muammo bo'lsa:</b>\nAdmin bilan bog'laning.",
        parse_mode=H
    )


# ══════════ TO'LOV ══════════

async def cb_buy_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price = db.gs("sub_price") or "15000"
    days = db.gs("sub_days") or "30"
    await q.edit_message_text(
        f"💳 <b>Obuna sotib olish</b>\n\n📅 Muddat: <b>{days} kun</b>\n💰 Narx: <b>{int(price):,} so'm</b>\n\nTo'lov usulini tanlang 👇",
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
        f"💳 <b>{names.get(card_type, '')} orqali to'lov</b>\n\n"
        f"💰 To'lov summasi: <b>{int(price):,} so'm</b>\n\n"
        f"🏦 Karta raqami:\n<code>{card}</code>\n"
        f"👤 Karta egasi: <b>{owner}</b>\n\n"
        f"📌 Qadamlar:\n1️⃣ Yuqoridagi kartaga pul o'tkazing\n2️⃣ To'lov chekining rasmini yuboring 👇",
        parse_mode=H, reply_markup=kb.back_kb("x")
    )
    return S_PAY


async def rcv_screenshot(update: Update, ctx):
    u = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("📸 Iltimos, to'lov chekining <b>rasmini</b> yuboring!", parse_mode=H)
        return S_PAY
    card_type = ctx.user_data.get("pay_card", "uzcard")
    price = int(db.gs("sub_price") or "15000")
    fid = update.message.photo[-1].file_id
    pay_id = db.add_payment(u.id, price, card_type, fid)
    if not pay_id:
        await update.message.reply_text(
            "⚠️ <b>Sizda kutilayotgan to'lov mavjud!</b>\n\nAdmin tasdiqlashini kuting.",
            parse_mode=H, reply_markup=kb.user_kb()
        )
        return END
    await update.message.reply_text(
        "⏳ <b>To'lovingiz qabul qilindi!</b>\n\nAdmin tez orada ko'rib chiqadi.\nTasdiqlangach sizga xabar keladi. ✅",
        parse_mode=H, reply_markup=kb.user_kb()
    )
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}
    # ✅ TO'G'IRLANGAN — apostrofli so'z o'zgaruvchiga olindi
    uname = u.username if u.username else "yoq"
    caption = (
        f"💳 <b>Yangi to'lov so'rovi!</b>\n\n"
        f"👤 Foydalanuvchi: <a href='tg://user?id={u.id}'>{u.first_name}</a>\n"
        f"🆔 ID: <code>{u.id}</code>\n"
        f"🔖 Username: @{uname}\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n"
        f"🏦 Karta: <b>{names.get(card_type, card_type)}</b>\n"
        f"🔢 To'lov #: <b>{pay_id}</b>"
    )
    await send_to_admins(ctx, photo=fid, caption=caption, markup=kb.pay_confirm_kb(pay_id))
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
        await q.answer("⚠️ Bu to'lov allaqachon hal qilingan!", show_alert=True)
        return
    days = int(db.gs("sub_days") or "30")
    db.resolve_payment(pay_id, "approved")
    db.give_sub(pay["user_id"], days)
    await q.edit_message_caption(f"✅ <b>TASDIQLANDI</b>\n\n{q.message.caption}", parse_mode=H)
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            f"🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n💎 <b>{days} kunlik obuna</b> faollashtirildi!\n\n🎬 Endi kino kodini yuboring!",
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
        await q.answer("⚠️ Bu to'lov allaqachon hal qilingan!", show_alert=True)
        return
    db.resolve_payment(pay_id, "rejected")
    await q.edit_message_caption(f"❌ <b>BEKOR QILINDI</b>\n\n{q.message.caption}", parse_mode=H)
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            "❌ <b>To'lovingiz tasdiqlanmadi.</b>\n\nSabab: Noto'g'ri chek yoki summa.\n\nQayta urinib ko'ring.",
            parse_mode=H, reply_markup=kb.user_kb()
        )
    except Exception:
        pass


# ══════════ STATISTIKA ══════════

async def msg_stats(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    s = db.user_stats()
    mc = db.movie_count()
    await update.message.reply_text(
        f"📊 <b>Bot statistikasi</b>\n\n"
        f"👥 <b>Yangi foydalanuvchilar:</b>\n• Bugun: +{s['today']} ta\n• 7 kun: +{s['week']} ta\n• 30 kun: +{s['month']} ta\n\n"
        f"📈 <b>Faollik:</b>\n• Oxirgi 24 soat: {s['act24']} ta\n• Oxirgi 7 kun: {s['act7']} ta\n• Oxirgi 30 kun: {s['act30']} ta\n\n"
        f"🎬 <b>Kinolar soni: {mc} ta</b>\n👤 <b>Jami foydalanuvchilar: {s['total']} ta</b>",
        parse_mode=H
    )


# ══════════ KINOLAR ══════════

async def msg_movies(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🎬 <b>Kinolar bo'limi</b>\n\nQuyidagi amallardan birini tanlang:", parse_mode=H, reply_markup=kb.movies_kb())


async def cb_mv_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bo'limidasiz:</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    # Kod kiritish uchun alohida xabar
    await ctx.bot.send_message(
        q.from_user.id,
        "🎬 <b>Kino qo'shish</b>\n\nKino kodini kiriting:\n<i>Masalan: 101, 202, 350</i>\n\n❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_MV_CODE


async def st_mv_code(update: Update, ctx):
    code = update.message.text.strip()
    existing = db.get_movie(code)
    if existing:
        await update.message.reply_text(
            f"⚠️ <b>{code}</b> kodi allaqachon mavjud!\nSarlavha: {existing['title'] or '—'}\n\nDavom etsangiz yangilanadi.\n\n<b>Message ID</b> yuboring — 2/3:",
            parse_mode=H
        )
    else:
        await update.message.reply_text(
            f"✅ Kod: <b>{code}</b>\n\n<b>Kino kanal Message ID</b> sini yuboring — 2/3:\n\n"
            f"💡 <i>Kino kanalida postga o'ng klik → Copy Link\nLink oxiridagi raqam = Message ID\nMasalan: .../45 → ID = 45</i>",
            parse_mode=H
        )
    ctx.user_data["mv_code"] = code
    return S_MV_MSGID


async def st_mv_msgid(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Message ID faqat raqamdan iborat!\nQayta yuboring:")
        return S_MV_MSGID
    ctx.user_data["mv_msgid"] = t
    await update.message.reply_text("📝 Kino sarlavhasini yuboring — 3/3:\n\n<i>O'tkazish uchun: - yuboring</i>", parse_mode=H)
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
            await ctx.bot.copy_message(chat_id=update.effective_user.id, from_chat_id=ch, message_id=int(msgid))
            test_text = "\n\n✅ Yuqorida test ko'rinishi:"
        except Exception as e:
            test_text = f"\n\n⚠️ Test xato: {e}"
    await update.message.reply_text(
        f"✅ <b>Kino qo'shildi!</b>\n\n🔢 Kod: <code>{code}</code>\n🆔 Message ID: <code>{msgid}</code>\n📌 Sarlavha: {title or '—'}{test_text}",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    ctx.user_data.clear()
    return END


async def cb_mv_edit(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bo'limidasiz:</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "📝 <b>Kino tahrirlash</b>\n\nTahrirlamoqchi bo'lgan kino kodini kiriting:\n\n❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ED_OLD


async def st_ed_old(update: Update, ctx):
    code = update.message.text.strip()
    m = db.get_movie(code)
    if not m:
        await update.message.reply_text(f"❌ <b>{code}</b> topilmadi!\nQayta yuboring:", parse_mode=H)
        return S_ED_OLD
    ctx.user_data["ed_old"] = code
    await update.message.reply_text(
        f"✅ Topildi: <b>{m['title'] or code}</b>\nHozirgi ID: <code>{m['msg_id']}</code>\n\nYangi kodni yuboring:",
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
    db.update_movie(ctx.user_data["ed_old"], ctx.user_data["ed_code"], ctx.user_data["ed_msgid"], title)
    await update.message.reply_text("✅ <b>Kino yangilandi!</b>", parse_mode=H, reply_markup=kb.movies_kb())
    ctx.user_data.clear()
    return END


async def cb_mv_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🎬 <b>Kinolar bo'limidasiz:</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "🗑 <b>Kino o'chirish</b>\n\nO'chirmoqchi bo'lgan kino kodini kiriting:\n\n❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_DEL


async def st_del(update: Update, ctx):
    code = update.message.text.strip()
    if db.del_movie(code):
        await update.message.reply_text(f"✅ <b>{code}</b> o'chirildi!", parse_mode=H, reply_markup=kb.movies_kb())
    else:
        await update.message.reply_text(f"❌ <b>{code}</b> topilmadi!\nQayta yuboring:", parse_mode=H)
        return S_DEL
    return END


async def cb_mv_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    movies = db.get_movies(30)
    if not movies:
        await q.edit_message_text("🎬 Kino bazasi bo'sh.", reply_markup=kb.movies_kb())
        return
    lines = [f"📋 <b>Kinolar ro'yxati ({len(movies)} ta):</b>\n"]
    for m in movies:
        lines.append(f"🔢 <code>{m['code']}</code> | {m['title'] or '—'} | 👁 {m['views']} marta")
    await q.edit_message_text("\n".join(lines), parse_mode=H, reply_markup=kb.back_kb("mv_back"))


async def cb_mv_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🎬 <b>Kinolar bo'limi</b>", parse_mode=H, reply_markup=kb.movies_kb())


# ══════════ KANALLAR ══════════

async def msg_channels(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    chs = db.get_channels()
    await update.message.reply_text(
        f"🔒 <b>Majburiy obuna kanallar</b>\n\nHozirda: <b>{len(chs)} ta</b> kanal\n\nQuyidagi amallardan birini tanlang:",
        parse_mode=H, reply_markup=kb.channels_kb()
    )


async def cb_ch_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Telegram kanal yoki guruh ID sini yuboring:\n\n"
        "📌 <b>Formatlar:</b>\n"
        "• Username: <code>@mykanal</code>\n"
        "• ID: <code>-1001234567890</code>\n\n"
        "💡 Kanal ID olish: @JsonDumpBot ga kanaldan post forward qiling\n\n"
        "⚠️ Botni kanalga <b>admin</b> qilib qo'shing!\n\n"
        "❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_CH_ID


async def st_ch_id(update: Update, ctx):
    text = update.message.text.strip()
    # Faqat Telegram kanal/guruh qabul qilish
    if not (text.startswith("@") or text.startswith("-100")):
        await update.message.reply_text(
            "❌ Noto'g'ri format!\n\n"
            "Faqat Telegram kanal/guruh:\n"
            "• <code>@mykanal</code>\n"
            "• <code>-1001234567890</code>\n\n"
            "Qayta yuboring:",
            parse_mode=H
        )
        return S_CH_ID
    ctx.user_data["ch_id"] = text
    await update.message.reply_text(
        "📌 Kanal nomini yuboring:\n<i>Bu nom tugmada ko'rinadi</i>",
        parse_mode=H
    )
    return S_CH_TITLE


async def st_ch_title(update: Update, ctx):
    ctx.user_data["ch_title"] = update.message.text.strip()
    ch_id = ctx.user_data["ch_id"]
    # Havolani avtomatik yaratish
    if ch_id.startswith("@"):
        auto_link = f"https://t.me/{ch_id[1:]}"
    else:
        auto_link = ""
    ctx.user_data["ch_auto_link"] = auto_link
    await update.message.reply_text(
        f"🔗 Kanal havolasini yuboring:\n"
        f"<i>Masalan: https://t.me/mykanal</i>\n\n"
        f"{'💡 Avtomatik: <code>' + auto_link + '</code> — o\\'zgartirmasangiz - yuboring' if auto_link else ''}",
        parse_mode=H
    )
    return S_CH_LINK


async def st_ch_link(update: Update, ctx):
    text = update.message.text.strip()
    # Avtomatik havola
    if text == "-" and ctx.user_data.get("ch_auto_link"):
        link = ctx.user_data["ch_auto_link"]
    else:
        link = text
    db.add_channel(ctx.user_data["ch_id"], ctx.user_data["ch_title"], link)
    await update.message.reply_text(
        f"✅ <b>Kanal qo'shildi!</b>\n\n"
        f"🆔 ID: <code>{ctx.user_data['ch_id']}</code>\n"
        f"📌 Nom: {ctx.user_data['ch_title']}\n"
        f"🔗 Havola: {link}",
        parse_mode=H, reply_markup=kb.channels_kb()
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
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    lines = [f"📋 <b>Majburiy kanallar ({len(chs)} ta):</b>\n"]
    buttons = []
    for c in chs:
        lines.append(f"• {c['title']} | <code>{c['channel_id']}</code>")
        buttons.append([InlineKeyboardButton(f"🗑 {c['title']} ni o'chirish", callback_data=f"delch_{c['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="ch_back")])
    await q.edit_message_text(
        "\n".join(lines),
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_ch_delete_inline(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id):
        return
    ch_id = int(q.data.replace("delch_", ""))
    if db.del_channel(ch_id):
        await q.answer("✅ Kanal o'chirildi!", show_alert=True)
        # Ro'yxatni yangilash
        chs = db.get_channels()
        if not chs:
            await q.edit_message_text("📋 Kanallar yo'q.", reply_markup=kb.channels_kb())
            return
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        lines = [f"📋 <b>Majburiy kanallar ({len(chs)} ta):</b>\n"]
        buttons = []
        for c in chs:
            lines.append(f"• {c['title']} | <code>{c['channel_id']}</code>")
            buttons.append([InlineKeyboardButton(f"🗑 {c['title']} ni o'chirish", callback_data=f"delch_{c['id']}")])
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="ch_back")])
        await q.edit_message_text("\n".join(lines), parse_mode=H, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await q.answer("❌ Topilmadi.", show_alert=True)


async def cb_ch_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    await q.edit_message_text(
        f"🔒 <b>Majburiy obuna kanallar</b>\n\nHozirda: <b>{len(chs)} ta</b> kanal",
        parse_mode=H,
        reply_markup=kb.channels_kb()
    )


async def cb_ch_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await q.edit_message_text("❌ O'chirish uchun kanallar yo'q.", reply_markup=kb.channels_kb())
        return
    # Ro'yxatni ko'rsatish
    await cb_ch_list(update, ctx)


async def cmd_delch(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("❌ Format: /delch 1")
        return
    if db.del_channel(int(ctx.args[0])):
        await update.message.reply_text("✅ Kanal o'chirildi!", reply_markup=kb.channels_kb())
    else:
        await update.message.reply_text("❌ Kanal topilmadi.")


# ══════════ ADMINLAR ══════════

async def msg_admins(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "👮 <b>Adminlar bo'limi</b>\n\nYangi admin qo'shish yoki o'chirish mumkin.",
        parse_mode=H, reply_markup=kb.admins_kb()
    )


async def cb_adm_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "➕ <b>Admin qo'shish</b>\n\nTelegram ID yuboring:\n\n💡 ID olish: @userinfobot ga /start\n\n❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ADM_ADD


async def st_adm_add(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam!\nQayta yuboring:")
        return S_ADM_ADD
    uid = int(t)
    if uid in ADMIN_IDS:
        await update.message.reply_text("⚠️ Bu asosiy admin!")
        return END
    db.add_admin(uid, f"Admin {uid}")
    await update.message.reply_text(f"✅ <code>{uid}</code> admin qo'shildi!", parse_mode=H, reply_markup=kb.admins_kb())
    try:
        await ctx.bot.send_message(uid, "👑 Siz admin qilib tayinlandingiz!")
    except Exception:
        pass
    return END


async def cb_adm_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("➖ <b>Adminni o'chirish</b>\n\nAdmin Telegram ID sini yuboring:\n\n❌ Bekor: /cancel", parse_mode=H)
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
        await update.message.reply_text(f"✅ <code>{uid}</code> o'chirildi!", parse_mode=H, reply_markup=kb.admins_kb())
    else:
        await update.message.reply_text("❌ Bu ID topilmadi.")
    return END


async def cb_adm_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    total = len(ADMIN_IDS) + len(db.get_admins())
    await q.edit_message_text(
        f"📋 <b>Adminlar ro'yxati</b>\n\nJami: <b>{total} ta</b> admin",
        parse_mode=H, reply_markup=kb.admins_kb()
    )


# ══════════ BROADCAST ══════════

async def msg_broadcast(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    users_count = len(db.all_user_ids())
    await update.message.reply_text(
        f"📨 <b>Xabar yuborish</b>\n\n👤 Jami: <b>{users_count} ta</b>\n\nXabar turini tanlang:",
        parse_mode=H, reply_markup=kb.broadcast_kb()
    )


async def cb_bc_text(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("💬 <b>Broadcast</b>\n\nBarcha userlarga yuboriladigan xabarni yozing:\n\n❌ Bekor: /cancel", parse_mode=H)
    return S_BC_TEXT


async def cb_bc_fwd(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("📨 <b>Forward broadcast</b>\n\nForward qilinadigan xabarni yuboring:\n\n❌ Bekor: /cancel", parse_mode=H)
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
    await msg.edit_text(f"✅ <b>Broadcast tugadi!</b>\n\n📨 Yuborildi: {sent} ta\n❌ Xatolik: {failed} ta", parse_mode=H)
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
    await msg.edit_text(f"✅ <b>Forward tugadi!</b>\n\n📨 Yuborildi: {sent} ta\n❌ Xatolik: {failed} ta", parse_mode=H)
    return END


# ══════════ SOZLAMALAR ══════════

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
        f"💰 <b>Obuna:</b> {int(price):,} so'm / {days} kun\n"
        f"🎬 <b>Kino kanal:</b> <code>{movch}</code>\n\n"
        f"💳 <b>UzCard:</b> <code>{uzcard}</code>\n"
        f"💳 <b>Humo:</b> <code>{humo}</code>\n"
        f"💳 <b>Visa:</b> <code>{visa}</code>\n"
        f"👤 <b>Karta egasi:</b> {owner}\n\n"
        f"📝 <b>Xush kelibsiz:</b>\n<i>{welcome}</i>",
        parse_mode=H, reply_markup=kb.settings_kb()
    )


async def cmd_clear_cache(update: Update, ctx):
    """Kesh tozalash — admin buyrug'i"""
    if not db.is_admin(update.effective_user.id):
        return
    ctx.user_data.clear()
    ctx.chat_data.clear()
    await update.message.reply_text(
        "🧹 <b>Kesh tozalandi!</b>\n\nBarcha vaqtinchalik ma'lumotlar o'chirildi.",
        parse_mode=H,
        reply_markup=kb.admin_kb()
    )


async def cb_st_cards(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("💳 <b>Karta sozlamalari</b>\n\nQaysi kartani sozlamoqchisiz?", parse_mode=H, reply_markup=kb.cards_kb())


async def cb_sc_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    key = q.data.replace("sc_", "")
    ctx.user_data["st_key"] = f"card_{key}"
    names = {"uzcard": "UzCard raqami", "humo": "Humo raqami", "visa": "Visa raqami", "owner": "Karta egasining ismi"}
    await q.edit_message_text(f"✏️ Yangi <b>{names.get(key, key)}</b> ni yuboring:\n\n❌ Bekor: /cancel", parse_mode=H)
    return S_ST_CARD


async def st_save_card(update: Update, ctx):
    db.ss(ctx.user_data["st_key"], update.message.text.strip())
    await update.message.reply_text("✅ Saqlandi!", reply_markup=kb.settings_kb())
    ctx.user_data.clear()
    return END


async def cb_st_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("💳 <b>Karta sozlamalari</b>", parse_mode=H, reply_markup=kb.cards_kb())


async def cb_st_price(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price = db.gs("sub_price") or "15000"
    days  = db.gs("sub_days")  or "30"
    await q.edit_message_text(
        f"💰 <b>Obuna narxi/muddat</b>\n\nHozirgi: <b>{int(price):,} so'm / {days} kun</b>\n\nYangi narxni yuboring:\n<i>Masalan: 15000</i>\n\n❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_PRICE


async def st_save_price(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam!\nMasalan: 15000")
        return S_ST_PRICE
    db.ss("sub_price", t)
    await update.message.reply_text(
        f"✅ Narx <b>{int(t):,} so'm</b> saqlandi!\n\nKunni ham o'zgartirasizmi?\n(raqam yuboring, o'zgarmasa - yuboring):",
        parse_mode=H
    )
    ctx.user_data["wait_days"] = True
    return S_ST_PRICE


async def st_save_days(update: Update, ctx):
    t = update.message.text.strip()
    if ctx.user_data.get("wait_days"):
        if t != "-" and t.isdigit():
            db.ss("sub_days", t)
            await update.message.reply_text(f"✅ Muddat <b>{t} kun</b> saqlandi!", parse_mode=H, reply_markup=kb.settings_kb())
        else:
            await update.message.reply_text("✅ Muddat o'zgarmadi.", reply_markup=kb.settings_kb())
        ctx.user_data.clear()
        return END
    return END


async def cb_st_movch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("movie_ch") or MOVIE_CH or "Sozlanmagan"
    await q.edit_message_text(
        f"🎬 <b>Kino kanal ID</b>\n\nHozirgi: <code>{cur}</code>\n\nYangi kanal ID yuboring:\n<i>Masalan: -1001234567890</i>\n\n💡 @JsonDumpBot ga kanaldan forward qiling\n\n⚠️ Botni kanalga admin qilib qo'shing!\n\n❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_MOVCH


async def st_save_movch(update: Update, ctx):
    val = update.message.text.strip()
    db.ss("movie_ch", val)
    await update.message.reply_text(f"✅ Kino kanal saqlandi!\n<code>{val}</code>", parse_mode=H, reply_markup=kb.settings_kb())
    return END


async def cb_st_welcome(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("welcome_text") or "—"
    await q.edit_message_text(
        f"📝 <b>Xush kelibsiz matni</b>\n\nHozirgi:\n<i>{cur}</i>\n\nYangi matnni yuboring:\n\n❌ Bekor: /cancel",
        parse_mode=H
    )
    return S_ST_WELCOME


async def st_save_welcome(update: Update, ctx):
    db.ss("welcome_text", update.message.text.strip())
    await update.message.reply_text("✅ Xush kelibsiz matni saqlandi!", reply_markup=kb.settings_kb())
    return END


async def msg_orqaga(update: Update, ctx):
    """Orqaga tugmasi — /start ga qaytaradi"""
    ctx.user_data.clear()
    await cmd_start(update, ctx)


# ══════════ MAIN ══════════

def main():
    db.init_db()
    logging.info("✅ Database tayyor")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_pay_card, pattern="^pay_(uzcard|humo|visa)$")],
        states={S_PAY: [MessageHandler(filters.PHOTO, rcv_screenshot)]},
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mv_add, pattern="^mv_add$")],
        states={
            S_MV_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_code)],
            S_MV_MSGID: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_msgid)],
            S_MV_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_mv_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
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
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mv_del, pattern="^mv_del$")],
        states={S_DEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_del)]},
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_ch_add, pattern="^ch_add$")],
        states={
            S_CH_ID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_id)],
            S_CH_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_title)],
            S_CH_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_ch_link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
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

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("admin",  cmd_start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("delch",  cmd_delch))
    app.add_handler(CommandHandler("clearcache", cmd_clear_cache))

    app.add_handler(CallbackQueryHandler(cb_chk_sub,  pattern="^chk_sub$"))
    app.add_handler(CallbackQueryHandler(cb_buy_sub,  pattern="^buy_sub$"))
    app.add_handler(CallbackQueryHandler(cb_pay_ok,   pattern=r"^pok_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_no,   pattern=r"^pno_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mv_list,  pattern="^mv_list$"))
    app.add_handler(CallbackQueryHandler(cb_mv_back,  pattern="^mv_back$"))
    app.add_handler(CallbackQueryHandler(cb_ch_list,  pattern="^ch_list$"))
    app.add_handler(CallbackQueryHandler(cb_ch_del,   pattern="^ch_del$"))
    app.add_handler(CallbackQueryHandler(cb_ch_delete_inline, pattern=r"^delch_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_ch_back,  pattern="^ch_back$"))
    app.add_handler(CallbackQueryHandler(cb_adm_list, pattern="^adm_list$"))
    app.add_handler(CallbackQueryHandler(cb_st_cards, pattern="^st_cards$"))
    app.add_handler(CallbackQueryHandler(cb_st_back,  pattern="^st_back$"))
    app.add_handler(CallbackQueryHandler(cb_cancel,   pattern="^x$"))

    app.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"),      msg_stats))
    app.add_handler(MessageHandler(filters.Regex("^📨 Xabar yuborish$"),  msg_broadcast))
    app.add_handler(MessageHandler(filters.Regex("^🎬 Kinolar$"),          msg_movies))
    app.add_handler(MessageHandler(filters.Regex("^🔒 Kanallar$"),         msg_channels))
    app.add_handler(MessageHandler(filters.Regex("^👮 Adminlar$"),         msg_admins))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Sozlamalar$"),       msg_settings))
    app.add_handler(MessageHandler(filters.Regex("^◀️ Orqaga$"),           msg_orqaga))
    app.add_handler(MessageHandler(filters.Regex("^👤 Profilim$"),         msg_profile))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yordam$"),           msg_help))
    app.add_handler(MessageHandler(filters.Regex("^🎬 Kino qidirish$"),
        lambda u, c: u.message.reply_text("🎬 Kino kodini yuboring:")))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d+$"),
        msg_find_movie
    ))

    if os.environ.get("RENDER") == "true":
        logging.info("🚀 Webhook rejimida (Render)...")
        app.run_webhook(
            listen="0.0.0.0", port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        logging.info("🔄 Polling rejimida (local test)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
