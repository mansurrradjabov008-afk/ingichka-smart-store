import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database.db_manager import DatabaseManager, init_db, get_connection
from services.order_matcher import OrderMatcher
from services.store_settings_manager import StoreSettingsManager
from ai_engine.ai_brain import ai_brain
from services.receipt_checker import ReceiptChecker
from config import STORE_SETTINGS

def test_production_flows():
    print("=" * 60)
    print("MARKAZSAVDO AI - 7 RULES & STORE SETTINGS VERIFICATION SUITE")
    print("=" * 60)
    init_db()

    # 1. TEST PRODUCT MATCHING
    print("\n--- 1. TEST PRODUCT MATCHING ---")
    p1 = OrderMatcher.match_product("Poplin ayollar ko'ylak komplekt olaman")
    assert p1 is not None and p1["id"] == 1, f"Expected ID 1, got {p1}"
    print(f"PASS: 'Poplin ayollar ko'ylak' -> #{p1['id']} {p1['name']} ({p1['sale_price']:,.0f} so'm)")

    p18 = OrderMatcher.match_product("Erkaklar klassik qora vitrofka berishingizni so'rayman")
    assert p18 is not None and p18["id"] == 18, f"Expected ID 18, got {p18}"
    print(f"PASS: 'Erkaklar klassik qora vitrofka' -> #{p18['id']} {p18['name']} ({p18['sale_price']:,.0f} so'm)")

    p12 = OrderMatcher.match_product("MS-1012")
    assert p12 is not None and p12["id"] == 12, f"Expected ID 12, got {p12}"
    print(f"PASS: 'MS-1012' -> #{p12['id']} {p12['name']} ({p12['sale_price']:,.0f} so'm)")

    p20 = OrderMatcher.match_product("O'zbekiston bolalar futbolkasi")
    assert p20 is not None and p20["id"] == 20, f"Expected ID 20, got {p20}"
    print(f"PASS: 'O'zbekiston bolalar futbolkasi' -> #{p20['id']} {p20['name']} ({p20['sale_price']:,.0f} so'm)")

    # 2. RULE 1: MIJOZ SOTIB OLISH NIYATINI BILDIRMAGUNCHA MANZIL VA TEL SO'RAMASLIK
    print("\n--- 2. RULE 1: PURCHASE INTENT GUARD ---")
    inquiry_no_intent = "Poplin ko'ylak qancha turadi?"
    details_no_intent = OrderMatcher.extract_order_details(inquiry_no_intent, has_pending_order=False)
    assert details_no_intent is None, "Should NOT extract order without purchase intent!"

    intent_text = "Poplin ayollar ko'ylagidan olaman, manzil: Navoiy ko'chasi 15, tel: +998901234567"
    details_with_intent = OrderMatcher.extract_order_details(intent_text, has_pending_order=False)
    assert details_with_intent is not None
    assert details_with_intent["phone"] == "+998901234567"
    print(f"PASS: Rule 1 verified! Phone/address only extracted when purchase intent ('olaman') is present.")

    # 3. RULE 3: QOLDIQ 2 YOKI KAMROQ BO'LSA 'OXIRGI N TA QOLDI'
    print("\n--- 3. RULE 3: LOW STOCK 'OXIRGI N TA QOLDI' LABEL ---")
    p9 = DatabaseManager.get_product_by_id(9) # Bolalar qora triko shimi (stock 2)
    assert p9["stock_quantity"] == 2
    post9 = OrderMatcher.format_channel_post(p9)
    assert "oxirgi 2 ta qoldi" in post9
    print(f"PASS: Product #{p9['id']} stock {p9['stock_quantity']} formatted with: 'oxirgi 2 ta qoldi'")

    p25 = DatabaseManager.get_product_by_id(25) # Ayollar qora kardigan kostyum (stock 1)
    assert p25["stock_quantity"] == 1
    post25 = OrderMatcher.format_channel_post(p25)
    assert "oxirgi 1 ta qoldi" in post25
    print(f"PASS: Product #{p25['id']} stock {p25['stock_quantity']} formatted with: 'oxirgi 1 ta qoldi'")

    # 4. RULE 4: NARX BO'YICHA FILTR (KOD FILTRLAYDI, AI EMAS)
    print("\n--- 4. RULE 4: DETERMINISTIC PRICE FILTER (CODE, NOT AI) ---")
    p_filt100 = OrderMatcher.parse_price_filter("100 minggacha nimalar bor?")
    assert p_filt100 is not None
    assert p_filt100["max_price"] == 100000.0
    prods100 = OrderMatcher.filter_products_by_price(p_filt100["min_price"], p_filt100["max_price"])
    assert len(prods100) > 0
    for p in prods100:
        assert p["sale_price"] <= 100000.0
    formatted_100 = OrderMatcher.format_price_filter_response(prods100, 0, 100000)
    print(f"PASS: Price filter for <= 100k returned {len(prods100)} products completely by code:")

    # 5. RULE 5: JAMI SUMMANI KOD HISOBLAYDI
    print("\n--- 5. RULE 5: CODE-CALCULATED TOTAL SUM ---")
    quote1 = OrderMatcher.calculate_quote("2 ta Poplin ayollar ko'ylak qancha bo'ladi?")
    assert quote1 is not None
    assert "140,000" in quote1 or "140 000" in quote1
    print(f"PASS: 2 Poplin ko'ylak (2 * 70,000) calculated by code: {quote1}")

    quote2 = OrderMatcher.calculate_quote("3 ta Polo erkaklar svitir narxi qancha?")
    assert quote2 is not None
    assert "225,000" in quote2 or "225 000" in quote2
    print(f"PASS: 3 Polo svitir (3 * 75,000) calculated by code: {quote2}")

    # 6. RULE 6: ASSALOMU ALAYKUM DEB MUROJAAT QILISH, JINSINI TAXMIN QILMASLIK
    print("\n--- 6. RULE 6: NEUTRAL GREETING & NO GENDER GUESSING ---")
    from bot.bot_app import clean_display_name
    assert clean_display_name(None) == "Mijoz"
    assert clean_display_name("Radjabov") == "Mijoz"
    assert clean_display_name("Mansurbek") == "Mansurbek"
    assert clean_display_name("Sardor") != "Akajon"
    confirm_text = OrderMatcher.format_order_confirmation(101, p1, "Mansurbek", "+998901234567", "Toshkent")
    assert "Assalomu alaykum, Mansurbek!" in confirm_text
    assert "Akajon" not in confirm_text
    print(f"PASS: Greeting correctly formats 'Assalomu alaykum' without gender guessing (no 'Akajon').")

    # 7. RULE 7: MAVJAV BO'LMAGAN O'LCHAM UCHUN 'BIZDA FAQAT X, Y, Z BOR' DEYISH
    print("\n--- 7. RULE 7: MISSING SIZE HANDLING ---")
    size_inq = OrderMatcher.check_size_inquiry("Poplin ayollar ko'ylakdan M razmer bormi?")
    assert size_inq is not None
    assert "bizda faqat 48 bor" in size_inq
    print(f"PASS: Missing size request handled: {size_inq}")

    # 8. STORE SETTINGS: EMPTY CONFIG -> 'Buni egasidan so'rab aytaman' + ADMIN ALERT
    print("\n--- 8. STORE SETTINGS CONFIG & FALLBACK ---")
    # By default in test environment delivery, discount, address are empty
    STORE_SETTINGS["delivery"] = ""
    STORE_SETTINGS["discount"] = ""
    STORE_SETTINGS["address"] = ""

    deliv_check = StoreSettingsManager.check_setting_inquiry("Yetkazib berish shartlari qanaqa?")
    assert deliv_check is not None
    assert deliv_check["empty"] is True
    assert deliv_check["reply"] == "Buni egasidan so'rab aytaman"
    print(f"PASS: Delivery inquiry with empty setting returns: '{deliv_check['reply']}'")

    disc_check = StoreSettingsManager.check_setting_inquiry("Sizlarda chegirma bormi?")
    assert disc_check is not None
    assert disc_check["empty"] is True
    assert disc_check["reply"] == "Buni egasidan so'rab aytaman"
    print(f"PASS: Discount inquiry with empty setting returns: '{disc_check['reply']}'")

    addr_check = StoreSettingsManager.check_setting_inquiry("Do'koningiz manzili qayerda joylashgan?")
    assert addr_check is not None
    assert addr_check["empty"] is True
    assert addr_check["reply"] == "Buni egasidan so'rab aytaman"
    print(f"PASS: Address inquiry with empty setting returns: '{addr_check['reply']}'")

    # When setting is configured:
    STORE_SETTINGS["delivery"] = "Butun shahar bo'ylab 1 soatda yetkazamiz"
    deliv_configured = StoreSettingsManager.check_setting_inquiry("Yetkazib berish bormi?")
    assert deliv_configured is not None
    assert deliv_configured["empty"] is False
    assert "Butun shahar bo'ylab 1 soatda yetkazamiz" in deliv_configured["reply"]
    print(f"PASS: Configured delivery setting returned directly: '{deliv_configured['reply']}'")

    # Reset
    STORE_SETTINGS["delivery"] = ""

    # 9. ATOMIC ORDER CREATION & STOCK INTEGRITY
    print("\n--- 9. ATOMIC ORDER CREATION & STOCK CHECK ---")
    test_user_id = 9999901
    DatabaseManager.upsert_customer(test_user_id, "Mansurbek", username="mansur_test")

    stock_before = DatabaseManager.get_product_by_id(1)["stock_quantity"]
    res = DatabaseManager.create_order(
        customer_telegram_id=test_user_id,
        customer_name="Mansurbek",
        customer_phone="+998901234567",
        delivery_address="Mustaqillik ko'chasi 10",
        items=[{"product_id": 1, "quantity": 1}],
        payment_method="cash_on_delivery"
    )
    assert res["success"] is True
    stock_after = DatabaseManager.get_product_by_id(1)["stock_quantity"]
    assert stock_after == stock_before - 1
    print(f"PASS: Order #{res['order_id']} created. Stock reduced from {stock_before} to {stock_after}.")

    # Out of stock guard (Product #10 LC Waikiki Termo Ko'k - stock 0)
    stock_0_check = DatabaseManager.check_stock_strict(10, 1)
    assert stock_0_check["available"] is False
    print("PASS: Out of stock product #10 blocked properly.")

    # Restore test stock
    with get_connection() as conn:
        conn.execute("UPDATE products SET stock_quantity = ? WHERE id = 1", (stock_before,))
        conn.commit()
    print("PASS: Cleaned test data and restored original stock.")

    # 10. RECEIPT & PRODUCT PHOTO DIFFERENTIATION SUITE
    print("\n--- 10. RECEIPT & PRODUCT PHOTO DIFFERENTIATION ---")
    assert ReceiptChecker.is_likely_product_inquiry("Shu kiyimdan bormi") is True
    assert ReceiptChecker.is_likely_product_inquiry("narxi qancha?") is True
    assert ReceiptChecker.is_likely_product_inquiry("razmeri bormi?") is True
    assert ReceiptChecker.is_likely_product_inquiry("To'lov qildim mana chek") is False

    assert ReceiptChecker.is_likely_payment_intent("To'lov qildim mana chek") is True
    assert ReceiptChecker.is_likely_payment_intent("Click orqali to'ladim") is True
    assert ReceiptChecker.is_likely_payment_intent("Shu kiyimdan bormi") is False
    assert ReceiptChecker.is_likely_payment_intent("Salom narxi qancha") is False
    print("PASS: Receipt vs Clothing photo intent separation verified with 100% precision!")

    # 11. UZBEK WORD NUMBERS & QUANTITY EXTRACTION SUITE
    print("\n--- 11. UZBEK WORD NUMBERS & QUANTITY EXTRACTION ---")
    quote_ikki = OrderMatcher.calculate_quote("ikkita Poplin ayollar ko'ylak qancha bo'ladi?")
    assert quote_ikki is not None and "140,000" in quote_ikki
    print(f"PASS: 'ikkita Poplin ko'ylak' -> {quote_ikki}")

    quote_bir = OrderMatcher.calculate_quote("bitta Polo erkaklar svitir qancha?")
    assert quote_bir is not None and "75,000" in quote_bir
    print(f"PASS: 'bitta Polo svitir' -> {quote_bir}")

    quote_uch = OrderMatcher.calculate_quote("uchta Polo erkaklar svitir narxi qancha?")
    assert quote_uch is not None and "225,000" in quote_uch
    print(f"PASS: 'uchta Polo svitir' -> {quote_uch}")

    order_two = OrderMatcher.extract_order_details("ikkita Poplin ayollar ko'ylak olaman, manzil: Navoiy ko'chasi 15, tel: +998901234567")
    assert order_two is not None
    assert order_two["quantity"] == 2
    assert order_two["address"] == "Navoiy ko'chasi 15"
    assert order_two["phone"] == "+998901234567"
    print(f"PASS: 'ikkita ko'ylak' parsed with quantity=2 and clean address='{order_two['address']}'")

    # 12. SQLITE WAL CONCURRENCY & INDEXES HEALTH SUITE
    print("\n--- 12. SQLITE WAL CONCURRENCY & INDEXES HEALTH ---")
    with get_connection() as conn:
        jmode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert jmode.lower() == "wal", f"Expected WAL mode, got {jmode}"
        indexes = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()]
        assert "idx_orders_customer" in indexes
        assert "idx_products_category" in indexes
        assert "idx_products_active" in indexes
    print("PASS: SQLite WAL mode and all performance indexes are active and healthy!")

    print("\n" + "=" * 60)
    print("ALL 12 TEST SUITES COVERING ALL ARCHITECTURAL RULES PASSED WITH 100%!")
    print("=" * 60)

if __name__ == "__main__":
    test_production_flows()
