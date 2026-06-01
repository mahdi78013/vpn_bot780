from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import aiosqlite
from database import DB_PATH
from config import ADMIN_ID

ASK_CONFIG, ASK_REJECT_REASON, ASK_BROADCAST, ASK_BAN, ASK_UNBAN, ASK_SEARCH, ASK_REPLY, ASK_WELCOME_TEXT = range(8)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("📊 آمار کامل ربات", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast"), InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search")],
        [InlineKeyboardButton("🚫 بن کردن", callback_data="admin_ban"), InlineKeyboardButton("✅ رفع مسدودی", callback_data="admin_unban")],
        [InlineKeyboardButton("📝 تغییر متن خوش‌آمدگویی", callback_data="admin_edit_welcome")],
        [InlineKeyboardButton("🛍 مدیریت پلن‌ها (بزودی)", callback_data="admin_plans")]
    ]
    await update.message.reply_text("👑 **پنل مدیریت جامع سیستم**\nلطفاً بخش مورد نظر را انتخاب کنید:", 
                                    reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin_stats":
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status='approved'")
            total_orders = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT SUM(price) FROM products p JOIN orders o ON p.id = o.product_id WHERE o.status='approved'")
            total_income = (await cursor.fetchone())[0] or 0
            
        stats_text = f"📊 **آمار جامع سیستم:**\n\n👥 کل کاربران: {total_users} نفر\n🛒 کل سفارشات موفق: {total_orders} عدد\n💰 درآمد تقریبی: {total_income:,} تومان"
        await query.message.reply_text(stats_text, parse_mode="Markdown")
        return
    elif data == "admin_broadcast":
        await query.message.reply_text("📢 لطفاً پیامی که قصد ارسال همگانی آن را دارید ارسال کنید:\n\n(برای لغو /cancel_admin بزنید)")
        return ASK_BROADCAST
    elif data == "admin_search":
        await query.message.reply_text("🔍 لطفاً آیدی عددی (Telegram ID) کاربر را بفرستید:")
        return ASK_SEARCH
    elif data == "admin_ban":
        await query.message.reply_text("🚫 لطفاً آیدی عددی کاربری که قصد مسدودسازی او را دارید بفرستید:")
        return ASK_BAN
    elif data == "admin_unban":
        await query.message.reply_text("✅ لطفاً آیدی عددی کاربری که قصد رفع مسدودی او را دارید بفرستید:")
        return ASK_UNBAN
    elif data == "admin_edit_welcome":
        await query.message.reply_text("📝 لطفاً متن جدید خوش‌آمدگویی ربات را بفرستید:\n(برای نمایش نام کاربر از کلمه `{name}` در متن استفاده کنید)\n\n(برای لغو /cancel_admin بزنید)", parse_mode="Markdown")
        return ASK_WELCOME_TEXT

    if data.startswith("replysupport_"):
        user_id = data.split("_")[1]
        context.user_data['reply_to_user'] = user_id
        await query.message.reply_text(f"💬 لطفاً پاسخ خود را برای کاربر `{user_id}` تایپ کنید:\n\n(برای لغو /cancel_admin بزنید)", parse_mode="Markdown")
        return ASK_REPLY

    if data.startswith("walletconfirm_"):
        tx_id = data.split("_")[1]
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT amount FROM wallet_transactions WHERE id = ?", (tx_id,)) as cursor:
                tx_data = await cursor.fetchone()
                if not tx_data: return
                amount = tx_data[0]
        keyboard = [[InlineKeyboardButton(f"✅ بله، {amount:,} تومان شارژ شود", callback_data=f"walletapprove_{tx_id}")],
                    [InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_admin")]]
        await query.message.reply_text(f"❓ آیا تایید می‌کنید مبلغ **{amount:,} تومان** شارژ شود؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    elif data.startswith("walletapprove_"):
        tx_id = int(data.split("_")[1])
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, amount FROM wallet_transactions WHERE id = ?", (tx_id,)) as cursor:
                tx = await cursor.fetchone()
            if tx:
                user_id, amount = tx
                await db.execute("UPDATE wallet_transactions SET status = 'approved' WHERE id = ?", (tx_id,))
                await db.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE telegram_id = ?", (amount, user_id))
                await db.commit()
                await query.edit_message_text(f"✅ مبلغ {amount:,} تومان واریز شد.")
                await context.bot.send_message(chat_id=user_id, text=f"🎉 **کیف پول شما مبلغ {amount:,} تومان شارژ شد!**", parse_mode="Markdown")
        return ConversationHandler.END
    elif data.startswith("walletreject_"):
        tx_id = int(data.split("_")[1])
        context.user_data['processing_wallet_tx'] = tx_id
        await query.message.reply_text(f"❌ دلیل رد فیش #{tx_id} را بنویسید:")
        return ASK_REJECT_REASON

    action, order_id = data.split("_")
    context.user_data['processing_order'] = int(order_id)
    if action == "approve":
        await query.message.reply_text(f"✅ کانفیگ (متن VPN) سفارش #{order_id} را ارسال کنید:")
        return ASK_CONFIG
    elif action == "reject":
        await query.message.reply_text(f"❌ دلیل رد سفارش #{order_id} را بنویسید:")
        return ASK_REJECT_REASON

# --- فانکشن جدید برای آپدیت دیتابیس متون ---
async def edit_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_text = update.message.text
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE bot_settings SET value = ? WHERE key = 'welcome_text'", (new_text,))
        await db.commit()
    await update.message.reply_text("✅ متن خوش‌آمدگویی ربات با موفقیت تغییر کرد.")
    return ConversationHandler.END

async def get_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_text = update.message.text
    target_user = context.user_data.get('reply_to_user')
    await context.bot.send_message(chat_id=target_user, text=f"👨‍💻 **پاسخ پشتیبانی:**\n\n{reply_text}", parse_mode="Markdown")
    await update.message.reply_text("✅ پیام شما به کاربر ارسال شد.")
    return ConversationHandler.END

async def get_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users") as cursor:
            users = await cursor.fetchall()
    count = 0
    await update.message.reply_text("⏳ در حال ارسال پیام...")
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=f"📢 **اطلاعیه:**\n\n{msg}", parse_mode="Markdown")
            count += 1
        except:
            pass
    await update.message.reply_text(f"✅ پیام همگانی با موفقیت به {count} نفر ارسال شد.")
    return ConversationHandler.END

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT full_name, wallet_balance, is_banned FROM users WHERE telegram_id = ?", (target_id,)) as cursor:
                user = await cursor.fetchone()
        if user:
            status = "🔴 مسدود" if user[2] else "🟢 فعال"
            await update.message.reply_text(f"🔍 **اطلاعات کاربر:**\n\n👤 نام: {user[0]}\n💰 موجودی: {user[1]:,} تومان\nوضعیت: {status}")
        else:
            await update.message.reply_text("❌ کاربری با این آیدی یافت نشد.")
    except:
        await update.message.reply_text("آیدی نامعتبر است.")
    return ConversationHandler.END

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET is_banned = True WHERE telegram_id = ?", (target_id,))
            await db.commit()
        await update.message.reply_text(f"✅ کاربر {target_id} با موفقیت مسدود شد.")
    except:
        await update.message.reply_text("خطا در مسدودسازی.")
    return ConversationHandler.END

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET is_banned = False WHERE telegram_id = ?", (target_id,))
            await db.commit()
        await update.message.reply_text(f"✅ مسدودی کاربر {target_id} با موفقیت لغو شد.")
    except:
        await update.message.reply_text("خطا در عملیات.")
    return ConversationHandler.END

async def get_vpn_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config_text = update.message.text
    order_id = context.user_data['processing_order']
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status = 'approved', delivery_text = ? WHERE id = ?", (config_text, order_id))
        async with db.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,)) as cursor:
            user_id = (await cursor.fetchone())[0]
        await db.commit()
    await context.bot.send_message(chat_id=user_id, text=f"✅ **سفارش تایید شد!**\n🔑 **کانفیگ:**\n`{config_text}`", parse_mode="Markdown")
    await update.message.reply_text("✅ ارسال شد.")
    return ConversationHandler.END

async def get_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    if 'processing_wallet_tx' in context.user_data:
        tx_id = context.user_data['processing_wallet_tx']
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE wallet_transactions SET status = 'rejected' WHERE id = ?", (tx_id,))
            async with db.execute("SELECT user_id FROM wallet_transactions WHERE id = ?", (tx_id,)) as cursor:
                user_id = (await cursor.fetchone())[0]
            await db.commit()
        await context.bot.send_message(chat_id=user_id, text=f"❌ **درخواست شارژ رد شد.**\nدلیل: {reason}", parse_mode="Markdown")
        del context.user_data['processing_wallet_tx']
    else:
        order_id = context.user_data.get('processing_order')
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE orders SET status = 'rejected', admin_note = ? WHERE id = ?", (reason, order_id))
            async with db.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,)) as cursor:
                user_id = (await cursor.fetchone())[0]
            await db.commit()
        await context.bot.send_message(chat_id=user_id, text=f"❌ **سفارش تایید نشد.**\nدلیل: {reason}", parse_mode="Markdown")
    await update.message.reply_text("❌ ارسال شد.")
    return ConversationHandler.END

async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.edit_message_text("عملیات لغو شد.")
    else:
        await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END
