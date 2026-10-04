"""
services/order_flow_service.py
TASK 3: Order flow as a state machine. Strictly follows RULES.md.

1. Trigger only when the customer clearly agrees to buy.
   States: product -> size -> color -> quantity -> name -> phone -> address -> summary -> confirm -> done.
   Persist state per chat_id in data/order_states.json.
2. Ask ONE field per message. Skip fields already known from memory.
3. Validate in code:
   - Phone must be a valid Uzbekistan number (+998 and 9 digits, accept 90 123 45 67 / 998901234567 formats, normalize to +998XXXXXXXXX).
   - Size/color must exist for that product and be in stock.
   - Quantity must be positive integer <= available stock.
   - Re-ask politely on invalid input.
4. Summary message is built by CODE from data (product, size, color, qty, unit price, total, delivery info).
   The LLM must not write numbers.
5. On "ha/tasdiqlayman":
   - Generate order_id (e.g. ORD-000123).
   - Decrease stock atomically.
   - Save to data/orders.json (thread-safe, atomic write).
   - Send formatted order to ADMIN_CHAT_ID with inline buttons: Qabul qilindi / Bekor qilish.
   - Tell the customer thanks + order_id.
6. Customer can say "bekor qilish" or "o'zgartirish" at any step: cancel or edit the field.
   Any unrelated question mid-flow is answered, then the flow resumes.
7. Double-click/duplicate confirm must not create two orders (idempotency).
"""

import os
import re
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from utils.file_utils import atomic_write_json
from database.db_manager import DatabaseManager
from services.catalog_service import load_products, PRODUCTS_FILE

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ORDER_STATES_FILE = DATA_DIR / "order_states.json"
ORDERS_FILE = DATA_DIR / "orders.json"

_ORDER_FLOW_LOCK = threading.RLock()

# -------------------------------------------------------------
# States Definition
# -------------------------------------------------------------
STATE_PRODUCT = "product"
STATE_SIZE = "size"
STATE_COLOR = "color"
STATE_QUANTITY = "quantity"
STATE_NAME = "name"
STATE_PHONE = "phone"
STATE_ADDRESS = "address"
STATE_SUMMARY = "summary"
STATE_CONFIRM = "confirm"
STATE_DONE = "done"

STATES_SEQUENCE = [
    STATE_PRODUCT,
    STATE_SIZE,
    STATE_COLOR,
    STATE_QUANTITY,
    STATE_NAME,
    STATE_PHONE,
    STATE_ADDRESS,
    STATE_SUMMARY,
    STATE_CONFIRM,
    STATE_DONE
]

DEFAULT_DELIVERY_INFO = "Ingichka va tuman bo'ylab bepul (1 kun ichida)"


