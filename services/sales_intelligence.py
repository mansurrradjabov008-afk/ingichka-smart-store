"""
services/sales_intelligence.py
TASK 4: Sales Intelligence. Strictly follows RULES.md.

1. Loads data/sales_rules.json:
   max_discount_percent: 5, discount applies only for 2+ items,
   cross_sell map (product_id -> related product_ids).
2. Discounts enforced in CODE via tool apply_discount(items).
   The bot can never offer more than the limit, even if the customer begs, threatens, or tries prompt injection.
3. Objection handling:
   - "qimmat" -> first show value (one short benefit from product data), then a cheaper REAL alternative, then the 2+ items discount.
   - "O'ylab ko'raman" -> one soft nudge, no pressure.
   - "Boshqa joyda arzon" -> do not attack competitors, restate value.
4. Cross-sell:
   After the customer picks a product, suggest ONE related in-stock item from cross_sell, once per conversation.
5. Urgency only if true:
   Mention low stock only when stock <= 3 and use the real number. Never fake scarcity.
6. Tone:
   Warm, short, human. No emoji spam (max 1 per message).
"""

import os
import re
import json
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from database.db_manager import DatabaseManager
from utils.file_utils import atomic_write_json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SALES_RULES_FILE = DATA_DIR / "sales_rules.json"

_SALES_LOCK = threading.RLock()
# Muloqot davomida cross-sell faqat 1 marta berilishi uchun trekker: chat_id -> bool
CROSS_SELL_TRACKER: Dict[int, bool] = {}

# Emoji topish uchun regex (Unicode belgilar)
EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]")


