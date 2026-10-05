"""
services/recovery_service.py
Smart Abandoned Cart & Incomplete Order Flow Recovery (Shopify Magic style).
Nudges customers who dropped off during checkout politely and respectfully,
strictly avoiding spam (maximum 1 gentle nudge per abandoned session).
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RECOVERY_LOG_FILE = DATA_DIR / "recovery_nudges.json"
_RECOVERY_LOCK = threading.RLock()

class RecoveryService:
    """Tashlab ketilgan savat va chala buyurtmalarni qaytarish xizmati"""

    @classmethod
    def _load_nudges(cls) -> Dict[str, Any]:
        with _RECOVERY_LOCK:
            if not RECOVERY_LOG_FILE.exists():
                return {}
            try:
                with open(RECOVERY_LOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading recovery_nudges.json: {e}")
                return {}

    @classmethod
    def _save_nudges(cls, data: Dict[str, Any]) -> None:
        with _RECOVERY_LOCK:
            temp = RECOVERY_LOG_FILE.with_suffix(".tmp")
            try:
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                temp.replace(RECOVERY_LOG_FILE)
            except Exception as e:
                logger.error(f"Error saving recovery_nudges.json: {e}")
                if temp.exists():
                    try:
                        temp.unlink()
                    except Exception:
                        pass

    @classmethod
    def should_nudge(cls, chat_id: int, nudge_type: str = "cart") -> bool:
        """Mijozga oldin nudge yuborilgan yoki yuborilmaganini tekshirish (faqat 1 marta)"""
        nudges = cls._load_nudges()
        key = f"{chat_id}_{nudge_type}" if nudge_type else str(chat_id)
        return key not in nudges and str(chat_id) not in nudges

    @classmethod
    def mark_nudged(cls, chat_id: int, context: str = "cart", message_text: str = "") -> None:
        """Nudge yuborilganini qayd qilish (Anti-Spam)"""
        with _RECOVERY_LOCK:
            nudges = cls._load_nudges()
            key = f"{chat_id}_{context}" if context else str(chat_id)
            nudges[key] = {
                "chat_id": chat_id,
                "context": context,
                "message": message_text,
                "nudged_at": datetime.now().isoformat()
            }
            # Shuningdek chat_id kaliti bilan ham saqlash
            nudges[str(chat_id)] = nudges[key]
            cls._save_nudges(nudges)

    @classmethod
    def generate_recovery_message(cls, customer_name: str, product_name: str) -> str:
        """Samimiy, xushmuomala eslatma matni (Rule 6: samimiy, max 1 emoji)"""
        c_name = customer_name or "Mijoz"
        return (
            f"Assalomu alaykum, {c_name}! 😊\n\n"
            f"Siz ko'rib chiqqan **'{product_name}'** mahsulotimiz omborda kam qolmoqda.\n"
            f"Agar xarid qilish niyatida bo'lsangiz, buyurtmangizni siz uchun saqlab turishimiz mumkin.\n\n"
            f"Davom ettirishni istasangiz, bemalol 'Ha' deb yozishingiz mumkin."
        )

    # Clean aliases
    can_send_nudge = should_nudge
    record_nudge = mark_nudged

