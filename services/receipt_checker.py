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
    def verify_payment_screenshot(image_b64: str) -> Dict[str, Any]:
        if not GEMINI_API_KEY:
            return {"is_valid": False, "reason": "AI kaliti ulanmagan"}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={GEMINI_API_KEY}"

        prompt = """
Ushbu rasm Click, Payme, Uzum Bank yoki boshqa bank ilovasining to'lov cheki (skrinshoti) ekanligini tekshir.
Quyidagi ma'lumotlarni aniq aniqlab, o'zbek tilida xulosa ber:
1. Bu haqiqiy to'lov chekimi yoki oddiy rasmmi?
2. To'lov summasi qancha (so'mda)?
3. To'lov holati muvaffaqiyatlimi (To'langan / Bajarilgan)?
4. To'lov sanasi va vaqti qachon?

Javobingni quyidagi formatda lo'nda qilib yoz:
To'lov ilovasi: [Click / Payme / Uzum / Noma'lum]
Summa: [Summa] so'm
Holati: [Muvaffaqiyatli / Kutilmoqda / Noma'lum]
Sana va vaqt: [Sana]
Xulosa: [To'lov haqiqiy va qabul qilish mumkin yoki shubhali]
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
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}
        }

        try:
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                is_valid = ("muvaffaqiyatli" in text.lower() or "bajarildi" in text.lower() or "to'langan" in text.lower())
                return {
                    "is_receipt": True,
                    "is_valid": is_valid,
                    "analysis": text
                }
            else:
                logger.error(f"Receipt OCR xatosi: {resp.status_code} - {resp.text}")
                return {"is_receipt": False, "is_valid": False, "analysis": "Chekni o'qib bo'lmadi."}
        except Exception as e:
            logger.error(f"Receipt OCR xatolik: {e}")
            return {"is_receipt": False, "is_valid": False, "analysis": f"Xatolik: {e}"}
