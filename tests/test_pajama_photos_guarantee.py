"""
tests/test_pajama_photos_guarantee.py
Verification test to guarantee pajamas and all catalog items receive real photos
without falling back to text when live images are available.
"""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.enums import ChatType

from services.order_matcher import OrderMatcher
from services.media_service import send_product_presentation, fetch_image_bytes
from database.db_manager import DatabaseManager, init_db


class TestPajamaPhotosGuarantee(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_pajama_matching_accuracy(self):
        """Mijoz 'Menga bolalar pijamalarini kursating' deganda pijama tovarlari 38 va 39 aniq topilishi"""
        matches = OrderMatcher.match_products_multi("Menga bolalar pijamalarini kursating")
        self.assertTrue(len(matches) >= 2, "Kamida 2 ta pijama modeli topilishi shart")
        p_ids = [p["id"] for p in matches]
        self.assertIn(38, p_ids, "Qiz bolalar pijamasi (ID 38) topilishi shart")
        self.assertIn(39, p_ids, "O'g'il bolalar pijamasi (ID 39) topilishi shart")

        # Har ikkala tovarning rasm URL-i to'g'ri va faol ekanligini tekshirish
        for p in matches:
            img = p.get("image_url")
            self.assertTrue(bool(img), f"Mahsulot {p['id']} da image_url bo'lishi shart")
            self.assertTrue(img.startswith("https://images.unsplash.com/photo-"), f"Mahsulot {p['id']} rasmi Unsplash bo'lishi shart")
            self.assertNotIn("519725392576", img, f"Eski 404 URL (519725392576) qolmagan bo'lishi shart")

    def test_media_service_pajama_media_group_success(self):
        """Media group orqali 2 ta pijama fotosi muvaffaqiyatli ketishi"""
        p38 = DatabaseManager.get_product_by_id(38)
        p39 = DatabaseManager.get_product_by_id(39)
        self.assertIsNotNone(p38)
        self.assertIsNotNone(p39)

        mock_bot = MagicMock()
        mock_bot.send_media_group = AsyncMock(return_value=[MagicMock()])
        mock_bot.send_message = AsyncMock(return_value=MagicMock())

        async def run_presentation():
            return await send_product_presentation(
                bot=mock_bot,
                chat_id=123456,
                products=[p38, p39],
                suggest_variants=True
            )

        res = asyncio.run(run_presentation())
        self.assertTrue(res)
        self.assertEqual(mock_bot.send_media_group.call_count, 1)

        # Tekshiramiz: media_group ichidagi rasmlar
        call_args = mock_bot.send_media_group.call_args
        media_list = call_args.kwargs.get("media") or call_args.args[1]
        self.assertEqual(len(media_list), 2)
        self.assertEqual(media_list[0].media, p38["image_url"])
        self.assertEqual(media_list[1].media, p39["image_url"])

    def test_media_service_curl_fail_direct_byte_fallback(self):
        """Agar Telegram serverida URL curl xatosi bo'lsa, to'g'ridan-to'g'ri baytlar bilan media group yuborilishi"""
        p38 = DatabaseManager.get_product_by_id(38)
        p39 = DatabaseManager.get_product_by_id(39)

        mock_bot = MagicMock()
        # Birinchi URL chaqiruvida WEBPAGE_CURL_FAILED xatosi beramiz
        async def mock_send_mg(*args, **kwargs):
            media = kwargs.get("media") or args[1]
            # Agar birinchi chaqiruv string URL bo'lsa, xato beramiz
            if isinstance(media[0].media, str):
                raise Exception("Bad Request: failed to get HTTP URL content / WEBPAGE_CURL_FAILED")
            # Agar BufferedInputFile bo'lsa, muvaffaqiyatli o'tadi
            return [MagicMock()]

        mock_bot.send_media_group = AsyncMock(side_effect=mock_send_mg)
        mock_bot.send_message = AsyncMock(return_value=MagicMock())

        # fetch_image_bytes soxta baytlar qaytaradi
        fake_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 1000
        with patch("services.media_service.fetch_image_bytes", new_callable=AsyncMock, return_value=fake_bytes):
            res = asyncio.run(send_product_presentation(
                bot=mock_bot,
                chat_id=123456,
                products=[p38, p39],
                suggest_variants=True
            ))

        self.assertTrue(res)
        # Ikki marta chaqirilgan bo'lishi kerak: 1-si URL (xato berdi), 2-si BufferedInputFile (muvaffaqiyatli)
        self.assertEqual(mock_bot.send_media_group.call_count, 2)
        second_call = mock_bot.send_media_group.call_args_list[1]
        buffered_media = second_call.kwargs.get("media") or second_call.args[1]
        self.assertEqual(len(buffered_media), 2)
        self.assertIsInstance(buffered_media[0].media, types.BufferedInputFile)


if __name__ == "__main__":
    unittest.main()
