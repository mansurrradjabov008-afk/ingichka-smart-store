import asyncio
import logging
import os
import sys
import io
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types.error_event import ErrorEvent
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import (
    BOT_TOKEN, ADMIN_TELEGRAM_IDS, STORE_NAME, LOCATION, DELIVERY_ZONE, STORE_SETTINGS,
    GEMINI_API_KEY, OPENAI_API_KEY, GROQ_API_KEY,
    STORE_PHONE, CHANNEL_USERNAME, CHANNEL_URL, WORKING_HOURS, CHANNEL_ID, ADMIN_USERNAMES,
    ADMIN_CHAT_ID
)

from database.db_manager import DatabaseManager, init_db
from ai_engine.sales_agent import SalesAgent
from ai_engine.ai_brain import ai_brain
from services.analytics_advisor import AnalyticsAdvisor
from services.inventory_manager import InventoryManager
from services.voice_service import VoiceService
from services.receipt_checker import ReceiptChecker
from services.excel_exporter import ExcelExporter
from services.tenant_manager import TenantManager
from services.sales_pitch import SalesPitchAdvisor
from services.order_matcher import OrderMatcher
from services.store_settings_manager import StoreSettingsManager
from services.cart_manager import CartManager
from services.promo_manager import PromoManager
from services.order_tracker import OrderTracker
from services.review_manager import ReviewManager
from services.recommendation_engine import RecommendationEngine
from services.waitlist_service import WaitlistService
from services.stock_advisor import StockAdvisor, PENDING_WAITLIST_OFFERS
from services.media_service import send_product_presentation, format_product_caption
from services.order_flow_service import OrderFlowService
from services.sales_intelligence import SalesIntelligence
from bot.keyboards import (
    get_main_menu, get_category_keyboard, get_report_periods_keyboard,
    get_order_action_keyboard, get_order_approval_keyboard, get_phone_request_keyboard, get_location_request_keyboard,
    get_channel_buy_button, get_product_card_keyboard, get_cart_keyboard, get_review_stars_keyboard
)
from utils.logger import log_bot_error, BOT_LOG_FILE

log_file_path = Path(__file__).resolve().parent.parent / "logs" / "bot_live.log"
log_file_path.parent.mkdir(parents=True, exist_ok=True)

handlers_list = [
    logging.FileHandler(str(log_file_path), encoding="utf-8"),
    logging.FileHandler(str(BOT_LOG_FILE), encoding="utf-8")
]
if sys.stdout and not getattr(sys.stdout, 'closed', False):
    handlers_list.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=handlers_list)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
agent = SalesAgent()

# Foydalanuvchilarning davom etayotgan (pending) buyurtmalari xotirasi (Multi-turn Order State, TTL 2 soat)
USER_PENDING_ORDERS: Dict[int, Dict[str, Any]] = {}

def set_pending_order(user_id: int, product: Dict[str, Any]):
    import time
    USER_PENDING_ORDERS[user_id] = {
        "product": product,
        "timestamp": time.time()
    }

def get_pending_order(user_id: int, max_age_seconds: int = 7200) -> Optional[Dict[str, Any]]:
    import time
    entry = USER_PENDING_ORDERS.get(user_id)
    if not entry:
        return None
    if isinstance(entry, dict) and "product" in entry:
        if time.time() - entry.get("timestamp", 0) > max_age_seconds:
            USER_PENDING_ORDERS.pop(user_id, None)
            return None
        return entry["product"]
    return entry

def clear_pending_order(user_id: int):
    USER_PENDING_ORDERS.pop(user_id, None)

PROMO_WAITING_USERS: set = set()
CHECKOUT_WAITING_USERS: Dict[int, Dict[str, Any]] = {}

def is_admin_user(user: Optional[types.User], chat_id: Optional[int] = None) -> bool:
    if not user and not chat_id:
        return False
    u_id = user.id if user else None
    c_id = chat_id
    if ADMIN_CHAT_ID:
        if (u_id and str(u_id) == str(ADMIN_CHAT_ID)) or (c_id and str(c_id) == str(ADMIN_CHAT_ID)):
            return True
    if u_id and u_id in ADMIN_TELEGRAM_IDS:
        return True
    if c_id and c_id in ADMIN_TELEGRAM_IDS:
        return True
    if user and user.username and user.username.lower() in [u.lower().replace("@", "") for u in ADMIN_USERNAMES]:
        if user.id not in ADMIN_TELEGRAM_IDS:
            ADMIN_TELEGRAM_IDS.append(user.id)
            logger.info(f"Registered admin user by username: @{user.username} (ID: {user.id})")
        return True
    return False

# Initialize AI Brain keys if configured
if GEMINI_API_KEY:
    ai_brain.set_api_key(GEMINI_API_KEY, "gemini")
if OPENAI_API_KEY:
    ai_brain.set_api_key(OPENAI_API_KEY, "openai")
if GROQ_API_KEY:
    ai_brain.set_api_key(GROQ_API_KEY, "groq")

async def safe_send(chat_id: int, text: str, reply_markup=None):
    """Xabarni xatosiz yetkazish kafolati (Markdown xatoliklaridan himoyalangan va 4096 belgi limitga mos)"""
    if not text:
        return None

    # Agar matn 4000 belgidan uzun bo'lsa, xavfsiz bo'laklarga ajratish
    chunks = []
    if len(text) > 4000:
        lines = text.split("\n")
        curr = ""
        for l in lines:
            if len(curr) + len(l) + 1 > 3900:
                chunks.append(curr)
                curr = l + "\n"
            else:
                curr += l + "\n"
        if curr:
            chunks.append(curr)
    else:
        chunks = [text]

    last_msg = None
    for idx, chunk in enumerate(chunks):
        markup = reply_markup if idx == len(chunks) - 1 else None
        try:
            last_msg = await asyncio.wait_for(
                bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown", reply_markup=markup),
                timeout=12.0
            )
        except TelegramBadRequest:
            clean_text = chunk.replace("**", "").replace("*", "").replace("`", "")
            try:
                last_msg = await asyncio.wait_for(
                    bot.send_message(chat_id=chat_id, text=clean_text, reply_markup=markup),
                    timeout=12.0
                )
            except Exception as e:
                log_bot_error(chat_id, f"Telegram send_message retry failed: {e}", exc=e)
        except Exception as e:
            log_bot_error(chat_id, f"Telegram send_message failed: {e}", exc=e)
    return last_msg


def clean_display_name(name: Optional[str], preferred: Optional[str] = None) -> str:
    """Xaridorning ismini tozalash (jinsini taxmin qilmasdan)"""
    if preferred and preferred.strip():
        return preferred.strip()
    if not name:
        return "Mijoz"
    import re
    n = re.sub(r"[\U00010000-\U0010ffff]", "", name).strip()
    n = re.sub(r"[@_#*`~]", "", n).strip()
    parts = n.split()
    if not parts:
        return "Mijoz"
    surname_suffixes = ("ov", "ova", "ev", "eva", "yev", "yeva", "ов", "ова", "ев", "ева")
    if len(parts) == 1 and parts[0].lower().endswith(surname_suffixes):
        return "Mijoz"
    if parts[0].lower().endswith(surname_suffixes) and len(parts) > 1:
        return parts[1]
    return parts[0]

def extract_preferred_name(text: str) -> Optional[str]:
    """Xabar ichidan xaridor o'z ismini aytganini aniqlash"""
    import re
    patterns = [
        r"(?:mening\s+ismim|ismim)\s+([A-Za-zА-Яа-яЎўҚқҒғҲҳ]{3,20})",
        r"(?:men\s+)([A-Za-zА-Яа-яЎўҚқҒғҲҳ]{3,20})(?:man|man\b)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1).capitalize()
            if val.lower() not in ["biror", "narsa", "bitta", "qora", "xudi", "kurtka", "krasovka", "dostavka"]:
                return val
    return None

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name or "Mijoz"
    username = message.from_user.username
    is_admin = is_admin_user(message.from_user)

    # DB ga mijozni qayd etish
    DatabaseManager.upsert_customer(
        telegram_id=user_id,
        full_name=user_name,
        username=username
    )

    # 1. Telegram Kanal Postidan chuqur havola (Deep Link: /start buy_16)
    parts = (message.text or "").split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""
    if args.startswith("buy_"):
        try:
            prod_id = int(args.replace("buy_", ""))
            prod = DatabaseManager.get_product_by_id(prod_id)
            if prod and prod["stock_quantity"] > 0:
                set_pending_order(user_id, prod)
                display_name = clean_display_name(message.from_user.first_name)
                stock = prod.get("stock_quantity", 0)
                stock_label = f"🔥 Shoshiling, oxirgi {stock} ta qoldi!" if 0 < stock <= 3 else f"{stock} dona mavjud"
                card_text = (
                    f"✨ **Ajoyib tanlov!**\n\n"
                    f"🛍️ **Mahsulot:** **{prod['name']}**\n"
                    f"📏 **O'lcham:** {prod['size']} | **Rang:** {prod['color']}\n"
                    f"💰 **Narxi:** **{prod['sale_price']:,.0f} so'm**\n"
                    f"📊 **Omborda:** {stock_label}\n\n"
                    f"To'lovni tovar yoqqanidan so'ng qilasiz (naqd yoki karta).\n\n"
                    f"📦 **Buyurtmani tasdiqlash uchun:**\n"
                    f"Iltimos, pastdagi **'📱 Telefon raqamimni yuborish'** tugmasini bosing yoki telefon raqamingiz va manzilingizni yozib yuboring 👇"
                )
                await safe_send(
                    chat_id=message.chat.id,
                    text=card_text,
                    reply_markup=get_phone_request_keyboard()
                )
                return
            else:
                await safe_send(
                    chat_id=message.chat.id,
                    text="Kechirasiz, siz tanlagan tovarimiz ayni daqiqada sotib bo'lindi. Lekin do'konimizda boshqa sara modellar bor! Quyidagi katalogdan ko'rishingiz mumkin:",
                    reply_markup=get_category_keyboard()
                )
                return
        except Exception as e:
            logger.error(f"Deep link error: {e}")

    cart_cnt = CartManager.get_cart_item_count(user_id)
    if is_admin:
        await safe_send(
            chat_id=message.chat.id,
            text=(
                f"👑 **Xush kelibsiz!**\n\n"
                f"Bu sening **'{STORE_NAME}'** AI Sotuvchi va Menejer tiziming.\n"
                f"Men 24/7 rejimda mijozlarga xizmat ko'rsataman, buyurtmalarni qabul qilaman va omborni nazorat qilaman.\n\n"
                f"Quyidagi tugmalar orqali kerakli bo'limni tanlang 👇"
            ),
            reply_markup=get_main_menu(is_admin=True, cart_count=cart_cnt)
        )
    else:
        clean_name = user_name if user_name and user_name != "Mijoz" else ""
        greeting = f"Assalomu alaykum, {clean_name}!" if clean_name else "Assalomu alaykum!"
        await safe_send(
            chat_id=message.chat.id,
            text=(
                f"{greeting} Xush kelibsiz!\n\n"
                f"Men **{STORE_NAME}** do'konining maslahatchisiman 😊\n\n"
                f"Bizda sifatli erkaklar, ayollar, bolalar kiyimlari va poyabzallar mavjud.\n\n"
                f"Sizga qanday mahsulot yoki kiyim kerak? Bemalol yozishingiz yoki mahsulotlarimizni ko'rishingiz mumkin ✨"
            ),
            reply_markup=get_main_menu(is_admin=False, cart_count=cart_cnt)
        )

# Foydalanuvchi tugmasi orqali telefon raqam yuborilganda
@dp.message(F.contact)
async def handle_contact_message(message: types.Message):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    user_name = clean_display_name(message.from_user.first_name)
    DatabaseManager.upsert_customer(telegram_id=user_id, full_name=user_name, phone=phone)

    # Task 3: Agar faol buyurtma oqimi mavjud bo'lsa
    if OrderFlowService.has_active_flow(message.chat.id):
        customer = DatabaseManager.get_customer(user_id)
        step_res = OrderFlowService.process_step(
            chat_id=message.chat.id,
            text=phone,
            user_name=user_name,
            crm_customer=customer,
            ai_answer_fn=lambda q: ai_brain.ask(message.chat.id, q, customer_name=user_name)
        )
        if step_res.get("reply"):
            await safe_send(message.chat.id, step_res["reply"])
        if step_res.get("is_completed") and step_res.get("admin_alert"):
            admin_alert = step_res["admin_alert"]
            db_ord_id = step_res.get("db_order_id") or 0
            kb = get_order_approval_keyboard(db_ord_id)
            target_admins = list(ADMIN_TELEGRAM_IDS)
            if ADMIN_CHAT_ID and ADMIN_CHAT_ID.lstrip("-").isdigit() and int(ADMIN_CHAT_ID) not in target_admins:
                target_admins.append(int(ADMIN_CHAT_ID))
            for aid in target_admins:
                try:
                    await safe_send(aid, admin_alert, reply_markup=kb)
                except Exception as e:
                    log_bot_error(aid, f"Failed to send admin order alert: {e}", exc=e)
        return

    # Agar savatchadan ko'p tovarli buyurtma kutilayotgan bo'lsa
    if user_id in CHECKOUT_WAITING_USERS:
        CHECKOUT_WAITING_USERS[user_id]["phone"] = phone
        CHECKOUT_WAITING_USERS[user_id]["stage"] = "address"
        await safe_send(
            chat_id=message.chat.id,
            text=(
                f"📱 Telefon raqamingiz qabul qilindi: `{phone}` ✅\n\n"
                f"Endi buyurtmangizni yetkazib berish **manzilini** yozib yuboring (yoki pastdagi geolokatsiya tugmasini bosing) 👇"
            ),
            reply_markup=get_location_request_keyboard()
        )
        return

    pending_prod = get_pending_order(user_id)
    if pending_prod:
        await safe_send(
            chat_id=message.chat.id,
            text=(
                f"📱 Telefon raqamingiz qabul qilindi: `{phone}` ✅\n\n"
                f"🛍️ Tanlangan tovar: **{pending_prod['name']}** ({pending_prod['sale_price']:,.0f} so'm)\n\n"
                f"Endi yetkazish manzilingizni yozib yuboring yoki pastdagi **'📍 Geolokatsiyamni yuborish'** tugmasini bosing 👇"
            ),
            reply_markup=get_location_request_keyboard()
        )
    else:
        await safe_send(
            chat_id=message.chat.id,
            text=(
                f"📱 Telefon raqamingiz qabul qilindi: `{phone}` ✅\n\n"
                f"Bizning qaysi kiyim yoki tovarimiz sizga ma'qul bo'ldi? Nomini yozing yoki pastdagi **'🛍️ Katalog va Mahsulotlar'** bo'limini ko'ring!"
            ),
            reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS)
        )

