"""
KINO BOT v5.0
Pro kinolar + Referral + Premium muddati + To'liq statistika
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
from telegram.error import TelegramError, BadRequest

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
    S_PRO_SET, S_PRO_UNSET,
    S_CH_ID, S_CH_TITLE, S_CH_LINK,
    S_ADM_ADD, S_ADM_DEL,
    S_BC_TEXT, S_BC_FWD,
    S_ST_CARD, S_ST_PRICE, S_ST_MOVCH, S_ST_WELCOME, S_ST_REFBONUS,
    S_GIVE_SUB_ID, S_GIVE_SUB_PLAN,
) = range(25)

CH_TYPE_KEY = "ch_type"

# ═══════════════════════════════
# YORDAMCHILAR
# ═══════════════════════════════

async def safe_edit_message_text(context, chat_id, message_id, text, parse_mode=None, reply_markup=None):
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return True
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return False
        raise
    except Exception as e:
        logging.error("Error editing message: %s", e)
        return False

async def safe_edit_message_caption(context, chat_id, message_id, caption, parse_mode=None, reply_markup=None):
    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return True
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return False
        raise
    except Exception as e:
        logging.error("Error editing caption: %s", e)
        return False

async def check_subs(bot, uid):
    result = []
    for ch in db.get_telegram_channels():
        try:
            m = await bot.get_chat_member(ch["channel_id"], uid)
            if m.status in ["left", "kicked"]:
                result.append(ch)
        except Exception:
            pass
    return result

async def must_subscribe(bot, uid):
    all_chs = db.get_channels()
    if not all_chs:
        return False, []
    unsubbed_telegram = await check_subs(bot, uid)
    non_telegram = [c for c in all_chs if c.get("type", "telegram") in ("private", "link")]
    show_channels = unsubbed_telegram + [
        c for c in non_telegram
        if c["id"] not in [x["id"] for x in unsubbed_telegram]
    ]
    blocked = len(unsubbed_telegram) > 0 or len(non_telegram) > 0
    return blocked, show_channels

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
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "Bekor qilindi."
    )

# ═══════════════════════════════
# START
# ═══════════════════════════════

async def cmd_start(update: Update, ctx):
    u = update.effective_user
    referral_by = None
    if ctx.args and ctx.args[0].startswith("ref"):
        try:
            referral_by = int(ctx.args[0][3:])
            if referral_by == u.id:
                referral_by = None
        except ValueError:
            referral_by = None

    is_new = db.add_user(u.id, u.first_name, u.username or "", referral_by)

    if referral_by and is_new:
        ref_user = db.get_user(referral_by)
        if ref_user:
            bonus = int(db.gs("referral_bonus") or "5")
            if ref_user["referral_count"] % bonus == 0:
                try:
                    await ctx.bot.send_message(
                        referral_by,
                        "Tabrik! " + str(bonus) + " ta referral to'ldingiz — 1 oy premium qo'shildi!"
                    )
                except Exception:
                    pass

    blocked, show_channels = await must_subscribe(ctx.bot, u.id)
    if blocked:
        await update.message.reply_text(
            "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna boling:</b>\n\n"
            "Obuna bolgach Tekshirish tugmasini bosing.",
            parse_mode=H, reply_markup=kb.sub_kb(show_channels)
        )
        return

    if db.is_admin(u.id):
        await update.message.reply_text(
            "<b>Salom, " + u.first_name + "!</b>\n\nAdmin paneliga xush kelibsiz. 👑",
            parse_mode=H, reply_markup=kb.admin_kb()
        )
    else:
        welcome = db.gs("welcome_text") or "Kino kodini yuboring"
        await update.message.reply_text(
            "🎬 <b>Salom, " + u.first_name + "!</b>\n\n" + welcome,
            parse_mode=H, reply_markup=kb.user_kb()
        )

async def cb_chk_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    blocked, show_channels = await must_subscribe(ctx.bot, u.id)
    if blocked:
        await q.answer("Hali barcha kanallarga obuna bolmadingiz!", show_alert=True)
        return
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "Obuna tasdiqlandi! Kino kodini yuboring."
    )
    mkb = kb.admin_kb() if db.is_admin(u.id) else kb.user_kb()
    await ctx.bot.send_message(u.id, "👇", reply_markup=mkb)

# ═══════════════════════════════
# USER — KINO QIDIRISH
# ═══════════════════════════════

async def msg_find_movie(update: Update, ctx):
    u = update.effective_user
    code = update.message.text.strip()

    blocked, show_channels = await must_subscribe(ctx.bot, u.id)
    if blocked:
        await update.message.reply_text(
            "📢 Avval kanallarga obuna boling!",
            reply_markup=kb.sub_kb(show_channels)
        )
        return

    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text(
            "❌ <b>" + code + "</b> kodli kino topilmadi.", parse_mode=H
        )
        return

    if movie.get("is_pro") and not db.has_sub(u.id):
        price_1m = db.gs("sub_price_1m") or "15000"
        price_3m = db.gs("sub_price_3m") or "40000"
        price_1y = db.gs("sub_price_1y") or "120000"
        text = (
            "💎 <b>Bu kino faqat Pro foydalanuvchilar uchun!</b>\n\n"
            "Pro obuna narxlari:\n"
            "📅 1 Oy — " + "{:,}".format(int(price_1m)) + " som\n"
            "📅 3 Oy — " + "{:,}".format(int(price_3m)) + " som\n"
            "📅 1 Yil — " + "{:,}".format(int(price_1y)) + " som\n\n"
            "Obuna sotib olish uchun Profilim tugmasini bosing."
        )
        await update.message.reply_text(
            text, parse_mode=H,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Obuna sotib olish", callback_data="buy_sub")
            ]])
        )
        return

    ch = get_movie_ch()
    if not ch:
        await update.message.reply_text("Kino kanal sozlanmagan. Admin bilan bog'laning.")
        return

    try:
        await ctx.bot.copy_message(
            chat_id=u.id,
            from_chat_id=ch,
            message_id=int(movie["msg_id"])
        )
        db.increment_views(code)
    except TelegramError as e:
        logging.error("Copy xato: %s", e)
        await update.message.reply_text("Kinoni yuborishda xatolik. Kino kodi: " + code)

# ═══════════════════════════════
# USER — PROFIL
# ═══════════════════════════════

async def msg_profile(update: Update, ctx):
    u = update.effective_user
    sub = db.has_sub(u.id)
    info = db.sub_info(u.id)
    user = db.get_user(u.id)

    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"

    if sub and info:
        plan_names = {"1_month": "1 Oy", "3_month": "3 Oy", "1_year": "1 Yil", "referral_bonus": "Referral Bonus"}
        plan = plan_names.get(info.get("plan", ""), "")
        expires = info['expires_at'][:10]
        sub_text = "Faol (" + expires + " gacha) — " + plan
    else:
        sub_text = "Obuna yo'q"

    ref_count = user["referral_count"] if user else 0

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("Obuna sotib olish", callback_data="buy_sub")
    ]])

    text = (
        "👤 <b>Mening profilim</b>\n\n"
        "ID: <code>" + str(u.id) + "</code>\n"
        "Ism: " + u.first_name + "\n"
        "Obuna: " + sub_text + "\n"
        "Referral: " + str(ref_count) + " ta\n\n"
        "━━━━━━━━━━━━━━━\n"
        "💰 <b>Obuna narxlari:</b>\n"
        "📅 1 Oy — " + "{:,}".format(int(price_1m)) + " som\n"
        "📅 3 Oy — " + "{:,}".format(int(price_3m)) + " som\n"
        "📅 1 Yil — " + "{:,}".format(int(price_1y)) + " som"
    )
    await update.message.reply_text(text, parse_mode=H, reply_markup=markup)

# ═══════════════════════════════
# USER — REFERRAL
# ═══════════════════════════════

async def msg_referral(update: Update, ctx):
    u = update.effective_user
    user = db.get_user(u.id)
    ref_count = user["referral_count"] if user else 0
    bonus = db.gs("referral_bonus") or "5"
    ref_link = "https://t.me/" + ctx.bot.username + "?start=ref" + str(u.id)
    next_bonus = int(bonus) - (ref_count % int(bonus))

    text = (
        "👥 <b>Referral tizimi</b>\n\n"
        "Sizning linkingiz:\n<code>" + ref_link + "</code>\n\n"
        "Taklif qilganlar: <b>" + str(ref_count) + " ta</b>\n"
        "Keyingi bonus uchun: <b>" + str(next_bonus) + " ta</b>\n\n"
        "Har <b>" + bonus + " ta</b> referral uchun — <b>1 oy premium</b> bepul!"
    )
    await update.message.reply_text(text, parse_mode=H)

async def msg_help(update: Update, ctx):
    await update.message.reply_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "Kino kodini yuboring — bot kinoni yuboradi.\n"
        "Oddiy kinolar — bepul.\n"
        "Pro kinolar — faqat obunachilarga.\n\n"
        "Obuna: Profilim tugmasi.",
        parse_mode=H
    )

# ═══════════════════════════════
# TOLOV — TARIF TANLASH
# ═══════════════════════════════

async def cb_buy_sub(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"

    text = (
        "💎 <b>Pro obuna tariflarini tanlang:</b>\n\n"
        "📅 1 Oy — <b>" + "{:,}".format(int(price_1m)) + " som</b>\n"
        "📅 3 Oy — <b>" + "{:,}".format(int(price_3m)) + " som</b>\n"
        "📅 1 Yil — <b>" + "{:,}".format(int(price_1y)) + " som</b>"
    )
    await q.message.reply_text(text, parse_mode=H, reply_markup=kb.plan_kb())

async def cb_plan(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    plan = q.data.replace("plan_", "")
    ctx.user_data["selected_plan"] = plan

    plan_info = db.PLANS.get(plan, {"label": "1 Oy", "key": "sub_price_1m"})
    price = db.gs(plan_info["key"]) or "15000"

    text = (
        "📅 <b>" + plan_info['label'] + " — " + "{:,}".format(int(price)) + " som</b>\n\n"
        "Tolov usulini tanlang:"
    )
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        text, parse_mode=H, reply_markup=kb.buy_kb()
    )

async def cb_back_to_plans(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"
    text = (
        "Pro obuna tariflarini tanlang:\n\n"
        "1 Oy — " + "{:,}".format(int(price_1m)) + " som\n"
        "3 Oy — " + "{:,}".format(int(price_3m)) + " som\n"
        "1 Yil — " + "{:,}".format(int(price_1y)) + " som"
    )
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        text, parse_mode=H, reply_markup=kb.plan_kb()
    )

async def cb_pay_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    card_type = q.data.replace("pay_", "")
    plan = ctx.user_data.get("selected_plan", "1_month")
    plan_info = db.PLANS.get(plan, {"label": "1 Oy", "key": "sub_price_1m"})
    price = db.gs(plan_info["key"]) or "15000"
    card = db.gs("card_" + card_type) or "Sozlanmagan"
    owner = db.gs("card_owner") or "Admin"
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}
    ctx.user_data["pay_card"] = card_type

    text = (
        names.get(card_type, "") + " orqali tolov\n\n"
        "Tarif: <b>" + plan_info['label'] + "</b>\n"
        "Summa: <b>" + "{:,}".format(int(price)) + " som</b>\n\n"
        "Karta: <code>" + card + "</code>\n"
        "Egasi: <b>" + owner + "</b>\n\n"
        "1. Kartaga pul otkazing\n"
        "2. Chek rasmini yuboring"
    )
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        text, parse_mode=H, reply_markup=kb.back_kb("back_to_plans")
    )
    return S_PAY

async def rcv_screenshot(update: Update, ctx):
    u = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("Chek rasmini yuboring!")
        return S_PAY
    card_type = ctx.user_data.get("pay_card", "uzcard")
    plan = ctx.user_data.get("selected_plan", "1_month")
    plan_info = db.PLANS.get(plan, {"label": "1 Oy", "key": "sub_price_1m"})
    price = int(db.gs(plan_info["key"]) or "15000")
    fid = update.message.photo[-1].file_id
    pay_id = db.add_payment(u.id, price, card_type, fid, plan)
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
        "Yangi tolov!\n\n"
        "Foydalanuvchi: <a href='tg://user?id=" + str(u.id) + "'>" + u.first_name + "</a>\n"
        "ID: <code>" + str(u.id) + "</code>\n"
        "Username: @" + uname + "\n"
        "Tarif: <b>" + plan_info['label'] + "</b>\n"
        "Summa: <b>" + "{:,}".format(price) + " som</b>\n"
        "Karta: " + names.get(card_type, card_type) + "\n"
        "Raqam: " + str(pay_id)
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
        await q.answer("Allaqachon hal qilingan!", show_alert=True)
        return
    plan = pay.get("plan", "1_month")
    db.resolve_payment(pay_id, "approved")
    db.give_sub(pay["user_id"], plan)
    plan_info = db.PLANS.get(plan, {"label": "1 Oy"})
    await safe_edit_message_caption(
        ctx, q.message.chat_id, q.message.message_id,
        "✅ TASDIQLANDI\n\n" + (q.message.caption or ""), parse_mode=H
    )
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            "✅ Tolovingiz tasdiqlandi!\n" + plan_info['label'] + " Pro obuna faollashtirildi!",
            reply_markup=kb.user_kb()
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
        await q.answer("Allaqachon hal qilingan!", show_alert=True)
        return
    db.resolve_payment(pay_id, "rejected")
    await safe_edit_message_caption(
        ctx, q.message.chat_id, q.message.message_id,
        "❌ BEKOR QILINDI\n\n" + (q.message.caption or ""), parse_mode=H
    )
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            "❌ Tolovingiz tasdiqlanmadi. Qayta urinib koring.",
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
    text = (
        "📊 <b>Bot statistikasi</b>\n\n"
        "Yangi foydalanuvchilar:\n"
        "• Bugun: +" + str(s['today']) + " ta\n"
        "• 7 kun: +" + str(s['week']) + " ta\n"
        "• 30 kun: +" + str(s['month']) + " ta\n\n"
        "Faollik:\n"
        "• 24 soat: " + str(s['act24']) + " ta\n"
        "• 7 kun: " + str(s['act7']) + " ta\n"
        "• 30 kun: " + str(s['act30']) + " ta\n\n"
        "Jami foydalanuvchilar: <b>" + str(s['total']) + " ta</b>\n"
        "Premium obunachillar: <b>" + str(s['premium']) + " ta</b>\n"
        "Jami referrallar: <b>" + str(s['referrals']) + " ta</b>\n\n"
        "Kinolar: <b>" + str(s['total_movies']) + " ta</b>\n"
        "Pro kinolar: <b>" + str(s['pro_movies']) + " ta</b>\n\n"
        "Kutilayotgan tolovlar: <b>" + str(s['pending']) + " ta</b>\n"
        "Tasdiqlangan tolovlar: <b>" + str(s['approved']) + " ta</b>"
    )
    await update.message.reply_text(text, parse_mode=H)

# ═══════════════════════════════
# ADMIN — KINOLAR
# ═══════════════════════════════

async def msg_movies(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🎬 <b>Kinolar boshqaruvi</b>\n\n"
        "Quyidagi tugmalar orqali kinolarni boshqaring:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )

async def cb_mv_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🎬 <b>Kino qo'shish</b>\n\n"
        "Kino kodini kiriting:\n"
        "Masalan: 101, 202\n\n"
        "Bekor qilish: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Kino kodini kiriting:\nMasalan: 101, 202\n\nBekor: /cancel"
    )
    return S_MV_CODE

async def st_mv_code(update: Update, ctx):
    code = update.message.text.strip()
    existing = db.get_movie(code)
    if existing:
        title = existing.get('title', "Noma'lum")
        await update.message.reply_text(
            code + " kodi mavjud!\nSarlavha: " + title + "\n\nYangi Message ID yuboring:"
        )
    else:
        await update.message.reply_text(
            "✅ Kod: <b>" + code + "</b>\n\n"
            "Endi Message ID yuboring:\n"
            "Kanalda postga ong klik - Copy Link - oxiridagi raqam",
            parse_mode=H
        )
    ctx.user_data["mv_code"] = code
    return S_MV_MSGID

async def st_mv_msgid(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam! Qayta urinib ko'ring:")
        return S_MV_MSGID
    ctx.user_data["mv_msgid"] = t
    await update.message.reply_text(
        "Kino sarlavhasini yuboring:\n"
        "Sarlavha qo'shmasangiz: - yuboring"
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
                from_chat_id=ch, message_id=int(msgid)
            )
            test_text = "\n\n✅ Test ko'rinishi yuqorida yuborildi!"
        except Exception as e:
            test_text = "\n\n⚠️ Test xato: " + str(e)

    title_display = title if title else "—"
    await update.message.reply_text(
        "✅ Kino qo'shildi!\n\n"
        "📌 Kod: <code>" + code + "</code>\n"
        "📝 Sarlavha: " + title_display + test_text,
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    ctx.user_data.clear()
    return END

async def cb_mv_pro(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "💎 <b>Pro kino boshqaruvi</b>\n\n"
        "Pro qilish — kino faqat obunachilarga ko'rinadi\n"
        "Oddiy qilish — kino hammaga ko'rinadi",
        parse_mode=H, reply_markup=kb.pro_manage_kb()
    )

async def cb_mv_set_pro(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "💎 <b>Pro kino qilish</b>\n\n"
        "Pro qilmoqchi bo'lgan kino kodini kiriting:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Pro qilmoqchi bo'lgan kino kodini kiriting:\n\nBekor: /cancel"
    )
    return S_PRO_SET

async def st_pro_set(update: Update, ctx):
    code = update.message.text.strip()
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text("❌ " + code + " topilmadi! Qayta urinib ko'ring:")
        return S_PRO_SET
    db.set_movie_pro(code, True)
    await update.message.reply_text(
        "✅ <code>" + code + "</code> — Pro qilindi!\n"
        "Endi bu kino faqat obunachilarga ko'rinadi.",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    return END

async def cb_mv_unset_pro(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🔄 <b>Oddiy kino qilish</b>\n\n"
        "Oddiy qilmoqchi bo'lgan kino kodini kiriting:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Oddiy qilmoqchi bo'lgan kino kodini kiriting:\n\nBekor: /cancel"
    )
    return S_PRO_UNSET

async def st_pro_unset(update: Update, ctx):
    code = update.message.text.strip()
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text("❌ " + code + " topilmadi! Qayta urinib ko'ring:")
        return S_PRO_UNSET
    db.set_movie_pro(code, False)
    await update.message.reply_text(
        "✅ <code>" + code + "</code> — Oddiy qilindi!\n"
        "Endi bu kino hammaga ko'rinadi.",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    return END

async def cb_mv_edit(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "✏️ <b>Kino tahrirlash</b>\n\n"
        "Tahrirlash uchun kino kodini kiriting:\n\n"
        "Bekor: /cancel",
        parse_mode=H
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
        await update.message.reply_text("❌ " + code + " topilmadi! Qayta urinib ko'ring:")
        return S_ED_OLD
    ctx.user_data["ed_old"] = code
    title_display = m['title'] if m['title'] else code
    await update.message.reply_text(
        "✅ Topildi: <b>" + title_display + "</b>\n"
        "🆔 Message ID: <code>" + str(m['msg_id']) + "</code>\n\n"
        "Yangi kodni yuboring:",
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
        await update.message.reply_text("❌ Faqat raqam! Qayta:")
        return S_ED_MSGID
    ctx.user_data["ed_msgid"] = t
    await update.message.reply_text("Yangi sarlavha yuboring (o'zgarmasa - yuboring):")
    return S_ED_TITLE

async def st_ed_title(update: Update, ctx):
    title = "" if update.message.text.strip() == "-" else update.message.text.strip()
    db.update_movie(
        ctx.user_data["ed_old"], ctx.user_data["ed_code"],
        ctx.user_data["ed_msgid"], title
    )
    await update.message.reply_text("✅ Kino yangilandi!", reply_markup=kb.movies_kb())
    ctx.user_data.clear()
    return END

async def cb_mv_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🗑️ <b>Kino o'chirish</b>\n\n"
        "O'chirmoqchi bo'lgan kino kodini kiriting:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "O'chirmoqchi bo'lgan kino kodini kiriting:\n\nBekor: /cancel"
    )
    return S_DEL

async def st_del(update: Update, ctx):
    code = update.message.text.strip()
    if db.del_movie(code):
        await update.message.reply_text(
            "✅ <b>" + code + "</b> o'chirildi!",
            parse_mode=H, reply_markup=kb.movies_kb()
        )
        return END
    else:
        await update.message.reply_text("❌ " + code + " topilmadi! Qayta urinib ko'ring:")
        return S_DEL

async def cb_mv_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    movies = db.get_movies(50)
    if not movies:
        await safe_edit_message_text(
            ctx, q.message.chat_id, q.message.message_id,
            "📋 Kinolar bazasi bo'sh.",
            reply_markup=kb.movies_kb()
        )
        return

    text = "📋 <b>Kinolar ro'yxati</b>\n\n"
    for m in movies:
        pro = " 💎" if m.get("is_pro") else ""
        views = m.get('views', 0)
        title = m['title'] if m['title'] else "—"
        text += "• <code>" + m['code'] + "</code>" + pro + " - " + title + " (" + str(views) + " ko'rish)\n"

    if len(text) > 4000:
        text = text[:4000] + "\n\n... va boshqalar"

    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        text, parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="mv_back")
        ]])
    )

async def cb_mv_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🎬 <b>Kinolar boshqaruvi</b>\n\n"
        "Quyidagi tugmalar orqali kinolarni boshqaring:",
        parse_mode=H, reply_markup=kb.movies_kb()
    )

# ═══════════════════════════════
# ADMIN — KANALLAR
# ═══════════════════════════════

async def msg_channels(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    chs = db.get_channels()
    await update.message.reply_text(
        "🔒 <b>Majburiy obuna kanallari</b>\n\nHozirda: <b>" + str(len(chs)) + " ta</b> kanal",
        parse_mode=H, reply_markup=kb.channels_kb()
    )

async def cb_ch_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Majburiy obuna turini tanlang:\n\n"
        "📢 Telegram kanal/guruh (obuna tekshiriladi)\n"
        "🔒 Shaxsiy/Sorovli havola\n"
        "🌐 Oddiy havola (Instagram, sayt va boshqalar)",
        parse_mode=H, reply_markup=kb.channel_type_kb()
    )

async def cb_cht_telegram(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "telegram"
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "📢 <b>Telegram kanal qo'shish</b>\n\n"
        "Kanal ID yoki username kiriting:\n\n"
        "Masalan: @mykanal yoki -1001234567890\n\n"
        "⚠️ Botni kanalga admin qilib qo'shing!",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="ch_add")
        ]])
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Kanal ID yoki username kiriting:\n\n"
        "Masalan: @mykanal yoki -1001234567890\n\n"
        "Botni kanalga admin qilib qo'shing!\n\nBekor: /cancel"
    )
    return S_CH_ID

async def cb_cht_private(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "private"
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🔒 <b>Shaxsiy havola qo'shish</b>\n\n"
        "Kanal ID yoki username kiriting:",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="ch_add")
        ]])
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Kanal ID yoki username kiriting:\n\nBekor: /cancel"
    )
    return S_CH_ID

async def cb_cht_link(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "link"
    ctx.user_data["ch_id"] = ""
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🌐 <b>Oddiy havola qo'shish</b>\n\n"
        "Havola nomini kiriting (tugmada ko'rinadi):",
        parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="ch_add")
        ]])
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Havola nomini kiriting (tugmada ko'rinadi):\n\nBekor: /cancel"
    )
    ctx.user_data["waiting_link_title"] = True
    return S_CH_TITLE

async def st_ch_id(update: Update, ctx):
    text = update.message.text.strip()
    ch_type = ctx.user_data.get(CH_TYPE_KEY, "telegram")
    if ch_type in ("telegram", "private"):
        if not (text.startswith("@") or text.startswith("-100")):
            await update.message.reply_text(
                "❌ Noto'g'ri format!\n\n"
                "Faqat:\n@mykanal yoki -1001234567890\n\n"
                "Qayta urinib ko'ring:"
            )
            return S_CH_ID
    ctx.user_data["ch_id"] = text
    await update.message.reply_text("Kanal nomini kiriting (tugmada ko'rinadi):")
    return S_CH_TITLE

async def st_ch_title(update: Update, ctx):
    ctx.user_data["ch_title"] = update.message.text.strip()
    ch_type = ctx.user_data.get(CH_TYPE_KEY, "telegram")
    ch_id = ctx.user_data.get("ch_id", "")

    if ctx.user_data.get("waiting_link_title"):
        await update.message.reply_text(
            "Havolani kiriting:\nMasalan: https://t.me/mykanal"
        )
        return S_CH_LINK

    if ch_type == "telegram" and ch_id.startswith("@"):
        auto_link = "https://t.me/" + ch_id[1:]
    else:
        auto_link = ""

    ctx.user_data["ch_auto_link"] = auto_link
    if auto_link:
        await update.message.reply_text(
            "Havola: " + auto_link + "\nO'zgartirmasangiz - yuboring:"
        )
    else:
        await update.message.reply_text("Kanal havolasini kiriting:")
    return S_CH_LINK

async def st_ch_link(update: Update, ctx):
    text = update.message.text.strip()
    link = ctx.user_data.get("ch_auto_link", "") if text == "-" else text
    ch_id = ctx.user_data.get("ch_id", "")
    title = ctx.user_data.get("ch_title", "Kanal")
    ch_type = ctx.user_data.get(CH_TYPE_KEY, "telegram")

    db.add_channel(ch_id, title, link, ch_type)

    type_names = {"telegram": "Telegram kanal", "private": "Shaxsiy havola", "link": "Oddiy havola"}
    await update.message.reply_text(
        "✅ Kanal qo'shildi!\n\n"
        "📌 Tur: " + type_names.get(ch_type, ch_type) + "\n"
        "📝 Nom: " + title + "\n"
        "🔗 Havola: " + link,
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
        await safe_edit_message_text(
            ctx, q.message.chat_id, q.message.message_id,
            "📋 Hozircha kanallar yo'q.",
            reply_markup=kb.channels_kb()
        )
        return

    text = "🔒 <b>Majburiy obuna kanallari</b>\n\n"
    for i, c in enumerate(chs, 1):
        icons = {"telegram": "📢", "private": "🔒", "link": "🌐"}
        icon = icons.get(c.get("type", "telegram"), "📢")
        text += str(i) + ". " + icon + " <b>" + c['title'] + "</b>\n"
        text += "   🆔 ID: " + str(c['channel_id']) + "\n"
        if c.get('link'):
            text += "   🔗 Havola: " + c['link'] + "\n"
        text += "\n"

    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        text, parse_mode=H,
        reply_markup=kb.channel_list_kb(chs)
    )

async def cb_ch_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await safe_edit_message_text(
            ctx, q.message.chat_id, q.message.message_id,
            "🗑️ O'chirish uchun kanallar yo'q.",
            reply_markup=kb.channels_kb()
        )
        return

    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🗑️ <b>Kanal o'chirish</b>\n\n"
        "O'chirish uchun kanal nomini bosing:",
        parse_mode=H,
        reply_markup=kb.channel_del_list_kb(chs)
    )

async def cb_dch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if not db.is_admin(q.from_user.id):
        return
    ch_id = int(q.data.replace("dch_", ""))
    if db.del_channel(ch_id):
        await q.answer("✅ Kanal o'chirildi!", show_alert=True)
        chs = db.get_channels()
        if not chs:
            await safe_edit_message_text(
                ctx, q.message.chat_id, q.message.message_id,
                "📋 Hozircha kanallar yo'q.",
                reply_markup=kb.channels_kb()
            )
            return
        await safe_edit_message_text(
            ctx, q.message.chat_id, q.message.message_id,
            "🗑️ <b>Kanal o'chirish</b>\n\n"
            "O'chirish uchun kanal nomini bosing:",
            parse_mode=H,
            reply_markup=kb.channel_del_list_kb(chs)
        )
    else:
        await q.answer("❌ Kanal topilmadi.", show_alert=True)

async def cb_ch_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🔒 <b>Majburiy obuna kanallari</b>\n\nHozirda: <b>" + str(len(chs)) + " ta</b> kanal",
        parse_mode=H,
        reply_markup=kb.channels_kb()
    )

async def cmd_delch(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Format: /delch <kanal_id>")
        return
    if db.del_channel(int(ctx.args[0])):
        await update.message.reply_text("✅ Kanal o'chirildi!")
    else:
        await update.message.reply_text("❌ Kanal topilmadi.")

# ═══════════════════════════════
# ADMIN — ADMINLAR
# ═══════════════════════════════

async def msg_admins(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    admins = db.get_admins()
    total = len(ADMIN_IDS) + len(admins)
    await update.message.reply_text(
        "👮 <b>Adminlar boshqaruvi</b>\n\nJami adminlar: <b>" + str(total) + " ta</b>",
        parse_mode=H, reply_markup=kb.admins_kb()
    )

async def cb_adm_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "➕ <b>Admin qo'shish</b>\n\n"
        "Yangi admin Telegram ID sini yuboring:\n\n"
        "ID olish: @userinfobot ga /start yozing\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Yangi admin Telegram ID sini yuboring:\n\n"
        "ID olish: @userinfobot ga /start yozing\n\n"
        "Bekor: /cancel"
    )
    return S_ADM_ADD

async def st_adm_add(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam! Qayta urinib ko'ring:")
        return S_ADM_ADD
    uid = int(t)
    if uid in ADMIN_IDS:
        await update.message.reply_text("⚠️ Bu asosiy admin!")
        return END
    if db.add_admin(uid, "Admin " + str(uid)):
        await update.message.reply_text(
            "✅ <code>" + str(uid) + "</code> admin qo'shildi!",
            parse_mode=H, reply_markup=kb.admins_kb()
        )
        try:
            await ctx.bot.send_message(uid, "✅ Siz admin qilib tayinlandingiz!")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ Xatolik yuz berdi!")
    return END

async def cb_adm_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🗑️ <b>Admin o'chirish</b>\n\n"
        "Admin Telegram ID sini yuboring:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Admin Telegram ID sini yuboring:\n\nBekor: /cancel"
    )
    return S_ADM_DEL

async def st_adm_del(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam! Qayta urinib ko'ring:")
        return S_ADM_DEL
    uid = int(t)
    if uid in ADMIN_IDS:
        await update.message.reply_text("⚠️ Asosiy adminni o'chirib bo'lmaydi!")
        return END
    if db.del_admin(uid):
        await update.message.reply_text(
            "✅ <code>" + str(uid) + "</code> o'chirildi!",
            parse_mode=H, reply_markup=kb.admins_kb()
        )
    else:
        await update.message.reply_text("❌ Bu ID topilmadi.")
    return END

async def cb_adm_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    total = len(ADMIN_IDS) + len(db.get_admins())
    main_admins = ", ".join(map(str, ADMIN_IDS))
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "👮 <b>Adminlar ro'yxati</b>\n\n"
        "Jami: <b>" + str(total) + " ta</b> admin\n\n"
        "👑 Asosiy adminlar: " + main_admins,
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
        "📨 <b>Xabar yuborish</b>\n\n"
        "Jami foydalanuvchilar: <b>" + str(count) + " ta</b>\n\n"
        "Xabar turini tanlang:",
        parse_mode=H, reply_markup=kb.broadcast_kb()
    )

async def cb_bc_text(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "📝 <b>Matnli xabar yuborish</b>\n\n"
        "Barcha userlarga yuboriladigan xabarni yozing:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Xabar matnini yuboring:\n\nBekor: /cancel"
    )
    return S_BC_TEXT

async def cb_bc_fwd(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🔄 <b>Forward xabar yuborish</b>\n\n"
        "Forward qilinadigan xabarni yuboring:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Forward qilinadigan xabarni yuboring:\n\nBekor: /cancel"
    )
    return S_BC_FWD

async def st_bc_text(update: Update, ctx):
    text = update.message.text
    users = db.all_user_ids()
    sent = failed = 0
    total = len(users)
    msg = await update.message.reply_text("📤 Yuborilmoqda: 0/" + str(total))

    for i, uid in enumerate(users):
        try:
            await ctx.bot.send_message(uid, text, parse_mode=H)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try:
                await safe_edit_message_text(
                    ctx, msg.chat_id, msg.message_id,
                    "📤 Yuborilmoqda: " + str(i + 1) + "/" + str(total)
                )
            except Exception:
                pass
        await asyncio.sleep(0.04)

    await safe_edit_message_text(
        ctx, msg.chat_id, msg.message_id,
        "✅ Broadcast tugadi!\n\n"
        "✅ Yuborildi: " + str(sent) + "\n"
        "❌ Xatolik: " + str(failed),
        reply_markup=kb.admin_kb()
    )
    return END

async def st_bc_fwd(update: Update, ctx):
    users = db.all_user_ids()
    sent = failed = 0
    total = len(users)
    msg = await update.message.reply_text("🔄 Forward: 0/" + str(total))

    for i, uid in enumerate(users):
        try:
            await update.message.forward(uid)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try:
                await safe_edit_message_text(
                    ctx, msg.chat_id, msg.message_id,
                    "🔄 Forward: " + str(i + 1) + "/" + str(total)
                )
            except Exception:
                pass
        await asyncio.sleep(0.04)

    await safe_edit_message_text(
        ctx, msg.chat_id, msg.message_id,
        "✅ Forward tugadi!\n\n"
        "✅ Yuborildi: " + str(sent) + "\n"
        "❌ Xatolik: " + str(failed),
        reply_markup=kb.admin_kb()
    )
    return END

# ═══════════════════════════════
# ADMIN — SOZLAMALAR
# ═══════════════════════════════

async def msg_settings(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"
    movch    = db.gs("movie_ch") or MOVIE_CH or "Sozlanmagan"
    uzcard   = db.gs("card_uzcard") or "Sozlanmagan"
    humo     = db.gs("card_humo") or "Sozlanmagan"
    visa     = db.gs("card_visa") or "Sozlanmagan"
    owner    = db.gs("card_owner") or "Sozlanmagan"
    refbonus = db.gs("referral_bonus") or "5"
    welcome  = db.gs("welcome_text") or "Kino kodini yuboring"

    # ✅ f-string TASHQARISIDA qisqartirish — SyntaxError fix
    welcome_short = welcome[:50]

    text = (
        "⚙️ <b>Bot sozlamalari</b>\n\n"
        "💰 <b>Obuna narxlari:</b>\n"
        "📅 1 Oy: " + "{:,}".format(int(price_1m)) + " som\n"
        "📅 3 Oy: " + "{:,}".format(int(price_3m)) + " som\n"
        "📅 1 Yil: " + "{:,}".format(int(price_1y)) + " som\n\n"
        "🎬 <b>Kino kanali:</b>\n"
        "<code>" + movch + "</code>\n\n"
        "💳 <b>To'lov kartalari:</b>\n"
        "UzCard: <code>" + uzcard + "</code>\n"
        "Humo: <code>" + humo + "</code>\n"
        "Visa: <code>" + visa + "</code>\n"
        "Egasi: " + owner + "\n\n"
        "👥 <b>Referral sozlamalari:</b>\n"
        "Har " + refbonus + " ta referral = 1 oy premium\n\n"
        "📝 <b>Xush kelibsiz xabari:</b>\n" +
        welcome_short + "..."
    )
    await update.message.reply_text(text, parse_mode=H, reply_markup=kb.settings_kb())

async def cb_st_cards(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "💳 <b>Karta sozlamalari</b>\n\n"
        "Qaysi kartani sozlamoqchisiz?",
        parse_mode=H, reply_markup=kb.cards_kb()
    )

async def cb_sc_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    key = q.data.replace("sc_", "")
    ctx.user_data["st_key"] = "card_" + key
    names = {"uzcard": "UzCard raqami", "humo": "Humo raqami",
             "visa": "Visa raqami", "owner": "Karta egasi ismi"}
    name = names.get(key, key)
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "✏️ <b>" + name + "</b>\n\n"
        "Yangi qiymatni yuboring:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Yangi " + name + " ni yuboring:\n\nBekor: /cancel"
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
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "💳 <b>Karta sozlamalari</b>\n\n"
        "Qaysi kartani sozlamoqchisiz?",
        parse_mode=H, reply_markup=kb.cards_kb()
    )

async def cb_st_prices(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"
    text = (
        "💰 <b>Obuna narxlari</b>\n\n"
        "📅 1 Oy: " + "{:,}".format(int(price_1m)) + " som\n"
        "📅 3 Oy: " + "{:,}".format(int(price_3m)) + " som\n"
        "📅 1 Yil: " + "{:,}".format(int(price_1y)) + " som\n\n"
        "Qaysi narxni o'zgartirmoqchisiz?"
    )
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        text, parse_mode=H, reply_markup=kb.prices_kb()
    )

async def cb_sp(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    plan = q.data.replace("sp_", "")
    ctx.user_data["price_plan"] = plan
    plan_info = db.PLANS.get(plan, {"label": "1 Oy"})
    key = "sub_price_" + plan.replace("_month", "m").replace("_year", "y")
    current = db.gs(key) or "15000"
    label = plan_info['label']
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "✏️ <b>" + label + " narxi</b>\n\n"
        "Hozirgi: " + "{:,}".format(int(current)) + " som\n\n"
        "Yangi narx yuboring:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        label + " uchun yangi narx yuboring:\n\nBekor: /cancel"
    )
    return S_ST_PRICE

async def st_save_price(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam! Qayta:")
        return S_ST_PRICE
    plan = ctx.user_data.get("price_plan", "1_month")
    key = "sub_price_" + plan.replace("_month", "m").replace("_year", "y")
    db.ss(key, t)
    await update.message.reply_text(
        "✅ Narx " + "{:,}".format(int(t)) + " som saqlandi!",
        reply_markup=kb.settings_kb()
    )
    ctx.user_data.clear()
    return END

async def cb_st_movch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("movie_ch") or MOVIE_CH or "Sozlanmagan"
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "🎬 <b>Kino kanali</b>\n\n"
        "Hozirgi: <code>" + str(cur) + "</code>\n\n"
        "Yangi kino kanal ID yuboring:\n\n"
        "ID olish: @JsonDumpBot ga forward qiling\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Yangi kino kanal ID yuboring:\n\n"
        "@JsonDumpBot ga forward qiling\n\nBekor: /cancel"
    )
    return S_ST_MOVCH

async def st_save_movch(update: Update, ctx):
    db.ss("movie_ch", update.message.text.strip())
    await update.message.reply_text("✅ Kino kanal saqlandi!", reply_markup=kb.settings_kb())
    return END

async def cb_st_welcome(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("welcome_text") or "—"
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "📝 <b>Xush kelibsiz xabari</b>\n\n"
        "Hozirgi:\n<i>" + cur + "</i>\n\n"
        "Yangi matnni yuboring:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Yangi xush kelibsiz xabarini yuboring:\n\nBekor: /cancel"
    )
    return S_ST_WELCOME

async def st_save_welcome(update: Update, ctx):
    db.ss("welcome_text", update.message.text.strip())
    await update.message.reply_text("✅ Saqlandi!", reply_markup=kb.settings_kb())
    return END

async def cb_st_refbonus(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("referral_bonus") or "5"
    await safe_edit_message_text(
        ctx, q.message.chat_id, q.message.message_id,
        "👥 <b>Referral bonus sozlamasi</b>\n\n"
        "Hozirgi: har <b>" + cur + "</b> ta referral = 1 oy premium\n\n"
        "Yangi sonni yuboring:\n\n"
        "Bekor: /cancel",
        parse_mode=H
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Yangi referral bonus sonini yuboring:\n\nBekor: /cancel"
    )
    return S_ST_REFBONUS

async def st_save_refbonus(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Faqat raqam! Qayta:")
        return S_ST_REFBONUS
    db.ss("referral_bonus", t)
    await update.message.reply_text(
        "✅ Har " + t + " ta referral = 1 oy premium saqlandi!",
        reply_markup=kb.settings_kb()
    )
    return END

# ═══════════════════════════════
# ADMIN — PREMIUM BERISH
# ═══════════════════════════════

async def cmd_give(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "📝 <b>Premium berish formati:</b>\n\n"
            "/give &lt;user_id&gt; &lt;plan&gt;\n\n"
            "Planlar:\n"
            "• 1_month - 1 oylik\n"
            "• 3_month - 3 oylik\n"
            "• 1_year - 1 yillik",
            parse_mode=H
        )
        return
    try:
        uid = int(ctx.args[0])
        plan = ctx.args[1]
        if plan not in db.PLANS:
            await update.message.reply_text("❌ Noto'g'ri plan! 1_month | 3_month | 1_year")
            return
        db.give_sub(uid, plan)
        plan_info = db.PLANS[plan]
        await update.message.reply_text("✅ " + str(uid) + " ga " + plan_info['label'] + " premium berildi!")
        try:
            await ctx.bot.send_message(
                uid,
                "✅ Admin sizga " + plan_info['label'] + " Pro obuna berdi!\n"
                "Endi barcha Pro kinolarni ko'rishingiz mumkin.",
                reply_markup=kb.user_kb()
            )
        except Exception:
            pass
    except Exception:
        await update.message.reply_text("❌ Xatolik. Format: /give 123456 1_month")

async def cmd_clear_cache(update: Update, ctx):
    if not db.is_admin(update.effective_user.id):
        return
    ctx.user_data.clear()
    ctx.chat_data.clear()
    await update.message.reply_text("✅ Kesh tozalandi!", reply_markup=kb.admin_kb())

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
    # Pro boshqaruv
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_mv_set_pro,   pattern="^mv_set_pro$"),
            CallbackQueryHandler(cb_mv_unset_pro, pattern="^mv_unset_pro$"),
        ],
        states={
            S_PRO_SET:   [MessageHandler(filters.TEXT & ~filters.COMMAND, st_pro_set)],
            S_PRO_UNSET: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_pro_unset)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))
    # Kanal qoshish
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_cht_telegram, pattern="^cht_telegram$"),
            CallbackQueryHandler(cb_cht_private,  pattern="^cht_private$"),
            CallbackQueryHandler(cb_cht_link,     pattern="^cht_link$"),
        ],
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
            CallbackQueryHandler(cb_sp,          pattern="^sp_(1_month|3_month|1_year)$"),
            CallbackQueryHandler(cb_st_movch,    pattern="^st_movch$"),
            CallbackQueryHandler(cb_st_welcome,  pattern="^st_welcome$"),
            CallbackQueryHandler(cb_st_refbonus, pattern="^st_refbonus$"),
        ],
        states={
            S_ST_CARD:     [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_card)],
            S_ST_PRICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_price)],
            S_ST_MOVCH:    [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_movch)],
            S_ST_WELCOME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_welcome)],
            S_ST_REFBONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_save_refbonus)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], per_user=True,
    ))

    # Commands
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("admin",      cmd_start))
    app.add_handler(CommandHandler("cancel",     cancel))
    app.add_handler(CommandHandler("delch",      cmd_delch))
    app.add_handler(CommandHandler("give",       cmd_give))
    app.add_handler(CommandHandler("clearcache", cmd_clear_cache))

    # Callbacks
    app.add_handler(CallbackQueryHandler(cb_chk_sub,       pattern="^chk_sub$"))
    app.add_handler(CallbackQueryHandler(cb_buy_sub,        pattern="^buy_sub$"))
    app.add_handler(CallbackQueryHandler(cb_plan,           pattern="^plan_(1_month|3_month|1_year)$"))
    app.add_handler(CallbackQueryHandler(cb_back_to_plans,  pattern="^back_to_plans$"))
    app.add_handler(CallbackQueryHandler(cb_pay_ok,         pattern=r"^pok_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_no,         pattern=r"^pno_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mv_list,        pattern="^mv_list$"))
    app.add_handler(CallbackQueryHandler(cb_mv_back,        pattern="^mv_back$"))
    app.add_handler(CallbackQueryHandler(cb_mv_pro,         pattern="^mv_pro$"))
    app.add_handler(CallbackQueryHandler(cb_ch_add,         pattern="^ch_add$"))
    app.add_handler(CallbackQueryHandler(cb_ch_list,        pattern="^ch_list$"))
    app.add_handler(CallbackQueryHandler(cb_ch_del,         pattern="^ch_del$"))
    app.add_handler(CallbackQueryHandler(cb_dch,            pattern=r"^dch_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_ch_back,        pattern="^ch_back$"))
    app.add_handler(CallbackQueryHandler(cb_adm_list,       pattern="^adm_list$"))
    app.add_handler(CallbackQueryHandler(cb_st_cards,       pattern="^st_cards$"))
    app.add_handler(CallbackQueryHandler(cb_st_prices,      pattern="^st_prices$"))
    app.add_handler(CallbackQueryHandler(cb_st_back,        pattern="^st_back$"))
    app.add_handler(CallbackQueryHandler(cb_cancel,         pattern="^x$"))

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
    app.add_handler(MessageHandler(filters.Regex("^👥 Referral$"),        msg_referral))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yordam$"),          msg_help))
    app.add_handler(MessageHandler(filters.Regex("^🎬 Kino qidirish$"),
        lambda u, c: u.message.reply_text("🎬 Kino kodini yuboring:")))

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
            webhook_url=WEBHOOK_URL + "/" + BOT_TOKEN,
        )
    else:
        logging.info("Polling (local)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
