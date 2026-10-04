"""
services/promo_manager.py
Jahon darajasidagi Promokodlar va Chegirmalar Moduli.
Xaridorlar uchun chegirmalarni tekshirish, qo'llash va Admin uchun promokod boshqaruvi.
"""

from typing import Dict, Any, Optional
from datetime import datetime

class PromoManager:
    """Promokodlar menejeri (Dynamic Promo Engine)"""

    _promo_codes: Dict[str, Dict[str, Any]] = {
        "MARKAZ10": {
            "type": "percent",
            "value": 10.0,
            "description": "10% umumiy chegirma",
            "is_active": True,
            "usage_count": 0
        },
        "SUPER2026": {
            "type": "amount",
            "value": 25000.0,
            "description": "25,000 so'm chegirma",
            "is_active": True,
            "usage_count": 0
        },
        "VIPMIJOZ": {
            "type": "percent",
            "value": 15.0,
            "description": "VIP mijozlar uchun 15% chegirma",
            "is_active": True,
            "usage_count": 0
        },
        "YANGI": {
            "type": "amount",
            "value": 10000.0,
            "description": "Yangi xaridorlar uchun 10,000 so'm chegirma",
            "is_active": True,
            "usage_count": 0
        },
        "BAHOR2026": {
            "type": "percent",
            "value": 12.0,
            "description": "Bahorgi mavsumiy 12% chegirma",
            "is_active": True,
            "usage_count": 0
        }
    }

    @classmethod
    def validate_code(cls, code: str) -> Dict[str, Any]:
        """Promokodni tekshirish va qiymatini qaytarish"""
        clean_code = code.strip().upper()
        promo = cls._promo_codes.get(clean_code)

        if not promo:
            return {
                "valid": False,
                "message": f"❌ '{clean_code}' nomli promokod topilmadi yoki muddati tugagan."
            }

        if not promo.get("is_active", True):
            return {
                "valid": False,
                "message": f"❌ '{clean_code}' promokodi hozirda faol emas."
            }

        p_type = promo["type"]
        val = promo["value"]
        desc = promo["description"]

        return {
            "valid": True,
            "code": clean_code,
            "type": p_type,
            "value": val,
            "description": desc,
            "percent": val if p_type == "percent" else 0.0,
            "amount": val if p_type == "amount" else 0.0,
            "message": f"🎉 Tabriklaymiz! '{clean_code}' promokodi muvaffaqiyatli qo'llandi ({desc})!"
        }

    @classmethod
    def register_usage(cls, code: str):
        """Promokod ishlatilganligini qayd etish"""
        clean_code = code.strip().upper()
        if clean_code in cls._promo_codes:
            cls._promo_codes[clean_code]["usage_count"] += 1

    @classmethod
    def add_promo_code(cls, code: str, promo_type: str, value: float, description: str = "") -> bool:
        """Admin tomonidan yangi promokod qo'shish"""
        clean_code = code.strip().upper()
        cls._promo_codes[clean_code] = {
            "type": promo_type,
            "value": float(value),
            "description": description or (f"{value}% chegirma" if promo_type == "percent" else f"{value:,.0f} so'm chegirma"),
            "is_active": True,
            "usage_count": 0
        }
        return True

    @classmethod
    def get_active_promos_display(cls) -> str:
        """Xaridorlarga ko'rsatiladigan ommaviy aksiyalar ro'yxati"""
        lines = ["🏷 **DO'KONIMIZNING FAOLLIK AKSIYALARI VA PROMOKODLARI:**\n"]
        for code, info in cls._promo_codes.items():
            if info.get("is_active", True):
                lines.append(f"🎁 Promokod: `{code}` — **{info['description']}**")
        lines.append("\n💡 *Promokodni savatchangizda yoki xarid paytida yozib chegirmaga ega bo'ling!*")
        return "\n".join(lines)
