import re
from typing import Dict, Any, Optional, List, Tuple
from database.db_manager import DatabaseManager

class OrderMatcher:
    """
    Intellektual Mahsulot va Buyurtma Aniqlash Tizimi:
    - Mijoz xabaridan aniq mahsulotni topish (ID, kalit so'zlar, rang, razmer, muloqot konteksti)
    - 0-ta gallutsinatsiya: Omborda bor-yo'qligini tekshirish
    - Narx bo'yicha filtrda bazadagi barcha mos mahsulotlarni kod orqali chiqarish (Qoida 4)
    - Jami summani kod orqali hisoblash (Qoida 5)
    - Kam qolgan tovar uchun 'oxirgi N ta qoldi' deyish (Qoida 3)
    - Mavjud bo'lmagan o'lcham uchun 'bizda faqat X, Y, Z bor' deyish (Qoida 7)
    - Ko'p bosqichli buyurtma oqimini xatosiz yakunlash
    """

    WORD_TO_NUM = {
        "bitta": 1, "bir dona": 1, "bir ta": 1, "bir": 1,
        "ikkita": 2, "ikki dona": 2, "ikki": 2,
        "uchta": 3, "uch dona": 3, "uch": 3,
        "to'rtta": 4, "tortta": 4, "toʻrtta": 4, "to‘rtta": 4, "to’rtta": 4, "to'rt": 4, "tort": 4,
        "beshta": 5, "besh dona": 5, "besh": 5,
        "oltita": 6, "olti dona": 6, "olti": 6,
        "yettita": 7, "yetti dona": 7, "yetti": 7,
        "sakkizta": 8, "sakkiz dona": 8, "sakkiz": 8,
        "to'qqizta": 9, "toqqizta": 9, "to'qqiz": 9,
        "o'nta": 10, "onta": 10, "o'n": 10
    }

    KEYWORD_MAP = {
        1: ["qora kurtka", "erkaklar kurtka", "erkaklar qora kurtkasi", "kurtka", "qora kurtkasi", "куртка"],
        2: ["oversize futbolka", "oq futbolka", "qora futbolka", "futbolka", "futbolkasi", "футболка"],
        3: ["klassik jinsi shim", "jinsi shim", "jinsi", "shim", "ko'k jinsi", "klassik jinsi", "джинсы"],
        4: ["ayollar gulli ko'ylagi", "gulli ko'ylak", "gulli koylak", "ayollar ko'ylagi", "ko'ylak", "koylak", "платье"],
        5: ["sport kostyum", "sportivka", "kostyum", "kulrang kostyum", "спортивка", "костюм"],
        6: ["ayollar qishki paltosi", "qishki palto", "bej palto", "ayollar paltosi", "palto", "пальто"],
        7: ["kepka", "qora kepka", "oq kepka", "bita", "кепка"],
        8: ["krossovka", "krasovka", "oq krossovka", "oq krasovka", "sport krossovka", "poyabzal", "красовка", "кроссовки"],
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

        # 1a. SKU orqali aniqlash (KK-1002, KK 1002, KK-1025)
        sku_match = re.search(r"\b(?:kk[-_\s]?)(\d{4})\b", t_low)
        if sku_match:
            sku_target = f"KK-{sku_match.group(1)}"
            all_p = DatabaseManager.get_products(in_stock_only=False)
            for p in all_p:
                if p.get("sku") == sku_target or sku_target.lower() in (p.get("description") or "").lower():
                    return p

        # 1b. Aniq ID orqali (#16, buy_16, id 16, 16-tovar)
        id_match = re.search(r"(?:#|buy_|id\s*|tovar\s*|mahsulot\s*)(\d{1,3})", t_low)
        if id_match:
            pid = int(id_match.group(1))
            prod = DatabaseManager.get_product_by_id(pid)
            if prod:
                return prod

        # 2. Agar mijoz "1-kursatganingiz", "birinchi", "2-chi" desa
        if history:
            ord_match = cls._match_ordinal_from_history(t_low, history)
            if ord_match:
                return ord_match

        # 3. Dinamik ko'p parametrli qidiruv (Barcha 49 ta tovar bo'yicha)
        all_prods = DatabaseManager.get_products(in_stock_only=False)
        best_dyn_prod = None
        best_dyn_score = 0

        for p in all_prods:
            p_name = p.get("name", "").lower()
            p_cat = p.get("category", "").lower()
            p_color = p.get("color", "").lower()
            p_brand = (p.get("brand") or "").lower()
            p_desc = (p.get("description") or "").lower()

            score = 0
            if p_name and p_name in t_low:
                score += 60
            if p_brand and p_brand in t_low:
                score += 30
            if p_cat and p_cat in t_low:
                score += 20
            if p_color and p_color in t_low:
                score += 15
            for w in t_low.split():
                if len(w) >= 4 and (w in p_name or w in p_desc):
                    score += 8

            if p.get("stock_quantity", 0) > 0 and score > 0:
                score += 5

            if score > best_dyn_score:
                best_dyn_score = score
                best_dyn_prod = p

        if best_dyn_prod and best_dyn_score >= 25:
            return best_dyn_prod

        # 4. Agar foydalanuvchida oldindan tanlangan tovar (pending_product) bo'lsa
        if pending_product:
            return pending_product

        # 5. Muloqot tarixidan qidirish
        if history:
            for msg in reversed(history[-4:]):
                content = msg.get("content", "").lower()
                for p in all_prods:
                    if p.get("name", "").lower() in content:
                        return p

        # 6. Umumiy kategoriya bo'yicha zaxira (ombordagi birinchi mavjud tovar)
        cat_triggers = {
            "futbolka": "Futbolka",
            "jinsi": "Jinsi",
            "ko'ylak": "Ko'ylak",
            "koylak": "Ko'ylak",
            "kurtka": "Kurtka",
            "palto": "Palto",
            "paypoq": "Paypoq",
            "kepka": "Kepka",
            "ichki kiyim": "Ichki kiyim",
            "shim": "Shim"
        }
        for kw, cat_name in cat_triggers.items():
            if kw in t_low:
                cat_prods = [p for p in all_prods if p.get("category") == cat_name and p.get("stock_quantity", 0) > 0]
                if cat_prods:
                    return cat_prods[0]

        return None

    @classmethod
    def _match_ordinal_from_history(cls, text: str, history: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        is_first = any(w in text for w in ["1-", "1 ", "birinchi", "1-si", "1-tovar", "1-kursatgan", "1-ko'rsatgan", "boshidagi"])
        is_second = any(w in text for w in ["2-", "2 ", "ikkinchi", "2-si", "2-tovar", "2-kursatgan", "2-ko'rsatgan"])

        if not (is_first or is_second):
            return None

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

    # === QOIDA 4: NARX BO'YICHA FILTR (KOD FILTRLAYDI, AI EMAS) ===
    @classmethod
    def parse_price_filter(cls, text: str) -> Optional[Dict[str, float]]:
        """
        Mijoz xabaridan narx filtr parametrlarini ajratish.
        Masalan: "300 minggacha nimalar bor?", "200 000 dan arzon mahsulotlar", "100 mingdan 300 minggacha"
        """
        if not text:
            return None
        t_low = text.lower().strip()

        # Buyurtma berish niyatida bo'lsa filtr emas
        if any(w in t_low for w in ["olaman", "zakaz", "sotib olaman", "bering"]) and not any(w in t_low for w in ["gacha", "arzon", "kam", "oraliq"]):
            return None

        # 1. Oraliq (min va max narx): "100 mingdan 300 minggacha", "100 000 dan 300 000 gacha"
        range_match = re.search(r"(\d+(?:\s*\d{3})*)\s*(?:ming|000|k)?\s*(?:dan|-)\s*(\d+(?:\s*\d{3})*)\s*(?:ming|000|k)?\s*(?:gacha|oraliqida|orasida)", t_low)
        if range_match:
            n1_str = re.sub(r"\s+", "", range_match.group(1))
            n2_str = re.sub(r"\s+", "", range_match.group(2))
            n1 = float(n1_str)
            n2 = float(n2_str)
            if n1 < 1000:
                n1 *= 1000
            if n2 < 1000:
                n2 *= 1000
            min_p = min(n1, n2)
            max_p = max(n1, n2)
            return {"min_price": min_p, "max_price": max_p}

        # 2. Maksimal chegara: "300 minggacha", "200 000 dan arzon", "100 mingdan kam"
        max_patterns = [
            r"(\d+(?:\s*\d{3})*)\s*(?:ming|000|k)?\s*(?:so['`]?mgacha|somgacha|gacha|dan\s*arzon|dan\s*kam|arzonroq|past)",
            r"(?:narxi\s*)?(\d+(?:\s*\d{3})*)\s*(?:ming|000|k)?\s*gacha",
            r"(?:kamida\s*)?(\d+(?:\s*\d{3})*)\s*(?:ming|000|k)?\s*(?:dan\s*kam)",
        ]
        for pat in max_patterns:
            m = re.search(pat, t_low)
            if m:
                n_str = re.sub(r"\s+", "", m.group(1))
                n = float(n_str)
                if n < 1000:
                    n *= 1000
                return {"min_price": 0.0, "max_price": n}

        # 3. Faqat "eng arzon tovarlar", "arzon mahsulotlar" so'ralsa
        if any(w in t_low for w in ["eng arzon", "arzon tovarlar", "arzon mahsulotlar", "arzon kiyimlar", "arzonroq narsalar"]):
            return {"min_price": 0.0, "max_price": 200000.0}

        return None

    @classmethod
    def filter_products_by_price(cls, min_price: float = 0, max_price: float = float("inf")) -> List[Dict[str, Any]]:
        """
        Bazadagi BARCHA mos mahsulotlarni Python va SQL orqali filtrlaydi (AI emas).
        """
        all_prods = DatabaseManager.get_products(in_stock_only=True)
        matched = []
        for p in all_prods:
            price = float(p.get("sale_price", 0))
            if min_price <= price <= max_price:
                matched.append(p)
        matched.sort(key=lambda x: x.get("sale_price", 0))
        return matched

    @classmethod
    def format_price_filter_response(cls, products: List[Dict[str, Any]], min_price: float, max_price: float) -> str:
        """
        Qoida 4 va Qoida 3 ga binoan:
        - Bazadagi BARCHA mos mahsulotni ko'rsatadi (kod formatlaydi)
        - Qoldiq 2 yoki kamroq bo'lsa 'oxirgi N ta qoldi' deydi
        - Javob 2-3 jumla (Qoida 2)
        """
        if not products:
            if max_price < float("inf"):
                return f"Bu narx oralig'ida hozirda mahsulotlar mavjud emas. Boshqa narxdagi tovarlarimizni ko'rishni xohlaysizmi?"
            return "Hozirda omborda tovarlar topilmadi. Tez orada yangi mahsulotlar keladi."

        lines = []
        for idx, p in enumerate(products, 1):
            stock = p.get("stock_quantity", 0)
            if stock <= 2 and stock > 0:
                stock_str = f"oxirgi {stock} ta qoldi"
            else:
                stock_str = f"{stock} ta bor"
            lines.append(f"{idx}. {p['name']} ({p['size']}) — {p['sale_price']:,.0f} so'm ({stock_str})")

        listing = "\n".join(lines)
        return (
            f"Siz so'ragan narx oralig'ida do'konimizda quyidagi mahsulotlar mavjud:\n"
            f"{listing}\n"
            f"Qaysi biri sizga ma'qul bo'ldi?"
        )

    # === QOIDA 5: JAMI SUMMANI KOD HISOBLAYDI ===
    @classmethod
    def calculate_quote(cls, text: str) -> Optional[str]:
        """
        Qoida 5: Jami summani kod hisoblaydi (AI arifmetika qilmaydi).
        Masalan: "2 ta kurtka qancha bo'ladi?", "ikkita kepka narxi qancha?", "3 ta kepka narxi qancha?"
        """
        if not text:
            return None
        t_low = text.lower()

        is_asking_total = any(w in t_low for w in ["qancha", "necha pul", "jami", "bo'ladi", "boladi", "summa", "narxi", "qanchadan"])
        if not is_asking_total:
            return None

        qty = None
        # 1. Raqamlar orqali qidirish: "2 ta", "3 dona"
        qty_match = re.search(r"(\d+)\s*(?:ta|dona|shtuk)", t_low)
        if qty_match:
            qty = int(qty_match.group(1))
        else:
            # 2. So'z bilan yozilgan sonlar: "ikkita", "uchta", "bitta", "to'rtta"
            for word, val in cls.WORD_TO_NUM.items():
                if re.search(rf"\b{re.escape(word)}\b", t_low):
                    qty = val
                    break

        if qty and qty > 0:
            prod = cls.match_product(text)
            if prod:
                total_sum = qty * float(prod["sale_price"])
                stock = prod.get("stock_quantity", 0)
                stock_info = f" (oxirgi {stock} ta qoldi)" if stock <= 2 and stock > 0 else ""
                return (
                    f"{qty} ta {prod['name']} jami {total_sum:,.0f} so'm bo'ladi{stock_info}. "
                    f"Xarid qilish niyatida bo'lsangiz, buyurtmani rasmiylashtirib berishim mumkin."
                )
        return None

    # === QOIDA 7: MAVJUD BO'LMAGAN O'LCHAM UCHUN 'BIZDA FAQAT X, Y, Z BOR' DEYISH ===
    @classmethod
    def check_size_inquiry(cls, text: str) -> Optional[str]:
        """
        Qoida 7: Mavjud bo'lmagan o'lcham uchun 'bizda faqat X, Y, Z bor' deydi.
        Masalan: "Kurtkadan XXL bormi?", "Futbolkadan 48 razmer bormi?"
        """
        if not text:
            return None
        t_low = text.lower()

        size_patterns = [
            r"\b(xxxl|xxl|xl|xs|s|m|l)\b",
            r"\b(\d{2})\s*(?:razmer|o['`]?lcham|razmeri)?\b"
        ]
        asked_size = None
        for pat in size_patterns:
            m = re.search(pat, t_low)
            if m:
                val = m.group(1).upper()
                if val.isdigit() and int(val) in [28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 48, 50, 52, 54]:
                    asked_size = val
                    break
                elif not val.isdigit():
                    asked_size = val
                    break

        if asked_size and any(w in t_low for w in ["bormi", "bormikin", "qoldimi", "razmer"]):
            prod = cls.match_product(text)
            if prod:
                avail_raw = prod.get("size", "")
                avail_list = [s.strip().upper() for s in avail_raw.split(",") if s.strip()]
                if avail_list and (asked_size not in avail_list and "UNIVERSAL" not in avail_list):
                    sizes_str = ", ".join(avail_list)
                    return f"Kechirasiz, {prod['name']} mahsulotimizda bunday o'lcham yo'q, bizda faqat {sizes_str} bor."
        return None

    # === BUYURTMA MA'LUMOTLARINI AJRATISH (Qoida 1: Faqat xarid niyati bo'lganda) ===
    @classmethod
    def extract_order_details(cls, text: str, has_pending_order: bool = False) -> Optional[Dict[str, Any]]:
        """
        Xabar ichidan telefon, manzil va miqdorni aniq ajratib olish.
        Qoida 1: Faqat mijoz sotib olish niyatini bildirganida yoki pending buyurtmasi bo'lganda ishlaydi.
        """
        if not text:
            return None

        t_low = text.lower()

        # Telefon raqam qidirish
        std_phone = None
        phone_raw = ""

        m1 = re.search(r"(\+?998[\s-]?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})", text)
        if m1:
            phone_raw = m1.group(1)
            digits = re.sub(r"\D", "", phone_raw)
            if not digits.startswith("998"):
                digits = "998" + digits
            std_phone = "+" + digits
        else:
            m2 = re.search(r"(?:\+?998\s*)?(?:\(?([23789][0-9])\)?[\s-]?)(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})\b", text)
            if m2:
                phone_raw = m2.group(0)
                std_phone = f"+998{m2.group(1)}{m2.group(2)}{m2.group(3)}{m2.group(4)}"
            else:
                m3 = re.search(r"\b([23789][0-9]\d{7})\b", text)
                if m3:
                    phone_raw = m3.group(0)
                    std_phone = f"+998{m3.group(1)}"

        if not std_phone or not phone_raw:
            return None

        address_triggers = [
            "ko'cha", "kocha", "mahalla", "uy", "qishloq", "manzil",
            "дом", "улица", "маҳалла", "markaz", "markazi", "yonida", "ropara",
            "oldida", "maktab", "bogcha", "shifoxona", "dom"
        ]
        has_address = any(a in t_low for a in address_triggers) or len(text.strip()) > 14

        order_triggers = [
            "buyurtma", "zakaz", "olaman", "yetkazing", "olib keling", "yetkazib",
            "bering", "yuboring", "jo'nating", "jonating", "olmoqchiman", "sotib olaman"
        ]
        has_order_intent = any(o in t_low for o in order_triggers)

        if (has_pending_order or has_order_intent) and has_address:
            # Miqdorni aniqlash (Default 1)
            qty = 1
            qty_match = re.search(r"(\d+)\s*(?:ta|dona|shtuk)", t_low)
            if qty_match:
                qty = max(1, int(qty_match.group(1)))
            else:
                for word, val in cls.WORD_TO_NUM.items():
                    if re.search(rf"\b{re.escape(word)}\b", t_low):
                        qty = val
                        break

            # Toza manzilni ajratish
            manzil_m = re.search(r"(?:manzil(?:im)?|adres(?:im)?)\s*[:=-]?\s*([^,\n\r]+)", text, flags=re.IGNORECASE)
            if manzil_m:
                addr = manzil_m.group(1).strip()
            else:
                addr = text.replace(phone_raw, "")
                for trg in ["buyurtma", "zakaz", "olaman", "yetkazing", "olib keling", "olmoqchiman", "bering", "yuboring", "sotib olaman"]:
                    addr = re.sub(re.escape(trg), "", addr, flags=re.IGNORECASE)
                prod = cls.match_product(text)
                if prod:
                    addr = re.sub(re.escape(prod["name"]), "", addr, flags=re.IGNORECASE)
                for w in cls.WORD_TO_NUM.keys():
                    addr = re.sub(rf"\b{re.escape(w)}\b", "", addr, flags=re.IGNORECASE)
                addr = re.sub(r"(?:manzilim|manzil|tel|telefon|telefonim|nomerim|nomer)\s*[:=-]?", "", addr, flags=re.IGNORECASE).strip()
                addr = re.sub(r"^[,.\s\-]+|[,.\s\-]+$", "", addr).strip()

            if not addr or len(addr) < 3:
                addr = "Markaz (Kuryer telefon orqali aniqlashtiradi)"

            return {
                "phone": std_phone,
                "address": addr,
                "quantity": qty,
                "is_complete": True
            }

        return None

        return None

    @classmethod
    def format_channel_post(cls, product: Dict[str, Any], bot_username: str = "Markazsavdo00_bot") -> str:
        """Telegram kanal uchun savdo posti"""
        stock = product.get("stock_quantity", 0)
        stock_text = f"oxirgi {stock} ta qoldi" if stock <= 2 and stock > 0 else f"{stock} dona bor"
        post_text = (
            f"✨ **YANGI KELGAN TOP MAHSULOT!** ✨\n\n"
            f"🛍️ **{product['name']}**\n\n"
            f"📋 **Xususiyatlari:**\n"
            f"• 📏 **O'lchamlari:** {product['size']}\n"
            f"• 🎨 **Rangi:** {product['color']}\n"
            f"• 📂 **Kategoriya:** {product['category']}\n"
            f"• 📊 **Holati:** Omborda bor ({stock_text})\n\n"
            f"💰 **Narxi:** **{product['sale_price']:,.0f} so'm**\n\n"
            f"To'lovni tovar yoqqanidan so'ng qilasiz (naqd yoki karta).\n\n"
            f"👇 **Xarid qilish uchun pastdagi tugmani bosing:**"
        )
        return post_text

    @classmethod
    def format_order_confirmation(cls, order_id: int, product: Dict[str, Any], user_name: str, phone: str, address: str) -> str:
        """Xaridor uchun rasmiy chek-xabarnoma (Qoida 6: Assalomu alaykum deb murojaat qil, jinsini taxmin qilma)"""
        greeting = f"Assalomu alaykum, {user_name}!" if user_name and user_name != "Mijoz" else "Assalomu alaykum!"
        return (
            f"🎉 **{greeting} Buyurtmangiz qabul qilindi!**\n\n"
            f"🧾 **Buyurtma raqami:** `#{order_id}`\n"
            f"🛍️ **Mahsulot:** **{product['name']}**\n"
            f"📏 **O'lcham / Rang:** {product['size']} | {product['color']}\n"
            f"💰 **To'lov summasi:** **{product['sale_price']:,.0f} so'm**\n"
            f"📞 **Telefon:** `{phone}`\n"
            f"📍 **Manzil:** {address}\n\n"
            f"Buyurtmangiz tayyorlanmoqda. Xaridingiz barakali bo'lsin! ✨"
        )

    @classmethod
    def format_admin_alert(cls, order_id: int, product: Dict[str, Any], user_name: str, phone: str, address: str, full_raw: str = "") -> str:
        """Do'kon egasi (Admin) uchun zudlik bilan push xabarnoma"""
        stock_remaining = product.get('stock_quantity', 1) - 1
        stock_label = f"oxirgi {stock_remaining} ta qoldi" if stock_remaining <= 2 and stock_remaining > 0 else f"{stock_remaining} dona qoldi"
        return (
            f"🚨 **YANGI BUYURTMA TUSHDI! (# {order_id})**\n\n"
            f"👤 **Xaridor:** {user_name}\n"
            f"📞 **Telefon:** `{phone}`\n"
            f"📍 **Manzil:** {address}\n"
            f"🛍️ **Mahsulot:** **{product['name']}** (ID: #{product['id']})\n"
            f"📏 **O'lcham:** {product['size']} | **Rang:** {product['color']}\n"
            f"💵 **Narxi:** **{product['sale_price']:,.0f} so'm**\n"
            f"📊 **Qoldiq:** {stock_label}\n"
            f"📝 **Mijoz xabari:** {full_raw}"
        )
