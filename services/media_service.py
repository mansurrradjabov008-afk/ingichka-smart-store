"""
services/media_service.py
Task 2 Requirements 1 & 2:
1. When the bot recommends or the customer asks about a specific product,
   send its photo (image_url) with a caption: name, price, available sizes.
   If several products match, send max 3 as a media group.
2. If image_url is broken or missing, send the text only. Never fail.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from aiogram import Bot, types
from aiogram.types import InputMediaPhoto

from utils.logger import log_bot_error

logger = logging.getLogger(__name__)

def format_product_caption(prod: Dict[str, Any]) -> str:
    """Format product caption with name, price, available sizes"""
    name = prod.get("name", "Mahsulot")
    price = prod.get("price") or prod.get("sale_price", 0)
    sizes = prod.get("sizes")
    if not sizes and prod.get("size"):
        sizes = [s.strip() for s in str(prod["size"]).split(",") if s.strip()]
    sizes_str = ", ".join(sizes) if sizes else "Standard"
    
    st = prod.get("stock") or prod.get("stock_quantity", 0)
    stock_label = f" (oxirgi {st} ta qoldi)" if 0 < st <= 2 else ""

    return f"👕 {name}\n💰 Narxi: {price:,.0f} so'm{stock_label}\n📏 Mavjud o'lchamlar: {sizes_str}"

async def send_product_presentation(
    bot: Bot,
    chat_id: int,
    products: List[Dict[str, Any]],
    reply_markup=None,
    safe_send_fn=None
) -> bool:
    """
    Sends product photo(s) with caption(s).
    - If 1 product: sends single photo with caption.
    - If several products: sends max 3 as media group.
    - If image_url is broken or missing: sends text only. Never fails.
    """
    if not products:
        return False

    prods_to_send = products[:3]

    # Helper for sending safe text fallback
    async def _send_text_fallback():
        for p in prods_to_send:
            cap = format_product_caption(p)
            if safe_send_fn:
                await safe_send_fn(chat_id=chat_id, text=cap, reply_markup=reply_markup)
            else:
                try:
                    await bot.send_message(chat_id=chat_id, text=cap, reply_markup=reply_markup)
                except Exception as ex:
                    log_bot_error(chat_id, f"Failed fallback text send: {ex}", exc=ex)

    # 1. Bitta tovar bo'lsa
    if len(prods_to_send) == 1:
        p = prods_to_send[0]
        img_url = p.get("image_url") or p.get("photo_id")
        caption = format_product_caption(p)

        if img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("AgAC")):
            try:
                await asyncio.wait_for(
                    bot.send_photo(chat_id=chat_id, photo=img_url, caption=caption, reply_markup=reply_markup),
                    timeout=12.0
                )
                return True
            except Exception as e:
                # Broken URL or Telegram photo error -> Fallback to text only
                log_bot_error(chat_id, f"Broken image_url or photo send failed: {e}. Falling back to text.", exc=e)
                if safe_send_fn:
                    await safe_send_fn(chat_id=chat_id, text=caption, reply_markup=reply_markup)
                else:
                    await bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup)
                return True
        else:
            # Missing image_url -> text only
            if safe_send_fn:
                await safe_send_fn(chat_id=chat_id, text=caption, reply_markup=reply_markup)
            else:
                await bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup)
            return True

    # 2. Bir nechta tovar bo'lsa (max 3 ta media group)
    media_items = []
    for p in prods_to_send:
        img_url = p.get("image_url") or p.get("photo_id")
        if img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("AgAC")):
            media_items.append(InputMediaPhoto(media=img_url, caption=format_product_caption(p)))

    # Agar kamida 2 ta tovarning rasmi bo'lsa -> media group yuborish
    if len(media_items) >= 2:
        try:
            await asyncio.wait_for(
                bot.send_media_group(chat_id=chat_id, media=media_items),
                timeout=15.0
            )
            return True
        except Exception as e:
            # Media group failed (e.g. one URL broken) -> Fallback to text
            log_bot_error(chat_id, f"Media group send failed: {e}. Falling back to text.", exc=e)
            await _send_text_fallback()
            return True
    else:
        # Rasmlar yetarli emas yoki yo'q -> Text fallback
        await _send_text_fallback()
        return True
