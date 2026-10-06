"""
run_all_tests.py
Executes all 16 test suites (11 unittest suites + 5 comprehensive procedural suites)
in strict order with clean DB / inventory teardowns and prints a unified report.
"""

import sys
import os
import unittest
import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.build_real_inventory import build_inventory
from database.db_manager import init_db

UNITTEST_SUITES = [
    ("tests.test_channel_integration", "Channel Deep Links & Boss Permissions"),
    ("tests.test_rules_compliance", "Rules 1-10 Full Compliance"),
    ("tests.test_task2_photos_stock", "Task 2: Real Photos, Stock & Restock"),
    ("tests.test_task3_order_state_machine", "Task 3: Order State Machine & Idempotency"),
    ("tests.test_task4_sales_intelligence", "Task 4: Sales Intelligence & Discounts"),
    ("tests.test_task5_human_handoff", "Task 5: Human Handoff & /bot_on"),
    ("tests.test_task6_media_input", "Task 6: Voice Transcription & Vision Search"),
    ("tests.test_world_class_upgrade", "World-Class Retail Upgrades"),
    ("tests.test_enterprise_features", "Enterprise VIP Loyalty & AI Stylist"),
    ("tests.test_channel_reply_intelligence", "Channel Post Replies & Discussion Intelligence"),
    ("tests.test_voice_sales_intelligence", "20-Year Sales Master Voice Response Intelligence"),
    ("tests.test_real_photo_presentation", "Instant Real Photo Presentation & Ranked Scoring")
]

PROCEDURAL_SUITES = [
    ("test_production_suite", "tests.test_production_suite", "test_production_flows"),
    ("test_consultative_sales", "tests.test_consultative_sales", "test_consultative_sales_flow"),
    ("test_conversational_intelligence", "tests.test_conversational_intelligence", "run_tests"),
    ("audit_everything", "tests.audit_everything", "run_deep_audit"),
    ("ultimate_verification", "tests.ultimate_verification", "run_ultimate_verification"),
]

def main():
    print("=" * 70)
    print("🚀 RUNNING ALL 16 VERIFICATION SUITES FOR MARKAZSAVDO AI STORE BOT")
    print("=" * 70)

    total_tests = 0
    total_failures = 0
    total_errors = 0
    results_summary = []

    # 1. Run all 9 Unittest Suites
    for mod_name, label in UNITTEST_SUITES:
        build_inventory()
        init_db()

        try:
            mod = importlib.import_module(mod_name)
            suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
            runner = unittest.TextTestRunner(verbosity=1)
            print(f"\n--- Running: {mod_name} ({label}) ---")
            res = runner.run(suite)

            total_tests += res.testsRun
            total_failures += len(res.failures)
            total_errors += len(res.errors)

            status = "PASSED" if (len(res.failures) == 0 and len(res.errors) == 0) else "FAILED"
            results_summary.append((mod_name, res.testsRun, status))
        except Exception as e:
            print(f"Error loading {mod_name}: {e}")
            total_errors += 1
            results_summary.append((mod_name, 0, "ERROR"))

    # 2. Run all 5 Procedural Suites
    for key, mod_name, fn_name in PROCEDURAL_SUITES:
        build_inventory()
        init_db()
        print(f"\n--- Running: {mod_name}.{fn_name} ---")

        try:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, fn_name)
            res = fn()
            status = "PASSED"
            total_tests += 1
            results_summary.append((mod_name, 1, status))
            print(f"✅ {mod_name} PASSED successfully!")
        except Exception as e:
            print(f"❌ {mod_name} FAILED: {e}")
            total_failures += 1
            total_tests += 1
            results_summary.append((mod_name, 1, "FAILED"))

    # Final cleanup to leave inventory pristine
    build_inventory()
    init_db()

    print("\n" + "=" * 70)
    print("📊 UNIFIED 16-SUITE TEST EXECUTION REPORT FOR @MARKAZSAVDO")
    print("=" * 70)
    for mod, count, status in results_summary:
        print(f"  {status.ljust(8)} | {count:2d} tests | {mod}")
    print("=" * 70)
    print(f"TOTAL TESTS / VERIFICATIONS RUN: {total_tests}")
    print(f"TOTAL FAILURES:                  {total_failures}")
    print(f"TOTAL ERRORS:                    {total_errors}")

    if total_failures == 0 and total_errors == 0:
        print("\n🏆 ALL 16 TEST & VERIFICATION SUITES PASSED WITH 100% SUCCESS RATE!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED. PLEASE FIX THEM.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
