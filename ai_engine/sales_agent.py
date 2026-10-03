import os
import re
from typing import Dict, Any, List, Optional
from database.db_manager import DatabaseManager
from config import STORE_NAME, CATEGORIES, STORE_SETTINGS
from services.store_settings_manager import StoreSettingsManager
from services.order_matcher import OrderMatcher

class SalesAgent:
    """
    Do'kon sotuvchi-maslahatchisi offline tizimi.
    Nol gallutsinatsiya (Grounding) kafolati bilan ishlaydi.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    def process_message(self, user_text: str, customer_id: int, customer_name: str = "Mijoz", context: Optional[Dict] = None) -> str:
        """
        Mijoz xabarini tahlil qilib, 7 ta qat'iy qoidaga mos holda javob berish.
        """
        text_lower = user_text.lower().strip()

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

        # 6. Buyurtma berish / Xarid niyati bildirilgan holat (Qoida 1: Faqat xarid niyati bo'lganda manzil/tel so'rash)
        order_triggers = ["buyurtma", "zakaz", "olaman", "olmoqchiman", "yetkazing", "olib keling", "sotib olaman", "bering"]
        has_order_intent = any(w in text_lower for w in order_triggers)
        phone_match = re.search(r"(\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}|\b\d{9}\b)", text_lower)

        if has_order_intent:
            if phone_match:
                return (
                    "Ajoyib tanlov! Buyurtmangiz qabul qilinmoqda.\n"
                    "Siz bilan tez orada bog'lanib, buyurtmani tasdiqlaymiz."
                )
            return (
                "Ajoyib tanlov! Buyurtmani rasmiylashtirish uchun telefon raqamingiz va manzilingizni yozib yuboring.\n"
                "Buyurtmangizni darhol tayyorlaymiz."
            )

        # 7. Aniq tovar so'rovi (krasovka bormi, kurtka bormi, kepka bormi...)
        matched_prod = OrderMatcher.match_product(user_text)
        is_asking_availability = any(w in text_lower for w in ["bor", "bormi", "narxi", "qancha", "qanaqa", "razmer", "o'lcham", "rangi", "qanaqa"])

        if matched_prod and is_asking_availability:
            stock = matched_prod.get("stock_quantity", 0)
            stock_str = f"oxirgi {stock} ta qoldi" if (stock <= 2 and stock > 0) else f"{stock} ta bor"
            size_info = f"O'lchamlari: {matched_prod['size']}" if matched_prod.get('size') else ""
            color_info = f"Rangi: {matched_prod['color']}" if matched_prod.get('color') else ""
            details = ", ".join(filter(None, [size_info, color_info]))
            
            return (
                f"Ha, albatta bor! Do'konimizda {matched_prod['name']} mavjud.\n"
                f"{details}.\n"
                f"Narxi: {matched_prod['sale_price']:,.0f} so'm ({stock_str}).\n"
                f"Xarid qilish niyatida bo'lsangiz, buyurtmani rasmiylashtirib berishim mumkin."
            )

        # 8. Do'konda yo'q mahsulot so'ralganda (butsa bormi, kitob bormi, telefon bormi...)
        if any(w in text_lower for w in ["bormi", "bormikan", "bormi?"]):
            # Agar tovar bazada topilmagan bo'lsa
            return (
                "Kechirasiz, do'konimizda bunday mahsulot mavjud emas.\n"
                "Bizda asosan sifatli erkaklar va ayollar kiyimlari, poyabzallar hamda aksessuarlar bor.\n"
                "Sizga mos kiyim yoki poyabzal tanlashda yordam beraymi?"
            )

        # 9. Salomlashish (Assalomu alaykum, jinsini taxmin qilmasdan)
        if any(w in text_lower for w in ["salom", "assalom", "qalesiz", "yaxshimisiz", "bormisiz"]):
            clean_name = customer_name if customer_name and customer_name != "Mijoz" else ""
            greeting = f"Assalomu alaykum, {clean_name}!" if clean_name else "Assalomu alaykum!"
            return (
                f"{greeting} Do'konimizda erkaklar, ayollar, bolalar kiyimlari va sifatli poyabzallar mavjud.\n"
                f"Sizga aynan qaysi turdagi mahsulot ma'qul, qanday kiyim qidiryapsiz?"
            )

        # 10. Kategoriya bo'yicha qidiruv
        found_category = None
        if "erkak" in text_lower:
            found_category = "Erkaklar kiyimi"
        elif "ayol" in text_lower or "ko'ylak" in text_lower:
            found_category = "Ayollar kiyimi"
        elif "bola" in text_lower or "qizim" in text_lower or "o'g'lim" in text_lower:
            found_category = "Bolalar kiyimi"
        elif "sumka" in text_lower or "kamar" in text_lower:
            found_category = "Sumkalar va aksessuarlar"
        elif "sochiq" in text_lower:
            found_category = "Sochiqlar va uy to'qimachiligi"

        if found_category:
            products = DatabaseManager.get_products(category=found_category, in_stock_only=True)
            if products:
                reply_lines = [f"{found_category} bo'limida quyidagi mahsulotlar mavjud:"]
                for idx, p in enumerate(products[:3], 1):
                    stock = p['stock_quantity']
                    stock_str = f"oxirgi {stock} ta qoldi" if stock <= 2 and stock > 0 else f"{stock} ta bor"
                    reply_lines.append(f"{idx}. {p['name']} ({p['size']}) — {p['sale_price']:,.0f} so'm ({stock_str})")
                reply_lines.append("Qaysi biri sizga ma'qul bo'ldi?")
                return "\n".join(reply_lines)

        # 11. Boshqa umumiy murojaat
        return (
            "Do'konimizda sifatli erkaklar va ayollar kiyimlari, poyabzallar va aksessuarlar mavjud.\n"
            "Sizga aynan qanday mahsulot yoki o'lcham kerak, yordam beraymi?"
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
