import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.db_manager import init_db, DatabaseManager

SAMPLE_PRODUCTS = [
    # 1. Erkaklar kiyimi
    {
        "name": "Turkiya Premium Xudi (Kapushonka)",
        "category": "Erkaklar kiyimi",
        "size": "L",
        "color": "Qora",
        "cost_price": 140000,
        "sale_price": 220000,
        "stock_quantity": 8,
        "description": "100% paxta, ichi momiq (nachess), sovuqda issiq tutadi, rangi o'chmaydi."
    },
    {
        "name": "Turkiya Premium Xudi (Kapushonka)",
        "category": "Erkaklar kiyimi",
        "size": "M",
        "color": "To'q ko'k",
        "cost_price": 140000,
        "sale_price": 220000,
        "stock_quantity": 4, # Low stock!
        "description": "Zamonaviy fason, har qanday sportivka yoki jinsi bilan ajoyib yarashadi."
    },
    {
        "name": "Klassik Erkaklar Ko'ylagi",
        "category": "Erkaklar kiyimi",
        "size": "XL",
        "color": "Oq",
        "cost_price": 95000,
        "sale_price": 160000,
        "stock_quantity": 12,
        "description": "Dazmol talab qilmaydigan yumshoq toza mato. To'y va kundalik kiyish uchun ideal."
    },
    {
        "name": "Erkaklar Qalin Qishki Kurtkasi (Koreya)",
        "category": "Erkaklar kiyimi",
        "size": "L",
        "color": "Qora",
        "cost_price": 320000,
        "sale_price": 480000,
        "stock_quantity": 3, # Low stock!
        "description": "Suv va shamol o'tkazmaydigan qalin xolofayber astarli issiq kurtka."
    },

    # 2. Ayollar kiyimi
    {
        "name": "Elegant Kuzgi Ayollar Kardigani",
        "category": "Ayollar kiyimi",
        "size": "Standart (42-48)",
        "color": "Och bejiviy",
        "cost_price": 120000,
        "sale_price": 195000,
        "stock_quantity": 6,
        "description": "Yumshoq yupqa junli ipdan to'qilgan, nihoyatda chiroyli va qulay kardigan."
    },
    {
        "name": "Ayollar Trikotaj Sport Kostyumi",
        "category": "Ayollar kiyimi",
        "size": "M",
        "color": "Pushti (Pudra)",
        "cost_price": 160000,
        "sale_price": 260000,
        "stock_quantity": 2, # Low stock!
        "description": "Uyda va ko'chada kiyishga nihoyatda qulay, keng va zamonaviy fason."
    },
    {
        "name": "Klassik Ayollar Gullik Ko'ylagi",
        "category": "Ayollar kiyimi",
        "size": "L",
        "color": "Zumrad yashil",
        "cost_price": 130000,
        "sale_price": 210000,
        "stock_quantity": 0, # Out of stock! (Test zero hallucination)
        "description": "Shoyi aralash sifatli mato, bayramlar uchun mos."
    },

    # 3. Bolalar kiyimi
    {
        "name": "Bolalar Momiqli Qishki Sportivkasi",
        "category": "Bolalar kiyimi",
        "size": "5-7 yosh",
        "color": "Kulrang",
        "cost_price": 85000,
        "sale_price": 140000,
        "stock_quantity": 10,
        "description": "Bolajonlar uchun terlatmaydigan toza paxta, ichi issiq momiqli."
    },
    {
        "name": "Bolalar Issiq Nimchasi (Jiletka)",
        "category": "Bolalar kiyimi",
        "size": "8-10 yosh",
        "color": "Ko'k",
        "cost_price": 75000,
        "sale_price": 125000,
        "stock_quantity": 4, # Low stock!
        "description": "Shamol o'tkazmaydigan yengil va qulay bolalar jiletkasi."
    },

    # 4. Sumkalar va aksessuarlar
    {
        "name": "Erkaklar Tabiiy Charm Qora Sumkasi (Messendjer)",
        "category": "Sumkalar va aksessuarlar",
        "size": "Ixcham (Planshet sig'adi)",
        "color": "Qora",
        "cost_price": 110000,
        "sale_price": 185000,
        "stock_quantity": 7,
        "description": "Hujjatlar, telefon va pul uchun mustahkam zamokli charm yelkama sumka."
    },
    {
        "name": "Ayollar Zamonaviy Qo'l Sumkasi",
        "category": "Ayollar kiyimi",
        "size": "O'rtacha",
        "color": "Shokolad jigarrang",
        "cost_price": 95000,
        "sale_price": 165000,
        "stock_quantity": 5,
        "description": "Klassik va zamonaviy uslubdagi sig'imli ayollar sumkasi."
    },

    # 5. Sochiqlar va uy to'qimachiligi
    {
        "name": "Turkiya Banya Sochiqlar To'plami (2 talik)",
        "category": "Sochiqlar va uy to'qimachiligi",
        "size": "70x140 sm va 50x90 sm",
        "color": "Oq / Ko'k",
        "cost_price": 70000,
        "sale_price": 120000,
        "stock_quantity": 15,
        "description": "100% paxta maxroviy yumshoq sochiqlar, suvni bir zumda shimib oladi."
    },
    {
        "name": "Oshxona Sochiqlari (6 talik to'plam)",
        "category": "Sochiqlar va uy to'qimachiligi",
        "size": "30x50 sm",
        "color": "Gulli aralash",
        "cost_price": 35000,
        "sale_price": 65000,
        "stock_quantity": 20,
        "description": "Chiroyli bezakli, har bir xonadon oshxonasiga kerakli to'plam."
    }
]

def seed_database():
    init_db()
    print("Bazani tozalash va tayyorlash...")
    
    # Check if products already exist
    existing = DatabaseManager.get_products(in_stock_only=False)
    if existing:
        print(f"Bazada allaqachon {len(existing)} ta mahsulot mavjud.")
        return

    count = 0
    for p in SAMPLE_PRODUCTS:
        DatabaseManager.add_product(
            name=p["name"],
            category=p["category"],
            size=p["size"],
            color=p["color"],
            cost_price=p["cost_price"],
            sale_price=p["sale_price"],
            stock_quantity=p["stock_quantity"],
            description=p["description"]
        )
        count += 1

    print(f"Muvaffaqiyatli: {count} ta mahsulot omborga kiritildi!")

if __name__ == "__main__":
    seed_database()
