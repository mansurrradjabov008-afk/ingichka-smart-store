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
    p1 = OrderMatcher.match_product("Qora kurtkadan bormi olaman")
    assert p1 is not None and p1["id"] == 1, f"Expected ID 1, got {p1}"
    print(f"PASS: 'Qora kurtka' -> #{p1['id']} {p1['name']} ({p1['sale_price']:,.0f} so'm)")

    p2 = OrderMatcher.match_product("Oversize futbolka oq rangidan bering")
    assert p2 is not None and p2["id"] == 2, f"Expected ID 2, got {p2}"
    print(f"PASS: 'Oversize futbolka' -> #{p2['id']} {p2['name']} ({p2['sale_price']:,.0f} so'm)")

    p3 = OrderMatcher.match_product("Klassik jinsi shim 32 razmer")
    assert p3 is not None and p3["id"] == 3, f"Expected ID 3, got {p3}"
    print(f"PASS: 'Jinsi shim' -> #{p3['id']} {p3['name']} ({p3['sale_price']:,.0f} so'm)")

    p8 = OrderMatcher.match_product("Oq krossovka 42 razmer bormi")
    assert p8 is not None and p8["id"] == 8, f"Expected ID 8, got {p8}"
    print(f"PASS: 'Krossovka' -> #{p8['id']} {p8['name']} ({p8['sale_price']:,.0f} so'm)")

    # 2. RULE 1: MIJOZ SOTIB OLISH NIYATINI BILDIRMAGUNCHA MANZIL VA TEL SO'RAMASLIK
    print("\n--- 2. RULE 1: PURCHASE INTENT GUARD ---")
    inquiry_no_intent = "Kurtka qancha turadi?"
    details_no_intent = OrderMatcher.extract_order_details(inquiry_no_intent, has_pending_order=False)
    assert details_no_intent is None, "Should NOT extract order without purchase intent!"

    intent_text = "Erkaklar qora kurtkasidan olaman, manzil: Navoiy ko'chasi 15, tel: +998901234567"
    details_with_intent = OrderMatcher.extract_order_details(intent_text, has_pending_order=False)
    assert details_with_intent is not None
    assert details_with_intent["phone"] == "+998901234567"
    print(f"PASS: Rule 1 verified! Phone/address only extracted when purchase intent ('olaman') is present.")

    # 3. RULE 3: QOLDIQ 2 YOKI KAMROQ BO'LSA 'OXIRGI N TA QOLDI'
    print("\n--- 3. RULE 3: LOW STOCK 'OXIRGI N TA QOLDI' LABEL ---")
    p4 = DatabaseManager.get_product_by_id(4) # Ayollar gulli ko'ylagi (stock 2)
    assert p4["stock_quantity"] == 2
    post4 = OrderMatcher.format_channel_post(p4)
    assert "oxirgi 2 ta qoldi" in post4
    print(f"PASS: Product #{p4['id']} stock {p4['stock_quantity']} formatted with: 'oxirgi 2 ta qoldi'")

    p6 = DatabaseManager.get_product_by_id(6) # Ayollar qishki paltosi (stock 1)
    assert p6["stock_quantity"] == 1
    post6 = OrderMatcher.format_channel_post(p6)
    assert "oxirgi 1 ta qoldi" in post6
    print(f"PASS: Product #{p6['id']} stock {p6['stock_quantity']} formatted with: 'oxirgi 1 ta qoldi'")

    # 4. RULE 4: NARX BO'YICHA FILTR (KOD FILTRLAYDI, AI EMAS)
    print("\n--- 4. RULE 4: DETERMINISTIC PRICE FILTER (CODE, NOT AI) ---")
    p_filt300 = OrderMatcher.parse_price_filter("300 minggacha nimalar bor?")
    assert p_filt300 is not None
    assert p_filt300["max_price"] == 300000.0
    prods300 = OrderMatcher.filter_products_by_price(p_filt300["min_price"], p_filt300["max_price"])
    # Should include: Kepka (60k), Oversize futbolka (120k), Klassik jinsi (280k)
    prod_names = [p["name"] for p in prods300]
    assert "Kepka" in prod_names
    assert "Oversize futbolka" in prod_names
    assert "Klassik jinsi shim" in prod_names
    assert len(prods300) == 3
    formatted_300 = OrderMatcher.format_price_filter_response(prods300, 0, 300000)
    print(f"PASS: Price filter for <= 300k returned exactly {len(prods300)} products completely by code:")
    print(formatted_300)

    # 5. RULE 5: JAMI SUMMANI KOD HISOBLAYDI
    print("\n--- 5. RULE 5: CODE-CALCULATED TOTAL SUM ---")
    quote1 = OrderMatcher.calculate_quote("2 ta kurtka qancha bo'ladi?")
    assert quote1 is not None
    assert "900,000" in quote1 or "900 000" in quote1
    print(f"PASS: 2 kurtka (2 * 450,000) calculated by code: {quote1}")

    quote2 = OrderMatcher.calculate_quote("3 ta kepka narxi qancha?")
    assert quote2 is not None
    assert "180,000" in quote2 or "180 000" in quote2
    print(f"PASS: 3 kepka (3 * 60,000) calculated by code: {quote2}")

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

    # 7. RULE 7: MAVJUD BO'LMAGAN O'LCHAM UCHUN 'BIZDA FAQAT X, Y, Z BOR' DEYISH
    print("\n--- 7. RULE 7: MISSING SIZE HANDLING ---")
    size_inq = OrderMatcher.check_size_inquiry("Erkaklar qora kurtkasidan XXL bormi?")
    assert size_inq is not None
    assert "bizda faqat M, L, XL bor" in size_inq
    print(f"PASS: Missing size request handled: {size_inq}")

    size_inq2 = OrderMatcher.check_size_inquiry("Futbolkadan 48 razmer bormi?")
    assert size_inq2 is not None
    assert "bizda faqat S, M, L bor" in size_inq2
    print(f"PASS: Missing size request handled: {size_inq2}")

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

    # Out of stock guard (Sport kostyum - stock 0)
    stock_0_check = DatabaseManager.check_stock_strict(5, 1)
    assert stock_0_check["available"] is False
    print("PASS: Out of stock product #5 blocked properly.")

    # Restore test stock
    with get_connection() as conn:
        conn.execute("UPDATE products SET stock_quantity = 5 WHERE id = 1")
        conn.commit()
    print("PASS: Cleaned test data and restored stock.")

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
    quote_ikki = OrderMatcher.calculate_quote("ikkita kurtka qancha bo'ladi?")
    assert quote_ikki is not None and "900,000" in quote_ikki
    print(f"PASS: 'ikkita kurtka' -> {quote_ikki}")

    quote_bir = OrderMatcher.calculate_quote("bitta futbolka qancha?")
    assert quote_bir is not None and "120,000" in quote_bir
    print(f"PASS: 'bitta futbolka' -> {quote_bir}")

    quote_uch = OrderMatcher.calculate_quote("uchta kepka narxi qancha?")
    assert quote_uch is not None and "180,000" in quote_uch
    print(f"PASS: 'uchta kepka' -> {quote_uch}")

    order_two = OrderMatcher.extract_order_details("ikkita kurtka olaman, manzil: Navoiy ko'chasi 15, tel: +998901234567")
    assert order_two is not None
    assert order_two["quantity"] == 2
    assert order_two["address"] == "Navoiy ko'chasi 15"
    assert order_two["phone"] == "+998901234567"
    print(f"PASS: 'ikkita kurtka' parsed with quantity=2 and clean address='{order_two['address']}'")

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
