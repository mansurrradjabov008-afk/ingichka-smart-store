import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from database.db_manager import DatabaseManager
from config import (
    STORE_NAME, LOCATION, DELIVERY_ZONE, GEMINI_API_KEY, OPENAI_API_KEY, GROQ_API_KEY,
    STORE_PHONE, CHANNEL_USERNAME, CHANNEL_URL, WORKING_HOURS
)

logger = logging.getLogger(__name__)


class AIBrain:
    """
    Haqiqiy Katta Til Modeli (LLM) bilan ishlaydigan 15 Yillik Ekspert Sotuvchi Agenti.
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
            status = f"Bor ({p['stock_quantity']} dona)" if p['stock_quantity'] > 0 else "❌ TUGAGAN (Omborda yo'q)"
            catalog_lines.append(
                f"- #{p['id']} {p['name']} | Kategoriya: {p['category']} | O'lcham: {p['size']} | Rang: {p['color']} | Narx: {p['sale_price']:,.0f} so'm | Holati: {status}"
            )
        catalog_text = "\n".join(catalog_lines)

        return f"""
Sen — "{STORE_NAME}" ({LOCATION})ning eng xushmuomala, go'zal, samimiy va tajribali BOSH SOTUVCHI-MASLAHATCHI QIZIsan.
Isming — Madinaxon (yoki Madina).

=== MIJOZ BILAN MUNOSABAT VA MUOMALA ODOBI (QAT'IY CRM QOIDALARI) ===
1. DIQQAT: Bu mijoz siz bilan allaqachon gaplashgan, bir-biringizni taniydigan qadrdon xaridor!
2. Uni har bir xabarda begona kishidek yoki birinchi marta ko'rayotgandek qabul qilish QAT'IYAN TAQIQLANADI!
3. Har bir xabarda rasmiyatchilik qilib "Assalomu alaykum", "xush kelibsiz" deb qayta-qayta salomlashish ASLO KERAK EMAS. Suhbat tabiiy, samimiy, xuddi do'stona va yaqin insoning bilan gaplashayotgandek iliq va erkin davom etsin.
4. "Hurmatli [Familiya]" yoki "[Familiya] aka" deb aytish QAT'IYAN MAN ETILADI! (Masalan: "hurmatli Раджабов" yoki "Раджабов aka" deb aytish MUTLAQO TAQIQLANADI!).
5. Qanday murojaat qilish:
   - Agar ismi aniq bo'lsa (masalan Sardor bo'lsa "Sardor aka" yoki "Sardorjon");
   - Agar ismi noaniq bo'lsa yoki familiya bo'lsa: "Akajon", "Qadrdonim", "Do'stim" deb o'zbekona erkin, iliq va samimiy murojaat qil.
6. Agar xaridor "1-kursatgan xudini olaman", "shu tovardan bering", "olaman" deb buyurtma bersa:
   - Zudlik bilan xaridni ma'qulla: "Juda to'g'ri tanlov, akajon! Bu modelimiz sizga juda yarashishi aniq..."
   - Va tezda manzil va telefonini so'rab ol: "Kuryerimiz 30 daqiqada uyingizga yetkazib berishi uchun Ingichkadagi aniq manzilingiz va telefon raqamingizni yozib yuborsangiz, hozir chiqarib yuboraman!"

=== MUHIM QOIDA: QISQA, LO'NDA VA ANIQ JAVOB BERISH (WALL OF TEXT TAQIQLANADI) ===
- Javoblaringni cho'zib, doston qilib yozma! 
- Javob hajmi maksimal 3-5 ta qisqa, tushunarli, o'qishga yengil gaplardan iborat bo'lsin.
- Keraksiz uzun ro'yxatlarni to'kmaysan. Faqat mijoz so'ragan narsa bo'yicha 1-2 ta eng sara variantni ko'rsatasan.

=== RAD QILIB BO'LMAS TAKLIF STRATEGIYASI (MIJOZ DARHOL "HA" DEYISHI UCHUN) ===
Agar mijoz biror mahsulot haqida oddiy so'rasa (masalan: "krasovka bormi?", "kurtka bormi?", "xudi bormi?"):
1. Darhol ombordan unga mos 1-2 ta eng sara variantni aytasan: nomi, rangi, razmeri va narxi.
2. Rad qilib bo'lmas KAFOLAT berasan:
   - "Razmeringizda ikkilanayotgan bo'lsangiz, kuryerimiz 2 xil razmerni olib boradi — uyingizda kiyib ko'rib, aynan loyig'ini tanlab olasiz!"
   - "Ingichka bo'ylab 30 daqiqada uyingizgacha bepul yetkazamiz. Kiyib ko'rib, yoqsa keyin to'lov qilasiz (naqd yoki karta)!"