# Foydalanuvchi Telegram orqali geolokatsiya (manzil) yuborganida
@dp.message(F.location)
async def handle_location_message(message: types.Message):
    """Xaridor Telegram orqali geolokatsiya (manzil) yuborganida qabul qilish"""
    user_id = message.from_user.id
    user_name = clean_display_name(message.from_user.first_name)
    lat = message.location.latitude
    lon = message.location.longitude
    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    location_text = f"📍 Geolokatsiya ({lat:.5f}, {lon:.5f}) - {maps_link}"

    # Databasega mijoz manzilini yangilash
    DatabaseManager.upsert_customer(telegram_id=user_id, full_name=user_name, address=location_text)

    # Task 3: Agar faol buyurtma oqimi mavjud bo'lsa
    if OrderFlowService.has_active_flow(message.chat.id):
        customer = DatabaseManager.get_customer(user_id)
        step_res = OrderFlowService.process_step(
            chat_id=message.chat.id,
            text=location_text,
            user_name=user_name,
            crm_customer=customer,
            ai_answer_fn=lambda q: ai_brain.ask(message.chat.id, q, customer_name=user_name)
        )
        if step_res.get("reply"):
            await safe_send(message.chat.id, step_res["reply"])
        if step_res.get("is_completed") and step_res.get("admin_alert"):
            admin_alert = step_res["admin_alert"]
            db_ord_id = step_res.get("db_order_id") or 0
            kb = get_order_approval_keyboard(db_ord_id)
            target_admins = list(ADMIN_TELEGRAM_IDS)
            if ADMIN_CHAT_ID and ADMIN_CHAT_ID.lstrip("-").isdigit() and int(ADMIN_CHAT_ID) not in target_admins:
                target_admins.append(int(ADMIN_CHAT_ID))
            for aid in target_admins:
                try:
                    await safe_send(aid, admin_alert, reply_markup=kb)
                except Exception as e:
                    log_bot_error(aid, f"Failed to send admin order alert: {e}", exc=e)
        return

    pending_prod = get_pending_order(user_id)
    customer = DatabaseManager.get_customer(user_id)
    cust_phone = customer.get("phone") if customer else None

    # Agar savatchadan ko'p tovarli buyurtma kutilayotgan bo'lsa
    cart_summary = CartManager.get_cart_summary(user_id)
    if cart_summary["items"] and user_id in CHECKOUT_WAITING_USERS:
        phone_to_use = cust_phone or CHECKOUT_WAITING_USERS[user_id].get("phone")
        if phone_to_use:
            CHECKOUT_WAITING_USERS.pop(user_id, None)
            order_items = [{"product_id": i["product_id"], "quantity": i["quantity"]} for i in cart_summary["items"]]
            order_res = DatabaseManager.create_order(
                customer_telegram_id=user_id,
                customer_name=user_name,
                customer_phone=phone_to_use,
                delivery_address=location_text,
                items=order_items,
                payment_method="cash_on_delivery",
                notes=f"Savatchadan (Geolokatsiya: {maps_link}, Promo: {cart_summary['promo_code'] or 'yoq'})"
            )
            if order_res.get("success"):
                new_id = order_res["order_id"]
                CartManager.clear_cart(user_id)
                if cart_summary["promo_code"]:
                    PromoManager.register_usage(cart_summary["promo_code"])
                await safe_send(
                    message.chat.id,
                    f"🎉 **BUYURTMANGIZ QABUL QILINDI!**\n\n"
                    f"🧾 Buyurtma raqami: **#{new_id}**\n"
                    f"🛍️ Jami tovarlar: {cart_summary['total_items']} dona\n"
                    f"💰 To'lov summasi: **{cart_summary['final_total']:,.0f} so'm**\n"
                    f"📍 Manzil: [Xaritada ko'rish]({maps_link})\n"
                    f"📞 Telefon: `{phone_to_use}`\n\n"
                    f"Kuryerimiz tez orada manzilga yetkazib beradi! Rahmat 😊",
                    reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS, cart_count=0)
                )
                admin_alert = (
                    f"🚨 **YANGI KO'P TOVARLI BUYURTMA (GEOLOKATSIYA BILAN)!**\n\n"
                    f"🆔 Buyurtma: #{new_id}\n"
                    f"👤 Xaridor: {user_name} (ID: `{user_id}`)\n"
                    f"📞 Telefon: {phone_to_use}\n"
                    f"💰 Summa: {cart_summary['final_total']:,.0f} so'm\n"
                    f"📍 Xarita: {maps_link}\n"
                    f"📦 Tovarlar ({len(cart_summary['items'])} xil):\n" +
                    "\n".join([f"  • {i['name']} ({i['quantity']}x) - {i['price']:,.0f} so'm" for i in cart_summary['items']])
                )
                for aid in ADMIN_TELEGRAM_IDS:
                    try:
                        await safe_send(aid, admin_alert, reply_markup=get_order_action_keyboard(new_id))
                    except Exception:
                        pass
                return

    # Agar ham tovar, ham telefon raqami mavjud bo'lsa -> Buyurtmani darhol yakunlash
    if pending_prod and cust_phone:
        stock_check = DatabaseManager.check_stock_strict(pending_prod["id"], 1)
        if stock_check["available"]:
            res = DatabaseManager.create_order(
                customer_telegram_id=user_id,
                customer_name=user_name,
                customer_phone=cust_phone,
                delivery_address=location_text,
                items=[{"product_id": pending_prod["id"], "quantity": 1}],
                payment_method="cash_on_delivery",
                notes=f"Geolokatsiya orqali: {maps_link}"
            )
            if res.get("success"):
                clear_pending_order(user_id)
                await safe_send(
                    message.chat.id,
                    f"🎉 **Buyurtmangiz muvaffaqiyatli qabul qilindi!**\n\n"
                    f"🧾 Buyurtma raqami: **#{res['order_id']}**\n"
                    f"🛍️ Mahsulot: **{pending_prod['name']}**\n"
                    f"💰 Narxi: **{pending_prod['sale_price']:,.0f} so'm**\n"
                    f"📍 Manzil: [Xaritada ko'rish]({maps_link})\n"
                    f"📞 Telefon: `{cust_phone}`\n\n"
                    f"Kuryerimiz tez orada manzilga yetkazib beradi! Rahmat 😊",
                    reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS)
                )
                admin_alert = (
                    f"🚨 **YANGI BUYURTMA (GEOLOKATSIYA BILAN)!**\n\n"
                    f"🆔 Buyurtma: #{res['order_id']}\n"
                    f"👤 Xaridor: {user_name} (ID: `{user_id}`)\n"
                    f"📞 Telefon: {cust_phone}\n"
                    f"🛍️ Mahsulot: {pending_prod['name']}\n"
                    f"💰 Summa: {pending_prod['sale_price']:,.0f} so'm\n"
                    f"📍 Xarita: {maps_link}"
                )
                for aid in ADMIN_TELEGRAM_IDS:
                    try:
                        await safe_send(aid, admin_alert, reply_markup=get_order_action_keyboard(res['order_id']))
                    except Exception:
                        pass
                if CHANNEL_ID:
                    try:
                        await safe_send(CHANNEL_ID, admin_alert)
                    except Exception:
                        pass
                return
            else:
                await safe_send(message.chat.id, "Kechirasiz, tanlangan tovar ayni paytda omborda qolmagan.")
                return

    # Agar tovar bor, lekin telefon raqami yo'q bo'lsa
    if pending_prod and not cust_phone:
        await safe_send(
            message.chat.id,
            f"📍 Geolokatsiyangiz qabul qilindi!\n\n"
            f"Endi buyurtmani tasdiqlash uchun pastdagi **'📱 Telefon raqamimni yuborish'** tugmasini bosing yoki telefon raqamingizni yozing 👇",
            reply_markup=get_phone_request_keyboard()
        )
        return

    await safe_send(
        message.chat.id,
        f"📍 Geolokatsiyangiz qabul qilindi va eslab qolindi!\n\n"
        f"Bizning qaysi tovarimizni yetkazib beraylik? Nomini yozing yoki katalogdan tanlang 👇",
        reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS)
    )

# Bekor qilish tugmasi
@dp.message(F.text == "❌ Bekor qilish")
async def handle_cancel_pending_order(message: types.Message):
    clear_pending_order(message.from_user.id)
    await safe_send(
        chat_id=message.chat.id,
        text="Buyurtma bekor qilindi. Boshqa qanday tovar qidiryapsiz? Sizga yordam berishdan xursandman 😊",
        reply_markup=get_main_menu(is_admin=message.from_user.id in ADMIN_TELEGRAM_IDS)
    )


# Mijozning o'z buyurtmalarini ko'rish (Real-time Tracker)
@dp.message(F.text.in_(["📦 Mening buyurtmalarim", "📦 Buyurtmalarim"]))
async def handle_customer_orders_list(message: types.Message):
    user_id = message.from_user.id
    customer = DatabaseManager.get_customer(user_id)
    user_name = customer.get("full_name", message.from_user.first_name) if customer else message.from_user.first_name
    orders = OrderTracker.get_customer_orders(user_id, limit=5)
    text = OrderTracker.format_orders_view(user_name, orders)
    cart_count = CartManager.get_cart_item_count(user_id)
    await safe_send(
        chat_id=message.chat.id,
        text=text,
        reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS, cart_count=cart_count)
    )

# Aksiya va Promokodlar menyusi
@dp.message(F.text.in_(["🏷️ Aksiya va Promokodlar", "🏷️ Aksiyalar", "🏷️ Promokodlar"]))
async def handle_promos_menu(message: types.Message):
    user_id = message.from_user.id
    text = PromoManager.get_active_promos_display()
    cart_count = CartManager.get_cart_item_count(user_id)
    await safe_send(
        chat_id=message.chat.id,
        text=text,
        reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS, cart_count=cart_count)
    )

# Sotuvchi bilan bog'lanish
@dp.message(F.text == "📞 Sotuvchi bilan bog'lanish")
async def handle_contact_seller_info(message: types.Message):
    address_val = StoreSettingsManager.get_setting("address")
    address_text = address_val if address_val else "Buni egasidan so'rab aytaman"
    await safe_send(
        chat_id=message.chat.id,
        text=(
            f"📞 **'{STORE_NAME}' Bilan Aloqa:**\n\n"
            f"📍 **Manzil:** {address_text}\n"
            f"📱 **Telefon:** `{STORE_PHONE}`\n"
            f"🕒 **Ish vaqti:** {WORKING_HOURS}\n"
            f"📢 **Rasmiy Telegram kanal:** {CHANNEL_USERNAME} ({CHANNEL_URL})\n\n"
            f"Har qanday savolingiz bo'lsa, bemalol matn yoki ovozli xabar yuborishingiz mumkin 😊"
        )
    )



