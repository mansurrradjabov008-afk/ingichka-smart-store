"""
tests/test_real_photo_presentation.py
Verification suite for instant real product photo presentation and zero-hallucination catalog intelligence.
"""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.enums import ChatType

from services.order_matcher import OrderMatcher
from database.db_manager import DatabaseManager, init_db


class TestRealPhotoPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_multi_factor_ranked_queries(self):
        """Tovar nomi, rangi, brendi va toifasi bo'yicha aniq reyting tekshiruvi"""
        # 1. Boss vitrofka
        boss = OrderMatcher.match_products_multi("Boss vitrofka rasmini tashla")
        self.assertTrue(len(boss) >= 1)
        self.assertEqual(boss[0]["id"], 31)
        self.assertIn("Boss", boss[0]["name"])

        # 2. Qora vitrofka
        black_j = OrderMatcher.match_products_multi("qora vitrofka rasmini tashla")
        self.assertTrue(len(black_j) >= 1)
        self.assertIn(black_j[0]["id"], [17, 18, 29])
        self.assertIn("qora", black_j[0]["name"].lower() + " " + black_j[0]["color"].lower())

        # 3. Tonika
        tonika = OrderMatcher.match_products_multi("tonika rasmini tashla")
        self.assertTrue(len(tonika) >= 1)
        self.assertIn(tonika[0]["id"], [27, 28])
        self.assertIn("tonika", tonika[0]["name"].lower())

        # 4. Xudi svitir
        hoodie = OrderMatcher.match_products_multi("xudi svitir rasmini tashla")
        self.assertTrue(len(hoodie) >= 1)
        self.assertEqual(hoodie[0]["id"], 35)
        self.assertIn("xudi", hoodie[0]["name"].lower())

        # 5. Qizlar krossovkasi vs O'g'il bolalar krossovkasi
        girl_shoes = OrderMatcher.match_products_multi("qizlar krasovkasi rasmini tashla")
        self.assertTrue(len(girl_shoes) >= 1)
        self.assertEqual(girl_shoes[0]["id"], 41)
        self.assertIn("qiz", girl_shoes[0]["name"].lower())

        boy_shoes = OrderMatcher.match_products_multi("ogil bolalar krasovkasi rasmini tashla")
        self.assertTrue(len(boy_shoes) >= 1)
        self.assertEqual(boy_shoes[0]["id"], 40)
        self.assertIn("o'g'il", boy_shoes[0]["name"].lower())

    def test_flagship_and_video_triggers(self):
        """Videodagi yoki kanaldagi tovarlar rasmi so'ralganda saralangan flagman tovarlar chiqishi"""
        video_res = OrderMatcher.match_products_multi("videodagi kiyim rasmini tashla")
        self.assertTrue(len(video_res) >= 2)
        v_ids = [p["id"] for p in video_res]
        self.assertTrue(any(pid in [1, 4, 17, 40] for pid in v_ids))

        channel_res = OrderMatcher.match_products_multi("dukon kanalidagi kiyim rasmini tashla")
        self.assertTrue(len(channel_res) >= 2)
        c_ids = [p["id"] for p in channel_res]
        self.assertTrue(any(pid in [1, 4, 17, 40] for pid in c_ids))

    def test_contextual_pending_and_history_photo_queries(self):
        """Mijoz 'rasmini tashla' yoki 'buni ko'rsat' deganda kontekstdagi tovar rasmi chiqishi"""
        pending = {"id": 16, "name": "Erkaklar kapyushonli moviy vitrofka", "sale_price": 140000, "image_url": "http://img.test"}
        res = OrderMatcher.match_products_multi("rasmini tashlang", pending_product=pending)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], 16)

        history = [
            {"role": "user", "content": "Polo svitir bormi?"},
            {"role": "assistant", "content": "Ha, bizda #4 Polo erkaklar svitir kofta mavjud, narxi 75,000 so'm"}
        ]
        res_hist = OrderMatcher.match_products_multi("buni rasmini ko'raylik", history=history)
        self.assertEqual(len(res_hist), 1)
        self.assertEqual(res_hist[0]["id"], 4)

    def test_handle_private_chat_triggers_presentation(self):
        """Shaxsiy chatda tovar so'ralganda foto taqdimot va sotuvchi maslahati chaqirilishi"""
        from bot.bot_app import handle_private_chat, bot

        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=881234, type=ChatType.PRIVATE)
        mock_msg.from_user = MagicMock(id=881234, full_name="Mansur", first_name="Mansur", username="mansur")
        mock_msg.text = "Boss vitrofka rasmini tashlang"
        mock_msg.caption = None
        mock_msg.reply_to_message = None

        sent_messages = []
        async def fake_safe_send(chat_id, text, reply_markup=None, **kwargs):
            sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
            return True

        photo_presentations = []
        async def fake_send_product_presentation(bot, chat_id, products, **kwargs):
            photo_presentations.append({"chat_id": chat_id, "products": products})
            return True

        mock_bot_info = MagicMock(username="Markazsavdo00_bot", id=8663033870)
        with patch("bot.bot_app.safe_send", side_effect=fake_safe_send), \
             patch("bot.bot_app.send_product_presentation", side_effect=fake_send_product_presentation), \
             patch.object(bot, "send_chat_action", new_callable=AsyncMock), \
             patch.object(bot, "get_me", new_callable=AsyncMock, return_value=mock_bot_info):
            asyncio.run(handle_private_chat(mock_msg))

        self.assertTrue(len(photo_presentations) >= 1)
        first_pres = photo_presentations[0]
        self.assertEqual(first_pres["products"][0]["id"], 31)
        self.assertIn("Boss", first_pres["products"][0]["name"])


if __name__ == "__main__":
    unittest.main()
