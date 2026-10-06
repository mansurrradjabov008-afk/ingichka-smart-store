import re
from typing import Dict, Any, Optional, List, Tuple
from database.db_manager import DatabaseManager

def normalize_uzbek_word(w: str) -> str:
    """O'zbek tilidagi kiyim nomlari, qo'shimchalari va shevalarini normallashtirish"""
    w = w.lower().strip(",.!?\"'`:;()[]{}-_")
    w = re.sub(r"['`ʻ‘’]", "'", w)
    if re.search(r"kr[ao]s+[ao][vf]?k", w):
        return "krossovka"
    if re.search(r"v[ie]tr[ao][vf]?k", w):
        return "vitrofka"
    if re.search(r"svit[ie]r", w):
        return "svitir"
    if re.search(r"k[o']?ylak", w):
        return "ko'ylak"
    if re.search(r"o'?g'?il", w):
        return "o'g'il"
    if re.search(r"p[ie]jam", w):
        return "pijama"
    if re.search(r"troyk", w):
        return "troyka"
    if re.search(r"dvoyk", w):
        return "dvoyka"
    if re.search(r"tap[io]ch?k|shippak", w):
        return "tapichka"
    suffixes = [
        "chalarga", "chalarini", "chalari", "chalardan", "chasi", "chalar", "cha",
        "larga", "larini", "lardan", "larning", "larni", "lari", "lar",
        "dagi", "dami", "dek",
        "ga", "ka", "qa", "da", "dan", "ni", "ning", "si", "i"
    ]
    for suf in suffixes:
        if len(w) > len(suf) + 2 and w.endswith(suf):
            w = w[:-len(suf)]
            break
    if w in ("bola", "bolacha", "bolalar"):
        return "bolalar"
    if w in ("qiz", "qizcha", "qizaloq", "qizlar"):
        return "qiz"
    return w


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
    def _get_products_from_history(cls, history: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Muloqot tarixidan eng oxirgi tilga olingan tovarlarni ketma-ketlikda olish"""
        if not history:
            return []
        all_prods = DatabaseManager.get_products(in_stock_only=False)
        prods_by_id = {p["id"]: p for p in all_prods}
        found_prods = []
        seen_ids = set()

        for msg in reversed(history):
            content = msg.get("content", "")
            # 1. ID orqali qidirish: ID: 39, #39, buy_39, 39-tovar
            id_matches = re.findall(r"(?:ID:\s*|#|buy_|tovar\s*)(\d{1,3})", content, re.IGNORECASE)
            for id_str in id_matches:
                pid = int(id_str)
                if pid in prods_by_id and pid not in seen_ids:
                    seen_ids.add(pid)
                    found_prods.append(prods_by_id[pid])

            # 2. Nom orqali qidirish
            content_low = content.lower()
            for p in all_prods:
                p_id = p["id"]
                if p_id not in seen_ids and p.get("name", "").lower() in content_low:
                    seen_ids.add(p_id)
                    found_prods.append(p)

            if found_prods:
                break

        return found_prods

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

        # 1a. SKU orqali aniqlash (MS-1001, KK-1002, MS 1012, etc.)
        sku_match = re.search(r"\b(kk|ms)[-_\s]?(\d{4})\b", t_low)
        if sku_match:
            prefix = sku_match.group(1).upper()
            sku_target = f"{prefix}-{sku_match.group(2)}"
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

        # 2b. KONTEKSTUAL DAVOM QIDIRUVI (Context-First Matching for Follow-up Inquiries)
        # Agar foydalanuvchi yangi kategoriya aytmasdan, avvalgi tovarning rangi, rasmi,
        # razmeri yoki xususiyati haqida so'rasa (masalan: "Menga qora rangini kursata olasizmi")
        if history:
            category_words = [
                "kurtka", "vitrofka", "vetrovka", "svitir", "sviter", "kofta", "koftacha", "xudi", "hoodie",
                "ko'ylak", "koylak", "koʻylak", "koylakcha", "tonika", "yubka", "shim", "jinsi", "triko",
                "kostyum", "sportivka", "troyka", "kardigan", "pijama", "pijamacha",
                "krossovka", "krasovka", "tapichka", "shippak", "poyabzal", "futbolka",
                "tekstil", "pastel", "ichki kiyim"
            ]
            has_new_category = any(cat in t_low for cat in category_words)

            followup_triggers = [
                "qora", "oq", "ko'k", "kok", "koʻk", "yashil", "sariq", "qizil", "pushti", "kulrang", "jigarrang", "havorang",
                "rang", "rangi", "ranglar", "ranglari", "rangini", "ranglisi", "rangdagi", "rangidan",
                "kursat", "ko'rsat", "koʻrsat", "kursata", "ko'rsata", "kursating", "ko'rsating", "ko'raylik",
                "rasm", "rasmi", "rasmini", "surat", "surati", "suratini", "foto", "fotoni",
                "razmer", "razmeri", "o'lcham", "o'lchami", "bormi", "bor", "mavjud",
                "menga", "bizga", "olaman", "olmoqchiman", "shuni", "buni", "o'shani", "iltimos", "yoqdi",
                "черный", "белый", "красный", "синий", "зеленый", "цвет", "показать", "фото"
            ]
            is_followup = any(trg in t_low for trg in followup_triggers) or len(t_low.split()) <= 7

            if not has_new_category and is_followup:
                hist_prods = cls._get_products_from_history(history)
                if hist_prods:
                    return hist_prods[0]

        # 3. Dinamik ko'p parametrli qidiruv (Barcha tovarlar bo'yicha)
        all_prods = DatabaseManager.get_products(in_stock_only=False)
        best_dyn_prod = None
        best_dyn_score = 0

        t_words = [normalize_uzbek_word(w) for w in t_low.split()]

        for p in all_prods:
            p_name = p.get("name", "").lower()
            p_cat = p.get("category", "").lower()
            p_color = p.get("color", "").lower()
            p_brand = (p.get("brand") or "").lower()
            p_desc = (p.get("description") or "").lower()
            p_name_words = [normalize_uzbek_word(w) for w in p_name.split()]

            score = 0
            if p_name and (p_name in t_low or (len(t_low) >= 5 and t_low in p_name)):
                score += 60
            if p_desc and len(t_low) >= 5 and t_low in p_desc:
                score += 40
            if p_brand and p_brand in t_low:
                score += 30
            if p_cat and p_cat in t_low:
                score += 20
            if p_color and p_color in t_low:
                score += 15

            # O'zbekcha so'z ildizlari va sinonimlari bo'yicha moslik
            for qw in t_words:
                if len(qw) >= 3:
                    if qw in p_name_words:
                        score += 30
                    elif qw in p_name:
                        score += 20
                    elif qw in p_desc:
                        score += 10

            # Jins (Gender) bo'yicha saralash - O'g'il bolalar va Qiz bolalar tovarlarini adashtirmaslik!
            if "qiz" in t_words:
                if "qiz" in p_name_words or "qiz" in p_name:
                    score += 35
                elif "o'g'il" in p_name_words or "o'g'il" in p_name:
                    score -= 45

            if "o'g'il" in t_words:
                if "o'g'il" in p_name_words or "o'g'il" in p_name:
                    score += 35
                elif "qiz" in p_name_words or "qiz" in p_name:
                    score -= 45

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

        # 6. Umumiy kategoriya bo'yicha zaxira (ombordagi birinchi mos tovar)
        cat_triggers = {
            "svitir": "Svitir",
            "sviter": "Svitir",
            "svitercha": "Svitir",
            "kofta": "Svitir",
            "koftacha": "Svitir",
            "xudi": "Svitir",
            "kurtka": "Kurtka",
            "kurtkacha": "Kurtka",
            "vitrofka": "Kurtka",
            "vetrovka": "Kurtka",
            "tapichka": "Oyoq kiyim",
            "tapochka": "Oyoq kiyim",
            "shippak": "Oyoq kiyim",
            "krossovka": "Oyoq kiyim",
            "krasovka": "Oyoq kiyim",
            "krasofka": "Oyoq kiyim",
            "krasofkacha": "Oyoq kiyim",
            "krosofka": "Oyoq kiyim",
            "krosovka": "Oyoq kiyim",
            "poyabzal": "Oyoq kiyim",
            "oyoq kiyim": "Oyoq kiyim",
            "futbolka": "Futbolka",
            "futbolkacha": "Futbolka",
            "jinsi": "Shim",
            "triko": "Shim",
            "shim": "Shim",
            "shimcha": "Shim",
            "ko'ylak": "Ko'ylak",
            "koylak": "Ko'ylak",
            "koylakcha": "Ko'ylak",
            "ko'ylakcha": "Ko'ylak",
            "tonika": "Ko'ylak",
            "kostyum": "Kostyum",
            "sportivka": "Kostyum",
            "kardigan": "Kardigan",
            "pijama": "Pijama",
            "pijamacha": "Pijama",
            "palto": "Kurtka",
            "tekstil": "Uy tekstili",
            "pastel": "Uy tekstili",
            "ichki kiyim": "Ichki kiyim"
        }
        for kw, cat_name in cat_triggers.items():
            if kw in t_low:
                cat_prods = [
                    p for p in all_prods
                    if (p.get("category") == cat_name or cat_name.lower() in p.get("category", "").lower() or kw in p.get("name", "").lower())
                    and p.get("stock_quantity", 0) > 0
                ]
                if cat_prods:
                    # Agar jins ko'rsatilgan bo'lsa, mosini saralash
                    if "qiz" in t_words:
                        filtered = [p for p in cat_prods if "qiz" in p.get("name", "").lower()]
                        if filtered:
                            return filtered[0]
                    elif "o'g'il" in t_words:
                        filtered = [p for p in cat_prods if "o'g'il" in p.get("name", "").lower()]
                        if filtered:
                            return filtered[0]
                    return cat_prods[0]

    @classmethod
    def match_products_multi(
        cls,
        text: str,
        history: Optional[List[Dict[str, str]]] = None,
        max_limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Mijoz so'ragan yoki qidirgan mahsulotlarni topish (Task 2).
        Bir nechta mahsulot mos kelsa max 3 ta gacha qaytaradi.
        """
        if not text:
            return []

        t_low = text.lower().strip()

        # 1. Aniq ID yoki SKU bo'lsa (bitta mahsulot)
        if re.search(r"\b(?:kk[-_\s]?)(\d{4})\b", t_low) or re.search(r"(?:#|buy_|id\s*|tovar\s*|mahsulot\s*)(\d{1,3})", t_low):
            single = cls.match_product(text, history=history)
            return [single] if single else []

        all_prods = DatabaseManager.get_products(in_stock_only=False)

        # 2. Mijoz "boshqa turlari", "boshqa variantlar", "yana qanaqa bor" desa - avvalgi tovar toifasini olish
        variant_inquiry_words = ["boshqa turlari", "boshqa variant", "turlarini", "turlari", "yana qanaqa", "boshqacha", "boshqalari", "yana bormi"]
        if any(w in t_low for w in variant_inquiry_words) and history:
            for msg in reversed(history[-4:]):
                c_low = msg.get("content", "").lower()
                for p in all_prods:
                    if p.get("name", "").lower() in c_low or str(p.get("id")) in c_low:
                        cat_matches = [item for item in all_prods if item.get("category") == p.get("category") and item.get("id") != p.get("id")]
                        if cat_matches:
                            return cat_matches[:max_limit]

        # 2b. Mijoz joriy tovar bo'yicha rang, rasm, razmer yoki ko'rsatish so'rasa (Context-First Follow-up)
        # Masalan: "Menga qora rangini kursata olasizmi", "Iltimos qora rangini kursating", "Rasmini tashlang"
        if history:
            category_words = [
                "kurtka", "vitrofka", "vetrovka", "svitir", "sviter", "kofta", "koftacha", "xudi", "hoodie",
                "ko'ylak", "koylak", "koʻylak", "koylakcha", "tonika", "yubka", "shim", "jinsi", "triko",
                "kostyum", "sportivka", "troyka", "kardigan", "pijama", "pijamacha",
                "krossovka", "krasovka", "tapichka", "shippak", "poyabzal", "futbolka",
                "tekstil", "pastel", "ichki kiyim"
            ]
            has_new_category = any(cat in t_low for cat in category_words)

            followup_triggers = [
                "qora", "oq", "ko'k", "kok", "koʻk", "yashil", "sariq", "qizil", "pushti", "kulrang", "jigarrang", "havorang",
                "rang", "rangi", "ranglar", "ranglari", "rangini", "ranglisi", "rangdagi", "rangidan",
                "kursat", "ko'rsat", "koʻrsat", "kursata", "ko'rsata", "kursating", "ko'rsating", "ko'raylik",
                "rasm", "rasmi", "rasmini", "surat", "surati", "suratini", "foto", "fotoni",
                "razmer", "razmeri", "o'lcham", "o'lchami", "bormi", "bor", "mavjud",
                "menga", "bizga", "olaman", "olmoqchiman", "shuni", "buni", "o'shani", "iltimos", "yoqdi",
                "черный", "белый", "красный", "синий", "зеленый", "цвет", "показать", "фото"
            ]
            is_followup = any(trg in t_low for trg in followup_triggers) or len(t_low.split()) <= 7

            if not has_new_category and is_followup:
                hist_prods = cls._get_products_from_history(history)
                if hist_prods:
                    return hist_prods[:max_limit]

        # 3. Kategoriya va mahsulot turlari bo'yicha aniq saralash (Real 41 ta tovar uchun)
        # 3a. Oyoq kiyim / Tapichka / Krossovka alohida turlari
        if any(w in t_low for w in ["tapichka", "shippak", "slansi", "tapochka"]):
            tap_matches = [p for p in all_prods if "tapichka" in p.get("name", "").lower() or "shippak" in p.get("name", "").lower()]
            if tap_matches:
                return tap_matches[:max_limit]

        if any(w in t_low for w in ["krossovka", "krasovka", "krasofka", "krasofkacha", "krosofka", "krosovka", "krasovkacha", "kedalar", "keta"]):
            kros_matches = [p for p in all_prods if "krossovka" in p.get("name", "").lower()]
            if any(w in t_low for w in ["qiz", "qizlar", "qizlarga", "qizcha"]):
                kros_matches = [p for p in kros_matches if "qiz" in p.get("name", "").lower()] + [p for p in kros_matches if "qiz" not in p.get("name", "").lower()]
            elif any(w in t_low for w in ["o'g'il", "ogil", "o‘g‘il", "oʻgʻil", "ogilcha"]):
                kros_matches = [p for p in kros_matches if "o'g'il" in p.get("name", "").lower()] + [p for p in kros_matches if "o'g'il" not in p.get("name", "").lower()]
            if kros_matches:
                return kros_matches[:max_limit]

        if any(w in t_low for w in ["oyoq kiyim", "poyabzal", "poyafzal", "oyoq kiyimi"]):
            shoes = [p for p in all_prods if p.get("category") == "Oyoq kiyim"]
            if shoes:
                return shoes[:max_limit]

        # 3b. Kurtkalar va vitrofkalar
        if any(w in t_low for w in ["kurtka", "kurtkacha", "vitrofka", "vetrovka", "jilet", "nimcha", "plash"]):
            kurtkas = [p for p in all_prods if p.get("category") == "Kurtka" or "vitrofka" in p.get("name", "").lower() or "kurtka" in p.get("name", "").lower()]
            if kurtkas:
                return kurtkas[:max_limit]

        # 3c. Svitirlar, sviterlar, koftalar, xudilar
        if any(w in t_low for w in ["svitir", "sviter", "svitercha", "kofta", "koftacha", "xudi", "hoodie", "pulover", "jumper", "svitshot"]):
            sviters = [p for p in all_prods if p.get("category") == "Svitir" or "svitir" in p.get("name", "").lower() or "sviter" in p.get("name", "").lower() or "kofta" in p.get("name", "").lower()]
            if sviters:
                return sviters[:max_limit]

        # 3d. Ko'ylaklar, tonikalar, yubkalar
        if any(w in t_low for w in ["ko'ylak", "koylak", "koʻylak", "koylakcha", "tonika", "dvoyka", "yubka"]):
            dresses = [p for p in all_prods if p.get("category") == "Ko'ylak" or "ko'ylak" in p.get("name", "").lower() or "tonika" in p.get("name", "").lower()]
            if dresses:
                return dresses[:max_limit]

        # 3e. Shimlar, jinsilar, trikolar
        if any(w in t_low for w in ["shim", "shimcha", "jinsi", "triko", "bryuk"]):
            pants = [p for p in all_prods if p.get("category") == "Shim" or "shim" in p.get("name", "").lower() or "jinsi" in p.get("name", "").lower() or "triko" in p.get("name", "").lower()]
            if pants:
                return pants[:max_limit]

        # 3f. Kostyumlar va sportivkalar
        if any(w in t_low for w in ["kostyum", "sportivka", "troyka", "troykacha"]):
            suits = [p for p in all_prods if p.get("category") == "Kostyum" or "kostyum" in p.get("name", "").lower() or "sportivka" in p.get("name", "").lower()]
            if suits:
                return suits[:max_limit]

        # 3g. Kardiganlar
        if any(w in t_low for w in ["kardigan", "jaket"]):
            cardigans = [p for p in all_prods if p.get("category") == "Kardigan" or "kardigan" in p.get("name", "").lower()]
            if cardigans:
                return cardigans[:max_limit]

        # 3h. Pijamalar
        if any(w in t_low for w in ["pijama", "pijamacha", "pijamalar", "uy kiyimi"]):
            pijamas = [p for p in all_prods if p.get("category") == "Pijama" or "pijama" in p.get("name", "").lower()]
            if any(w in t_low for w in ["qiz", "qizlar", "qizlarga", "qizcha"]):
                pijamas = [p for p in pijamas if "qiz" in p.get("name", "").lower()] + [p for p in pijamas if "qiz" not in p.get("name", "").lower()]
            elif any(w in t_low for w in ["o'g'il", "ogil", "o‘g‘il", "oʻgʻil", "ogilcha"]):
                pijamas = [p for p in pijamas if "o'g'il" in p.get("name", "").lower()] + [p for p in pijamas if "o'g'il" not in p.get("name", "").lower()]
            if pijamas:
                return pijamas[:max_limit]

        # 3i. Bolalar kiyimlari
        if any(w in t_low for w in ["bolalar kiyimi", "bolalar", "chaqaloq", "bolalarga"]):
            kids = [p for p in all_prods if p.get("gender") == "Bolalar" or "bolalar" in p.get("name", "").lower() or p.get("category") == "Bolalar kiyimi"]
            if kids:
                return kids[:max_limit]

        # 3j. Ayollar kiyimlari
        if any(w in t_low for w in ["ayollar kiyimi", "ayollar", "ayol", "qizlar"]):
            women = [p for p in all_prods if p.get("gender") == "Ayol" or p.get("category") in ["Ko'ylak", "Kardigan"]]
            if women:
                return women[:max_limit]

        # 3k. Erkaklar kiyimlari
        if any(w in t_low for w in ["erkaklar kiyimi", "erkaklar", "erkak"]):
            men = [p for p in all_prods if p.get("gender") == "Erkak"]
            if men:
                return men[:max_limit]

        # 3l. Futbolkalar va Uy tekstili
        if any(w in t_low for w in ["futbolka", "mayka"]):
            tshirts = [p for p in all_prods if p.get("category") == "Futbolka" or "futbolka" in p.get("name", "").lower()]
            if tshirts:
                return tshirts[:max_limit]

        if any(w in t_low for w in ["uy tekstili", "tekstil", "pastel", "postel", "jild", "choyshab"]):
            textile = [p for p in all_prods if p.get("category") == "Uy tekstili" or "pastel" in p.get("name", "").lower()]
            if textile:
                return textile[:max_limit]

        # 3m. Umumiy kiyimlar yoki do'kon katalogi so'ralganda
        if any(w in t_low for w in ["qanday kiyimlar bor", "nimalar bor", "qanaqa kiyim", "do'konda nima bor", "assortiment", "katalog"]):
            # Har xil toifadagi eng mashhur tovarlardan sara 3 tasini taqdim etish
            samples = [p for p in all_prods if p.get("id") in [15, 4, 1]]
            if len(samples) >= 2:
                return samples[:max_limit]

        # 4. Brend bo'yicha
        for brand in ["zara", "nike", "adidas", "h&m", "lc waikiki", "uztex", "pull&bear", "defacto", "polo", "boss"]:
            if brand in t_low:
                brand_prods = [
                    p for p in all_prods
                    if brand in (p.get("brand") or "").lower() or brand in p.get("name", "").lower()
                ]
                if len(brand_prods) > 1:
                    return brand_prods[:max_limit]
                elif len(brand_prods) == 1:
                    return brand_prods

        # 5. Yagona mahsulotni aniqlash
        single = cls.match_product(text, history=history)
        return [single] if single else []

    @classmethod
    def get_category_variants(
        cls,
        category_or_product: Any,
        exclude_ids: Optional[List[int]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Mijoz so'ragan mahsulot toifasidagi barcha boshqa turlarni (variantlarni) aniqlab,
        chiroyli konsultatsiya matni va katalog tugmasini tayyorlash.
        """
        exclude_ids = exclude_ids or []
        cat_name = ""
        cat_key = ""

        if isinstance(category_or_product, dict):
            cat_name = category_or_product.get("category", "")
            cat_key = cat_name
        elif isinstance(category_or_product, str):
            cat_name = category_or_product
            cat_key = category_or_product

        if not cat_name:
            return None

        # Friendly titles & standard category callback keys
        title_map = {
            "Kurtka": ("Kurtkalar & Vitrofkalar", "Kurtka"),
            "Svitir": ("Svitirlar & Koftalar", "Svitir"),
            "Ko'ylak": ("Ko'ylaklar & Tonikalar", "Ko'ylak"),
            "Shim": ("Shimlar & Trikolar", "Shim"),
            "Oyoq kiyim": ("Poyabzal & Tapichkalar", "Oyoq kiyim"),
            "Kostyum": ("Kostyumlar & Sportivkalar", "Kostyum"),
            "Kardigan": ("Kardiganlar", "Kardigan"),
            "Pijama": ("Pijamalar", "Pijama"),
            "Bolalar kiyimi": ("Bolalar kiyimlari", "Bolalar"),
            "Bolalar": ("Bolalar kiyimlari", "Bolalar"),
            "Futbolka": ("Futbolkalar", "Futbolka"),
            "Uy tekstili": ("Uy tekstili & Choyshablar", "Uy tekstili"),
            "Ayol": ("Ayollar kiyimlari", "Ko'ylak"),
            "Erkak": ("Erkaklar kiyimlari", "Kurtka")
        }

        friendly_title, cb_key = title_map.get(cat_name, (cat_name, cat_name))

        all_cat_prods = DatabaseManager.get_products(category=cat_name, in_stock_only=True)
        if not all_cat_prods:
            all_cat_prods = DatabaseManager.get_products(category=cat_name, in_stock_only=False)

        total_count = len(all_cat_prods)
        other_variants = [p for p in all_cat_prods if p.get("id") not in exclude_ids]

        if not other_variants:
            return {
                "total_count": total_count,
                "category_title": friendly_title,
                "category_key": cb_key,
                "other_variants": [],
                "summary_text": f"✨ Bizda jami **{total_count} ta model** mavjud. Barcha saralangan namunalar yuqorida ko'rsatildi.",
                "button_text": f"🛍️ Barcha {friendly_title}ni ko'rish ({total_count} ta model)"
            }

        lines = [f"✨ **Do'konimizda jami {total_count} xil {friendly_title} modellari mavjud:**\n"]
        for p in other_variants[:4]:
            p_name = p.get("name", "Model")
            p_price = p.get("sale_price") or p.get("price", 0)
            p_size = p.get("size", "")
            size_part = f" (O'lcham: {p_size})" if p_size else ""
            lines.append(f"• **{p_name}** — {p_price:,.0f} so'm{size_part}")

        if len(other_variants) > 4:
            lines.append(f"• *...va yana {len(other_variants) - 4} ta boshqa sara modellar!*")

        lines.append("\nBarcha modellarni birma-bir tomosha qilish uchun quyidagi tugmani bosing 👇")

        return {
            "total_count": total_count,
            "category_title": friendly_title,
            "category_key": cb_key,
            "other_variants": other_variants,
            "summary_text": "\n".join(lines),
            "button_text": f"🛍️ Barcha {friendly_title}ni ko'rish ({total_count} ta model)"
        }

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
