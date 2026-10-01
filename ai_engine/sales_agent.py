import os
import re
from typing import Dict, Any, List, Optional
from database.db_manager import DatabaseManager
from ai_engine.sales_persona import SALES_EXPERT_SYSTEM_PROMPT
from config import STORE_NAME, LOCATION, DELIVERY_ZONE, CATEGORIES

class SalesAgent:
    """
    15 yillik tajribali o'zbek sotuvchi-menejeri kognitiv tizimi.
    Nol gallutsinatsiya (Grounding) kafolati bilan ishlaydi.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    def process_message(self, user_text: str, customer_id: int, customer_name: str = "Hurmatli mijoz", context: Optional[Dict] = None) -> str:
        """
        Mijoz xabarini tahlil qilib, 15 yillik tajribali sotuvchi sifatida mukammal o'zbekcha javob berish.
        """
        text_lower = user_text.lower().strip()

        # 1. Salomlashish va kirish
        if any(w in text_lower for w in ["salom", "assalom", "qalesiz", "yaxshimisiz", "bormisiz"]):
            return (
                f"Assalomu alaykum, {customer_name}! Xush kelibsiz.\n\n"
                f"Bizning 'Ingichka Baraka Savdo Markazi' do'konimizda erkaklar, ayollar, bolalar kiyimlari, "
                f"chiroyli sumkalar va sifatli Turkiya sochiqlari bor.\n\n"
                f"Aynan kim uchun kiyim yoki narsa qidiryapsiz? O'zim sizga eng yaxshisini tanlashda yordam beraymi?"
            )

        # 2. Buyurtma berish / Telefon / Manzil / Aniq zakaz aniqlansa (ENG YUQORI USTUVORLIK)
        phone_match = re.search(r"(\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}|\b\d{9}\b)", text_lower)
        if phone_match or any(w in text_lower for w in ["buyurtma", "zakaz", "olaman", "yetkazib bering", "olib keling", "manzil:"]):
            return (
                f"Ajoyib tanlov! Buyurtmangiz qabul qilinmoqda. 🛍️\n\n"
                f"Ingichka shaharchasi bo'yicha kuryerimiz 30-60 daqiqada eshigingiz oldiga yetkazib boradi.\n"
                f"Siz bilan telefon orqali bog'lanib, buyurtmani tasdiqlaymiz.\n\n"
                f"🚗 *Kuryerimiz yetib borgach, kiyib ko'rasiz va ma'qul bo'lsa, to'lovni (naqd yoki karta orqali) amalga oshirasiz.*"
            )

        # 3. Yetkazib berish (Dostavka) haqidagi umumiy savol
        if any(w in text_lower for w in ["dostavka", "yetkazish", "olib kelish", "qayergacha"]) or ("ingichka" in text_lower and not phone_match):
            return (
                f"Ha, albatta! Biz aynan **{LOCATION}** bo'ylab buyurtmangizni 30-60 daqiqa ichida eshigingiz oldigacha "
                f"**mutlaqo bepul** yetkazib beramiz! 🚗💨\n\n"
                f"Kuryerimiz olib boradi, bemalol kiyib, ko'rib tekshirasiz, ma'qul bo'lsa keyin to'lov qilasiz (naqd yoki karta orqali). "
                f"Qaysi tovarimizni ko'rib beray?"
            )

        # 3. Narxlar va e'tirozlar ("qimmat", "arzon")
        if any(w in text_lower for w in ["qimmat", "narxi baland", "arzonroq"]):
            return (
                f"To'g'ri aytasiz, har bir inson puliga yarasha sifatli narsa olishni xohlaydi. 😊\n\n"
                f"Lekin bizning tovarlarimiz arzon sintetikadan emas, toza Turkiya va Koreya paxtasidan tikilgan. "
                f"Yuvganda rangi o'chmaydi, cho'zilib ketmaydi. Bozordan har 2 oyda yangisini olgandan ko'ra, "
                f"bu kiyimlarimiz sizga yillab xizmat qiladi.\n\n"
                f"Ustiga-ustak Ingichka bo'ylab bepul olib boramiz, kiyib ko'rib o'zingiz baho berasiz. Qaysi modelimizni o'lchamini bilmoqchisiz?"
            )

        # 4. Bot / AI Agent holati haqida savol berilsa
        if any(w in text_lower for w in ["ai agent", "ishlayaptimi", "ishlaysanmi", "botmisan", "kimsan", "robotmisan"]):
            return (
                f"Assalomu alaykum! Ha, albatta, men 24/7 rejimda to'liq ishlayapman! 😊\n\n"
                f"Men **{STORE_NAME}**ning 15 yillik tajribaga ega AI sotuvchi-menejeriman.\n"
                f"Do'konimizdagi barcha erkaklar, ayollar, bolalar kiyimlari, zamonaviy sumkalar va sifatli Turkiya sochiqlari bo'yicha xizmatingizdaman.\n\n"
                f"🚗 *Ingichka bo'ylab 30-60 daqiqada eshigingizgacha bepul yetkazib beramiz! Sizga qanday kiyim yoki mahsulot kerak?*"
            )

        # 5. Kategoriya yoki Mahsulot bo'yicha aniq qidiruv
        found_category = None
        if "erkak" in text_lower:
            found_category = "Erkaklar kiyimi"
        elif "ayol" in text_lower or "ko'ylak" in text_lower or "kardigan" in text_lower:
            found_category = "Ayollar kiyimi"
        elif "bola" in text_lower or "qizim" in text_lower or "o'g'lim" in text_lower:
            found_category = "Bolalar kiyimi"
        elif "sumka" in text_lower or "kamar" in text_lower:
            found_category = "Sumkalar va aksessuarlar"
        elif "sochiq" in text_lower or "vanna" in text_lower:
            found_category = "Sochiqlar va uy to'qimachiligi"

        # Aniq mahsulot qidirish (xudi, kurtka, ko'ylak, sportivka, sumka, sochiq, jiletka)
        search_terms = ["xudi", "kurtka", "ko'ylak", "sportivka", "sumka", "sochiq", "jiletka", "jinsi", "shim"]
        matched_term = next((term for term in search_terms if term in text_lower), None)

        # FAQAT KATEGORIYA YOKI MAXSULOT NOMI BO'LSAGINA TOVARLAR CHIQARILADI
        if found_category or matched_term:
            products = DatabaseManager.get_products(
                category=found_category,
                search_query=matched_term,
                in_stock_only=True
            )

            if products:
                reply = [f"Aynan siz so'ragan eng sifatli modellarimizdan hozir omborda borlari bilan tanishtiraman:\n"]
                for idx, p in enumerate(products[:4], 1):
                    reply.append(
                        f"✨ **{idx}. {p['name']}**\n"
                        f"   • O'lchami: {p['size']} | Rangi: {p['color']}\n"
                        f"   • Narxi: **{p['sale_price']:,.0f} so'm**\n"
                        f"   • Tavsifi: {p['description']}\n"
                        f"   • Omborda: {p['stock_quantity']} dona qolgan\n"
                    )

                reply.append(
                    f"💡 *Ingichka bo'yicha 30 daqiqada eshigingizgacha yetkazamiz! Bularning qaysi biri sizga ko'proq ma'qul bo'lyapti, razmerini ajratib qo'yaymi?*"
                )
                return "\n".join(reply)

        # 5. Buyurtma berish / Telefon / Manzil yozilgan holat
        phone_match = re.search(r"(\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}|\b\d{9}\b)", text_lower)
        if phone_match or any(w in text_lower for w in ["buyurtma", "zakaz", "olaman", "yetkazing", "manzilim", "ko'cha"]):
            return (
                f"Ajoyib tanlov! Buyurtmangizni darhol rasmiylashtiramiz. 🛍️\n\n"
                f"Ingichka shaharchasi bo'yicha kuryerimiz tezda yetkazib borishi uchun menga quyidagilarni yozib yuborsangiz kifoya:\n"
                f"1️⃣ Tanlagan kiyimingiz nomi, o'lchami va rangi;\n"
                f"2️⃣ Ingichkadagi aniq manzilingiz (mahalla, ko'cha yoki mo'ljal);\n"
                f"3️⃣ Bog'lanish uchun telefon raqamingiz.\n\n"
                f"To'lovni kiyim yetib borgach, kiyib ko'rganingizdan keyin qilsangiz ham bo'ladi (naqd yoki karta)."
            )

        # 6. Umumiy / Boshqa holatlar uchun mehmondo'st professional sotuvchi javobi
        all_cats = "\n".join([f"  • {c}" for c in CATEGORIES])
        return (
            f"Albatta, qadrdonim! Do'konimizda barcha turdagi sifatli mahsulotlar mavjud:\n\n"
            f"{all_cats}\n\n"
            f"Sizga aynan qaysi biri qiziq yoki qanday o'lcham va rangdagi kiyim qidiryapsiz? Aytsangiz, hozir ombordagi eng saralarini rasmlari va narxlari bilan ajratib beraman."
        )

    @staticmethod
    def parse_product_voice_text(transcription: str) -> Dict[str, Any]:
        """
        Ovoz yoki yozuv orqali aytilgan tovar ma'lumotlarini qirqib olib, bazaga qo'shish formati.
        Masalan: "Turkiya xudi, qora rang, L razmer, 140 ming tan narxi, 220 ming sotuv, 10 dona keldi"
        """
        # Standart qolipni tahlil qilish
        t_low = transcription.lower()
        
        # Narxlarni topish
        prices = [int(p) for p in re.findall(r"(\d+)\s*(?:ming|000)", t_low)]
        cost_price = prices[0] * 1000 if len(prices) > 0 else 100000
        sale_price = prices[1] * 1000 if len(prices) > 1 else (cost_price * 1.5)

        # Sonini topish
        qty_match = re.search(r"(\d+)\s*(?:ta|dona|shtuk)", t_low)
        stock_qty = int(qty_match.group(1)) if qty_match else 5

        # Razmer
        size = "M"
        for s in ["xxl", "xl", "xs", "l", "m", "s", "42", "44", "46", "48", "50", "standart"]:
            if s in t_low:
                size = s.upper()
                break

        # Rang
        color = "Klassik"
        for c in ["qora", "oq", "ko'k", "qizil", "sariq", "yashil", "kulrang", "jigarrang", "pushti"]:
            if c in t_low:
                color = c.capitalize()
                break

        # Kategoriya aniqlash
        category = "Erkaklar kiyimi"
        if "ayol" in t_low or "ko'ylak" in t_low:
            category = "Ayollar kiyimi"
        elif "bola" in t_low:
            category = "Bolalar kiyimi"
        elif "sumka" in t_low:
            category = "Sumkalar va aksessuarlar"
        elif "sochiq" in t_low:
            category = "Sochiqlar va uy to'qimachiligi"

        name = transcription.split(",")[0].strip() if "," in transcription else transcription[:40].strip()

        return {
            "name": name.capitalize(),
            "category": category,
            "size": size,
            "color": color,
            "cost_price": float(cost_price),
            "sale_price": float(sale_price),
            "stock_quantity": stock_qty,
            "description": transcription
        }
