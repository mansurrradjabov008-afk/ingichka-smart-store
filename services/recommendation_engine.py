"""
services/recommendation_engine.py
AI Aqlli Tavsiya va Kross-Savdo (Cross-Sell & Upsell) Mexanizmi.
Mijoz savatiga yoki tanloviga mos tovarlarni avtomatik moslab berish.
"""

from typing import List, Dict, Any, Optional
from services.catalog_service import load_products

COMPLEMENTARY_MAP = {
    "futbolka": ["jinsi", "kepka", "sport paypoq"],
    "jinsi": ["futbolka", "ko'ylak", "kurtka"],
    "kurtka": ["paypoq", "jinsi", "ko'ylak"],
    "ko'ylak": ["jinsi", "palto", "kepka"],
    "palto": ["ko'ylak", "jinsi"],
    "kepka": ["futbolka", "jinsi"],
    "paypoq": ["ichki kiyim", "futbolka"],
    "ichki kiyim": ["paypoq", "futbolka"]
}

class RecommendationEngine:
    """Tavsiyalar va komplekt takliflar generatori"""

    @classmethod
    def get_cross_sell_for_product(cls, product_name: str, exclude_ids: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
        """Bitta tovar uchun eng mos keluvchi kross-tovar topish"""
        all_prods = load_products()
        exclude_ids = exclude_ids or []
        p_name_low = product_name.lower()

        # Tovarning asosiy turini aniqlash
        matched_cat = None
        for key in COMPLEMENTARY_MAP:
            if key in p_name_low:
                matched_cat = key
                break

        if not matched_cat:
            matched_cat = "futbolka"

        target_cats = COMPLEMENTARY_MAP.get(matched_cat, ["futbolka", "kepka"])

        # Mos tovarlarni qidirish
        candidates = []
        for p in all_prods:
            if p["id"] in exclude_ids:
                continue
            if p.get("stock", 0) <= 0:
                continue

            name_l = p["name"].lower()
            if any(tc in name_l for tc in target_cats):
                candidates.append(p)

        if candidates:
            return candidates[0]
        return None

    @classmethod
    def format_cross_sell_pitch(cls, main_product_name: str, recommended_prod: Dict[str, Any]) -> str:
        """Kross-savdo taklifining chiroyli matni"""
        p_name = recommended_prod["name"]
        price = recommended_prod["price"]
        return (
            f"💡 **AI Tavsiya (Mukammal Komplekt):**\n"
            f"Siz tanlagan '{main_product_name}' bilan **'{p_name}'** ({price:,.0f} so'm) "
            f"juda chiroyli yarashadi!\n"
            f"Uni ham savatchangizga qo'shamizmi? 🛍"
        )
