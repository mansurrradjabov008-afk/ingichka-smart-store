"""
services/stock_advisor.py
Task 2 Requirements 3 & 4 (Stock rules in CODE):
3. If stock = 0 the bot says it is sold out, offers the closest in-stock alternative,
   and asks "Kelganda xabar beraymi?". If yes, save {chat_id, product_id, created_at}
   to data/waitlist.json (no duplicates).
4. If the customer wants more units than stock, say the exact available number from data.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from database.db_manager import DatabaseManager
from services.catalog_service import load_products
from services.waitlist_service import WaitlistService

# chat_id -> product_id kutayotgan tovar IDsi
PENDING_WAITLIST_OFFERS: Dict[int, int] = {}

UZBEK_NUMBER_WORDS = {
    "bitta": 1, "bir": 1,
    "ikkita": 2, "ikki": 2,
    "uchta": 3, "uch": 3,
    "to'rtta": 4, "to‘rtta": 4, "tortta": 4, "to'rt": 4,
    "beshta": 5, "besh": 5,
    "oltita": 6, "olti": 6,
    "yettita": 7, "yetti": 7,
    "sakkizta": 8, "sakkiz": 8,
    "to'qqizta": 9, "to‘qqizta": 9, "toqqizta": 9, "to'qqiz": 9,
    "o'nta": 10, "o‘nta": 10, "onta": 10, "o'n": 10,
    "yigirmata": 20, "yigirma": 20
}

class StockAdvisor:
    """Ombor qoldiqlari bo'yicha deterministik qoidalar (Rule 6, Rule 10, Task 2)"""

    @classmethod
    def extract_requested_quantity(cls, text: str) -> Optional[int]:
        """Matndan so'ralgan tovar miqdorini ajratib olish (masalan: 5 ta, 10 dona, ikkita)"""
        t_low = text.lower()
        
        # 1. Raqam bilan: "5 ta", "10 dona", "3ta"
        digit_match = re.search(r"\b(\d+)\s*(?:ta|dona|shtuk|xil)?\b", t_low)
        if digit_match:
            try:
                num = int(digit_match.group(1))
                if 1 <= num <= 1000:
                    return num
            except ValueError:
                pass

        # 2. So'z bilan: "ikkita", "beshta", "o'nta"
        for word, val in UZBEK_NUMBER_WORDS.items():
            if re.search(r"\b" + re.escape(word) + r"\b", t_low):
                return val

        return None

    @classmethod
    def find_in_stock_alternative(cls, category: str, exclude_id: int) -> Optional[Dict[str, Any]]:
        """Aynan shu toifadagi eng yaqin omborda bor (stock > 0) toparni topish"""
        all_prods = DatabaseManager.get_products(in_stock_only=True)
        # 1. Shu kategoriyadagi
        for p in all_prods:
            if p["id"] != exclude_id and p.get("category", "").lower() == category.lower() and p.get("stock_quantity", 0) > 0:
                return p
        # 2. Agar kategoriya bo'yicha qolmagan bo'lsa, istalgan ombordagi tovar
        for p in all_prods:
            if p["id"] != exclude_id and p.get("stock_quantity", 0) > 0:
                return p
        return None

    @classmethod
    def evaluate_stock_rules(cls, text: str, matched_product: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Stock qoidalarini tekshirish:
        - Agar stock = 0: "sotib bo'lingan" deb muqobil taklif qiladi va "Kelganda xabar beraymi?" deb so'raydi.
        - Agar so'ralgan son > stock: aniq mavjud sonni aytadi.
        """
        if not matched_product:
            return None

        pid = matched_product["id"]
        # DatabaseManager dan eng yangi stockni olish
        db_prod = DatabaseManager.get_product_by_id(pid) or matched_product
        current_stock = db_prod.get("stock_quantity", db_prod.get("stock", 0))
        p_name = db_prod.get("name", "Ushbu mahsulot")
        p_cat = db_prod.get("category", "")

        # 1. Stock = 0 (Sold out) qoidasi
        if current_stock <= 0:
            alt = cls.find_in_stock_alternative(category=p_cat, exclude_id=pid)
            alt_text = ""
            if alt:
                alt_price = alt.get("sale_price") or alt.get("price", 0)
                alt_text = f" Sizga eng yaqin muqobil sifatida **'{alt['name']}'** ({alt_price:,.0f} so'm) mahsulotimizni taklif qila olaman."

            reply = f"Afsuski, **{p_name}** hozirda sotib bo'lingan (tugagan).{alt_text}\n\nKelganda xabar beraymi?"
            return {
                "type": "sold_out",
                "product": db_prod,
                "alternative": alt,
                "reply": reply,
                "product_id": pid
            }

        # 2. So'ralgan miqdor mavjud stockdan ko'p bo'lsa (Quantity above stock)
        req_qty = cls.extract_requested_quantity(text)
        if req_qty and req_qty > current_stock:
            reply = f"Kechirasiz, **{p_name}** mahsulotimizdan omborda faqat **{current_stock} dona** mavjud."
            return {
                "type": "quantity_above_stock",
                "product": db_prod,
                "available_stock": current_stock,
                "requested_qty": req_qty,
                "reply": reply,
                "product_id": pid
            }

        return None

    @classmethod
    def handle_waitlist_confirmation(cls, chat_id: int, text: str) -> Optional[str]:
        """
        Foydalanuvchi "Kelganda xabar beraymi?" savoliga ijobiy javob berganida
        data/waitlist.json ga saqlash (dublikatsiz).
        """
        if chat_id not in PENDING_WAITLIST_OFFERS:
            return None

        t_low = text.lower().strip()
        positive_answers = [
            "ha", "xa", "ha albatta", "mayli", "xabar bering", "xabar qiling",
            "ayting", "ok", "yaxshi", "kutaman", "albatta", "ha xabar", "ha mayli"
        ]

        # Foydalanuvchi rozilik bildirdimi?
        is_yes = any(re.search(r"\b" + re.escape(w) + r"\b", t_low) for w in positive_answers)
        if is_yes:
            pid = PENDING_WAITLIST_OFFERS.pop(chat_id)
            added = WaitlistService.add_to_waitlist(chat_id=chat_id, product_id=pid)
            if added:
                return "Kelishi bilan sizga darhol xabar beramiz! Rahmat 😊"
            else:
                return "Siz allaqachon ushbu tovar uchun navbatdasiz. Kelishi bilan xabar beramiz! 😊"

        # Agar rad javobi berilgan bo'lsa
        negative_answers = ["yo'q", "yoq", "kerak emas", "shart emas", "kutmayman"]
        is_no = any(w in t_low for w in negative_answers)
        if is_no:
            PENDING_WAITLIST_OFFERS.pop(chat_id, None)
            return "Tushundim. Boshqa qanday tovar qidiryapsiz? Sizga yordam berishdan xursandman 😊"

        return None
