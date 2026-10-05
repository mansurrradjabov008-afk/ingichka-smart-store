"""
services/stylist_service.py
AI Stylist & Total Look (To'liq Komplekt) Curation Engine.
Assembles intelligent, matching 3-piece outfits from the 41 real in-stock products.
Calculates bundle totals and automatic 5% multi-item discounts strictly in code.
"""

from typing import Dict, Any, List, Optional
from services.catalog_service import load_products
from services.sales_intelligence import SalesIntelligence

class StylistService:
    """Do'kon AI Stilisti — Mos kiyimlar komplektini shakllantirish"""

    LOOK_CATEGORIES = {
        "ayol": {
            "top": ["ko'ylak", "tonika"],
            "outer": ["kardigan"],
            "shoes": ["tapichka", "shippak"]
        },
        "erkak": {
            "top": ["svitir", "polo"],
            "outer": ["vitrofka", "kurtka", "sportivka"],
            "bottom": ["shim", "triko"]
        },
        "bolalar": {
            "main": ["troyka", "futbolka", "pijama"],
            "bottom": ["triko", "shim"],
            "shoes": ["krossovka", "tapichka"]
        }
    }

    @classmethod
    def curate_total_look(
        cls,
        gender: str = "ayol",
        theme: str = "kundalik"
    ) -> Optional[Dict[str, Any]]:
        """
        Ombordagi mavjud tovarlardan 100% mos to'liq komplekt yig'ish.
        Hamma hisob-kitoblar kodda qat'iy va xatosiz bajariladi.
        """
        all_prods = [p for p in load_products() if p.get("stock", 0) > 0]
        g_low = gender.lower()

        target_gender = "Ayol" if "ayol" in g_low or "qiz" in g_low or "xotin" in g_low else (
            "Bolalar" if "bola" in g_low or "o'g'il" in g_low or "ogil" in g_low or "chaqaloq" in g_low else "Erkak"
        )

        # Shu jinsga mos tovarlarni filtrlash
        matching = [p for p in all_prods if p.get("gender") == target_gender or p.get("gender") == "Uniseks"]

        selected_items = []
        used_ids = set()

        if target_gender == "Ayol":
            # 1. Ko'ylak yoki Tonika
            dress = next((p for p in matching if p["category"] == "Ko'ylak" and p["id"] not in used_ids), None)
            if dress:
                selected_items.append(dress)
                used_ids.add(dress["id"])

            # 2. Kardigan
            cardigan = next((p for p in matching if p["category"] == "Kardigan" and p["id"] not in used_ids), None)
            if cardigan:
                selected_items.append(cardigan)
                used_ids.add(cardigan["id"])

            # 3. Oyoq kiyim (Tapichka)
            shoes = next((p for p in matching if p["category"] == "Oyoq kiyim" and p["id"] not in used_ids), None)
            if shoes:
                selected_items.append(shoes)
                used_ids.add(shoes["id"])

        elif target_gender == "Erkak":
            # 1. Svitir
            sweater = next((p for p in matching if p["category"] == "Svitir" and p["id"] not in used_ids), None)
            if sweater:
                selected_items.append(sweater)
                used_ids.add(sweater["id"])

            # 2. Vitrofka
            jacket = next((p for p in matching if p["category"] == "Kurtka" and p["id"] not in used_ids), None)
            if jacket:
                selected_items.append(jacket)
                used_ids.add(jacket["id"])

            # 3. Shim / Triko
            pants = next((p for p in matching if p["category"] == "Shim" and p["id"] not in used_ids), None)
            if pants:
                selected_items.append(pants)
                used_ids.add(pants["id"])

        else: # Bolalar
            # 1. Asosiy kiyim (Troyka komplekt yoki Pijama)
            main_item = next((p for p in matching if p["category"] in ["Kostyum", "Pijama", "Bolalar kiyimi"] and p["id"] not in used_ids), None)
            if main_item:
                selected_items.append(main_item)
                used_ids.add(main_item["id"])

            # 2. Futbolka yoki Triko
            triko = next((p for p in matching if p["category"] in ["Shim", "Futbolka"] and p["id"] not in used_ids), None)
            if triko:
                selected_items.append(triko)
                used_ids.add(triko["id"])

            # 3. Bolalar krossovkasi
            shoes = next((p for p in matching if p["category"] == "Oyoq kiyim" and p["id"] not in used_ids), None)
            if shoes:
                selected_items.append(shoes)
                used_ids.add(shoes["id"])

        if len(selected_items) < 2:
            return {"success": False, "items": [], "message": "Yetarli tovar topilmadi"}

        # Narxlarni kod orqali hisoblash
        subtotal = sum(float(p["price"]) for p in selected_items)
        # 2+ tovar uchun 5% chegirma
        discount_calc = SalesIntelligence.apply_discount(
            items=[{"id": p["id"], "unit_price": p["price"], "quantity": 1} for p in selected_items]
        )

        return {
            "success": True,
            "gender": target_gender,
            "theme": theme,
            "items": selected_items,
            "subtotal": subtotal,
            "total_raw": subtotal,
            "discount_percent": discount_calc["discount_percent"],
            "discount_amount": discount_calc["discount_amount"],
            "final_bundle_price": discount_calc["final_total"],
            "bundle_price": discount_calc["final_total"]
        }

    @classmethod
    def format_look_presentation(cls, look: Dict[str, Any]) -> str:
        """Komplekt taqdimotining chiroyli matni"""
        if not look or not look.get("success", True) or not look.get("items"):
            return "Kechirasiz, tanlangan toifa bo'yicha to'liq komplekt tuzish uchun hozirda yetarli tovarlar omborda qolmagan."

        gender = look.get("gender", "Mijoz")
        items = look.get("items", [])
        subtotal = look.get("subtotal") or look.get("total_raw", 0.0)
        discount_amt = look.get("discount_amount", 0.0)
        final_price = look.get("final_bundle_price") or look.get("bundle_price", subtotal)

        lines = [
            f"✨ **AI STILIST TAVSIYASI — {gender.upper()}LAR UCHUN TOTAL LOOK (KOMPLEKT)** ✨\n",
            "Do'konimiz stilisti siz uchun mukammal yarashadigan quyidagi kiyimlar to'plamini tanladi:\n"
        ]

        for idx, item in enumerate(items, 1):
            sizes_str = ", ".join(item.get("sizes", [])) if isinstance(item.get("sizes"), list) else str(item.get("sizes", ""))
            colors_str = ", ".join(item.get("colors", [])) if isinstance(item.get("colors"), list) else str(item.get("colors", ""))
            lines.append(f"{idx}. **{item['name']}**")
            lines.append(f"   📏 O'lcham: {sizes_str} | 🎨 Rang: {colors_str}")
            lines.append(f"   💰 Narxi: {item['price']:,.0f} so'm\n")

        lines.append("─────────────────────────")
        lines.append(f"💵 Alohida narxlar jami: **{subtotal:,.0f} so'm**")
        lines.append(f"🎁 **To'liq komplekt chegirmasi (5%):** -{discount_amt:,.0f} so'm")
        lines.append(f"🏷️ **Komplekt maxsus narxi:** **{final_price:,.0f} so'm**")
        lines.append("─────────────────────────")
        lines.append("🚚 O'zbekiston bo'ylab tezkor yetkazib beramiz!")
        lines.append("Ushbu komplektni buyurtma qilishni istaysizmi? 'Ha' deb yozishingiz kifoya 😊")

        return "\n".join(lines)

    # Clean aliases
    curate_outfit = curate_total_look
    format_outfit_card = format_look_presentation

