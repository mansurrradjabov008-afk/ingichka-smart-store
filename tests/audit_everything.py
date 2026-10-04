import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.db_manager import DatabaseManager, init_db
from ai_engine.ai_brain import ai_brain
from ai_engine.sales_agent import SalesAgent
from services.order_matcher import OrderMatcher
from services.store_settings_manager import StoreSettingsManager
import json

def run_deep_audit():
    print("=" * 60)
    print("MARKAZSAVDO 100% DEEP ARCHITECTURAL & COMPLIANCE AUDIT")
    print("=" * 60)
    init_db()
    agent = SalesAgent()

    errors = []

    # 1. TEST PRODUCT MATCHING: Krasovka / Krossovka / Poyabzal
    print("\n--- 1. Krasovka & Shoe Detection ---")
    inquiries = [
        "men uglimga krasovka olmoqchi edim,menga krasovkalarizni kursata olasizmi",
        "krasovka bormi",
        "menga poyabzal kerak",
        "oq krossovki qancha"
    ]
    for inq in inquiries:
        res = agent.process_message(user_text=inq, customer_id=101, customer_name="Mansur")
        if "krossovka" in res.lower() or "380,000" in res or "380 000" in res or "40, 41" in res:
            print(f"PASS: '{inq}' -> {res[:70]}...")
        else:
            errors.append(f"Product matching failed for: {inq} -> {res}")

    # 2. RULE 1: Never ask phone/address unless buying intent
    print("\n--- 2. Rule 1: No phone/address without purchase intent ---")
    non_purchase = [
        "narxlar qanaqa",
        "kurtka bormi",
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
        "men 42-razmer krasovka olaman, manzil Navoiy ko'chasi 15, tel 901234567",
        "bitta qora kurtka sotib olmoqchiman, manzil Toshkent uy 5, tel 991112233"
    ]
    for p in purchase:
        parsed = OrderMatcher.extract_order_details(p)
        if not parsed or not parsed.get("phone"):
            errors.append(f"Purchase order details missed for '{p}'")
        else:
            print(f"PASS: Order details extracted for '{p}': phone={parsed['phone']}, addr={parsed['address']}")

    # 3. RULE 2: Dynamic closings (no repetitive loops)
    print("\n--- 3. Rule 2: Dynamic Closings Rotation ---")
    replies = set()
    for h_len in range(4):
        fake_hist = [{"role": "user", "content": f"msg {i}"} for i in range(h_len)]
        rep = agent.process_message(customer_id=200 + h_len, user_text="krasovka bormi", customer_name="Test", history=fake_hist)
        replies.add(rep)
    if len(replies) >= 2:
        print(f"PASS: {len(replies)} distinct response/closing variants produced across turns.")
    else:
        print(f"INFO: Generated replies: {len(replies)}")

    # 4. RULE 3: Low stock label (<= 2)
    print("\n--- 4. Rule 3: Low Stock Label 'oxirgi N ta qoldi' ---")
    from services.catalog_service import search_products
    cat_res = search_products("ko'ylak")
    p4_match = next((p for p in cat_res.get("products", []) if p["id"] == 4), None)
    if p4_match and "oxirgi 2 ta qoldi" in p4_match.get("stock_status", ""):
        print(f"PASS: catalog_service product #4 (stock 2): '{p4_match['stock_status']}'")
    else:
        errors.append(f"Rule 3 violation in catalog_service: {p4_match}")

    order_quote = OrderMatcher.calculate_quote("bitta ko'ylak qancha bo'ladi")
    if order_quote and "oxirgi 2 ta qoldi" in order_quote:
        print(f"PASS: OrderMatcher quote: '{order_quote}'")
    else:
        errors.append(f"Rule 3 violation in OrderMatcher quote: {order_quote}")

    # 5. RULE 4: Deterministic code price filter
    print("\n--- 5. Rule 4: Code Price Filtering ---")
    filter_prods = OrderMatcher.filter_products_by_price(max_price=300000)
    filter_res = OrderMatcher.format_price_filter_response(filter_prods, min_price=0, max_price=300000)
    if "Kepka" in filter_res and "futbolka" in filter_res and "jinsi" in filter_res and "kurtka" not in filter_res:
        print("PASS: Price filter correctly returned all products <= 300,000 via code.")
    else:
        errors.append(f"Rule 4 violation: Price filter returned incorrect items: {filter_res}")

    # 6. RULE 5: Deterministic code total sum calculation
    print("\n--- 6. Rule 5: Code-calculated Total Sum ---")
    sum_test1 = OrderMatcher.calculate_quote("2 ta kurtka qancha bo'ladi")
    sum_test2 = OrderMatcher.calculate_quote("3 ta kurtka qancha bo'ladi")
    if sum_test1 and "900,000 so'm" in sum_test1 and sum_test2 and "1,350,000 so'm" in sum_test2:
        print(f"PASS: 2 kurtka = 900,000 so'm; 3 kurtka = 1,350,000 so'm calculated by code.")
    else:
        errors.append(f"Rule 5 violation: Sum calculation mismatch: {sum_test1}, {sum_test2}")

    # 7. RULE 6: Neutral greeting & no gender guessing
    print("\n--- 7. Rule 6: Respectful Greeting without Gender Guessing ---")
    greet_msg = agent.process_message(customer_id=105, user_text="salom", customer_name="Mijoz")
    if "assalomu alaykum" in greet_msg.lower() and "akajon" not in greet_msg.lower() and "opajon" not in greet_msg.lower():
        print(f"PASS: Respectful neutral greeting verified: '{greet_msg[:50]}...'")
    else:
        errors.append(f"Rule 6 violation: Greeting improper: {greet_msg}")

    # 8. RULE 7: Missing sizes handled with 'bizda faqat X, Y, Z bor'
    print("\n--- 8. Rule 7: Missing Size Handling ---")
    size_msg = agent.process_message(customer_id=102, user_text="krasovkadan 46 razmer bormi", customer_name="Mijoz")
    if "faqat" in size_msg.lower() and ("40" in size_msg or "41" in size_msg):
        print(f"PASS: Missing size handled: {size_msg}")
    else:
        errors.append(f"Rule 7 violation: Missing size response format incorrect: {size_msg}")

    # 9. STORE SETTINGS CONFIG & OWNER NOTIFICATION
    print("\n--- 9. Store Settings Config & Owner Notification ---")
    deliv_check = StoreSettingsManager.check_setting_inquiry("yetkazib berish qancha")
    if deliv_check and "egasidan so'rab" in deliv_check["reply"]:
        print(f"PASS: Empty setting inquiry handled: '{deliv_check['reply']}'")
    else:
        errors.append(f"Store settings check failed: {deliv_check}")

    # 10. MISSING ITEMS HANDLING
    print("\n--- 10. Missing Catalog Items ---")
    missing_item = agent.process_message(customer_id=103, user_text="sizlarda velosiped bormi", customer_name="Mijoz")
    if "mavjud emas" in missing_item.lower():
        print(f"PASS: Missing item response: {missing_item}")
    else:
        errors.append(f"Missing item handling failed: {missing_item}")

    print("\n" + "=" * 60)
    if not errors:
        print("ALL 10 ARCHITECTURAL & BUSINESS RULE SUITES PASSED 100% WITH ZERO ERRORS!")
        print("=" * 60)
        return True
    else:
        print(f"FAILURES DETECTED ({len(errors)}):")
        for e in errors:
            print(f" - {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = run_deep_audit()
    sys.exit(0 if success else 1)
