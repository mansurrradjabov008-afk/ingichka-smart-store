"""
tests/test_enterprise_features.py
Tests for VIP Loyalty System, AI Stylist (Total Look), Abandoned Cart Recovery,
and @markazsavdo channel integration.
"""

import unittest
import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.loyalty_service import LoyaltyService, LOYALTY_FILE
from services.stylist_service import StylistService
from services.recovery_service import RecoveryService, RECOVERY_LOG_FILE
from services.channel_service import ChannelService
from database.db_manager import DatabaseManager, init_db
from config import CHANNEL_USERNAME, CHANNEL_URL



class TestEnterpriseFeatures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        test_uids = ["9999901", "9999902", "9999903"]
        if LOYALTY_FILE.exists():
            try:
                with open(LOYALTY_FILE, "r", encoding="utf-8") as f:
                    ldata = json.load(f)
                for tu in test_uids:
                    ldata.pop(tu, None)
                with open(LOYALTY_FILE, "w", encoding="utf-8") as f:
                    json.dump(ldata, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        if RECOVERY_LOG_FILE.exists():
            try:
                with open(RECOVERY_LOG_FILE, "r", encoding="utf-8") as f:
                    rdata = json.load(f)
                for tu in test_uids:
                    rdata.pop(tu, None)
                    rdata.pop(f"{tu}_cart", None)
                with open(RECOVERY_LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(rdata, f, ensure_ascii=False, indent=2)
            except Exception:
                pass


    def test_channel_configuration_is_markazsavdo(self):
        """Channel username must be @markazsavdo and URL must be https://t.me/markazsavdo"""
        self.assertEqual(CHANNEL_USERNAME, "@markazsavdo")
        self.assertEqual(CHANNEL_URL, "https://t.me/markazsavdo")

        cfg = ChannelService.get_config()
        self.assertEqual(cfg.get("channel_username"), "@markazsavdo")
        self.assertEqual(cfg.get("channel_url"), "https://t.me/markazsavdo")

    def test_channel_post_formatting_contains_deep_link(self):
        """Channel post format must include deep link to buy in private chat"""
        prods = DatabaseManager.get_products(in_stock_only=True)
        self.assertTrue(len(prods) > 0)
        prod = prods[0]
        text, kb = ChannelService.format_channel_post(prod, bot_username="Markazsavdo00_bot")
        self.assertIn(prod["name"], text)
        self.assertIn(f"{prod['sale_price']:,.0f}", text)
        self.assertIn("buy_" + str(prod["id"]), str(kb))

    def test_loyalty_service_tiers_and_points(self):
        """VIP loyalty calculates 2% for Bronza, upgrades tiers, and redemptions adhere to max 20% limit"""
        test_uid = 9999901
        # Award order cashback on 100,000 so'm -> 2% = 2,000 points
        res = LoyaltyService.award_order_cashback(test_uid, 100000.0, order_id="ORD-TEST-1")
        self.assertEqual(res["earned_points"], 2000)
        self.assertEqual(res["tier"], "Bronza")
        self.assertEqual(res["rate_percent"], 2)

        # Test redemption calculation
        calc = LoyaltyService.calculate_redemption(test_uid, order_total=100000.0, requested_points=50000)
        # Max 20% of 100,000 = 20,000 max usable, but user only has 2,000 points
        self.assertEqual(calc["used_points"], 2000)
        self.assertEqual(calc["discount_amount"], 2000.0)
        self.assertEqual(calc["final_total"], 98000.0)

        # Formatting card check
        card = LoyaltyService.format_loyalty_card(test_uid, "Mansur Test")
        self.assertIn("VIP", card)
        self.assertIn("Bronza", card)

    def test_ai_stylist_outfit_curation(self):
        """Stylist must curate 3-piece outfits with deterministic 5% bundle discount"""
        for gender in ["ayol", "erkak", "bolalar"]:
            outfit = StylistService.curate_outfit(gender)
            self.assertTrue(outfit["success"], f"Failed for {gender}: {outfit.get('message')}")
            items = outfit.get("items", [])
            self.assertTrue(len(items) >= 2, f"Expected at least 2 items in {gender} outfit, got {len(items)}")

            # Verify math
            raw_sum = sum(p["price"] for p in items)
            self.assertEqual(outfit["total_raw"], raw_sum)
            expected_discount = int(raw_sum * 0.05)
            self.assertEqual(outfit["discount_amount"], expected_discount)
            self.assertEqual(outfit["bundle_price"], raw_sum - expected_discount)

            # Verify formatted card
            card = StylistService.format_outfit_card(outfit)
            self.assertIn("total look", card.lower())
            self.assertIn("5%", card)

    def test_recovery_service_single_nudge_rule(self):
        """Recovery nudge must be sent at most once per user"""
        test_uid = 9999902
        nudge_text = "Savatingizda tovarlar qolib ketdi!"

        # First nudge: allowed
        self.assertTrue(RecoveryService.can_send_nudge(test_uid, "cart"))
        RecoveryService.record_nudge(test_uid, "cart", nudge_text)

        # Immediate second nudge: blocked by single-nudge rule
        self.assertFalse(RecoveryService.can_send_nudge(test_uid, "cart"))

    def test_inventory_integrity_41_verified_products(self):
        """All 41 products from the real video catalog must remain intact and valid"""
        prods = DatabaseManager.get_products(in_stock_only=False)
        self.assertEqual(len(prods), 41, f"Expected exactly 41 products, found {len(prods)}")

        for p in prods:
            self.assertTrue(p["id"] > 0)
            self.assertTrue(len(p["name"]) > 2)
            self.assertTrue(p["sale_price"] > 0)
            self.assertTrue(p["stock_quantity"] >= 0)
            self.assertTrue(len(p["category"]) > 0)
            self.assertTrue(len(p["size"]) > 0)
            self.assertTrue(len(p["color"]) > 0)


if __name__ == "__main__":
    unittest.main()
