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
    print("MARKAZSAVDO 49-PRODUCT REAL STORE INVENTORY AUDIT")
    print("=" * 70)
    init_db()
    agent = SalesAgent()
    errors = []

    # 1. TEST REAL STORE PRODUCT MATCHING
    print("\n--- 1. Real Products Matching (SKU, Brand, Category) ---")
    test_cases = [
        ("adidas futbolka bormi", "Adidas Printli futbolka Ko'k", 200000),
        ("nike kepka qancha", "Nike Yozgi kepka Bej", 229000),
        ("zara palto bej", "Zara Yengil palto Bej", 2062000),
        ("KK-1022", "Adidas Slim fit jinsi Moviy", 445000),
        ("uztex paypoq", "UzTex", 45000)
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
        "palto bormi",
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
        "men Adidas futbolka olaman, manzil Navoiy ko'chasi 15, tel 901234567",
        "bitta Nike kepka sotib olmoqchiman, manzil Toshkent uy 5, tel 991112233"
    ]
    for p in purchase:
        parsed = OrderMatcher.extract_order_details(p)
        if not parsed or not parsed.get("phone"):
            errors.append(f"Purchase order details missed for '{p}'")
        else:
            print(f"PASS: Order details extracted for '{p}': phone={parsed['phone']}, addr={parsed['address']}")

    # 3. RULE 3: Low stock label (<= 2)
    print("\n--- 3. Rule 3: Low Stock Label 'oxirgi N ta qoldi' ---")
    # KK-1059 LC Waikiki Briefs (id 9, stock 2) -> "oxirgi 2 ta qoldi"
    p9_cat = search_products("KK-1059")
    p9 = p9_cat.get("products", [{}])[0]
    if "oxirgi 2 ta qoldi" in p9.get("stock_status", ""):
        print(f"PASS: Product #9 (stock 2): '{p9['stock_status']}'")
    else:
        errors.append(f"Rule 3 violation for #9: {p9.get('stock_status')}")

    # KK-1008 Puma ofis ko'ylak (id 25, stock 1) -> "oxirgi 1 ta qoldi"
    p25_cat = search_products("KK-1008")
    p25 = p25_cat.get("products", [{}])[0]
    if "oxirgi 1 ta qoldi" in p25.get("stock_status", ""):
        print(f"PASS: Product #25 (stock 1): '{p25['stock_status']}'")
    else:
        errors.append(f"Rule 3 violation for #25: {p25.get('stock_status')}")

    # 4. OUT OF STOCK (stock == 0)
    print("\n--- 4. Out of Stock Handling (stock == 0) ---")
    # KK-1064 LC Waikiki Termo (id 10, stock 0)
    p10_cat = search_products("KK-1064")
    p10 = p10_cat.get("products", [{}])[0]
    if "yo'q" in p10.get("stock_status", ""):
        print(f"PASS: Product #10 (stock 0): '{p10['stock_status']}'")
    else:
        errors.append(f"Out of stock labeling failed for #10: {p10.get('stock_status')}")

    # 5. RULE 4: Code Price Filtering
    print("\n--- 5. Rule 4: Deterministic Code Price Filter ---")
    filter_prods = OrderMatcher.filter_products_by_price(min_price=0, max_price=100000)
    filter_res = OrderMatcher.format_price_filter_response(filter_prods, min_price=0, max_price=100000)
    if len(filter_prods) >= 4 and ("Paypoq" in filter_res or "ichki" in filter_res.lower() or "Briefs" in filter_res) and "Palto" not in filter_res:
        print(f"PASS: Filter <= 100,000 returned {len(filter_prods)} products completely by code.")
    else:
        errors.append(f"Price filter returned unexpected items: {filter_res}")

    # 6. RULE 5: Code-calculated Total Sum
    print("\n--- 6. Rule 5: Code-calculated Total Sum ---")
    quote1 = OrderMatcher.calculate_quote("2 ta Adidas futbolka qancha bo'ladi")
    # 2 * 200,000 = 400,000
    if quote1 and "400,000 so'm" in quote1:
        print(f"PASS: 2 x Adidas futbolka = {quote1}")
    else:
        errors.append(f"Sum calculation failed for Adidas futbolka: {quote1}")

    quote2 = OrderMatcher.calculate_quote("3 ta Nike polo narxi qancha")
    # 3 * 174,000 = 522,000
    if quote2 and "522,000 so'm" in quote2:
        print(f"PASS: 3 x Nike polo = {quote2}")
    else:
        errors.append(f"Sum calculation failed for Nike polo: {quote2}")

    # 7. RULE 6: Neutral greeting & no gender guessing
    print("\n--- 7. Rule 6: Respectful Greeting without Gender Guessing ---")
    greet_msg = agent.process_message(customer_id=105, user_text="salom", customer_name="Mijoz")
    if "assalomu alaykum" in greet_msg.lower() and "akajon" not in greet_msg.lower() and "opajon" not in greet_msg.lower():
        print(f"PASS: Respectful neutral greeting verified: '{greet_msg[:50]}...'")
    else:
        errors.append(f"Rule 6 violation: Greeting improper: {greet_msg}")

    # 8. RULE 7: Missing sizes handled with 'bizda faqat X, Y, Z bor'
    print("\n--- 8. Rule 7: Missing Size Handling ---")
    # Adidas Printli futbolka is size XXL
    miss_msg = OrderMatcher.check_size_inquiry("Adidas Printli futbolkadan M razmer bormi")
    if miss_msg and "faqat XXL bor" in miss_msg:
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

    # 10. TOTAL 49 PRODUCTS IN DATABASE
    print("\n--- 10. SQLite Database Integrity ---")
    all_prods = DatabaseManager.get_products(in_stock_only=False)
    in_stock = DatabaseManager.get_products(in_stock_only=True)
    if len(all_prods) == 49:
        print(f"PASS: Jami 49 ta tovar bazada to'liq mavjud! (Omborda bor: {len(in_stock)} ta, Tugagan: {len(all_prods)-len(in_stock)} ta)")
    else:
        errors.append(f"Expected 49 products in DB, found {len(all_prods)}")

    print("\n" + "=" * 70)
    if not errors:
        print("ALL 10 VERIFICATION SUITES FOR 49 REAL PRODUCTS PASSED 100% WITH ZERO ERRORS!")
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
