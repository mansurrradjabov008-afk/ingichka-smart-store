"""
services/loyalty_service.py
Enterprise VIP Loyalty & Cashback Engine (Shopify / Klarna style).
Features:
- Tiered VIP Status: Bronza (2%), Kumush (3%), Oltin (4%), Platina (5%).
- Real Cashback balance stored atomically in data/loyalty_users.json.
- Points redemption during checkout (up to 20% of order total).
- Visual VIP card dashboard for customers.
Strictly follows RULES.md (Rule 4: atomic writes, Rule 6-10: deterministic math).
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOYALTY_FILE = DATA_DIR / "loyalty_users.json"
_LOYALTY_LOCK = threading.RLock()

# VIP Tiers definition
TIERS = [
    {
        "name": "Platina",
        "badge": "💎 Platina VIP",
        "min_spent": 1000000.0,
        "cashback_percent": 5.0,
        "perk": "5% keshbek + Bepul ekspress yetkazib berish + Shaxsiy menejer"
    },
    {
        "name": "Oltin",
        "badge": "🥇 Oltin VIP",
        "min_spent": 500000.0,
        "cashback_percent": 4.0,
        "perk": "4% keshbek + Navbatsiz tezkor yetkazish"
    },
    {
        "name": "Kumush",
        "badge": "🥈 Kumush Mijoz",
        "min_spent": 200000.0,
        "cashback_percent": 3.0,
        "perk": "3% keshbek + Maxsus mavsumiy aksiyalar"
    },
    {
        "name": "Bronza",
        "badge": "🥉 Bronza Mijoz",
        "min_spent": 0.0,
        "cashback_percent": 2.0,
        "perk": "2% keshbek har bir xariddan"
    }
]

class LoyaltyService:
    """Do'konning VIP sodiqlik va keshbek tizimi"""

    @classmethod
    def _load_all(cls) -> Dict[str, Any]:
        with _LOYALTY_LOCK:
            if not LOYALTY_FILE.exists():
                return {}
            try:
                with open(LOYALTY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading loyalty_users.json: {e}")
                return {}

    @classmethod
    def _save_all(cls, data: Dict[str, Any]) -> None:
        with _LOYALTY_LOCK:
            temp = LOYALTY_FILE.with_suffix(".tmp")
            try:
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                temp.replace(LOYALTY_FILE)
            except Exception as e:
                logger.error(f"Error saving loyalty_users.json: {e}")
                if temp.exists():
                    try:
                        temp.unlink()
                    except Exception:
                        pass

    @classmethod
    def get_tier(cls, total_spent: float) -> Dict[str, Any]:
        """Xarid summasiga qarab mijozning VIP darajasini aniqlash"""
        for t in TIERS:
            if total_spent >= t["min_spent"]:
                return t
        return TIERS[-1]

    @classmethod
    def get_user_profile(cls, user_id: int, user_name: str = "Mijoz") -> Dict[str, Any]:
        """Foydalanuvchi profilini olish yoki yangisini yaratish"""
        data = cls._load_all()
        uid_str = str(user_id)
        if uid_str not in data:
            data[uid_str] = {
                "user_id": user_id,
                "name": user_name,
                "total_spent": 0.0,
                "cashback_balance": 0.0,
                "orders_count": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            cls._save_all(data)

        user_data = data[uid_str]
        tier = cls.get_tier(user_data.get("total_spent", 0.0))
        user_data["tier"] = tier["name"]
        user_data["tier_badge"] = tier["badge"]
        user_data["cashback_percent"] = tier["cashback_percent"]
        user_data["tier_perk"] = tier["perk"]
        return user_data

    @classmethod
    def add_order_cashback(cls, user_id: int, order_amount: float, user_name: str = "Mijoz", order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Muvaffaqiyatli buyurtmadan so'ng keshbek hisoblash va hisobga qo'shish (Rule 6: deterministik kod).
        """
        with _LOYALTY_LOCK:
            data = cls._load_all()
            uid_str = str(user_id)
            if uid_str not in data:
                data[uid_str] = {
                    "user_id": user_id,
                    "name": user_name,
                    "total_spent": 0.0,
                    "cashback_balance": 0.0,
                    "orders_count": 0,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }

            user = data[uid_str]
            current_spent = float(user.get("total_spent", 0.0))
            tier = cls.get_tier(current_spent)

            # Keshbek miqdori (aniq kod hisobi)
            earned_cashback = round(order_amount * (tier["cashback_percent"] / 100.0), 0)

            user["total_spent"] = current_spent + float(order_amount)
            user["cashback_balance"] = round(float(user.get("cashback_balance", 0.0)) + earned_cashback, 0)
            user["orders_count"] = int(user.get("orders_count", 0)) + 1
            user["updated_at"] = datetime.now().isoformat()

            new_tier = cls.get_tier(user["total_spent"])
            user["tier"] = new_tier["name"]

            cls._save_all(data)

            return {
                "earned_points": earned_cashback,
                "earned_cashback": earned_cashback,
                "rate_percent": tier["cashback_percent"],
                "cashback_percent": tier["cashback_percent"],
                "new_balance": user["cashback_balance"],
                "total_spent": user["total_spent"],
                "tier": new_tier["name"],
                "tier_badge": new_tier["badge"],
                "tier_upgraded": new_tier["name"] != tier["name"],
                "order_id": order_id
            }

    @classmethod
    def apply_points_discount(cls, user_id: int, order_total: float, points_to_use: Optional[float] = None, requested_points: Optional[float] = None) -> Dict[str, Any]:
        """
        Buyurtma uchun to'plangan keshbek ballarini ishlatish.
        Maksimal chegirma: Buyurtma summasining 20% igacha.
        """
        with _LOYALTY_LOCK:
            user = cls.get_user_profile(user_id)
            avail_balance = float(user.get("cashback_balance", 0.0))

            target_points = points_to_use if points_to_use is not None else requested_points

            if avail_balance <= 0 or order_total <= 0:
                return {
                    "applied": False,
                    "used_points": 0.0,
                    "points_used": 0.0,
                    "discount_amount": 0.0,
                    "final_total": order_total,
                    "remaining_balance": avail_balance,
                    "message": "Keshbek balansingizda ballar mavjud emas."
                }

            # Maksimal chegirma limit: 20%
            max_allowed_discount = round(order_total * 0.20, 0)

            if target_points is None or target_points <= 0:
                actual_discount = min(avail_balance, max_allowed_discount)
            else:
                actual_discount = min(float(target_points), avail_balance, max_allowed_discount)

            final_total = max(0.0, order_total - actual_discount)

            return {
                "applied": actual_discount > 0,
                "used_points": actual_discount,
                "points_used": actual_discount,
                "discount_amount": actual_discount,
                "final_total": final_total,
                "remaining_balance": avail_balance - actual_discount,
                "max_allowed": max_allowed_discount
            }

    @classmethod
    def confirm_points_deduction(cls, user_id: int, points_to_deduct: float) -> bool:
        """Buyurtma tasdiqlanganda ballarni hisobdan chiqarish"""
        with _LOYALTY_LOCK:
            data = cls._load_all()
            uid_str = str(user_id)
            if uid_str not in data:
                return False
            cur_bal = float(data[uid_str].get("cashback_balance", 0.0))
            new_bal = max(0.0, cur_bal - float(points_to_deduct))
            data[uid_str]["cashback_balance"] = round(new_bal, 0)
            data[uid_str]["updated_at"] = datetime.now().isoformat()
            cls._save_all(data)
            return True

    @classmethod
    def format_loyalty_dashboard(cls, user_id: int, user_name: str = "Mijoz") -> str:
        """Mijoz uchun chiroyli VIP Sodiqlik Karta ko'rinishi"""
        user = cls.get_user_profile(user_id, user_name)
        total_spent = float(user.get("total_spent", 0.0))
        balance = float(user.get("cashback_balance", 0.0))
        orders_cnt = int(user.get("orders_count", 0))
        tier_name = user.get("tier", "Bronza")
        tier_badge = user.get("tier_badge", "🥉 Bronza Mijoz")
        perk = user.get("tier_perk", "2% keshbek")

        # Keyingi darajaga qadar qolgan summa
        next_tier_msg = ""
        if tier_name == "Bronza":
            needed = 200000.0 - total_spent
            next_tier_msg = f"📈 **Kumush** maqomigacha: yana **{needed:,.0f} so'm** xarid kerak"
        elif tier_name == "Kumush":
            needed = 500000.0 - total_spent
            next_tier_msg = f"📈 **Oltin VIP** maqomigacha: yana **{needed:,.0f} so'm** xarid kerak"
        elif tier_name == "Oltin":
            needed = 1000000.0 - total_spent
            next_tier_msg = f"📈 **Platina VIP** maqomigacha: yana **{needed:,.0f} so'm** xarid kerak"
        else:
            next_tier_msg = "👑 Siz eng yuqori darajadagi **Platina VIP** a'zosiz!"

        return (
            f"💳 **MARKAZSAVDO VIP SODIQLIK KARTASI**\n"
            f"─────────────────────────\n"
            f"👤 Mijoz: **{user_name}**\n"
            f"🏅 Maqomingiz: **{tier_badge}**\n"
            f"💰 Keshbek balansingiz: **{balance:,.0f} so'm**\n"
            f"🛍️ Jami xaridlaringiz: **{total_spent:,.0f} so'm** ({orders_cnt} ta buyurtma)\n\n"
            f"🎁 **Sizning imtiyozlaringiz:**\n"
            f"• {perk}\n"
            f"• To'plangan ballaringizni xaridda 20% gacha chegirma qilib ishlatishingiz mumkin!\n\n"
            f"{next_tier_msg}\n"
            f"─────────────────────────\n"
            f"Har bir buyurtmangiz uchun sizga minnatdormiz! 😊"
        )

    # Clean aliases
    award_order_cashback = add_order_cashback
    calculate_redemption = apply_points_discount
    format_loyalty_card = format_loyalty_dashboard

