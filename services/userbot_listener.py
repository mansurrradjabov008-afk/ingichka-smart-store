"""
Telegram Shaxsiy Profil (UserBot) Integratsiyasi.
Bu modul orqali bot mijozlarga rasmiy @bot sifatida emas, balki
Do'kon egasining yoki sotuvchisining O'Z SHAXSIY TELEGRAM PROFILIDAN
xuddi tirik insondek javob qaytaradi!
"""

import os
import sys
import logging
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient, events
from ai_engine.ai_brain import ai_brain

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Sozlamalar: my.telegram.org dan olinadi
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_NAME = str(Path(__file__).resolve().parent.parent / "seller_personal_session")

async def start_personal_account_ai():
    if not API_ID or not API_HASH:
        logger.warning(
            "DIQQAT: Shaxsiy profilga ulash uchun TELEGRAM_API_ID va TELEGRAM_API_HASH sozlanmagan. "
            "Buni my.telegram.org dan 1 daqiqada bepul olishingiz mumkin."
        )
        return

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    logger.info(f"Shaxsiy profilga AI muvaffaqiyatli ulandi: {me.first_name} (@{me.username})")

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def handle_personal_dm(event):
        sender = await event.get_sender()
        # Botlar yoki Telegram rasmiy xabarlarini chetlab o'tish
        if sender.bot or sender.is_self:
            return

        text = event.raw_text
        user_name = sender.first_name or "Qadrdonim"
        user_id = sender.id

        logger.info(f"Shaxsiy profilingizga xabar keldi: {user_name} -> '{text}'")

        # Tirik insondek 'yozmoqda...' (typing) ko'rsatish
        async with client.action(event.chat_id, 'typing'):
            response = ai_brain.ask(
                user_id=user_id,
                user_message=text,
                customer_name=user_name
            )

        # O'z profilingiz nomidan javob yuborish
        await event.reply(response)
        logger.info(f"AI sizning profilingiz nomidan javob berdi -> {user_name}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_personal_account_ai())
