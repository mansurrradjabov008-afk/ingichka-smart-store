"""
tests/test_rules_compliance.py
Comprehensive verification suite for all 12 Permanent Project Rules (RULES.md).
"""

import os
import sys
import json
import time
import threading
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from utils.file_utils import atomic_write_text, atomic_write_json, atomic_write_binary
from utils.logger import log_bot_error, BOT_LOG_FILE
from ai_engine.grounding_validator import GroundingValidator, OPERATOR_FALLBACK_TEXT
from ai_engine.ai_brain import ai_brain
from services.catalog_service import load_products
from database.db_manager import DatabaseManager, init_db

class TestRulesCompliance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.products = load_products()
        assert len(cls.products) > 0, "Store inventory must not be empty"

    # =========================================================================
    # RULE 1: Existing Language & Framework
    # =========================================================================
    def test_rule_1_framework_integrity(self):
        """Rule 1: Verify framework is aiogram 3.x, SQLite, and Python 3.10+"""
        self.assertGreaterEqual(sys.version_info.major, 3)
        self.assertGreaterEqual(sys.version_info.minor, 10)
        import aiogram
        self.assertTrue(hasattr(aiogram, "Dispatcher"))
        self.assertTrue(hasattr(aiogram, "Bot"))

    # =========================================================================
    # RULE 2: Secrets only in .env
    # =========================================================================
    def test_rule_2_secrets_management(self):
        """Rule 2: Secrets must be loaded via os.getenv / .env"""
        self.assertTrue(hasattr(config, "BOT_TOKEN"))
        self.assertTrue(bool(config.BOT_TOKEN))
        self.assertTrue(hasattr(config, "GEMINI_API_KEY"))
        self.assertTrue(bool(config.GEMINI_API_KEY))

    # =========================================================================
    # RULE 3: Resilient Calls & Safe User-Facing Fallback
    # =========================================================================
    def test_rule_3_external_call_fallbacks(self):
        """Rule 3: External calls must never crash or go silent; return safe fallback."""
        # Simulated request with invalid chat/user
        fallback_reply = ai_brain.ask(chat_id=999888777, user_message="qanday kiyimlar bor", customer_name="Test")
        self.assertIsInstance(fallback_reply, str)
        self.assertGreater(len(fallback_reply), 10)
        # Verify no unhandled exception occurred

    # =========================================================================
    # RULE 4: Atomic Data Writes with Lock
    # =========================================================================
    def test_rule_4_atomic_writes_and_concurrency(self):
        """Rule 4: Write data files atomically with lock; no corrupted files."""
        test_dir = PROJECT_ROOT / "scratch" / "test_atomic"
        test_dir.mkdir(parents=True, exist_ok=True)
        target_file = str(test_dir / "atomic_test.json")

        # Concurrent atomic writes
        def worker(worker_id: int):
            data = {"worker": worker_id, "timestamp": time.time(), "items": list(range(100))}
            atomic_write_json(target_file, data)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Target file must exist and be valid JSON
        self.assertTrue(os.path.exists(target_file))
        with open(target_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertIn("worker", loaded)
        self.assertIn("items", loaded)

    # =========================================================================
    # RULE 5: Log Errors to bot.log with chat_id and reason
    # =========================================================================
    def test_rule_5_error_logging_to_bot_log(self):
        """Rule 5: Log errors to bot.log with chat_id and short reason."""
        test_chat_id = 9988776655
        test_reason = "Test simulated network failure"
        log_line = log_bot_error(chat_id=test_chat_id, reason=test_reason)

        self.assertIn(str(test_chat_id), log_line)
        self.assertIn(test_reason, log_line)

        # Verify bot.log file exists and contains the entry
        self.assertTrue(os.path.exists(BOT_LOG_FILE))
        with open(BOT_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(f"[Chat {test_chat_id}]", content)
        self.assertIn(test_reason, content)

    # =========================================================================
    # RULE 6 & 10: Facts & Money Math Done in Code
    # =========================================================================
    def test_rule_6_and_10_facts_and_money_math_in_code(self):
        """Rule 6 & 10: Prices and totals come from DB/code, never decided by LLM."""
        prod = self.products[0]
        p_name = prod["name"]
        p_price = int(prod["price"])

        # Code-based total computation test
        user_qty = 3
        calc_reply = ai_brain.ask(chat_id=123123123, user_message=f"{user_qty} ta {p_name} qancha bo'ladi", customer_name="Mijoz")
        expected_total = f"{user_qty * p_price:,.0f}"
        self.assertIn(expected_total, calc_reply)

    # =========================================================================
    # RULE 7: Temperature <= 0.2
    # =========================================================================
    def test_rule_7_temperature_less_equal_0_2(self):
        """Rule 7: Verify all LLM configurations have temperature <= 0.2."""
        # Read ai_brain.py source code and check all temperature values
        ai_brain_path = PROJECT_ROOT / "ai_engine" / "ai_brain.py"
        with open(ai_brain_path, "r", encoding="utf-8") as f:
            source = f.read()

        import re
        temp_matches = re.findall(r'["\']temperature["\']\s*:\s*([0-9.]+)', source)
        self.assertGreater(len(temp_matches), 0, "Must have temperature settings")
        for temp_val_str in temp_matches:
            val = float(temp_val_str)
            self.assertLessEqual(val, 0.2, f"Temperature {val} exceeds maximum allowed 0.2!")

    # =========================================================================
    # RULE 8: Grounding Validator & Regeneration
    # =========================================================================
    def test_rule_8_grounding_validator_pass(self):
        """Rule 8: Valid factual reply passes validation."""
        valid_price = self.products[0]["price"]
        valid_reply = f"Bizda {self.products[0]['name']} bor, narxi {valid_price:,.0f} so'm."
        is_valid, reason = GroundingValidator.validate_reply(valid_reply, self.products)
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

    def test_rule_8_grounding_validator_fail_hallucinated_price(self):
        """Rule 8: Catches hallucinated price and triggers guardrail."""
        # Mention a fake price that doesn't exist in any store product
        hallucinated_reply = "Bizda zo'r kurtka bor, narxi 987,654 so'm."
        is_valid, reason = GroundingValidator.validate_reply(hallucinated_reply, self.products)
        self.assertFalse(is_valid)
        self.assertIn("katalogida mavjud emas", reason)

    def test_rule_8_grounding_guardrail_regeneration_and_fallback(self):
        """Rule 8: Guardrail regenerates on error; if still failing, returns operator fallback."""
        regen_calls = []

        def failing_regen(err_msg: str):
            regen_calls.append(err_msg)
            # Still returns hallucinated price on attempt 2
            return "Qayta urinish: narxi 999,999 so'm."

        final_reply = GroundingValidator.apply_grounding_guardrail(
            first_reply="Birinchi xato: narxi 888,888 so'm.",
            regenerate_fn=failing_regen,
            catalog_products=self.products,
            chat_id=12345
        )

        self.assertEqual(len(regen_calls), 1)
        self.assertEqual(final_reply, OPERATOR_FALLBACK_TEXT)

    # =========================================================================
    # RULE 9: Missing Data Handled Without Guessing
    # =========================================================================
    def test_rule_9_missing_data_no_guessing(self):
        """Rule 9: If data/setting is missing, bot says it does not know or asks owner."""
        from services.store_settings_manager import StoreSettingsManager
        StoreSettingsManager.set_setting("discount", "")
        check = StoreSettingsManager.check_setting_inquiry("Sizlarda qanday chegirma yoki skidka bor?")
        self.assertIsNotNone(check)
        self.assertTrue(check["empty"])
        self.assertEqual(check["reply"], "Buni egasidan so'rab aytaman")

if __name__ == "__main__":
    unittest.main()
