import os
import aiosqlite
import jdatetime
from config import DB_PATH

async def get_persian_time():
    now = jdatetime.datetime.now()
    return now.strftime("%Y/%m/%d %H:%M:%S")

async def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, 
            phone TEXT DEFAULT '🔴 ارسال نشده است 🔴', join_date TEXT, 
            wallet_balance INTEGER DEFAULT 0, referral_code TEXT, 
            user_group TEXT DEFAULT 'عادی', is_banned BOOLEAN DEFAULT False)''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, 
            price INTEGER, duration_days INTEGER, gb_limit INTEGER, is_active BOOLEAN DEFAULT True)''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER, 
            status TEXT, price_paid INTEGER, created_at TEXT, receipt_photo TEXT, admin_note TEXT, delivery_text TEXT)''')
        
        # جدول تنظیمات ربات
        await db.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY, value TEXT)''')
        cursor = await db.execute("SELECT COUNT(*) FROM bot_settings")
        if (await cursor.fetchone())[0] == 0:
            await db.execute("INSERT INTO bot_settings (key, value) VALUES ('welcome_text', '💠 درود {name} گرامی؛ به مجموعه تخصصی اینترنت آزاد³⁶⁹ خوش اومدید . از منوی زیر استفاده کنید ⬇️')")
            await db.execute("INSERT INTO bot_settings (key, value) VALUES ('support_text', '📞 **پشتیبانی مجموعه اینترنت آزاد³⁶⁹**\n\nلطفاً پیام خود را تایپ کنید:')")
        
        # جدول جدید برای ذخیره فیش‌های کیف پول
        await db.execute('''CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, 
            status TEXT, receipt_photo TEXT, created_at TEXT)''')
        
        cursor = await db.execute("SELECT COUNT(*) FROM products")
        if (await cursor.fetchone())[0] == 0:
            default_plans = [
                ("🔰 ۲۰ گیگ یکماهه", "کاربر نامحدود", 389000, 30, 20),
                ("🔰 ۳۰ گیگ یکماهه", "کاربر نامحدود", 430000, 30, 30),
                ("🔰 ۵۰ گیگ یکماهه", "کاربر نامحدود", 598000, 30, 50),
                ("🌟 ۱۰۰ گیگ یکماهه", "کاربر نامحدود", 950000, 30, 100)
            ]
            await db.executemany("INSERT INTO products (name, description, price, duration_days, gb_limit) VALUES (?, ?, ?, ?, ?)", default_plans)
        await db.commit()