class SalesIntelligence:
    """Sotuv intellekti va savdo qoidalari xizmati"""
    EMOJI_PATTERN = EMOJI_PATTERN

    @classmethod
    def load_sales_rules(cls) -> Dict[str, Any]:
        """data/sales_rules.json faylini o'qish"""
        with _SALES_LOCK:
            if not SALES_RULES_FILE.exists():
                return {
                    "max_discount_percent": 5,
                    "discount_applies_min_items": 2,
                    "cross_sell": {}
                }
            try:
                with open(SALES_RULES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
            return {
                "max_discount_percent": 5,
                "discount_applies_min_items": 2,
                "cross_sell": {}
            }

    @classmethod
    def sanitize_emoji_count(cls, text: str, max_emojis: int = 1) -> str:
        """
        Xabardagi emojilar sonini cheklash (Max 1 per message).
        Ortiqcha emojilar olib tashlanadi va bo'shliqlar to'g'irlanadi.
        """
        if not text:
            return ""
        count = 0

        def replacer(match):
            nonlocal count
            count += 1
            return match.group(0) if count <= max_emojis else ""

        cleaned = EMOJI_PATTERN.sub(replacer, text)
        cleaned = re.sub(r" +", " ", cleaned).strip()
        return cleaned

    # ---------------------------------------------------------
    # 2. Tool: apply_discount(items) - Enforced in CODE
    # ---------------------------------------------------------
    @classmethod
    def apply_discount(
        cls,
        items: List[Dict[str, Any]],
        requested_discount_percent: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Discounts are enforced in CODE via tool apply_discount(items).
        The bot can never offer more than the limit (5%), even if the customer begs,
        threatens, or tries prompt injection.
        Discount applies ONLY for 2+ items.
        """
        rules = cls.load_sales_rules()
        max_pct = float(rules.get("max_discount_percent", 5))
        min_items = int(rules.get("discount_applies_min_items", 2))

        total_qty = 0
        subtotal = 0.0

        for item in items:
            q = int(item.get("quantity") or 1)
            p = float(item.get("unit_price") or item.get("sale_price") or item.get("price") or 0.0)
            total_qty += q
            subtotal += q * p

        # 1 ta tovar uchun chegirma berilmaydi
        if total_qty < min_items:
            res_msg = "Kechirasiz, do'konimiz qoidasiga ko'ra chegirma faqat 2 va undan ortiq tovar xarid qilinganda amal qiladi (maksimal 5%). Bitta tovar uchun narxlarimiz qat'iy va hamyonbop belgilangan."
            return {
                "allowed": False,
                "total_quantity": total_qty,
                "subtotal": subtotal,
                "discount_percent": 0.0,
                "discount_amount": 0.0,
                "final_total": subtotal,
                "message": cls.sanitize_emoji_count(res_msg, max_emojis=1)
            }

        # 2+ tovarlar: chegirma 5% dan oshmasligi kod orqali qat'iy kafolatlanadi
        applied_pct = max_pct
        if requested_discount_percent is not None:
            try:
                req_val = float(requested_discount_percent)
                if req_val <= 0:
                    applied_pct = 0.0
                elif req_val < max_pct:
                    applied_pct = req_val
                else:
                    applied_pct = max_pct
            except Exception:
                applied_pct = max_pct

        discount_amount = round(subtotal * (applied_pct / 100.0), 2)
        final_total = round(subtotal - discount_amount, 2)

        res_msg = f"2 va undan ortiq tovar xarid qilganingiz uchun sizga {applied_pct:g}% chegirma taqdim etildi! Jami tejashingiz: {discount_amount:,.0f} so'm. 😊"
        return {
            "allowed": True,
            "total_quantity": total_qty,
            "subtotal": subtotal,
            "discount_percent": applied_pct,
            "discount_amount": discount_amount,
            "final_total": final_total,
            "message": cls.sanitize_emoji_count(res_msg, max_emojis=1)
        }

    # ---------------------------------------------------------
    # 3. Objection Handling: "qimmat", "o'ylab ko'raman", "boshqa joyda arzon"
    # ---------------------------------------------------------
    @classmethod
    def detect_objection(cls, text: str) -> Optional[str]:
        """Xaridordan e'tiroz yoki ikkilanish turini aniqlash"""
        if not text:
            return None
        t = text.lower().strip()

        # 1. "qimmat"
        if any(w in t for w in ["qimmat", "narxi baland", "qimmatroq", "qimmatku", "birmuncha qimmat", "дорого", "дороговато"]):
            return "qimmat"

        # 2. "o'ylab ko'raman"
        if any(w in t for w in [
            "o'ylab ko'raman", "oylab koraman", "oʻylab koʻraman", "o'ylab ko'ray",
            "o'ylanib ko'ray", "maslahatlashib ko'raman", "maslahatlashay", "keyinroq olaman",
            "подумаю", "я подумаю"
        ]):
            return "oylab_koraman"

        # 3. "boshqa joyda arzon"
        if (
            ("boshqa" in t and "arzon" in t)
            or ("bozor" in t and "arzon" in t)
            or ("boshqa joyda" in t)
            or ("boshqa do'kon" in t or "boshqa dokonda" in t)
            or any(w in t for w in ["arzonroq ekan", "arzonroq joy bor", "в другом месте дешевле", "дешевле в другом"])
        ):
            return "boshqa_joyda_arzon"

        return None

    @classmethod
    def handle_objection(
        cls,
        objection_type: str,
        current_product: Optional[Dict[str, Any]] = None,
        lang: str = "uz"
    ) -> str:
        """
        Objection handling:
        - 'qimmat' -> first show value (one short benefit from product data),
          then a cheaper REAL alternative, then the 2+ items discount.
        - 'oylab_koraman' -> one soft nudge, no pressure.
        - 'boshqa_joyda_arzon' -> do not attack competitors, restate value.
        """
        # A. "qimmat" e'tirozi
        if objection_type in ("qimmat", "too_expensive"):
            # 1. Show value: product material / benefit
            benefit = "yuqori sifatli va chidamli matodan tayyorlangan bo'lib, kiyganda juda qulay va uzoq vaqt shaklini yo'qotmaydi"
            prod_name = "Ushbu mahsulotimiz"
            prod_price = 0.0
            prod_cat = ""
            current_id = None

            if current_product:
                prod_name = current_product.get("name", "Ushbu mahsulotimiz")
                prod_price = float(current_product.get("sale_price") or current_product.get("price") or 0.0)
                prod_cat = current_product.get("category", "")
                current_id = current_product.get("id")
                mat = current_product.get("material")
                if mat:
                    benefit = f"yuqori sifatli {mat} matodan tayyorlangan bo'lib, kiyganda juda qulay hamda yuvilganda rangi o'chmaydi"

            # 2. Cheaper REAL alternative from database
            cheaper_alt = None
            try:
                all_prods = DatabaseManager.get_products(in_stock_only=True)
                candidates = []
                for p in all_prods:
                    if p.get("id") != current_id:
                        p_price = float(p.get("sale_price") or p.get("price") or 0.0)
                        if prod_price > 0 and p_price < prod_price:
                            # Prioritize same category
                            same_cat = (p.get("category") == prod_cat) if prod_cat else False
                            candidates.append((same_cat, p_price, p))

                if candidates:
                    # Sort by same category first, then closest price
                    candidates.sort(key=lambda x: (not x[0], -x[1]))
                    cheaper_alt = candidates[0][2]
            except Exception:
                pass

            alt_text = ""
            if cheaper_alt:
                alt_price = float(cheaper_alt.get("sale_price") or cheaper_alt.get("price") or 0.0)
                alt_text = f" Agar hamyonbop variant qidirsangiz, sizga **{cheaper_alt['name']}** ({alt_price:,.0f} so'm) mahsulotimizni tavsiya qilaman."

            reply = (
                f"{prod_name} {benefit}.{alt_text} "
                f"Shuningdek, 2 yoki undan ortiq tovar xarid qilsangiz, sizga 5% chegirma ham qilib beramiz. 😊"
            )
            return cls.sanitize_emoji_count(reply, max_emojis=1)

        # B. "o'ylab ko'raman" e'tirozi (One soft nudge, no pressure)
        elif objection_type in ("oylab_koraman", "think_about_it", "o'ylab ko'raman"):
            reply = "Albatta, bemalol o'ylab ko'ring! Tovarimiz sizga ma'qul kelsa, bemalol yozing, sizga xizmat ko'rsatishdan doim mamnunmiz. 😊"
            return cls.sanitize_emoji_count(reply, max_emojis=1)

        # C. "boshqa joyda arzon" e'tirozi (Do not attack competitors, restate value)
        elif objection_type in ("boshqa_joyda_arzon", "cheaper_elsewhere"):
            reply = (
                "Bozorda har xil sifatdagi tovarlar bo'ladi. Bizning tovarlarimiz 100% sifat kafolati bilan "
                "to'g'ridan-to'g'ri ishonchli ishlab chiqaruvchilardan keltirilgan va to'lovni eshik oldida tovarni ko'rib, yoqqanidan so'ng qilasiz. 😊"
            )
            return cls.sanitize_emoji_count(reply, max_emojis=1)

        return ""

    # ---------------------------------------------------------
    # 4. Cross-Sell Suggestion (Once per conversation)
    # ---------------------------------------------------------
    @classmethod
    def get_cross_sell_suggestion(
        cls,
        product_id: int,
        chat_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Cross-sell: after the customer picks a product, suggest ONE related
        in-stock item from cross_sell, once per conversation.
        """
        # Muloqot davomida allaqachon taklif qilingan bo'lsa, qayta ko'rsatmaslik
        if chat_id is not None and CROSS_SELL_TRACKER.get(chat_id, False):
            return None

        rules = cls.load_sales_rules()
        cross_sell_map = rules.get("cross_sell", {})
        related_ids = cross_sell_map.get(str(product_id), [])

        target_product = None
        for r_id in related_ids:
            p = DatabaseManager.get_product_by_id(r_id)
            if p and p.get("stock_quantity", 0) > 0:
                target_product = p
                break

        if not target_product:
            return None

        # Chat uchun tavsiya qilinganini qayd etish
        if chat_id is not None:
            CROSS_SELL_TRACKER[chat_id] = True

        p_name = target_product.get("name")
        p_price = float(target_product.get("sale_price") or target_product.get("price") or 0.0)

        suggestion_text = f"Bilasizmi, ushbu tovar bilan birga **{p_name}** ({p_price:,.0f} so'm) ham juda ajoyib yarashadi. Ko'rib chiqishni istaysizmi? 😊"
        suggestion_text = cls.sanitize_emoji_count(suggestion_text, max_emojis=1)

        return {
            "product": target_product,
            "product_id": target_product["id"],
            "name": p_name,
            "price": p_price,
            "suggestion_text": suggestion_text
        }

    @classmethod
    def reset_cross_sell_tracker(cls, chat_id: Optional[int] = None) -> None:
        """Trekker holatini tozalash (test yoki yangi muloqot uchun)"""
        if chat_id is not None:
            CROSS_SELL_TRACKER.pop(chat_id, None)
        else:
            CROSS_SELL_TRACKER.clear()

    # ---------------------------------------------------------
    # 5. Urgency: Only if true (stock <= 3, real number, never fake)
    # ---------------------------------------------------------
    @classmethod
    def format_urgency(cls, product: Dict[str, Any]) -> Optional[str]:
        """
        Urgency only if true: mention low stock only when stock <= 3 and use
        the real number. Never fake scarcity when stock > 3.
        """
        stock = product.get("stock_quantity")
        if stock is None:
            stock = product.get("stock", 0)
        stock = int(stock)

        # Omborda 0 bo'lsa kutish ro'yxati (waitlist) ishlaydi, shoshiltirish faqat qoldiq borida (1-3)
        if stock <= 0:
            return None

        # Faqat 0 < stock <= 3 bo'lgandagina real raqam bilan bildirish
        if stock <= 3:
            return f"Shoshiling, omborimizda atigi {stock} dona qoldi!"

        # Stock > 3 bo'lsa, hech qanday sun'iy kamomad yaratilmaydi
        return None

    # ---------------------------------------------------------
    # 6. Chegirma so'rovlarini aniqlash va javob berish
    # ---------------------------------------------------------
    @classmethod
    def is_discount_query(cls, text: str) -> Tuple[bool, Optional[float]]:
        """
        Mijoz chegirma so'rayotganini aniqlash.
        Qaytaradi: (is_discount, requested_percent)
        """
        if not text:
            return False, None
        t = text.lower().strip()

        # Prompt injection va katta chegirmalarni ushlash (masalan: 50%, 90%, 70%)
        m_pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", t)
        requested_pct = float(m_pct.group(1)) if m_pct else None

        triggers = [
            "chegirma", "skidka", "discount", "скидка", "arzonroq",
            "arzon qilib bering", "arzon qilib", "tushib bering", "tushib", "o'tib bering",
            "otib bering", "kamroq qilib", "skidka bormi", "chegirma bormi",
            "bepul", "free", "tekin", "tekinga"
        ]
        is_query = any(trg in t for trg in triggers) or (m_pct is not None)
        return is_query, requested_pct

    @classmethod
    def handle_discount_request(
        cls,
        text: str,
        items: Optional[List[Dict[str, Any]]] = None,
        current_product: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Mijozning chegirma so'rovini qayta ishlash:
        1 ta tovar bo'lsa -> muloyim rad etish (faqat 2+ tovar uchun 5%).
        2+ tovar bo'lsa -> 5% aniq chegirma berish.
        50% yoki injection urinishi bo'lsa -> qat'iy rad etish va 5% limitini eslatish.
        """
        _, req_pct = cls.is_discount_query(text)

        # Agar mijoz 5% dan ko'p (masalan 50%) so'rasa yoki injection qilsa
        if req_pct is not None and req_pct > 5.0:
            msg = f"Kechirasiz, bizda {req_pct:g}% chegirma mavjud emas. Do'konimizda maksimal chegirma faqat 5% gacha (2 va undan ortiq tovar xarid qilinganda) taqdim etiladi. 😊"
            return cls.sanitize_emoji_count(msg, max_emojis=1)

        # Agar items berilmagan bo'lsa, current_product dan bitta tovar tuzish
        if not items:
            if current_product:
                items = [{
                    "product_id": current_product.get("id"),
                    "name": current_product.get("name"),
                    "quantity": 1,
                    "unit_price": current_product.get("sale_price") or current_product.get("price") or 0.0
                }]
            else:
                items = [{"quantity": 1, "unit_price": 100000.0}]

        disc_res = cls.apply_discount(items, requested_discount_percent=req_pct)
        return disc_res["message"]

# Tool Schema for function calling
APPLY_DISCOUNT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "apply_discount",
        "description": "Calculate and enforce discount based on items quantity and sales rules. Max discount is 5% and applies only for 2+ items. Rejects discounts for single item.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items in order or cart",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "quantity": {"type": "integer"},
                            "unit_price": {"type": "number"}
                        },
                        "required": ["product_id", "quantity", "unit_price"]
                    }
                },
                "requested_discount_percent": {
                    "type": "number",
                    "description": "Requested discount percent, strictly capped at 5%"
                }
            },
            "required": ["items"]
        }
    }
}