@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    user_id = message.from_user.id
    is_admin = is_admin_user(message.from_user, chat_id=message.chat.id)
    status_label = "Do'kon Egasi (Admin)" if is_admin else "Mijoz"
    await safe_send(
        chat_id=message.chat.id,
        text=(
            f"🆔 Sening Telegram ID: `{user_id}`\n"
            f"👤 Maqomingiz: **{status_label}**"
        )
    )

@dp.message(Command("admin"))
async def cmd_admin_setup(message: types.Message):
    user = message.from_user
    chat_id = message.chat.id
    user_id = user.id if user else chat_id

    if not is_admin_user(user, chat_id=chat_id):
        await safe_send(
            chat_id=chat_id,
            text=f"Kechirasiz, siz admin emassiz. Sizning Telegram ID: `{user_id}`. Ruxsat olish uchun tizim administratori bilan bog'laning."
        )
        return

    await safe_send(
        chat_id=chat_id,
        text=(
            f"👑 **Siz muvaffaqiyatli Do'kon Egasi (Admin) sifatida tizimga ulandingiz!**\n\n"
            f"🆔 Sening Telegram ID: `{user_id}`\n\n"
            f"Endi siz kassa hisobotlari (/hisobot), ombor nazorati (/ombor, /restock) va tovar boshqaruvi huquqiga egasiz."
        ),
        reply_markup=get_main_menu(is_admin=True)
    )

# 1. Kassa Hisoboti (Admin)
@dp.message(F.text == "📊 Do'kon Kassa Hisoboti")
@dp.message(Command("hisobot"))
async def handle_reports_menu(message: types.Message):
    if not is_admin_user(message.from_user, chat_id=message.chat.id):
        await message.answer("Kechirasiz, bu ma'lumot faqat do'kon egasi uchun.")
        return

    await message.answer(
        "📊 **Qaysi davr bo'yicha kassa hisobotini ko'rmoqchisiz?**\nTanlang 👇",
        reply_markup=get_report_periods_keyboard()
    )

@dp.callback_query(F.data.startswith("rep_"))
async def handle_report_callback(callback: types.CallbackQuery):
    if not is_admin_user(callback.from_user, chat_id=callback.message.chat.id if callback.message else None):
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    period = callback.data.replace("rep_", "")
    report = AnalyticsAdvisor.get_sales_report(period=period)
    text = AnalyticsAdvisor.format_report_message(report)

    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_report_periods_keyboard())
    except Exception:
        await callback.message.edit_text(text.replace("**", "").replace("*", ""), reply_markup=get_report_periods_keyboard())
    await callback.answer()

# 2. Ombor va Zakazlar tahlili (Admin)
@dp.message(F.text == "⚠️ Ombor va Zakazlar")
@dp.message(Command("ombor"))
async def handle_inventory_alerts(message: types.Message):
    if not is_admin_user(message.from_user, chat_id=message.chat.id):
        await message.answer("Kechirasiz, bu ma'lumot faqat do'kon egasi uchun.")
        return

    alerts = InventoryManager.get_stock_alerts()
    text = InventoryManager.format_inventory_message(alerts)
    await safe_send(message.chat.id, text)

# 2b. Restock buyrug'i (Admin only - Task 2)
@dp.message(Command("restock"))
async def handle_restock_command(message: types.Message):
    user = message.from_user
    chat_id = message.chat.id
    user_id = user.id if user else chat_id

    # 1. Adminlik tekshiruvi (Rule 5: check ADMIN_CHAT_ID)
    if not is_admin_user(user, chat_id=chat_id):
        await safe_send(chat_id, "Kechirasiz, ushbu buyruq faqat do'kon ma'muri (admin) uchun ruxsat etilgan!")
        return

    # 2. Argumentlar: /restock <product_id> <qty>
    text = (message.text or "").strip()
    parts = text.split()
    if len(parts) < 3:
        await safe_send(chat_id, "ℹ️ Foydalanish: `/restock <product_id> <qty>`\nMasalan: `/restock 10 5`")
        return

    try:
        product_id = int(parts[1])
        quantity = int(parts[2])
        if quantity <= 0:
            await safe_send(chat_id, "❌ Miqdor 0 dan katta butun son bo'lishi kerak.")
            return
    except ValueError:
        await safe_send(chat_id, "❌ Noto'g'ri format. Mahsulot ID va miqdorini raqamda kiriting.\nMasalan: `/restock 10 5`")
        return

    # 3. Ombor qoldig'ini yangilash (SQLite va products.json - atomic)
    res = DatabaseManager.restock_product(product_id, quantity)
    if not res.get("success"):
        await safe_send(chat_id, f"❌ Xatolik: {res.get('message', 'Mahsulot topilmadi')}")
        return

    prod_name = res.get("name", f"#{product_id}")
    new_stock = res.get("new_stock", quantity)

    # 4. Waitlist dagi mijozlarga bir martalik xabar va ularni tozalash (Task 2)
    waiting_users = WaitlistService.clear_product_waitlist(product_id)
    notified_count = 0
    for item in waiting_users:
        w_chat_id = item.get("chat_id")
        if w_chat_id:
            notify_text = (
                f"🎉 **XUSHXABAR! Tovaringiz keldi!**\n\n"
                f"Siz kutayotgan **{prod_name}** mahsulotimiz omborimizga qayta keldi! (Hozirda {new_stock} dona mavjud)\n\n"
                f"Hoziroq xarid qilish uchun do'konimizga yozishingiz mumkin 😊"
            )
            try:
                await safe_send(w_chat_id, notify_text)
                notified_count += 1
            except Exception as e:
                log_bot_error(w_chat_id, f"Waitlist mijoziga xabar yetkazishda xatolik: {e}", exc=e)

    await safe_send(
        chat_id,
        f"✅ **Mahsulot muvaffaqiyatli to'ldirildi (Restock)!**\n\n"
        f"📦 Mahsulot: **{prod_name}** (ID: #{product_id})\n"
        f"➕ Qo'shildi: {quantity} dona\n"
        f"📊 Yangi qoldiq: {new_stock} dona\n"
        f"📢 Xabardor qilingan mijozlar: {notified_count} ta"
    )

