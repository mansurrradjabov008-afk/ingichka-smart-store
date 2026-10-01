import sys
from pathlib import Path
import base64

# Add project root
sys.path.append(str(Path(__file__).resolve().parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import GEMINI_API_KEY
from database.db_manager import DatabaseManager, init_db
from ai_engine.ai_brain import ai_brain
from services.analytics_advisor import AnalyticsAdvisor
from services.inventory_manager import InventoryManager

def run_superpowers_verification():
    print("=================================================================")
    print("⚡ BARCHA YANGI KUCH VA FUNKSIYALARNI 100% TEKSHIRISH")
    print("=================================================================\n")

    init_db()

    # 1. AI Matnli muloqot testi (Gemini Flash)
    print("--- 1. GEMINI AI MATN TESTI ---")
    reply = ai_brain.ask(user_id=888, user_message="Do'konda ayollar ko'ylaklari bormi?", customer_name="Nodira opa")
    print("AI Javobi:\n", reply[:250], "...\n")
    assert len(reply) > 20, "AI javobi bo'sh!"
    print("✅ 1-Test Muvaffaqiyatli!")

    # 2. Multimodal Vision Testi (Rasm ko'rish)
    print("\n--- 2. GEMINI MULTIMODAL VISION (RASM KO'RISH) TESTI ---")
    # 1x1 test image
    tiny_jpeg = base64.b64decode('/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=')
    b64_img = base64.b64encode(tiny_jpeg).decode('utf-8')
    vision_reply = ai_brain.ask_with_photo(user_id=888, image_b64=b64_img, caption="Shunaqasidan bormi?", customer_name="Nodira opa")
    print("Vision AI Javobi:\n", vision_reply[:250], "...\n")
    assert len(vision_reply) > 10, "Vision javobi bo'sh!"
    print("✅ 2-Test Muvaffaqiyatli!")

    # 3. Buyurtma yaratish va Ombor zaxirasini qaytarish (Bekor qilish testi)
    print("\n--- 3. BUYURTMA BEKOR QILINSA OMBORGA QAYTARISH TESTI ---")
    prods = DatabaseManager.get_products(in_stock_only=True)
    test_prod = prods[0]
    stock_before = test_prod["stock_quantity"]

    # Zakaz yaratish
    order = DatabaseManager.create_order(
        customer_telegram_id=888,
        customer_name="Test Xaridor",
        customer_phone="+998901112233",
        delivery_address="Ingichka, Sinov ko'chasi 1-uy",
        items=[{"product_id": test_prod["id"], "quantity": 2}],
        payment_method="cash_on_delivery"
    )
    assert order["success"], "Zakaz yaratilmadi!"
    order_id = order["order_id"]

    # Ombor kamayganini tekshirish
    prod_after_order = DatabaseManager.get_product_by_id(test_prod["id"])
    assert prod_after_order["stock_quantity"] == stock_before - 2, "Ombor to'g'ri kamaymadi!"

    # Buyurtmani bekor qilish
    cancel_success = DatabaseManager.update_order_status(order_id, "bekor")
    assert cancel_success, "Bekor qilib bo'lmadi!"

    # Ombor qayta tiklanganini tekshirish
    prod_after_cancel = DatabaseManager.get_product_by_id(test_prod["id"])
    assert prod_after_cancel["stock_quantity"] == stock_before, "Bekor qilingach ombor tiklanmadi!"
    print(f"✅ 3-Test Muvaffaqiyatli: Qoldiq {stock_before} -> {stock_before - 2} -> {stock_before} (To'liq avtomatik tiklandi)!")

    # 4. Reklama uchun mijozlar bazasi
    print("\n--- 4. REKLAMA TARQATISH BAZASI TESTI ---")
    DatabaseManager.upsert_customer(telegram_id=888, full_name="Nodira opa", phone="+998901234567")
    cust_ids = DatabaseManager.get_all_customers_ids()
    print(f"Bazada jami {len(cust_ids)} ta mijoz ID si topildi.")
    assert len(cust_ids) > 0, "Mijozlar bazasi bo'sh!"
    print("✅ 4-Test Muvaffaqiyatli!")

    # 5. Kassa va Ombor hisoboti
    print("\n--- 5. KASSA VA OMBOR TAHLILI ---")
    rep = AnalyticsAdvisor.get_sales_report("day")
    assert rep["total_revenue"] >= 0, "Hisobot xatosi!"
    print(f"Bugungi tushum: {rep['total_revenue']:,.0f} so'm | Sof foyda: {rep['net_profit']:,.0f} so'm")
    print("✅ 5-Test Muvaffaqiyatli!")

    print("\n=================================================================")
    print("🏆 BARCHA 5 TA TEST 100% MUVAFFAQIShLI YAKUNLANDI! XATOLIK: 0")
    print("=================================================================")

if __name__ == "__main__":
    run_superpowers_verification()
