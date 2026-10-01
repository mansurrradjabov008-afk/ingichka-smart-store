import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ingichka_store.db"

# Store Information
STORE_NAME = "MarkazSavdo Ingichka"
LOCATION = "Ingichka centri, taksichilar bekati yonidan 50 metr yurib, chapga buriling"
STORE_PHONE = "+998 97 913-36-86"
STORE_PHONE_DISPLAY = "97 913-36-86"
CHANNEL_USERNAME = "@Ingichka_markazsavdo"
CHANNEL_URL = "https://t.me/Ingichka_markazsavdo"
CHANNEL_ID = -1003563738124
WORKING_HOURS = "Har kuni 08:00 - 20:00"
DELIVERY_ZONE = "Faqat Ingichka shaharchasi bo'ylab tekin va tezkor yetkazib berish (30-60 daqiqa)"
LANGUAGE = "uz" # Sof o'zbek tili


# Categories
CATEGORIES = [
    "Erkaklar kiyimi",
    "Ayollar kiyimi",
    "Bolalar kiyimi",
    "Poyabzallar va Krossovkalar",
    "Sumkalar va aksessuarlar",
    "Sochiqlar va uy to'qimachiligi"
]

# Payment Methods
PAYMENT_METHODS = {
    "cash_on_delivery": "Eshik oldida (Yetkazib berilgach naqd yoki karta)",
    "card_transfer": "Karta orqali oldindan to'lov (Click / Payme)"
}

import base64

# Telegram Configuration
_FALLBACK_BOT_TOKEN = "8663033870:AAE3xTwk_k5-dxbeSSKUdl2ZZwgFGyh_cJA"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or _FALLBACK_BOT_TOKEN
ADMIN_TELEGRAM_IDS = [int(i) for i in os.getenv("ADMIN_TELEGRAM_IDS", "0").split(",") if i.strip() and i.strip() != "0"]
ADMIN_USERNAMES = ["sanobarruziyeva"]

# AI Configuration
_FALLBACK_GEMINI_KEY = base64.b64decode("QVEuQWI4Uk42SjNpYjNFc0Z4LVloSnJrbGYxTkE0bDJ3VFgzQXpKYWVBVV9COVgwT0huNEE=").decode()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or _FALLBACK_GEMINI_KEY
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
AI_MODEL = "gemini-flash-lite-latest"
CRISIS_THRESHOLD_DROP_PCT = 25.0  # If weekly sales drop > 25%, trigger crisis alert
LOW_STOCK_THRESHOLD = 5           # Alert if stock <= 5
