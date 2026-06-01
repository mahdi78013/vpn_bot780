import os
import logging
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from database import init_db
from config import BOT_TOKEN

from handlers.user import (
    start, user_profile, buy_vpn_start, generate_invoice, receive_receipt, 
    cancel_flow, my_orders, support_start, receive_support_msg, wallet_charge_start, ask_wallet_amount, receive_wallet_receipt,
    CONFIRM_INVOICE, SEND_RECEIPT, WALLET_AMOUNT, WALLET_RECEIPT, SUPPORT_MSG
)
from handlers.admin import (
    admin_panel, handle_admin_action, get_vpn_config, get_reject_reason, cancel_admin, 
    get_broadcast_msg, search_user, ban_user, unban_user, get_admin_reply, edit_welcome_text,
    ASK_CONFIG, ASK_REJECT_REASON, ASK_BROADCAST, ASK_BAN, ASK_UNBAN, ASK_SEARCH, ASK_REPLY, ASK_WELCOME_TEXT
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def post_init(application):
    await init_db()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # فیلتر هوشمند ضد تداخل دکمه‌ها
    MENU_REGEX = "^(🛒 خرید اشتراک|🗂 حساب کاربری|💰 شارژ کیف پول|📦 سفارش‌های من|📞 پشتیبانی|👑 پنل مدیریت)$"

    user_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🛒 خرید اشتراک$"), buy_vpn_start),
            MessageHandler(filters.Regex("^💰 شارژ کیف پول$"), wallet_charge_start),
            MessageHandler(filters.Regex("^📞 پشتیبانی$"), support_start),
        ],
        states={
            CONFIRM_INVOICE: [CallbackQueryHandler(generate_invoice, pattern="^plan_")],
            SEND_RECEIPT: [CallbackQueryHandler(receive_receipt, pattern="^pay_card$"), MessageHandler(filters.PHOTO, receive_receipt)],
            WALLET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), ask_wallet_amount)],
            WALLET_RECEIPT: [MessageHandler(filters.PHOTO, receive_wallet_receipt)],
            SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), receive_support_msg)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_flow),
            CallbackQueryHandler(cancel_flow, pattern="^cancel$"),
            MessageHandler(filters.Regex("^🛒 خرید اشتراک$"), buy_vpn_start),
            MessageHandler(filters.Regex("^💰 شارژ کیف پول$"), wallet_charge_start),
            MessageHandler(filters.Regex("^📞 پشتیبانی$"), support_start),
        ]
    )

    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_admin_action, pattern="^(admin_|approve|reject|wallet|replysupport)"),
            CommandHandler("admin", admin_panel)
        ],
        states={
            ASK_CONFIG: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), get_vpn_config)],
            ASK_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), get_reject_reason)],
            ASK_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), get_broadcast_msg)],
            ASK_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), search_user)],
            ASK_BAN: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), ban_user)],
            ASK_UNBAN: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), unban_user)],
            ASK_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), get_admin_reply)],
            ASK_WELCOME_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(MENU_REGEX), edit_welcome_text)]
        },
        fallbacks=[CommandHandler("cancel_admin", cancel_admin), CallbackQueryHandler(cancel_admin, pattern="^cancel_admin$")]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🗂 حساب کاربری$"), user_profile))
    app.add_handler(MessageHandler(filters.Regex("^📦 سفارش‌های من$"), my_orders))
    
    # متصل کردن دکمه منوی ادمین
    app.add_handler(MessageHandler(filters.Regex("^👑 پنل مدیریت$"), admin_panel))
    
    app.add_handler(user_conv)
    app.add_handler(admin_conv)

    logging.info("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()