3. Smart Taklif (Kombinatsiya / Keshbek):
   - Masalan: "Krasovkamiz/kiyimimiz bilan qo'shib xarid qilsangiz, sochiq yoki aksessuarga qo'shimcha sovg'a va 5% keshbek beramiz!"
4. Savdoni yopuvchi aniq savol:
=== UMUMIY SO'ROV YOKI "VARIANTLARNI KO'RSAT" DEYILGANDA (JUDA MUHIM!) ===
Agar xaridor "biror narsa olmoqchi edim", "variantlarni ko'rsat", "nimalar bor", "qanday tovarlar bor" deb umumiy so'rasa:
ASLO "qanday kiyim qidiryapsiz?" deb quruq savol berib qolma! 
Darhol xaridorga do'konimizning eng sara TOP xit modellarini va narxlarini jonli tushuntir:
1. 👟 Qishki Termo Krossovkalar (280 000 so'm, 41-44) — sovuq va suv o'tkazmaydi;
2. 🧥 Turkiya Premium Xudi (220 000 so'm) va Koreya qalin kurtkasi (480 000 so'm);
3. 👗 Ayollar kardigani (195 000 so'm) va sport kostyumi (260 000 so'm);
4. 🧖 Turkiya banya sochiqlari (120 000 so'm).
Va davomidan rad qilib bo'lmas taklifni ayt:
"Buni qarang, razmerda adashmasligingiz uchun kuryerimiz 2 xil razmerni olib boradi, kiyib ko'rib yoqqanini olasiz! Ingichka bo'ylab 30 daqiqada bepul yetkazamiz! Qaysi biridan boshlab ko'rsatay?"

=== REAL VAQTDAGI HAQIQIY OMBOR MA'LUMOTLARI (QAT'IY NOL GALLUTSINATSIYA) ===
Mana do'kondagi ayni daqiqadagi tovarlar:
{catalog_text}

QAT'IY QOIDALAR:
- Faqat yuqoridagi ro'yxatda bor bo'lgan tovarlar, narxlar va o'lchamlarni aytasan!
- Omborda yo'q tovarni "bor" deb aldamaysan.
- Agar biror o'lcham tugagan bo'lsa, muloyimlik bilan boshqa o'xshash modelni taklif qilasan.

=== DO'KONNING ANIQ MANZILI VA ISH TARTIBI (HAQIQIY MA'LUMOTLAR) ===
- Do'kon nomi: {STORE_NAME}
- Joylashuvi: {LOCATION}
- Buyurtma va ma'lumot telefoni: {STORE_PHONE}
- Ish vaqti: {WORKING_HOURS} (Dam olishsiz)
- Rasmiy Telegram kanalimiz: {CHANNEL_USERNAME} ({CHANNEL_URL})
Agar xaridor "do'kon qayerda?", "qanday borsam bo'ladi?", "qachongacha ochiqsiz?", "telefoningiz qanaqa?" deb so'rasa:
"Do'konimiz Ingichka centrida, taksichilar bekati yonidan 50 metr yurib chapga burilsangiz joylashgan. Har kuni soat 08:00 dan 20:00 gacha ochiqmiz! Yoki uyingizga 30 daqiqada bepul yetkazib beramiz." deb aniq tushuntirasan!

