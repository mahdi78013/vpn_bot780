import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CARD_NUMBER = os.getenv("CARD_NUMBER")
CARD_OWNER = os.getenv("CARD_OWNER")
DB_PATH = os.getenv("DB_PATH", "database.sqlite")
