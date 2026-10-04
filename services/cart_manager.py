"""
services/cart_manager.py
Jahon darajasidagi Interaktiv Savatcha (Shopping Cart) va Express Checkout tizimi.
Har bir mijoz uchun ko'p tovarli savatni boshqarish, miqdorni o'zgartirish va 1-bosishda buyurtma berish.
"""

import logging
from typing import Dict, Any, List, Optional
from database.db_manager import DatabaseManager
from services.catalog_service import load_products

logger = logging.getLogger(__name__)

class CartManager:
    """
    Foydalanuvchilarning savatchalari menejeri (In-Memory + Database integration).
    user_id -> {
        "items": {product_id: {"quantity": int, "size": str, "color": str}},
        "promo_code": Optional[str],
        "discount_percent": float,
        "discount_amount": float
    }
    """
    _carts: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def get_or_create_cart(cls, user_id: int) -> Dict[str, Any]:
        if user_id not in cls._carts:
            cls._carts[user_id] = {
                "items": {},
                "promo_code": None,
                "discount_percent": 0.0,
                "discount_amount": 0.0
            }
        return cls._carts[user_id]

    @classmethod
    def add_item(
        cls,
        user_id: int,
        product_id: int,
        quantity: int = 1,
        size: Optional[str] = None,
        color: Optional[str] = None
    ) -> Dict[str, Any]:
        """Savatga tovar qo'shish yoki miqdorini oshirish"""
        cart = cls.get_or_create_cart(user_id)
        prod = DatabaseManager.get_product_by_id(product_id)
        if not prod:
            return {"success": False, "message": "Mahsulot topilmadi!"}

        current_qty = cart["items"].get(product_id, {}).get("quantity", 0)
        new_qty = current_qty + quantity
        available_stock = prod.get("stock_quantity", 0)

        if new_qty > available_stock:
            return {
                "success": False,
                "message": f"Kechirasiz, omborda faqat {available_stock} dona mavjud!"
            }

        sel_size = size or prod.get("size", "Standart")
        sel_color = color or prod.get("color", "Standart")

        cart["items"][product_id] = {
            "product_id": product_id,
            "name": prod["name"],
            "price": float(prod["sale_price"]),
            "quantity": new_qty,
            "size": sel_size,
            "color": sel_color
        }

        return {
            "success": True,
            "message": f"'{prod['name']}' savatchaga qo'shildi!",
            "cart_count": cls.get_cart_item_count(user_id)
        }

    @classmethod
    def update_quantity(cls, user_id: int, product_id: int, delta: int) -> Dict[str, Any]:
        """Tovarning savatdagi sonini +1 yoki -1 ga o'zgartirish"""
        cart = cls.get_or_create_cart(user_id)
        if product_id not in cart["items"]:
            return {"success": False, "message": "Mahsulot savatda yo'q!"}

        item = cart["items"][product_id]
        new_qty = item["quantity"] + delta

        if new_qty <= 0:
            del cart["items"][product_id]
            return {"success": True, "action": "removed", "message": "Mahsulot savatdan olib tashlandi"}

        prod = DatabaseManager.get_product_by_id(product_id)
        available = prod.get("stock_quantity", 0) if prod else 99
        if new_qty > available:
            return {"success": False, "message": f"Omborda faqat {available} dona mavjud!"}

        item["quantity"] = new_qty
        return {"success": True, "action": "updated", "new_quantity": new_qty}

    @classmethod
    def remove_item(cls, user_id: int, product_id: int) -> bool:
        """Tovarni savatdan butunlay o'chirish"""
        cart = cls.get_or_create_cart(user_id)
        if product_id in cart["items"]:
            del cart["items"][product_id]
            return True
        return False

    @classmethod
    def clear_cart(cls, user_id: int):
        """Savatni tozalash"""
        if user_id in cls._carts:
            cls._carts[user_id] = {
                "items": {},
                "promo_code": None,
                "discount_percent": 0.0,
                "discount_amount": 0.0
            }

    @classmethod
    def get_cart_item_count(cls, user_id: int) -> int:
        """Savatdagi jami tovarlar soni"""
        cart = cls._carts.get(user_id)
        if not cart:
            return 0
        return sum(item["quantity"] for item in cart["items"].values())

    @classmethod
    def apply_promo(cls, user_id: int, promo_code: str, discount_percent: float = 0.0, discount_amount: float = 0.0) -> Dict[str, Any]:
        """Savatga promokod qo'llash"""
        clean_code = promo_code.upper().strip()
        cart = cls.get_or_create_cart(user_id)
        
        if discount_percent == 0.0 and discount_amount == 0.0:
            from services.promo_manager import PromoManager
            val_res = PromoManager.validate_code(clean_code)
            if not val_res.get("valid"):
                return {"success": False, "message": val_res.get("message", "Promokod yaroqsiz.")}
            discount_percent = float(val_res.get("percent", 0.0))
            discount_amount = float(val_res.get("amount", 0.0))

        cart["promo_code"] = clean_code
        cart["discount_percent"] = discount_percent
        cart["discount_amount"] = discount_amount
        return {"success": True, "promo_code": cart["promo_code"], "percent": discount_percent, "amount": discount_amount}

    @classmethod
    def remove_promo(cls, user_id: int):
        cart = cls.get_or_create_cart(user_id)
        cart["promo_code"] = None
        cart["discount_percent"] = 0.0
        cart["discount_amount"] = 0.0

    @classmethod
    def get_cart_summary(cls, user_id: int) -> Dict[str, Any]:
        """Savat tafsilotlari, tovarlar ro'yxati va hisob-kitob"""
        cart = cls.get_or_create_cart(user_id)
        items_list = list(cart["items"].values())

        raw_total = sum(item["price"] * item["quantity"] for item in items_list)
        discount_val = 0.0

        if cart["discount_percent"] > 0:
            discount_val += raw_total * (cart["discount_percent"] / 100.0)
        if cart["discount_amount"] > 0:
            discount_val += cart["discount_amount"]

        # Chegirma umumiy summadan oshib ketmasligi kerak
        discount_val = min(discount_val, raw_total)
        final_total = max(0.0, raw_total - discount_val)

        # 300,000 so'mdan oshsa yetkazib berish bepul
        free_delivery = final_total >= 300_000

        return {
            "items": items_list,
            "total_items": sum(i["quantity"] for i in items_list),
            "raw_total": raw_total,
            "discount_val": discount_val,
            "promo_code": cart["promo_code"],
            "final_total": final_total,
            "free_delivery": free_delivery
        }

    @classmethod
    def format_cart_message(cls, user_id: int) -> str:
        """Xaridorga ko'rsatiladigan chiroyli, premium savatcha xabari"""
        summary = cls.get_cart_summary(user_id)
        items = summary["items"]

        if not items:
            return (
                "🛒 **Sizning savatchangiz bo'sh!**\n\n"
                "Do'konimiz katalogidan o'zingizga yoqqan kiyim va buyumlarni tanlab, "
                "savatchaga qo'shishingiz mumkin.\n\n"
                "👇 Katalogga o'tish uchun quyidagi tugmani bosing:"
            )

        lines = ["🛒 **SIZNING SAVATCHANGIZ:**\n"]
        for idx, item in enumerate(items, 1):
            sub = item["price"] * item["quantity"]
            lines.append(
                f"**{idx}. {item['name']}**\n"
                f"   • O'lcham: `{item['size']}` | Rang: `{item['color']}`\n"
                f"   • {item['quantity']} dona x {item['price']:,.0f} = **{sub:,.0f} so'm**\n"
            )

        lines.append("─────────────────────────")
        lines.append(f"📦 Jami tovarlar: **{summary['total_items']} dona**")
        lines.append(f"💵 Tovar qiymati: **{summary['raw_total']:,.0f} so'm**")

        if summary["discount_val"] > 0:
            promo = summary['promo_code'] or 'Aksiya'
            lines.append(f"🎁 Chegirma ({promo}): **-{summary['discount_val']:,.0f} so'm**")

        lines.append(f"💰 **JAMI TO'LOV: {summary['final_total']:,.0f} so'm**")

        if summary["free_delivery"]:
            lines.append("🚚 Yetkazib berish: **MUTLAQO BEPUL! (300k+ sovg'asi)** 🎉")
        else:
            diff = 300_000 - summary['final_total']
            lines.append(f"💡 *Yana {diff:,.0f} so'mlik xarid qilsangiz, yetkazib berish bepul bo'ladi!*")

        lines.append("\nBuyurtmani rasmiylashtirish uchun pastdagi **🛍 Buyurtma berish** tugmasini bosing:")
        return "\n".join(lines)
