"""
tests/test_task3_order_state_machine.py
Comprehensive test suite for TASK 3: Order flow as a state machine.
Strictly follows RULES.md.

Tests:
1. Full happy path:
   Trigger -> size -> color -> quantity -> name -> phone -> address -> summary -> confirm -> done
2. Invalid phone:
   Rejects invalid formats, accepts valid UZ numbers (+998 and 9 digits), normalizes to +998XXXXXXXXX
3. Wrong size:
   Rejects unavailable size with polite message listing available sizes, accepts valid size
4. Cancel mid-flow:
   "bekor qilish" cancels order, clears state per chat_id in data/order_states.json
5. Edit address:
   "o'zgartirish" allows editing address mid-flow, rebuilds summary with updated address
6. Question mid-flow:
   Answers unrelated question mid-flow and resumes the field prompt without losing state
7. Duplicate confirm:
   Double-click / duplicate "ha" does not create two orders or double-decrement stock (idempotency)
8. Stock decrement:
   Verifies atomic stock decrement in both SQLite database and products.json
"""

import sys
import os
import json
import unittest
from pathlib import Path

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
from services.order_flow_service import (
    OrderFlowService,
    STATE_PRODUCT,
    STATE_SIZE,
    STATE_COLOR,
    STATE_QUANTITY,
    STATE_NAME,
    STATE_PHONE,
    STATE_ADDRESS,
    STATE_CONFIRM,
    STATE_DONE,
    ORDER_STATES_FILE,
    ORDERS_FILE,
    PRODUCTS_FILE
)
from services.catalog_service import load_products


