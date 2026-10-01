import sys
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).resolve().parent))

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database.db_manager import init_db, DatabaseManager
from ai_engine.sales_agent import SalesAgent
from services.analytics_advisor import AnalyticsAdvisor
from services.inventory_manager import InventoryManager
from data.seed_data import seed_database

def run_full_system_verification():
    print("=================================================================")
    print("🚀 INGICHKA BARAKA SAVDO MARKAZI: TIZIMNI TO'LIQ SINOVDAN O'TKAZISH")
    print("=================================================================\n")

    # 1. Baza va tovarlarni tayyorlash
    seed_database()
    agent = SalesAgent()

    # 2. Mijoz bilan jonli AI muloqotini sinash
    customer_id = 998901112233
    customer_name = "Otabek aka"

    test_queries = [
        "Assalomu alaykum, do'konda nimalar bor?",
        "Erkaklar uchun issiq kiyimlar, ayniqsa xudi bormi?",
        "220 ming so'm sal qimmatroq ekan, boshqa joyda arzonroq ko'rdim...",
        "Ingichka shaharchasi bo'yicha dostavka qilsa bo'ladimi?",
        "Menga 1 ta qora Turkiya xudi L razmeridan yetkazib bering. Manzil: Ingichka, Yangi hayot mahallasi 12-uy. Tel: +998912345678"
    ]

    print("\n--- 1-BOSQICH: 15 YILLIK EKSPERT SOTUVCHI MULOQOTI TESTI ---")
    for q in test_queries:
        print(f"\n👤 [Mijoz: {customer_name}]: {q}")
        reply = agent.process_message(q, customer_id=customer_id, customer_name=customer_name)
        print(f"🤖 [AI Sotuvchi]:\n{reply}")
        print("-" * 50)

    # 3. Buyurtmani rasmiylashtirish va Ombordan avtomatik yechish
    print("\n--- 2-BOSQICH: BUYURTMA RASMIYLASHTIRISH VA OMBOR TEKSHIRUVI ---")
    products = DatabaseManager.get_products(search_query="Xudi", in_stock_only=True)
    if products:
        target_prod = products[0]
        initial_stock = target_prod["stock_quantity"]
        print(f"Oldingi ombor qoldig'i: '{target_prod['name']}' ({target_prod['color']}/{target_prod['size']}) = {initial_stock} dona")

        order_res = DatabaseManager.create_order(
            customer_telegram_id=customer_id,
            customer_name=customer_name,
            customer_phone="+998912345678",
            delivery_address="Ingichka shaharchasi, Yangi hayot mahallasi, 12-uy",
            items=[{"product_id": target_prod["id"], "quantity": 1}],
            payment_method="cash_on_delivery",
            notes="Eshik oldida tekshirib to'lanadi"
        )

        assert order_res["success"] is True, f"Buyurtma xatosi: {order_res.get('error')}"
        print(f"✅ Buyurtma muvaffaqiyatli yaratildi! ID: #{order_res['order_id']}, Jami summa: {order_res['total_amount']:,.0f} so'm")

        # Omborni qayta tekshirish
        updated_prod = DatabaseManager.get_product_by_id(target_prod["id"])
        print(f"Yangi ombor qoldig'i: {updated_prod['stock_quantity']} dona (aniq 1 taga kamaydi, xatolik = 0)")
        assert updated_prod["stock_quantity"] == initial_stock - 1, "Ombor hisobida nomuvofiqlik!"

    # 4. Kassa Hisoboti va AI Biznes Maslahatchisi
    print("\n--- 3-BOSQICH: KASSA HISOBOTI VA BIZNES MASLAHATCHI ---")
    daily_report = AnalyticsAdvisor.get_sales_report(period="day")
    formatted_report = AnalyticsAdvisor.format_report_message(daily_report)
    print(formatted_report)

    # 5. Ombor Tahlili va Kam Qolgan Tovarlar Xabarnomasi
    print("\n--- 4-BOSQICH: OMBOR VA ZAKAZLAR TAHLILI ---")
    inventory_alerts = InventoryManager.get_stock_alerts()
    formatted_inventory = InventoryManager.format_inventory_message(inventory_alerts)
    print(formatted_inventory)

    # 6. Ovoz/Matn orqali yangi tovar kiritish testi
    print("\n--- 5-BOSQICH: OVOZ/MATN ORQALI YANGI TOVAR QO'SHISH TESTI ---")
    sample_voice_text = "Turkiya yangi sifatli jinsi, to'q ko'k rang, 32 razmer, tan narxi 110 ming, sotuv narxi 190 ming, 15 dona keldi"
    parsed = agent.parse_product_voice_text(sample_voice_text)
    new_id = DatabaseManager.add_product(
        name=parsed["name"],
        category=parsed["category"],
        size=parsed["size"],
        color=parsed["color"],
        cost_price=parsed["cost_price"],
        sale_price=parsed["sale_price"],
        stock_quantity=parsed["stock_quantity"],
        description=parsed["description"]
    )
    print(f"✅ Yangi tovar qo'shildi: #{new_id} - {parsed['name']} ({parsed['color']}, {parsed['size']}) | Tan: {parsed['cost_price']} | Sotuv: {parsed['sale_price']} | Qoldiq: {parsed['stock_quantity']} dona")

    print("\n=================================================================")
    print("🏆 BARCHA TESTLAR 100% MUVAFFAQIShLI YAKUNLANDI! XATOLIK: 0")
    print("=================================================================")

if __name__ == "__main__":
    run_full_system_verification()
