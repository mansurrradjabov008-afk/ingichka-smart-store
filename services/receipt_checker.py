import logging
import requests
from typing import Dict, Any, Optional
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

class ReceiptChecker:
    """
    Click, Payme, Uzum to'lov cheklarini skrinshot orqali tekshirish va firibgarlikdan himoya qilish.
    Gemini Multimodal Vision texnologiyasidan foydalanadi.
    """

    @staticmethod
    def is_likely_payment_intent(caption: Optional[str]) -> bool:
        """Matnda to'lov, kvitansiya yoki chek niyati bor-yo'qligini aniqlash"""
        if not caption:
            return False
        cap = caption.lower()
        keywords = [
            "chek", "to'lov", "tolov", "to'ladim", "toladim", "oplata", 
            "skrinshot", "payme", "click", "uzum bank", "kvitansiya", 
            "tushdimi", "otkazdim", "o'tkazdim", "pul tashladim"
        ]
        return any(kw in cap for kw in keywords)

    @staticmethod
    def is_likely_product_inquiry(caption: Optional[str]) -> bool:
        """Matnda tovar, kiyim, narx yoki o'lcham so'ralganligini aniqlash"""
        if not caption:
            return False
        cap = caption.lower()
        keywords = [
            "bormi", "qancha", "narxi", "kiyim", "razmer", "rangi", 
            "matosi", "qanaqa", "ayting", "shu", "bor", "bormi?", "qanchadan",
            "olaman", "olmoqchiman", "yetkazasizmi", "necha pul"
        ]
        return any(kw in cap for kw in keywords)

    @staticmethod
    def verify_payment_screenshot(image_b64: str) -> Dict[str, Any]:
        if not GEMINI_API_KEY:
            return {"is_receipt": False, "is_valid": False, "reason": "AI kaliti ulanmagan"}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={GEMINI_API_KEY}"

        prompt = """
Siz bank to'lov cheklarini tekshiruvchi mutaxassisiz.
Ushbu rasm bank ilovasi (Click, Payme, Uzum Bank, Anorbank, Apelsin va h.k.) to'lov cheki / kvitansiyasi ekanligini tekshiring.

QAT'IY QOIDA:
- Agar rasmda kiyim, poyabzal, do'kon tovari, odam yoki boshqa oddiy narsa bo'lsa, qat'iyan:
IS_RECEIPT: YOQ deb javob bering.
- Faqat va faqat rasm haqiqiy bank ilovasi to'lov cheki yoki o'tkazma kvitansiyasi bo'lsagina:
IS_RECEIPT: HA deb yozing.

Javob formati:
IS_RECEIPT: [HA yoki YOQ]
To'lov ilovasi: [Click / Payme / Uzum / Noma'lum / Chek emas]
Summa: [Summa] so'm
Holati: [Muvaffaqiyatli / Kutilmoqda / Noma'lum]
Xulosa: [To'lov haqiqiy va qabul qilish mumkin yoki Chek emas]
"""

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
        }

        try:
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text_lower = text.lower()

                # IS_RECEIPT tekshiruvi: faqat HA bo'lsa va YOQ bo'lmasa
                is_receipt = False
                if "is_receipt: ha" in text_lower or ("is_receipt:ha" in text_lower):
                    if "is_receipt: yoq" not in text_lower and "chek emas" not in text_lower:
                        is_receipt = True

                is_valid = is_receipt and any(kw in text_lower for kw in ["muvaffaqiyatli", "bajarildi", "to'langan", "qabul qilish mumkin"])

                return {
                    "is_receipt": is_receipt,
                    "is_valid": is_valid,
                    "analysis": text
                }
            else:
                logger.error(f"Receipt OCR xatosi: {resp.status_code} - {resp.text}")
                return {"is_receipt": False, "is_valid": False, "analysis": "Chekni o'qib bo'lmadi."}
        except Exception as e:
            logger.error(f"Receipt OCR xatolik: {e}")
            return {"is_receipt": False, "is_valid": False, "analysis": f"Xatolik: {e}"}
