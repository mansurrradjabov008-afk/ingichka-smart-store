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
from aiogram.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from utils.logger import log_bot_error

logger = logging.getLogger(__name__)

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
    - If image_url is broken or missing: sends text only. Never fails.
    """
    if not products:
        return False

    prods_to_send = products[:3]

    # Helper for sending safe text fallback
    async def _send_text_fallback():
        if len(prods_to_send) == 1:
            p = prods_to_send[0]
            cap = format_product_caption(p)
            kb = reply_markup if reply_markup is not None else get_single_product_keyboard(p)
            if safe_send_fn:
                await safe_send_fn(chat_id=chat_id, text=cap, reply_markup=kb)
            else:
                try:
                    await bot.send_message(chat_id=chat_id, text=cap, reply_markup=kb)
                except Exception as ex:
                    log_bot_error(chat_id, f"Failed fallback text send: {ex}", exc=ex)
        else:
            multi_cap = format_multi_product_caption(prods_to_send)
            cat_name = prods_to_send[0].get("category", "")
            kb = reply_markup if reply_markup is not None else get_multi_product_action_keyboard(prods_to_send, category=cat_name)
            if safe_send_fn:
                await safe_send_fn(chat_id=chat_id, text=multi_cap, reply_markup=kb)
            else:
                try:
                    await bot.send_message(chat_id=chat_id, text=multi_cap, reply_markup=kb)
                except Exception as ex:
                    log_bot_error(chat_id, f"Failed fallback text send: {ex}", exc=ex)

    # 1. Bitta tovar bo'lsa
    if len(prods_to_send) == 1:
        p = prods_to_send[0]
        img_url = p.get("image_url") or p.get("photo_id")
        caption = format_product_caption(p)
        kb = reply_markup if reply_markup is not None else get_single_product_keyboard(p)

        if img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("AgAC")):
            try:
                await asyncio.wait_for(
                    bot.send_photo(chat_id=chat_id, photo=img_url, caption=caption, parse_mode="Markdown", reply_markup=kb),
                    timeout=12.0
                )
                return True
            except Exception as e:
                # Broken URL or Telegram photo error -> Fallback to text only
                log_bot_error(chat_id, f"Broken image_url or photo send failed: {e}. Falling back to text.", exc=e)
                if safe_send_fn:
                    await safe_send_fn(chat_id=chat_id, text=caption, reply_markup=kb)
                else:
                    await bot.send_message(chat_id=chat_id, text=caption, reply_markup=kb)
                return True
        else:
            # Missing image_url -> text only
            if safe_send_fn:
                await safe_send_fn(chat_id=chat_id, text=caption, reply_markup=kb)
            else:
                await bot.send_message(chat_id=chat_id, text=caption, reply_markup=kb)
            return True

    # 2. Bir nechta tovar bo'lsa (max 3 ta media group)
    media_items = []
    for p in prods_to_send:
        img_url = p.get("image_url") or p.get("photo_id")
        if img_url and isinstance(img_url, str) and (img_url.startswith("http") or img_url.startswith("AgAC")):
            media_items.append(InputMediaPhoto(media=img_url))

    if len(media_items) >= 2:
        group_caption = format_multi_product_caption(prods_to_send)
        media_items[0].caption = group_caption
        media_items[0].parse_mode = "Markdown"
        try:
            await asyncio.wait_for(
                bot.send_media_group(chat_id=chat_id, media=media_items),
                timeout=15.0
            )

            # Media group muvaffaqiyatli ketgandan so'ng, xarid tugmalari va boshqa turlari taklifini yuborish
            cat_name = prods_to_send[0].get("category", "")
            from services.order_matcher import OrderMatcher
            var_info = OrderMatcher.get_category_variants(cat_name, exclude_ids=[p["id"] for p in prods_to_send]) if suggest_variants else None

            if var_info and var_info.get("other_variants"):
                kb = get_multi_product_action_keyboard(prods_to_send, category=var_info["category_key"], total_cat_count=var_info["total_count"])
                consultative_msg = var_info["summary_text"]
            else:
                kb = reply_markup if reply_markup is not None else get_multi_product_action_keyboard(prods_to_send, category=cat_name)
                consultative_msg = "Yuqoridagi tovarlardan birini xarid qilish yoki savatga qo'shish uchun quyidagi tugmalarni bosing 👇"

            if safe_send_fn:
                await safe_send_fn(chat_id=chat_id, text=consultative_msg, reply_markup=kb)
            else:
                await bot.send_message(chat_id=chat_id, text=consultative_msg, reply_markup=kb)

            return True
        except Exception as e:
            log_bot_error(chat_id, f"Media group send failed: {e}. Falling back to text.", exc=e)
            await _send_text_fallback()
            return True
    else:
        await _send_text_fallback()
        return True
