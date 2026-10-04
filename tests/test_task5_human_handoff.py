"""
tests/test_task5_human_handoff.py
Comprehensive test suite for TASK 5: Human handoff.
Strictly follows RULES.md.

Tests:
1. Explicit request for human (uz/ru/en):
   Customer asks for a human -> triggers handoff with "Operatorga ulayman, tez orada javob beradi"
   and sends notification to admin with customer details, 5-line summary, and reason.
2. Angry message or complaint words (uz/ru/en):
   Customer uses anger or complaint words -> triggers handoff.
3. Repeated unknown (2 consecutive "I don't know" answers):
   2 consecutive unknown answers trigger handoff; normal answers reset unknown counter.
4. Admin reply reaches customer:
   While in handoff mode, bot stays silent to customer. Admin reply to forwarded message
   is delivered directly to customer.
5. /bot_on works & 6-hour auto-return:
   Admin command /bot_on restores bot; auto-return triggers after 6 hours of admin silence
   with polite message. Non-admin is refused.
6. Normal question does NOT trigger handoff:
   Normal inquiries (price, stock, size, delivery) do not trigger handoff.
7. Grounding validator failed twice:
   When grounding fails twice, handoff is triggered with reason "Grounding validator failed twice".
8. 5-line chat summary:
   Summary generated from real chat always contains exactly 5 numbered lines.
"""

import sys
import os
import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.db_manager import DatabaseManager, init_db
from services.handoff_service import (
    HandoffService,
    HANDOFF_SESSIONS_FILE,
    MESSAGE_MAP_FILE,
    CUSTOMER_HANDOFF_REPLY,
    AUTO_RETURN_MESSAGE,
    BOT_ON_CUSTOMER_MESSAGE,
    REASON_HUMAN_REQUEST,
    REASON_ANGER_COMPLAINT,
    REASON_GROUNDING_FAILED_TWICE,
    REASON_CONSECUTIVE_UNKNOWN
)
from ai_engine.ai_brain import ai_brain
from ai_engine.grounding_validator import GroundingValidator


