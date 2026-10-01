"""
services/sales_pitch.py
Do'kon egalari uchun AI Sotuvchi Botning Tijoriy Taklifi (Commercial Pitch)
va "Nega aynan sizning do'koningizga bu AI kerak?" tahlil moduli.
"""

from typing import Dict, Any
from config import STORE_NAME, LOCATION

class SalesPitchAdvisor:
    """
    Do'kon egasini botni sotib olishga 100% ishontiruvchi
    tijoriy va psixologik asoslar generatori.
    """

    @staticmethod
    def get_full_pitch() -> str:
        return (
            f"👑 **NEGA HAR BIR DO'KON EGASI BU AI SOTUVCHINI O'RNATISHI SHART?**\n"
            f"─────────────────────────────────\n\n"
            f"Hurmatli do'kon egasi! Savdoni oshirish va xarajatlarni qisqartirishning "
            f"eng zamonaviy formulasi bilan tanishing:\n\n"
            f"🔥 **1. OYLIK XARAJATNI 10 BAROBAR TEJASH**\n"
            f"• Oddiy sotuvchi: Oyiga kamida **3 500 000 - 5 000 000 so'm** oylik oladi.\n"
            f"  U charchaydi, kechikadi, kasal bo'ladi, ba'zan mijozga beparvo javob beradi.\n"
            f"• **AI Sotuvchi:** Oyiga atigi **300 000 - 500 000 so'm**!\n"
            f"  Dam olishsiz, 24/7 tun-u kun har bir mijozga eng samimiy, xushmuomala xizmat ko'rsatadi.\n"
            f"  👉 *Bir yilda kamida 40 000 000 so'm sof tejab qolasiz!*\n\n"
            f"🌙 **2. KECHKI VA TUNGI SAVDO (Yo'qotilgan 35% tushumni qaytarish)**\n"
            f"• Statistikaga ko'ra, xaridorlarning 35% dan ortig'i soat 20:00 dan 01:00 gacha Telegramda kiyim qidiradi.\n"
            f"• Oddiy do'kon bu paytda yopiq, sotuvchi uxlagan. Natijada xaridor boshqa joydan oladi.\n"
            f"• **Bizning AI esa kechasi ham:**\n"
            f"  - Mijoz bilan gaplashadi;\n"
            f"  - O'lcham va ranglarini tanlatadi;\n"
            f"  - Buyurtmani rasmiylashtirib, ombordan yechadi;\n"
            f"  - Ertalab sizga tayyor buyurtmani stolingizga qo'yadi!\n\n"
            f"🎙️ **3. O'ZBEK MENTALITETI: OVOZLI XABAR VA RASMLARNI TUSHUNISH**\n"
            f"• O'zbekiston xaridorlarining 70%i yozishga erinadi. Ular yo rasm tashlaydi, yo ovoz yuboradi.\n"
            f"• Oddiy botlar bunga tushunmaydi va mijoz chiqib ketadi.\n"
            f"• **Bizning AI:** Rasmni ham ko'radi, ovozli xabarni ham eshitadi va mijozga "
            f"o'zbek tilida jonli ovoz bilan javob qaytaradi!\n\n"
            f"📊 **4. AVTOMATIK EXCEL VA KAMOMADDAN HIMOYALANISH**\n"
            f"• Qog'oz-daftarga yozish davri o'tdi. Qaysi tovar qoldi, qanchasi sotildi, "
            f"qancha sof foyda ko'rdingiz — barchasi 1 tugma bilan chiroyli Excel (.xlsx) jadvalida qo'lingizda bo'ladi.\n"
            f"• Sotuvchi tovardan o'g'irlashi yoki pulni berkitishi mumkin emas.\n\n"
            f"🛡️ **5. SOXTA TO'LOV CHEKLARINI (FRAUD) ANIQLASH**\n"
            f"• Soxta Click/Payme cheklaridan charchadingizmi?\n"
            f"• AI Vision tizimi mijoz tashlagan to'lov chekining haqiqiyligini tekshiradi va soxta bo'lsa darhol ogohlantiradi.\n\n"
            f"⚡ **6. TEZKOR JAVOB VA YUQORI SOTUV**\n"
            f"• Mijoz kutishni yoqtirmaydi. AI 1 soniyada javob berib, buyurtmani qabul qiladi.\n\n"
            f"🎁 **7. 100% BEXATAR KAFOLAT (RISK-FREE)**\n"
            f"• Do'koningizga o'rnatib bering: **3 kun mutlaqo BEPUL sinab ko'ring!**\n"
            f"• Agar 3 kunda sizga yoqmasa yoki foyda keltirmasa — 1 so'm ham to'lamaysiz!\n"
            f"─────────────────────────────────\n"
            f"📞 **Ulanish uchun hoziroq admin bilan bog'laning!**"
        )

    @staticmethod
    def calculate_roi(monthly_sales_volume: float = 20_000_000, seller_salary: float = 4_000_000) -> Dict[str, Any]:
        """Do'kon egasi uchun foyda kalkulyatori"""
        bot_cost = 400_000
        salary_savings = seller_salary - bot_cost
        night_sales_boost = monthly_sales_volume * 0.20
        total_monthly_benefit = salary_savings + (night_sales_boost * 0.25)
        
        return {
            "salary_savings": salary_savings,
            "night_sales_boost": night_sales_boost,
            "total_monthly_benefit": total_monthly_benefit,
            "yearly_benefit": total_monthly_benefit * 12
        }

    @staticmethod
    def format_roi_message(monthly_sales_volume: float = 20_000_000, seller_salary: float = 4_000_000) -> str:
        calc = SalesPitchAdvisor.calculate_roi(monthly_sales_volume, seller_salary)
        return (
            f"💰 **DO'KON EGASI UCHUN ANIQ RAQAMLAR VA FOYDA HISOB-KITOBI:**\n"
            f"─────────────────────────────────\n"
            f"O'rtacha do'kon ko'rsatkichlari misolida:\n"
            f"• Do'kon oylik aylanmasi: **{monthly_sales_volume:,.0f} so'm**\n"
            f"• Sotuvchi xodimi maoshi: **{seller_salary:,.0f} so'm**\n\n"
            f"📈 **AI Bot o'rnatilgandan so'ng:**\n"
            f"1. Oylik xarajatdan tejash: **+{calc['salary_savings']:,.0f} so'm/oy**\n"
            f"2. Kechki va qo'shimcha savdo (+20%): **+{calc['night_sales_boost']:,.0f} so'm/oy**\n"
            f"3. Do'kon egasiga oylik sof qo'shimcha daromad: **+{calc['total_monthly_benefit']:,.0f} so'm/oy**\n\n"
            f"🔥 **BIR YILDA SIZNING CHO'NTAGINGIZDA QOLADIGAN SOF FOYDA:**\n"
            f"👉 **+{calc['yearly_benefit']:,.0f} SO'M!**\n"
            f"─────────────────────────────────\n"
            f"Siz sotuvchiga beradigan oylik puliga AI botni 1 yil ishlatishingiz mumkin!"
        )

    @staticmethod
    def get_growth_hacks() -> str:
        return (
            f"🚀 **DO'KON TUSHUMINI 2-3 BAROBARGA OSHIRUVCHI 5 TA MAXFIY G'OYA:**\n"
            f"─────────────────────────────────\n"
            f"💡 **1. To'g'ri maslahat va tezkor xizmat**\n"
            f"• Mijoz savol berishi bilan unga mos o'lcham va modellarni ko'rsatish.\n"
            f"👉 *Natija: Onlayn savdo konversiyasi bir necha barobar oshadi!*\n\n"
            f"💡 **2. Smart Up-Sell (Komplekt taklifi / O'rtacha chekni ko'tarish)**\n"
            f"• Mahsulot tanlagan mijozga mos aksessuarlarni taklif qilish.\n"
            f"👉 *Natija: Har bir xariddan tushadigan daromad ko'payadi!*\n\n"
            f"💡 **3. Doimiy mijozlar bilan ishlash**\n"
            f"• Xaridorlar bilan samimiy munosabat o'rnatish va sifatli xizmat ko'rsatish.\n"
            f"👉 *Natija: Mijoz doimiy xaridorga aylanadi!*\n\n"
            f"💡 **4. Tungi savdoni yo'lga qo'yish**\n"
            f"• Tunda buyurtma bergan mijozlarga darhol xizmat ko'rsatish.\n"
            f"👉 *Natija: Har doim faol sotuvchi bo'lish!*\n\n"
            f"💡 **5. Xariddan so'ng 100% Qoniqish Nazorati (Customer Care)**\n"
            f"• Buyurtmadan so'ng xaridor fikrini bilish va minnatdorchilik bildirish."
        )
