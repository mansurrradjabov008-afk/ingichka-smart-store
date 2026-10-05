import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.db_manager import DatabaseManager, init_db
from ai_engine.ai_brain import ai_brain
from ai_engine.sales_agent import SalesAgent
from services.order_matcher import OrderMatcher
from services.store_settings_manager import StoreSettingsManager
from services.catalog_service import search_products
import json

def run_deep_audit():
    print("=" * 70)
    print("MARKAZSAVDO 41-PRODUCT REAL STORE INVENTORY AUDIT")
    print("=" * 70)
    init_db()
    agent = SalesAgent()
    errors = []

    # 1. TEST REAL STORE PRODUCT MATCHING
    print("\n--- 1. Real Products Matching (SKU, Brand, Category) ---")
    test_cases = [
        ("poplin koylak bormi", "Poplin ayollar ko'ylak komplekt", 70000),
        ("polo svitir qancha", "Polo erkaklar svitir kofta", 75000),
        ("MS-1012", "Ayollar charmli shippak tapichka", 43000),
        ("ozbekiston futbolka", "O'zbekiston bolalar futbolkasi", 8000),
        ("jinsi troyka", "Bolalar jinsi troyka komplekt", 170000)
    ]
    for q, exp_name, exp_price in test_cases:
        matched = OrderMatcher.match_product(q)
        if matched and exp_name.lower() in matched["name"].lower():
            print(f"PASS: '{q}' -> #{matched['id']} {matched['name']} ({matched['sale_price']:,.0f} so'm, SKU: {matched.get('sku')})")
        else:
            errors.append(f"Matching failed for '{q}'. Got: {matched['name'] if matched else None}, Expected: {exp_name}")

    # 2. RULE 1: Never ask phone/address without purchase intent
    print("\n--- 2. Rule 1: No phone/address without purchase intent ---")
    non_purchase = [
        "narxlar qanaqa",
        "vitrofka bormi",
        "razmerlari qanaqa",
        "rangi qanaqa"
    ]
    for np in non_purchase:
        parsed = OrderMatcher.extract_order_details(np)
        if parsed and parsed.get("has_purchase_intent"):
            errors.append(f"Rule 1 violation: Purchase intent falsely detected for '{np}'")
        else:
            print(f"PASS: No purchase intent for '{np}'")

    purchase = [
        "men Poplin koylak olaman, manzil Navoiy ko'chasi 15, tel 901234567",
        "bitta Polo svitir sotib olmoqchiman, manzil Toshkent uy 5, tel 991112233"
    ]
    for p in purchase:
        parsed = OrderMatcher.extract_order_details(p)
        if not parsed or not parsed.get("phone"):
            errors.append(f"Purchase order details missed for '{p}'")
        else:
            print(f"PASS: Order details extracted for '{p}': phone={parsed['phone']}, addr={parsed['address']}")

    # 3. RULE 3: Low stock label (<= 2)
    print("\n--- 3. Rule 3: Low Stock Label 'oxirgi N ta qoldi' ---")
    p9_cat = search_products("MS-1009")
    p9 = p9_cat.get("products", [{}])[0]
    if "oxirgi 2 ta qoldi" in p9.get("stock_status", ""):
        print(f"PASS: Product #9 (stock 2): '{p9['stock_status']}'")
    else:
        errors.append(f"Rule 3 violation for #9: {p9.get('stock_status')}")

    p25_cat = search_products("MS-1025")
    p25 = p25_cat.get("products", [{}])[0]
    if "oxirgi 1 ta qoldi" in p25.get("stock_status", ""):
        print(f"PASS: Product #25 (stock 1): '{p25['stock_status']}'")
    else:
        errors.append(f"Rule 3 violation for #25: {p25.get('stock_status')}")

    # 4. OUT OF STOCK (stock == 0)
    print("\n--- 4. Out of Stock Handling (stock == 0) ---")
    p10_cat = search_products("MS-1010")
    p10 = p10_cat.get("products", [{}])[0]
    if "yo'q" in p10.get("stock_status", "") or "tugagan" in p10.get("stock_status", ""):
        print(f"PASS: Product #10 (stock 0): '{p10['stock_status']}'")
    else:
        errors.append(f"Out of stock labeling failed for #10: {p10.get('stock_status')}")

    # 5. RULE 4: Code Price Filtering
    print("\n--- 5. Rule 4: Deterministic Code Price Filter ---")
    filter_prods = OrderMatcher.filter_products_by_price(min_price=0, max_price=100000)
    filter_res = OrderMatcher.format_price_filter_response(filter_prods, min_price=0, max_price=100000)
    if len(filter_prods) >= 15:
        print(f"PASS: Filter <= 100,000 returned {len(filter_prods)} products completely by code.")
    else:
        errors.append(f"Price filter returned unexpected count: {len(filter_prods)}")

    # 6. RULE 5: Code-calculated Total Sum
    print("\n--- 6. Rule 5: Code-calculated Total Sum ---")
    quote1 = OrderMatcher.calculate_quote("2 ta Poplin ayollar ko'ylak qancha bo'ladi")
    # 2 * 70,000 = 140,000
    if quote1 and "140,000" in quote1:
        print(f"PASS: 2 x Poplin ko'ylak = {quote1}")
    else:
        errors.append(f"Sum calculation failed for Poplin ko'ylak: {quote1}")

    quote2 = OrderMatcher.calculate_quote("3 ta Polo erkaklar svitir narxi qancha")
    # 3 * 75,000 = 225,000
    if quote2 and "225,000" in quote2:
        print(f"PASS: 3 x Polo svitir = {quote2}")
    else:
        errors.append(f"Sum calculation failed for Polo svitir: {quote2}")

    # 7. RULE 6: Neutral greeting & no gender guessing
    print("\n--- 7. Rule 6: Respectful Greeting without Gender Guessing ---")
    greet_msg = agent.process_message(customer_id=105, user_text="salom", customer_name="Mijoz")
    if "assalomu alaykum" in greet_msg.lower() and "akajon" not in greet_msg.lower() and "opajon" not in greet_msg.lower():
        print(f"PASS: Respectful neutral greeting verified: '{greet_msg[:50]}...'")
    else:
        errors.append(f"Rule 6 violation: Greeting improper: {greet_msg}")

    # 8. RULE 7: Missing sizes handled with 'bizda faqat X, Y, Z bor'
    print("\n--- 8. Rule 7: Missing Size Handling ---")
    miss_msg = OrderMatcher.check_size_inquiry("Poplin ayollar ko'ylakdan M razmer bormi")
    if miss_msg and "faqat 48 bor" in miss_msg:
        print(f"PASS: Missing size handled: {miss_msg}")
    else:
        errors.append(f"Rule 7 violation: {miss_msg}")

    # 9. STORE SETTINGS CONFIG & OWNER NOTIFICATION
    print("\n--- 9. Store Settings Config & Owner Notification ---")
    deliv_check = StoreSettingsManager.check_setting_inquiry("yetkazib berish qancha")
    if deliv_check and "egasidan so'rab" in deliv_check["reply"]:
        print(f"PASS: Empty setting inquiry handled: '{deliv_check['reply']}'")
    else:
        errors.append(f"Store settings check failed: {deliv_check}")

    # 10. TOTAL 41 PRODUCTS IN DATABASE
    print("\n--- 10. SQLite Database Integrity ---")
    all_prods = DatabaseManager.get_products(in_stock_only=False)
    in_stock = DatabaseManager.get_products(in_stock_only=True)
    if len(all_prods) == 41:
        print(f"PASS: Jami 41 ta tovar bazada to'liq mavjud! (Omborda bor: {len(in_stock)} ta, Tugagan: {len(all_prods)-len(in_stock)} ta)")
    else:
        errors.append(f"Expected 41 products in DB, found {len(all_prods)}")

    print("\n" + "=" * 70)
    if not errors:
        print("ALL 10 VERIFICATION SUITES FOR 41 REAL PRODUCTS PASSED 100% WITH ZERO ERRORS!")
        print("=" * 70)
        return True
    else:
        print(f"FAILURES DETECTED ({len(errors)}):")
        for e in errors:
            print(f" - {e}")
        print("=" * 70)
        return False

if __name__ == "__main__":
    success = run_deep_audit()
    sys.exit(0 if success else 1)
