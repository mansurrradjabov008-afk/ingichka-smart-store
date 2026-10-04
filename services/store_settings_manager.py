import re
from typing import Optional, Dict, Any
from config import STORE_SETTINGS, ADMIN_TELEGRAM_IDS

class StoreSettingsManager:
    """
    Do'kon sozlamalari (delivery, discount, address) boshqaruvchi xizmat.
    Agar sozlama bo'sh bo'lsa, mijozga "Buni egasidan so'rab aytaman" deb javob beradi
    va do'kon egasiga (admin) darhol xabar yuboradi.
    """

    @classmethod
    def get_setting(cls, key: str) -> str:
        return STORE_SETTINGS.get(key, "").strip()

    @classmethod
    def set_setting(cls, key: str, value: str):
        STORE_SETTINGS[key] = value.strip()

    @classmethod
    def check_setting_inquiry(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Xabar ichida yetkazib berish (delivery), chegirma (discount) yoki
        do'kon manzili (address) haqida savol borligini aniqlash.
        """
        if not text:
            return None

        t_low = text.lower().strip()

        # 1. Do'kon manzili (address) haqida savol
        # Mijoz o'z manzilini berayotganini ("manzilim: ...", "uy: ...") ajratish kerak
        address_inquiry_patterns = [
            r"(?:manzili|manzilingiz|adres|adresi|adresingiz|lokatsiya|lokatsiyangiz)",
            r"(?:do['`]?kon|dokon|magazin).*(?:qayerda|joylashgan|manzili|adresi)",
            r"qayerda\s*(?:joylashgan|joylashgansiz|do['`]?kon|dokon|sizlar)",
            r"(?:qayerdan\s*(?:topsam|olsam|borsam)\s*bo['`]?ladi)",
            r"(?:sizlar\s*qayerdasizlar|qayerdagi\s*do['`]?konsizlar)",
            r"(?:do['`]?konga\s*borib\s*(?:kursam|ko['`]?rsam|olsam))"
        ]
        is_address_query = any(re.search(p, t_low) for p in address_inquiry_patterns)
        # Agar "manzilim" yoki telefon raqam bo'lsa, bu mijozning o'z manzili
        if is_address_query and "manzilim" not in t_low and not re.search(r"\b\d{9}\b", t_low):
            val = cls.get_setting("address")
            if not val:
                return {
                    "setting": "address",
                    "setting_name_uz": "Do'kon manzili (address)",
                    "empty": True,
                    "reply": "Buni egasidan so'rab aytaman"
                }
            return {
                "setting": "address",
                "setting_name_uz": "Do'kon manzili (address)",
                "empty": False,
                "reply": f"Do'konimiz manzili: {val}"
            }

        # 2. Chegirma (discount) haqida savol
        discount_inquiry_patterns = [
            r"(?:chegirma|skidka|aksiya|aktsiya)\s*(?:bormi|bormikin|bormi\?|qilib berasizmi|bormi hozir)?",
            r"(?:arzonroq\s*(?:qilib\s*berasizmi|bering|bo['`]?ladimi|qilolmaysizmi))",
            r"(?:narxidan\s*(?:o['`]?tib\s*berasizmi|tushib\s*berasizmi|kamaytirib\s*berasizmi))",
            r"(?:skidka|chegirmalar)\s*(?:bormi|qilasizmi)"
        ]
        is_discount_query = any(re.search(p, t_low) for p in discount_inquiry_patterns)
        if is_discount_query:
            val = cls.get_setting("discount")
            if not val:
                return {
                    "setting": "discount",
                    "setting_name_uz": "Chegirma (discount)",
                    "empty": True,
                    "reply": "Buni egasidan so'rab aytaman"
                }
            return {
                "setting": "discount",
                "setting_name_uz": "Chegirma (discount)",
                "empty": False,
                "reply": f"Do'konimizdagi chegirma va aksiyalar: {val}"
            }

        # 3. Yetkazib berish (delivery) haqida savol
        # Faqat shartlari, bormi-yo'qligi so'ralganda (zakaz bering / olaman demagan bo'lsa)
        delivery_inquiry_patterns = [
            r"(?:yetkazib\s*berish|yetkazish|dostavka|kuryer|eltib\s*berish|доставка)\s*(?:bormi|qanaqa|qancha|narxi|shartlari|bepulmi|qilasizmi|necha pul|qayergacha)",
            r"(?:yetkazib\s*berasizmi|eltib\s*berasizmi|dostavka\s*qilasizmi|dostavka\s*bormi)",
            r"(?:uygacha\s*(?:olib\s*kelasizmi|yetkazasizmi|berasizmi))"
        ]
        is_delivery_query = any(re.search(p, t_low) for p in delivery_inquiry_patterns)
        if is_delivery_query and not any(w in t_low for w in ["olaman", "zakaz qilmoqchiman", "sotib olaman", "bering", "olmoqchiman"]):
            val = cls.get_setting("delivery")
            if not val:
                return {
                    "setting": "delivery",
                    "setting_name_uz": "Yetkazib berish (delivery)",
                    "empty": True,
                    "reply": "Buni egasidan so'rab aytaman"
                }
            return {
                "setting": "delivery",
                "setting_name_uz": "Yetkazib berish (delivery)",
                "empty": False,
                "reply": f"Yetkazib berish xizmati: {val}"
            }

        return None