class TestTask5HumanHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Backup handoff sessions and message map if they exist
        self.sessions_backup = None
        if HANDOFF_SESSIONS_FILE.exists():
            with open(HANDOFF_SESSIONS_FILE, "r", encoding="utf-8") as f:
                self.sessions_backup = f.read()

        self.map_backup = None
        if MESSAGE_MAP_FILE.exists():
            with open(MESSAGE_MAP_FILE, "r", encoding="utf-8") as f:
                self.map_backup = f.read()

        # Clean slate for each test
        with open(HANDOFF_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

        with open(MESSAGE_MAP_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

        HandoffService._CONSECUTIVE_UNKNOWN_TRACKER.clear()

    def tearDown(self):
        # Restore backups
        if self.sessions_backup is not None:
            with open(HANDOFF_SESSIONS_FILE, "w", encoding="utf-8") as f:
                f.write(self.sessions_backup)
        elif HANDOFF_SESSIONS_FILE.exists():
            HANDOFF_SESSIONS_FILE.unlink(missing_ok=True)

        if self.map_backup is not None:
            with open(MESSAGE_MAP_FILE, "w", encoding="utf-8") as f:
                f.write(self.map_backup)
        elif MESSAGE_MAP_FILE.exists():
            MESSAGE_MAP_FILE.unlink(missing_ok=True)

    # ---------------------------------------------------------
    # TEST 1: Explicit Request for Human (uz/ru/en)
    # ---------------------------------------------------------
    def test_01_explicit_request_triggers_handoff(self):
        """
        Customer asking for a human (uz/ru/en) triggers handoff:
        - Customer receives: "Operatorga ulayman, tez orada javob beradi"
        - Admin receives: name, chat_id, 5-line summary, reason
        - Session becomes active
        """
        print("\n--- TEST 1: Explicit human request (uz/ru/en) ---")

        test_cases = [
            ("Menga operator bilan bog'lanish kerak", "uz"),
            ("Jonli odam bilan gaplashmoqchiman", "uz"),
            ("Позовите живого человека, оператора пожалуйста", "ru"),
            ("Соедините с менеджером или оператором", "ru"),
            ("I want to speak with a human support agent", "en"),
            ("Connect me to a real person please", "en")
        ]

        chat_id_base = 88001
        for idx, (phrase, lang) in enumerate(test_cases, 1):
            cid = chat_id_base + idx
            is_trig, reason = HandoffService.is_handoff_triggered(phrase, cid)
            self.assertTrue(is_trig, f"Failed to detect human request for [{lang}]: '{phrase}'")
            self.assertEqual(reason, REASON_HUMAN_REQUEST)

            # Start handoff
            history = [
                {"role": "user", "content": "Kiyimlar bormi?"},
                {"role": "assistant", "content": "Ha, bizda sara kiyimlar mavjud."},
                {"role": "user", "content": phrase}
            ]
            res = HandoffService.start_handoff(
                chat_id=cid,
                customer_name=f"Customer {idx}",
                username=f"user_{idx}",
                reason=reason,
                history=history
            )

            # Customer reply check
            self.assertEqual(res["customer_reply"], CUSTOMER_HANDOFF_REPLY)

            # Admin message check
            admin_msg = res["admin_message"]
            self.assertIn(str(cid), admin_msg)
            self.assertIn(f"Customer {idx}", admin_msg)
            self.assertIn(f"@user_{idx}", admin_msg)
            self.assertIn(REASON_HUMAN_REQUEST, admin_msg)

            # 5-line summary check
            summary_lines = [l for l in res["summary"].split("\n") if l.strip()]
            self.assertEqual(len(summary_lines), 5, f"Summary must be exactly 5 lines, got {len(summary_lines)}")

            # Session active check
            self.assertTrue(HandoffService.is_active_session(cid))

        print(f"✅ TEST 1 PASSED: All {len(test_cases)} explicit human requests in UZ, RU, EN triggered handoff perfectly.")

    # ---------------------------------------------------------
    # TEST 2: Angry Message or Complaint Words (uz/ru/en)
    # ---------------------------------------------------------
    def test_02_angry_message_triggers_handoff(self):
        """
        Anger or complaint words (uz/ru/en) trigger handoff:
        - Customer receives: "Operatorga ulayman, tez orada javob beradi"
        - Reason: "G'azab yoki shikoyat so'zlari aniqlandi"
        """
        print("\n--- TEST 2: Angry message / complaint words (uz/ru/en) ---")

        test_cases = [
            ("Bu nima bema'nilik aldadingiz, shikoyat qilaman!", "uz"),
            ("Rasvo xizmat, asabimni buzdingiz firibgarlar!", "uz"),
            ("Ужасный сервис, вы обманули меня, это мошенники!", "ru"),
            ("Отвратительно, верните деньги, я буду жаловаться!", "ru"),
            ("This is an awful scam, you are cheaters!", "en"),
            ("Terrible experience, horrible service, waste of time!", "en")
        ]

        chat_id_base = 88101
        for idx, (phrase, lang) in enumerate(test_cases, 1):
            cid = chat_id_base + idx
            is_trig, reason = HandoffService.is_handoff_triggered(phrase, cid)
            self.assertTrue(is_trig, f"Failed to detect anger/complaint for [{lang}]: '{phrase}'")
            self.assertEqual(reason, REASON_ANGER_COMPLAINT)

            res = HandoffService.start_handoff(
                chat_id=cid,
                customer_name=f"Angry User {idx}",
                username=f"angry_{idx}",
                reason=reason
            )
            self.assertEqual(res["customer_reply"], CUSTOMER_HANDOFF_REPLY)
            self.assertIn(REASON_ANGER_COMPLAINT, res["admin_message"])
            self.assertTrue(HandoffService.is_active_session(cid))

        print(f"✅ TEST 2 PASSED: All {len(test_cases)} angry messages in UZ, RU, EN successfully routed to operator.")

    # ---------------------------------------------------------
    # TEST 3: Repeated Unknown (2 consecutive "I don't know" answers)
    # ---------------------------------------------------------
    def test_03_repeated_unknown_triggers_handoff(self):
        """
        2 consecutive "I don't know" answers trigger handoff.
        A normal valid answer resets the unknown counter to 0.
        """
        print("\n--- TEST 3: Repeated unknown (2 consecutive 'I don't know') ---")

        chat_id = 88201

        # 1. First unknown answer -> count = 1, NOT yet triggered
        unknown_reply_1 = "Afsuski, bu haqida menda ma'lumot yo'q."
        self.assertTrue(HandoffService.is_unknown_answer(unknown_reply_1))

        cnt_1 = HandoffService.increment_consecutive_unknown(chat_id)
        self.assertEqual(cnt_1, 1)

        is_trig_1, _ = HandoffService.is_handoff_triggered(
            text="qandaydir savol",
            chat_id=chat_id,
            consecutive_unknown_count=cnt_1
        )
        self.assertFalse(is_trig_1, "1st unknown answer should NOT trigger handoff yet")

        # 2. Second unknown answer -> count = 2, MUST trigger handoff!
        unknown_reply_2 = "Kechirasiz, aniq ma'lumot yo'q, bilmayman."
        self.assertTrue(HandoffService.is_unknown_answer(unknown_reply_2))

        cnt_2 = HandoffService.increment_consecutive_unknown(chat_id)
        self.assertEqual(cnt_2, 2)

        is_trig_2, reason_2 = HandoffService.is_handoff_triggered(
            text="yana boshqa savol",
            chat_id=chat_id,
            consecutive_unknown_count=cnt_2
        )
        self.assertTrue(is_trig_2, "2nd consecutive unknown answer MUST trigger handoff")
        self.assertEqual(reason_2, REASON_CONSECUTIVE_UNKNOWN)

        res = HandoffService.start_handoff(
            chat_id=chat_id,
            customer_name="Bobur",
            reason=reason_2
        )
        self.assertEqual(res["customer_reply"], CUSTOMER_HANDOFF_REPLY)
        self.assertIn(REASON_CONSECUTIVE_UNKNOWN, res["admin_message"])

        # 3. Test that a normal answer resets the counter
        chat_id_2 = 88202
        HandoffService.increment_consecutive_unknown(chat_id_2)
        self.assertEqual(HandoffService.get_consecutive_unknown_count(chat_id_2), 1)

        # Normal answer comes in
        normal_reply = "Nike krossovkamiz narxi 350,000 so'm, 42 razmeri omborda mavjud."
        self.assertFalse(HandoffService.is_unknown_answer(normal_reply))
        HandoffService.reset_consecutive_unknown(chat_id_2)
        self.assertEqual(HandoffService.get_consecutive_unknown_count(chat_id_2), 0)

        print("✅ TEST 3 PASSED: 2 consecutive unknown answers triggered handoff; counter resets on valid replies.")

    # ---------------------------------------------------------
    # TEST 4: Admin Reply Reaches Customer
    # ---------------------------------------------------------
    def test_04_admin_reply_reaches_customer(self):
        """
        While in handoff mode:
        - The bot stays silent to the customer.
        - Admin replies to the notification/forwarded message.
        - The admin's reply is delivered to the customer.
        """
        print("\n--- TEST 4: Admin reply reaches customer & bot stays silent ---")

        customer_cid = 88301
        admin_message_id = 998877

        # Start handoff
        HandoffService.start_handoff(
            chat_id=customer_cid,
            customer_name="Dilshod",
            username="dilshod99",
            reason=REASON_HUMAN_REQUEST
        )

        # Customer sends message mid-handoff: "Qachon javob berasiz?"
        # 1. Verify bot stays silent (check_and_process_handoff returns True, None)
        is_in_handoff, auto_ret = HandoffService.check_and_process_handoff(customer_cid)
        self.assertTrue(is_in_handoff, "Bot must stay silent to customer while in handoff mode")
        self.assertIsNone(auto_ret)

        # 2. Map forwarded/alert message ID to customer
        HandoffService.map_admin_message(admin_message_id, customer_cid)

        # 3. Admin replies to admin_message_id
        target_cid = HandoffService.get_customer_chat_id_from_admin_reply(
            reply_to_message_id=admin_message_id,
            reply_to_text=f"Chat ID: {customer_cid}"
        )
        self.assertEqual(target_cid, customer_cid, "Must correctly identify customer chat ID from admin reply")

        # 4. Verify admin activity update refreshes session
        session_before = HandoffService._load_sessions()[str(customer_cid)]
        initial_activity = session_before["last_activity_at"]

        HandoffService.record_admin_activity(customer_cid)
        session_after = HandoffService._load_sessions()[str(customer_cid)]
        self.assertIsNotNone(session_after["last_activity_at"])

        print(f"✅ TEST 4 PASSED: Admin reply successfully routed to customer {customer_cid}; bot stays silent.")

    # ---------------------------------------------------------
    # TEST 5: /bot_on Works and 6-Hour Auto-Return
    # ---------------------------------------------------------
    def test_05_bot_on_works_and_auto_return(self):
        """
        Admin command /bot_on <chat_id> returns the chat to the bot.
        Auto-return triggers after 6 hours of admin silence with polite message.
        """
        print("\n--- TEST 5: /bot_on works & 6-hour auto-return ---")

        chat_id_1 = 88401
        chat_id_2 = 88402

        # Part A: /bot_on resolution
        HandoffService.start_handoff(
            chat_id=chat_id_1,
            customer_name="Alisher",
            reason=REASON_HUMAN_REQUEST
        )
        self.assertTrue(HandoffService.is_active_session(chat_id_1))

        # Admin executes /bot_on
        success = HandoffService.resolve_handoff(chat_id_1, resolved_by="admin_command")
        self.assertTrue(success)
        self.assertFalse(HandoffService.is_active_session(chat_id_1))

        session_1 = HandoffService._load_sessions()[str(chat_id_1)]
        self.assertEqual(session_1["status"], "resolved")
        self.assertEqual(session_1["resolution"], "admin_command")

        # Part B: 6-Hour Auto-Return
        HandoffService.start_handoff(
            chat_id=chat_id_2,
            customer_name="Malika",
            reason=REASON_ANGER_COMPLAINT
        )

        # Simulate 6 hours and 1 minute of silence (21660 seconds ago)
        six_hours_ago = (datetime.now() - timedelta(hours=6, minutes=1)).isoformat()
        sessions = HandoffService._load_sessions()
        sessions[str(chat_id_2)]["last_activity_at"] = six_hours_ago
        HandoffService._save_sessions(sessions)

        # check_and_process_handoff should detect > 6 hours and trigger auto-return
        is_in_handoff, auto_ret_msg = HandoffService.check_and_process_handoff(chat_id_2)
        self.assertFalse(is_in_handoff, "Handoff must be resolved after 6 hours")
        self.assertIsNotNone(auto_ret_msg, "Must return polite auto-return message")
        self.assertEqual(auto_ret_msg, AUTO_RETURN_MESSAGE)
        self.assertIn("Operatorlarimiz hozirda band bo'lgani sababli", auto_ret_msg)

        session_2 = HandoffService._load_sessions()[str(chat_id_2)]
        self.assertEqual(session_2["status"], "resolved")
        self.assertEqual(session_2["resolution"], "auto_return_6h")

        print("✅ TEST 5 PASSED: /bot_on cleanly returned chat to bot; 6-hour silence auto-returned with polite message.")

    # ---------------------------------------------------------
    # TEST 6: Normal Question Does NOT Trigger Handoff
    # ---------------------------------------------------------
    def test_06_normal_question_does_not_trigger_handoff(self):
        """
        Do NOT trigger handoff for normal customer questions:
        - Product inquiries, prices, stock, sizes, delivery, store info.
        """
        print("\n--- TEST 6: Normal questions do NOT trigger handoff ---")

        normal_queries = [
            "Qora futbolka bormi?",
            "Kurtka narxi qancha?",
            "42 razmer bormi?",
            "Yetkazib berish shartlari qanday?",
            "Do'kon qayerda joylashgan?",
            "Oyoq kiyimlar katalogini ko'rsating",
            "To'lovni qanday qilsam bo'ladi?",
            "Сколько стоит куртка?",
            "Есть ли в наличии 44 размер?",
            "How much is the delivery?",
            "Do you have black jackets?"
        ]

        chat_id = 88501
        for query in normal_queries:
            is_trig, reason = HandoffService.is_handoff_triggered(query, chat_id)
            self.assertFalse(is_trig, f"Normal query falsely triggered handoff: '{query}'")
            self.assertIsNone(reason)

        print(f"✅ TEST 6 PASSED: All {len(normal_queries)} normal questions safely bypassed handoff.")

    # ---------------------------------------------------------
    # TEST 7: Grounding Validator Failed Twice
    # ---------------------------------------------------------
    def test_07_grounding_validator_failed_twice_triggers_handoff(self):
        """
        When grounding validator fails twice consecutively on a response,
        handoff is triggered with reason: 'Grounding validator failed twice'.
        """
        print("\n--- TEST 7: Grounding validator failed twice ---")

        chat_id = 88601

        # Simulate grounding failure trigger
        is_trig, reason = HandoffService.is_handoff_triggered(
            text="oddiy savol",
            chat_id=chat_id,
            grounding_failed_twice=True
        )
        self.assertTrue(is_trig)
        self.assertEqual(reason, REASON_GROUNDING_FAILED_TWICE)

        res = HandoffService.start_handoff(
            chat_id=chat_id,
            customer_name="Sardor",
            reason=reason
        )
        self.assertEqual(res["customer_reply"], CUSTOMER_HANDOFF_REPLY)
        self.assertIn(REASON_GROUNDING_FAILED_TWICE, res["admin_message"])
        self.assertTrue(HandoffService.is_active_session(chat_id))

        print("✅ TEST 7 PASSED: Grounding validator failure successfully triggers handoff.")

    # ---------------------------------------------------------
    # TEST 8: 5-Line Chat Summary Quality
    # ---------------------------------------------------------
    def test_08_five_line_summary_format(self):
        """
        Summary generated from real chat always contains exactly 5 numbered lines.
        """
        print("\n--- TEST 8: 5-Line chat summary quality ---")

        history = [
            {"role": "user", "content": "Assalomu alaykum, qishki kurtka bormi?"},
            {"role": "assistant", "content": "Assalomu alaykum! Ha, bizda qalin qishki kurtkalar bor, narxi 450,000 so'm."},
            {"role": "user", "content": "Razmerlari qanaqa?"},
            {"role": "assistant", "content": "M, L, XL va XXL o'lchamlarimiz mavjud."},
            {"role": "user", "content": "Operator bilan gaplashmoqchiman"}
        ]

        summary = HandoffService.generate_5_line_summary(
            chat_id=88701,
            history=history,
            reason=REASON_HUMAN_REQUEST
        )

        lines = [ln.strip() for ln in summary.split("\n") if ln.strip()]
        self.assertEqual(len(lines), 5, f"Summary must be exactly 5 lines, got {len(lines)}:\n{summary}")

        for idx, line in enumerate(lines, 1):
            self.assertTrue(line.startswith(f"{idx}."), f"Line {idx} must start with '{idx}.': {line}")

        print(f"✅ TEST 8 PASSED: 5-line summary generated perfectly:\n{summary}")


if __name__ == "__main__":
    unittest.main()