class OrderFlowService:
    """Buyurtma olish ko'p bosqichli holat mashinasi (State Machine)"""

    # ---------------------------------------------------------
    # 1. Trigger Detection (Only when customer clearly agrees to buy)
    # ---------------------------------------------------------
    @classmethod
    def is_buy_intent(cls, text: str) -> bool:
        """
        Mijoz aniq xarid qilishga rozi bo'lganini tekshirish.
        Oddiy savollar (narx, bormi, razmer bormi) xarid deb hisoblanmaydi.
        """
        if not text:
            return False
        t = text.lower().strip()

        # Aniq xarid niyatini ifodalovchi iboralar
        buy_patterns = [
            r"\b(?:sotib\s+)?olaman\b",
            r"\bolmoqchiman\b",
            r"\bolmoqchimiz\b",
            r"\bsotib\s+olmoqchiman\b",
            r"\bxarid\s+qilmoqchiman\b",
            r"\bxarid\s+qilaman\b",
            r"\bzakaz\s+qilmoqchiman\b",
            r"\bzakaz\s+qilmoqchimiz\b",
            r"\bzakaz\s+bermoqchiman\b",
            r"\bzakaz\s+qilaman\b",
            r"\bzakaz\s+beraman\b",
            r"\bzakaz\s+qilay\b",
            r"\bzakaz\s+qilmoqchi\b",
            r"\bbuyurtma\s+qilmoqchiman\b",
            r"\bbuyurtma\s+bermoqchiman\b",
            r"\bbuyurtma\s+qilaman\b",
            r"\bbuyurtma\s+beraman\b",
            r"\bbuyurtma\s+qilay\b",
            r"\bbuyurtma\s+qilmoqchi\b",
            r"\bmenga\s+(?:ham\s+|yam\s+)?(?:bering|yuboring|jo'nating|jo‘nating|jonating)\b",
            r"\bbuni\s+olaman\b",
            r"\bshuni\s+olaman\b",
            r"\bshuni\s+zakaz\b"
        ]

        for pat in buy_patterns:
            if re.search(pat, t):
                return True
        return False

    # ---------------------------------------------------------
    # 2. Validation in Code (Phone, Size, Color, Quantity)
    # ---------------------------------------------------------
    @classmethod
    def validate_and_normalize_phone(cls, phone_text: str) -> Optional[str]:
        """
        Validate in code: phone must be a valid Uzbekistan number (+998 and
        9 digits, accept 90 123 45 67 / 998901234567 formats, normalize to
        +998XXXXXXXXX).
        """
        if not phone_text:
            return None
        cleaned = re.sub(r"[^\d+]", "", phone_text.strip())
        digits = cleaned.lstrip("+")

        # 9 raqamli mahalliy format (masalan: 901234567)
        if len(digits) == 9 and digits.isdigit():
            return f"+998{digits}"

        # 12 raqamli xalqaro format (masalan: 998901234567)
        if len(digits) == 12 and digits.startswith("998") and digits.isdigit():
            return f"+{digits}"

        return None

    @classmethod
    def get_available_sizes(cls, product: Dict[str, Any]) -> List[str]:
        """Mahsulotning mavjud o'lchamlarini olish"""
        sizes = []
        if isinstance(product.get("sizes"), list) and product["sizes"]:
            sizes.extend(product["sizes"])
        elif product.get("size"):
            sizes.append(str(product["size"]))

        # Katalogdagi bir xil brend/kategoriya qatorini ham tekshirish
        try:
            prod_name = product.get("name", "")
            base_name = prod_name.split()[0] if prod_name else ""
            all_prods = DatabaseManager.get_products(in_stock_only=True)
            for p in all_prods:
                if p.get("name", "").startswith(base_name) and p.get("category") == product.get("category"):
                    s = p.get("size")
                    if s and s not in sizes:
                        sizes.append(s)
        except Exception:
            pass

        seen = set()
        result = []
        for s in sizes:
            clean_s = s.strip()
            norm = clean_s.upper()
            if norm not in seen:
                seen.add(norm)
                result.append(clean_s)
        return result if result else ["Standart"]

    @classmethod
    def validate_size(cls, product: Dict[str, Any], size_input: str) -> Tuple[bool, Optional[str], List[str]]:
        """O'lcham mavjudligini kod orqali tekshirish"""
        avail = cls.get_available_sizes(product)
        inp = size_input.strip().upper()
        for s in avail:
            if s.strip().upper() == inp:
                return True, s, avail
        return False, None, avail

    @classmethod
    def get_available_colors(cls, product: Dict[str, Any]) -> List[str]:
        """Mahsulotning mavjud ranglarini olish"""
        colors = []
        if isinstance(product.get("colors"), list) and product["colors"]:
            colors.extend(product["colors"])
        elif product.get("color"):
            colors.append(str(product["color"]))

        try:
            prod_name = product.get("name", "")
            base_name = prod_name.split()[0] if prod_name else ""
            all_prods = DatabaseManager.get_products(in_stock_only=True)
            for p in all_prods:
                if p.get("name", "").startswith(base_name) and p.get("category") == product.get("category"):
                    c = p.get("color")
                    if c and c not in colors:
                        colors.append(c)
        except Exception:
            pass

        seen = set()
        result = []
        for c in colors:
            clean_c = c.strip()
            norm = clean_c.lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'")
            if norm not in seen:
                seen.add(norm)
                result.append(clean_c)
        return result if result else ["Asl rang"]

    @classmethod
    def validate_color(cls, product: Dict[str, Any], color_input: str) -> Tuple[bool, Optional[str], List[str]]:
        """Rang mavjudligini kod orqali tekshirish"""
        avail = cls.get_available_colors(product)
        inp = color_input.strip().lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'")
        for c in avail:
            c_norm = c.strip().lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'")
            if c_norm == inp or inp in c_norm:
                return True, c, avail
        return False, None, avail

    @classmethod
    def validate_quantity(cls, product: Dict[str, Any], qty_input: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Miqdorni tekshirish: musbat butun son va ombordagi qoldiqdan oshmasligi kerak.
        Agar mijoz ombordagidan ko'p so'rasa, aniq mavjud sonini bildirish (Task 2: Rule 4).
        """
        stock = product.get("stock_quantity")
        if stock is None:
            stock = product.get("stock", 0)
        stock = int(stock)

        word_map = {
            "bitta": 1, "bir": 1, "1ta": 1, "1 dona": 1, "1dona": 1,
            "ikkita": 2, "ikki": 2, "2ta": 2, "2 dona": 2, "2dona": 2,
            "uchta": 3, "uch": 3, "3ta": 3, "3 dona": 3, "3dona": 3,
            "to'rtta": 4, "tortta": 4, "toʻrtta": 4, "4ta": 4, "4 dona": 4,
            "beshta": 5, "besh": 5, "5ta": 5, "5 dona": 5,
            "oltita": 6, "olti": 6, "6ta": 6,
            "yettita": 7, "yetti": 7, "7ta": 7,
            "sakkizta": 8, "sakkiz": 8, "8ta": 8,
            "to'qqizta": 9, "toqqizta": 9, "9ta": 9,
            "o'nta": 10, "onta": 10, "10ta": 10
        }
        cleaned = qty_input.strip().lower()
        qty = None
        if cleaned in word_map:
            qty = word_map[cleaned]
        else:
            m = re.search(r"\b(\d+)\b", cleaned)
            if m:
                qty = int(m.group(1))

        if qty is None or qty <= 0:
            return False, None, "Iltimos, mahsulot miqdorini musbat raqamda kiriting (masalan: 1 yoki 2):"

        if qty > stock:
            return False, None, f"Kechirasiz, omborimizda ushbu mahsulotdan faqat {stock} dona mavjud. Nechta buyurtma qilasiz?"

        return True, qty, None

    # ---------------------------------------------------------
    # 3. Intent Helpers: Cancel, Edit, Unrelated Question
    # ---------------------------------------------------------
    @classmethod
    def is_cancel_intent(cls, text: str) -> bool:
        """Bekor qilish niyatini tekshirish"""
        if not text:
            return False
        t = text.lower().strip()
        cancel_keywords = ["bekor qilish", "bekor", "otmena", "cancel", "rad etish", "kerakmas", "to'xtatish", "yo'q, bekor"]
        return any(k == t or t.startswith(k) for k in cancel_keywords)

    @classmethod
    def is_edit_intent(cls, text: str) -> Tuple[bool, Optional[str]]:
        """O'zgartirish niyatini tekshirish"""
        if not text:
            return False, None
        t = text.lower().strip()
        edit_keywords = ["o'zgartirish", "ozgartirish", "oʻzgartirish", "o'zgartirmoqchiman", "tahrirlash", "edit", "almashtirish", "boshqasini tanlayman"]
        is_edit = any(k in t for k in edit_keywords)
        if not is_edit:
            return False, None

        if any(w in t for w in ["manzil", "adres", "address", "joy"]):
            return True, STATE_ADDRESS
        if any(w in t for w in ["telefon", "nomer", "tel", "phone"]):
            return True, STATE_PHONE
        if any(w in t for w in ["ism", "nomi", "name"]):
            return True, STATE_NAME
        if any(w in t for w in ["miqdor", "dona", "soni", "nechta", "quantity"]):
            return True, STATE_QUANTITY
        if any(w in t for w in ["rang", "rangi", "color"]):
            return True, STATE_COLOR
        if any(w in t for w in ["o'lcham", "razmer", "size"]):
            return True, STATE_SIZE
        if any(w in t for w in ["tovar", "mahsulot", "product"]):
            return True, STATE_PRODUCT

        return True, None

    @classmethod
    def is_unrelated_question(cls, text: str, current_state: str) -> bool:
        """Jarayon o'rtasida berilgan mavzudan tashqari savolni aniqlash"""
        if not text:
            return False
        t = text.lower().strip()

        question_markers = [
            "qachon", "qayerda", "qanchada", "qancha vaqtda", "dostavka", "yetkazib",
            "kafolat", "garantiya", "material", "paxtami", "original", "haqiqiy",
            "ish vaqti", "do'kon qayerda", "dokon qayerda", "telefon raqamingiz",
            "to'lov qanday", "tolov turi", "click", "payme", "qanaqa", "nechida",
            "bormi", "mumkinmi", "qayerdan olasizlar"
        ]
        has_q = "?" in t or any(m in t for m in question_markers)
        if not has_q:
            return False

        # Agar kutilayotgan maydonga to'g'ri keluvchi format bo'lsa, savol emas
        if current_state == STATE_PHONE and cls.validate_and_normalize_phone(t):
            return False
        if current_state == STATE_QUANTITY and t.isdigit():
            return False
        if current_state == STATE_CONFIRM and t in ["ha", "tasdiqlayman", "xa", "ok"]:
            return False

        return True

    # ---------------------------------------------------------
    # 4. Summary Message Generator (Deterministic Code Math)
    # ---------------------------------------------------------
    @classmethod
    def build_summary_message(cls, data: Dict[str, Any]) -> str:
        """
        Summary message is built by CODE from data (product, size, color, qty,
        unit price, total, delivery info). The LLM must not write numbers.
        """
        qty = int(data.get("quantity") or 1)
        unit_price = float(data.get("unit_price") or 0.0)
        total = qty * unit_price
        delivery_info = DEFAULT_DELIVERY_INFO

        prod_name = data.get("product_name", "Mahsulot")
        size = data.get("size", "Standart")
        color = data.get("color", "Asl rang")
        name = data.get("name", "Mijoz")
        phone = data.get("phone", "")
        address = data.get("address", "")

        summary = (
            "📋 **Buyurtma xulosasi:**\n\n"
            f"🛍️ **Mahsulot:** **{prod_name}**\n"
            f"📏 **O'lcham:** {size}\n"
            f"🎨 **Rang:** {color}\n"
            f"🔢 **Miqdor:** {qty} dona\n"
            f"💵 **Dona narxi:** {unit_price:,.0f} so'm\n"
            f"💰 **Jami to'lov:** **{total:,.0f} so'm**\n"
            f"🚚 **Yetkazib berish:** {delivery_info}\n\n"
            f"👤 **Qabul qiluvchi:** {name}\n"
            f"📞 **Telefon:** `{phone}`\n"
            f"📍 **Yetkazish manzili:** {address}\n\n"
            "Buyurtmani tasdiqlaysizmi?\n"
            "Tasdiqlash uchun: **Ha** yoki **Tasdiqlayman**\n"
            "O'zgartirish uchun: **O'zgartirish**\n"
            "Bekor qilish uchun: **Bekor qilish**"
        )
        return summary

    # ---------------------------------------------------------
    # 5. State Persistence (data/order_states.json)
    # ---------------------------------------------------------
    @classmethod
    def _load_states(cls) -> Dict[str, Any]:
        with _ORDER_FLOW_LOCK:
            if not ORDER_STATES_FILE.exists():
                return {}
            try:
                with open(ORDER_STATES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
            return {}

    @classmethod
    def _save_states(cls, states: Dict[str, Any]) -> None:
        with _ORDER_FLOW_LOCK:
            atomic_write_json(str(ORDER_STATES_FILE), states, indent=2)

    @classmethod
    def get_session(cls, chat_id: int) -> Optional[Dict[str, Any]]:
        states = cls._load_states()
        return states.get(str(chat_id))

    @classmethod
    def has_active_flow(cls, chat_id: int) -> bool:
        session = cls.get_session(chat_id)
        if not session:
            return False
        state = session.get("state")
        return state is not None and state != STATE_DONE

    @classmethod
    def clear_session(cls, chat_id: int) -> None:
        with _ORDER_FLOW_LOCK:
            states = cls._load_states()
            cid_str = str(chat_id)
            if cid_str in states:
                del states[cid_str]
                cls._save_states(states)

    @classmethod
    def _save_session(cls, session: Dict[str, Any]) -> None:
        with _ORDER_FLOW_LOCK:
            states = cls._load_states()
            chat_id = str(session["chat_id"])
            states[chat_id] = session
            cls._save_states(states)

    # ---------------------------------------------------------
    # 6. Orders Storage (data/orders.json)
    # ---------------------------------------------------------
    @classmethod
    def _load_orders(cls) -> List[Dict[str, Any]]:
        with _ORDER_FLOW_LOCK:
            if not ORDERS_FILE.exists():
                return []
            try:
                with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
            return []

    @classmethod
    def _save_orders(cls, orders: List[Dict[str, Any]]) -> None:
        with _ORDER_FLOW_LOCK:
            atomic_write_json(str(ORDERS_FILE), orders, indent=2)

    @classmethod
    def generate_order_id(cls) -> str:
        orders = cls._load_orders()
        return f"ORD-{len(orders) + 1:06d}"

    # ---------------------------------------------------------
    # 7. Step Advance Logic (Ask ONE field per message, skip known)
    # ---------------------------------------------------------
    @classmethod
    def _get_next_field_prompt(cls, session: Dict[str, Any]) -> Tuple[str, str]:
        """
        Keyingi to'ldirilmagan maydonni aniqlash va tegishli savolni qaytarish.
        Qaytaradi: (state_name, prompt_message)
        """
        data = session.setdefault("data", {})
        prod_id = data.get("product_id")
        product = DatabaseManager.get_product_by_id(prod_id) if prod_id else None

        # 1. Product
        if not prod_id or not product:
            session["state"] = STATE_PRODUCT
            return STATE_PRODUCT, "Ajoyib! Qaysi mahsulotni buyurtma qilmoqchisiz? Mahsulot nomi yoki ID raqamini yozing:"

        # 2. Size
        if not data.get("size"):
            avail_sizes = cls.get_available_sizes(product)
            if len(avail_sizes) == 1:
                # Agar tovar faqat bitta o'lchamda bo'lsa, avtomatik biriktirib o'tkazish
                data["size"] = avail_sizes[0]
            else:
                session["state"] = STATE_SIZE
                return STATE_SIZE, f"Iltimos, o'lchamni (razmer) tanlang ({', '.join(avail_sizes)}):"

        # 3. Color
        if not data.get("color"):
            avail_colors = cls.get_available_colors(product)
            if len(avail_colors) == 1:
                # Agar tovar faqat bitta rangda bo'lsa, avtomatik biriktirib o'tkazish
                data["color"] = avail_colors[0]
            else:
                session["state"] = STATE_COLOR
                return STATE_COLOR, f"Iltimos, rangini tanlang ({', '.join(avail_colors)}):"

        # 4. Quantity
        if not data.get("quantity"):
            session["state"] = STATE_QUANTITY
            return STATE_QUANTITY, "Nechta buyurtma qilasiz? (Miqdorni kiriting, masalan: 1):"

        # 5. Name
        if not data.get("name"):
            session["state"] = STATE_NAME
            return STATE_NAME, "Buyurtma kimning nomiga rasmiylashtiriladi? Ismingizni yozib yuboring:"

        # 6. Phone
        if not data.get("phone"):
            session["state"] = STATE_PHONE
            return STATE_PHONE, "Bog'lanish uchun telefon raqamingizni yozib yuboring (masalan: +998901234567):"

        # 7. Address
        if not data.get("address"):
            session["state"] = STATE_ADDRESS
            return STATE_ADDRESS, "Yetkazib berish manzilini yozib yuboring (shahar, tuman, mahalla, ko'cha, uy):"

        # 8. All fields known -> Summary & Confirmation
        session["state"] = STATE_CONFIRM
        summary = cls.build_summary_message(data)
        return STATE_CONFIRM, summary

    # ---------------------------------------------------------
    # 8. Flow Lifecycle: Start, Process, Confirm
    # ---------------------------------------------------------
    @classmethod
    def start_order_flow(
        cls,
        chat_id: int,
        initial_product: Optional[Dict[str, Any]] = None,
        initial_text: str = "",
        crm_customer: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Buyurtma holat mashinasini ishga tushirish"""
        with _ORDER_FLOW_LOCK:
            now_iso = datetime.now().isoformat()
            data: Dict[str, Any] = {}

            # CRM va avvalgi xotiradan ma'lum bo'lgan maydonlarni yuklash (Skip known fields)
            if crm_customer:
                pref_name = crm_customer.get("preferred_name")
                full_name = crm_customer.get("full_name")
                if pref_name and pref_name.strip():
                    data["name"] = pref_name.strip()
                elif full_name and full_name.strip() and full_name != "Mijoz":
                    data["name"] = full_name.strip()

                phone = crm_customer.get("phone")
                if phone:
                    norm_phone = cls.validate_and_normalize_phone(phone)
                    if norm_phone:
                        data["phone"] = norm_phone

                address = crm_customer.get("address")
                if address and len(address.strip()) >= 3:
                    data["address"] = address.strip()

            # Mahsulotni biriktirish
            if initial_product:
                data["product_id"] = initial_product["id"]
                data["product_name"] = initial_product.get("name")
                data["unit_price"] = initial_product.get("sale_price") or initial_product.get("price") or 0.0

            # Boshlang'ich matndan maydonlarni intellektual ajratib olish
            if initial_text:
                t_low = initial_text.lower()
                # Miqdor
                for w, num in [("bitta", 1), ("ikkita", 2), ("uchta", 3), ("to'rtta", 4), ("beshta", 5)]:
                    if w in t_low:
                        data["quantity"] = num
                        break
                if not data.get("quantity"):
                    m_qty = re.search(r"\b(\d+)\s*(?:ta|dona)\b", t_low)
                    if m_qty:
                        data["quantity"] = int(m_qty.group(1))

                # O'lcham
                if initial_product:
                    for s in cls.get_available_sizes(initial_product):
                        if re.search(r"\b" + re.escape(s.lower()) + r"\b", t_low):
                            data["size"] = s
                            break

                # Rang
                if initial_product:
                    for c in cls.get_available_colors(initial_product):
                        if re.search(r"\b" + re.escape(c.lower()) + r"\b", t_low):
                            data["color"] = c
                            break

            session = {
                "chat_id": chat_id,
                "state": STATE_PRODUCT,
                "data": data,
                "editing_field": None,
                "is_confirmed": False,
                "order_id": None,
                "created_at": now_iso,
                "updated_at": now_iso
            }

            next_state, prompt = cls._get_next_field_prompt(session)
            cls._save_session(session)

            return {
                "reply": prompt,
                "state": next_state,
                "is_completed": False,
                "order_id": None
            }

    @classmethod
    def process_step(
        cls,
        chat_id: int,
        text: str,
        user_name: str = "",
        crm_customer: Optional[Dict[str, Any]] = None,
        ai_answer_fn = None
    ) -> Dict[str, Any]:
        """
        Har bir kiruvchi xabarni oqim bo'yicha qayta ishlash.
        Faqat bitta maydonni so'raydi, xatolarni muloyim tushuntiradi,
        savollarga javob berib oqimni davom ettiradi.
        """
        with _ORDER_FLOW_LOCK:
            session = cls.get_session(chat_id)
            if not session:
                return {"reply": "", "state": None, "is_completed": False}

            now_iso = datetime.now().isoformat()
            session["updated_at"] = now_iso
            state = session.get("state")
            data = session.setdefault("data", {})
            editing_field = session.get("editing_field")

            # -------------------------------------------------
            # A. Cancel mid-flow ("bekor qilish")
            # -------------------------------------------------
            if cls.is_cancel_intent(text):
                cls.clear_session(chat_id)
                return {
                    "reply": "❌ Buyurtmangiz bekor qilindi. Agar boshqa biror narsa kerak bo'lsa, bemalol murojaat qiling! 😊",
                    "state": None,
                    "is_completed": False
                }

            # -------------------------------------------------
            # B. Edit field ("o'zgartirish")
            # -------------------------------------------------
            is_edit, target_field = cls.is_edit_intent(text)
            if is_edit:
                if target_field:
                    session["editing_field"] = target_field
                    field_prompts = {
                        STATE_PRODUCT: "Qaysi mahsulotni tanlamoqchisiz? Nomini yoki ID sini yozing:",
                        STATE_SIZE: f"Yangi o'lchamni tanlang:",
                        STATE_COLOR: f"Yangi rangni tanlang:",
                        STATE_QUANTITY: "Nechta buyurtma qilmoqchisiz? Yangi miqdorni kiriting:",
                        STATE_NAME: "Ismingizni qanday yozaylik? Yangi ismni kiriting:",
                        STATE_PHONE: "Yangi telefon raqamingizni kiriting (+998XXXXXXXXX):",
                        STATE_ADDRESS: "Yangi yetkazib berish manzilini yozib yuboring:"
                    }
                    prompt = field_prompts.get(target_field, "Yangi qiymatni kiriting:")
                    cls._save_session(session)
                    return {"reply": prompt, "state": f"edit_{target_field}", "is_completed": False}
                else:
                    return {
                        "reply": "Qaysi ma'lumotni o'zgartirmoqchisiz?\n• Mahsulot\n• O'lcham\n• Rang\n• Miqdor\n• Ism\n• Telefon\n• Manzil",
                        "state": "await_edit_field_choice",
                        "is_completed": False
                    }

            # -------------------------------------------------
            # C. Question mid-flow (Answer question, then resume)
            # -------------------------------------------------
            if cls.is_unrelated_question(text, state):
                # Savolga javob tayyorlash
                answer = "Ingichka va tuman bo'ylab yetkazib berish mutlaqo bepul va 1 kun ichida yetkaziladi."
                if ai_answer_fn:
                    try:
                        ai_ans = ai_answer_fn(text)
                        if ai_ans and len(ai_ans.strip()) > 5:
                            answer = ai_ans.strip()
                    except Exception:
                        pass

                # Joriy bosqich savolini qayta eslatish
                _, current_prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                reply = f"{answer}\n\n📝 **Buyurtmangizni davom ettiramiz:** {current_prompt}"
                return {"reply": reply, "state": state, "is_completed": False}

            # -------------------------------------------------
            # D. Handle Editing Specific Field
            # -------------------------------------------------
            if editing_field:
                prod_id = data.get("product_id")
                product = DatabaseManager.get_product_by_id(prod_id) if prod_id else None

                if editing_field == STATE_ADDRESS:
                    if len(text.strip()) < 3:
                        return {"reply": "Iltimos, manzilni to'liqroq yozib yuboring (shahar, tuman, mahalla, uy):", "state": "edit_address", "is_completed": False}
                    data["address"] = text.strip()
                elif editing_field == STATE_PHONE:
                    p = cls.validate_and_normalize_phone(text)
                    if not p:
                        return {"reply": "Iltimos, telefon raqamingizni to'g'ri formatda kiriting (masalan: +998901234567 yoki 90 123 45 67):", "state": "edit_phone", "is_completed": False}
                    data["phone"] = p
                elif editing_field == STATE_NAME:
                    data["name"] = text.strip()
                elif editing_field == STATE_QUANTITY:
                    ok, qty_val, err_msg = cls.validate_quantity(product, text)
                    if not ok:
                        return {"reply": err_msg or "Noto'g'ri miqdor.", "state": "edit_quantity", "is_completed": False}
                    data["quantity"] = qty_val
                elif editing_field == STATE_SIZE:
                    ok, s_val, avail = cls.validate_size(product, text)
                    if not ok:
                        return {"reply": f"Kechirasiz, ushbu mahsulotda '{text}' o'lchami mavjud emas. Mavjud o'lchamlar: {', '.join(avail)}. Qaysi birini tanlaysiz?", "state": "edit_size", "is_completed": False}
                    data["size"] = s_val
                elif editing_field == STATE_COLOR:
                    ok, c_val, avail = cls.validate_color(product, text)
                    if not ok:
                        return {"reply": f"Kechirasiz, ushbu mahsulotda '{text}' rangi mavjud emas. Mavjud ranglar: {', '.join(avail)}. Qaysi birini tanlaysiz?", "state": "edit_color", "is_completed": False}
                    data["color"] = c_val

                session["editing_field"] = None
                session["state"] = STATE_CONFIRM
                cls._save_session(session)
                summary = cls.build_summary_message(data)
                return {"reply": f"✅ Ma'lumot yangilandi!\n\n{summary}", "state": STATE_CONFIRM, "is_completed": False}

            # -------------------------------------------------
            # E. Normal State Machine Flow
            # -------------------------------------------------
            prod_id = data.get("product_id")
            product = DatabaseManager.get_product_by_id(prod_id) if prod_id else None

            # 1. State: Product
            if state == STATE_PRODUCT:
                from services.order_matcher import OrderMatcher
                matched = OrderMatcher.match_product(text)
                if not matched:
                    return {
                        "reply": "Kechirasiz, ushbu nom bo'yicha mahsulot topilmadi. Iltimos, mahsulot nomi yoki ID raqamini aniqroq yozing:",
                        "state": STATE_PRODUCT,
                        "is_completed": False
                    }
                if matched.get("stock_quantity", 0) <= 0:
                    return {
                        "reply": f"Kechirasiz, '{matched['name']}' hozirda sotib bo'lingan. Boshqa mahsulot tanlaysizmi?",
                        "state": STATE_PRODUCT,
                        "is_completed": False
                    }
                data["product_id"] = matched["id"]
                data["product_name"] = matched["name"]
                data["unit_price"] = matched.get("sale_price") or matched.get("price") or 0.0
                next_state, prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                return {"reply": prompt, "state": next_state, "is_completed": False}

            # 2. State: Size
            elif state == STATE_SIZE:
                ok, s_val, avail = cls.validate_size(product, text)
                if not ok:
                    return {
                        "reply": f"Kechirasiz, ushbu mahsulotda '{text}' o'lchami mavjud emas. Mavjud o'lchamlar: {', '.join(avail)}. Iltimos, mavjud o'lchamlardan birini tanlang:",
                        "state": STATE_SIZE,
                        "is_completed": False
                    }
                data["size"] = s_val
                next_state, prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                return {"reply": prompt, "state": next_state, "is_completed": False}

            # 3. State: Color
            elif state == STATE_COLOR:
                ok, c_val, avail = cls.validate_color(product, text)
                if not ok:
                    return {
                        "reply": f"Kechirasiz, ushbu mahsulotda '{text}' rangi mavjud emas. Mavjud ranglar: {', '.join(avail)}. Iltimos, mavjud ranglardan birini tanlang:",
                        "state": STATE_COLOR,
                        "is_completed": False
                    }
                data["color"] = c_val
                next_state, prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                return {"reply": prompt, "state": next_state, "is_completed": False}

            # 4. State: Quantity
            elif state == STATE_QUANTITY:
                ok, qty_val, err_msg = cls.validate_quantity(product, text)
                if not ok:
                    return {
                        "reply": err_msg or "Iltimos, mahsulot miqdorini musbat raqamda kiriting (masalan: 1 yoki 2):",
                        "state": STATE_QUANTITY,
                        "is_completed": False
                    }
                data["quantity"] = qty_val
                next_state, prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                return {"reply": prompt, "state": next_state, "is_completed": False}

            # 5. State: Name
            elif state == STATE_NAME:
                name_clean = text.strip()
                if len(name_clean) < 2 or name_clean.isdigit():
                    return {
                        "reply": "Iltimos, ismingizni to'liqroq yozib yuboring:",
                        "state": STATE_NAME,
                        "is_completed": False
                    }
                data["name"] = name_clean.capitalize()
                next_state, prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                return {"reply": prompt, "state": next_state, "is_completed": False}

            # 6. State: Phone
            elif state == STATE_PHONE:
                norm_phone = cls.validate_and_normalize_phone(text)
                if not norm_phone:
                    return {
                        "reply": "Iltimos, telefon raqamingizni to'g'ri formatda kiriting (masalan: +998901234567 yoki 90 123 45 67):",
                        "state": STATE_PHONE,
                        "is_completed": False
                    }
                data["phone"] = norm_phone
                next_state, prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                return {"reply": prompt, "state": next_state, "is_completed": False}

            # 7. State: Address
            elif state == STATE_ADDRESS:
                addr_clean = text.strip()
                if len(addr_clean) < 3:
                    return {
                        "reply": "Iltimos, yetkazib berish manzilini to'liqroq yozib yuboring (shahar, tuman, mahalla, uy):",
                        "state": STATE_ADDRESS,
                        "is_completed": False
                    }
                data["address"] = addr_clean
                next_state, prompt = cls._get_next_field_prompt(session)
                cls._save_session(session)
                return {"reply": prompt, "state": next_state, "is_completed": False}

            # 8. State: Confirm
            elif state in [STATE_SUMMARY, STATE_CONFIRM]:
                t_low = text.lower().strip()
                confirm_words = ["ha", "tasdiqlayman", "xa", "tasdiq", "yes", "albatta", "ha tasdiqlayman", "ok", "mayli", "buyurtma qilaman"]

                # Dublikat / allaqachon tasdiqlangan tekshiruvi (Idempotency)
                if session.get("is_confirmed") or session.get("order_id"):
                    ord_id = session.get("order_id")
                    return {
                        "reply": f"Buyurtmangiz allaqachon qabul qilingan (#{ord_id}). Kuryerimiz tez orada siz bilan bog'lanadi! 😊",
                        "state": STATE_DONE,
                        "is_completed": True,
                        "order_id": ord_id
                    }

                if any(w == t_low or t_low.startswith(w) for w in confirm_words):
                    confirm_res = cls.confirm_order(chat_id, session)
                    return {
                        "reply": confirm_res["reply"],
                        "state": STATE_DONE,
                        "is_completed": True,
                        "order_id": confirm_res.get("order_id"),
                        "db_order_id": confirm_res.get("db_order_id"),
                        "admin_alert": confirm_res.get("admin_alert")
                    }
                else:
                    return {
                        "reply": "Buyurtmani tasdiqlash uchun **Ha** yoki **Tasdiqlayman** deb yozing.\nO'zgartirish uchun: **O'zgartirish**\nBekor qilish uchun: **Bekor qilish**",
                        "state": STATE_CONFIRM,
                        "is_completed": False
                    }

            # 9. State: Done
            elif state == STATE_DONE:
                ord_id = session.get("order_id")
                return {
                    "reply": f"Buyurtmangiz allaqachon qabul qilingan (#{ord_id}). Kuryerimiz tez orada siz bilan bog'lanadi! 😊",
                    "state": STATE_DONE,
                    "is_completed": True,
                    "order_id": ord_id
                }

            return {"reply": "Tushunarsiz buyruq.", "state": state, "is_completed": False}

    # ---------------------------------------------------------
    # 9. Confirm & Atomic Stock Decrement & Idempotency
    # ---------------------------------------------------------
    @classmethod
    def confirm_order(cls, chat_id: int, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Buyurtmani tasdiqlash:
        1. Idempotency kafolati: Ikkinchi marta bosilganda qayta zakaz yaratilmaydi va stock ikki marta kamaytirilmaydi.
        2. Formatlangan order_id yaratish (ORD-000123).
        3. Ombordagi qoldiqni atomik kamaytirish (SQLite + products.json).
        4. data/orders.json fayliga atomik yozish.
        5. Admin va xaridor xabarlarini tayyorlash.
        """
        with _ORDER_FLOW_LOCK:
            data = session.get("data", {})

            # Idempotency tekshiruvi
            if session.get("is_confirmed") or session.get("order_id"):
                existing_id = session.get("order_id")
                return {
                    "success": True,
                    "is_duplicate": True,
                    "order_id": existing_id,
                    "reply": f"Buyurtmangiz allaqachon qabul qilingan (#{existing_id}). Kuryerimiz tez orada siz bilan bog'lanadi! 😊"
                }

            prod_id = data.get("product_id")
            qty = int(data.get("quantity") or 1)
            name = data.get("name") or "Mijoz"
            phone = data.get("phone") or ""
            address = data.get("address") or ""
            unit_price = float(data.get("unit_price") or 0.0)
            total = qty * unit_price
            delivery_info = DEFAULT_DELIVERY_INFO

            # Order ID yaratish
            orders = cls._load_orders()
            formatted_order_id = f"ORD-{len(orders) + 1:06d}"

            # Ensure customer exists in customers table (Foreign key requirement)
            DatabaseManager.upsert_customer(
                telegram_id=chat_id,
                full_name=name,
                phone=phone,
                address=address
            )

            # SQLite da buyurtma yaratish va qoldiqni kamaytirish
            db_res = DatabaseManager.create_order(
                customer_telegram_id=chat_id,
                customer_name=name,
                customer_phone=phone,
                delivery_address=address,
                items=[{"product_id": prod_id, "quantity": qty}],
                payment_method="cash_on_delivery",
                notes=f"OrderFlow: {formatted_order_id} ({qty} dona)"
            )
            if not db_res.get("success"):
                return {
                    "success": False,
                    "error": db_res.get("error", "Ombor qoldig'i yetarli emas"),
                    "reply": f"Kechirasiz, buyurtmani rasmiylashtirishda xatolik yuz berdi: {db_res.get('error')}"
                }

            db_order_id = db_res["order_id"]

            # products.json da qoldiqni atomik kamaytirish (Rule 4)
            try:
                prods = load_products()
                for p in prods:
                    if p.get("id") == prod_id:
                        curr = p.get("stock", 0)
                        p["stock"] = max(0, curr - qty)
                        break
                atomic_write_json(str(PRODUCTS_FILE), prods, indent=2)
            except Exception:
                pass

            # data/orders.json ga saqlash (Rule 4: atomik)
            order_record = {
                "order_id": formatted_order_id,
                "db_order_id": db_order_id,
                "chat_id": chat_id,
                "customer_name": name,
                "customer_phone": phone,
                "delivery_address": address,
                "items": [
                    {
                        "product_id": prod_id,
                        "product_name": data.get("product_name"),
                        "size": data.get("size"),
                        "color": data.get("color"),
                        "quantity": qty,
                        "unit_price": unit_price,
                        "subtotal": total
                    }
                ],
                "total_amount": total,
                "payment_method": "cash_on_delivery",
                "delivery_info": delivery_info,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            orders.append(order_record)
            atomic_write_json(str(ORDERS_FILE), orders, indent=2)

            # Session holatini yangilash
            session["is_confirmed"] = True
            session["order_id"] = formatted_order_id
            session["db_order_id"] = db_order_id
            session["state"] = STATE_DONE
            session["updated_at"] = datetime.now().isoformat()
            cls._save_session(session)

            # Admin ogohlantirish xabari
            admin_alert = (
                f"🔔 **YANGI BUYURTMA #{formatted_order_id}!**\n\n"
                f"🛍️ **Mahsulot:** {data.get('product_name')}\n"
                f"📏 **O'lcham:** {data.get('size')} | **Rang:** {data.get('color')}\n"
                f"🔢 **Miqdor:** {qty} dona\n"
                f"💰 **Jami:** {total:,.0f} so'm\n\n"
                f"👤 **Mijoz:** {name} (ID: `{chat_id}`)\n"
                f"📱 **Tel:** {phone}\n"
                f"📍 **Manzil:** {address}\n"
                f"🚚 **Yetkazib berish:** Bepul (Ingichka)"
            )

            # Xaridorga tasdiq xabari
            customer_msg = (
                f"🎉 **Katta rahmat! Buyurtmangiz muvaffaqiyatli qabul qilindi!**\n\n"
                f"🧾 **Buyurtma raqami:** `{formatted_order_id}`\n"
                f"🛍️ **Mahsulot:** **{data.get('product_name')}** ({qty} dona)\n"
                f"💰 **Jami to'lov:** **{total:,.0f} so'm**\n"
                f"📍 **Yetkazish manzili:** {address}\n"
                f"📞 **Telefon:** `{phone}`\n\n"
                f"Kuryerimiz tez orada siz bilan bog'lanib, buyurtmani yetkazib beradi! Xaridingiz barakali bo'lsin! 😊"
            )

            return {
                "success": True,
                "is_duplicate": False,
                "order_id": formatted_order_id,
                "db_order_id": db_order_id,
                "reply": customer_msg,
                "admin_alert": admin_alert
            }
