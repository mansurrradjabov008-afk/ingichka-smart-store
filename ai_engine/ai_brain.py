import os
import re
import json
import logging
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from config import (
    STORE_NAME, GEMINI_API_KEY, OPENAI_API_KEY, GROQ_API_KEY,
    STORE_PHONE, CHANNEL_USERNAME, ADMIN_TELEGRAM_IDS
)
from database.db_manager import DatabaseManager
from services.catalog_service import (
    search_products, load_products, load_store_info, SEARCH_PRODUCTS_TOOL_SCHEMA
)

logger = logging.getLogger(__name__)

class AIBrain:
    """
    Intellektual LLM Savdo Maslahatchisi.
    Barcha tovarlar products.json orqali search_products vositasidan olinadi.
    Do'kon shartlari store_info.json orqali beriladi.
    Muloqot xotirasi har bir chat_id uchun oxirgi 10 ta xabarni saqlaydi.
    """

    def __init__(self):
        # Muloqot xotirasi: chat_id -> List[Dict[str, str]]
        self.conversations: Dict[int, List[Dict[str, str]]] = {}
        self.gemini_api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.groq_api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        self.operator_requests: List[Dict[str, Any]] = []

    def set_api_key(self, key: str, provider: str = "gemini") -> bool:
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

    @staticmethod
    def detect_language(text: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Foydalanuvchi tilini aniqlash:
        'uz_latn' (O'zbek lotin), 'uz_cyrl' (O'zbek kirill), 'ru' (Rus tili)
        """
        t_low = text.lower()
        combined = t_low
        if history:
            user_msgs = [m.get("content", "").lower() for m in history if m.get("role") == "user"]
            combined = " ".join(user_msgs[-3:] + [t_low])

        # Rus tili belgilari
        ru_words = [
            "здравствуйте", "привет", "есть", "цена", "доставка", "какие", "хочу",
            "размер", "куртка", "кроссовки", "джинсы", "белые", "черные", "сколько",
            "стоит", "купить", "пожалуйста", "оплата", "возврат", "оператор", "человек"
        ]
        if any(w in combined for w in ru_words):
            return "ru"

        # O'zbek kirill belgilari
        cyrl_chars = re.findall(r"[а-яА-ЯёЁўЎқҚғҒҳҲ]", combined)
        uz_cyrl_specific = ["борми", "қандай", "неча", "қанча", "етказиб", "кийим", "салом", "олмоқчи", "рахмат", "пул"]
        if any(w in combined for w in uz_cyrl_specific):
            return "uz_cyrl"
        if len(cyrl_chars) > len(text) * 0.3 and len(cyrl_chars) > 3:
            # Agar ruscha so'z bo'lmasa, kirill yozuvidagi o'zbek tili
            return "uz_cyrl"

        # Standart: O'zbek lotin
        return "uz_latn"

    @staticmethod
    def is_operator_request(text: str) -> bool:
        """Foydalanuvchi jonli odam/operator so'raganini aniqlash"""
        t_low = text.lower()
        triggers = [
            "operator", "odam", "jonli inson", "admin", "rahbar", "direktor",
            "bog'lang", "boglang", "telefon bering", "operatorga ula", "operator kerak",
            "odam bilan", "operator bilan", "inson bilan", "оператор", "живой человек",
            "админ", "позови человека", "человека"
        ]
        return any(trg in t_low for trg in triggers)

    @staticmethod
    def check_store_info_inquiry(text: str, lang: str) -> Optional[str]:
        """
        Yetkazib berish, to'lov, qaytarish, ish vaqti va manzil
        haqidagi savollarga store_info.json dan javob berish.
        """
        t_low = text.lower()
        info = load_store_info()
        if not info:
            return None

        # 1. Yetkazib berish (Delivery)
        if any(w in t_low for w in ["yetkazib", "dostavka", "yetkazish", "етказиб", "доставка", "доставк"]):
            d = info.get("delivery", {})
            return d.get(lang, d.get("uz_latn", ""))

        # 2. To'lov (Payment)
        if any(w in t_low for w in ["to'lov", "tolov", "to'lash", "kartadan", "click", "payme", "тўлов", "оплата", "оплатить"]):
            p = info.get("payment", {})
            return p.get(lang, p.get("uz_latn", ""))

        # 3. Qaytarish / Almashtirish (Return / Exchange)
        if any(w in t_low for w in ["qaytar", "almashtir", "qaytarsa", "almashtirsa", "қайтар", "алмаштир", "возврат", "обмен", "вернуть"]):
            r = info.get("return_policy", {})
            return r.get(lang, r.get("uz_latn", ""))

        # 4. Ish vaqti (Working hours)
        if any(w in t_low for w in ["ish vaqti", "ochiq", "soat nechagacha", "иш вақти", "время работы", "график"]):
            w = info.get("working_hours", {})
            return w.get(lang, w.get("uz_latn", ""))

        # 5. Manzil / Qayerda joylashgan (Address)
        if any(w in t_low for w in ["manzil", "qayerda", "lokatsiya", "qayerdasiz", "манзил", "қаерда", "где находитесь", "адрес"]):
            a = info.get("address", {})
            return a.get(lang, a.get("uz_latn", ""))

        return None

    def _build_system_prompt(self) -> str:
        return f"""
Sen — "{STORE_NAME}" do'konining professional va samimiy BOSH SOTUVCHI-MASLAHATCHISIsan.

=== QAT'IY QOIDALAR (SYSTEM PROMPT RULES) ===
1. TILING VA USLUB (LANGUAGE & STYLE):
   - Xaridor qaysi tilda yozsa, aynan o'sha tilda javob ber (O'zbek lotin, O'zbek kirill yoki Rus tili).
   - Qisqa va lo'nda javob ber: QAT'IY 2-3 TA JUMLA (gap).
   - Har safar bir xil qolipdagi yakun yozma, muloqotni turli xil, samimiy va jonli yakunla.
   - Mijozga 'Assalomu alaykum' deb murojaat qil, jinsini aslo taxmin qilma (hech qachon 'Akajon', 'Opajon' dema).
   - Bir safarda FAQAT BITTA savol ber (one question at a time).
   - Xaridor allaqachon javob bergan savolni ASLO qaytadan so'rama.

2. VOSITA VA MAHSULOTLAR (TOOL USAGE & GROUNDING):
   - Har qanday tovar qidiruvi uchun FAQAT `search_products(query, category, size, color, max_price)` vositasini chaqirasan.
   - FAQAT VA FAQAT vosita qaytargan natijalar asosida javob berasan! O'zingdan hech qachon tovar, narx yoki o'lcham to'qib chiqarma (Never invent products, prices or sizes).
   - Agar biror tovar qoldig'i 2 yoki kamroq bo'lsa, 'oxirgi N ta qoldi' deb ayt (masalan: 'oxirgi 1 ta qoldi', 'oxirgi 2 ta qoldi').
   - Agar so'ralgan o'lcham (razmer) bazada bo'lmasa, 'bizda faqat X, Y, Z bor' deb mavjud o'lchamlarni bildir.
   - Agar so'ralgan tovar topilmasa (`found: false`), aniq qilib ayt:
     * O'zbekcha: "Afsuski, hozir yo'q", so'ng katalogdagi eng yaqin real alternativ tovarlarni taklif qil.
     * Ruscha: "К сожалению, сейчас нет в наличии", затем предложи ближайшую реальную альтернативу из каталога.

3. SAVDO BOSQICHLARI (SALES FLOW):
   - Bosqichlar ketma-ketligi: Ehtiyoj (need) -> O'lcham/Rang (size/color) -> Narx (price) -> Tasdiqlash (confirm) -> Telefon va manzil (phone & address).
   - FAQAT VA FAQAT xaridor sotib olishga rozi bo'lganidan so'ng ("ha", "olaman", "zakaz qilaylik" degandan keyin) telefon raqami va manzilini so'ra! Ungacha aslo so'rama.

4. DO'KON SHARTLARI (DELIVERY, PAYMENT, RETURN):
   - Yetkazib berish, to'lov va qaytarish bo'yicha savollarga store_info.json ma'lumotlaridan javob ber. Agar ma'lumot bo'lmasa, "Buni egasidan so'rab aytaman" deb javob ber.

5. OPERATOR / JONLI INSON SO'RALGANDA:
   - Agar xaridor operator yoki jonli odam bilan gaplashmoqchi bo'lsa, "Operatorga ulayman" deb javob ber.
"""

    def ask(self, chat_id: int, user_message: str, customer_name: str = "Mijoz") -> str:
        """
        Foydalanuvchi xabarini tahlil qilib, oxirgi 10 ta xabar tarixi bilan birga
        LLM vositasi (search_products) va qoidalar asosida javob qaytarish.
        """
        if chat_id not in self.conversations:
            self.conversations[chat_id] = []

        # 1. Xabarni tarixga qo'shish
        self.conversations[chat_id].append({"role": "user", "content": user_message})

        # Oxirgi 10 ta xabar (Conversation memory per chat_id)
        history = self.conversations[chat_id][-10:]

        # Foydalanuvchi tilini aniqlash
        lang = self.detect_language(user_message, history)

        # 2. Qoida: Operator / Jonli odam so'ralganda
        if self.is_operator_request(user_message):
            self.operator_requests.append({
                "chat_id": chat_id,
                "user_name": customer_name,
                "message": user_message
            })
            if lang == "ru":
                reply = "Operatorga ulayman. Наш сотрудник свяжется с вами в ближайшее время."
            elif lang == "uz_cyrl":
                reply = "Operatorga ulayman. Тез орада ходимимиз сиз билан боғланади."
            else:
                reply = "Operatorga ulayman. Tez orada xodimimiz siz bilan bog'lanadi."

            self.conversations[chat_id].append({"role": "assistant", "content": reply})
            return reply

        # 3. Qoida: Do'kon shartlari (Yetkazib berish, to'lov, qaytarish)
        store_reply = self.check_store_info_inquiry(user_message, lang)
        if store_reply:
            self.conversations[chat_id].append({"role": "assistant", "content": store_reply})
            return store_reply

        # 4. Google Gemini chaqiruvi (Haqiqiy Gemini 3.5/3.6/3.8 Flash modeli)
        if self.gemini_api_key and not getattr(self, '_gemini_invalid', False):
            gemini_res = self._call_gemini(user_message, history, lang)
            if gemini_res:
                self.conversations[chat_id].append({"role": "assistant", "content": gemini_res})
                return gemini_res

        # 5. Tashqi LLM chaqiruvlari (Groq yoki OpenAI)
        if self.groq_api_key or self.openai_api_key:
            llm_res = self._call_cloud_llm(user_message, history)
            if llm_res:
                self.conversations[chat_id].append({"role": "assistant", "content": llm_res})
                return llm_res

        # 6. Ichki Intellektual Tool-Calling Agenti (Deterministik va Kafolatlangan 0-Gallutsinatsiya)
        reply = self._run_grounded_tool_agent(user_message, history, lang, customer_name, chat_id)
        self.conversations[chat_id].append({"role": "assistant", "content": reply})

        # Tarix hajmini nazorat qilish
        if len(self.conversations[chat_id]) > 20:
            self.conversations[chat_id] = self.conversations[chat_id][-20:]

        return reply

    def _call_gemini(self, user_message: str, history: List[Dict[str, str]], lang: str) -> Optional[str]:
        """Google Gemini API (gemini-3.5-flash, gemini-3.6-flash, gemini-3.8-flash) chaqiruvi"""
        if not self.gemini_api_key:
            return None

        products = load_products()
        store_info = load_store_info()
        catalog_str = json.dumps(products, ensure_ascii=False, indent=2)
        store_str = json.dumps(store_info, ensure_ascii=False, indent=2)

        system_instruction = f"""Sen — "{STORE_NAME}" do'konining professional va samimiy BOSH SOTUVCHI-MASLAHATCHISIsan.

=== QAT'IY QOIDALAR (SYSTEM PROMPT RULES) ===
1. TILING VA USLUB (LANGUAGE & STYLE):
   - Xaridor qaysi tilda yozsa, aynan o'sha tilda javob ber (O'zbek lotin, O'zbek kirill yoki Rus tili).
   - Qisqa va lo'nda javob ber: QAT'IY 2-3 TA JUMLA (gap).
   - Har safar bir xil qolipdagi yakun yozma, muloqotni turli xil, samimiy va jonli yakunla.
   - Mijozga 'Assalomu alaykum' deb murojaat qil, jinsini aslo taxmin qilma (hech qachon 'Akajon', 'Opajon' dema).
   - Bir safarda FAQAT BITTA savol ber (one question at a time).
   - Xaridor allaqachon javob bergan savolni ASLO qaytadan so'rama.

2. VOSITA VA MAHSULOTLAR (GROUNDING):
   - FAQAT VA FAQAT quyidagi do'kon katalogida (products.json) bor tovarlar, narxlar va o'lchamlar asosida javob berasan! O'zingdan hech qachon tovar, narx yoki o'lcham to'qib chiqarma (Never invent products, prices or sizes).
   - Agar biror tovar qoldig'i 2 yoki kamroq bo'lsa, 'oxirgi N ta qoldi' deb ayt (masalan: 'oxirgi 1 ta qoldi', 'oxirgi 2 ta qoldi').
   - Agar so'ralgan o'lcham (razmer) bazada bo'lmasa, 'bizda faqat X, Y, Z bor' deb mavjud o'lchamlarni bildir.
   - Agar so'ralgan tovar bo'lmasa, aniq qilib ayt:
     * O'zbekcha: "Afsuski, hozir yo'q", so'ng katalogdagi eng yaqin real muqobilni taklif qil.
     * Ruscha: "К сожалению, сейчас нет в наличии", затем предложи ближайшую реальную альтернативу из каталога.

3. SAVDO BOSQICHLARI (SALES FLOW):
   - Bosqichlar: Ehtiyoj -> O'lcham/Rang -> Narx -> Tasdiqlash -> Telefon va manzil.
   - FAQAT VA FAQAT xaridor sotib olishga rozi bo'lganidan so'ng ("ha", "olaman", "zakaz qilaylik" degandan keyin) telefon raqami va manzilini so'ra! Ungacha aslo manzil va telefon so'rama.

4. DO'KON SHARTLARI (store_info.json):
   - Yetkazib berish, to'lov va qaytarish bo'yicha savollarga do'kon shartlaridan javob ber. Agar biror sozlama bo'sh bo'lsa, "Buni egasidan so'rab aytaman" de.

5. OPERATOR / JONLI INSON SO'RALGANDA:
   - "Operatorga ulayman" deb javob ber.

6. JAVOB FORMATI:
   - FAQAT xaridorga qaratilgan toza yakuniy matnni yoz!
   - Hech qanday "Sentence 1", "Sales Flow", rejalashtirish yoki texnik izohlar yozish QAT'IYAN TAQIQLANADI!
   - To'g'ridan-to'g'ri mijozga aytiladigan gapni yoz.

DO'KON MAHSULOTLARI (products.json):
{catalog_str}

DO'KON SHARTLARI (store_info.json):
{store_str}
"""

        # Format history for Gemini API
        contents = []
        for m in history:
            role = "user" if m.get("role") == "user" else "model"
            text_part = m.get("content", "").strip()
            if text_part:
                contents.append({"role": role, "parts": [{"text": text_part}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": user_message}]}]

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 350
            }
        }

        models_to_try = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.6-flash",
            "gemini-3.8-flash",
            "gemini-3.5-flash"
        ]
        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
                resp = requests.post(url, json=payload, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"].strip()
                            clean_text = re.sub(r"(?i)^(?:sentence\s*\d*|step\s*\d*|thought|stage\s*\d*|bosqich\s*\d*|sales\s*flow)\s*(?:\([^)]*\))?\s*:\s*", "", raw_text)
                            lines = clean_text.splitlines()
                            valid_lines = []
                            for line in lines:
                                stripped = line.strip()
                                if "->" in stripped and ("Need" in stripped or "Size" in stripped or "Ehtiyoj" in stripped or "Rang" in stripped):
                                    continue
                                if re.match(r"(?i)^(?:sentence\s*\d*|step\s*\d*|sales\s*flow|bosqich\s*\d*)\s*:", stripped):
                                    continue
                                valid_lines.append(line)
                            result = "\n".join(valid_lines).strip()
                            if result:
                                return result
                elif resp.status_code in [429, 503]:
                    logger.info(f"{model_name} ({resp.status_code}), next modelga o'tilmoqda...")
                    continue
                elif resp.status_code in [400, 401, 403]:
                    logger.warning(f"Gemini API key error ({resp.status_code}): {resp.text[:100]}")
                    break
            except Exception as e:
                logger.error(f"Error calling {model_name}: {e}")
                continue

        return None

    def _call_cloud_llm(self, user_message: str, history: List[Dict[str, str]]) -> Optional[str]:
        """Groq yoki OpenAI API orqali Function Calling (Tool Call) bilan chaqirish"""
        api_key = self.groq_api_key or self.openai_api_key
        is_groq = bool(self.groq_api_key)
        url = "https://api.groq.com/openai/v1/chat/completions" if is_groq else "https://api.openai.com/v1/chat/completions"
        model = "llama-3.3-70b-versatile" if is_groq else "gpt-4o-mini"

        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "tools": [SEARCH_PRODUCTS_TOOL_SCHEMA],
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 400
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                msg = data["choices"][0]["message"]
                tool_calls = msg.get("tool_calls", [])
                
                if tool_calls:
                    # Tool call bajarish
                    tool_call = tool_calls[0]
                    fn_name = tool_call["function"]["name"]
                    fn_args = json.loads(tool_call["function"]["arguments"])
                    
                    if fn_name == "search_products":
                        tool_res = search_products(**fn_args)
                        
                        # Tool natijasini LLM ga qaytarish
                        messages.append(msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": "search_products",
                            "content": json.dumps(tool_res, ensure_ascii=False)
                        })
                        
                        second_payload = {
                            "model": model,
                            "messages": messages,
                            "temperature": 0.3,
                            "max_tokens": 400
                        }
                        resp2 = requests.post(url, headers=headers, json=second_payload, timeout=15)
                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            return data2["choices"][0]["message"]["content"].strip()
                else:
                    return msg.get("content", "").strip()
        except Exception as e:
            logger.error(f"Cloud LLM call error: {e}")

        return None

    def _run_grounded_tool_agent(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        lang: str,
        customer_name: str,
        chat_id: int
    ) -> str:
        """
        Kafolatlangan Intellektual Tool-Calling Agenti:
        1. Xabardan qidiruv parametrlarini ajratadi.
        2. search_products vositasini chaqiradi.
        3. FAQAT vosita natijalaridan va savdo qoidalaridan kelib chiqib javob shakllantiradi.
        """
        text_lower = user_message.lower().strip()

        # Tarixdan oldingi xabarlarni birlashtirish
        history_text = " ".join([m.get("content", "").lower() for m in history[:-1]])

        # 1. Salomlashish
        if any(w in text_lower for w in ["salom", "assalom", "здравствуйте", "привет", "ассалому"]):
            if len(text_lower.split()) <= 3:
                if lang == "ru":
                    return "Здравствуйте! Добро пожаловать в магазин Ingichka Baraka Savdo. Какую одежду или обувь вы ищете?"
                elif lang == "uz_cyrl":
                    return f"Ассалому алайкум! Ingichka Baraka Savdo дўконимизга хуш келибсиз. Қандай кийим ёки пойабзал қидиряпсиз?"
                else:
                    return f"Assalomu alaykum! Ingichka Baraka Savdo do'konimizga xush kelibsiz. Qanday kiyim yoki poyabzal qidiryapsiz?"

        # 2. Xarid niyati va Tasdiqlash (Agreement to buy) tekshiruvi
        # Qoida: Faqat xaridor sotib olishga rozi bo'lgandan keyin telefon va manzil so'rash
        phone_match = re.search(r"(\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}|\b\d{9}\b)", text_lower)
        has_address = any(a in text_lower for a in ["ko'cha", "kocha", "mahalla", "uy", "qishloq", "manzil", "markaz", "toshkent", "samarqand", "дом", "улица"]) or len(user_message.strip()) > 20

        # Agar xaridor telefon va manzilini yuborgan bo'lsa
        if phone_match and has_address:
            # DB ga buyurtma yozish
            return self._format_order_received(lang, customer_name)

        # Xaridni tasdiqlash so'zlari
        agreement_triggers = ["ha", "olaman", "zakaz", "buyurtma", "bering", "yetkazing", "tasdiqlayman", "да", "беру", "заказываю", "купить", "бер"]
        # Agar oldingi suhbatda tovar tanlangan bo'lsa va xaridor rozi bo'lsa
        is_agreeing = any(re.search(rf"\b{re.escape(w)}\b", text_lower) for w in agreement_triggers)
        has_product_in_context = any(p in (history_text + " " + text_lower) for p in ["krossovka", "krasovka", "kurtka", "futbolka", "ko'ylak", "jinsi", "palto", "kepka", "кроссовк", "куртк", "плать"])

        if is_agreeing and has_product_in_context and not any(w in text_lower for w in ["bormi", "qancha", "narxi", "qanday"]):
            if lang == "ru":
                return "Отличный выбор! Для оформления заказа, пожалуйста, напишите ваш номер телефона и адрес доставки."
            elif lang == "uz_cyrl":
                return "Ажойиб танлов! Буюртмани расмийлаштириш учун телефон рақамингиз ва манзилингизни ёзиб юборинг."
            else:
                return "Ajoyib tanlov! Buyurtmani rasmiylashtirish uchun telefon raqamingiz va manzilingizni yozib yuboring."

        # 3. Parametrlarni ajratish va search_products chaqirish
        extracted_query, extracted_cat, extracted_size, extracted_color, extracted_max_price = self._extract_tool_args(user_message, history)

        # Vosita chaqiruvi (Tool call)
        tool_result = search_products(
            query=extracted_query,
            category=extracted_cat,
            size=extracted_size,
            color=extracted_color,
            max_price=extracted_max_price
        )

        # 4. Javobni FAQAT vosita natijalaridan shakllantirish
        return self._format_tool_response(
            user_message=user_message,
            tool_result=tool_result,
            history=history,
            lang=lang,
            customer_name=customer_name
        )

    @staticmethod
    def _extract_tool_args(text: str, history: List[Dict[str, str]]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[float]]:
        """Xabar va kontekstdan search_products parametrlarini ajratish"""
        t_low = text.lower()
        hist_low = " ".join([m.get("content", "").lower() for m in history[-3:]])

        # 1. Query (Mahsulot nomi yoki alias)
        query = None
        keywords_map = {
            "krossovka": ["krasovka", "krossovka", "krasovki", "krossovki", "кроссовк", "sneaker", "oyoq kiyim", "poyabzal"],
            "kurtka": ["kurtka", "куртка", "jacket"],
            "futbolka": ["futbolka", "футболк", "t-shirt", "mayka"],
            "jinsi": ["jinsi", "shim", "джинсы", "брюки", "jeans"],
            "ko'ylak": ["ko'ylak", "koylak", "платье", "dress"],
            "palto": ["palto", "пальто", "coat"],
            "kepka": ["kepka", "кепка", "бейсболка", "cap"],
            "sport kostyum": ["sportivka", "sport kostyum", "спортивка"]
        }
        for canon, aliases in keywords_map.items():
            if any(a in t_low for a in aliases):
                query = canon
                break
        
        # Agar joriy xabarda tovar aytilmagan bo'lsa, tarixdan qidirish
        if not query:
            for canon, aliases in keywords_map.items():
                if any(a in hist_low for a in aliases):
                    query = canon
                    break

        # Maxsus: do'konda yo'q tovarlar so'rovi (butsa, kitob, telefon...)
        if not query:
            no_stock_words = ["butsa", "бутсы", "kitob", "книга", "telefon", "телефон", "soat", "часы", "noutbuk"]
            for w in no_stock_words:
                if w in t_low:
                    query = w
                    break

        # 2. Category
        category = None
        if any(w in t_low for w in ["ayol", "ayollar", "xotinim", "ayolim", "onam", "qizim", "женск"]):
            category = "Ayollar kiyimi"
        elif any(w in t_low for w in ["erkak", "erkaklar", "erim", "otam", "o'zim", "мужск"]):
            category = "Erkaklar kiyimi"

        # 3. Size
        size = None
        size_match = re.search(r"\b(xxl|xl|xs|s|m|l|30|32|34|40|41|42|43|44|46|48|50)\b", t_low)
        if size_match:
            size = size_match.group(1).upper()
        elif "razmer" in hist_low:
            h_match = re.search(r"\b(xxl|xl|xs|s|m|l|30|32|34|40|41|42|43|44|46|48|50)\b", hist_low)
            if h_match:
                size = h_match.group(1).upper()

        # 4. Color (Faqat to'liq so'z chegarasi bilan)
        color = None
        colors = {
            "qora": [r"\bqora\b", r"\bчерный\b", r"\bчерная\b", r"\bчерные\b", r"\bчерного\b"],
            "oq": [r"\boq\b", r"\bбелый\b", r"\bбелая\b", r"\bбелые\b", r"\bбелого\b"],
            "qizil": [r"\bqizil\b", r"\bкрасный\b", r"\bкрасная\b", r"\bкрасные\b", r"\bкрасного\b"],
            "bej": [r"\bbej\b", r"\bбежевый\b", r"\bбежевая\b", r"\bбежевое\b"],
            "ko'k": [r"\bko'k\b", r"\bkok\b", r"\bсиний\b", r"\bсиняя\b", r"\bсиние\b"]
        }
        for c_canon, c_patterns in colors.items():
            if any(re.search(pat, t_low) for pat in c_patterns):
                color = c_canon
                break

        # 5. Max price
        max_price = None
        price_match = re.search(r"(\d+(?:\s*\d{3})*)\s*(?:ming|000|k)?\s*(?:so['`]?mgacha|gacha|до)", t_low)
        if price_match:
            raw = re.sub(r"\s+", "", price_match.group(1))
            val = float(raw)
            if val < 1000:
                val *= 1000
            max_price = val

        return query, category, size, color, max_price

    def _format_tool_response(
        self,
        user_message: str,
        tool_result: Dict[str, Any],
        history: List[Dict[str, str]],
        lang: str,
        customer_name: str
    ) -> str:
        """
        System prompt qoidalari asosida javob shakllantirish:
        - Faqat vosita natijasidan javob berish.
        - Agar topilmasa: "Afsuski, hozir yo'q", so'ng yaqin real alternativ.
        - Maksimal 3 ta jumla.
        - Bir safarda faqat 1 ta savol.
        - Foydalanuvchi javob bergan savolni qaytarmaslik.
        """
        t_low = user_message.lower()
        hist_text = " ".join([m.get("content", "").lower() for m in history])

        # 1. Agar tovar topilmagan bo'lsa (found: False)
        if not tool_result.get("found"):
            alts = tool_result.get("closest_alternatives", [])
            alt_names = [f"'{p['name']}' ({p['price']:,.0f} so'm)" for p in alts[:2]]
            alt_text = " yoki ".join(alt_names) if alt_names else "boshqa sifatli kiyimlarimiz"

            if lang == "ru":
                alt_names_ru = [f"'{p['name']}' ({p['price']:,.0f} сум)" for p in alts[:2]]
                alt_text_ru = " или ".join(alt_names_ru)
                return f"К сожалению, сейчас нет в наличии. Могу предложить отличную альтернативу: {alt_text_ru}. Хотите посмотреть?"
            elif lang == "uz_cyrl":
                return f"Афсуски, ҳозир йўқ. Лекин бизда муқобил сифатли {alt_text} бор. Қайси бирини кўриб чиқамиз?"
            else:
                return f"Afsuski, hozir yo'q. Lekin do'konimizda muqobil sifatli {alt_text} mavjud. Qaysi birini ko'rib chiqamiz?"

        # 2. Tovar topilgan holat
        products = tool_result.get("products", [])
        
        # Umumiy assortiment so'rovi
        if any(w in t_low for w in ["что у вас", "что есть", "қандай кийимлар", "qanday kiyimlar", "nimalar bor", "barcha tovarlar"]):
            if lang == "ru":
                return "В нашем магазине Ingichka Baraka Savdo есть мужская и женская одежда, куртки, джинсы, платья, пальто и кроссовки. Какая именно категория вас интересует?"
            elif lang == "uz_cyrl":
                return "Ingichka Baraka Savdo дўконимизда эркаклар ва аёллар кийимлари, курткалар, шимлар, кўйлак ва кроссовкалар бор. Сизга қайси турдаги кийим керак?"
            else:
                return "Ingichka Baraka Savdo do'konimizda erkaklar va ayollar kiyimlari, kurtkalar, shimlar, ko'ylaklar va krossovkalar mavjud. Sizga qaysi turdagi kiyim kerak?"

        # Narx bo'yicha filtr so'ralgan bo'lsa
        if any(w in t_low for w in ["gacha", "arzon", "до"]):
            lines = [f"{idx}. {p['name']} ({p['price']:,.0f} so'm)" for idx, p in enumerate(products[:3], 1)]
            listing = ", ".join(lines)
            if lang == "ru":
                return f"В этом ценовом диапазоне у нас есть: {listing}. Какой вариант вам больше нравится?"
            elif lang == "uz_cyrl":
                return f"Ушбу нарх оралиғида бизда қуйидагилар бор: {listing}. Қайси бири сизга маъқул?"
            else:
                return f"Bu narx oralig'ida do'konimizda quyidagilar mavjud: {listing}. Qaysi biri sizga ma'qul?"

        # Agar kategoriya bo'yicha bir nechta tovar bo'lsa (masalan ayollar kiyimi, xotinimga)
        if len(products) > 1 and not any(w in t_low for w in ["krossovka", "krasovka", "kurtka", "futbolka", "ko'ylak", "koylak", "jinsi", "palto", "kepka"]):
            prod_names = [f"'{p['name']}' ({p['price']:,.0f} so'm)" for p in products[:2]]
            listing = " va ".join(prod_names)
            if lang == "ru":
                prod_names_ru = [f"'{p['name']}' ({p['price']:,.0f} сум)" for p in products[:2]]
                listing_ru = " и ".join(prod_names_ru)
                return f"В этой категории у нас есть: {listing_ru}. Какой фасон, цвет или размер вы ищете?"
            elif lang == "uz_cyrl":
                return f"Ушбу бўлимда бизда {listing} бор. Сизга қайси фасон, ранг ёки ўлчам маъқул?"
            else:
                return f"Bu bo'limda do'konimizda {listing} mavjud. Sizga ko'proq qaysi fason, rang yoki o'lcham ma'qul?"

        # Aniq 1 ta tovar
        prod = products[0]
        p_name = prod["name"]
        p_price = f"{prod['price']:,.0f}"
        p_sizes = ", ".join(prod["sizes"])
        p_colors = ", ".join(prod["colors"])
        p_stock = prod.get("stock_status", "")

        # Foydalanuvchi allaqachon aytgan parametrlar
        already_has_size = any(s.lower() in (hist_text + " " + t_low) for s in prod["sizes"])
        already_has_color = any(c.lower() in (hist_text + " " + t_low) for c in prod["colors"])
        is_asking_price = any(w in t_low for w in ["narxi", "qancha", "necha", "цена", "почем", "сколько"])

        # Agar faqat narxini so'ragan bo'lsa
        if is_asking_price:
            if lang == "ru":
                return f"Цена {p_name} составляет {p_price} сум ({p_stock}). Хотите оформить заказ?"
            elif lang == "uz_cyrl":
                return f"{p_name} нархи {p_price} сўм ({p_stock}). Буюртма расмийлаштирамизми?"
            else:
                return f"{p_name} narxi {p_price} so'm ({p_stock}). Buyurtma rasmiylashtiraylikmi?"

        # Savdo bosqichi: Ehtiyoj -> O'lcham/Rang -> Narx -> Tasdiqlash
        # Agar o'lcham va rang aytilmagan bo'lsa, bittasini so'rash (one question at a time)
        if not already_has_size and len(prod["sizes"]) > 1:
            if lang == "ru":
                return f"Да, у нас есть {p_name}! Доступные размеры: {p_sizes}, цена {p_price} сум ({p_stock}). Какой размер вам нужен?"
            elif lang == "uz_cyrl":
                return f"Ҳа, дўконимизда {p_name} бор! Ўлчамлари: {p_sizes}, нархи {p_price} сўм ({p_stock}). Сизга қайси ўлчам тўғри келади?"
            else:
                return f"Ha, do'konimizda {p_name} bor! O'lchamlari: {p_sizes}, narxi {p_price} so'm ({p_stock}). Sizga qaysi o'lcham to'g'ri keladi?"

        if not already_has_color and len(prod["colors"]) > 1:
            if lang == "ru":
                return f"Отлично! Доступные цвета для {p_name}: {p_colors}. Какой цвет предпочитаете?"
            elif lang == "uz_cyrl":
                return f"Ажойиб! {p_name} учун мавжуд ранглар: {p_colors}. Қайси рангни танлайсиз?"
            else:
                return f"Ajoyib! {p_name} uchun mavjud ranglar: {p_colors}. Qaysi rangni tanlaysiz?"

        # O'lcham va rang allaqachon ma'lum -> Tasdiqlash savoli
        if lang == "ru":
            return f"Отлично, {p_name} в наличии ({p_stock}), цена {p_price} сум. Оформляем заказ?"
        elif lang == "uz_cyrl":
            return f"Ажойиб, {p_name} омборда бор ({p_stock}), нархи {p_price} сўм. Буюртмани расмийлаштирамизми?"
        else:
            return f"Ajoyib, {p_name} omborda bor ({p_stock}), narxi {p_price} so'm. Xarid qilishni tasdiqlaysizmi?"

    @staticmethod
    def _format_order_received(lang: str, customer_name: str) -> str:
        if lang == "ru":
            return "Спасибо! Ваш заказ принят. Мы свяжемся с вами в ближайшее время для подтверждения."
        elif lang == "uz_cyrl":
            return "Раҳмат! Буюртмангиз қабул қилинди. Тез орада буюртмани тасдиқлаш учун боғланамиз."
        else:
            return "Rahmat! Buyurtmangiz qabul qilindi. Tez orada buyurtmani tasdiqlash uchun bog'lanamiz."

ai_brain = AIBrain()
