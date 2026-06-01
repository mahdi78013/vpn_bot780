from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import aiosqlite
import jdatetime
from database import DB_PATH, get_persian_time
from config import ADMIN_ID, CARD_NUMBER, CARD_OWNER

CONFIRM_INVOICE, SEND_RECEIPT, WALLET_AMOUNT, WALLET_RECEIPT, SUPPORT_MSG = range(5)

async def is_user_banned(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await is_user_banned(user.id):
        await update.message.reply_text("🚫 دسترسی شما به ربات مسدود شده است.")
        return

    username = f"@{user.username}" if user.username else "بدون یوزرنیم"
    now_persian = await get_persian_time()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (telegram_id, username, full_name, join_date, referral_code) VALUES (?, ?, ?, ?, ?)",
                         (user.id, username, user.full_name, now_persian, f"{user.id:x}"))
        async with db.execute("SELECT value FROM bot_settings WHERE key = 'welcome_text'") as cursor:
            welcome_template = (await cursor.fetchone())[0]
        await db.commit()

    # --- چیدمان داینامیک دکمه‌ها ---
    keyboard = [["🛒 خرید اشتراک", "🗂 حساب کاربری"], ["💰 شارژ کیف پول", "📦 سفارش‌های من"], ["📞 پشتیبانی"]]
    
    # اگر کاربر، ادمین سیستم بود دکمه مدیریت اضافه می‌شود
    if user.id == ADMIN_ID:
        keyboard.append(["👑 پنل مدیریت"])
        
    text = welcome_template.replace("{name}", user.full_name)
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode="Markdown")

async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update.effective_user.id): return
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            user_data = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'approved'", (user_id,)) as cursor:
            orders_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status IN ('approved', 'pending')", (user_id,)) as cursor:
            invoices_count = (await cursor.fetchone())[0]

    now = jdatetime.datetime.now()
    text = (f"🗂 **اطلاعات حساب کاربری شما :**\n\n🪪 شناسه کاربری: `{user_data[0]}`\n👤 نام: {user_data[2]}\n"
            f"👨‍👩‍👦 کد معرف شما: `{user_data[6]}`\n📱 شماره تماس: {user_data[3]}\n⌚️ زمان ثبت نام: {user_data[4]}\n"
            f"💰 موجودی: {user_data[5]:,} تومان\n🛒 تعداد سرویس های خریداری شده: {orders_count} عدد\n"
            f"📑 تعداد فاکتور های پرداخت شده: {invoices_count} عدد\n🤝 تعداد زیر مجموعه های شما: 0 نفر\n"
            f"🔖 گروه کاربری: {user_data[7]}\n\n📆 {now.strftime('%Y/%m/%d')}  →  ⏰ {now.strftime('%H:%M:%S')}")
    await update.message.reply_text(text, parse_mode="Markdown")

