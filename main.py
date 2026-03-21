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
    await q.edit_message_text("Bekor qilindi.")

# ═══════════════════════════════
# START
# ═══════════════════════════════

async def cmd_start(update: Update, ctx):
    u = update.effective_user
    # Referral tekshirish
    referral_by = None
    if ctx.args and ctx.args[0].startswith("ref"):
        try:
            referral_by = int(ctx.args[0][3:])
            if referral_by == u.id:
                referral_by = None
        except ValueError:
            referral_by = None

    is_new = db.add_user(u.id, u.first_name, u.username or "", referral_by)

    # Referral bonus bildirishnoma
    if referral_by and is_new:
        ref_user = db.get_user(referral_by)
        if ref_user:
            bonus = int(db.gs("referral_bonus") or "5")
            if ref_user["referral_count"] % bonus == 0:
                try:
                    await ctx.bot.send_message(
                        referral_by,
                        f"Tabrik! {bonus} ta referral to'ldingiz — 1 oy premium qo'shildi!"
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
            f"👑 <b>Salom, {u.first_name}!</b>\n\nAdmin paneliga xush kelibsiz.",
            parse_mode=H, reply_markup=kb.admin_kb()
        )
    else:
        welcome = db.gs("welcome_text") or "Kino kodini yuboring"
        await update.message.reply_text(
            f"🎬 <b>Salom, {u.first_name}!</b>\n\n{welcome}",
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
    await q.edit_message_text("Obuna tasdiqlandi! Kino kodini yuboring.")
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
            f"❌ <b>{code}</b> kodli kino topilmadi.", parse_mode=H
        )
        return

    # Pro kino tekshirish
    if movie.get("is_pro") and not db.has_sub(u.id):
        price_1m = db.gs("sub_price_1m") or "15000"
        price_3m = db.gs("sub_price_3m") or "40000"
        price_1y = db.gs("sub_price_1y") or "120000"
        await update.message.reply_text(
            f"💎 <b>Bu kino faqat Pro foydalanuvchilar uchun!</b>\n\n"
            f"Pro obuna narxlari:\n"
            f"📅 1 Oy — {int(price_1m):,} som\n"
            f"📅 3 Oy — {int(price_3m):,} som\n"
            f"📅 1 Yil — {int(price_1y):,} som\n\n"
            f"Obuna sotib olish uchun Profilim tugmasini bosing.",
            parse_mode=H,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Obuna sotib olish", callback_data="buy_sub")
            ]])
        )
        return

    ch = get_movie_ch()
    if not ch:
        await update.message.reply_text("Kino kanal sozlanmagan.")
        return

    try:
        await ctx.bot.copy_message(
            chat_id=u.id, from_chat_id=ch, message_id=int(movie["msg_id"])
        )
    except TelegramError as e:
        logging.error(f"Copy xato: {e}")
        await update.message.reply_text("Kinoni yuborishda xatolik.")

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
        sub_text = f"Faol ({info['expires_at'][:10]} gacha) — {plan}"
    else:
        sub_text = "Obuna yoq"

    ref_count = user["referral_count"] if user else 0
    bonus = db.gs("referral_bonus") or "5"
    ref_link = f"https://t.me/{ctx.bot.username}?start=ref{u.id}"

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("Obuna sotib olish", callback_data="buy_sub")
    ]])

    await update.message.reply_text(
        f"👤 <b>Mening profilim</b>\n\n"
        f"ID: <code>{u.id}</code>\n"
        f"Ism: {u.first_name}\n"
        f"Obuna: {sub_text}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Obuna narxlari:</b>\n"
        f"📅 1 Oy — {int(price_1m):,} som\n"
        f"📅 3 Oy — {int(price_3m):,} som\n"
        f"📅 1 Yil — {int(price_1y):,} som",
        parse_mode=H, reply_markup=markup
    )

# ═══════════════════════════════
# USER — REFERRAL
# ═══════════════════════════════

async def msg_referral(update: Update, ctx):
    u = update.effective_user
    user = db.get_user(u.id)
    ref_count = user["referral_count"] if user else 0
    bonus = db.gs("referral_bonus") or "5"
    ref_link = f"https://t.me/{ctx.bot.username}?start=ref{u.id}"
    next_bonus = int(bonus) - (ref_count % int(bonus))

    await update.message.reply_text(
        f"👥 <b>Referral tizimi</b>\n\n"
        f"Sizning linkingiz:\n<code>{ref_link}</code>\n\n"
        f"Taklif qilganlar: <b>{ref_count} ta</b>\n"
        f"Keyingi bonus uchun: <b>{next_bonus} ta</b>\n\n"
        f"Har <b>{bonus} ta</b> referral uchun — <b>1 oy premium</b> bepul!",
        parse_mode=H
    )

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
    await q.edit_message_text(
        f"💎 <b>Pro obuna tariflarini tanlang:</b>\n\n"
        f"📅 1 Oy — <b>{int(price_1m):,} som</b>\n"
        f"📅 3 Oy — <b>{int(price_3m):,} som</b>\n"
        f"📅 1 Yil — <b>{int(price_1y):,} som</b>",
        parse_mode=H, reply_markup=kb.plan_kb()
    )

