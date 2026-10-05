"""
services/channel_service.py
Telegram Kanal va Do'kon Egasi (Boshliq) Boshqaruv Xizmati.
Strictly follows RULES.md:
- Rule 1: Clean integration, never breaks existing features.
- Rule 2: No hardcoded secrets.
- Rule 3: Wrap external calls in try/except with safe fallback.
- Rule 4: Atomic file I/O with lock.
- Rule 5: Log errors with chat_id.
- Rule 6-10: Anti-hallucination.
"""

import os
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus

from config import CHANNEL_ID, CHANNEL_USERNAME, CHANNEL_URL, STORE_NAME, ADMIN_TELEGRAM_IDS
from utils.logger import log_bot_error

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHANNEL_CONFIG_FILE = DATA_DIR / "channel_config.json"
_CONFIG_LOCK = threading.RLock()


class ChannelService:
    """Do'kon kanali va Boshliqni (Store Owner) boshqarish xizmati"""

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Kanal va boshliq sozlamalarini xavfsiz o'qish"""
        with _CONFIG_LOCK:
            if not CHANNEL_CONFIG_FILE.exists():
                default_cfg = {
                    "channel_id": CHANNEL_ID,
                    "channel_username": CHANNEL_USERNAME,
                    "channel_url": CHANNEL_URL,
                    "channel_title": STORE_NAME,
                    "boss_id": None,
                    "boss_name": None,
                    "boss_username": None,
                    "linked_chat_id": None,
                    "auto_post_new_products": True,
                    "updated_at": None
                }
                cls._save_config_atomic(default_cfg)
                return default_cfg

            try:
                with open(CHANNEL_CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading channel_config.json: {e}")
                return {
                    "channel_id": CHANNEL_ID,
                    "channel_username": CHANNEL_USERNAME,
                    "channel_url": CHANNEL_URL,
                    "channel_title": STORE_NAME,
                    "boss_id": None,
                    "boss_name": None,
                    "boss_username": None
                }

    @classmethod
    def _save_config_atomic(cls, config: Dict[str, Any]) -> None:
        """Kanal sozlamalarini atomik ravishda faylga saqlash (Rule 4)"""
        temp_file = CHANNEL_CONFIG_FILE.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            temp_file.replace(CHANNEL_CONFIG_FILE)
        except Exception as e:
            logger.error(f"Error saving channel_config.json: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    @classmethod
    def update_config(cls, **kwargs) -> Dict[str, Any]:
        """Kanal sozlamalarini yangilash"""
        with _CONFIG_LOCK:
            cfg = cls.get_config()
            cfg.update(kwargs)
            from datetime import datetime
            cfg["updated_at"] = datetime.now().isoformat()
            cls._save_config_atomic(cfg)
            return cfg

    @classmethod
    def get_boss_id(cls) -> Optional[int]:
        """Boshliqning (Store Owner) Telegram ID sini olish"""
        cfg = cls.get_config()
        return cfg.get("boss_id")

    @classmethod
    def is_boss(cls, user_id: int) -> bool:
        """Foydalanuvchi Boshliq ekanligini tekshirish"""
        if not user_id:
            return False
        cfg = cls.get_config()
        boss_id = cfg.get("boss_id")
        if boss_id and int(boss_id) == int(user_id):
            return True
        return False

    @classmethod
    def register_boss(cls, user_id: int, full_name: str, username: Optional[str] = None) -> Dict[str, Any]:
        """Kanal egasini botning rasmiy Boshlig'i sifatida ro'yxatga olish"""
        cfg = cls.update_config(
            boss_id=user_id,
            boss_name=full_name,
            boss_username=username or ""
        )
        if user_id not in ADMIN_TELEGRAM_IDS:
            ADMIN_TELEGRAM_IDS.append(user_id)
            logger.info(f"Registered Boss into ADMIN_TELEGRAM_IDS: {user_id} ({full_name})")
        return cfg

    @classmethod
    async def sync_channel_and_boss(
        cls,
        bot: Bot,
        channel_id: int,
        channel_title: Optional[str] = None,
        channel_username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Kanalga bot admin qilinganda, kanal ma'lumotlarini va kanal yaratuvchisini (Boshliq)
        avtomatik aniqlash va ro'yxatdan o'tkazish.
        """
        try:
            chat = await bot.get_chat(channel_id)
            c_title = channel_title or chat.title or STORE_NAME
            c_username = channel_username or (f"@{chat.username}" if chat.username else CHANNEL_USERNAME)

            boss_user = None
            try:
                admins = await bot.get_chat_administrators(channel_id)
                for adm in admins:
                    # ChatMemberOwner yoki creator statusi
                    if adm.status in [ChatMemberStatus.CREATOR, "creator"]:
                        boss_user = adm.user
                        break
            except Exception as admin_err:
                logger.warning(f"Could not fetch channel administrators for {channel_id}: {admin_err}")

            updates: Dict[str, Any] = {
                "channel_id": channel_id,
                "channel_title": c_title,
                "channel_username": c_username,
                "channel_url": f"https://t.me/{chat.username}" if chat.username else CHANNEL_URL
            }

            if boss_user:
                updates["boss_id"] = boss_user.id
                updates["boss_name"] = boss_user.full_name or "Do'kon Egasi"
                updates["boss_username"] = boss_user.username or ""
                if boss_user.id not in ADMIN_TELEGRAM_IDS:
                    ADMIN_TELEGRAM_IDS.append(boss_user.id)
                logger.info(f"Auto-detected Channel Owner (Boss): {boss_user.full_name} (ID: {boss_user.id})")

            cfg = cls.update_config(**updates)
            return {
                "success": True,
                "channel_title": c_title,
                "channel_username": c_username,
                "boss_user": boss_user,
                "config": cfg
            }
        except Exception as e:
            logger.error(f"Failed to sync channel and boss: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    async def check_user_is_channel_owner(cls, bot: Bot, user_id: int) -> bool:
        """
        Foydalanuvchi ulangan kanalning yaratuvchisi/admini ekanligini Telegram API orqali tekshirish.
        """
        cfg = cls.get_config()
        channel_id = cfg.get("channel_id") or CHANNEL_ID
        if not channel_id:
            return False
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in [ChatMemberStatus.CREATOR, "creator"]:
                # Avtomatik Boshliq sifatida saqlaymiz
                cls.register_boss(
                    user_id=user_id,
                    full_name=member.user.full_name or "Do'kon Egasi",
                    username=member.user.username or ""
                )
                return True
            elif member.status in [ChatMemberStatus.ADMINISTRATOR, "administrator"]:
                if user_id not in ADMIN_TELEGRAM_IDS:
                    ADMIN_TELEGRAM_IDS.append(user_id)
                return True
        except Exception as e:
            logger.debug(f"check_user_is_channel_owner check failed: {e}")
        return False

    @classmethod
    def format_channel_post(cls, product: Dict[str, Any], bot_username: str) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Telegram Kanal uchun yuqori konversiyali, estetik va to'liq ma'lumotli mahsulot posti.
        Pastida 1-bosishda xarid qilish tugmasi bo'ladi.
        """
        p_id = product.get("id", 1)
        name = product.get("name", "Mahsulot")
        cat = product.get("category", "Kiyim")
        price = float(product.get("sale_price") or product.get("price") or 0.0)
        stock = int(product.get("stock_quantity") or product.get("stock") or 0)
        size = product.get("size") or ", ".join(product.get("sizes", [])) or "Standart"
        color = product.get("color") or ", ".join(product.get("colors", [])) or "Mavjud"
        desc = product.get("description", "").strip()

        stock_badge = ""
        if stock <= 0:
            stock_badge = "❌ **Hozirda sotuvda tugagan**"
        elif 0 < stock <= 3:
            stock_badge = f"🔥 **Shoshiling, omborda faqat {stock} dona qoldi!**"
        else:
            stock_badge = f"📊 Omborda mavjud: **{stock} dona**"

        desc_block = f"📝 {desc}\n\n" if desc else ""

        post_text = (
            f"✨ **YANGI TOVAR KELDI!** ✨\n\n"
            f"🏷️ **{name}**\n"
            f"📁 Toifasi: #{cat.replace(' ', '_')}\n\n"
            f"{desc_block}"
            f"📏 **O'lchamlar:** {size}\n"
            f"🎨 **Ranglar:** {color}\n"
            f"💰 **Narxi:** **{price:,.0f} so'm**\n"
            f"{stock_badge}\n\n"
            f"🚚 Yetkazib berish xizmati mavjud!\n"
            f"🛡️ To'lovni tovarni eshik oldida ko'rib, yoqqanidan so'ng qilasiz.\n\n"
            f"👇 **Xarid qilish uchun pastdagi tugmani bosing:**"
        )

        buy_url = f"https://t.me/{bot_username}?start=buy_{p_id}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🛍️ Xarid qilish (1-bosishda)", url=buy_url)
            ],
            [
                InlineKeyboardButton(text="💬 Sotuvchi bilan bog'lanish", url=f"https://t.me/{bot_username}")
            ]
        ])

        return post_text, keyboard

    @classmethod
    def format_boss_dashboard(
        cls,
        stats: Dict[str, Any],
        bot_username: str = "Markazsavdo00_bot"
    ) -> str:
        """
        Do'kon Egasi (Boshliq) uchun to'liq boshqaruv paneli ko'rinishi.
        """
        cfg = cls.get_config()
        c_title = cfg.get("channel_title") or STORE_NAME
        c_user = cfg.get("channel_username") or CHANNEL_USERNAME
        boss_name = cfg.get("boss_name") or "Do'kon Egasi"
        boss_id = cfg.get("boss_id") or "O'rnatilmagan"

        total_prods = stats.get("total_products", 0)
        total_stock = stats.get("total_stock", 0)
        low_stock = stats.get("low_stock_count", 0)
        sold_out = stats.get("sold_out_count", 0)
        today_rev = stats.get("today_revenue", 0.0)
        today_orders = stats.get("today_orders", 0)
        waitlist_cnt = stats.get("waitlist_count", 0)

        return (
            f"👑 **HURMATLI BOSHLIQ — DO'KON VA BOT BOSHQARUVI** 👑\n\n"
            f"🏪 **Do'kon:** {STORE_NAME}\n"
            f"📢 **Ulangan Kanal:** **{c_title}** ({c_user})\n"
            f"👤 **Boshliq:** **{boss_name}** (ID: `{boss_id}`)\n"
            f"🤖 **Bot holati:** 🟢 24/7 Faol va Savdoda\n\n"
            f"📊 **BUGUNGI SAVDO KO'RSATKICHLARI:**\n"
            f"💰 Bugungi tushum: **{today_rev:,.0f} so'm**\n"
            f"📋 Bugungi buyurtmalar: **{today_orders} ta**\n"
            f"📦 Ombordagi tovarlar: **{total_prods} xil** ({total_stock} dona)\n"
            f"⚠️ Kam qolganlar (<=3): **{low_stock} xil**\n"
            f"❌ Tugagan tovarlar: **{sold_out} xil**\n"
            f"👥 Kutayotgan mijozlar (Waitlist): **{waitlist_cnt} kishi**\n\n"
            f"⚡ **BOSHLIQ BUYRUQLARI:**\n"
            f"📢 `/kanalga_post <id>` — Tovarni kanalga xarid tugmasi bilan joylash\n"
            f"🔄 `/restock <id> <soni>` — Ombordagi tovarni to'ldirish (kutayotganlarga avto-xabar yuboradi)\n"
            f"📈 `/stat` — Batafsil to'liq savdo va kassa hisoboti\n"
            f"💵 `/kassa` — Kassa va to'lovlar holati\n"
            f"📦 `/orders` — So'nggi faol buyurtmalar ro'yxati\n"
            f"🔗 `/set_channel @kanal` — Boshqa kanalga ulash\n\n"
            f"🎙️ **OVOZLI BOSHQARUV:**\n"
            f"Siz botga ovozli xabar orqali: *'Bugun 20 ta oq krossovka keldi, tan narxi 150 ming, sotuv narxi 220 ming'* desangiz, bot avtomatik yangi tovar sifatida omborga qo'shadi!"
        )
