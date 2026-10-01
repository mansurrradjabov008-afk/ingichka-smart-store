import re
from typing import Dict, Any, Optional, List
from database.db_manager import DatabaseManager

class OrderMatcher:
    """
    Intellektual Mahsulot va Buyurtma Aniqlash Tizimi:
    - Mijoz xabaridan aniq mahsulotni topish (ID, kalit so'zlar, rang, razmer, muloqot konteksti)
    - 0-ta gallutsinatsiya: Omborda bor-yo'qligini tekshirish
    - Ko'p bosqichli (multi-turn) buyurtma oqimini xatosiz yakunlash
    """

    KEYWORD_MAP = {
        16: ["termo", "termal", "waterproof", "qishki krasovka", "qishki krossovka", "suv o'tmaydigan", "термо", "красовка"],
        17: ["nike", "nayk", "sport krasovka", "air sport", "yengil krasovka", "найк"],
        18: ["ayollar krossovka", "ayollar krasovka", "ayol krasovka", "oq krasovka", "pudra krasovka"],
        19: ["charm tufli", "tufli", "klassik tufli", "charm", "туфли"],
        1: ["xudi", "hudi", "kapushon", "kapushonka", "толстовка", "худи", "qora xudi"],
        2: ["to'q ko'k xudi", "kok xudi", "ko'k xudi", "xudi m"],
        3: ["ko'ylak", "koylak", "oq ko'ylak", "oq koylak", "klassik ko'ylak", "рубашка"],
        4: ["kurtka", "koreya kurtka", "qalin kurtka", "qishki kurtka", "куртка"],
        5: ["kardigan", "ayollar kardigan", "bej kardigan", "kuzgi kardigan", "кардиган"],
        6: ["sport kostyum", "trikotaj", "ayollar sport kostyum", "pudra kostyum"],
        8: ["bolalar sportivka", "momiqli sportivka", "bolalar qishki"],
        9: ["jiletka", "nimcha", "bolalar nimcha", "issiq nimcha", "жилетка"],
        10: ["messendjer", "erkaklar sumka", "charm sumka", "planshet sumka"],
        11: ["ayollar sumka", "qo'l sumka", "sumkacha"],
        12: ["banya sochiq", "turkiya sochiq", "katta sochiq", "banya sochiqlar", "полотенец", "сочик"],
        13: ["oshxona sochiq", "oshxona sochiqlari", "6 talik sochiq"],
        14: ["jinsi", "shim", "turkiya jinsi", "ko'k jinsi", "джинсы"],
    }

    @classmethod
    def match_product(
        cls,
        text: str,
        history: Optional[List[Dict[str, str]]] = None,
        pending_product: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Mijoz yozgan matn, muloqot tarixi yoki pending zakazdan to'g'ri mahsulotni aniqlash"""
        if not text:
            return pending_product

        t_low = text.lower()

        # 1. Aniq ID orqali (#16, buy_16, id 16, 16-tovar)
        id_match = re.search(r"(?:#|buy_|id\s*|tovar\s*|mahsulot\s*)(\d{1,3})", t_low)
        if id_match:
            pid = int(id_match.group(1))
            prod = DatabaseManager.get_product_by_id(pid)
            if prod and prod.get("stock_quantity", 0) > 0:
                return prod

        # 2. Agar mijoz "1-kursatganingiz", "birinchi", "2-chi" desa
        if history:
            ord_match = cls._match_ordinal_from_history(t_low, history)
            if ord_match:
                return ord_match

        # 3. Kalit so'zlar orqali aniqlash
        best_prod_id = None
        max_score = 0

        for pid, keywords in cls.KEYWORD_MAP.items():
            score = 0
            for kw in keywords:
                if kw in t_low:
                    score += len(kw) # Uzunroq kalit so'zga kattaroq vazn
            if score > max_score:
                max_score = score
                best_prod_id = pid

        if best_prod_id and max_score >= 3:
            prod = DatabaseManager.get_product_by_id(best_prod_id)
            if prod and prod.get("stock_quantity", 0) > 0:
                return prod

        # 4. Agar foydalanuvchida oldindan tanlangan tovar (pending_product) bo'lsa
        if pending_product:
            return pending_product

        # 5. Muloqot tarixidan qidirish (agar so'nggi xabarlarda qaysidir tovar tilga olingan bo'lsa)
        if history:
            for msg in reversed(history[-4:]):
                content = msg.get("content", "").lower()
                for pid, keywords in cls.KEYWORD_MAP.items():
                    for kw in keywords:
                        if kw in content:
                            prod = DatabaseManager.get_product_by_id(pid)
                            if prod and prod.get("stock_quantity", 0) > 0:
                                return prod

        # 6. Oxirgi zaxira: Agar xaridor "krasovka" yoki "kiyim" deb umumiy aytsa
        if any(w in t_low for w in ["krasovka", "krossovka", "poyabzal"]):
            return DatabaseManager.get_product_by_id(16) # Qishki termo krasovka
        if any(w in t_low for w in ["xudi", "hudiy", "kapushon"]):
            return DatabaseManager.get_product_by_id(1)  # Turkiya xudi

        return None

    @classmethod
    def _match_ordinal_from_history(cls, text: str, history: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """1-ko'rsatganingiz, 2-chi variant kabi so'zlarni tarix orqali topish"""
        is_first = any(w in text for w in ["1-", "1 ", "birinchi", "1-si", "1-tovar", "1-kursatgan", "1-ko'rsatgan", "boshidagi"])
        is_second = any(w in text for w in ["2-", "2 ", "ikkinchi", "2-si", "2-tovar", "2-kursatgan", "2-ko'rsatgan"])

        if not (is_first or is_second):
            return None

        # Tarixning so'nggi assistent xabaridan tovarlarni qidiramiz
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                found_ids = []
                for pid, keywords in cls.KEYWORD_MAP.items():
                    for kw in keywords:
                        if kw in content.lower() and pid not in found_ids:
                            found_ids.append(pid)
                            break
                if found_ids:
                    if is_first and len(found_ids) >= 1:
                        return DatabaseManager.get_product_by_id(found_ids[0])
                    elif is_second and len(found_ids) >= 2:
                        return DatabaseManager.get_product_by_id(found_ids[1])
                    elif is_second and len(found_ids) == 1:
                        return DatabaseManager.get_product_by_id(found_ids[0])
        return None

    @classmethod
    def extract_order_details(cls, text: str, has_pending_order: bool = False) -> Optional[Dict[str, Any]]:
        """
        Xabar ichidan telefon va manzilni ajratib olish.
        Agar mijozda pending_order bo'lsa, xabarda faqat telefon va manzil bo'lishi ham yetarli!
        """
        if not text:
            return None

        t_low = text.lower()

        # Telefon raqam qidirish (+998 (90) 123-45-67, (90) 123-45-67, 90 123 45 67, 901234567, 88, 33, 77, 99)
        std_phone = None
        phone_raw = ""

        # 1. Mamlakat kodi bilan (+998 yoki 998)
        m1 = re.search(r"(\+?998[\s-]?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})", text)
        if m1:
            phone_raw = m1.group(1)
            digits = re.sub(r"\D", "", phone_raw)
            if not digits.startswith("998"):
                digits = "998" + digits
            std_phone = "+" + digits
        else:
            # 2. Operator kodi va 7 raqam: (90) 123-45-67, 90 123 45 67, 88 123 45 67
            m2 = re.search(r"(?:\+?998\s*)?(?:\(?([23789][0-9])\)?[\s-]?)(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})\b", text)
            if m2:
                phone_raw = m2.group(0)
                std_phone = f"+998{m2.group(1)}{m2.group(2)}{m2.group(3)}{m2.group(4)}"
            else:
                # 3. Ketma-ket 9 xonali son: 901234567
                m3 = re.search(r"\b([23789][0-9]\d{7})\b", text)
                if m3:
                    phone_raw = m3.group(0)
                    std_phone = f"+998{m3.group(1)}"

        if not std_phone or not phone_raw:
            return None


        # Manzil belgilari
        address_triggers = [
            "ingichka", "ko'cha", "kocha", "mahalla", "uy", "qishloq", "manzil",
            "дом", "улица", "маҳалла", "markaz", "markazi", "yonida", "ropara",
            "oldida", "maktab", "bogcha", "shifoxona", "dom"
        ]
        has_address = any(a in t_low for a in address_triggers) or len(text.strip()) > 14

        # Buyurtma niyati belgilari
        order_triggers = [
            "buyurtma", "zakaz", "olaman", "yetkazing", "olib keling", "yetkazib",
            "dostavka qiling", "доставка", "bering", "yuboring", "jo'nating", "jonating", "olmoqchiman"
        ]
        has_order_intent = any(o in t_low for o in order_triggers)

        # Agar pending_order bo'lsa yoki matnda zakaz niyati bo'lsa:
        if (has_pending_order or has_order_intent) and has_address:
            # Manzilni matndan tozalash (telefon va buyurtma fe'llarini olib tashlash)
            addr = text.replace(phone_raw, "")
            for trg in ["buyurtma", "zakaz", "olaman", "yetkazing", "olib keling", "dostavka qiling", "olmoqchiman", "bering", "yuboring"]:
                addr = re.sub(re.escape(trg), "", addr, flags=re.IGNORECASE)
            addr = re.sub(r"(?:manzilim|manzil|tel|telefon|telefonim|nomerim|nomer)\s*[:=-]?", "", addr, flags=re.IGNORECASE).strip()
            addr = re.sub(r"^[,.\s\-]+|[,.\s\-]+$", "", addr).strip()
            if not addr or len(addr) < 3:
                addr = "Ingichka markazi (Kuryer telefon orqali aniqlashtiradi)"

            return {
                "phone": std_phone,
                "address": addr,
                "is_complete": True
            }


        return None

    @classmethod
    def format_channel_post(cls, product: Dict[str, Any], bot_username: str = "Markazsavdo00_bot") -> str:
        """Telegram kanal uchun eng yuqori konversiyali chiroyli savdo posti"""
        clean_bot = bot_username.replace("@", "")
        post_text = (
            f"✨ **YANGI KELGAN TOP MAHSULOT!** ✨\n\n"
            f"🛍️ **{product['name']}**\n\n"
            f"📋 **Xususiyatlari:**\n"
            f"• 📏 **O'lchamlari:** {product['size']}\n"
            f"• 🎨 **Rangi:** {product['color']}\n"
            f"• 📂 **Kategoriya:** {product['category']}\n"
            f"• 📊 **Holati:** Omborda bor ({product['stock_quantity']} dona qoldi)\n\n"
            f"💰 **Narxi:** **{product['sale_price']:,.0f} so'm**\n\n"
            f"💎 **BIZNING KAFOLATLARIMIZ:**\n"
            f"🚗 **Ingichka bo'ylab 30-60 daqiqada MUTLAQO BEPUL yetkazamiz!**\n"
            f"👟 **2 xil razmer olib boramiz** — eshigingiz oldida kiyib ko'rib, aynan loyig'ini tanlaysiz!\n"
            f"💳 To'lovni faqat tovar yoqqanidan so'ng qilasiz (naqd yoki karta).\n\n"
            f"👇 **Hoziroq xarid qilish uchun pastdagi tugmani bosing:**"
        )
        return post_text

    @classmethod
    def format_order_confirmation(cls, order_id: int, product: Dict[str, Any], user_name: str, phone: str, address: str) -> str:
        """Xaridor uchun rasmiy chek-xabarnoma"""
        return (
            f"🎉 **Rahmat, {user_name}! Buyurtmangiz qabul qilindi!**\n\n"
            f"🧾 **Buyurtma raqami:** `#{order_id}`\n"
            f"🛍️ **Mahsulot:** **{product['name']}**\n"
            f"📏 **O'lcham / Rang:** {product['size']} | {product['color']}\n"
            f"💰 **To'lov summasi:** **{product['sale_price']:,.0f} so'm**\n"
            f"📞 **Telefon:** `{phone}`\n"
            f"📍 **Yetkazish manzili:** {address}\n\n"
            f"🚗 **Kuryerimiz Ingichka bo'ylab 30-60 daqiqada eshigingiz oldiga yetkazib boradi!**\n"
            f"Kiyib ko'rib, ma'qul bo'lsa keyin to'laysiz (naqd yoki karta). Xaridingiz barakali bo'lsin! ✨"
        )

    @classmethod
    def format_admin_alert(cls, order_id: int, product: Dict[str, Any], user_name: str, phone: str, address: str, full_raw: str = "") -> str:
        """Do'kon egasi (Admin) uchun zudlik bilan push xabarnoma"""
        return (
            f"🚨 **YANGI BUYURTMA TUSHDI! (# {order_id})**\n\n"
            f"👤 **Xaridor:** {user_name}\n"
            f"📞 **Telefon:** `{phone}`\n"
            f"📍 **Yetkazish manzili:** {address}\n"
            f"🛍️ **Mahsulot:** **{product['name']}** (ID: #{product['id']})\n"
            f"📏 **O'lcham:** {product['size']} | **Rang:** {product['color']}\n"
            f"💵 **Narxi:** **{product['sale_price']:,.0f} so'm**\n"
            f"📊 **Qoldiq:** {product.get('stock_quantity', 1) - 1} dona qoldi\n"
            f"📝 **Mijozning to'liq xabari:** {full_raw}\n\n"
            f"🚚 *Ingichka bo'yicha kuryerni tayyorlang!*"
        )