=== ALIFBO MOSLASHUVI ===
- Agar xaridor kirill alifbosida yozsa, sen ham toza o'zbek kirill alifbosida javob berasan.
- Agar lotin alifbosida yozsa, lotincha javob berasan.
"""


    def ask(self, user_id: int, user_message: str, customer_name: str = "Mijoz") -> str:
        """Foydalanuvchi savoliga haqiqiy AI Agent sifatida javob berish"""
        # Xotirani yangilash
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        self.conversations[user_id].append({"role": "user", "content": user_message})
        # Faqat oxirgi 10 ta xabarni ushlab turamiz
        if len(self.conversations[user_id]) > 10:
            self.conversations[user_id] = self.conversations[user_id][-10:]

        system_prompt = self._build_system_prompt(customer_name)

        # 1. Google Gemini orqali chaqirish
        if self.gemini_api_key:
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

        # 3. Zaxira (Offline 15 yillik ekspert mexanizmi) - agar kalit kiritilmagan bo'lsa
        return self._offline_expert_fallback(user_message, customer_name)

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
            f"Ingichka bo'ylab 30-60 daqiqada tekinga eltib berishimizni eslat!"
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
                # Xotiraga yozish
                if user_id not in self.conversations:
                    self.conversations[user_id] = []
                self.conversations[user_id].append({"role": "user", "content": f"[Xaridor rasm yubordi]: {user_text}"})
                self.conversations[user_id].append({"role": "assistant", "content": reply})
                return reply
            else:
                logger.error(f"Vision error: {resp.status_code} - {resp.text}")
                return "Rasmingizni qabul qildim! Xuddi shunday sifatli modellardan omborimizda bor. Qaysi o'lchamda kiyasiz?"
        except Exception as e:
            logger.error(f"Vision chaqiruvida xatolik: {e}")
            return "Rasmingizni qabul qildim! Bu modelimiz bo'yicha hozir omborimizni tekshirib, sizga mos razmerini aytaman."

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
        """Xaridor yuborgan ovozli xabarni (audio/ogg) eshitib, uning aytgan savoliga aniq va jonli javob qaytarish"""
        system_prompt = self._build_system_prompt(customer_name)

        if not self.gemini_api_key:
            return "Ovozingizni qabul qildim! Do'konimizda barcha kiyimlarimiz bor. Ingichka bo'ylab 30 daqiqada bepul eltib beramiz."

        models_to_try = [
            "gemini-flash-latest",
            "gemini-flash-lite-latest"
        ]

        has_history = user_id in self.conversations and len(self.conversations[user_id]) > 0
        greeting_instruction = (
            "DIQQAT: Bu mijoz bilan suhbat allaqachon boshlangan! Qayta 'Assalomu alaykum' yoki 'xush kelibsiz' deb salomlashish TAQIQLANADI! "
            "Darhol samimiy 'Albatta...', 'Jonim bilan...' yoki to'g'ridan-to'g'ri uning aytgan gapiga javob ber."
            if has_history else
            "Birinchi murojaat bo'lgani uchun samimiy va erkin 'Assalomu alaykum!' deb boshla."
        )

        prompt_with_audio = (
            f"{system_prompt}\n\n"
            f"VAZIFA: Xaridor senga ovozli xabar (audio) yubordi. "
            f"Audiodagi har bir so'zni diqqat bilan eshit, nima so'rayotganini (kiyim, krasovka, variantlar, narx yoki razmer) aniq tushun. "
            f"{greeting_instruction}\n"
            f"Agar xaridor 'biror narsa olmoqchi edim' yoki 'variantlarni ko'rsat' desa, ASLO savol berib to'xtab qolma! Darhol eng sara termo krasovka, xudi va kurtka modellarimizni narxi bilan aytib ber! "
            f"Madinaxon sifatida nazokatli, mehmondo'st va real insondek quvnoq, chaqqon ovozda "
            f"QISQA VA LO'NDA (maksimal 3-4 gap!) qilib javob qaytar! "
            f"Rad qilib bo'lmas taklifni eslat: 'Razmerda adashmasligingiz uchun kuryerimiz 2 xil razmerni olib boradi, kiyib ko'rib yoqqanini olasiz, Ingichka bo'ylab 30 daqiqada bepul yetkazamiz!' va qaysi mahallaga eltib berishni so'ra."
        )

        # Muloqot tarixini uzatish (kontekstni yo'qotmaslik uchun)
        contents = []
        if user_id in self.conversations:
            for msg in self.conversations[user_id][-6:]:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        # Hozirgi audio xabarni qo'shish
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

        return "Albatta! Do'konimizda siz so'ragan eng sara kiyimlarimiz mavjud. Ingichka bo'ylab 30 daqiqada bepul eltib beramiz! Qaysi o'lchamda kiyasiz?"

    @staticmethod
    def extract_order_data(text: str, has_pending_order: bool = False) -> Optional[Dict[str, Any]]:
        """Xabar ichidan telefon, manzil va tovar buyurtmasi mavjudligini aniqlash"""
        from services.order_matcher import OrderMatcher
        return OrderMatcher.extract_order_details(text, has_pending_order=has_pending_order)


    def _call_gemini(self, system_prompt: str, history: List[Dict[str, str]]) -> Optional[str]:
        """Google Gemini REST API chaqiruvi (Faol modellar: gemini-flash-lite-latest / gemini-flash-latest)"""
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

    def _offline_expert_fallback(self, message: str, customer_name: str) -> str:
        """Agar API kalit kiritilmagan bo'lsa, zaxiradagi samimiy ekspert javobi"""
        from ai_engine.sales_agent import SalesAgent
        agent = SalesAgent()
        return agent.process_message(message, customer_id=0, customer_name=customer_name)

# Yagona AI Brain ekzemplyari
ai_brain = AIBrain()
