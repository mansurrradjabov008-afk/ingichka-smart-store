import unittest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.enums import ChatType
from database.db_manager import init_db
from services.voice_service import VoiceService
from services.media_input_service import MediaInputService


class TestVoiceSalesIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_voice_text_to_speech_synthesis(self):
        """TTS orqali o'zbekcha 20 yillik sotuvchi ovozi fayli yaratilishi kerak"""
        text = "Assalomu alaykum! Bizda sifatli qiz bolalar krossovkasi bor, o'lchami 28 mavjud!"
        path = asyncio.run(VoiceService.text_to_speech(text, filename_prefix="unit_test"))
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 1000)
        # Tozalash
        if os.path.exists(path):
            os.remove(path)

    def test_handle_voice_message_flow_with_product(self):
        """Mijoz ovozli xabar yuborganda, bot ovozli javob va tovar kartasini yuborishi kerak"""
        from bot.bot_app import handle_voice_message, bot

        # Mock voice object
        mock_voice = MagicMock()
        mock_voice.duration = 12
        mock_voice.file_id = "voice_file_123"

        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=11223344, type=ChatType.PRIVATE)
        mock_msg.from_user = MagicMock(id=11223344, first_name="Zilola", is_bot=False)
        mock_msg.voice = mock_voice
        mock_msg.audio = None

        sent_voices = []
        sent_messages = []

        async def fake_send_voice(chat_id, voice, caption=None, **kwargs):
            sent_voices.append({"chat_id": chat_id, "voice": voice, "caption": caption})
            return True

        async def fake_safe_send(chat_id, text, reply_markup=None, **kwargs):
            sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
            return True

        mock_bot_info = MagicMock(username="Markazsavdo00_bot", id=8663033870)

        # Mock transcribe_audio to return product query
        mock_trans = {"success": True, "transcript": "Qiz bolalarga Xitoy krasovka bormi 28 razmer?"}

        with patch("services.media_input_service.MediaInputService.transcribe_audio", return_value=mock_trans), \
             patch.object(bot, "download", new_callable=AsyncMock), \
             patch.object(bot, "send_chat_action", new_callable=AsyncMock), \
             patch.object(bot, "get_me", new_callable=AsyncMock, return_value=mock_bot_info), \
             patch.object(bot, "send_voice", side_effect=fake_send_voice), \
             patch("bot.bot_app.safe_send", side_effect=fake_safe_send):
            asyncio.run(handle_voice_message(mock_msg))

        # 1. Ovozli javob (send_voice) yuborilganini tekshirish
        self.assertEqual(len(sent_voices), 1)
        self.assertIn("sotuvchi", sent_voices[0]["caption"].lower())

        # 2. Tovar kartasi / taqdimoti yuborilganini tekshirish
        self.assertGreater(len(sent_messages), 0)
        card_resp = sent_messages[0]
        self.assertIn("Qiz bolalar Xitoy krossovka", card_resp["text"])
        self.assertIn("85,000 so'm", card_resp["text"])

        # 3. 1-bosishda xarid qilish tugmasi mavjudligi (callback_data yoki url)
        kb = card_resp["reply_markup"]
        self.assertIsNotNone(kb)
        btn = kb.inline_keyboard[0][0]
        self.assertTrue(
            btn.callback_data == "fast_buy_41" or (btn.url and "start=buy_41" in btn.url),
            f"Expected fast_buy_41 or buy_41 url, got: {btn}"
        )

    def test_handle_voice_message_empty_transcript(self):
        """Ovoz tushunarsiz/bo'sh bo'lsa, xushmuomala takrorlash xabari yuborilishi kerak"""
        from bot.bot_app import handle_voice_message, bot

        mock_voice = MagicMock()
        mock_voice.duration = 5
        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=11223344, type=ChatType.PRIVATE)
        mock_msg.from_user = MagicMock(id=11223344, first_name="Zilola", is_bot=False)
        mock_msg.voice = mock_voice
        mock_msg.audio = None

        sent_messages = []
        async def fake_safe_send(chat_id, text, **kwargs):
            sent_messages.append(text)
            return True

        mock_trans = {"success": False, "message": "Ovozli xabarni aniqlab bo'lmadi. Iltimos, qaytadan aniqroq gapiring."}

        with patch("services.media_input_service.MediaInputService.transcribe_audio", return_value=mock_trans), \
             patch.object(bot, "download", new_callable=AsyncMock), \
             patch.object(bot, "send_chat_action", new_callable=AsyncMock), \
             patch("bot.bot_app.safe_send", side_effect=fake_safe_send):
            asyncio.run(handle_voice_message(mock_msg))

        self.assertEqual(len(sent_messages), 1)
        self.assertIn("aniqlab bo'lmadi", sent_messages[0])

    def test_handle_voice_message_too_long(self):
        """60 sekunddan oshsa, rad etilishi kerak"""
        from bot.bot_app import handle_voice_message

        mock_voice = MagicMock()
        mock_voice.duration = 65 # 65 soniya > 60
        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=11223344, type=ChatType.PRIVATE)
        mock_msg.from_user = MagicMock(id=11223344, first_name="Zilola", is_bot=False)
        mock_msg.voice = mock_voice
        mock_msg.audio = None

        sent_messages = []
        async def fake_safe_send(chat_id, text, **kwargs):
            sent_messages.append(text)
            return True

        with patch("bot.bot_app.safe_send", side_effect=fake_safe_send):
            asyncio.run(handle_voice_message(mock_msg))

        self.assertEqual(len(sent_messages), 1)
        self.assertIn("60 soniyadan oshmasligi kerak", sent_messages[0])


if __name__ == "__main__":
    unittest.main()
