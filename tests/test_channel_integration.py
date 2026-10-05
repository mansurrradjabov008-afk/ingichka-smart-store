"""
tests/test_channel_integration.py
Test suite for Store Channel Integration and Store Boss (Do'kon Egasi) System.
Strictly follows RULES.md.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from services.channel_service import ChannelService, CHANNEL_CONFIG_FILE
from bot.bot_app import is_admin_user
from aiogram.enums import ChatMemberStatus


class TestChannelIntegration(unittest.TestCase):
    def setUp(self):
        self.backup_config = None
        if CHANNEL_CONFIG_FILE.exists():
            with open(CHANNEL_CONFIG_FILE, "r", encoding="utf-8") as f:
                self.backup_config = f.read()

    def tearDown(self):
        if self.backup_config is not None:
            with open(CHANNEL_CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(self.backup_config)

    def test_channel_config_atomic_rw(self):
        """Kanal va boshliq konfiguratsiyasi to'g'ri o'qiladi va atomik saqlanadi"""
        cfg = ChannelService.update_config(
            channel_id=-10099887766,
            channel_title="Baraka Test Kanal",
            channel_username="@baraka_test",
            boss_id=777888999,
            boss_name="Test Boshliq",
            boss_username="test_boshliq"
        )
        self.assertEqual(cfg["channel_id"], -10099887766)
        self.assertEqual(cfg["boss_id"], 777888999)
        self.assertEqual(ChannelService.get_boss_id(), 777888999)
        self.assertTrue(ChannelService.is_boss(777888999))
        self.assertFalse(ChannelService.is_boss(111222333))

    def test_boss_admin_permission(self):
        """Boshliq sifatida ro'yxatdan o'tgan foydalanuvchi is_admin_user da True qaytaradi"""
        ChannelService.register_boss(
            user_id=555444333,
            full_name="Akrom Aka",
            username="akrom_boss"
        )
        fake_user = MagicMock()
        fake_user.id = 555444333
        fake_user.username = "akrom_boss"
        self.assertTrue(is_admin_user(fake_user, chat_id=555444333))

    def test_channel_post_formatting(self):
        """Kanal uchun xarid posti va 1-bosishda xarid tugmasi to'g'ri shakllanadi"""
        dummy_prod = {
            "id": 16,
            "name": "Zara Straight jinsi Moviy",
            "category": "Erkaklar kiyimi",
            "sale_price": 434000.0,
            "stock_quantity": 3,
            "size": "30, 32, 34",
            "color": "Moviy",
            "description": "Klassik qulay model"
        }
        text, kb = ChannelService.format_channel_post(dummy_prod, "Markazsavdo00_bot")

        # Anti-hallucination checks
        self.assertIn("Zara Straight jinsi Moviy", text)
        self.assertIn("434,000 so'm", text)
        self.assertIn("30, 32, 34", text)
        self.assertIn("Moviy", text)
        self.assertIn("Shoshiling, omborda faqat 3 dona qoldi!", text)

        # Inline button link check
        self.assertIsNotNone(kb)
        buttons = kb.inline_keyboard
        self.assertEqual(len(buttons), 2)
        buy_btn = buttons[0][0]
        self.assertEqual(buy_btn.text, "🛍️ Xarid qilish (1-bosishda)")
        self.assertIn("https://t.me/Markazsavdo00_bot?start=buy_16", buy_btn.url)

    def test_boss_dashboard_formatting(self):
        """Boshliq boshqaruv paneli formatlanishi barcha ma'lumotlarni o'z ichiga oladi"""
        ChannelService.update_config(
            channel_title="Do'kon Rasmiy Kanali",
            channel_username="@dukon_kanali",
            boss_name="Dilshodbek",
            boss_id=999888777
        )
        stats = {
            "total_products": 49,
            "total_stock": 250,
            "low_stock_count": 5,
            "sold_out_count": 2,
            "today_revenue": 1500000.0,
            "today_orders": 4,
            "waitlist_count": 6
        }
        dash = ChannelService.format_boss_dashboard(stats, bot_username="Markazsavdo00_bot")
        self.assertIn("HURMATLI BOSHLIQ", dash)
        self.assertIn("Dilshodbek", dash)
        self.assertIn("Do'kon Rasmiy Kanali", dash)
        self.assertIn("1,500,000 so'm", dash)
        self.assertIn("4 ta", dash)
        self.assertIn("49 xil", dash)
        self.assertIn("/kanalga_post", dash)
        self.assertIn("/restock", dash)

    def test_sync_channel_and_boss_mock(self):
        """Bot kanalga admin bo'lganda, kanal yaratuvchisi avtomatik Boshliq bo'ladi"""
        bot_mock = AsyncMock()

        # Mock chat info
        chat_mock = MagicMock()
        chat_mock.title = "Markaziy Savdo Kanali"
        chat_mock.username = "markaziy_savdo"
        bot_mock.get_chat.return_value = chat_mock

        # Mock creator admin
        owner_user_mock = MagicMock()
        owner_user_mock.id = 888777666
        owner_user_mock.full_name = "Kanal Yaratuvchisi"
        owner_user_mock.username = "owner_channel"

        creator_adm_mock = MagicMock()
        creator_adm_mock.status = ChatMemberStatus.CREATOR
        creator_adm_mock.user = owner_user_mock

        bot_mock.get_chat_administrators.return_value = [creator_adm_mock]

        import asyncio
        res = asyncio.run(ChannelService.sync_channel_and_boss(
            bot=bot_mock,
            channel_id=-1001234567890
        ))

        self.assertTrue(res["success"])
        self.assertEqual(res["channel_title"], "Markaziy Savdo Kanali")
        self.assertEqual(ChannelService.get_boss_id(), 888777666)
        self.assertTrue(ChannelService.is_boss(888777666))


if __name__ == "__main__":
    unittest.main()
