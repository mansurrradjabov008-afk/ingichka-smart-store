import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from database.db_manager import DatabaseManager
from config import (
    STORE_NAME, LOCATION, DELIVERY_ZONE, STORE_SETTINGS, GEMINI_API_KEY, OPENAI_API_KEY, GROQ_API_KEY,
    STORE_PHONE, CHANNEL_USERNAME, CHANNEL_URL, WORKING_HOURS
)

logger = logging.getLogger(__name__)


class AIBrain:
    """
    Haqiqiy Katta Til Modeli (LLM) bilan ishlaydigan Ekspert Sotuvchi Agenti.
    Google Gemini, Groq, OpenAI yoki OpenRouter API bilan ishlaydi.
    """

    def __init__(self):
        # Foydalanuvchilarning muloqot xotirasi (History)
        self.conversations: Dict[int, List[Dict[str, str]]] = {}
        # Dinamik saqlangan API kalit
        self.gemini_api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.groq_api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")

    def set_api_key(self, key: str, provider: str = "gemini") -> bool:
        """Telegram orqali API kalitni darhol faollashtirish"""
        key = key.strip()
        if provider == "gemini":
            self.gemini_api_key = key
            self._gemini_invalid = False
            os.environ["GEMINI_API_KEY"] = key
            return True
        elif provider == "openai":
            self.openai_api_key = key
            os.environ["OPENAI_API_KEY"] = key
            return True
        elif provider == "groq":
            self.groq_api_key = key
            os.environ["GROQ_API_KEY"] = key
            return True
        return False

    def is_ai_ready(self) -> bool:
        return bool(self.gemini_api_key or self.openai_api_key or self.groq_api_key)

    def _build_system_prompt(self, customer_name: str) -> str:
        # Ombordagi tovarlarni real vaqtda bazadan tortib olish
        products = DatabaseManager.get_products(in_stock_only=False)
        catalog_lines = []
        for p in products:
            qty = p['stock_quantity']
            if qty <= 0:
                status = "❌ TUGAGAN (Omborda yo'q)"
            elif qty <= 2:
                status = f"Bor (oxirgi {qty} ta qoldi)"
            else:
                status = f"Bor ({qty} dona)"
            catalog_lines.append(
                f"- #{p['id']} {p['name']} | Kategoriya: {p['category']} | O'lcham: {p['size']} | Rang: {p['color']} | Narx: {p['sale_price']:,.0f} so'm | Holati: {status}"
            )
        catalog_text = "\n".join(catalog_lines)

        delivery_setting = STORE_SETTINGS.get("delivery", "").strip() or "[BO'SH - SOZLAMA KIRITILMAGAN]"
        discount_setting = STORE_SETTINGS.get("discount", "").strip() or "[BO'SH - SOZLAMA KIRITILMAGAN]"
        address_setting = STORE_SETTINGS.get("address", "").strip() or "[BO'SH - SOZLAMA KIRITILMAGAN]"

        clean_name = customer_name if customer_name and customer_name != "Mijoz" else ""
        greeting_instruction = f'"Assalomu alaykum, {clean_name}!"' if clean_name else '"Assalomu alaykum!"'

        return f"""
Sen — "{STORE_NAME}" do'konining professional, samimiy va tajribali BOSH SOTUVCHI-MASLAHATCHISIsan.
Isming — Madinaxon (yoki Madina).

=== QAT'IY QOIDALAR (MUHIM BUYRUQLAR) ===
1. SALOMLASHISH VA MUOMALA ODOBI (QOIDA 6):
   - Mijozga har doim xushmuomala bo'lib, "Assalomu alaykum" deb murojaat qil ({greeting_instruction}).
   - Jinsini taxmin qilish QAT'IYAN TAQIQLANADI! "Akajon", "Opajon", "Aka", "Opa", "Uka", "Singlim" deb aslo aytma.
   - Har bir xabarda qayta-qayta sun'iy ravishda salomlashib boshlash shart emas, suhbat tabiiy va erkin davom etsin.

2. MA'LUMOT SO'RASH CHEKLOVI (QOIDA 1):
   - Mijoz o'zi sotib olish niyatini ochiq bildirmaguncha (masalan: "olaman", "sotib olaman", "zakaz qilmoqchiman", "bering", "buyurtma qilmoqchiman" demaguncha) ASLO MANZIL VA TELEFON RAQAMINI SO'RAMA!
   - Faqat tovar, narx yoki o'lcham so'rayotgan mijozga faqat uning so'rovi bo'yicha maslahat ber.
   - Faqat va faqat mijoz ochiq xarid niyatini bildirganidagina manzil va telefonini so'ra.

3. MASLAHATCHI VA KONSULTATIV SOTUVCHI STANDARTI:
   - Agar mijoz umumiy kiyim (masalan "ayollar kiyimi", "xotinimga", "ayolimga", "erkaklar kiyimi", "o'zimga", "sovg'a", "biror narsa") so'rasa, ASLO DARHOL manzil/tel SO'RAMA!
   - Birinchi navbatda mavjud tovarlarni narxi va qoldig'i bilan samimiy tanishtir.
   - Mijozdan ehtiyojini aniqlashtirish uchun savol ber: qanaqa fason yoqadi (ko'ylakmi, issiq qishki paltomi), qaysi o'lcham (razmer: S, M, L) va qanaqa ranglar ma'qul!
   - Mijoz rang yoki o'lcham tanlasa, unga mos tovarimizni tavsiya qil va "shuni buyurtma qilamizmi?" deb so'ra.
   - Faqat va faqat mijoz aniq bir tovarni tanlab, "ha shuni olaman", "zakaz qilaman" deb tasdiqlagandagina telefon va manzilini so'ra.

4. JAVOB HAJMI VA USLUBI (QOIDA 2):
   - Javobing qisqa va lo'nda bo'lsin: QAT'IY 2-3 JUMLA (gap).
   - Har safar bir xil yakunlovchi gap yozish QAT'IYAN TAQIQLANADI! Javob yakunlarini turli xil, tabiiy shaklda yakunla.

5. KAM QOLGAN TOVAR VA OMBOR QOLDIG'I (QOIDA 3):
   - Agar mahsulot qoldig'i 2 yoki kamroq bo'lsa (1 yoki 2 dona), u haqida gapirganda QAT'IY "oxirgi N ta qoldi" deb ayt (masalan: "oxirgi 1 ta qoldi" yoki "oxirgi 2 ta qoldi").
   - Qoldig'i 0 bo'lgan tovar uchun uning omborda tugaganini bildir.

6. MAVJUD BO'LMAGAN O'LCHAM (QOIDA 7):
   - Agar mijoz so'ragan mahsulotda u xohlagan o'lcham (razmer) mavjud bo'lmasa, QAT'IY ravishda: "bizda faqat [mavjud o'lchamlar] bor" deb javob ber (masalan: "Kechirasiz, bu mahsulotimizda bunday o'lcham yo'q, bizda faqat M, L, XL bor").

6. DO'KON SOZLAMALARI (DELIVERY, DISCOUNT, ADDRESS):
   - Yetkazib berish (delivery): {delivery_setting}
   - Chegirma (discount): {discount_setting}
   - Do'kon manzili (address): {address_setting}
   QAT'IY QOIDA: Agar mijoz yetkazib berish, chegirma yoki do'kon manzili haqida so'rasa va yuqoridagi sozlama bo'sh ("[BO'SH - SOZLAMA KIRITILMAGAN]") bo'lsa, FAQAT: "Buni egasidan so'rab aytaman" deb javob ber. O'zingdan hech qanday shart yoki manzil to'qib chiqarma!

=== REAL VAQTDAGI HAQIQIY OMBOR MA'LUMOTLARI (QAT'IY NOL GALLUTSINATSIYA) ===
Mana do'kondagi ayni daqiqadagi tovarlar:
{catalog_text}

QAT'IY QOIDALAR:
- Faqat yuqoridagi ro'yxatda bor bo'lgan tovarlar, narxlar va o'lchamlarni aytasan!
- Omborda yo'q tovarni "bor" deb aldamaysan.
- Agar mijoz kirill alifbosida yozsa, kirillcha javob berasan. Lotin alifbosida yozsa, lotincha javob berasan.
"""

    def ask(self, user_id: int, user_message: str, customer_name: str = "Mijoz") -> str:
        """Foydalanuvchi savoliga haqiqiy AI Agent sifatida javob berish"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        self.conversations[user_id].append({"role": "user", "content": user_message})
        if len(self.conversations[user_id]) > 10:
            self.conversations[user_id] = self.conversations[user_id][-10:]

        system_prompt = self._build_system_prompt(customer_name)

        # 1. Google Gemini orqali chaqirish
        if self.gemini_api_key and not getattr(self, '_gemini_invalid', False):
            try:
                response = self._call_gemini(system_prompt, self.conversations[user_id])
                if response:
                    self.conversations[user_id].append({"role": "assistant", "content": response})
                    return response
            except Exception as e:
                logger.error(f"Gemini API xatosi: {e}")

        # 2. OpenAI / Groq orqali chaqirish
        if self.openai_api_key or self.groq_api_key:
            try:
                response = self._call_openai_compatible(system_prompt, self.conversations[user_id])
                if response:
                    self.conversations[user_id].append({"role": "assistant", "content": response})
                    return response
            except Exception as e:
                logger.error(f"OpenAI/Groq API xatosi: {e}")

        # 3. Zaxira (Offline ekspert mexanizmi)
        return self._offline_expert_fallback(user_message, customer_name, user_id=user_id)

    def ask_with_photo(self, user_id: int, image_b64: str, caption: str = "", customer_name: str = "Mijoz") -> str:
        """Xaridor yuborgan kiyim yoki buyum rasmini tahlil qilib, ombordagi tovarlar bilan solishtirish"""
        system_prompt = self._build_system_prompt(customer_name)
        user_text = caption if caption else "Menga mana shunaqa yoki shunga o'xshash kiyim kerak. Do'koningizda bormi?"

        if not self.gemini_api_key:
            return "Rasmingizni ko'rishim uchun AI kalit talab etiladi. Hozirda do'konimizda barcha turdagi erkaklar, ayollar, bolalar kiyimlari mavjud!"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={self.gemini_api_key}"
        
        prompt_with_vision = (
            f"{system_prompt}\n\n"
            f"VAZIFA: Xaridor rasm yubordi. Rasmda qanday kiyim/buyum ekanini tahlil qil va bizning omborimizdagi "
            f"eng yaqin, mos tovarlarni narxi va o'lchami bilan samimiy tavsiya qil. "
            f"QAT'IY: Javob 2-3 jumla bo'lsin. Mijoz sotib olish niyatini bildirmaguncha telefon va manzil so'rama."
        )

        payload = {
            "system_instruction": {"parts": [{"text": prompt_with_vision}]},
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": user_text},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800}
        }

        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if user_id not in self.conversations:
                    self.conversations[user_id] = []
                self.conversations[user_id].append({"role": "user", "content": f"[Xaridor rasm yubordi]: {user_text}"})
                self.conversations[user_id].append({"role": "assistant", "content": reply})
                return reply
            else:
                logger.error(f"Vision error: {resp.status_code} - {resp.text}")
                return "Rasmingizni qabul qildim! Xuddi shunday sifatli modellardan omborimizda bor. Qaysi o'lcham sizga ma'qul?"
        except Exception as e:
            logger.error(f"Vision chaqiruvida xatolik: {e}")
            return "Rasmingizni qabul qildim! Bu modelimiz bo'yicha hozir omborimizni tekshirib, sizga mos variantni aytaman."

    def transcribe_audio(self, audio_b64: str, mime_type: str = "audio/ogg") -> str:
        """Audiodagi gapni matnga aylantirish (Speech-to-Text)"""
        if not self.gemini_api_key:
            return ""

        models = ["gemini-flash-latest", "gemini-flash-lite-latest"]
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Ushbu audiodagi gapni eshitib, faqat xaridor/foydalanuvchi aytgan so'zlarni toza o'zbek tilida transkripsiya qilib ber. Boshqa ortiqcha gap yozma."},
                    {"inlineData": {"mimeType": mime_type, "data": audio_b64}}
                ]
            }],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
        }

        for m in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.gemini_api_key}"
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        return candidates[0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                logger.error(f"Transcribe error with {m}: {e}")
                continue
        return ""

    def ask_with_audio(self, user_id: int, audio_b64: str, mime_type: str = "audio/ogg", customer_name: str = "Mijoz") -> str:
        """Xaridor yuborgan ovozli xabarni eshitib javob qaytarish"""
        system_prompt = self._build_system_prompt(customer_name)

        if not self.gemini_api_key:
            return "Assalomu alaykum! Ovozli xabaringizni qabul qildim. Do'konimizda barcha sifatli mahsulotlar mavjud, sizga qaysi biri kerak?"

        models_to_try = [
            "gemini-flash-latest",
            "gemini-flash-lite-latest"
        ]

        has_history = user_id in self.conversations and len(self.conversations[user_id]) > 0
        greeting_instruction = (
            "DIQQAT: Bu mijoz bilan suhbat allaqachon boshlangan, qayta salomlashish shart emas. To'g'ridan-to'g'ri uning aytgan gapiga javob ber."
            if has_history else
            "Birinchi murojaat bo'lgani uchun samimiy 'Assalomu alaykum!' deb boshla (jinsini taxmin qilma)."
        )

        prompt_with_audio = (
            f"{system_prompt}\n\n"
            f"VAZIFA: Xaridor senga ovozli xabar (audio) yubordi. "
            f"Audiodagi har bir so'zni diqqat bilan eshit, nima so'rayotganini aniq tushun. "
            f"{greeting_instruction}\n"
            f"QAT'IY QOIDALAR:\n"
            f"- Javob hajmi aniq 2-3 jumla bo'lsin.\n"
            f"- Mijoz sotib olish niyatini bildirmaguncha manzil va telefon so'rama.\n"
            f"- Har safar bir xil qolipdagi yakun yozma.\n"
            f"- Qoldiq 2 yoki kamroq bo'lsa 'oxirgi N ta qoldi' de.\n"
            f"- Mavjud bo'lmagan o'lcham bo'lsa 'bizda faqat X, Y, Z bor' deb javob ber."
        )

        contents = []
        if user_id in self.conversations:
            for msg in self.conversations[user_id][-6:]:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        contents.append({
            "role": "user",
            "parts": [
                {"text": "Xaridorning hozirgi ovozli xabari:"},
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": audio_b64
                    }
                }
            ]
        })

        payload = {
            "system_instruction": {"parts": [{"text": prompt_with_audio}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800}
        }

        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
                resp = requests.post(url, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        reply = candidates[0]["content"]["parts"][0]["text"].strip()
                        if user_id not in self.conversations:
                            self.conversations[user_id] = []
                        self.conversations[user_id].append({"role": "user", "content": "[Xaridor ovozli xabar yubordi]"})
                        self.conversations[user_id].append({"role": "assistant", "content": reply})
                        return reply
                else:
                    logger.warning(f"Audio model {model_name} xatosi: {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                logger.error(f"Audio chaqiruvida xatolik ({model_name}): {e}")
                continue

        return "Assalomu alaykum! Ovozli xabaringizni qabul qildim. Do'konimizda siz so'ragan sifatli modellar bor, qaysi o'lcham sizga ma'qul?"

    @staticmethod
    def extract_order_data(text: str, has_pending_order: bool = False) -> Optional[Dict[str, Any]]:
        """Xabar ichidan telefon, manzil va tovar buyurtmasi mavjudligini aniqlash"""
        from services.order_matcher import OrderMatcher
        return OrderMatcher.extract_order_details(text, has_pending_order=has_pending_order)

    def _call_gemini(self, system_prompt: str, history: List[Dict[str, str]]) -> Optional[str]:
        """Google Gemini REST API chaqiruvi"""
        models_to_try = [
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-2.5-flash-lite",
            "gemini-3.8-flash"
        ]
        
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800
            }
        }

        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        return candidates[0]["content"]["parts"][0]["text"].strip()
                elif resp.status_code in [400, 401, 403]:
                    logger.warning(f"Gemini API kaliti yaroqsiz ({resp.status_code}). Zudlik bilan offline ekspert rejimiga o'tilmoqda.")
                    self._gemini_invalid = True
                    break
                elif resp.status_code == 503:
                    logger.warning(f"{model_name} band (503), keyingi modelga o'tilmoqda...")
                    continue
                else:
                    logger.warning(f"{model_name} xatosi: {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                logger.error(f"Xatolik {model_name} chaqiruvida: {e}")
                continue

        return None

    def _call_openai_compatible(self, system_prompt: str, history: List[Dict[str, str]]) -> Optional[str]:
        """OpenAI yoki Groq REST API chaqiruvi"""
        is_groq = bool(self.groq_api_key)
        api_key = self.groq_api_key if is_groq else self.openai_api_key
        url = "https://api.groq.com/openai/v1/chat/completions" if is_groq else "https://api.openai.com/v1/chat/completions"
        model = "llama-3.3-70b-versatile" if is_groq else "gpt-4o-mini"

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 800
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        return None

    def _offline_expert_fallback(self, message: str, customer_name: str, user_id: int = 0) -> str:
        """Agar API kalit kiritilmagan bo'lsa, zaxiradagi ekspert javobi"""
        from ai_engine.sales_agent import sales_agent
        reply = sales_agent.process_message(
            user_text=message,
            customer_id=user_id,
            customer_name=customer_name,
            history=self.conversations.get(user_id, [])
        )
        if user_id in self.conversations:
            self.conversations[user_id].append({"role": "assistant", "content": reply})
        return reply

ai_brain = AIBrain()
