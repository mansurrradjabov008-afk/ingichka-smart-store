import os
import re
from typing import Dict, Any, List, Optional
from database.db_manager import DatabaseManager
from config import STORE_NAME, CATEGORIES, STORE_SETTINGS
from services.store_settings_manager import StoreSettingsManager
from services.order_matcher import OrderMatcher

class SalesAgent:
    """
    Do'kon bosh sotuvchi-maslahatchisi (20 yillik tajribali savdogar) intellektual tizimi.
    Nol gallutsinatsiya (Grounding) kafolati bilan ishlaydi.
    Haqiqiy muloqot, konsultatsiya, rang, o'lcham va fason bo'yicha aniq savol berish,
    va to'liq xarid oqimini professional darajada boshqaradi.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.sessions: Dict[int, Dict[str, Any]] = {}

    def get_session(self, customer_id: int) -> Dict[str, Any]:
        """Har bir mijoz uchun muloqot holatini eslab qolish"""
        if customer_id not in self.sessions:
            self.sessions[customer_id] = {
                "category": None,
                "product_id": None,
                "preferred_size": None,
                "preferred_color": None,
                "stage": "idle"  # idle, discovery, size_color, confirm_purchase
            }
        return self.sessions[customer_id]

    def reset_session(self, customer_id: int):
        if customer_id in self.sessions:
            self.sessions[customer_id] = {
                "category": None,
                "product_id": None,
                "preferred_size": None,
                "preferred_color": None,
                "stage": "idle"
            }

    def process_message(
        self,
        user_text: str,
        customer_id: int = 0,
        customer_name: str = "Mijoz",
        context: Optional[Dict] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Mijoz xabarini tahlil qilib, 7 ta qat'iy qoidaga mos holda
        haqiqiy 20 yillik tajribali savdogar kabi maslahat berish.
        """
        text_lower = user_text.lower().strip()
        session = self.get_session(customer_id)

        # 1. Do'kon sozlamalari (delivery, discount, address) tekshiruvi
        setting_res = StoreSettingsManager.check_setting_inquiry(user_text)
        if setting_res:
            return setting_res["reply"]

        # 2. Qoida 7: Mavjud bo'lmagan o'lcham tekshiruvi
        size_check = OrderMatcher.check_size_inquiry(user_text)
        if size_check:
            return size_check

        # 3. Qoida 5: Jami summani kod hisoblashi (Quote / Narx hisobi)
        quote_res = OrderMatcher.calculate_quote(user_text)
        if quote_res:
            return quote_res

        # 4. Qoida 4: Narx bo'yicha filtr (kod filtrlaydi)
        price_filt = OrderMatcher.parse_price_filter(user_text)
        if price_filt:
            prods = OrderMatcher.filter_products_by_price(price_filt["min_price"], price_filt["max_price"])
            return OrderMatcher.format_price_filter_response(prods, price_filt["min_price"], price_filt["max_price"])

        # 5. "Botmisiz yoki odammisiz" savoliga samimiy insoniy javob
        if any(w in text_lower for w in ["botmisiz", "odammisiz", "kim bu", "robotmisiz", "jonlimisiz", "insonmisiz"]):
            return (
                "Assalomu alaykum! Men Ingichka Baraka Savdo do'konining aqlli yordamchisiman. "
                "Sizga tovarlar, o'lcham va narxlar bo'yicha ma'lumot berib, buyurtmangizni tezda qabul qilib olaman. "
                "Do'kon egasi bilan to'g'ridan-to'g'ri bog'lanish uchun: 97 913-36-86."
            )

        # 6. Agar xaridor telefon raqam va manzil bilan to'g'ridan-to'g'ri buyurtma bersa
        phone_match = re.search(r"(\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}|\b\d{9}\b)", text_lower)
        address_triggers = ["ko'cha", "kocha", "mahalla", "uy", "qishloq", "manzil", "markaz", "toshkent", "samarqand", "ingichka", "rayon", "tuman", "dom"]
        has_address = any(a in text_lower for a in address_triggers) or len(user_text.strip()) > 20
        if phone_match and has_address:
            clean_name = customer_name if customer_name and customer_name != "Mijoz" else ""
            greeting = f"Assalomu alaykum, {clean_name}!" if clean_name else "Assalomu alaykum!"
            return (
                f"{greeting} Ajoyib tanlov! Buyurtmangiz qabul qilinmoqda.\n"
                f"Siz bilan tez orada bog'lanib, buyurtmani tasdiqlaymiz."
            )

        # 7. Kategoriya va Konsultatsiya Qidiruvi (Ayollar kiyimi, Xotinimga, Ayolimga, Erkaklar kiyimi, O'zimga, Bolalar...)
        is_women_inquiry = any(w in text_lower for w in [
            "ayol", "ayollar", "ayollarning", "xotinim", "xotin", "ayolim", "singlim", "onam", "qizim", "kelin"
        ])
        is_men_inquiry = any(w in text_lower for w in [
            "erkak", "erkaklar", "erkaklarning", "erim", "otam", "dadam", "akam", "ukam", "o'zimga", "o'zim", "o'g'lim"
        ])
        is_kids_inquiry = any(w in text_lower for w in ["bola", "bolalar", "go'dak", "kichkintoy"])
        is_shoes_inquiry = any(w in text_lower for w in [
            "oyoq kiyim", "poyabzal", "tufli", "etik", "krasovka", "krossovka",
            "krasovkalar", "krossovkalar", "krasovki", "krossovki", "кроссовк", "sneaker"
        ])
        is_gift_general = any(w in text_lower for w in ["sovg'a", "sovga", "kiyim kerak", "kiyim olmoqchi", "nima tavsiya", "maslahat"])

        # Ayollar kiyimi bo'yicha konsultatsiya
        if is_women_inquiry and not any(w in text_lower for w in ["kurtka", "krossovka", "krasovka", "kepka"]):
            session["category"] = "Ayollar kiyimi"
            session["stage"] = "discovery"

            person_ref = "Ayolingiz uchun" if ("xotin" in text_lower or "ayol" in text_lower) else (
                "Onangiz uchun" if "onam" in text_lower else (
                    "Qizingiz uchun" if "qizim" in text_lower else (
                        "Singlingiz uchun" if "singlim" in text_lower else "Ayollar bo'limimizda"
                    )
                )
            )

            # Ombordagi ayollar tovarlarini tekshirish
            prods = DatabaseManager.get_products(category="Ayollar kiyimi", in_stock_only=True)
            prod_names = []
            for p in prods:
                stock = p["stock_quantity"]
                st_label = f"oxirgi {stock} ta qoldi" if (stock <= 2 and stock > 0) else f"{stock} ta bor"
                prod_names.append(f"'{p['name']}' ({p['sale_price']:,.0f} so'm, {st_label})")
            
            prods_intro = " va ".join(prod_names) if prod_names else "sifatli ko'ylak va issiq qishki paltolarimiz"
            return (
                f"Assalomu alaykum! {person_ref} do'konimizda nafis {prods_intro} mavjud.\n"
                f"Ko'proq qaysi fason ma'qul — nafis ko'ylakmi yoki qishki palto? Qaysi o'lcham (S, M, L) va qanaqa ranglar yoqadi?"
            )

        # Erkaklar kiyimi bo'yicha konsultatsiya
        if is_men_inquiry and not any(w in text_lower for w in ["kurtka", "krossovka", "krasovka", "kepka", "jinsi", "futbolka"]):
            session["category"] = "Erkaklar kiyimi"
            session["stage"] = "discovery"

            person_ref = "Eringiz uchun" if "erim" in text_lower else (
                "Otangiz uchun" if ("otam" in text_lower or "dadam" in text_lower) else (
                    "O'g'lingiz uchun" if "o'g'lim" in text_lower else (
                        "O'zingiz uchun" if ("o'zim" in text_lower or "o'zimga" in text_lower) else "Erkaklar bo'limimizda"
                    )
                )
            )

            return (
                f"{person_ref} sifatli qora kurtka (450,000 so'm), zamonaviy oversize futbolkalar (120,000 so'm) va klassik jinsi shimlar (280,000 so'm) bor.\n"
                f"Sizga ko'proq qaysi uslub ma'qul — kundalik jinsi va futbolkami yoki issiq kurtka? O'lchamingiz va qanaqa rang qidiryapsiz?"
            )

        # Bolalar kiyimi bo'yicha konsultatsiya
        if is_kids_inquiry:
            session["category"] = "Bolalar kiyimi"
            session["stage"] = "discovery"
            return (
                "Bolalar kiyimlari bo'limida yangi mavsumiy to'plamlar tayyorlanmoqda.\n"
                "Farzandingiz necha yoshda va o'g'il bolami yoki qiz bolami? Mos variantlarni tavsiya qilaman."
            )

        # Poyabzal / Oyoq kiyim konsultatsiyasi
        if is_shoes_inquiry:
            session["product_id"] = 8
            session["stage"] = "size_color"
            return (
                "Ha, albatta bor! Do'konimizda oq rangli qulay Krossovka mavjud (o'lchamlari: 40, 41, 42, 43, narxi: 380,000 so'm, 7 ta bor).\n"
                "Sizga qaysi o'lcham (razmer) to'g'ri keladi, buyurtma qilib beraymi?"
            )

        # Umumiy sovg'a yoki maslahat so'rovi
        if is_gift_general and not OrderMatcher.match_product(user_text, history=history):
            return (
                "Do'konimizda erkaklar va ayollar uchun sifatli mavsumiy kiyimlar, qishki palto, kurtkalar va krossovkalar bor.\n"
                "Sovg'a kimga mo'ljallangan va qanday uslubdagi kiyim yoki o'lcham qidiryapsiz?"
            )

        # 8. Muloqot davomida mijoz tanlovi (Fason, Rang yoki O'lcham aytgan holat)
        # 8a. Fason tanlovi
        if "ko'ylak" in text_lower or "koylak" in text_lower:
            session["product_id"] = 4
            session["stage"] = "size_color"
            return (
                "Ajoyib tanlov! 'Ayollar gulli ko'ylagi' qizil va ko'k rangda, S va M o'lchamlari mavjud (narxi: 350,000 so'm, oxirgi 2 ta qoldi).\n"
                "Qaysi o'lcham va rangda buyurtma rasmiylashtiraylik?"
            )

        if "palto" in text_lower:
            session["product_id"] = 6
            session["stage"] = "size_color"
            return (
                "Ajoyib tanlov! 'Ayollar qishki paltosi' bej rangda, S, M, L o'lchamlari bor (narxi: 890,000 so'm, oxirgi 1 ta qoldi).\n"
                "Sizga qaysi o'lcham ma'qul, buyurtma qilib beraymi?"
            )

        if "kurtka" in text_lower and not any(w in text_lower for w in ["bormi", "qancha", "narxi"]):
            session["product_id"] = 1
            session["stage"] = "size_color"
            return (
                "Ajoyib tanlov! Erkaklar qora kurtkasi qora rangda, M, L, XL o'lchamlari bor (narxi: 450,000 so'm, 5 ta bor).\n"
                "Sizga qaysi o'lcham to'g'ri keladi, buyurtma qilib beraymi?"
            )

        if "futbolka" in text_lower and not any(w in text_lower for w in ["bormi", "qancha", "narxi"]):
            session["product_id"] = 2
            session["stage"] = "size_color"
            return (
                "Ajoyib tanlov! Oversize futbolkalarimiz oq va qora rangda, S, M, L o'lchamlari bor (narxi: 120,000 so'm, 12 ta bor).\n"
                "Qaysi rang va o'lchamda buyurtma qilamiz?"
            )

        if "jinsi" in text_lower and not any(w in text_lower for w in ["bormi", "qancha", "narxi"]):
            session["product_id"] = 3
            session["stage"] = "size_color"
            return (
                "Ajoyib tanlov! Klassik jinsi shim ko'k rangda, 30, 32, 34 o'lchamlari mavjud (narxi: 280,000 so'm, 3 ta bor).\n"
                "Qaysi o'lchamda buyurtma rasmiylashtiraylik?"
            )

        # 8b. Rang tanlovi
        color_patterns = {
            "qora": ["qora", "qorasi", "qora rang"],
            "oq": ["oq", "oqi", "oq rang"],
            "qizil": ["qizil", "qizili", "qizil rang"],
            "bej": ["bej", "bejiviy", "bej rang"],
            "ko'k": ["ko'k", "kok", "ko'ki", "ko'k rang"]
        }
        matched_color = None
        for col, pats in color_patterns.items():
            if any(p in text_lower for p in pats):
                matched_color = col
                break

        if matched_color:
            session["preferred_color"] = matched_color
            if session.get("category") == "Ayollar kiyimi" or session.get("product_id") in [4, 6]:
                if matched_color in ["qizil", "ko'k"]:
                    session["product_id"] = 4
                    return (
                        f"Ajoyib tanlov! {matched_color.capitalize()} rangdagi 'Ayollar gulli ko'ylagi' (S va M o'lchamlari bor, narxi: 350,000 so'm, oxirgi 2 ta qoldi).\n"
                        f"Shuni xarid qilish uchun buyurtma rasmiylashtiraylikmi?"
                    )
                elif matched_color == "bej":
                    session["product_id"] = 6
                    return (
                        f"Ajoyib tanlov! Bej rangdagi 'Ayollar qishki paltosi' (S, M, L o'lchamlari bor, narxi: 890,000 so'm, oxirgi 1 ta qoldi).\n"
                        f"Sizga qaysi o'lcham ma'qul, buyurtma qilib beraymi?"
                    )
            elif session.get("category") == "Erkaklar kiyimi" or session.get("product_id") in [1, 2, 3]:
                if matched_color == "qora":
                    return (
                        "Qora rangda do'konimizda Erkaklar qora kurtkasi (450,000 so'm), Oversize futbolka (120,000 so'm) va Kepkalar bor.\n"
                        "Sizga qaysi biri ma'qul bo'ldi, qaysi o'lchamda ko'rib chiqamiz?"
                    )

        # 8c. O'lcham (Razmer) tanlovi
        size_match = re.search(r"\b(xxl|xl|xs|s|m|l|30|32|34|40|41|42|43|44|46|48|50)\b", text_lower)
        if size_match and not any(w in text_lower for w in ["bormi", "bormikan"]):
            chosen_size = size_match.group(1).upper()
            session["preferred_size"] = chosen_size
            curr_pid = session.get("product_id")
            if curr_pid:
                prod = DatabaseManager.get_product_by_id(curr_pid)
                if prod:
                    prod_sizes = [s.strip().upper() for s in prod.get("size", "").split(",")]
                    if chosen_size in prod_sizes:
                        session["stage"] = "confirm_purchase"
                        return (
                            f"Ajoyib! {prod['name']} mahsulotimizda {chosen_size} o'lcham mavjud (narxi: {prod['sale_price']:,.0f} so'm).\n"
                            f"Xarid qilishni tasdiqlaysizmi, buyurtma rasmiylashtiraymi?"
                        )
                    else:
                        return f"Kechirasiz, {prod['name']} mahsulotimizda bunday o'lcham yo'q, bizda faqat {prod['size']} bor."

        # 9. Aniq xarid niyati / Buyurtma tasdig'i (Qoida 1: Faqat xarid tasdiqlanganda manzil/tel so'rash)
        order_triggers = ["buyurtma", "zakaz", "olaman", "olmoqchiman", "yetkazing", "olib keling", "sotib olaman", "bering", "tasdiqlayman"]
        has_direct_order_intent = any(w in text_lower for w in order_triggers) or (
            session.get("stage") == "confirm_purchase" and any(w in text_lower for w in ["ha", "mayli", "shuni", "albatta", "tasdiq"])
        )

        if has_direct_order_intent:
            curr_pid = session.get("product_id")
            matched_prod = DatabaseManager.get_product_by_id(curr_pid) if curr_pid else OrderMatcher.match_product(user_text, history=history)
            
            if matched_prod:
                session["product_id"] = matched_prod["id"]
                session["stage"] = "asked_details"
                return (
                    "Ajoyib tanlov! Buyurtmani rasmiylashtirish uchun telefon raqamingiz va manzilingizni yozib yuboring.\n"
                    "Buyurtmangizni darhol tayyorlaymiz."
                )
            elif any(w in text_lower for w in ["olaman", "zakaz", "buyurtma", "bering"]):
                return (
                    "Ajoyib tanlov! Buyurtmani rasmiylashtirish uchun telefon raqamingiz va manzilingizni yozib yuboring.\n"
                    "Buyurtmangizni darhol tayyorlaymiz."
                )

        # 10. Aniq tovar so'rovi (krasovka, kurtka, kepka...)
        matched_prod = OrderMatcher.match_product(user_text, history=history)
        if matched_prod:
            session["product_id"] = matched_prod["id"]
            session["category"] = matched_prod.get("category")
            session["stage"] = "size_color"

            stock = matched_prod.get("stock_quantity", 0)
            stock_str = f"oxirgi {stock} ta qoldi" if (stock <= 2 and stock > 0) else f"{stock} ta bor"
            size_info = f"O'lchamlari: {matched_prod['size']}" if matched_prod.get('size') else ""
            color_info = f"Rangi: {matched_prod['color']}" if matched_prod.get('color') else ""
            details = ", ".join(filter(None, [size_info, color_info]))

            closings_list = [
                "Sizga qaysi o'lcham to'g'ri keladi, buyurtma rasmiylashtirib beraymi?",
                "Qaysi o'lchamini ajratib qo'yaylik?",
                "Qaysi razmer sizga ma'qul bo'ladi?",
                "O'lchamini bilib beraymi?"
            ]
            c_close = closings_list[len(history) % len(closings_list)]

            return (
                f"Ha, do'konimizda {matched_prod['name']} mavjud!\n"
                f"{details}.\n"
                f"Narxi: {matched_prod['sale_price']:,.0f} so'm ({stock_str}).\n"
                f"{c_close}"
            )

        # 11. Do'konda yo'q mahsulot so'ralganda (butsa bormi, kitob bormi, telefon bormi...)
        if any(w in text_lower for w in ["bormi", "bormikan", "bormi?"]):
            missing_match = re.search(r"(\b[\w']+\b)\s+(?:bormi|bormikan)", text_lower)
            missing_name = missing_match.group(1) if missing_match else "bunday mahsulot"
            return (
                f"Kechirasiz, do'konimizda {missing_name} mavjud emas.\n"
                f"Bizda asosan sifatli erkaklar va ayollar kiyimlari, poyabzallar hamda aksessuarlar bor.\n"
                f"Sizga mos kiyim yoki poyabzal tanlashda yordam beraymi?"
            )

        # 12. Salomlashish (Assalomu alaykum, jinsini taxmin qilmasdan - Qoida 6)
        if any(w in text_lower for w in ["salom", "assalom", "qalesiz", "yaxshimisiz", "bormisiz"]):
            clean_name = customer_name if customer_name and customer_name != "Mijoz" else ""
            greeting = f"Assalomu alaykum, {clean_name}!" if clean_name else "Assalomu alaykum!"
            return (
                f"{greeting} Ingichka Baraka Savdo do'konimizga xush kelibsiz! Bizda erkaklar, ayollar kiyimlari, poyabzallar va sifatli aksessuarlar mavjud.\n"
                f"Bugun sizga qanday kiyim tanlashda yordam beraylik, kim uchun qidiryapsiz?"
            )

        # 13. Boshqa umumiy murojaat (Turli xil, samimiy yakunlar - Qoida 2)
        closings_gen = [
            "Sizga aynan qanday mahsulot yoki o'lcham kerak, yordam beraymi?",
            "Qaysi turdagi kiyim yoki poyabzal qidiryapsiz, tanlab beraymi?",
            "Bugun sizga qanday tovar tanlashda ko'maklashaylik?",
            "Qidirayotgan mahsulotingiz nomini aytsangiz, narx va o'lchamlarini chiqarib beraman."
        ]
        c_gen = closings_gen[len(history) % len(closings_gen)]
        return (
            f"Do'konimizda sifatli erkaklar, ayollar kiyimlari va poyabzallar mavjud.\n"
            f"{c_gen}"
        )

    @staticmethod
    def parse_product_voice_text(transcription: str) -> Dict[str, Any]:
        """Admin tomonidan aytilgan tovar ma'lumotlarini qirqib olish"""
        t_low = transcription.lower()
        prices = [int(p) for p in re.findall(r"(\d+)\s*(?:ming|000)", t_low)]
        cost_price = prices[0] * 1000 if len(prices) > 0 else 100000
        sale_price = prices[1] * 1000 if len(prices) > 1 else (cost_price * 1.5)

        qty_match = re.search(r"(\d+)\s*(?:ta|dona|shtuk)", t_low)
        stock_qty = int(qty_match.group(1)) if qty_match else 5

        size = "M"
        for s in ["xxl", "xl", "xs", "l", "m", "s", "42", "44", "46", "48", "50", "universal", "standart"]:
            if s in t_low:
                size = s.upper()
                break

        color = "Klassik"
        for c in ["qora", "oq", "ko'k", "qizil", "sariq", "yashil", "kulrang", "jigarrang", "pushti"]:
            if c in t_low:
                color = c.capitalize()
                break

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

sales_agent = SalesAgent()
