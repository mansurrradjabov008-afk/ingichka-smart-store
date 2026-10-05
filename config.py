import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ingichka_store.db"

# Do'kon sozlamalari (Store Settings)
# Agar ushbu sozlamalar bo'sh bo'lsa, bot "Buni egasidan so'rab aytaman" deb javob beradi va egasiga xabar yuboradi.
STORE_SETTINGS = {
    "delivery": os.getenv("STORE_DELIVERY", "").strip(),
    "discount": os.getenv("STORE_DISCOUNT", "").strip(),
    "address": os.getenv("STORE_ADDRESS", "").strip(),
}

# Store Information
STORE_NAME = os.getenv("STORE_NAME", "MarkazSavdo")
LOCATION = STORE_SETTINGS["address"]
DELIVERY_ZONE = STORE_SETTINGS["delivery"]
STORE_PHONE = os.getenv("STORE_PHONE", "+998 33 261-09-28")
STORE_PHONE_DISPLAY = "33 261-09-28"
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@markazsavdo")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/markazsavdo")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003563738124"))
WORKING_HOURS = os.getenv("WORKING_HOURS", "Har kuni 08:00 - 20:00")
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
    "cash_on_delivery": "Eshik oldida to'lov (naqd yoki karta)",
    "card_transfer": "Karta orqali oldindan to'lov (Click / Payme)"
}

import base64

# Telegram Configuration
_FALLBACK_BOT_TOKEN = "8663033870:AAE3xTwk_k5-dxbeSSKUdl2ZZwgFGyh_cJA"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or _FALLBACK_BOT_TOKEN
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
ADMIN_TELEGRAM_IDS = [int(i) for i in os.getenv("ADMIN_TELEGRAM_IDS", "0").split(",") if i.strip() and i.strip() != "0"]
if ADMIN_CHAT_ID and ADMIN_CHAT_ID.lstrip("-").isdigit() and int(ADMIN_CHAT_ID) not in ADMIN_TELEGRAM_IDS:
    ADMIN_TELEGRAM_IDS.append(int(ADMIN_CHAT_ID))
ADMIN_USERNAMES = ["radjabovmansur", "sanobarruziyeva"]

# AI Configuration
_FALLBACK_GEMINI_KEY = base64.b64decode("QVEuQWI4Uk42Sm0tc0g5NFJHYWxfd2ZvYjd6bzhZZUdFSnJPZERNNVR6ZElhWnVuY3VmMGc=").decode()
raw_gemini = os.getenv("GEMINI_API_KEY", "").strip()
if not raw_gemini or raw_gemini.startswith("AIzaSy"):
    GEMINI_API_KEY = _FALLBACK_GEMINI_KEY
else:
    GEMINI_API_KEY = raw_gemini
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
AI_MODEL = "gemini-3.5-flash"
CRISIS_THRESHOLD_DROP_PCT = 25.0
LOW_STOCK_THRESHOLD = 2 # Qoida 3: stock <= 2