async def cb_plan(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    plan = q.data.replace("plan_", "")
    ctx.user_data["selected_plan"] = plan

    plan_info = db.PLANS.get(plan, {"label": "1 Oy", "key": "sub_price_1m"})
    price = db.gs(plan_info["key"]) or "15000"

    await q.edit_message_text(
        f"📅 <b>{plan_info['label']} — {int(price):,} som</b>\n\n"
        f"Tolov usulini tanlang:",
        parse_mode=H, reply_markup=kb.buy_kb()
    )

async def cb_back_to_plans(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"
    await q.edit_message_text(
        f"Pro obuna tariflarini tanlang:\n\n"
        f"1 Oy — {int(price_1m):,} som\n"
        f"3 Oy — {int(price_3m):,} som\n"
        f"1 Yil — {int(price_1y):,} som",
        parse_mode=H, reply_markup=kb.plan_kb()
    )

async def cb_pay_card(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    card_type = q.data.replace("pay_", "")
    plan = ctx.user_data.get("selected_plan", "1_month")
    plan_info = db.PLANS.get(plan, {"label": "1 Oy", "key": "sub_price_1m"})
    price = db.gs(plan_info["key"]) or "15000"
    card = db.gs(f"card_{card_type}") or "Sozlanmagan"
    owner = db.gs("card_owner") or "Admin"
    names = {"uzcard": "UzCard", "humo": "Humo", "visa": "Visa/MasterCard"}
    ctx.user_data["pay_card"] = card_type
    await q.edit_message_text(
        f"{names.get(card_type, '')} orqali tolov\n\n"
        f"Tarif: <b>{plan_info['label']}</b>\n"
        f"Summa: <b>{int(price):,} som</b>\n\n"
        f"Karta: <code>{card}</code>\n"
        f"Egasi: <b>{owner}</b>\n\n"
        f"1. Kartaga pul otkazing\n"
        f"2. Chek rasmini yuboring",
        parse_mode=H, reply_markup=kb.back_kb("back_to_plans")
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
        f"Yangi tolov!\n\n"
        f"Foydalanuvchi: <a href='tg://user?id={u.id}'>{u.first_name}</a>\n"
        f"ID: <code>{u.id}</code>\n"
        f"Username: @{uname}\n"
        f"Tarif: <b>{plan_info['label']}</b>\n"
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
        await q.answer("Allaqachon hal qilingan!", show_alert=True)
        return
    plan = pay.get("plan", "1_month")
    db.resolve_payment(pay_id, "approved")
    db.give_sub(pay["user_id"], plan)
    plan_info = db.PLANS.get(plan, {"label": "1 Oy"})
    await q.edit_message_caption(f"TASDIQLANDI\n\n{q.message.caption}", parse_mode=H)
    try:
        await ctx.bot.send_message(
            pay["user_id"],
            f"Tolovingiz tasdiqlandi!\n{plan_info['label']} Pro obuna faollashtirildi!",
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
        await q.answer("Allaqachon hal qilingan!", show_alert=True)
        return
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
        f"Jami foydalanuvchilar: <b>{s['total']} ta</b>\n"
        f"Premium obunachillar: <b>{s['premium']} ta</b>\n"
        f"Jami referrallar: <b>{s['referrals']} ta</b>\n\n"
        f"Kinolar: <b>{s['total_movies']} ta</b>\n"
        f"Pro kinolar: <b>{s['pro_movies']} ta</b>\n\n"
        f"Kutilayotgan tolovlar: <b>{s['pending']} ta</b>\n"
        f"Tasdiqlangan tolovlar: <b>{s['approved']} ta</b>",
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
        "Kino kodini kiriting:\nMasalan: 101, 202\n\nBekor: /cancel"
    )
    return S_MV_CODE

async def st_mv_code(update: Update, ctx):
    code = update.message.text.strip()
    existing = db.get_movie(code)
    pro_hint = " [PRO]" if existing and existing.get("is_pro") else ""
    if existing:
        await update.message.reply_text(
            f"{code} kodi mavjud{pro_hint}!\n\nMessage ID yuboring:"
        )
    else:
        await update.message.reply_text(
            f"Kod: <b>{code}</b>\n\nMessage ID yuboring:\n"
            f"Kanalda postga ong klik - Copy Link - oxiridagi raqam",
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
    await update.message.reply_text(
        "Kino sarlavhasini yuboring:\nOtkazish uchun: - yuboring"
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
            test_text = "\n\nTest korinishi yuqorida:"
        except Exception as e:
            test_text = f"\n\nTest xato: {e}"
    await update.message.reply_text(
        f"Kino qoshildi!\nKod: <code>{code}</code>\n"
        f"Sarlavha: {title or '—'}{test_text}",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    ctx.user_data.clear()
    return END

# PRO boshqaruv
async def cb_mv_pro(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Pro boshqaruv:\n\n"
        "Pro qilish — kino faqat obunachilarga korinadi\n"
        "Oddiy qilish — kino hammaga korinadi",
        reply_markup=kb.pro_manage_kb()
    )

async def cb_mv_set_pro(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Pro qilmoqchi bolgan kino kodini kiriting:\n\nBekor: /cancel")
    return S_PRO_SET

async def st_pro_set(update: Update, ctx):
    code = update.message.text.strip()
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text(f"{code} topilmadi! Qayta:")
        return S_PRO_SET
    db.set_movie_pro(code, True)
    await update.message.reply_text(
        f"<code>{code}</code> — Pro qilindi! Faqat obunachilarga korinadi.",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
    return END

async def cb_mv_unset_pro(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Oddiy qilmoqchi bolgan kino kodini kiriting:\n\nBekor: /cancel")
    return S_PRO_UNSET

async def st_pro_unset(update: Update, ctx):
    code = update.message.text.strip()
    movie = db.get_movie(code)
    if not movie:
        await update.message.reply_text(f"{code} topilmadi! Qayta:")
        return S_PRO_UNSET
    db.set_movie_pro(code, False)
    await update.message.reply_text(
        f"<code>{code}</code> — Oddiy qilindi! Hammaga korinadi.",
        parse_mode=H, reply_markup=kb.movies_kb()
    )
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
        pro = " 💎" if m.get("is_pro") else ""
        lines.append(f"<code>{m['code']}</code>{pro} | {m['title'] or '—'} | {m['views']} marta")
    await q.edit_message_text(
        "\n".join(lines), parse_mode=H,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Orqaga", callback_data="mv_back")
        ]])
    )

async def cb_mv_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🎬 <b>Kinolar bomi</b>", parse_mode=H, reply_markup=kb.movies_kb())

# ═══════════════════════════════
# ADMIN — KANALLAR
# ═══════════════════════════════

async def msg_channels(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    chs = db.get_channels()
    await update.message.reply_text(
        f"🔒 <b>Majburiy obuna kanallar</b>\n\nHozirda: <b>{len(chs)} ta</b>",
        parse_mode=H, reply_markup=kb.channels_kb()
    )

async def cb_ch_add(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Majburiy obuna turini tanlang:\n\n"
        "Ommaviy/Shaxsiy — Telegram kanal/guruh (obuna tekshiriladi)\n"
        "Shaxsiy/Sorovli — maxfiy havola\n"
        "Oddiy havola — Instagram, sayt va boshqalar",
        reply_markup=kb.channel_type_kb()
    )

async def cb_cht_telegram(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "telegram"
    await q.edit_message_text(
        "Ommaviy / Shaxsiy (Kanal / Guruh)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="ch_add")]])
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Kanal ID yoki username kiriting:\n\n"
        "Masalan: @mykanal yoki -1001234567890\n\n"
        "Botni kanalga admin qilib qoshing!\n\nBekor: /cancel"
    )
    return S_CH_ID

async def cb_cht_private(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data[CH_TYPE_KEY] = "private"
    await q.edit_message_text(
        "Shaxsiy / Sorovli havola",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="ch_add")]])
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
    await q.edit_message_text(
        "Oddiy havola",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="ch_add")]])
    )
    await ctx.bot.send_message(
        q.from_user.id,
        "Havola nomini kiriting (tugmada korinadi):\n\nBekor: /cancel"
    )
    ctx.user_data["waiting_link_title"] = True
    return S_CH_TITLE

async def st_ch_id(update: Update, ctx):
    text = update.message.text.strip()
    ch_type = ctx.user_data.get(CH_TYPE_KEY, "telegram")
    if ch_type in ("telegram", "private"):
        if not (text.startswith("@") or text.startswith("-100")):
            await update.message.reply_text(
                "Notogri format!\n\nFaqat:\n@mykanal yoki -1001234567890\n\nQayta:"
            )
            return S_CH_ID
    ctx.user_data["ch_id"] = text
    await update.message.reply_text("Kanal nomini kiriting (tugmada korinadi):")
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
            f"Havola: {auto_link}\nOzgartirmasangiz - yuboring:"
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
        f"Kanal qoshildi!\nTur: {type_names.get(ch_type)}\nNom: {title}",
        reply_markup=kb.channels_kb()
    )
    ctx.user_data.clear()
    return END

async def cb_ch_list(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await q.edit_message_text("Kanallar yoq.", reply_markup=kb.channels_kb())
        return
    lines = [f"Majburiy kanallar ({len(chs)} ta):"]
    for c in chs:
        icons = {"telegram": "📢", "private": "🔒", "link": "🌐"}
        icon = icons.get(c.get("type", "telegram"), "📢")
        lines.append(f"{icon} {c['title']}")
    await q.edit_message_text("\n".join(lines), reply_markup=kb.channel_list_kb(chs))

async def cb_ch_del(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    if not chs:
        await q.edit_message_text("Ochirish uchun kanallar yoq.", reply_markup=kb.channels_kb())
        return
    await q.edit_message_text(
        "Ochirish uchun kanal nomini bosing:",
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
            "Ochirish uchun kanal nomini bosing:",
            reply_markup=kb.channel_del_list_kb(chs)
        )
    else:
        await q.answer("Topilmadi.", show_alert=True)

async def cb_ch_back(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    chs = db.get_channels()
    await q.edit_message_text(
        f"Majburiy obuna kanallar — {len(chs)} ta",
        reply_markup=kb.channels_kb()
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
    await update.message.reply_text("👮 <b>Adminlar bomi</b>", parse_mode=H, reply_markup=kb.admins_kb())

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
        f"Adminlar royxati\n\nJami: <b>{total} ta</b> admin",
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
    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"
    movch    = db.gs("movie_ch")  or MOVIE_CH or "Sozlanmagan"
    uzcard   = db.gs("card_uzcard") or "Sozlanmagan"
    humo     = db.gs("card_humo")   or "Sozlanmagan"
    visa     = db.gs("card_visa")   or "Sozlanmagan"
    owner    = db.gs("card_owner")  or "Sozlanmagan"
    refbonus = db.gs("referral_bonus") or "5"
    await update.message.reply_text(
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"Obuna narxlari:\n"
        f"1 Oy: {int(price_1m):,} som\n"
        f"3 Oy: {int(price_3m):,} som\n"
        f"1 Yil: {int(price_1y):,} som\n\n"
        f"Kino kanal: <code>{movch}</code>\n\n"
        f"UzCard: <code>{uzcard}</code>\n"
        f"Humo: <code>{humo}</code>\n"
        f"Visa: <code>{visa}</code>\n"
        f"Egasi: {owner}\n\n"
        f"Referral bonus: har {refbonus} ta = 1 oy",
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

async def cb_st_prices(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    price_1m = db.gs("sub_price_1m") or "15000"
    price_3m = db.gs("sub_price_3m") or "40000"
    price_1y = db.gs("sub_price_1y") or "120000"
    await q.edit_message_text(
        f"Obuna narxlari:\n\n"
        f"1 Oy: {int(price_1m):,} som\n"
        f"3 Oy: {int(price_3m):,} som\n"
        f"1 Yil: {int(price_1y):,} som\n\n"
        f"Qaysi narxni ozgartirmoqchisiz?",
        reply_markup=kb.prices_kb()
    )

async def cb_sp(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    plan = q.data.replace("sp_", "")
    ctx.user_data["price_plan"] = plan
    plan_info = db.PLANS.get(plan, {"label": "1 Oy"})
    key = "sub_price_" + plan.replace("_month", "m").replace("_year", "y")
    current = db.gs(key) or "15000"
    await q.edit_message_text(
        f"{plan_info['label']} narxi: {int(current):,} som\n\nYangi narx yuboring:\n\nBekor: /cancel"
    )
    return S_ST_PRICE

async def st_save_price(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam!")
        return S_ST_PRICE
    plan = ctx.user_data.get("price_plan", "1_month")
    key = "sub_price_" + plan.replace("_month", "m").replace("_year", "y")
    db.ss(key, t)
    await update.message.reply_text(f"Narx {int(t):,} som saqlandi!", reply_markup=kb.settings_kb())
    ctx.user_data.clear()
    return END

async def cb_st_movch(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("movie_ch") or MOVIE_CH or "Sozlanmagan"
    await q.edit_message_text(
        f"Hozirgi: <code>{cur}</code>\n\nYangi kino kanal ID yuboring:\n\n"
        f"@JsonDumpBot ga forward qiling\n\nBekor: /cancel",
        parse_mode=H
    )
    return S_ST_MOVCH

async def st_save_movch(update: Update, ctx):
    db.ss("movie_ch", update.message.text.strip())
    await update.message.reply_text("Kino kanal saqlandi!", reply_markup=kb.settings_kb())
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

async def cb_st_refbonus(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cur = db.gs("referral_bonus") or "5"
    await q.edit_message_text(
        f"Hozirgi: har <b>{cur}</b> ta referral = 1 oy premium\n\nYangi sonni yuboring:\n\nBekor: /cancel",
        parse_mode=H
    )
    return S_ST_REFBONUS

async def st_save_refbonus(update: Update, ctx):
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("Faqat raqam!")
        return S_ST_REFBONUS
    db.ss("referral_bonus", t)
    await update.message.reply_text(f"Har {t} ta referral = 1 oy saqlandi!", reply_markup=kb.settings_kb())
    return END

# Admin tomonidan qolda premium berish
async def cmd_give(update: Update, ctx):
    if not db.is_admin(update.effective_user.id): return
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "Format: /give <user_id> <plan>\n"
            "Planlar: 1_month | 3_month | 1_year"
        )
        return
    try:
        uid = int(ctx.args[0])
        plan = ctx.args[1]
        if plan not in db.PLANS:
            await update.message.reply_text("Notogri plan! 1_month | 3_month | 1_year")
            return
        db.give_sub(uid, plan)
        plan_info = db.PLANS[plan]
        await update.message.reply_text(f"{uid} ga {plan_info['label']} premium berildi!")
        try:
            await ctx.bot.send_message(
                uid, f"Admin sizga {plan_info['label']} Pro obuna berdi!",
                reply_markup=kb.user_kb()
            )
        except Exception: pass
    except Exception:
        await update.message.reply_text("Xatolik. Format: /give 123456 1_month")

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
            CallbackQueryHandler(cb_sc_card,      pattern="^sc_(uzcard|humo|visa|owner)$"),
            CallbackQueryHandler(cb_sp,            pattern="^sp_(1_month|3_month|1_year)$"),
            CallbackQueryHandler(cb_st_movch,      pattern="^st_movch$"),
            CallbackQueryHandler(cb_st_welcome,    pattern="^st_welcome$"),
            CallbackQueryHandler(cb_st_refbonus,   pattern="^st_refbonus$"),
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
    app.add_handler(CallbackQueryHandler(cb_chk_sub,      pattern="^chk_sub$"))
    app.add_handler(CallbackQueryHandler(cb_buy_sub,      pattern="^buy_sub$"))
    app.add_handler(CallbackQueryHandler(cb_plan,         pattern="^plan_(1_month|3_month|1_year)$"))
    app.add_handler(CallbackQueryHandler(cb_back_to_plans,pattern="^back_to_plans$"))
    app.add_handler(CallbackQueryHandler(cb_pay_ok,       pattern=r"^pok_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_no,       pattern=r"^pno_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mv_list,      pattern="^mv_list$"))
    app.add_handler(CallbackQueryHandler(cb_mv_back,      pattern="^mv_back$"))
    app.add_handler(CallbackQueryHandler(cb_mv_pro,       pattern="^mv_pro$"))
    app.add_handler(CallbackQueryHandler(cb_ch_add,       pattern="^ch_add$"))
    app.add_handler(CallbackQueryHandler(cb_ch_list,      pattern="^ch_list$"))
    app.add_handler(CallbackQueryHandler(cb_ch_del,       pattern="^ch_del$"))
    app.add_handler(CallbackQueryHandler(cb_dch,          pattern=r"^dch_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_ch_back,      pattern="^ch_back$"))
    app.add_handler(CallbackQueryHandler(cb_adm_list,     pattern="^adm_list$"))
    app.add_handler(CallbackQueryHandler(cb_st_cards,     pattern="^st_cards$"))
    app.add_handler(CallbackQueryHandler(cb_st_prices,    pattern="^st_prices$"))
    app.add_handler(CallbackQueryHandler(cb_st_back,      pattern="^st_back$"))
    app.add_handler(CallbackQueryHandler(cb_cancel,       pattern="^x$"))

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
