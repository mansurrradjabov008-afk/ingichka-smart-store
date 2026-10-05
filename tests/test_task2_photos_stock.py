"""
tests/test_task2_photos_stock.py
Comprehensive verification suite for Task 2: Photos and Stock.
Strictly tests:
1. Sold-out product (stock = 0: says sold out, offers in-stock alternative, asks "Kelganda xabar beraymi?")
2. Quantity above stock (states exact available number from data)
3. Broken image URL (failsafe fallback to text only with name, price, sizes)
4. Duplicate waitlist signup (strict deduplication in data/waitlist.json)
5. Non-admin using /restock (must be refused, while admin successfully restocks and notifies waitlist)
"""

import sys
import os
import json
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.db_manager import DatabaseManager, init_db
from services.waitlist_service import WaitlistService, WAITLIST_FILE
from services.stock_advisor import StockAdvisor, PENDING_WAITLIST_OFFERS
from services.media_service import send_product_presentation, format_product_caption
from services.order_matcher import OrderMatcher
from config import ADMIN_CHAT_ID, ADMIN_TELEGRAM_IDS
from bot.bot_app import is_admin_user, handle_restock_command

class TestTask2PhotosAndStock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        from data.build_real_inventory import build_inventory
        build_inventory()

    def setUp(self):
        # Backup waitlist.json if exists
        self.waitlist_backup = None
        if WAITLIST_FILE.exists():
            with open(WAITLIST_FILE, "r", encoding="utf-8") as f:
                self.waitlist_backup = f.read()

        # Start each test with an empty waitlist
        with open(WAITLIST_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        PENDING_WAITLIST_OFFERS.clear()

    def tearDown(self):
        # Restore waitlist.json
        if self.waitlist_backup is not None:
            with open(WAITLIST_FILE, "w", encoding="utf-8") as f:
                f.write(self.waitlist_backup)
        elif WAITLIST_FILE.exists():
            WAITLIST_FILE.unlink(missing_ok=True)
        PENDING_WAITLIST_OFFERS.clear()

    # -------------------------------------------------------------
    # TEST 1: Sold-Out Product
    # -------------------------------------------------------------
    def test_01_sold_out_product_rule(self):
        """
        Stock rules in CODE:
        if stock = 0 the bot says it is sold out, offers the closest in-stock alternative,
        and asks 'Kelganda xabar beraymi?'.
        """
        print("\n--- TEST 1: Sold-Out Product ---")
        # Ensure product #10 has stock = 0
        p10 = DatabaseManager.get_product_by_id(10)
        self.assertIsNotNone(p10, "Product #10 should exist in database")

        # Force stock to 0 for strict testing if needed
        conn = DatabaseManager.get_connection() if hasattr(DatabaseManager, 'get_connection') else None
        
        # Test evaluation
        eval_res = StockAdvisor.evaluate_stock_rules("LC Waikiki Termo ichki Ko'k bormi?", p10)
        self.assertIsNotNone(eval_res, "Stock evaluation should not be None for stock=0 product")
        self.assertEqual(eval_res["type"], "sold_out")
        
        reply = eval_res["reply"]
        print(f"Sold-out reply:\n{reply}")
        
        # Verify message requirements:
        # 1. Says sold out
        self.assertTrue("sotib bo'lingan" in reply or "tugagan" in reply, "Must state product is sold out")
        # 2. Offers in-stock alternative
        self.assertIsNotNone(eval_res.get("alternative"), "Must offer an in-stock alternative")
        self.assertGreater(eval_res["alternative"].get("stock_quantity", 0), 0, "Alternative must be in stock")
        self.assertIn(eval_res["alternative"]["name"], reply, "Reply must mention alternative product name")
        # 3. Asks 'Kelganda xabar beraymi?'
        self.assertIn("Kelganda xabar beraymi?", reply, "Must ask 'Kelganda xabar beraymi?'")
        print("✅ TEST 1 PASSED: Sold-out rule triggers properly with alternative and waitlist prompt.")

    # -------------------------------------------------------------
    # TEST 2: Quantity Above Stock
    # -------------------------------------------------------------
    def test_02_quantity_above_stock_rule(self):
        """
        If the customer wants more units than stock, say the exact available number from data.
        """
        print("\n--- TEST 2: Quantity Above Stock ---")
        # Find a product with stock > 0
        prods = DatabaseManager.get_products(in_stock_only=True)
        self.assertTrue(len(prods) > 0, "Should have in-stock products")
        target = prods[0]
        cur_stock = target["stock_quantity"]
        requested_qty = cur_stock + 10

        query_text = f"Menga {requested_qty} ta {target['name']} kerak"
        eval_res = StockAdvisor.evaluate_stock_rules(query_text, target)

        self.assertIsNotNone(eval_res, "Stock evaluation should trigger for quantity > stock")
        self.assertEqual(eval_res["type"], "quantity_above_stock")
        self.assertEqual(eval_res["available_stock"], cur_stock)
        self.assertEqual(eval_res["requested_qty"], requested_qty)

        reply = eval_res["reply"]
        print(f"Quantity-above-stock reply:\n{reply}")

        # Verify exact number is stated
        self.assertIn(f"{cur_stock} dona", reply, "Must state exact available number from data")
        print(f"✅ TEST 2 PASSED: Correctly stated available stock ({cur_stock} dona) when {requested_qty} requested.")

    # -------------------------------------------------------------
    # TEST 3: Broken Image URL
    # -------------------------------------------------------------
    def test_03_broken_image_url_fallback(self):
        """
        If image_url is broken or missing, send the text only. Never fail.
        """
        print("\n--- TEST 3: Broken Image URL Fallback ---")
        async def _run_async_test():
            mock_bot = MagicMock()
            # Simulate photo sending throwing TelegramBadRequest (broken URL / network error)
            mock_bot.send_photo = AsyncMock(side_effect=Exception("Failed to get HTTP URL content: 404 Not Found"))
            mock_bot.send_message = AsyncMock(return_value=True)

            sent_texts = []
            async def mock_safe_send(chat_id, text, reply_markup=None):
                sent_texts.append(text)
                return True

            bad_product = {
                "id": 999,
                "name": "Sinov Ko'ylagi",
                "price": 180000,
                "size": "M, L, XL",
                "stock": 5,
                "image_url": "http://invalid-domain-broken-url-xyz.com/photo.jpg"
            }

            # Must not raise an exception, must return True
            success = await send_product_presentation(
                bot=mock_bot,
                chat_id=112233,
                products=[bad_product],
                safe_send_fn=mock_safe_send
            )

            self.assertTrue(success, "Presentation must return True even when image is broken")
            self.assertEqual(len(sent_texts), 1, "Must have called text fallback once")
            
            caption = sent_texts[0]
            print(f"Fallback caption sent:\n{caption}")
            # Verify caption contents
            self.assertIn("Sinov Ko'ylagi", caption, "Caption must include product name")
            self.assertIn("180,000", caption, "Caption must include formatted price")
            self.assertIn("M, L, XL", caption, "Caption must include available sizes")

        asyncio.run(_run_async_test())
        print("✅ TEST 3 PASSED: Broken image URL safely fell back to text without failing.")

    # -------------------------------------------------------------
    # TEST 4: Duplicate Waitlist Signup
    # -------------------------------------------------------------
    def test_04_duplicate_waitlist_signup(self):
        """
        Save {chat_id, product_id, created_at} to data/waitlist.json (no duplicates).
        """
        print("\n--- TEST 4: Duplicate Waitlist Signup ---")
        chat_id = 998877
        prod_id = 10

        # First signup
        first_add = WaitlistService.add_to_waitlist(chat_id=chat_id, product_id=prod_id)
        self.assertTrue(first_add, "First waitlist signup must succeed")

        # Verify in file
        with open(WAITLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1, "File must have exactly 1 record")
        self.assertEqual(data[0]["chat_id"], chat_id)
        self.assertEqual(data[0]["product_id"], prod_id)
        self.assertTrue("created_at" in data[0], "Must record created_at timestamp")

        # Second duplicate signup
        second_add = WaitlistService.add_to_waitlist(chat_id=chat_id, product_id=prod_id)
        self.assertFalse(second_add, "Duplicate signup must be rejected (return False)")

        # Verify file still has only 1 record
        with open(WAITLIST_FILE, "r", encoding="utf-8") as f:
            data_after = json.load(f)
        self.assertEqual(len(data_after), 1, "File must still have only 1 record (no duplicates)")

        # Test conversational waitlist confirmation flow
        PENDING_WAITLIST_OFFERS[chat_id] = prod_id
        confirmation_reply = StockAdvisor.handle_waitlist_confirmation(chat_id, "Ha, kelganda xabar bering")
        self.assertIn("allaqachon", confirmation_reply.lower(), "Should inform user they are already on waitlist")
        print(f"Duplicate waitlist response: {confirmation_reply}")
        print("✅ TEST 4 PASSED: Duplicate waitlist signups strictly prevented in data/waitlist.json.")

    # -------------------------------------------------------------
    # TEST 5: Non-Admin Using /restock (Must Be Refused)
    # -------------------------------------------------------------
    def test_05_non_admin_restock_refusal(self):
        """
        Admin command /restock <product_id> <qty> (admin only, check ADMIN_CHAT_ID).
        Non-admin using /restock must be refused.
        Admin successfully updates stock and messages waitlist once, then clears them.
        """
        print("\n--- TEST 5: Non-Admin /restock Refusal & Admin Restock ---")
        async def _run_async_test():
            # 1. Non-admin refusal
            non_admin_id = 111222333
            self.assertFalse(
                is_admin_user(MagicMock(id=non_admin_id, username="random_user"), chat_id=non_admin_id),
                "Random user must not be recognized as admin"
            )

            p_before = DatabaseManager.get_product_by_id(10)
            stock_before = p_before["stock_quantity"]

            # Mock message from non-admin
            non_admin_msg = MagicMock()
            non_admin_msg.from_user = MagicMock(id=non_admin_id, username="random_user")
            non_admin_msg.chat = MagicMock(id=non_admin_id)
            non_admin_msg.text = "/restock 10 5"

            replies = []
            with patch("bot.bot_app.safe_send", new=AsyncMock(side_effect=lambda cid, txt, **kw: replies.append((cid, txt)))):
                await handle_restock_command(non_admin_msg)

            self.assertTrue(len(replies) > 0, "Must send a response to non-admin")
            self.assertIn("faqat do'kon ma'muri", replies[0][1], "Must refuse non-admin")
            print(f"Non-admin refusal message: {replies[0][1]}")

            # Verify stock was NOT changed
            p_after = DatabaseManager.get_product_by_id(10)
            self.assertEqual(p_after["stock_quantity"], stock_before, "Stock must remain unchanged after non-admin attempt")

            # 2. Add customer to waitlist for product 10
            waitlist_customer_id = 445566
            WaitlistService.add_to_waitlist(chat_id=waitlist_customer_id, product_id=10)
            self.assertTrue(WaitlistService.is_user_waiting(waitlist_customer_id, 10))

            # 3. Authorized Admin execution
            admin_id = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID and ADMIN_CHAT_ID.lstrip("-").isdigit() else ADMIN_TELEGRAM_IDS[0]
            admin_msg = MagicMock()
            admin_msg.from_user = MagicMock(id=admin_id, username="admin_user")
            admin_msg.chat = MagicMock(id=admin_id)
            admin_msg.text = "/restock 10 5"

            admin_replies = []
            with patch("bot.bot_app.safe_send", new=AsyncMock(side_effect=lambda cid, txt, **kw: admin_replies.append((cid, txt)))):
                await handle_restock_command(admin_msg)

            # Check admin received confirmation
            admin_confirm = [r[1] for r in admin_replies if r[0] == admin_id]
            self.assertTrue(len(admin_confirm) > 0, "Admin must receive confirmation")
            self.assertIn("muvaffaqiyatli to'ldirildi", admin_confirm[0])
            print(f"Admin restock confirmation:\n{admin_confirm[0]}")

            # Check waitlist customer received notification
            customer_notif = [r[1] for r in admin_replies if r[0] == waitlist_customer_id]
            self.assertEqual(len(customer_notif), 1, "Waitlist customer must be messaged exactly once")
            self.assertIn("XUSHXABAR", customer_notif[0])
            print(f"Waitlist notification:\n{customer_notif[0]}")

            # Verify stock actually increased
            p_restocked = DatabaseManager.get_product_by_id(10)
            self.assertEqual(p_restocked["stock_quantity"], stock_before + 5, "Stock must increase by 5")

            # Verify waitlist was cleared
            waiting_after = WaitlistService.get_waitlist_for_product(10)
            self.assertEqual(len(waiting_after), 0, "Waitlist for product 10 must be cleared after restock")

            # Restore original stock for product 10
            DatabaseManager.restock_product(10, -5)

        asyncio.run(_run_async_test())
        print("✅ TEST 5 PASSED: Non-admin strictly refused; Admin restock successfully updated stock and notified waitlist.")

if __name__ == "__main__":
    unittest.main()
