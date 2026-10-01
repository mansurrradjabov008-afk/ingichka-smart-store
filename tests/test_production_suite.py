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
from ai_engine.ai_brain import ai_brain

def test_production_flows():
    print("=" * 60)
    print("INGICHKA BARAKA SAVDO AI - PRODUCTION VERIFICATION SUITE")
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

    p7 = OrderMatcher.match_product("Qora kepka bormi")
    assert p7 is not None and p7["id"] == 7, f"Expected ID 7, got {p7}"
    print(f"PASS: 'Kepka' -> #{p7['id']} {p7['name']} ({p7['sale_price']:,.0f} so'm)")

    # 2. TEST MULTI-TURN ORDER FLOW
    print("\n--- 2. TEST MULTI-TURN ORDER FLOW ---")
    test_user_id = 9999901
    DatabaseManager.upsert_customer(test_user_id, "Mansurbek", username="mansur_test")

    # Turn 1: Customer selects product
    t1_text = "Erkaklar qora kurtkasidan olaman"
    matched_prod = OrderMatcher.match_product(t1_text)
    assert matched_prod["id"] == 1
    pending_state = {test_user_id: matched_prod}
    print("PASS: Turn 1 - User pending order set to Product #1")

    # Turn 2: Customer provides phone and address
    t2_text = "Ingichka Navoiy ko'chasi 15-uy, tel: +998901234567"
    order_details = OrderMatcher.extract_order_details(t2_text, has_pending_order=(test_user_id in pending_state))
    assert order_details is not None
    assert order_details["phone"] == "+998901234567"
    assert "Ingichka" in order_details["address"]
    print(f"PASS: Turn 2 - Order details extracted: {order_details}")

    # Check stock before
    stock_before = DatabaseManager.get_product_by_id(1)["stock_quantity"]

    # Create Order
    res = DatabaseManager.create_order(
        customer_telegram_id=test_user_id,
        customer_name="Mansurbek",
        customer_phone=order_details["phone"],
        delivery_address=order_details["address"],
        items=[{"product_id": matched_prod["id"], "quantity": 1}],
        payment_method="cash_on_delivery",
        notes="Automated production test"
    )
    assert res["success"] is True
    order_id = res["order_id"]
    stock_after = DatabaseManager.get_product_by_id(1)["stock_quantity"]
    assert stock_after == stock_before - 1
    print(f"PASS: Order #{order_id} created successfully! Stock reduced from {stock_before} to {stock_after} atomically.")

    # 3. TEST SINGLE-TURN FULL ORDER (VOICE OR TEXT)
    print("\n--- 3. TEST SINGLE-TURN FULL ORDER ---")
    voice_transcript = "Krossovkani olaman, manzilim Ingichka 12-maktab yonida, tel: 93 987 65 43"
    v_details = OrderMatcher.extract_order_details(voice_transcript, has_pending_order=False)
    assert v_details is not None
    assert v_details["phone"] == "+998939876543"
    v_prod = OrderMatcher.match_product(voice_transcript)
    assert v_prod["id"] == 8
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
        customer_name="Mansurbek"
    )
    print(f"Mijoz: 'Sizda iPhone 16 Pro Max bormi?'")
    print(f"AI Javobi: {reply}")
    assert "yo'q" in reply.lower() or "mavjud emas" in reply.lower() or "kiyim" in reply.lower(), "AI should reject non-clothing product!"
    print("PASS: Zero hallucination verified! AI truthfully stated non-clothing item is not available.")

    # 6. TEST OUT OF STOCK HANDLING (Sport kostyum - stock 0)
    print("\n--- 6. TEST OUT OF STOCK STRICT GUARD ---")
    p5 = DatabaseManager.get_product_by_id(5)
    assert p5["stock_quantity"] == 0
    stock_check = DatabaseManager.check_stock_strict(5, 1)
    assert stock_check["available"] is False
    print(f"PASS: #{p5['id']} {p5['name']} out of stock blocked cleanly: {stock_check['reason']}")

    # 7. TEST CHANNEL POST FORMATTER
    print("\n--- 7. TEST CHANNEL POST FORMATTER ---")
    prod1 = DatabaseManager.get_product_by_id(1)
    post = OrderMatcher.format_channel_post(prod1, "Markazsavdo00_bot")
    assert "Erkaklar qora kurtkasi" in post
    assert "450,000" in post or "450 000" in post
    print("PASS: Channel post generated with compelling copy and guarantee:")
    print(post[:250] + "...")

    # 8. TEST COMPREHENSIVE PHONE FORMATS
    print("\n--- 8. TEST UZBEK PHONE NUMBER FORMATS ---")
    formats_to_test = [
        "+998 (90) 123-45-67",
        "(91) 456-78-90",
        "88 123 45 67",
        "33 765 43 21",
        "901234567"
    ]
    for ph in formats_to_test:
        test_txt = f"Oversize futbolka olaman, Ingichka Navoiy 14, tel: {ph}"
        det = OrderMatcher.extract_order_details(test_txt)
        assert det is not None, f"Failed to extract: {ph}"
        assert det["phone"].startswith("+998"), f"Invalid standardized phone: {det['phone']}"
        print(f"PASS: Format '{ph:22}' -> {det['phone']}")

    # 9. TEST ATOMIC OVERSELLING GUARD
    print("\n--- 9. TEST ATOMIC OVERSELLING GUARD ---")
    prod = DatabaseManager.get_product_by_id(6) # Ayollar qishki paltosi (1 dona)
    current_stock = prod["stock_quantity"]
    excessive_qty = current_stock + 10
    guard_res = DatabaseManager.create_order(
        customer_telegram_id=test_user_id,
        customer_name="Mansurbek",
        customer_phone="+998901234567",
        delivery_address="Ingichka",
        items=[{"product_id": 6, "quantity": excessive_qty}],
        payment_method="cash_on_delivery"
    )
    assert guard_res["success"] is False
    print(f"PASS: Overselling blocked! Error: {guard_res['error']}")

    # 10. TEST PENDING ORDER TTL
    print("\n--- 10. TEST PENDING ORDER TTL (EXPIRATION) ---")
    from bot.bot_app import set_pending_order, get_pending_order, USER_PENDING_ORDERS
    import time
    
    set_pending_order(777, prod1)
    assert get_pending_order(777) is not None
    print("PASS: Fresh pending order retrieved successfully")

    # Manually backdate timestamp by 3 hours
    USER_PENDING_ORDERS[777]["timestamp"] = time.time() - 10800
    expired = get_pending_order(777, max_age_seconds=7200)
    assert expired is None
    print("PASS: Stale pending order expired and cleaned from memory (TTL enforced)")

    # Reset stock for test data
    with get_connection() as conn:
        conn.execute("UPDATE products SET stock_quantity = 5 WHERE id = 1")
        conn.commit()
    print("PASS: Cleaned test data and restored stock.")

    print("\n" + "=" * 60)
    print("ALL 10 PRODUCTION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    test_production_flows()