class TestTask3OrderStateMachine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Backup order_states.json and orders.json if they exist
        self.states_backup = None
        if ORDER_STATES_FILE.exists():
            with open(ORDER_STATES_FILE, "r", encoding="utf-8") as f:
                self.states_backup = f.read()

        self.orders_backup = None
        if ORDERS_FILE.exists():
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                self.orders_backup = f.read()

        # Clean slate for each test
        with open(ORDER_STATES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

    def tearDown(self):
        # Restore backups
        if self.states_backup is not None:
            with open(ORDER_STATES_FILE, "w", encoding="utf-8") as f:
                f.write(self.states_backup)
        elif ORDER_STATES_FILE.exists():
            ORDER_STATES_FILE.unlink(missing_ok=True)

        if self.orders_backup is not None:
            with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                f.write(self.orders_backup)
        elif ORDERS_FILE.exists():
            ORDERS_FILE.unlink(missing_ok=True)

    # ---------------------------------------------------------
    # TEST 1: Full Happy Path
    # ---------------------------------------------------------
    def test_01_full_happy_path(self):
        """
        Full state sequence:
        product -> size -> color -> quantity -> name -> phone -> address -> summary -> confirm -> done
        """
        print("\n--- TEST 1: Full Happy Path ---")
        chat_id = 999001
        p1 = DatabaseManager.get_product_by_id(1)
        self.assertIsNotNone(p1, "Product #1 must exist")

        # 1. Trigger flow
        self.assertTrue(OrderFlowService.is_buy_intent("bu futbolkani olaman"))
        flow = OrderFlowService.start_order_flow(
            chat_id=chat_id,
            initial_product=p1,
            initial_text="bu futbolkani olaman"
        )
        self.assertTrue(OrderFlowService.has_active_flow(chat_id))

        # Maydonlarni bosqichma-bosqich yuborish
        # Agar tovarning o'lchami so'ralsa:
        curr_state = flow["state"]
        if curr_state == STATE_SIZE:
            res = OrderFlowService.process_step(chat_id, "XXL")
            curr_state = res["state"]

        if curr_state == STATE_COLOR:
            res = OrderFlowService.process_step(chat_id, "ko'k")
            curr_state = res["state"]

        if curr_state == STATE_QUANTITY:
            res = OrderFlowService.process_step(chat_id, "2")
            curr_state = res["state"]

        if curr_state == STATE_NAME:
            res = OrderFlowService.process_step(chat_id, "Mansur")
            curr_state = res["state"]

        if curr_state == STATE_PHONE:
            res = OrderFlowService.process_step(chat_id, "+998901234567")
            curr_state = res["state"]

        if curr_state == STATE_ADDRESS:
            res = OrderFlowService.process_step(chat_id, "Navoiy ko'chasi 15")
            curr_state = res["state"]

        # Summary / Confirm bosqichi
        self.assertEqual(curr_state, STATE_CONFIRM)
        self.assertIn("Buyurtma xulosasi", res["reply"])
        self.assertIn("Mansur", res["reply"])
        self.assertIn("+998901234567", res["reply"])
        self.assertIn("Navoiy ko'chasi 15", res["reply"])
        self.assertIn("2 dona", res["reply"])

        # Tasdiqlash: "ha"
        confirm_res = OrderFlowService.process_step(chat_id, "ha")
        self.assertTrue(confirm_res["is_completed"])
        self.assertEqual(confirm_res["state"], STATE_DONE)
        self.assertIsNotNone(confirm_res["order_id"])
        self.assertTrue(confirm_res["order_id"].startswith("ORD-"))
        self.assertIn("Buyurtmangiz muvaffaqiyatli qabul qilindi", confirm_res["reply"])

        # data/orders.json da saqlanganini tekshirish
        orders = OrderFlowService._load_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["order_id"], confirm_res["order_id"])
        self.assertEqual(orders[0]["customer_name"], "Mansur")
        self.assertEqual(orders[0]["customer_phone"], "+998901234567")
        self.assertEqual(orders[0]["delivery_address"], "Navoiy ko'chasi 15")
        self.assertEqual(orders[0]["items"][0]["quantity"], 2)

        print(f"✅ TEST 1 PASSED: Happy path completed with order {confirm_res['order_id']}")

    # ---------------------------------------------------------
    # TEST 2: Invalid Phone Validation
    # ---------------------------------------------------------
    def test_02_invalid_phone_validation(self):
        """
        Validate in code: phone must be a valid Uzbekistan number (+998 and 9 digits).
        Accepts 90 123 45 67 / 998901234567 formats, normalizes to +998XXXXXXXXX.
        Re-asks politely on invalid input.
        """
        print("\n--- TEST 2: Invalid Phone Validation ---")
        chat_id = 999002
        p1 = DatabaseManager.get_product_by_id(1)

        # Normalization unit checks
        self.assertEqual(OrderFlowService.validate_and_normalize_phone("90 123 45 67"), "+998901234567")
        self.assertEqual(OrderFlowService.validate_and_normalize_phone("998901234567"), "+998901234567")
        self.assertEqual(OrderFlowService.validate_and_normalize_phone("+998901234567"), "+998901234567")
        self.assertEqual(OrderFlowService.validate_and_normalize_phone("901234567"), "+998901234567")
        self.assertIsNone(OrderFlowService.validate_and_normalize_phone("12345"))
        self.assertIsNone(OrderFlowService.validate_and_normalize_phone("+15551234567"))
        self.assertIsNone(OrderFlowService.validate_and_normalize_phone("salom"))

        # State machine flow test at phone step
        session = {
            "chat_id": chat_id,
            "state": STATE_PHONE,
            "data": {
                "product_id": 1,
                "product_name": p1["name"],
                "unit_price": p1["sale_price"],
                "size": "XXL",
                "color": "ko'k",
                "quantity": 1,
                "name": "Alisher"
            },
            "editing_field": None,
            "is_confirmed": False,
            "order_id": None
        }
        OrderFlowService._save_session(session)

        # 1. Yaroqsiz raqam yuborish
        res_bad = OrderFlowService.process_step(chat_id, "12345")
        self.assertEqual(res_bad["state"], STATE_PHONE)
        self.assertIn("to'g'ri formatda", res_bad["reply"])

        # 2. To'g'ri raqam mahalliy formatda (90 123 45 67)
        res_good = OrderFlowService.process_step(chat_id, "90 123 45 67")
        self.assertEqual(res_good["state"], STATE_ADDRESS)
        sess_updated = OrderFlowService.get_session(chat_id)
        self.assertEqual(sess_updated["data"]["phone"], "+998901234567")

        print("✅ TEST 2 PASSED: Invalid phone rejected politely; normalized to +998901234567.")

    # ---------------------------------------------------------
    # TEST 3: Wrong Size Validation
    # ---------------------------------------------------------
    def test_03_wrong_size_validation(self):
        """
        Size/color must exist for that product and be in stock.
        Re-ask politely on invalid input.
        """
        print("\n--- TEST 3: Wrong Size Validation ---")
        chat_id = 999003
        p1 = DatabaseManager.get_product_by_id(1)

        avail_sizes = OrderFlowService.get_available_sizes(p1)
        print(f"Product #1 available sizes: {avail_sizes}")

        # Start session at size step
        session = {
            "chat_id": chat_id,
            "state": STATE_SIZE,
            "data": {
                "product_id": 1,
                "product_name": p1["name"],
                "unit_price": p1["sale_price"]
            },
            "editing_field": None,
            "is_confirmed": False,
            "order_id": None
        }
        OrderFlowService._save_session(session)

        # 1. Noto'g'ri razmer kiritish ("XXXL")
        res_wrong = OrderFlowService.process_step(chat_id, "XXXL")
        self.assertEqual(res_wrong["state"], STATE_SIZE)
        self.assertIn("mavjud emas", res_wrong["reply"])
        self.assertIn("Mavjud o'lchamlar", res_wrong["reply"])

        # 2. To'g'ri razmer kiritish ("XXL")
        res_correct = OrderFlowService.process_step(chat_id, "XXL")
        self.assertNotEqual(res_correct["state"], STATE_SIZE)
        sess_updated = OrderFlowService.get_session(chat_id)
        self.assertEqual(sess_updated["data"]["size"], "XXL")

        print("✅ TEST 3 PASSED: Wrong size rejected politely with available options, valid size accepted.")

    # ---------------------------------------------------------
    # TEST 4: Cancel Mid-Flow
    # ---------------------------------------------------------
    def test_04_cancel_mid_flow(self):
        """
        Customer can say 'bekor qilish' at any step: cancel the flow immediately.
        Clears session from data/order_states.json.
        """
        print("\n--- TEST 4: Cancel Mid-Flow ---")
        chat_id = 999004
        p1 = DatabaseManager.get_product_by_id(1)

        flow = OrderFlowService.start_order_flow(chat_id, initial_product=p1)
        self.assertTrue(OrderFlowService.has_active_flow(chat_id))

        # Mid-flow cancel
        res_cancel = OrderFlowService.process_step(chat_id, "bekor qilish")
        self.assertIn("bekor qilindi", res_cancel["reply"])
        self.assertFalse(OrderFlowService.has_active_flow(chat_id))
        self.assertIsNone(OrderFlowService.get_session(chat_id))

        print("✅ TEST 4 PASSED: Mid-flow cancellation cleared state immediately.")

    # ---------------------------------------------------------
    # TEST 5: Edit Address
    # ---------------------------------------------------------
    def test_05_edit_address(self):
        """
        Customer can say 'o'zgartirish' or 'manzilni o'zgartirish' at any step to edit.
        """
        print("\n--- TEST 5: Edit Address ---")
        chat_id = 999005
        p1 = DatabaseManager.get_product_by_id(1)

        # Set session to confirm step with initial address
        session = {
            "chat_id": chat_id,
            "state": STATE_CONFIRM,
            "data": {
                "product_id": 1,
                "product_name": p1["name"],
                "unit_price": p1["sale_price"],
                "size": "XXL",
                "color": "ko'k",
                "quantity": 1,
                "name": "Bekzod",
                "phone": "+998901234567",
                "address": "Eski manzil ko'chasi 1"
            },
            "editing_field": None,
            "is_confirmed": False,
            "order_id": None
        }
        OrderFlowService._save_session(session)

        # 1. Customer asks to edit address
        res_edit_prompt = OrderFlowService.process_step(chat_id, "manzilni o'zgartirish")
        self.assertIn("manzilini yozib yuboring", res_edit_prompt["reply"])

        # 2. Customer provides new address
        res_updated = OrderFlowService.process_step(chat_id, "Samarqand shahar, Registon 5")
        self.assertEqual(res_updated["state"], STATE_CONFIRM)
        self.assertIn("Samarqand shahar, Registon 5", res_updated["reply"])
        self.assertIn("Ma'lumot yangilandi", res_updated["reply"])

        sess_updated = OrderFlowService.get_session(chat_id)
        self.assertEqual(sess_updated["data"]["address"], "Samarqand shahar, Registon 5")

        print("✅ TEST 5 PASSED: Address edited mid-flow and summary updated.")

    # ---------------------------------------------------------
    # TEST 6: Question Mid-Flow
    # ---------------------------------------------------------
    def test_06_question_mid_flow(self):
        """
        Any unrelated question mid-flow is answered, then the flow resumes.
        """
        print("\n--- TEST 6: Question Mid-Flow ---")
        chat_id = 999006
        p1 = DatabaseManager.get_product_by_id(1)

        session = {
            "chat_id": chat_id,
            "state": STATE_ADDRESS,
            "data": {
                "product_id": 1,
                "product_name": p1["name"],
                "unit_price": p1["sale_price"],
                "size": "XXL",
                "color": "ko'k",
                "quantity": 1,
                "name": "Nodir",
                "phone": "+998901234567"
            },
            "editing_field": None,
            "is_confirmed": False,
            "order_id": None
        }
        OrderFlowService._save_session(session)

        # Foydalanuvchi manzil o'rniga yetkazib berish haqida savol beradi
        res_q = OrderFlowService.process_step(
            chat_id=chat_id,
            text="Dostavka qancha vaqtda keladi va bepulmi?",
            ai_answer_fn=lambda q: "Yetkazib berish Ingichka bo'ylab mutlaqo bepul va 1 kun ichida yetkaziladi."
        )

        # 1. Savolga javob berilgan bo'lishi kerak
        self.assertIn("bepul", res_q["reply"].lower())
        # 2. Oqim davom etayotganini va manzil so'ralayotganini eslatishi kerak
        self.assertIn("davom ettiramiz", res_q["reply"].lower())
        self.assertIn("manzil", res_q["reply"].lower())
        # 3. Holat o'zgarmasdan ADDRESS bo'lib turishi kerak
        self.assertEqual(res_q["state"], STATE_ADDRESS)

        # Endi xaridor manzilni yuboradi
        res_addr = OrderFlowService.process_step(chat_id, "Navoiy 24-uy")
        self.assertEqual(res_addr["state"], STATE_CONFIRM)
        self.assertIn("Navoiy 24-uy", res_addr["reply"])

        print("✅ TEST 6 PASSED: Mid-flow question answered and state preserved.")

    # ---------------------------------------------------------
    # TEST 7: Duplicate Confirm (Idempotency)
    # ---------------------------------------------------------
    def test_07_duplicate_confirm_idempotency(self):
        """
        Double-click/duplicate confirm must not create two orders (idempotency).
        """
        print("\n--- TEST 7: Duplicate Confirm Idempotency ---")
        chat_id = 999007
        p1 = DatabaseManager.get_product_by_id(1)
        initial_stock = p1["stock_quantity"]

        session = {
            "chat_id": chat_id,
            "state": STATE_CONFIRM,
            "data": {
                "product_id": 1,
                "product_name": p1["name"],
                "unit_price": p1["sale_price"],
                "size": "XXL",
                "color": "ko'k",
                "quantity": 1,
                "name": "Rustam",
                "phone": "+998901234567",
                "address": "Mustaqillik 10"
            },
            "editing_field": None,
            "is_confirmed": False,
            "order_id": None
        }
        OrderFlowService._save_session(session)

        # Birinchi marta tasdiqlash
        res1 = OrderFlowService.process_step(chat_id, "ha")
        self.assertTrue(res1["is_completed"])
        order_id_1 = res1["order_id"]
        self.assertIsNotNone(order_id_1)

        orders_1 = OrderFlowService._load_orders()
        self.assertEqual(len(orders_1), 1)

        p1_after1 = DatabaseManager.get_product_by_id(1)
        self.assertEqual(p1_after1["stock_quantity"], initial_stock - 1)

        # Ikkinchi marta takroriy tasdiqlash (Double-click / duplicate)
        res2 = OrderFlowService.process_step(chat_id, "ha")
        self.assertTrue(res2["is_completed"])
        self.assertEqual(res2["order_id"], order_id_1)
        self.assertIn("allaqachon qabul qilingan", res2["reply"])

        # Qayta zakaz yaratilmaganini tekshirish
        orders_2 = OrderFlowService._load_orders()
        self.assertEqual(len(orders_2), 1, "Must NOT create duplicate order in orders.json")

        # Qoldiq yana kamayib ketmaganini tekshirish
        p1_after2 = DatabaseManager.get_product_by_id(1)
        self.assertEqual(p1_after2["stock_quantity"], initial_stock - 1, "Must NOT decrement stock twice")

        print(f"✅ TEST 7 PASSED: Idempotency enforced. Single order {order_id_1}, single stock decrement.")

    # ---------------------------------------------------------
    # TEST 8: Stock Decrement
    # ---------------------------------------------------------
    def test_08_stock_decrement(self):
        """
        Verify stock decrement in both SQLite and products.json atomically.
        """
        print("\n--- TEST 8: Stock Decrement ---")
        chat_id = 999008
        p2 = DatabaseManager.get_product_by_id(2)
        initial_db_stock = p2["stock_quantity"]

        # products.json dagi boshlang'ich stock
        prods = load_products()
        p2_json = next(p for p in prods if p["id"] == 2)
        initial_json_stock = p2_json["stock"]

        order_qty = 2

        session = {
            "chat_id": chat_id,
            "state": STATE_CONFIRM,
            "data": {
                "product_id": 2,
                "product_name": p2["name"],
                "unit_price": p2["sale_price"],
                "size": "L",
                "color": "ko'k",
                "quantity": order_qty,
                "name": "Ziyodulla",
                "phone": "+998901234567",
                "address": "Ingichka markazi"
            },
            "editing_field": None,
            "is_confirmed": False,
            "order_id": None
        }
        OrderFlowService._save_session(session)

        # Tasdiqlash
        confirm_res = OrderFlowService.process_step(chat_id, "tasdiqlayman")
        self.assertTrue(confirm_res["is_completed"])

        # 1. SQLite qoldig'i tekshiruvi
        p2_updated = DatabaseManager.get_product_by_id(2)
        self.assertEqual(p2_updated["stock_quantity"], initial_db_stock - order_qty)

        # 2. products.json qoldig'i tekshiruvi
        prods_updated = load_products()
        p2_json_updated = next(p for p in prods_updated if p["id"] == 2)
        self.assertEqual(p2_json_updated["stock"], initial_json_stock - order_qty)

        print(f"✅ TEST 8 PASSED: Stock decremented by {order_qty} in SQLite ({initial_db_stock} -> {p2_updated['stock_quantity']}) and products.json ({initial_json_stock} -> {p2_json_updated['stock']}).")


if __name__ == "__main__":
    unittest.main()