# 3. Oxirgi Buyurtmalar (Admin)
@dp.message(F.text == "📋 Oxirgi Buyurtmalar")
@dp.message(Command("buyurtmalar"))
async def handle_recent_orders(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return

    orders = DatabaseManager.get_recent_orders(limit=5)
    if not orders:
        await message.answer("Hozircha hech qanday yangi buyurtma yo'q.")
        return

    for o in orders:
        status_icon = "🆕 Yangi" if o["status"] == "yangi" else ("✅ Yetkazildi" if o["status"] == "yakunlandi" else "❌ Bekor")
        text = (
            f"📦 **Buyurtma #{o['id']}** ({status_icon})\n"
            f"👤 Mijoz: **{o['customer_name']}** ({o['customer_phone']})\n"
            f"📍 Manzil: {o['delivery_address']}\n"
            f"💰 Summa: **{o['total_amount']:,.0f} so'm**\n"
            f"💳 To'lov: {o['payment_method']} ({o['payment_status']})\n"
            f"🕒 Vaqt: {o['created_at']}"
        )
        await safe_send(message.chat.id, text, reply_markup=get_order_action_keyboard(o["id"]))

# Buyurtma holatini o'zgartirish (Admin callback)
@dp.callback_query(F.data.startswith("ord_done_"))
async def handle_order_done(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_TELEGRAM_IDS:
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    order_id = int(callback.data.replace("ord_done_", ""))
    order = DatabaseManager.get_order_by_id(order_id)
    success = DatabaseManager.update_order_status(order_id, "yakunlandi")
    if success:
        await callback.message.edit_text(f"✅ **Buyurtma #{order_id} muvaffaqiyatli yakunlandi va kassa tushumiga qo'shildi!**")
        await callback.answer("Buyurtma yetkazildi deb belgilandi!", show_alert=True)
        if order and order.get("customer_telegram_id"):
            try:
                await safe_send(
                    order["customer_telegram_id"],
                    f"🎉 **Hurmatli xaridor!**\n\n"
                    f"Sizning **#{order_id}**-sonli buyurtmangiz muvaffaqiyatli yetkazildi! Xaridingiz barakali bo'lsin! 😊\n\n"
                    f"Bizni tanlaganingiz uchun tashakkur!"
                )
            except Exception:
                pass

@dp.callback_query(F.data.startswith("ord_cancel_"))
async def handle_order_cancel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_TELEGRAM_IDS:
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    order_id = int(callback.data.replace("ord_cancel_", ""))
    order = DatabaseManager.get_order_by_id(order_id)
    success = DatabaseManager.update_order_status(order_id, "bekor")
    if success:
        await callback.message.edit_text(f"❌ **Buyurtma #{order_id} bekor qilindi va tovar omborga qaytarildi.**")
        await callback.answer("Buyurtma bekor qilindi!", show_alert=True)
        if order and order.get("customer_telegram_id"):
            try:
                await safe_send(
                    order["customer_telegram_id"],
                    f"ℹ️ **Hurmatli xaridor!**\n\n"
                    f"Sizning **#{order_id}**-sonli buyurtmangiz bekor qilindi. Savollaringiz bo'lsa, xodimimiz bilan bog'lanishingiz mumkin."
                )
            except Exception:
                pass

# 4. Reklama / E'lon yuborish (Admin)
@dp.message(F.text == "📢 Mijozlarga Xabar (Reklama)")
async def handle_broadcast_prompt(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return
    await message.answer(
        "📢 **Barcha mijozlarga e'lon yuborish:**\n\n"
        "Xabarni quyidagi buyruq bilan yuboring:\n"
        "`/reklama Sizning xabaringiz matni...`\n\n"
        "📌 Masalan:\n"
        "`/reklama Assalomu alaykum! Do'konimizga yangi Turkiya kurtkalari keldi. Bugun barcha tovarlarga 10% chegirma!`"
    )

@dp.message(Command("reklama"))
async def handle_broadcast_send(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Iltimos, xabar matnini ham yozing: `/reklama <matn>`")
        return

    broadcast_text = parts[1]
    customer_ids = DatabaseManager.get_all_customers_ids()
    sent_count = 0

    await message.answer(f"⏳ Jami {len(customer_ids)} ta mijozga xabar yuborilmoqda...")
    for cid in customer_ids:
        try:
            await bot.send_message(chat_id=cid, text=broadcast_text)
            sent_count += 1
            await asyncio.sleep(0.05) # Rate limit saqlash
        except Exception:
            pass

    await message.answer(f"✅ E'lon {sent_count} ta mijozga muvaffaqiyatli yetkazildi!")

# 4.01 Savdo Kanaliga Post Joylash (Admin)
@dp.message(Command("kanalga_post"))
@dp.message(Command("post"))
async def handle_post_to_channel(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "📢 **Savdo Kanaliga 1-Bosishda Xarid Postini Joylash:**\n\n"
            "Foydalanish: `/kanalga_post <mahsulot_id> [@kanal_username]`\n\n"
            "📌 Masalan:\n"
            "`/kanalga_post 16` — Post preview ko'rish va forward qilish uchun;\n"
            "`/kanalga_post 16 @markaz_savdo` — To'g'ridan-to'g'ri kanalga joylash uchun (bot kanalda admin bo'lishi kerak)."
        )
        return

    try:
        prod_id = int(parts[1])
    except ValueError:
        await message.answer("Iltimos, to'g'ri mahsulot ID raqamini kiriting! Masalan: `/kanalga_post 16`")
        return

    prod = DatabaseManager.get_product_by_id(prod_id)
    if not prod:
        await message.answer(f"#{prod_id} raqamli mahsulot omborda topilmadi!")
        return

    bot_info = await bot.get_me()
    bot_username = bot_info.username or "Markazsavdo00_bot"
    post_text = OrderMatcher.format_channel_post(prod, bot_username)
    buy_kb = get_channel_buy_button(prod_id, bot_username)

    channel_target = parts[2] if len(parts) > 2 else CHANNEL_USERNAME
    if channel_target:
        try:
            if prod.get("photo_id"):
                await bot.send_photo(chat_id=channel_target, photo=prod["photo_id"], caption=post_text, parse_mode="Markdown", reply_markup=buy_kb)
            else:
                await bot.send_message(chat_id=channel_target, text=post_text, parse_mode="Markdown", reply_markup=buy_kb)
            await message.answer(f"✅ Post muvaffaqiyatli ravishda **{channel_target}** kanaliga joylandi!")
            if prod.get("photo_id"):
                await bot.send_photo(chat_id=message.chat.id, photo=prod["photo_id"], caption=post_text, parse_mode="Markdown", reply_markup=buy_kb)
            else:
                await bot.send_message(chat_id=message.chat.id, text=post_text, parse_mode="Markdown", reply_markup=buy_kb)
            return
        except Exception as e:
            await message.answer(
                f"⚠️ **{channel_target}** kanaliga avtomatik joylashda xatolik yuz berdi: {e}\n\n"
                f"💡 **Sababi:** Bot ushbu kanalga Administrator qilib qo'shilmagan yoki post joylash huquqi berilmagan.\n"
                f"Iltimos, botni (@{bot_username}) kanalingizga Admin qiling va qayta `/kanalga_post {prod_id}` yuboring.\n\n"
                f"Quyida tayyor post berildi, uni hozircha kanalingizga Forward qilishingiz mumkin 👇"
            )

    if prod.get("photo_id"):
        await bot.send_photo(chat_id=message.chat.id, photo=prod["photo_id"], caption=post_text, parse_mode="Markdown", reply_markup=buy_kb)
    else:
        await bot.send_message(chat_id=message.chat.id, text=post_text, parse_mode="Markdown", reply_markup=buy_kb)
    await message.answer("👆 Yuqoridagi tayyor postni o'z savdo kanalingizga forward qiling yoki nusxasini joylang!")


# 4.1 Excel Hisoboti (Admin)
@dp.message(F.text == "📑 Excel Hisobotini Yuklab Olish")
@dp.message(Command("excel"))
async def handle_excel_export(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return
    await message.answer("⏳ Barcha buyurtmalar va ombor qoldiqlari bo'yicha to'liq Excel (.xlsx) hisoboti tayyorlanmoqda...")
    file_path = ExcelExporter.generate_full_report()
    await message.answer_document(
        document=types.FSInputFile(file_path),
        caption=f"📊 **{STORE_NAME}** - To'liq Moliyaviy va Ombor Excel Hisoboti"
    )

# 4.2 SaaS B2B Biznes Paneli (Admin)
@dp.message(F.text == "🏢 SaaS Biznes Paneli")
@dp.message(Command("saas"))
async def handle_saas_panel(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return
    data = TenantManager.calculate_saas_mrr()
    text = (
        f"🏢 **B2B SaaS Biznes Boshqaruv Markazi**\n"
        f"───────────────────────\n"
        f"👥 **Jami ulangan do'konlar:** {data['total_clients']} ta\n"
        f"🟢 **Faol do'konlar:** {data['active_clients']} ta\n"
        f"💰 **Oylik daromad (MRR):** {data['monthly_recurring_revenue']:,.0f} so'm\n"
        f"📈 **Yillik aylanma (ARR):** {data['annual_run_rate']:,.0f} so'm\n\n"
        f"➕ **Yangi do'kon qo'shish uchun buyruq:**\n"
        f"`/yangi_dokon Nomi, Egasi, Telefon, Shahar, Dostavka, Token`\n"
        f"───────────────────────\n"
        f"💡 *10 ta do'kon ulasangiz = Oyiga kamida 5,000,000 so'm passiv daromad!*"
    )
    await safe_send(message.chat.id, text)

@dp.message(Command("yangi_dokon"))
@dp.message(Command("yangi_do'kon"))
async def handle_add_store(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return
    parts = message.text.replace("/yangi_dokon", "").replace("/yangi_do'kon", "").split(",")
    if len(parts) < 4:
        await message.answer("Format: `/yangi_dokon Do'kon Nomi, Egasining Ismi, Telefon, Shahar, Dostavka, BotToken`")
        return
    res = TenantManager.register_new_store(
        store_name=parts[0].strip(),
        owner_name=parts[1].strip(),
        owner_phone=parts[2].strip() if len(parts) > 2 else "",
        location=parts[3].strip() if len(parts) > 3 else "Ingichka",
        delivery_zone=parts[4].strip() if len(parts) > 4 else "Bepul",
        bot_token=parts[5].strip() if len(parts) > 5 else "token"
    )
    await message.answer(f"✅ {res.get('message', 'Muvaffaqiyatli!')}")

# 4.3 Do'kon Egasiga Foydasi / Tijoriy Taklif (Sales Pitch)
@dp.message(F.text == "💡 Nega Bu Bot? (Tijoriy Taklif)")
@dp.message(Command("pitch"))
@dp.message(Command("taklif"))
async def handle_sales_pitch_msg(message: types.Message):
    pitch_text = SalesPitchAdvisor.get_full_pitch()
    roi_text = SalesPitchAdvisor.format_roi_message()
    hacks_text = SalesPitchAdvisor.get_growth_hacks()
    await safe_send(message.chat.id, pitch_text)
    await safe_send(message.chat.id, roi_text)
    await safe_send(message.chat.id, hacks_text)

# 5. Yangi tovar qo'shish (Admin)
@dp.message(F.text == "➕ Yangi tovar qo'shish")
async def handle_add_product_prompt(message: types.Message):
    if message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return

    await message.answer(
        "📸🎙️ **Yangi tovar qo'shish (AI Ovoz yoki Matn orqali):**\n\n"
        "Shunchaki tovar rasmini tashlang va izohida (yoki alohida xabarda/ovozda) quyidagicha yozing:\n\n"
        "📌 *Masalan:*\n"
        "`Turkiya issiq xudi, qora rang, L razmer, tan narxi 140 ming, sotuv narxi 220 ming, 10 dona keldi`\n\n"
        "Bizning AI o'zi buni tushunib, avtomatik omborga kiritadi!"
    )

# 6. Foydalanuvchi tugmalari
def format_product_card(prod: Dict[str, Any], category: str, idx: int, total: int) -> str:
    stock = prod.get("stock_quantity", 0)
    stock_badge = "🟢 Omborda mavjud" if stock > 2 else (f"🔥 Shoshiling, oxirgi {stock} ta qoldi!" if stock > 0 else "🔴 Hozircha tugagan")
    return (
        f"🛍 **{prod['name']}**\n\n"
        f"📁 Bo'lim: **{category}**\n"
        f"📏 Mavjud o'lchamlar: `{prod['size']}`\n"
        f"🎨 Rangi: `{prod['color']}`\n"
        f"💰 Narxi: **{prod['sale_price']:,.0f} so'm**\n"
        f"📊 Holati: {stock_badge}\n"
        f"📌 Model: {idx + 1} / {total}\n\n"
        f"Savatga qo'shish yoki hoziroq sotib olish uchun quyidagi tugmalarni bosing 👇"
    )

# 6. Foydalanuvchi tugmalari: Katalog va Interaktiv Karusel
@dp.message(F.text == "🛍️ Katalog va Mahsulotlar")
async def handle_catalog(message: types.Message):
    await message.answer(
        "🛍 **Do'konimiz bo'limlari:**\n\n"
        "O'zingizga qiziq bo'limni tanlang va tovarlarni qulay tomosha qiling:",
        reply_markup=get_category_keyboard()
    )

@dp.callback_query(F.data.startswith("cat_"))
async def handle_category_select(callback: types.CallbackQuery):
    cat_name = callback.data.replace("cat_", "")
    prods = DatabaseManager.get_products(category=cat_name, in_stock_only=True)

    if not prods:
        await callback.message.answer(f"Hozirda '{cat_name}' bo'limidagi barcha tovarlar sotib bo'lindi. Yangi partiya yo'lda!")
        await callback.answer()
        return

    prod = prods[0]
    total = len(prods)
    text = format_product_card(prod, cat_name, 0, total)
    kb = get_product_card_keyboard(prod["id"], cat_name, 0, total)

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("p_nav_"))
async def handle_product_nav(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    cat_name = parts[2]
    idx = int(parts[3])
    prods = DatabaseManager.get_products(category=cat_name, in_stock_only=True)

    if not prods or idx < 0 or idx >= len(prods):
        await callback.answer("Boshqa tovar yo'q", show_alert=False)
        return

    prod = prods[idx]
    total = len(prods)
    text = format_product_card(prod, cat_name, idx, total)
    kb = get_product_card_keyboard(prod["id"], cat_name, idx, total)

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "p_cats")
async def handle_back_to_categories(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            "🛍 **Do'konimiz bo'limlari:**\n\nO'zingizga qiziq bo'limni tanlang:",
            reply_markup=get_category_keyboard()
        )
    except Exception:
        await callback.message.answer(
            "🛍 **Do'konimiz bo'limlari:**\n\nO'zingizga qiziq bo'limni tanlang:",
            reply_markup=get_category_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("cart_add_"))
async def handle_cart_add(callback: types.CallbackQuery):
    p_id = int(callback.data.replace("cart_add_", ""))
    user_id = callback.from_user.id
    res = CartManager.add_item(user_id, p_id, quantity=1)

    if res["success"]:
        count = CartManager.get_cart_item_count(user_id)
        prod = DatabaseManager.get_product_by_id(p_id)
        p_name = prod["name"] if prod else "Mahsulot"
        rec = RecommendationEngine.get_cross_sell_for_product(p_name, exclude_ids=[p_id])
        rec_hint = f"\n💡 Tavsiya: '{rec['name']}' ham juda yarashadi!" if rec else ""
        await callback.answer(f"✅ Savatga qo'shildi! (Jami: {count} ta){rec_hint}", show_alert=False)
    else:
        await callback.answer(f"⚠️ {res['message']}", show_alert=True)

@dp.callback_query(F.data.startswith("fast_buy_"))
async def handle_fast_buy(callback: types.CallbackQuery):
    p_id = int(callback.data.replace("fast_buy_", ""))
    user_id = callback.from_user.id
    prod = DatabaseManager.get_product_by_id(p_id)
    if not prod:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    set_pending_order(user_id, prod)
    customer = DatabaseManager.get_customer(user_id)
    flow_res = OrderFlowService.start_order_flow(
        chat_id=user_id,
        initial_product=prod,
        crm_customer=customer
    )
    await callback.message.answer(flow_res["reply"])
    await callback.answer()

# Savatcha interfeysi
@dp.callback_query(F.data == "open_cart")
@dp.message(F.text.startswith("🛒 Savatcham"))
async def handle_open_cart(event: types.CallbackQuery | types.Message):
    user_id = event.from_user.id
    summary = CartManager.get_cart_summary(user_id)
    text = CartManager.format_cart_message(user_id)
    kb = get_cart_keyboard(summary["items"], has_promo=bool(summary["promo_code"]))

    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=kb)
        except Exception:
            await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await safe_send(event.chat.id, text, reply_markup=kb)

@dp.callback_query(F.data.startswith("cart_inc_"))
async def handle_cart_inc(callback: types.CallbackQuery):
    p_id = int(callback.data.replace("cart_inc_", ""))
    user_id = callback.from_user.id
    CartManager.update_quantity(user_id, p_id, delta=1)
    summary = CartManager.get_cart_summary(user_id)
    text = CartManager.format_cart_message(user_id)
    kb = get_cart_keyboard(summary["items"], has_promo=bool(summary["promo_code"]))
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("cart_dec_"))
async def handle_cart_dec(callback: types.CallbackQuery):
    p_id = int(callback.data.replace("cart_dec_", ""))
    user_id = callback.from_user.id
    CartManager.update_quantity(user_id, p_id, delta=-1)
    summary = CartManager.get_cart_summary(user_id)
    text = CartManager.format_cart_message(user_id)
    kb = get_cart_keyboard(summary["items"], has_promo=bool(summary["promo_code"]))
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("cart_del_"))
async def handle_cart_del(callback: types.CallbackQuery):
    p_id = int(callback.data.replace("cart_del_", ""))
    user_id = callback.from_user.id
    CartManager.remove_item(user_id, p_id)
    summary = CartManager.get_cart_summary(user_id)
    text = CartManager.format_cart_message(user_id)
    kb = get_cart_keyboard(summary["items"], has_promo=bool(summary["promo_code"]))
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer("Mahsulot savatdan olib tashlandi")

@dp.callback_query(F.data == "cart_clear")
async def handle_cart_clear(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    CartManager.clear_cart(user_id)
    text = CartManager.format_cart_message(user_id)
    kb = get_cart_keyboard([], has_promo=False)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer("Savat tozalandi")

@dp.callback_query(F.data == "cart_promo_add")
async def handle_cart_promo_add(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    PROMO_WAITING_USERS.add(user_id)
    await callback.message.answer(
        "🏷 **Promokodingizni kiriting:**\n\n"
        "Masalan: `MARKAZ10`, `SUPER2026` yoki `VIPMIJOZ` deb yozib yuboring:"
    )
    await callback.answer()

@dp.callback_query(F.data == "cart_promo_del")
async def handle_cart_promo_del(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    CartManager.remove_promo(user_id)
    summary = CartManager.get_cart_summary(user_id)
    text = CartManager.format_cart_message(user_id)
    kb = get_cart_keyboard(summary["items"], has_promo=False)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer("Promokod bekor qilindi")

@dp.callback_query(F.data == "cart_checkout")
async def handle_cart_checkout(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    summary = CartManager.get_cart_summary(user_id)
    if not summary["items"]:
        await callback.answer("Savatchangiz bo'sh!", show_alert=True)
        return

    customer = DatabaseManager.get_customer(user_id)
    cust_phone = customer.get("phone") if customer else None
    cust_address = customer.get("address") if customer else None

    if cust_phone and cust_address:
        order_items = [{"product_id": i["product_id"], "quantity": i["quantity"]} for i in summary["items"]]
        order_res = DatabaseManager.create_order(
            customer_telegram_id=user_id,
            customer_name=customer.get("full_name", callback.from_user.first_name),
            customer_phone=cust_phone,
            delivery_address=cust_address,
            items=order_items,
            payment_method="cash_on_delivery",
            notes=f"Savatchadan (Promo: {summary['promo_code'] or 'yoq'})"
        )
        if order_res.get("success"):
            new_id = order_res["order_id"]
            CartManager.clear_cart(user_id)
            if summary["promo_code"]:
                PromoManager.register_usage(summary["promo_code"])

            delivery_label = "Bepul! (Sovg'a)" if summary["free_delivery"] else "Oddiy tarif"
            confirm_text = (
                f"🎉 **BUYURTMANGIZ QABUL QILINDI!**\n\n"
                f"🧾 Buyurtma raqami: **#{new_id}**\n"
                f"👤 Qabul qiluvchi: **{customer.get('full_name')}**\n"
                f"📱 Telefon: `{cust_phone}`\n"
                f"📍 Manzil: **{cust_address}**\n"
                f"💰 Jami to'lov: **{summary['final_total']:,.0f} so'm**\n"
                f"🚚 Yetkazib berish: {delivery_label}\n\n"
                f"Kuryerimiz tez orada siz bilan bog'lanadi! Xaridingiz barakali bo'lsin! 😊"
            )
            await callback.message.answer(confirm_text, reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS, cart_count=0))

            admin_alert = (
                f"🔔 **YANGI KO'P TOVARLI BUYURTMA #{new_id}!**\n\n"
                f"👤 Mijoz: {customer.get('full_name')} (ID: `{user_id}`)\n"
                f"📱 Tel: {cust_phone}\n"
                f"📍 Manzil: {cust_address}\n"
                f"💰 Summa: **{summary['final_total']:,.0f} so'm**\n"
                f"📦 Tovarlar ({len(summary['items'])} xil):\n" +
                "\n".join([f"  • {i['name']} ({i['quantity']}x) - {i['price']:,.0f} so'm" for i in summary['items']])
            )
            for aid in ADMIN_TELEGRAM_IDS:
                await safe_send(aid, admin_alert, reply_markup=get_order_action_keyboard(new_id))
            if CHANNEL_ID:
                try:
                    await safe_send(CHANNEL_ID, admin_alert)
                except Exception:
                    pass
            await callback.answer()
            return

    # Agar telefon yoki manzil yetishmasa
    CHECKOUT_WAITING_USERS[user_id] = {"stage": "phone"}
    await callback.message.answer(
        "📱 Buyurtmani rasmiylashtirish uchun, iltimos, **telefon raqamingizni** yuboring (yoki pastdagi tugmani bosing):",
        reply_markup=get_phone_request_keyboard()
    )
    await callback.answer()

# Admin Buyurtma Holatini O'zgartirish va Push Xabar
@dp.callback_query(F.data.startswith("ord_prep_"))
async def handle_order_prep(callback: types.CallbackQuery):
    ord_id = int(callback.data.replace("ord_prep_", ""))
    DatabaseManager.update_order_status(ord_id, "tayyorlanmoqda")
    order = DatabaseManager.get_order(ord_id)
    if order and order.get("customer_telegram_id"):
        push = OrderTracker.format_status_notification(ord_id, "tayyorlanmoqda", order.get("customer_name", "Mijoz"))
        await safe_send(order["customer_telegram_id"], push)
    await callback.answer("Buyurtma 'Qadoqlanmoqda' holatiga o'tkazildi!", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=get_order_action_keyboard(ord_id))
    except Exception:
        pass

@dp.callback_query(F.data.startswith("ord_ship_"))
async def handle_order_ship(callback: types.CallbackQuery):
    ord_id = int(callback.data.replace("ord_ship_", ""))
    DatabaseManager.update_order_status(ord_id, "yetkazilmoqda")
    order = DatabaseManager.get_order(ord_id)
    if order and order.get("customer_telegram_id"):
        push = OrderTracker.format_status_notification(ord_id, "yetkazilmoqda", order.get("customer_name", "Mijoz"))
        await safe_send(order["customer_telegram_id"], push)
    await callback.answer("Buyurtma 'Kuryerga berildi (Yo'lda)' holatiga o'tkazildi!", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=get_order_action_keyboard(ord_id))
    except Exception:
        pass

# 5 Yulduzli Baholash (Review) Callback
@dp.callback_query(F.data.startswith("rev_"))
async def handle_customer_review(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    ord_id = int(parts[1])
    rating = int(parts[2])
    user_id = callback.from_user.id
    user_name = clean_display_name(callback.from_user.first_name)
    ReviewManager.add_review(user_id, user_name, rating, order_id=ord_id)
    stars = "⭐️" * rating
    await callback.message.edit_text(
        f"Katta rahmat! Siz do'konimizni **{stars} ({rating}/5)** deb baholadingiz. "
        f"Sizga xizmat ko'rsatishdan mamnunmiz! Har doim do'konimizda kutib qolamiz! 😊"
    )
    for aid in ADMIN_TELEGRAM_IDS:
        await safe_send(aid, f"⭐️ **Yangi mijoz bahosi:** {user_name} #{ord_id} buyurtmani {stars} ({rating}/5) deb baholadi!")
    await callback.answer("Bahoyingiz qabul qilindi!")

@dp.message(F.text.in_(["🚚 Yetkazib berish", "🚚 Ingichka bo'ylab yetkazish"]))
async def handle_delivery_info(message: types.Message):
    user_id = message.from_user.id
    user_name = clean_display_name(message.from_user.first_name)
    val = StoreSettingsManager.get_setting("delivery")
    if not val:
        await message.answer("Buni egasidan so'rab aytaman")
        for aid in ADMIN_TELEGRAM_IDS:
            try:
                await safe_send(
                    aid,
                    f"⚠️ **Yetkazib berish (delivery) sozlamasi bo'sh!**\n\n"
                    f"👤 Mijoz: {user_name} (ID: `{user_id}`)\n"
                    f"Mijoz yetkazib berish shartlari haqida so'radi."
                )
            except Exception:
                pass
        return
    await message.answer(f"🚚 **Yetkazib berish xizmati:**\n\n{val}")

# 7. AI Sozlamalari (Admin)
@dp.message(Command("set_ai"))
@dp.message(Command("ai_key"))
async def cmd_set_ai_key(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_TELEGRAM_IDS:
        ADMIN_TELEGRAM_IDS.append(user_id)
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Kalitni quyidagicha yuboring: `/set_ai SIZNING_API_KALITINGIZ`")
        return

    key = parts[1].strip()
    provider = "openai" if key.startswith("sk-") else "gemini"
    ai_brain.set_api_key(key, provider)
    await message.answer(f"🚀 **AI Agent muvaffaqiyatli yangilandi! Provider: {provider.upper()}**")

@dp.message(Command("ai_status"))
async def cmd_ai_status(message: types.Message):
    is_ready = ai_brain.is_ai_ready()
    status_text = "🟢 **AKTIV** (Haqiqiy Google Gemini Modeli ulangan)" if is_ready else "🟡 **ZAXIRA REJIMI** (Kalit ulanmagan)"
    await message.answer(f"🧠 **AI SOTUVCHI AGENT HOLATI:**\n\n{status_text}\n\nDo'kon: **{STORE_NAME}**\nHudud: **{LOCATION}**")

# 8. Rasmlar bilan ishlash (MULTIMODAL VISION)
@dp.message(F.photo)
async def handle_photo_message(message: types.Message):
    """Xaridor yoki Admin yuborgan rasmni ko'rib tahlil qilish"""
    user_id = message.from_user.id
    user_name = message.from_user.full_name or "Mijoz"
    caption = message.caption or ""

    # Agar Admin yangi tovar rasmini tashlagan bo'lsa
    if user_id in ADMIN_TELEGRAM_IDS and ("keldi" in caption.lower() or "tan narxi" in caption.lower() or "sotuv" in caption.lower()):
        parsed = agent.parse_product_voice_text(caption)
        photo_id = message.photo[-1].file_id
        prod_id = DatabaseManager.add_product(
            name=parsed["name"],
            category=parsed["category"],
            size=parsed["size"],
            color=parsed["color"],
            cost_price=parsed["cost_price"],
            sale_price=parsed["sale_price"],
            stock_quantity=parsed["stock_quantity"],
            description=parsed["description"],
            photo_id=photo_id
        )
        await message.answer(
            f"✅ **Rasm va ma'lumotlar bilan yangi tovar omborga kiritildi!**\n\n"
            f"📦 #{prod_id} - **{parsed['name']}**\n"
            f"📏 Razmer: {parsed['size']} | Rang: {parsed['color']}\n"
            f"💰 Sotuv narxi: {parsed['sale_price']:,.0f} so'm\n"
            f"📊 Soni: {parsed['stock_quantity']} dona"
        )
        return

    # Xaridor rasm yuborgan holat: Gemini Vision orqali ombordan o'xshashini topish
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # Rasmni xotiraga yuklab olish
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        # 1. Agar mijoz kiyim yoki tovar haqida so'ragan bo'lsa ("Shu kiyimdan bormi", "narxi qancha"),
        # to'lov chekini tekshirishga hojat yo'q, to'g'ridan-to'g'ri AI Brain Vision tahliliga yuboramiz.
        is_product_inq = ReceiptChecker.is_likely_product_inquiry(caption)
        
        receipt_res = {"is_receipt": False}
        if not is_product_inq:
            receipt_res = ReceiptChecker.verify_payment_screenshot(image_b64)

        if receipt_res.get("is_receipt"):
            if receipt_res.get("is_valid"):
                await message.answer(
                    "✅ **To'lov chekingiz muvaffaqiyatli qabul qilindi!**\n\n"
                    "Buyurtmangiz tayyorlanmoqda!"
                )
                admin_notify = (
                    f"💳 **MIJOZDAN TO'LOV CHEKI KELDI!**\n\n"
                    f"👤 Xaridor: **{user_name}**\n"
                    f"📝 Tahlil:\n{receipt_res['analysis']}"
                )
                for aid in ADMIN_TELEGRAM_IDS:
                    await safe_send(aid, admin_notify)
                return
            else:
                await message.answer(
                    "⚠️ To'lov chekini to'liq tasdiqlab bo'lmadi. Iltimos, chekning to'liq va ravshan skrinshotini yuboring yoki eshik oldida naqd/karta bilan to'lang."
                )
                return

        # 2. Gemini Vision bilan kiyimni tahlil qilish
        response = ai_brain.ask_with_photo(
            user_id=user_id,
            image_b64=image_b64,
            caption=caption,
            customer_name=user_name
        )
        await safe_send(message.chat.id, response)

    except Exception as e:
        logger.error(f"Rasm bilan ishlashda xatolik: {e}")
        await message.answer("Rasmingizni qabul qildim! Xuddi shunday sifatli modellarimiz hozir do'konimizda mavjud. Qaysi o'lchamda kiyasiz?")

# 8.1 Ovozli xabarlar bilan ishlash (AUDIO SOTUVCHI AGENT)
@dp.message(F.voice)
async def handle_voice_message(message: types.Message):
    """Xaridor ovozli xabar yuborganida uni tinglab, uning aynan shu savoliga samimiy ovozli xabar bilan javob qaytarish"""
    user_id = message.from_user.id
    customer = DatabaseManager.get_customer(user_id)
    preferred_name = customer.get("preferred_name") if customer else None
    user_name = clean_display_name(message.from_user.first_name, preferred_name)

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="record_voice")
    except Exception:
        pass

    try:
        # 1. Telegramdan ovoz faylini (.ogg) xotiraga yuklab olish
        voice_file_io = io.BytesIO()
        await bot.download(message.voice, destination=voice_file_io)
        audio_bytes = voice_file_io.getvalue()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        # 2. Audioni transkripsiya qilish (Speech-to-Text)
        transcript = ai_brain.transcribe_audio(audio_b64, mime_type="audio/ogg")
        t_low = transcript.lower() if transcript else ""

        # 3. Agar ADMIN ovoz orqali yangi tovar qo'shayotgan bo'lsa
        if user_id in ADMIN_TELEGRAM_IDS and any(w in t_low for w in ["keldi", "tan narxi", "sotuv narxi", "sotuv", "tovar qo'sh"]):
            parsed = agent.parse_product_voice_text(transcript)
            prod_id = DatabaseManager.add_product(
                name=parsed["name"],
                category=parsed["category"],
                size=parsed["size"],
                color=parsed["color"],
                cost_price=parsed["cost_price"],
                sale_price=parsed["sale_price"],
                stock_quantity=parsed["stock_quantity"],
                description=parsed["description"]
            )
            admin_reply = (
                f"✅ **Ovozli xabaringiz orqali yangi tovar omborga qo'shildi!**\n\n"
                f"📦 Nomi: **{parsed['name']}**\n"
                f"📏 O'lcham: {parsed['size']} | Rang: {parsed['color']}\n"
                f"💰 Sotuv narxi: **{parsed['sale_price']:,.0f} so'm**\n"
                f"📊 Omborda: {parsed['stock_quantity']} dona\n"
                f"🆔 Mahsulot ID: #{prod_id}"
            )
            voice_file = await VoiceService.text_to_speech(admin_reply, filename_prefix=f"admin_add_{user_id}")
            if voice_file and os.path.exists(voice_file):
                await message.answer_voice(types.FSInputFile(voice_file), caption=admin_reply)
            else:
                await safe_send(message.chat.id, admin_reply)
            return

        # 4. Ovoz orqali buyurtma berilgan bo'lsa (Voice Ordering)
        has_pending = user_id in USER_PENDING_ORDERS
        order_details = OrderMatcher.extract_order_details(transcript, has_pending_order=has_pending) if transcript else None
        if order_details:
            target_prod = OrderMatcher.match_product(
                text=transcript,
                history=ai_brain.conversations.get(user_id, []),
                pending_product=USER_PENDING_ORDERS.get(user_id)
            )
            if target_prod:
                qty = order_details.get("quantity", 1)
                stock_check = DatabaseManager.check_stock_strict(target_prod["id"], qty)
                if stock_check["available"]:
                    order_res = DatabaseManager.create_order(
                        customer_telegram_id=user_id,
                        customer_name=user_name,
                        customer_phone=order_details["phone"],
                        delivery_address=order_details["address"],
                        items=[{"product_id": target_prod["id"], "quantity": qty}],
                        payment_method="cash_on_delivery",
                        notes=f"Ovozli buyurtma ({qty} dona): {transcript}"
                    )
                    if order_res["success"]:
                        new_order_id = order_res["order_id"]
                        clear_pending_order(user_id)

                        confirm_msg = OrderMatcher.format_order_confirmation(
                            order_id=new_order_id,
                            product=target_prod,
                            user_name=user_name,
                            phone=order_details["phone"],
                            address=order_details["address"]
                        )
                        speech_text = f"Rahmat, {user_name}! Buyurtmangiz qabul qilindi. Buyurtmangiz tez orada tayyorlanadi!"
                        voice_file = await VoiceService.text_to_speech(speech_text, filename_prefix=f"ord_v_{user_id}")
                        try:
                            if voice_file and os.path.exists(voice_file):
                                await message.answer_voice(
                                    types.FSInputFile(voice_file),
                                    caption="🎉 **Buyurtmangiz qabul qilindi!**\nBarcha tafsilotlar quyidagi chekda 👇"
                                )
                        finally:
                            if voice_file and os.path.exists(voice_file):
                                try:
                                    os.remove(voice_file)
                                except Exception:
                                    pass
                        await safe_send(message.chat.id, confirm_msg)

                        admin_alert = OrderMatcher.format_admin_alert(
                            order_id=new_order_id,
                            product=target_prod,
                            user_name=user_name,
                            phone=order_details["phone"],
                            address=order_details["address"],
                            full_raw=f"Ovozli transkript ({qty} dona): {transcript}"
                        )
                        for aid in ADMIN_TELEGRAM_IDS:
                            try:
                                await safe_send(aid, admin_alert, reply_markup=get_order_action_keyboard(new_order_id))
                            except Exception:
                                pass
                        if CHANNEL_ID:
                            try:
                                await safe_send(CHANNEL_ID, admin_alert)
                            except Exception:
                                pass
                        return

        # 5. Oddiy ovozli savol bo'lsa
        if transcript:
            ext_name = extract_preferred_name(transcript)
            if ext_name:
                DatabaseManager.update_customer_preferred_name(user_id, ext_name)
                user_name = ext_name

            matched_interest = OrderMatcher.match_product(transcript, history=ai_brain.conversations.get(user_id, []))
            if matched_interest and any(w in t_low for w in ["olaman", "olmoqchiman", "bering", "zakaz", "buyurtma", "yuboring"]):
                set_pending_order(user_id, matched_interest)

            response_text = ai_brain.ask(
                user_id=user_id,
                user_message=transcript,
                customer_name=user_name
            )
        else:
            response_text = ai_brain.ask_with_audio(
                user_id=user_id,
                audio_b64=audio_b64,
                mime_type="audio/ogg",
                customer_name=user_name
            )

        # 6. Javobni tabiiy o'zbek tili ovoziga (TTS) aylantirish
        clean_text_for_tts = VoiceService._clean_for_speech(response_text)
        voice_file = await VoiceService.text_to_speech(clean_text_for_tts, filename_prefix=f"ans_{user_id}")

        try:
            if voice_file and os.path.exists(voice_file):
                await message.answer_voice(
                    types.FSInputFile(voice_file),
                    caption="🎙️ **Madinaxon (Ovozli maslahat)**"
                )
        finally:
            if voice_file and os.path.exists(voice_file):
                try:
                    os.remove(voice_file)
                except Exception:
                    pass
        await safe_send(message.chat.id, response_text)

    except Exception as e:
        logger.error(f"Ovozli xabarni tahlil qilishda xatolik: {e}")
        fallback = (
            f"Assalomu alaykum, {user_name}! Ovozli xabaringizni eshitdim 😊 "
            f"Do'konimizda barcha sifatli tovarlarimiz mavjud. Qaysi o'lchamda kiyasiz?"
        )
        await safe_send(message.chat.id, fallback)

# 9. Telegram Guruhlar va Shaxsiy Chatlar (AI Sotuvchi muloqoti + Buyurtma olish)
@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def handle_group_message(message: types.Message):
    if not message.text:
        return

    # Kanaldan avtomatik uzatilgan postlar va botlarga javob bermaslik (Anti-Spam)
    if getattr(message, "is_automatic_forward", False) or getattr(message, "sender_chat", None):
        return
    if not message.from_user or message.from_user.is_bot:
        return

    text = message.text.lower()
    bot_info = await bot.get_me()
    bot_username = (bot_info.username or "Markazsavdo00_bot").lower()

    # Botga murojaat qilinganmi (mention yoki reply)
    is_mentioned = f"@{bot_username}" in text
    is_reply_to_bot = bool(
        message.reply_to_message and
        message.reply_to_message.from_user and
        message.reply_to_message.from_user.id == bot_info.id
    )

    triggers = [
        "qancha", "narxi", "razmer", "bor", "bormi", "kurtka", "xudi", "ko'ylak", "koylak",
        "sumka", "sochiq", "ingichka", "dostavka", "yetkazish", "krasovka", "krossovka",
        "poyabzal", "tufli", "jinsi", "shim", "kiyim", "katalog", "chegirma", "aktsiya",
        "красовка", "худи", "куртка", "сочик", "туфли", "доставка"
    ]
    has_trigger = any(t in text for t in triggers)


    if has_trigger or is_mentioned or is_reply_to_bot:
        try:
            await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        except Exception:
            pass

        clean_user_text = message.text.replace(f"@{bot_info.username}", "").strip()

        # 1. Do'kon sozlamalari tekshiruvi
        setting_inq = StoreSettingsManager.check_setting_inquiry(clean_user_text or message.text)
        if setting_inq:
            await safe_send(message.chat.id, setting_inq["reply"])
            if setting_inq["empty"]:
                for aid in ADMIN_TELEGRAM_IDS:
                    try:
                        await safe_send(aid, f"⚠️ Guruhda mijoz {setting_inq['setting_name_uz']} haqida so'radi (bo'sh):\n{clean_user_text}")
                    except Exception:
                        pass
            return

        # 2. Qoida 7: Mavjud bo'lmagan o'lcham
        size_inq = OrderMatcher.check_size_inquiry(clean_user_text or message.text)
        if size_inq:
            await safe_send(message.chat.id, size_inq)
            return

        # 3. Qoida 4: Narx bo'yicha filtr
        price_filt = OrderMatcher.parse_price_filter(clean_user_text or message.text)
        if price_filt:
            prods = OrderMatcher.filter_products_by_price(price_filt["min_price"], price_filt["max_price"])
            reply_filt = OrderMatcher.format_price_filter_response(prods, price_filt["min_price"], price_filt["max_price"])
            await safe_send(message.chat.id, reply_filt)
            return

        # 4. Katta AI javobi
        ai_reply = ai_brain.ask(
            user_id=message.from_user.id,
            user_message=clean_user_text or message.text,
            customer_name=message.from_user.first_name or "Mijoz"
        )

        # Guruh a'zosiga 1-bosishda bot bilan shaxsiy chat ochish tugmasi
        pm_button = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🛍️ Lichkada xarid qilish", url=f"https://t.me/{bot_info.username}")
        ]])

        await safe_send(message.chat.id, ai_reply, reply_markup=pm_button)

@dp.message(F.chat.type == ChatType.PRIVATE)
async def handle_private_chat(message: types.Message):
    if not message.text:
        return

    user_id = message.from_user.id
    text = message.text
    text_lower = text.lower()

    # Adminlik huquqini tekshirish (username yoki ID bo'yicha)
    is_admin_user(message.from_user)

    # CRM xotirasi: Mijoz profilini tekshirish va ismni eslab qolish
    customer = DatabaseManager.get_customer(user_id)
    extracted = extract_preferred_name(text)
    if extracted:
        DatabaseManager.update_customer_preferred_name(user_id, extracted)
        customer = DatabaseManager.get_customer(user_id)

    preferred_name = customer.get("preferred_name") if customer else None
    user_name = clean_display_name(message.from_user.first_name, preferred_name)

    # 00. Waitlist rozilik javobini tekshirish ("Kelganda xabar beraymi?" -> "ha") (Task 2)
    waitlist_resp = StockAdvisor.handle_waitlist_confirmation(message.chat.id, text)
    if waitlist_resp:
        await safe_send(message.chat.id, waitlist_resp)
        return

    # === TASK 3: Faol buyurtma oqimi holat mashinasi (State Machine) ===
    if OrderFlowService.has_active_flow(message.chat.id):
        step_res = OrderFlowService.process_step(
            chat_id=message.chat.id,
            text=text,
            user_name=user_name,
            crm_customer=customer,
            ai_answer_fn=lambda q: ai_brain.ask(message.chat.id, q, customer_name=user_name)
        )
        if step_res.get("reply"):
            await safe_send(message.chat.id, step_res["reply"])

        if step_res.get("is_completed") and step_res.get("admin_alert"):
            admin_alert = step_res["admin_alert"]
            db_ord_id = step_res.get("db_order_id") or 0
            kb = get_order_approval_keyboard(db_ord_id)
            target_admins = list(ADMIN_TELEGRAM_IDS)
            if ADMIN_CHAT_ID and ADMIN_CHAT_ID.lstrip("-").isdigit() and int(ADMIN_CHAT_ID) not in target_admins:
                target_admins.append(int(ADMIN_CHAT_ID))
            for aid in target_admins:
                try:
                    await safe_send(aid, admin_alert, reply_markup=kb)
                except Exception as e:
                    log_bot_error(aid, f"Failed to send admin order alert: {e}", exc=e)
        return

    # 0. Promokod kutish holati tekshiruvi
    if user_id in PROMO_WAITING_USERS:
        PROMO_WAITING_USERS.remove(user_id)
        res = PromoManager.validate_code(text)
        if res["valid"]:
            CartManager.apply_promo(user_id, res["code"], discount_percent=res["percent"], discount_amount=res["amount"])
            summary = CartManager.get_cart_summary(user_id)
            kb = get_cart_keyboard(summary["items"], has_promo=True)
            await message.answer(f"{res['message']}\n\n" + CartManager.format_cart_message(user_id), reply_markup=kb)
            return
        else:
            await message.answer(res["message"])
            return

    # 0a. Checkout (savatdan ko'p tovarli buyurtma) kutish holati
    if user_id in CHECKOUT_WAITING_USERS:
        state = CHECKOUT_WAITING_USERS[user_id]
        if state.get("stage") == "phone":
            phone_match = re.search(r"(\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}|\b\d{9}\b)", text)
            if phone_match or len(text.strip()) >= 7:
                clean_phone = phone_match.group(1).replace(" ", "") if phone_match else text.strip()
                if not clean_phone.startswith("+"):
                    clean_phone = "+998" + clean_phone if len(clean_phone) == 9 else "+" + clean_phone
                state["phone"] = clean_phone
                state["stage"] = "address"
                DatabaseManager.upsert_customer(telegram_id=user_id, full_name=user_name, phone=clean_phone)
                await message.answer(
                    f"📱 Telefon qabul qilindi: `{clean_phone}` ✅\n\n"
                    f"Endi buyurtmangizni yetkazib berish **manzilini** (shahar, tuman, mahalla, uy) yozib yuboring (yoki pastdagi geolokatsiya tugmasini bosing):",
                    reply_markup=get_location_request_keyboard()
                )
                return
        elif state.get("stage") == "address":
            address = text.strip()
            phone = state.get("phone") or (customer.get("phone") if customer else "")
            DatabaseManager.upsert_customer(telegram_id=user_id, full_name=user_name, address=address)
            CHECKOUT_WAITING_USERS.pop(user_id, None)

            summary = CartManager.get_cart_summary(user_id)
            if summary["items"]:
                order_items = [{"product_id": i["product_id"], "quantity": i["quantity"]} for i in summary["items"]]
                order_res = DatabaseManager.create_order(
                    customer_telegram_id=user_id,
                    customer_name=user_name,
                    customer_phone=phone,
                    delivery_address=address,
                    items=order_items,
                    payment_method="cash_on_delivery",
                    notes=f"Savatchadan (Promo: {summary['promo_code'] or 'yoq'})"
                )
                if order_res.get("success"):
                    new_id = order_res["order_id"]
                    CartManager.clear_cart(user_id)
                    if summary["promo_code"]:
                        PromoManager.register_usage(summary["promo_code"])

                    delivery_label = "Bepul! (Sovg'a)" if summary["free_delivery"] else "Oddiy tarif"
                    confirm_text = (
                        f"🎉 **BUYURTMANGIZ QABUL QILINDI!**\n\n"
                        f"🧾 Buyurtma raqami: **#{new_id}**\n"
                        f"👤 Qabul qiluvchi: **{user_name}**\n"
                        f"📱 Telefon: `{phone}`\n"
                        f"📍 Manzil: **{address}**\n"
                        f"💰 Jami to'lov: **{summary['final_total']:,.0f} so'm**\n"
                        f"🚚 Yetkazib berish: {delivery_label}\n\n"
                        f"Kuryerimiz tez orada siz bilan bog'lanadi! Xaridingiz barakali bo'lsin! 😊"
                    )
                    await message.answer(confirm_text, reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS, cart_count=0))

                    admin_alert = (
                        f"🔔 **YANGI KO'P TOVARLI BUYURTMA #{new_id}!**\n\n"
                        f"👤 Mijoz: {user_name} (ID: `{user_id}`)\n"
                        f"📱 Tel: {phone}\n"
                        f"📍 Manzil: {address}\n"
                        f"💰 Summa: **{summary['final_total']:,.0f} so'm**\n"
                        f"📦 Tovarlar ({len(summary['items'])} xil):\n" +
                        "\n".join([f"  • {i['name']} ({i['quantity']}x) - {i['price']:,.0f} so'm" for i in summary['items']])
                    )
                    for aid in ADMIN_TELEGRAM_IDS:
                        await safe_send(aid, admin_alert, reply_markup=get_order_action_keyboard(new_id))
                    return

    # 0b. Savat va Promokod tabiiy so'rovlari
    if text_lower in ["savat", "savatcha", "karzinka", "savatim"]:
        summary = CartManager.get_cart_summary(user_id)
        text_cart = CartManager.format_cart_message(user_id)
        kb = get_cart_keyboard(summary["items"], has_promo=bool(summary["promo_code"]))
        await message.answer(text_cart, reply_markup=kb)
        return

    if any(w in text_lower for w in ["promokod", "promokodlar", "chegirma kodi", "aksiyalar"]):
        await message.answer(PromoManager.get_active_promos_display())
        return

    # Admin yangi tovar matnini yuborgan bo'lsa
    if user_id in ADMIN_TELEGRAM_IDS and ("keldi" in text_lower or "tan narxi" in text_lower or "sotuv" in text_lower):
        parsed = agent.parse_product_voice_text(text)
        prod_id = DatabaseManager.add_product(
            name=parsed["name"],
            category=parsed["category"],
            size=parsed["size"],
            color=parsed["color"],
            cost_price=parsed["cost_price"],
            sale_price=parsed["sale_price"],
            stock_quantity=parsed["stock_quantity"],
            description=parsed["description"]
        )
        await message.answer(
            f"✅ **Yangi tovar muvaffaqiyatli omborga qo'shildi!**\n\n"
            f"📦 **Nomi:** {parsed['name']}\n"
            f"📂 **Kategoriya:** {parsed['category']}\n"
            f"📏 **Razmer:** {parsed['size']} | **Rang:** {parsed['color']}\n"
            f"💵 **Tan narx:** {parsed['cost_price']:,.0f} so'm\n"
            f"💰 **Sotuv narx:** {parsed['sale_price']:,.0f} so'm\n"
            f"📊 **Omborda:** {parsed['stock_quantity']} dona\n"
            f"🆔 Mahsulot ID: #{prod_id}"
        )
        return

    # === TABIIY TIL INTENTLARI (Foydalanuvchi tugma matnini yozganda ham to'g'ri ishlash) ===
    # 1. Excel intent
    if any(w in text_lower for w in ["excel", "eksel", "jadval", "файлни юкла", "excelni ber", "excel malumotlarini"]):
        if user_id in ADMIN_TELEGRAM_IDS:
            await message.answer("⏳ Barcha buyurtmalar va ombor qoldiqlari bo'yicha to'liq Excel (.xlsx) hisoboti tayyorlanmoqda...")
            file_path = ExcelExporter.generate_full_report()
            await message.answer_document(
                document=types.FSInputFile(file_path),
                caption=f"📊 **{STORE_NAME}** - To'liq Moliyaviy va Ombor Excel Hisoboti"
            )
            return

    # 2. SaaS Biznes Paneli intent
    if any(w in text_lower for w in ["saas", "sas", "mrr", "biznes panel", "b2b", "boshqaruv paneli"]):
        if user_id in ADMIN_TELEGRAM_IDS:
            data = TenantManager.calculate_saas_mrr()
            text_saas = (
                f"🏢 **B2B SaaS Biznes Boshqaruv Markazi**\n"
                f"───────────────────────\n"
                f"👥 **Jami ulangan do'konlar:** {data['total_clients']} ta\n"
                f"🟢 **Faol do'konlar:** {data['active_clients']} ta\n"
                f"💰 **Oylik daromad (MRR):** {data['monthly_recurring_revenue']:,.0f} so'm\n"
                f"📈 **Yillik aylanma (ARR):** {data['annual_run_rate']:,.0f} so'm\n\n"
                f"➕ **Yangi do'kon qo'shish uchun buyruq:**\n"
                f"`/yangi_dokon Nomi, Egasi, Telefon, Shahar, Dostavka, Token`\n"
                f"───────────────────────\n"
                f"💡 *10 ta do'kon ulasangiz = Oyiga kamida 5,000,000 so'm passiv daromad!*"
            )
            await safe_send(message.chat.id, text_saas)
            return

    # 3. Sales Pitch / Nega bu bot kerak? intent
    if any(w in text_lower for w in ["pitch", "nega bu bot", "nega bot", "foydasi", "dokon egasiga", "do'kon egasi", "nima foyda", "kalkulyator", "taklif", "g'oya", "goyalar"]):
        pitch_text = SalesPitchAdvisor.get_full_pitch()
        roi_text = SalesPitchAdvisor.format_roi_message()
        hacks_text = SalesPitchAdvisor.get_growth_hacks()
        await safe_send(message.chat.id, pitch_text)
        await safe_send(message.chat.id, roi_text)
        await safe_send(message.chat.id, hacks_text)
        return

    # 4. Kassa Hisoboti intent
    if any(w in text_lower for w in ["kassa hisoboti", "kassa", "hisobot kursat", "qancha tushum"]):
        if user_id in ADMIN_TELEGRAM_IDS:
            await message.answer(
                "📊 **Qaysi davr bo'yicha kassa hisobotini ko'rmoqchisiz?**\nTanlang 👇",
                reply_markup=get_report_periods_keyboard()
            )
            return

    # 5. Ombor qoldiqlari intent
    if any(w in text_lower for w in ["ombor va zakaz", "qoldiqlar", "kam qolgan tovar"]):
        if user_id in ADMIN_TELEGRAM_IDS:
            alerts = InventoryManager.get_stock_alerts()
            text_inv = InventoryManager.format_inventory_message(alerts)
            await safe_send(message.chat.id, text_inv)
            return

    # === MAHSULOT VA OMBOR QOIDALARI (Task 2 & Rules 3, 6, 10) ===
    matched_prods = OrderMatcher.match_products_multi(
        text,
        history=ai_brain.conversations.get(message.chat.id, [])
    )
    first_matched = matched_prods[0] if matched_prods else None

    if first_matched:
        # Stock qoidalarini deterministik tekshirish (Rule 6, Rule 10, Task 2: Stock rules in CODE)
        stock_eval = StockAdvisor.evaluate_stock_rules(text, first_matched)
        if stock_eval:
            if stock_eval["type"] == "sold_out":
                PENDING_WAITLIST_OFFERS[message.chat.id] = first_matched["id"]
                await safe_send(message.chat.id, stock_eval["reply"])
                return
            elif stock_eval["type"] == "quantity_above_stock":
                await safe_send(message.chat.id, stock_eval["reply"])
                return

        # Task 3: Agar xaridor to'g'ridan-to'g'ri xarid qilishga rozi bo'lsa (Trigger only when customer agrees to buy)
        if OrderFlowService.is_buy_intent(text):
            set_pending_order(user_id, first_matched)
            flow_res = OrderFlowService.start_order_flow(
                chat_id=message.chat.id,
                initial_product=first_matched,
                initial_text=text,
                crm_customer=customer
            )
            await safe_send(message.chat.id, flow_res["reply"])
            return

        # Mahsulot haqida so'ralgan yoki qidirilgan bo'lsa, rasmli taqdimot yuborish (Task 2: Requirements 1 & 2)
        product_query_triggers = [
            "bormi", "bor mi", "narxi", "qancha", "necha", "rasm", "rasmi", "foto",
            "kursat", "ko'rsat", "koʻrsat", "haqida", "ma'lumot",
            "tavsiya", "variant", "razmer", "o'lcham", "kurtka", "krossovka", "krasovka",
            "futbolka", "shim", "ko'ylak", "koylak", "palto", "paypoq", "kepka",
            "zara", "nike", "adidas", "uztex", "defacto", "pull&bear", "h&m"
        ]
        is_asking_product = (
            any(w in text_lower for w in product_query_triggers)
            or bool(re.search(r"\b(?:kk[-_\s]?)(\d{4})\b", text_lower))
            or bool(re.search(r"(?:#|buy_|id\s*|tovar\s*|mahsulot\s*)(\d{1,3})", text_lower))
            or (first_matched.get("name", "").lower() in text_lower)
        )
        if is_asking_product:
            set_pending_order(user_id, first_matched)
            await send_product_presentation(
                bot=bot,
                chat_id=message.chat.id,
                products=matched_prods[:3],
                safe_send_fn=safe_send
            )
            # TASK 4: Cross-sell - suggest ONE related in-stock item once per conversation
            cs_sugg = SalesIntelligence.get_cross_sell_suggestion(first_matched["id"], chat_id=message.chat.id)
            if cs_sugg and cs_sugg.get("suggestion_text"):
                await safe_send(message.chat.id, cs_sugg["suggestion_text"])
            return

    # Task 3: Mahsulot nomi aytilmagan bo'lsa ham xarid niyati bo'lsa
    if OrderFlowService.is_buy_intent(text):
        target_prod = OrderMatcher.match_product(
            text,
            history=ai_brain.conversations.get(message.chat.id, []),
            pending_product=USER_PENDING_ORDERS.get(user_id)
        )
        flow_res = OrderFlowService.start_order_flow(
            chat_id=message.chat.id,
            initial_product=target_prod,
            initial_text=text,
            crm_customer=customer
        )
        await safe_send(message.chat.id, flow_res["reply"])
        return

    # Typing action
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except Exception:
        pass

    # === ASOSIY OQIM: Barcha xabarlar LLM ga boradi (oxirgi 10 ta xabar xotirasi bilan) ===
    response = ai_brain.ask(
        chat_id=message.chat.id,
        user_message=text,
        customer_name=user_name
    )

    # 1. Agar foydalanuvchi jonli operator so'ragan bo'lsa yoki Grounding talab etilsa (Rule 8)
    if "operatorga ulayman" in response.lower() or "aniqlashtirib, operator javob beradi" in response.lower():
        admin_alert = (
            f"🔔 **Mijoz jonli operator / adminga ulanishni so'radi!**\n\n"
            f"👤 **Mijoz:** {user_name} (ID: `{user_id}`)\n"
            f"📱 **Username:** @{message.from_user.username or 'mavjud_emas'}\n"
            f"💬 **Xabar:** {text}\n"
            f"ℹ️ **Holat:** {response}"
        )
        for aid in ADMIN_TELEGRAM_IDS:
            try:
                await safe_send(aid, admin_alert)
            except Exception as e:
                log_bot_error(aid, f"Failed to alert admin: {e}", exc=e)

    # 2. Agar xaridor buyurtma tafsilotlarini (telefon va manzil) yuborgan bo'lsa, DB ga yozish va tasdiqlash
    has_pending = user_id in USER_PENDING_ORDERS
    order_details = OrderMatcher.extract_order_details(text, has_pending_order=has_pending)
    if order_details and order_details.get("is_complete"):
        try:
            target_prod = OrderMatcher.match_product(
                text,
                history=ai_brain.conversations.get(message.chat.id, []),
                pending_product=USER_PENDING_ORDERS.get(user_id)
            )
            if target_prod:
                qty = order_details.get("quantity", 1)
                stock_check = DatabaseManager.check_stock_strict(target_prod["id"], qty)
                if stock_check["available"]:
                    order_res = DatabaseManager.create_order(
                        customer_telegram_id=user_id,
                        customer_name=user_name,
                        customer_phone=order_details["phone"],
                        delivery_address=order_details["address"],
                        items=[{"product_id": target_prod["id"], "quantity": qty}],
                        payment_method="cash_on_delivery",
                        notes=f"Zakaz ({qty} dona): {text[:150]}"
                    )
                    if order_res.get("success"):
                        clear_pending_order(user_id)
                        total_sum = qty * float(target_prod["sale_price"])
                        confirm_msg = (
                            f"🎉 **Buyurtmangiz muvaffaqiyatli qabul qilindi!**\n\n"
                            f"🧾 Buyurtma raqami: **#{order_res['order_id']}**\n"
                            f"🛍️ Mahsulot: **{target_prod['name']}** ({qty} dona)\n"
                            f"💰 Jami summa: **{total_sum:,.0f} so'm**\n"
                            f"📍 Manzil: **{order_details['address']}**\n"
                            f"📞 Telefon: `{order_details['phone']}`\n\n"
                            f"Kuryerimiz tez orada siz bilan bog'lanib, buyurtmani yetkazib beradi! Rahmat 😊"
                        )
                        await safe_send(message.chat.id, confirm_msg, reply_markup=get_main_menu(is_admin=user_id in ADMIN_TELEGRAM_IDS))

                        admin_alert = OrderMatcher.format_admin_alert(
                            order_id=order_res["order_id"],
                            product=target_prod,
                            user_name=user_name,
                            phone=order_details["phone"],
                            address=order_details["address"],
                            full_raw=f"{text} (Miqdor: {qty} dona)"
                        )
                        for aid in ADMIN_TELEGRAM_IDS:
                            try:
                                await safe_send(aid, admin_alert, reply_markup=get_order_action_keyboard(order_res["order_id"]))
                            except Exception:
                                pass
                        if CHANNEL_ID:
                            try:
                                await safe_send(CHANNEL_ID, admin_alert)
                            except Exception:
                                pass
                        return
        except Exception as e:
            logger.error(f"Avtomatik buyurtma qaydida xatolik: {e}")

    # Savollarga javob qaytarish
    await safe_send(message.chat.id, response, reply_markup=None)


# Global Error Handler: Kutilmagan xatolik yuz berganda Webhook 500 qaytarmasligi va Telegram loopga tushmasligi kafolati
@dp.errors()
async def global_error_handler(event: ErrorEvent):
    logger.error(f"Telegram handler xatoligi: {event.exception}", exc_info=event.exception)
    try:
        if event.update and event.update.message:
            await event.update.message.answer(
                "Kechirasiz, tizimda qisqa uzilish yuz berdi. Iltimos, xabaringizni qaytadan yuboring."
            )
        elif event.update and event.update.callback_query:
            await event.update.callback_query.answer(
                "Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.", show_alert=True
            )
    except Exception:
        pass
    return True


from aiohttp import web
import subprocess
import collections
from datetime import datetime

CURRENT_VERSION = "v5.0-global-retail-flagship"
PING_HISTORY = collections.deque(maxlen=30)

def get_current_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "latest"

async def handle_health_check(request):
    ua = request.headers.get("User-Agent", "Unknown")
    client_ip = request.headers.get("X-Forwarded-For", request.remote or "Unknown")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    PING_HISTORY.append({
        "time": now_str,
        "ua": ua[:80],
        "ip": str(client_ip).split(",")[0].strip(),
        "path": request.path
    })
    return web.Response(text="MarkazSavdo Ingichka AI Bot is 100% LIVE and Running 24/7!", status=200)

async def handle_status(request):
    ua = request.headers.get("User-Agent", "Unknown")
    client_ip = request.headers.get("X-Forwarded-For", request.remote or "Unknown")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    PING_HISTORY.append({
        "time": now_str,
        "ua": ua[:80],
        "ip": str(client_ip).split(",")[0].strip(),
        "path": request.path
    })
    prods = DatabaseManager.get_products(in_stock_only=False)
    data = {
        "status": "healthy",
        "version": CURRENT_VERSION,
        "commit": get_current_commit(),
        "bot_username": "Markazsavdo00_bot",
        "products_count": len(prods),
        "products": [{"id": p["id"], "name": p["name"], "stock": p["stock_quantity"], "price": p["sale_price"]} for p in prods],
        "has_gemini": bool(GEMINI_API_KEY),
        "has_token": bool(BOT_TOKEN),
        "recent_pings": list(PING_HISTORY)
    }
    return web.json_response(data)

async def handle_diag(request):
    """Render konteyneri ichidagi AI va tizim holatini to'liq tekshirish diagnostikasi"""
    prods = DatabaseManager.get_products(in_stock_only=False)
    gemini_alive = False
    sample_response = ""
    try:
        test_out = ai_brain.ask(chat_id=999999999, user_message="futbolka bormi", customer_name="TestMijoz")
        if test_out:
            gemini_alive = True
            sample_response = test_out
    except Exception as e:
        sample_response = f"Xato: {e}"

    diag_data = {
        "status": "online",
        "version": CURRENT_VERSION,
        "commit": get_current_commit(),
        "gemini_working": gemini_alive,
        "sample_response": sample_response,
        "total_products": len(prods),
        "channel_configured": bool(CHANNEL_ID)
    }
    return web.json_response(diag_data)

async def self_ping_task(base_url: str = "https://ingichka-smart-store-bot.onrender.com"):
    health_url = f"{base_url.rstrip('/')}/health"
    logger.info(f"Render 24/7 self-pinger faollashtirildi: {health_url}")
    await asyncio.sleep(20)
    import aiohttp
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(health_url, timeout=15) as resp:
                    logger.info(f"Render self-ping: status {resp.status}")
            except Exception as e:
                logger.warning(f"Self-ping xatosi: {e}")
            await asyncio.sleep(240)

async def webhook_watchdog_task(bot_inst: Bot, webhook_url: str):
    """
    Render 24/7 Webhook Qorovuli (Self-Healing Watchdog).
    Har 45 soniyada Telegram Webhook holatini tekshiradi.
    Agar webhook tasodifan o'chirilgan yoki uzilgan bo'lsa, uni darhol avtomatik qayta tiklaydi!
    """
    logger.info(f"Render Webhook Watchdog faollashtirildi: {webhook_url}")
    await asyncio.sleep(30)
    while True:
        try:
            info = await bot_inst.get_webhook_info()
            if info.url != webhook_url:
                logger.warning(f"[WATCHDOG] Webhook buzilgan ({info.url}). Darhol tiklanmoqda: {webhook_url}")
                await bot_inst.set_webhook(
                    webhook_url,
                    drop_pending_updates=False,
                    allowed_updates=dp.resolve_used_update_types()
                )
                logger.info("[WATCHDOG] Webhook muvaffaqiyatli tiklandi!")
        except Exception as e:
            logger.warning(f"[WATCHDOG] Tekshirishda ogohlantirish: {e}")
        await asyncio.sleep(45)

async def on_startup(bot: Optional[Bot] = None, *args: Any, **kwargs: Any) -> None:
    bot_inst = bot or kwargs.get("bot") or globals().get("bot")
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://ingichka-smart-store-bot.onrender.com")
    webhook_url = f"{render_url.rstrip('/')}/webhook"
    logger.info(f"Telegram Webhook sozlanmoqda: {webhook_url}")
    for attempt in range(5):
        try:
            await bot_inst.set_webhook(
                webhook_url,
                drop_pending_updates=False,
                allowed_updates=dp.resolve_used_update_types()
            )
            logger.info(f"Telegram Webhook muvaffaqiyatli ulandi: {webhook_url}")
            break
        except Exception as e:
            logger.error(f"Webhook o'rnatishda xatolik (urinish {attempt+1}/5): {e}")
            await asyncio.sleep(3)
    asyncio.create_task(self_ping_task(render_url))
    asyncio.create_task(webhook_watchdog_task(bot_inst, webhook_url))

def main():
    init_db()
    logger.info("Ingichka Baraka Savdo Markazi AI boti ishga tushmoqda...")

    if "--polling" in sys.argv:
        logger.info("Mahalliy sinov uchun Polling rejimida ishga tushirilmoqda (--polling)...")
        asyncio.run(dp.start_polling(bot))
        return

    port_env = os.getenv("PORT")
    is_render = bool(os.getenv("RENDER")) or bool(port_env)

    if is_render:
        port = int(port_env) if port_env else 8080
        render_url = os.getenv("RENDER_EXTERNAL_URL", "https://ingichka-smart-store-bot.onrender.com")
        logger.info(f"Render Cloud Webhook rejimi faollashmoqda (Port: {port}, URL: {render_url})")

        dp.startup.register(on_startup)

        app = web.Application()
        app.router.add_get("/", handle_health_check)
        app.router.add_get("/health", handle_health_check)
        app.router.add_get("/status", handle_status)
        app.router.add_get("/diag", handle_diag)

        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

        web.run_app(app, host="0.0.0.0", port=port)
    else:
        pid_file = Path(__file__).resolve().parent.parent / ".bot_sentinel.pid"
        try:
            pid_file.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

        render_url = os.getenv("RENDER_EXTERNAL_URL", "https://ingichka-smart-store-bot.onrender.com")
        webhook_target = f"{render_url.rstrip('/')}/webhook"
        logger.info(f"Mahalliy Aqlli Qo'riqchi (Local Sentinel & Watchdog) ishga tushmoqda (PID: {os.getpid()}, Cloud Target: {webhook_target})...")

        async def run_local_sentinel():
            import aiohttp
            async with aiohttp.ClientSession() as session:
                fail_count = 0
                while True:
                    try:
                        # 1. Render serverini tekshirish va uyg'oq saqlash (Keep-Alive Ping)
                        health_url = f"{render_url.rstrip('/')}/health"
                        render_alive = False
                        try:
                            async with session.get(health_url, timeout=12) as resp:
                                if resp.status == 200:
                                    render_alive = True
                                    fail_count = 0
                                else:
                                    fail_count += 1
                        except Exception:
                            fail_count += 1

                        # 2. Telegram Webhook holatini nazorat qilish
                        try:
                            info = await bot.get_webhook_info()
                            if render_alive:
                                if info.url != webhook_target:
                                    logger.info(f"[SENTINEL] Webhook Renderga ulanmoqda: {webhook_target}")
                                    await bot.set_webhook(
                                        webhook_target,
                                        drop_pending_updates=False,
                                        allowed_updates=dp.resolve_used_update_types()
                                    )
                                    logger.info("[SENTINEL] Webhook muvaffaqiyatli o'rnatildi!")
                                logger.info("[SENTINEL] Render Cloud 24/7 faol, Webhook to'g'ri sozlangan, bot 100% uyg'oq.")
                            else:
                                # Render uxlab qolgan bo'lsa yoki uyg'onish jarayonida bo'lsa, Webhookni Renderga yo'naltirilgan holda saqlaymiz!
                                if info.url != webhook_target:
                                    logger.warning(f"[SENTINEL] Webhook tiklanmoqda: {webhook_target}")
                                    await bot.set_webhook(
                                        webhook_target,
                                        drop_pending_updates=False,
                                        allowed_updates=dp.resolve_used_update_types()
                                    )
                                logger.info(f"[SENTINEL] Render uyg'onishi kutilmoqda (fail_count: {fail_count}). Webhook xavfsiz saqlanmoqda.")
                        except Exception as e:
                            logger.error(f"[SENTINEL] Telegram API tekshiruvida xato: {e}")

                    except Exception as loop_err:
                        logger.error(f"[SENTINEL] Asosiy sikl xatosi: {loop_err}")

                    await asyncio.sleep(60)

        asyncio.run(run_local_sentinel())

if __name__ == "__main__":
    main()
