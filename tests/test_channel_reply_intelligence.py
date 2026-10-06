import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.enums import ChatType
from database.db_manager import DatabaseManager
from services.order_matcher import OrderMatcher, normalize_uzbek_word


class TestChannelReplyIntelligence(unittest.TestCase):
    def setUp(self):
        self.c1_post_caption = (
            "Qiz bolachalarga Xitoy krasofkacha\n"
            "Razmer 26 27 28 29 30 31 32 33 34 35 36 37\n"
            "Narxi 110.000"
        )
        self.c2_post_caption = (
            "Ogil bolachalarga pijama\n"
            "Qora va Yashil ranglari keldi\n"
            "Razmer 3 4 5 6 7 8 yoshgacha\n"
            "Narxi 85.000"
        )

    def test_uzbek_word_normalization(self):
        """O'zbekcha so'z shakllari va shevalar to'g'ri normallashishi kerak"""
        self.assertEqual(normalize_uzbek_word("krasofkacha"), "krossovka")
        self.assertEqual(normalize_uzbek_word("krasovka"), "krossovka")
        self.assertEqual(normalize_uzbek_word("krosovka"), "krossovka")
        self.assertEqual(normalize_uzbek_word("bolachalarga"), "bolalar")
        self.assertEqual(normalize_uzbek_word("bolalarga"), "bolalar")
        self.assertEqual(normalize_uzbek_word("qizchalarga"), "qiz")
        self.assertEqual(normalize_uzbek_word("ogil"), "o'g'il")
        self.assertEqual(normalize_uzbek_word("pijamacha"), "pijama")

    def test_exact_channel_post_matching(self):
        """Kanal postlari aniq o'zining tovariga 100% mos kelishi shart"""
        # 1. Qizlar krasovkasi posti
        p1 = OrderMatcher.match_product(self.c1_post_caption)
        self.assertIsNotNone(p1)
        self.assertEqual(p1["id"], 41)
        self.assertEqual(p1["name"], "Qiz bolalar Xitoy krossovka")
        self.assertEqual(p1["category"], "Oyoq kiyim")

        # 2. O'g'il bolalar pijamasi posti
        p2 = OrderMatcher.match_product(self.c2_post_caption)
        self.assertIsNotNone(p2)
        self.assertEqual(p2["id"], 39)
        self.assertEqual(p2["name"], "O'g'il bolalar uchun pijama komplekt")
        self.assertEqual(p2["category"], "Pijama")

    def test_gender_distinction_no_mixup(self):
        """O'g'il va qiz bolalar tovarlari aralashib ketmasligi shart"""
        p_girl = OrderMatcher.match_product("qiz bolalarga krasovka bormi")
        self.assertIsNotNone(p_girl)
        self.assertEqual(p_girl["id"], 41)
        self.assertIn("qiz", p_girl["name"].lower())

        p_boy = OrderMatcher.match_product("o'g'il bolalarga krasovka bormi")
        self.assertIsNotNone(p_boy)
        self.assertEqual(p_boy["id"], 40)
        self.assertIn("o'g'il", p_boy["name"].lower())

    def test_handle_group_message_c1_girls_shoes_reply(self):
        """Guruhda qizlar krossovkasi posti ostida so'ralganda to'g'ri tovar kartasi va tugma berilishi"""
        from bot.bot_app import handle_group_message, bot

        # Mock reply_to_message (kanal posti)
        mock_reply_post = MagicMock(spec=types.Message)
        mock_reply_post.caption = self.c1_post_caption
        mock_reply_post.text = None
        mock_reply_post.is_automatic_forward = True
        mock_reply_post.sender_chat = MagicMock(id=-1001234567, title="MarkazSavdo Kanal")
        mock_reply_post.from_user = None

        # Mock foydalanuvchi xabari
        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=-1009876543, type=ChatType.SUPERGROUP)
        mock_msg.from_user = MagicMock(id=999888, first_name="Alisher", is_bot=False)
        mock_msg.text = "Bu krasovka xaqida tuliq malumot bera olasizmi"
        mock_msg.caption = None
        mock_msg.reply_to_message = mock_reply_post
        mock_msg.is_automatic_forward = False
        mock_msg.sender_chat = None

        sent_messages = []
        async def fake_safe_send(chat_id, text, reply_markup=None, **kwargs):
            sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
            return True

        mock_bot_info = MagicMock(username="Markazsavdo00_bot", id=8663033870)
        with patch("bot.bot_app.safe_send", side_effect=fake_safe_send), \
             patch.object(bot, "send_chat_action", new_callable=AsyncMock), \
             patch.object(bot, "get_me", new_callable=AsyncMock, return_value=mock_bot_info):
            asyncio.run(handle_group_message(mock_msg))

        self.assertEqual(len(sent_messages), 1)
        resp = sent_messages[0]
        text = resp["text"]
        kb = resp["reply_markup"]

        # Tekshiruvlar:
        self.assertIn("Qiz bolalar Xitoy krossovka", text)
        self.assertIn("85,000 so'm", text)
        self.assertIn("26, 27, 28, 29, 30, 31", text)
        self.assertNotIn("Afsuski, rasmni ko'rolmayapman", text)
        self.assertNotIn("O'g'il bolalar Xitoy krossovka", text)

        # 1-bosishda xarid tugmasi
        self.assertIsNotNone(kb)
        btn = kb.inline_keyboard[0][0]
        self.assertIn("start=buy_41", btn.url)

    def test_handle_group_message_c2_pajamas_reply(self):
        """Guruhda pijama posti ostida 'Bu rasmdagi kiyim haqida' deb so'ralganda to'g'ri javob"""
        from bot.bot_app import handle_group_message, bot

        mock_reply_post = MagicMock(spec=types.Message)
        mock_reply_post.caption = self.c2_post_caption
        mock_reply_post.text = None
        mock_reply_post.is_automatic_forward = True
        mock_reply_post.sender_chat = MagicMock(id=-1001234567, title="MarkazSavdo Kanal")
        mock_reply_post.from_user = None

        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=-1009876543, type=ChatType.SUPERGROUP)
        mock_msg.from_user = MagicMock(id=999888, first_name="Nodira", is_bot=False)
        mock_msg.text = "Bu rasmdagi kiyim xaqida malumot bera olasizmi"
        mock_msg.caption = None
        mock_msg.reply_to_message = mock_reply_post
        mock_msg.is_automatic_forward = False
        mock_msg.sender_chat = None

        sent_messages = []
        async def fake_safe_send(chat_id, text, reply_markup=None, **kwargs):
            sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
            return True

        mock_bot_info = MagicMock(username="Markazsavdo00_bot", id=8663033870)
        with patch("bot.bot_app.safe_send", side_effect=fake_safe_send), \
             patch.object(bot, "send_chat_action", new_callable=AsyncMock), \
             patch.object(bot, "get_me", new_callable=AsyncMock, return_value=mock_bot_info):
            asyncio.run(handle_group_message(mock_msg))

        self.assertEqual(len(sent_messages), 1)
        resp = sent_messages[0]
        text = resp["text"]
        kb = resp["reply_markup"]

        # Hech qachon 'rasmni ko'rolmayapman' demasligi kerak!
        self.assertNotIn("Afsuski, rasmni ko'rolmayapman", text)
        self.assertIn("O'g'il bolalar uchun pijama komplekt", text)
        self.assertIn("30,000 so'm", text)
        self.assertIn("4-7 yosh", text)

        # 1-bosishda xarid tugmasi
        self.assertIsNotNone(kb)
        btn = kb.inline_keyboard[0][0]
        self.assertIn("start=buy_39", btn.url)

    def test_handle_group_message_standalone_jackets_inquiry(self):
        """Guruhda postga replies bo'lmagan mustaqil savol: 'erkaklar kurtkalarini kursata olasizmi'
        20 yillik konsultativ javob, mahsulotlar taqdimoti va xom HTML teglarsiz toza chiqishi kerak"""
        from bot.bot_app import handle_group_message, bot

        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=-1009876543, type=ChatType.SUPERGROUP)
        mock_msg.from_user = MagicMock(id=999888, first_name="Mansur", is_bot=False)
        mock_msg.text = "erkaklar kurtkalarini kursata olasizmi"
        mock_msg.caption = None
        mock_msg.reply_to_message = None
        mock_msg.is_automatic_forward = False
        mock_msg.sender_chat = None

        sent_messages = []
        async def fake_safe_send(chat_id, text, reply_markup=None, **kwargs):
            sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
            return True

        presented_products = []
        presented_kbs = []
        async def fake_presentation(bot, chat_id, products, reply_markup=None, **kwargs):
            presented_products.extend(products)
            presented_kbs.append(reply_markup)
            return True

        mock_bot_info = MagicMock(username="Markazsavdo00_bot", id=8663033870)
        with patch("bot.bot_app.safe_send", side_effect=fake_safe_send), \
             patch("bot.bot_app.send_product_presentation", side_effect=fake_presentation), \
             patch.object(bot, "send_chat_action", new_callable=AsyncMock), \
             patch.object(bot, "get_me", new_callable=AsyncMock, return_value=mock_bot_info):
            asyncio.run(handle_group_message(mock_msg))

        # 1. Taqdimot chaqirilganini va erkaklar kurtkalari (15, 16, 17) uzatilganini tekshirish
        self.assertGreaterEqual(len(presented_products), 1, "Kamida 1 ta kurtka taqdim etilishi shart")
        p_ids = [p["id"] for p in presented_products]
        self.assertIn(15, p_ids, "#15 kulrang vitrofka kurtka bo'lishi shart")

        # 2. Xarid tugmalari va linklar mavjudligi
        self.assertGreaterEqual(len(presented_kbs), 1)
        kb = presented_kbs[0]
        self.assertIsNotNone(kb)
        has_buy_link = any(
            any("start=buy_" in getattr(btn, "url", "") for btn in row)
            for row in kb.inline_keyboard
        )
        self.assertTrue(has_buy_link, "Guruh xarid tugmalarida start=buy_ linki bo'lishi shart")

        # 3. Xabarlarning birontasida xom HTML teglari (<b>, <i>) chiqmasligi shart!
        for sm in sent_messages:
            msg_text = sm.get("text", "")
            self.assertNotIn("<b>", msg_text, "Xabarda xom <b> tegi chiqishi mumkin emas!")
            self.assertNotIn("<i>", msg_text, "Xabarda xom <i> tegi chiqishi mumkin emas!")

    def test_safe_send_html_and_markdown_safety(self):
        """safe_send HTML va Markdown formatlarini to'g'ri aniqlashi va xatolikda teglarni tozalashi kerak"""
        from bot.bot_app import safe_send, bot
        from aiogram.exceptions import TelegramBadRequest

        sent_calls = []
        async def mock_send(chat_id, text, parse_mode=None, reply_markup=None):
            sent_calls.append({"text": text, "parse_mode": parse_mode})
            if "FAIL_MD" in text and parse_mode == "Markdown":
                raise TelegramBadRequest(method=MagicMock(), message="Can't parse entities in Markdown")
            return MagicMock()

        with patch.object(bot, "send_message", side_effect=mock_send):
            # 1. HTML teglari bo'lgan matn -> parse_mode="HTML" orqali ketishi kerak
            asyncio.run(safe_send(12345, "✨ <b>Qizlar krossovkasi</b>\nNarxi: 85,000 so'm"))
            self.assertEqual(sent_calls[-1]["parse_mode"], "HTML")
            self.assertIn("<b>Qizlar krossovkasi</b>", sent_calls[-1]["text"])

            # 2. Markdown matn -> parse_mode="Markdown" orqali ketishi kerak
            asyncio.run(safe_send(12345, "✨ **Erkaklar kurtkasi**\nNarxi: 100,000 so'm"))
            self.assertEqual(sent_calls[-1]["parse_mode"], "Markdown")

            # 3. Buzilgan Markdown matn -> TelegramBadRequest bo'lganda teglarni tozalab plain text yuborishi kerak
            asyncio.run(safe_send(12345, "✨ **FAIL_MD kurtka** [test link"))
            self.assertIsNone(sent_calls[-1]["parse_mode"])
            self.assertNotIn("**", sent_calls[-1]["text"])


    def test_group_multiturn_dialogue_pajamas_color_followup(self):
        """Guruhda 2-bosqichli suhbat:
        Turn 1: 'Uglimga pijama olmoqchi edim qanqa ranglari bor'
        Turn 2: 'Menga qora rangini kursata olasizmi'
        Bot jim qolmasligi, #39 bolalar pijamasini tanishi va rasmli taqdimot berishi shart!"""
        from bot.bot_app import handle_group_message, bot, ACTIVE_GROUP_SESSIONS
        from ai_engine.ai_brain import ai_brain

        chat_id = -10077665544
        user_id = 11223344

        # Clear active sessions & brain conversations for clean test
        ACTIVE_GROUP_SESSIONS.clear()
        ai_brain.conversations[chat_id] = []

        sent_messages = []
        async def fake_safe_send(cid, text, reply_markup=None, **kwargs):
            sent_messages.append({"chat_id": cid, "text": text, "reply_markup": reply_markup})
            return True

        presented_products = []
        async def fake_presentation(bot, chat_id, products, reply_markup=None, **kwargs):
            presented_products.extend(products)
            return True

        mock_bot_info = MagicMock(username="Markazsavdo00_bot", id=8663033870)

        with patch("bot.bot_app.safe_send", side_effect=fake_safe_send), \
             patch("bot.bot_app.send_product_presentation", side_effect=fake_presentation), \
             patch.object(bot, "send_chat_action", new_callable=AsyncMock), \
             patch.object(bot, "get_me", new_callable=AsyncMock, return_value=mock_bot_info):

            # --- TURN 1 ---
            msg1 = MagicMock(spec=types.Message)
            msg1.chat = MagicMock(id=chat_id, type=ChatType.SUPERGROUP)
            msg1.from_user = MagicMock(id=user_id, first_name="Dildora", is_bot=False)
            msg1.text = "Uglimga pijama olmoqchi edim qanqa ranglari bor"
            msg1.caption = None
            msg1.reply_to_message = None
            msg1.is_automatic_forward = False
            msg1.sender_chat = None

            asyncio.run(handle_group_message(msg1))

            self.assertIn((chat_id, user_id), ACTIVE_GROUP_SESSIONS, "Aktiv sessiya saqlanishi shart!")
            self.assertGreaterEqual(len(presented_products), 1, "Turn 1 da pijama taqdim etilishi kerak")
            p1_ids = [p["id"] for p in presented_products]
            self.assertIn(39, p1_ids, "Turn 1 da #39 o'g'il bolalar pijamasi chiqishi shart")

            # --- TURN 2: Follow-up rang so'rovi ---
            presented_products.clear()
            sent_messages.clear()

            msg2 = MagicMock(spec=types.Message)
            msg2.chat = MagicMock(id=chat_id, type=ChatType.SUPERGROUP)
            msg2.from_user = MagicMock(id=user_id, first_name="Dildora", is_bot=False)
            msg2.text = "Menga qora rangini kursata olasizmi"
            msg2.caption = None
            msg2.reply_to_message = None
            msg2.is_automatic_forward = False
            msg2.sender_chat = None

            asyncio.run(handle_group_message(msg2))

            # Bot mutlaqo JIM QOLMASLIGI kerak!
            self.assertTrue(len(sent_messages) > 0 or len(presented_products) > 0, "Bot follow-up savolga aslo jim qolmasligi shart!")

            # Taqdim etilgan tovar #39 (pijama) bo'lishi kerak, #7 (svitir) EMAS!
            self.assertGreaterEqual(len(presented_products), 1, "Turn 2 da mahsulot taqdimoti chaqirilishi shart")
            p2_ids = [p["id"] for p in presented_products]
            self.assertIn(39, p2_ids, "Turn 2 da #39 bolalar pijamasi ko'rsatilishi shart! Begona tovar (#7 svitir) bo'lmasligi kerak!")
            self.assertNotIn(7, p2_ids, "Svitir (#7) ko'rsatilishi mutlaqo taqiqlanadi!")

            # Hech qanday 'rasmni ko'rsata olmayman' uzri bo'lmasligi kerak
            for sm in sent_messages:
                txt = sm.get("text", "")
                self.assertNotIn("rasmni ko'rsata olmayman", txt)
                self.assertNotIn("rasmlarni to'g'ridan-to'g'ri ko'rsata olmayman", txt)


if __name__ == "__main__":
    unittest.main()


