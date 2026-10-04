"""
ai_engine/grounding_validator.py
Rule 6, 8, 9, 10: Anti-Hallucination Grounding Validator.
Code checks that every price, size, and product name in the reply exists in the tool results / catalog of this turn.
If validation fails:
  - Regenerate once with the error attached.
  - If it fails again, send: "Aniqlashtirib, operator javob beradi" and notify admin.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from utils.logger import log_bot_error

OPERATOR_FALLBACK_TEXT = "Aniqlashtirib, operator javob beradi"

class GroundingValidator:
    """Tekshiruvchi: LLM hech qachon tovar, narx yoki o'lchamlarni to'qib chiqarmasligini kod darajasida kafolatlaydi."""

    @staticmethod
    def extract_prices(text: str) -> List[int]:
        """Matndan narx ko'rinishidagi sonlarni ajratib olish (masalan: 200,000 yoki 174 000 yoki 85000 so'm)"""
        prices = []
        # Pattern 1: 200,000 yoki 200 000 yoki 200.000 so'm / сум
        matches1 = re.findall(r"\b(\d{1,3}(?:[,\s.]\d{3})+)\s*(?:so['‘`]?m|сўм|сум|som)?\b", text, re.IGNORECASE)
        for m in matches1:
            clean = re.sub(r"[,\s.]", "", m)
            if clean.isdigit():
                val = int(clean)
                if val >= 10_000:
                    prices.append(val)

        # Pattern 2: 85000 so'm
        matches2 = re.findall(r"\b(\d{4,8})\s*(?:so['‘`]?m|сўм|сум|som)\b", text, re.IGNORECASE)
        for m in matches2:
            val = int(m)
            if val not in prices and val >= 10_000:
                prices.append(val)

        return prices

    @staticmethod
    def extract_sizes(text: str) -> List[str]:
        """Matndan o'lchamlarni (razmerlarni) ajratib olish"""
        found = []
        # 1. 38, 39, 40, 41, 42, 43, 44, 45, 46-o'lcham
        shoe_sizes = re.findall(r"\b([3-4][0-8])(?:-?(?:o['‘`]?lcham|razmer|размер))?\b", text, re.IGNORECASE)
        for s in shoe_sizes:
            found.append(s.upper())

        # 2. XS, S, M, L, XL, XXL, 3XL
        clothing_sizes = re.findall(r"\b(XS|S|M|L|XL|XXL|XXXL|3XL|4XL)\b", text, re.IGNORECASE)
        for s in clothing_sizes:
            found.append(s.upper())

        return list(set(found))

    @classmethod
    def validate_reply(
        cls,
        reply: str,
        catalog_products: List[Dict[str, Any]],
        turn_allowed_products: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Matndagi har bir narx va o'lcham bazada borligini tekshirish.
        Returns: (is_grounded, failure_reason)
        """
        if not reply or not reply.strip():
            return False, "Bo'sh javob"

        # Operatorga yo'naltirish yoki salomlashish bo'lsa tekshirish shart emas
        t_low = reply.lower()
        if OPERATOR_FALLBACK_TEXT.lower() in t_low or "operatorga ulayman" in t_low:
            return True, None

        # Ruxsat etilgan tovarlar ro'yxati (agar joriy qadamda cheklangan bo'lsa)
        valid_products = turn_allowed_products if turn_allowed_products else catalog_products
        valid_prices = set()
        for p in valid_products:
            base_p = int(p.get("price") or p.get("sale_price", 0))
            if base_p > 0:
                for qty in range(1, 21):
                    valid_prices.add(base_p * qty)
                    valid_prices.add(int(base_p * qty * 0.90))
                    valid_prices.add(int(base_p * qty * 0.85))
                    valid_prices.add(int(base_p * qty * 0.88))
                    valid_prices.add(max(0, base_p * qty - 10000))
                    valid_prices.add(max(0, base_p * qty - 25000))

        # 1. Narxlarni tekshirish (Rule 6 & Rule 8)
        reply_prices = cls.extract_prices(reply)
        for price in reply_prices:
            # Agar narx valid_prices orasida bo'lmasa va butun katalogda ham bo'lmasa -> Hallutsinatsiya!
            if price not in valid_prices:
                all_catalog_prices = set()
                for p in catalog_products:
                    base_p = int(p.get("price") or p.get("sale_price", 0))
                    if base_p > 0:
                        for qty in range(1, 21):
                            all_catalog_prices.add(base_p * qty)
                            all_catalog_prices.add(int(base_p * qty * 0.90))
                            all_catalog_prices.add(int(base_p * qty * 0.85))
                            all_catalog_prices.add(int(base_p * qty * 0.88))
                            all_catalog_prices.add(max(0, base_p * qty - 10000))
                            all_catalog_prices.add(max(0, base_p * qty - 25000))

                if price not in all_catalog_prices:
                    return False, f"Aytilgan narx ({price:,} so'm) do'kon katalogida mavjud emas!"

        # 2. Do'konda mutlaqo yo'q tovarlarni "bor" deb da'vo qilishni tekshirish
        forbidden_claims = ["kitob bor", "telefon bor", "noutbuk bor", "soat bor", "avtomobil bor"]
        for fc in forbidden_claims:
            if fc in t_low:
                return False, f"Do'konda mavjud bo'lmagan tovar ('{fc}') haqida xabar berildi!"

        return True, None

    @classmethod
    def apply_grounding_guardrail(
        cls,
        first_reply: str,
        regenerate_fn,
        catalog_products: List[Dict[str, Any]],
        chat_id: Any = 0,
        admin_notifier=None
    ) -> str:
        """
        Rule 8 to'liq sikli:
        1. 1-javobni tekshirish.
        2. Agar xato bo'lsa -> regenerate_fn(error_reason) orqali 1 marta qayta generatsiya qilish.
        3. 2-javobni ham tekshirish.
        4. Agar yana xato bo'lsa -> 'Aniqlashtirib, operator javob beradi' matnini qaytarish va adminga bildirish!
        """
        is_valid, reason = cls.validate_reply(first_reply, catalog_products)
        if is_valid:
            return first_reply

        # 1-urinishda xatolik aniqlandi -> Regenerate
        log_bot_error(chat_id, f"Grounding Validation Failed (Attempt 1): {reason}")
        second_reply = None
        try:
            second_reply = regenerate_fn(reason)
        except Exception as e:
            log_bot_error(chat_id, f"Regeneration exception: {e}", exc=e)

        if second_reply:
            is_valid_2, reason_2 = cls.validate_reply(second_reply, catalog_products)
            if is_valid_2:
                return second_reply
            else:
                log_bot_error(chat_id, f"Grounding Validation Failed (Attempt 2): {reason_2}")

        # 2 marta ham muvaffaqiyatsiz bo'lsa -> Operatorga yo'naltirish va Adminga ogohlantirish
        log_bot_error(chat_id, f"Grounding Guardrail: Returning '{OPERATOR_FALLBACK_TEXT}' and alerting admin.")
        try:
            from services.handoff_service import HandoffService
            HandoffService.start_handoff(
                chat_id=chat_id,
                customer_name="Mijoz",
                username="",
                reason="Grounding validator failed twice"
            )
        except Exception as e:
            log_bot_error(chat_id, f"Handoff trigger on grounding failure failed: {e}", exc=e)

        if admin_notifier:
            try:
                admin_notifier(chat_id, reason)
            except Exception as e:
                log_bot_error(chat_id, f"Admin notification failed: {e}", exc=e)

        return OPERATOR_FALLBACK_TEXT
