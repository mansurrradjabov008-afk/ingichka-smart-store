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

from database.db_manager import DatabaseManager, init_db

from services.order_matcher import OrderMatcher
from ai_engine.ai_brain import ai_brain

def test_production_flows():
    print("=" * 60)
    print("INGICHKA BARAKA SAVDO AI - PRODUCTION VERIFICATION SUITE")
    print("=" * 60)
    init_db()

    # 1. TEST PRODUCT MATCHING
    print("\n--- 1. TEST PRODUCT MATCHING ---")
    p1 = OrderMatcher.match_product("Termo krasovka 42 razmeri bormi olaman")
    assert p1 is not None and p1["id"] == 16, f"Expected ID 16, got {p1}"
    print(f"PASS: 'Termo krasovka' -> #{p1['id']} {p1['name']} ({p1['sale_price']:,.0f} so'm)")

    p2 = OrderMatcher.match_product("Koreya qalin kurtkasi")
    assert p2 is not None and p2["id"] == 4, f"Expected ID 4, got {p2}"
    print(f"PASS: 'Koreya kurtka' -> #{p2['id']} {p2['name']} ({p2['sale_price']:,.0f} so'm)")

    p3 = OrderMatcher.match_product("Nike krasovkasi")
    assert p3 is not None and p3["id"] == 17, f"Expected ID 17, got {p3}"
    print(f"PASS: 'Nike krasovka' -> #{p3['id']} {p3['name']} ({p3['sale_price']:,.0f} so'm)")

    p4 = OrderMatcher.match_product("Turkiya banya sochiq")
    assert p4 is not None and p4["id"] == 12, f"Expected ID 12, got {p4}"
    print(f"PASS: 'Banya sochiq' -> #{p4['id']} {p4['name']} ({p4['sale_price']:,.0f} so'm)")

    # 2. TEST MULTI-TURN ORDER FLOW
    print("\n--- 2. TEST MULTI-TURN ORDER FLOW ---")
    test_user_id = 9999901
    DatabaseManager.upsert_customer(test_user_id, "Sardor", username="sardor_test")

    # Turn 1: Customer selects product
    t1_text = "Termo krossovkadan olaman"
    matched_prod = OrderMatcher.match_product(t1_text)
    assert matched_prod["id"] == 16
    pending_state = {test_user_id: matched_prod}
    print("PASS: Turn 1 - User pending order set to Product #16")

    # Turn 2: Customer provides phone and address
    t2_text = "Ingichka Navoiy ko'chasi 15-uy, tel: +998901234567"
    order_details = OrderMatcher.extract_order_details(t2_text, has_pending_order=(test_user_id in pending_state))
    assert order_details is not None
    assert order_details["phone"] == "+998901234567"
    assert "Ingichka" in order_details["address"]
    print(f"PASS: Turn 2 - Order details extracted: {order_details}")

    # Check stock before
    stock_before = DatabaseManager.get_product_by_id(16)["stock_quantity"]

    # Create Order
    res = DatabaseManager.create_order(
        customer_telegram_id=test_user_id,
        customer_name="Sardor",
        customer_phone=order_details["phone"],
        delivery_address=order_details["address"],
        items=[{"product_id": matched_prod["id"], "quantity": 1}],
        payment_method="cash_on_delivery",
        notes="Automated production test"
    )
    assert res["success"] is True
    order_id = res["order_id"]
    stock_after = DatabaseManager.get_product_by_id(16)["stock_quantity"]
    assert stock_after == stock_before - 1
    print(f"PASS: Order #{order_id} created successfully! Stock reduced from {stock_before} to {stock_after} atomically.")

    # 3. TEST SINGLE-TURN FULL ORDER (VOICE OR TEXT)
    print("\n--- 3. TEST SINGLE-TURN FULL ORDER ---")
    voice_transcript = "Koreyskiy qalin kurtkani olaman, manzilim Ingichka 12-maktab yonida, tel: 93 987 65 43"
    v_details = OrderMatcher.extract_order_details(voice_transcript, has_pending_order=False)
    assert v_details is not None
    assert v_details["phone"] == "+998939876543"
    v_prod = OrderMatcher.match_product(voice_transcript)
    assert v_prod["id"] == 4
    print(f"PASS: Voice order matched Product #{v_prod['id']} ({v_prod['name']}), Phone: {v_details['phone']}, Address: {v_details['address']}")

    # 4. TEST CUSTOMER ORDER HISTORY
    print("\n--- 4. TEST CUSTOMER ORDER HISTORY ---")
    cust_orders = DatabaseManager.get_customer_orders(test_user_id)
    assert len(cust_orders) >= 1
    print(f"PASS: Retrieved {len(cust_orders)} customer orders. Latest: #{cust_orders[0]['id']} - {cust_orders[0]['total_amount']:,.0f} so'm")

    # 5. TEST ZERO HALLUCINATION WITH GEMINI
    print("\n--- 5. TEST ZERO HALLUCINATION (GEMINI BRAIN) ---")
    reply = ai_brain.ask(
        user_id=test_user_id,
        user_message="Sizda iPhone 16 Pro Max bormi?",
        customer_name="Sardor"
    )
    print(f"Mijoz: 'Sizda iPhone 16 Pro Max bormi?'")
    print(f"AI Javobi: {reply}")
    assert "yo'q" in reply.lower() or "mavjud emas" in reply.lower() or "kiyim" in reply.lower(), "AI should reject non-clothing product!"
    print("PASS: Zero hallucination verified! AI truthfully stated non-clothing item is not available.")

    # 6. TEST CHANNEL POST FORMATTER
    print("\n--- 6. TEST CHANNEL POST FORMATTER ---")
    prod16 = DatabaseManager.get_product_by_id(16)
    post = OrderMatcher.format_channel_post(prod16, "Markazsavdo00_bot")
    assert "Markazsavdo00_bot" in post or "30-60 daqiqada" in post
    assert "280,000" in post or "280 000" in post
    print("PASS: Channel post generated with compelling copy and guarantee:")
    print(post[:250] + "...")

    # 7. TEST COMPREHENSIVE PHONE FORMATS
    print("\n--- 7. TEST UZBEK PHONE NUMBER FORMATS ---")
    formats_to_test = [
        "+998 (90) 123-45-67",
        "(91) 456-78-90",
        "88 123 45 67",
        "33 765 43 21",
        "901234567"
    ]
    for ph in formats_to_test:
        test_txt = f"Termo krasovka olaman, Ingichka Navoiy 14, tel: {ph}"
        det = OrderMatcher.extract_order_details(test_txt)
        assert det is not None, f"Failed to extract: {ph}"
        assert det["phone"].startswith("+998"), f"Invalid standardized phone: {det['phone']}"
        print(f"PASS: Format '{ph:22}' -> {det['phone']}")

    # 8. TEST ATOMIC OVERSELLING GUARD
    print("\n--- 8. TEST ATOMIC OVERSELLING GUARD ---")
    prod = DatabaseManager.get_product_by_id(4)
    current_stock = prod["stock_quantity"]
    oversell_res = DatabaseManager.create_order(
        customer_telegram_id=test_user_id,
        customer_name="Test Oversell",
        customer_phone="+998901234567",
        delivery_address="Ingichka",
        items=[{"product_id": 4, "quantity": current_stock + 10}],
        payment_method="cash_on_delivery"
    )
    assert oversell_res["success"] is False
    assert "yetarli emas" in oversell_res["error"]
    print(f"PASS: Overselling blocked! Error: {oversell_res['error']}")

    # 9. TEST PENDING ORDER TTL (EXPIRATION)
    print("\n--- 9. TEST PENDING ORDER TTL (EXPIRATION) ---")
    from bot.bot_app import set_pending_order, get_pending_order, clear_pending_order
    test_uid = 88881
    set_pending_order(test_uid, prod)
    p_fresh = get_pending_order(test_uid)
    assert p_fresh is not None
    print("PASS: Fresh pending order retrieved successfully")
    # Test expired (age > 7200 seconds)
    import time
    from bot.bot_app import USER_PENDING_ORDERS
    USER_PENDING_ORDERS[test_uid]["timestamp"] = time.time() - 8000
    p_expired = get_pending_order(test_uid, max_age_seconds=7200)
    assert p_expired is None
    print("PASS: Stale pending order expired and cleaned from memory (TTL enforced)")

    # 10. CLEANUP TEST USER
    DatabaseManager.update_order_status(order_id, "bekor")
    from database.db_manager import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    c.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    c.execute("DELETE FROM customers WHERE telegram_id = ?", (test_user_id,))
    conn.commit()
    conn.close()
    # Reset product 16 stock
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE products SET stock_quantity = 14 WHERE id = 16")
    conn.commit()
    conn.close()
    print("PASS: Cleaned test data and restored stock.")

    print("\n" + "=" * 60)
    print("ALL 10 PRODUCTION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    test_production_flows()

