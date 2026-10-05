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


if __name__ == "__main__":
    unittest.main()
