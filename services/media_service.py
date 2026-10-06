"""
services/media_service.py
Task 2 Requirements 1 & 2:
1. When the bot recommends or the customer asks about a specific product,
   send its photo (image_url) with a caption: name, price, available sizes.
   If several products match, send max 3 as a media group.
2. If image_url is broken or missing, fallback to resilient byte download / backup image.
   Never fail silently or drop to text-only when photos can be shown.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp
from aiogram import Bot, types
from aiogram.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from utils.logger import log_bot_error

logger = logging.getLogger(__name__)

# In-memory image bytes cache to avoid duplicate network fetches
_IMAGE_BYTES_CACHE: Dict[str, bytes] = {}
DEFAULT_BACKUP_IMAGE_URL = "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=600"

async def fetch_image_bytes(url: Optional[str]) -> Optional[bytes]:
    """Fetch image bytes directly with desktop headers and cache. Never raises."""
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None
    if url in _IMAGE_BYTES_CACHE:
        return _IMAGE_BYTES_CACHE[url]
    try:
        timeout = aiohttp.ClientTimeout(total=8.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 500:
                        _IMAGE_BYTES_CACHE[url] = data
                        return data
    except Exception as err:
        logger.warning(f"Direct image fetch failed for {url}: {err}")
    return None

def format_product_caption(prod: Dict[str, Any]) -> str:
    """Format single product caption with name, price, available sizes, material, and sales prompt (Task 4: Max 1 emoji, urgency stock <= 3)"""
    name = prod.get("name", "Mahsulot")
    price = prod.get("price") or prod.get("sale_price", 0)
    sizes = prod.get("sizes")
    if not sizes and prod.get("size"):
        sizes = [s.strip() for s in str(prod["size"]).split(",") if s.strip()]
    sizes_str = ", ".join(sizes) if sizes else "Standard"
    
    st = prod.get("stock") or prod.get("stock_quantity", 0)
    stock_label = f" (oxirgi {st} ta qoldi)" if 0 < st <= 3 else (f" ({st} dona bor)" if st > 0 else "")

    color = prod.get("color") or (", ".join(prod.get("colors", [])) if prod.get("colors") else "")
    material = prod.get("material", "")
    sku = prod.get("sku", "")

    extra_info = []
    if color:
        extra_info.append(f"Rang: {color.capitalize()}")
    if material:
        extra_info.append(f"Material: {material}")
    if sku:
        extra_info.append(f"SKU: {sku}")

    extra_str = ("\n" + " | ".join(extra_info)) if extra_info else ""

    return (
        f"**{name}**\n"
        f"Narxi: **{price:,.0f} so'm**{stock_label}\n"
        f"Mavjud o'lchamlar: **{sizes_str}**"
        f"{extra_str}\n\n"
        f"Xarid qilishni istaysizmi? Buyurtmani rasmiylashtirib beraymi? 😊"
    )

def format_multi_product_caption(products: List[Dict[str, Any]]) -> str:
    """Multi-product caption for Telegram media groups (Task 4: Max 1 emoji, urgency stock <= 3)"""
    lines = ["**Do'konimizdagi tanlangan sara tovarlar:**\n"]
    for i, p in enumerate(products, 1):
        name = p.get("name", "Mahsulot")
        price = p.get("price") or p.get("sale_price", 0)
        sizes = p.get("sizes")
        if not sizes and p.get("size"):
            sizes = [s.strip() for s in str(p["size"]).split(",") if s.strip()]
        sizes_str = ", ".join(sizes) if sizes else "Standard"
        st = p.get("stock") or p.get("stock_quantity", 0)
        stock_label = f" (oxirgi {st} ta qoldi)" if 0 < st <= 3 else (f" ({st} dona bor)" if st > 0 else "")
        color = p.get("color") or (", ".join(p.get("colors", [])) if p.get("colors") else "")
        color_str = f" | Rang: {color.capitalize()}" if color else ""
        lines.append(f"{i}. **{name}**\n   Narxi: **{price:,.0f} so'm**{stock_label}\n   O'lcham: **{sizes_str}**{color_str}")

    lines.append("\nQaysi biri sizga ma'qul? Razmer va buyurtma bo'yicha yordam beraymi? 😊")
    return "\n".join(lines)

def get_single_product_keyboard(prod: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Tugmalar: Hoziroq sotib olish, Savatga qo'shish, Barcha turlarini ko'rish"""
    pid = prod.get("id", 1)
    cat = prod.get("category", "")
    buttons = [
        [
            InlineKeyboardButton(text="⚡️ Hoziroq sotib olish", callback_data=f"fast_buy_{pid}"),
            InlineKeyboardButton(text="🛒 Savatga qo'shish (+1)", callback_data=f"cart_add_{pid}")
        ]
    ]
    second_row = []
    if cat:
        second_row.append(InlineKeyboardButton(text="🛍️ Barcha turlarini ko'rish", callback_data=f"cat_{cat}"))
    second_row.append(InlineKeyboardButton(text="🛒 Savatcham", callback_data="open_cart"))
    buttons.append(second_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_multi_product_action_keyboard(products: List[Dict[str, Any]], category: str = "", total_cat_count: int = 0) -> InlineKeyboardMarkup:
    """Bir nechta tovar ko'rsatilganda har biri uchun xarid tugmalari va barcha modellarni ko'rish tugmasi"""
    buttons = []
    buy_row = []
    for i, p in enumerate(products[:3], 1):
        pid = p.get("id")
        buy_row.append(InlineKeyboardButton(text=f"⚡️ {i}-ni olish", callback_data=f"fast_buy_{pid}"))
    if buy_row:
        buttons.append(buy_row)

    cart_row = []
    for i, p in enumerate(products[:3], 1):
        pid = p.get("id")
        cart_row.append(InlineKeyboardButton(text=f"🛒 {i}-savat", callback_data=f"cart_add_{pid}"))
    if cart_row:
        buttons.append(cart_row)

    nav_row = []
    if category:
        cat_label = f"🛍️ Barcha {category}larni ko'rish"
        if total_cat_count > 0:
            cat_label += f" ({total_cat_count} ta model)"
        nav_row.append(InlineKeyboardButton(text=cat_label, callback_data=f"cat_{category}"))
    nav_row.append(InlineKeyboardButton(text="🛒 Savatcham", callback_data="open_cart"))
    buttons.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def send_product_presentation(
    bot: Bot,
    chat_id: int,
    products: List[Dict[str, Any]],
    reply_markup=None,
    safe_send_fn=None,
    suggest_variants: bool = True
) -> bool:
    """
    Sends product photo(s) with caption(s) and interactive action buttons.
    - If 1 product: sends single photo with caption and 1-click buy/cart buttons.
    - If several products: sends max 3 as media group with rich group caption,
      followed by consultative variant suggestions with individual 1-click buy buttons.
    - Multi-layer resilience: URL delivery -> Direct Byte Upload fallback -> Individual photo fallback -> Safe text fallback.
    """
    if not products:
        return False

    prods_to_send = products[:3]

    # Helper for sending safe text fallback as last resort
    async def _send_text_fallback():
        try:
            if len(prods_to_send) == 1:
                p = prods_to_send[0]
                cap = format_product_caption(p)
                kb = reply_markup if reply_markup is not None else get_single_product_keyboard(p)
                if safe_send_fn:
                    await safe_send_fn(chat_id=chat_id, text=cap, reply_markup=kb)
                else:
                    await bot.send_message(chat_id=chat_id, text=cap, reply_markup=kb)
            else:
                multi_cap = format_multi_product_caption(prods_to_send)
                cat_name = prods_to_send[0].get("category", "")
                kb = reply_markup if reply_markup is not None else get_multi_product_action_keyboard(prods_to_send, category=cat_name)
                if safe_send_fn:
                    await safe_send_fn(chat_id=chat_id, text=multi_cap, reply_markup=kb)
                else:
                    await bot.send_message(chat_id=chat_id, text=multi_cap, reply_markup=kb)
        except Exception as fb_err:
            log_bot_error(chat_id, f"Text fallback failed: {fb_err}", exc=fb_err)

    try:
        # 1. Bitta tovar bo'lsa
        if len(prods_to_send) == 1:
            p = prods_to_send[0]
            img_url = p.get("image_url") or p.get("photo_id")
            caption = format_product_caption(p)
            kb = reply_markup if reply_markup is not None else get_single_product_keyboard(p)

            sent = False
            # Try 1: URL / photo_id orqali yuborish
            if img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("AgAC")):
                try:
                    await asyncio.wait_for(
                        bot.send_photo(chat_id=chat_id, photo=img_url, caption=caption, parse_mode="Markdown", reply_markup=kb),
                        timeout=12.0
                    )
                    sent = True
                except Exception as e:
                    log_bot_error(chat_id, f"URL photo send failed: {e}. Trying direct byte upload fallback...", exc=e)

            # Try 2: To'g'ridan-to'g'ri baytlar orqali yuklash (Telegram curl xatoliklarini aylanib o'tadi)
            if not sent and img_url and isinstance(img_url, str) and img_url.startswith("http"):
                try:
                    raw_bytes = await fetch_image_bytes(img_url)
                    if not raw_bytes:
                        raw_bytes = await fetch_image_bytes(DEFAULT_BACKUP_IMAGE_URL)
                    if raw_bytes:
                        buf_file = BufferedInputFile(raw_bytes, filename=f"product_{p.get('id', 1)}.jpg")
                        await asyncio.wait_for(
                            bot.send_photo(chat_id=chat_id, photo=buf_file, caption=caption, parse_mode="Markdown", reply_markup=kb),
                            timeout=15.0
                        )
                        sent = True
                except Exception as byte_err:
                    log_bot_error(chat_id, f"Byte upload photo send failed: {byte_err}", exc=byte_err)

            if sent:
                return True
            else:
                await _send_text_fallback()
                return True

        # 2. Bir nechta tovar bo'lsa (max 3 ta)
        group_caption = format_multi_product_caption(prods_to_send)
        if len(group_caption) > 1000:
            group_caption = group_caption[:990] + "..."

        media_items = []
        for idx, p in enumerate(prods_to_send):
            img_url = p.get("image_url") or p.get("photo_id")
            if img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("AgAC")):
                cap = group_caption if idx == 0 else None
                pm = "Markdown" if idx == 0 else None
                media_items.append(InputMediaPhoto(media=img_url, caption=cap, parse_mode=pm))

        group_sent = False

        # Attempt 1: URL orqali Media Group yuborish
        if len(media_items) >= 2:
            try:
                await asyncio.wait_for(
                    bot.send_media_group(chat_id=chat_id, media=media_items),
                    timeout=15.0
                )
                group_sent = True
            except Exception as e:
                log_bot_error(chat_id, f"Media group URL send failed: {e}. Trying direct byte upload fallback...", exc=e)

        # Attempt 2: Direct byte upload (BufferedInputFile) media group
        if not group_sent:
            buffered_media = []
            for idx, p in enumerate(prods_to_send):
                url = p.get("image_url") or p.get("photo_id")
                raw_bytes = await fetch_image_bytes(url)
                if not raw_bytes:
                    raw_bytes = await fetch_image_bytes(DEFAULT_BACKUP_IMAGE_URL)
                if raw_bytes:
                    cap = group_caption if len(buffered_media) == 0 else None
                    pm = "Markdown" if len(buffered_media) == 0 else None
                    buf = BufferedInputFile(raw_bytes, filename=f"product_{p.get('id', idx)}.jpg")
                    buffered_media.append(InputMediaPhoto(media=buf, caption=cap, parse_mode=pm))

            if len(buffered_media) >= 2:
                try:
                    await asyncio.wait_for(
                        bot.send_media_group(chat_id=chat_id, media=buffered_media),
                        timeout=18.0
                    )
                    group_sent = True
                except Exception as b_mg_err:
                    log_bot_error(chat_id, f"Buffered media group send failed: {b_mg_err}. Trying individual photo fallback...", exc=b_mg_err)

        # Attempt 3: Alohida bittalab rasm yuborish fallback
        if not group_sent:
            any_photo_sent = False
            for idx, p in enumerate(prods_to_send):
                url = p.get("image_url") or p.get("photo_id")
                raw_bytes = await fetch_image_bytes(url)
                if not raw_bytes:
                    raw_bytes = await fetch_image_bytes(DEFAULT_BACKUP_IMAGE_URL)
                cap = format_product_caption(p)
                p_kb = get_single_product_keyboard(p) if reply_markup is None else None
                if raw_bytes:
                    try:
                        buf = BufferedInputFile(raw_bytes, filename=f"product_{p.get('id', idx)}.jpg")
                        await bot.send_photo(chat_id=chat_id, photo=buf, caption=cap, parse_mode="Markdown", reply_markup=p_kb)
                        any_photo_sent = True
                    except Exception as ind_err:
                        log_bot_error(chat_id, f"Individual photo send failed: {ind_err}", exc=ind_err)
            if any_photo_sent:
                group_sent = True

        if group_sent:
            # Media group yoki rasmlar muvaffaqiyatli ketdi!
            # Endi xarid tugmalari va variantlar taklifini yuborish
            cat_name = prods_to_send[0].get("category", "")
            from services.order_matcher import OrderMatcher
            var_info = OrderMatcher.get_category_variants(cat_name, exclude_ids=[p["id"] for p in prods_to_send]) if suggest_variants else None

            if reply_markup is not None:
                kb = reply_markup
                consultative_msg = var_info["summary_text"] if (var_info and var_info.get("other_variants")) else "Yuqoridagi tovarlardan birini xarid qilish uchun quyidagi tugmalarni bosing 👇"
            elif var_info and var_info.get("other_variants"):
                kb = get_multi_product_action_keyboard(prods_to_send, category=var_info["category_key"], total_cat_count=var_info["total_count"])
                consultative_msg = var_info["summary_text"]
            else:
                kb = get_multi_product_action_keyboard(prods_to_send, category=cat_name)
                consultative_msg = "Yuqoridagi tovarlardan birini xarid qilish yoki savatga qo'shish uchun quyidagi tugmalarni bosing 👇"

            if safe_send_fn:
                await safe_send_fn(chat_id=chat_id, text=consultative_msg, reply_markup=kb)
            else:
                await bot.send_message(chat_id=chat_id, text=consultative_msg, reply_markup=kb)
            return True
        else:
            await _send_text_fallback()
            return True

    except Exception as top_ex:
        log_bot_error(chat_id, f"send_product_presentation top error: {top_ex}", exc=top_ex)
        await _send_text_fallback()
        return True
