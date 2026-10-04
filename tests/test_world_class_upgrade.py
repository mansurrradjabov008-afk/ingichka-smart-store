"""
World-Class Flagship Upgrade Test Suite (v5.0)
Testing all 6 major enterprise e-commerce components:
1. Interactive Multi-Item Cart (CartManager)
2. Dynamic Promo Codes & Discount Engine (PromoManager)
3. Real-time Order Tracker with 4-step Visual Status (OrderTracker)
4. AI Cross-sell & Upsell Recommendations (RecommendationEngine)
5. 5-Star Customer Review & Rating System (ReviewManager)
6. Enterprise Keyboards & Carousel Controls (bot.keyboards)
"""

import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db_manager import DatabaseManager, init_db
from services.cart_manager import CartManager
from services.promo_manager import PromoManager
from services.order_tracker import OrderTracker, STATUS_MAP
from services.recommendation_engine import RecommendationEngine
from services.review_manager import ReviewManager
from bot.keyboards import (
    get_main_menu,
    get_product_card_keyboard,
    get_cart_keyboard,
    get_order_action_keyboard,
    get_review_stars_keyboard,
)

class TestWorldClassUpgrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        ReviewManager.init_reviews_table()
        prods = DatabaseManager.get_products()
        assert len(prods) > 0, "Database must have products for testing"
        cls.sample_product = prods[0]
        cls.test_user_id = 888999111

    def setUp(self):
        CartManager.clear_cart(self.test_user_id)

    def tearDown(self):
        CartManager.clear_cart(self.test_user_id)

    # ---------------- 1. CartManager Tests ----------------
    def test_cart_add_and_quantities(self):
        pid = self.sample_product["id"]
        # Add 1
        res1 = CartManager.add_item(self.test_user_id, pid, quantity=1)
        self.assertTrue(res1["success"])
        self.assertEqual(CartManager.get_cart_item_count(self.test_user_id), 1)

        # Add 1 more
        res2 = CartManager.add_item(self.test_user_id, pid, quantity=1)
        self.assertTrue(res2["success"])
        self.assertEqual(CartManager.get_cart_item_count(self.test_user_id), 2)

        # Increment via update_quantity
        CartManager.update_quantity(self.test_user_id, pid, delta=+1)
        self.assertEqual(CartManager.get_cart_item_count(self.test_user_id), 3)

        # Decrement via update_quantity
        CartManager.update_quantity(self.test_user_id, pid, delta=-1)
        self.assertEqual(CartManager.get_cart_item_count(self.test_user_id), 2)

        # Remove item
        CartManager.remove_item(self.test_user_id, pid)
        self.assertEqual(CartManager.get_cart_item_count(self.test_user_id), 0)

    def test_cart_promo_and_summary(self):
        pid = self.sample_product["id"]
        price = float(self.sample_product["sale_price"])
        CartManager.add_item(self.test_user_id, pid, quantity=2)

        # Apply 10% promo
        promo_res = CartManager.apply_promo(self.test_user_id, "MARKAZ10")
        self.assertTrue(promo_res["success"])

        summary = CartManager.get_cart_summary(self.test_user_id)
        expected_subtotal = price * 2
        expected_discount = expected_subtotal * 0.10
        expected_final = expected_subtotal - expected_discount

        self.assertEqual(summary["raw_total"], expected_subtotal)
        self.assertEqual(summary["discount_val"], expected_discount)
        self.assertEqual(summary["final_total"], expected_final)
        self.assertEqual(summary["promo_code"], "MARKAZ10")

        # Formatted message
        formatted = CartManager.format_cart_message(self.test_user_id)
        self.assertIn("SAVATCHANGIZ", formatted)
        self.assertIn("MARKAZ10", formatted)

    # ---------------- 2. PromoManager Tests ----------------
    def test_promo_manager_validation(self):
        # Valid promo
        res_valid = PromoManager.validate_code("MARKAZ10")
        self.assertTrue(res_valid["valid"])
        self.assertEqual(res_valid["value"], 10.0)

        # Invalid promo
        res_invalid = PromoManager.validate_code("NONEXISTENT_CODE")
        self.assertFalse(res_invalid["valid"])

        # Register usage
        before_count = PromoManager._promo_codes["MARKAZ10"]["usage_count"]
        PromoManager.register_usage("MARKAZ10")
        self.assertEqual(PromoManager._promo_codes["MARKAZ10"]["usage_count"], before_count + 1)

        # Display text contains active codes
        display_text = PromoManager.get_active_promos_display()
        self.assertIn("MARKAZ10", display_text)
        self.assertIn("SUPER2026", display_text)
        self.assertIn("VIPMIJOZ", display_text)

    # ---------------- 3. OrderTracker Tests ----------------
    def test_order_tracker_lifecycle(self):
        cust_id = 999111222
        DatabaseManager.upsert_customer(cust_id, "Test Mijoz", "+998901112233", "Ingichka Shaharchasi")
        order_res = DatabaseManager.create_order(
            customer_telegram_id=cust_id,
            customer_name="Test Mijoz",
            customer_phone="+998901112233",
            delivery_address="Ingichka Shaharchasi",
            items=[{"product_id": self.sample_product["id"], "quantity": 1}],
            payment_method="cash_on_delivery",
            notes="World Class Test Order"
        )
        self.assertTrue(order_res["success"])
        oid = order_res["order_id"]

        # 1. Check orders view formatting
        cust_orders = OrderTracker.get_customer_orders(cust_id, limit=5)
        self.assertGreaterEqual(len(cust_orders), 1)
        view_text = OrderTracker.format_orders_view("Test Mijoz", cust_orders)
        self.assertIn("SIZNING BUYURTMALARINGIZ", view_text)
        self.assertIn(f"#{oid}", view_text)

        # 2. Update status to 'tayyorlanmoqda' (Qadoqlanmoqda)
        up1 = DatabaseManager.update_order_status(oid, "tayyorlanmoqda")
        self.assertTrue(up1)
        push1 = OrderTracker.format_status_notification(oid, "tayyorlanmoqda", 85000)
        self.assertIn("Qadoqlanmoqda", push1)

        # 3. Update status to 'yetkazilmoqda' (Yo'lda)
        up2 = DatabaseManager.update_order_status(oid, "yetkazilmoqda")
        self.assertTrue(up2)
        push2 = OrderTracker.format_status_notification(oid, "yetkazilmoqda", 85000)
        self.assertIn("Yo'lda", push2)

        # 4. Update status to 'yakunlandi' (Yetkazildi)
        up3 = DatabaseManager.update_order_status(oid, "yakunlandi")
        self.assertTrue(up3)
        push3 = OrderTracker.format_status_notification(oid, "yakunlandi", 85000)
        self.assertIn("Yetkazildi", push3)

    # ---------------- 4. RecommendationEngine Tests ----------------
    def test_cross_sell_recommendations(self):
        # Recommendation for Futbolka
        rec = RecommendationEngine.get_cross_sell_for_product("Oq klassik futbolka", exclude_ids=[self.sample_product["id"]])
        self.assertIsNotNone(rec)
        self.assertNotEqual(rec["id"], self.sample_product["id"])

        # Pitch generator
        pitch = RecommendationEngine.format_cross_sell_pitch("Oq klassik futbolka", rec)
        self.assertIsInstance(pitch, str)
        self.assertTrue(len(pitch) > 10)
        self.assertIn(rec["name"], pitch)

    # ---------------- 5. ReviewManager Tests ----------------
    def test_review_submission_and_rating(self):
        user_rev_id = 777000111

        # Submit 5 star review
        res = ReviewManager.add_review(
            user_id=user_rev_id,
            user_name="Mijozbek",
            rating=5,
            order_id=123,
            comment="Ajoyib sifat va tez yetkazish!"
        )
        self.assertTrue(res)

        # Check store rating
        summary = ReviewManager.get_store_rating()
        self.assertGreaterEqual(summary["total_reviews"], 1)
        self.assertGreaterEqual(summary["average_rating"], 1.0)
        self.assertLessEqual(summary["average_rating"], 5.0)

        # Recent reviews
        recent = ReviewManager.get_recent_reviews(limit=5)
        self.assertTrue(len(recent) >= 1)
        self.assertEqual(recent[0]["user_name"], "Mijozbek")

    # ---------------- 6. Enterprise Keyboards Tests ----------------
    def test_enterprise_keyboards(self):
        # Main menu with cart count badge
        menu_empty = get_main_menu(is_admin=False, cart_count=0)
        menu_with_items = get_main_menu(is_admin=False, cart_count=3)
        
        flat_empty = [b.text for row in menu_empty.keyboard for b in row]
        flat_items = [b.text for row in menu_with_items.keyboard for b in row]
        
        self.assertIn("🛒 Savatcham", flat_empty)
        self.assertIn("🛒 Savatcham (3)", flat_items)
        self.assertIn("🏷️ Aksiya va Promokodlar", flat_items)

        # Product card carousel keyboard
        prod_kb = get_product_card_keyboard(
            product_id=self.sample_product["id"],
            category="Futbolka",
            current_idx=0,
            total_count=5
        )
        buttons_text = [b.text for row in prod_kb.inline_keyboard for b in row]
        self.assertTrue(any("Savatga qo'shish" in t for t in buttons_text))
        self.assertTrue(any("Hoziroq sotib olish" in t for t in buttons_text))
        self.assertTrue(any("Keyingi" in t for t in buttons_text))

        # Cart keyboard
        cart_items = [{"product_id": 1, "name": "Futbolka", "quantity": 2, "price": 85000}]
        cart_kb = get_cart_keyboard(cart_items, has_promo=False)
        cart_buttons = [b.text for row in cart_kb.inline_keyboard for b in row]
        self.assertTrue(any("➕" in t for t in cart_buttons))
        self.assertTrue(any("➖" in t for t in cart_buttons))
        self.assertTrue(any("Buyurtma berish" in t for t in cart_buttons))

        # Order action keyboard for admins
        order_kb = get_order_action_keyboard(order_id=999)
        order_buttons = [b.text for row in order_kb.inline_keyboard for b in row]
        self.assertTrue(any("Qadoqlash" in t for t in order_buttons))
        self.assertTrue(any("Kuryerga berish" in t for t in order_buttons))
        self.assertTrue(any("Yetkazildi" in t for t in order_buttons))

        # Review stars keyboard
        rev_kb = get_review_stars_keyboard(order_id=999)
        rev_buttons = [b.text for row in rev_kb.inline_keyboard for b in row]
        self.assertEqual(len(rev_buttons), 5)
        self.assertIn("⭐️ 5", rev_buttons[4])

if __name__ == "__main__":
    unittest.main()