async def buy_vpn_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update.effective_user.id): return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price FROM products WHERE is_active = True") as cursor:
            plans = await cursor.fetchall()

    keyboard = []
    for plan in plans:
        plan_id, name, price = plan
        btn_text = f"{name} | {price:,} تومان"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"plan_{plan_id}")])
    keyboard.append([InlineKeyboardButton("🔙 انصراف", callback_data="cancel_order")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "🌐 **جهت تهیه سرویس جدید، پنل مورد نظر رو انتخاب کنید:**"
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return CONFIRM_INVOICE

async def generate_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[1])
    context.user_data['selected_plan_id'] = plan_id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, duration_days, price, gb_limit FROM products WHERE id = ?", (plan_id,)) as cursor:
            plan = await cursor.fetchone()
        async with db.execute("SELECT wallet_balance FROM users WHERE telegram_id = ?", (update.effective_user.id,)) as cursor:
            wallet = (await cursor.fetchone())[0]

    text = (f"📇 **پیش فاکتور شما:**\n\n👤 نام کاربری: `{update.effective_user.id}`\n🔐 نام سرویس: {plan[0]}\n"
            f"📆 مدت اعتبار: {plan[1]} روز\n💶 قیمت: {plan[2]:,} تومان\n👥 حجم اکانت: {plan[3]} گیگ\n"
            f"🗒 یادداشت محصول: سرویس اختصاصی\n💵 موجودی کیف پول شما: {wallet:,} تومان\n\n💰 **سفارش شما آماده پرداخت است.**")
    keyboard = [[InlineKeyboardButton("💳 پرداخت کارت به کارت", callback_data="pay_card")],
                [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="cancel_order")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return SEND_RECEIPT

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query and update.callback_query.data == "pay_card":
        text = f"💳 **پرداخت کارت به کارت**\n\nلطفاً مبلغ فاکتور را به کارت زیر واریز نمایید:\n\n📌 `{CARD_NUMBER}`\n👤 به نام: {CARD_OWNER}\n\n⚠️ **پس از واریز، عکس رسید خود را همینجا ارسال کنید.**"
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        return SEND_RECEIPT

    if not update.message or not update.message.photo:
        return SEND_RECEIPT

    photo_id = update.message.photo[-1].file_id
    plan_id = context.user_data.get('selected_plan_id')
    now = await get_persian_time()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM products WHERE id = ?", (plan_id,)) as cursor:
            plan_name = (await cursor.fetchone())[0]
        cursor = await db.execute("INSERT INTO orders (user_id, product_id, status, created_at, receipt_photo) VALUES (?, ?, 'pending', ?, ?)", 
                                  (update.effective_user.id, plan_id, now, photo_id))
        order_id = cursor.lastrowid
        await db.commit()

    success_text = ("✅ رسید شما با موفقیت ثبت شد و در صف بررسی قرار گرفت ⏳\n\n"
                    "💡 **نکته مهم:** جهت حفظ بالاترین کیفیت، سرعت و پایداری، هر سرور اختصاصی نهایتاً برای ۱۰ کاربر تنظیم می‌شود. "
                    "لطفاً تا زمان ساخت و پیکربندی پنل اختصاصی خود صبور باشید.")
    await update.message.reply_text(success_text, parse_mode="Markdown")
    
    admin_text = f"🔔 **سفارش جدید #{order_id}**\n\n👤 کاربر: `{update.effective_user.id}`\n📦 پلن درخواستی: **{plan_name}**\n🕐 زمان: {now}"
    keyboard = [[InlineKeyboardButton("✅ تایید و ارسال VPN", callback_data=f"approve_{order_id}")],
                [InlineKeyboardButton("❌ رد سفارش", callback_data=f"reject_{order_id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update.effective_user.id): return
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT o.id, p.name, o.status, o.created_at, o.delivery_text FROM orders o JOIN products p ON o.product_id = p.id WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 5", (user_id,)) as cursor:
            orders = await cursor.fetchall()

    if not orders:
        await update.message.reply_text("📦 شما هنوز هیچ سفارشی ثبت نکرده‌اید.")
        return

    text = "📦 **۵ سفارش آخر شما:**\n\n"
    status_dict = {"pending": "در انتظار تایید ⏳", "approved": "تایید شده ✅", "rejected": "رد شده ❌"}
    for o in orders:
        text += f"🔖 سفارش `#{o[0]}`\n🛍 محصول: {o[1]}\n📅 تاریخ: {o[3]}\nوضعیت: {status_dict.get(o[2], o[2])}\n"
        if o[2] == "approved" and o[4]:
            text += f"🔑 **کانفیگ:**\n`{o[4]}`\n"
        text += "━━━━━━━━━━━━━━\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update.effective_user.id): return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key = 'support_text'") as cursor:
            text = (await cursor.fetchone())[0]
    
    await update.message.reply_text(text + "\n\n(برای لغو /cancel را ارسال کنید)", parse_mode="Markdown")
    return SUPPORT_MSG

async def receive_support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg_text = update.message.text
    
    await update.message.reply_text("✅ پیام شما با موفقیت برای پشتیبانی ارسال شد. لطفاً منتظر پاسخ باشید.")
    
    admin_msg = f"📩 **تیکت پشتیبانی جدید**\n\n👤 از: {user.full_name}\n🆔 آیدی عددی: `{user.id}`\n\n📝 **متن پیام:**\n{msg_text}"
    keyboard = [[InlineKeyboardButton("پاسخ به این کاربر 💬", callback_data=f"replysupport_{user.id}")]]
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END

async def wallet_charge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update.effective_user.id): return
    text = "💰 **شارژ کیف پول**\n\nلطفاً مبلغ مورد نظر خود را برای شارژ (به تومان) به صورت **عدد** وارد کنید:\nمثال: `50000`\n\n(برای لغو عملیات /cancel را ارسال کنید)"
    await update.message.reply_text(text, parse_mode="Markdown")
    return WALLET_AMOUNT

async def ask_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text
    if not amount_text.isdigit():
        await update.message.reply_text("⚠️ لطفاً مبلغ را فقط به صورت عدد وارد کنید:")
        return WALLET_AMOUNT

    amount = int(amount_text)
    if amount < 10000:
        await update.message.reply_text("⚠️ حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است. لطفاً مبلغ بیشتری وارد کنید:")
        return WALLET_AMOUNT

    context.user_data['wallet_amount'] = amount
    text = f"💳 **پرداخت کارت به کارت**\n\n💰 مبلغ درخواستی: {amount:,} تومان\nلطفاً مبلغ فوق را به کارت زیر واریز کنید:\n\n📌 `{CARD_NUMBER}`\n👤 به نام: {CARD_OWNER}\n\n⚠️ **سپس عکس فیش واریزی را همینجا ارسال کنید.**\n\n(برای لغو /cancel را ارسال کنید)"
    await update.message.reply_text(text, parse_mode="Markdown")
    return WALLET_RECEIPT

async def receive_wallet_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً فقط عکس فیش واریزی را ارسال کنید.")
        return WALLET_RECEIPT

    photo_id = update.message.photo[-1].file_id
    amount = context.user_data.get('wallet_amount', 0)
    now = await get_persian_time()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO wallet_transactions (user_id, amount, status, receipt_photo, created_at) VALUES (?, ?, 'pending', ?, ?)",
                                  (update.effective_user.id, amount, photo_id, now))
        tx_id = cursor.lastrowid
        await db.commit()

    await update.message.reply_text("✅ فیش واریزی شما جهت شارژ کیف پول با موفقیت ثبت شد و در حال بررسی است ⏳")

    admin_text = f"🔔 **درخواست شارژ کیف پول #{tx_id}**\n\n👤 کاربر: `{update.effective_user.id}`\n💰 مبلغ درخواستی: **{amount:,} تومان**\n🕐 زمان: {now}"
    keyboard = [[InlineKeyboardButton("✅ بررسی و تایید فیش", callback_data=f"walletconfirm_{tx_id}")],
                [InlineKeyboardButton("❌ رد فیش", callback_data=f"walletreject_{tx_id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.edit_message_text("❌ عملیات لغو شد.")
    else:
        await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END
