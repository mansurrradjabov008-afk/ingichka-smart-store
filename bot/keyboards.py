from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Asosiy menyu tugmalari"""
    buttons = [
        [KeyboardButton(text="🛍️ Katalog va Mahsulotlar"), KeyboardButton(text="🚚 Yetkazib berish")],
        [KeyboardButton(text="📞 Sotuvchi bilan bog'lanish"), KeyboardButton(text="📦 Mening buyurtmalarim")]
    ]
    
    if is_admin:
        buttons.append([KeyboardButton(text="📊 Do'kon Kassa Hisoboti"), KeyboardButton(text="⚠️ Ombor va Zakazlar")])
        buttons.append([KeyboardButton(text="📋 Oxirgi Buyurtmalar"), KeyboardButton(text="➕ Yangi tovar qo'shish")])
        buttons.append([KeyboardButton(text="📑 Excel Hisobotini Yuklab Olish"), KeyboardButton(text="📢 Mijozlarga Xabar")])
        buttons.append([KeyboardButton(text="🏢 SaaS Biznes Paneli"), KeyboardButton(text="💡 Nega Bu Bot? (Tijoriy Taklif)")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Qanday kiyim yoki tovar qidiryapsiz?..."
    )

def get_order_action_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Buyurtma bo'yicha tezkor harakat tugmalari (Admin uchun)"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Yetkazildi (Pul olindi)", callback_data=f"ord_done_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ord_cancel_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_category_keyboard() -> InlineKeyboardMarkup:
    """Kategoriyalar inline tugmalari"""
    buttons = [
        [InlineKeyboardButton(text="👔 Erkaklar kiyimi", callback_data="cat_Erkaklar kiyimi")],
        [InlineKeyboardButton(text="👗 Ayollar kiyimi", callback_data="cat_Ayollar kiyimi")],
        [InlineKeyboardButton(text="🧸 Bolalar kiyimi", callback_data="cat_Bolalar kiyimi")],
        [InlineKeyboardButton(text="👟 Poyabzallar va Krossovkalar", callback_data="cat_Poyabzallar va Krossovkalar")],
        [InlineKeyboardButton(text="👜 Sumka va aksessuarlar", callback_data="cat_Sumkalar va aksessuarlar")],
        [InlineKeyboardButton(text="🧖 Sochiqlar va to'qimachilik", callback_data="cat_Sochiqlar va uy to'qimachiligi")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_report_periods_keyboard() -> InlineKeyboardMarkup:
    """Hisobot davrlari inline tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="📅 Bugungi kun", callback_data="rep_day"),
            InlineKeyboardButton(text="📈 7 kunlik (Hafta)", callback_data="rep_week")
        ],
        [
            InlineKeyboardButton(text="📊 30 kunlik (Oy)", callback_data="rep_month"),
            InlineKeyboardButton(text="🏛️ 1 yillik hisobot", callback_data="rep_year")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_phone_request_keyboard() -> ReplyKeyboardMarkup:
    """Telefon raqamni 1-bosishda yuborish klaviaturasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamimni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_channel_buy_button(product_id: int, bot_username: str = "Markazsavdo00_bot") -> InlineKeyboardMarkup:
    """Telegram kanal postlari ostidagi xarid tugmasi"""
    clean_bot = bot_username.replace("@", "")
    buttons = [
        [InlineKeyboardButton(text="🛍️ Hoziroq xarid qilish (Lichka)", url=f"https://t.me/{clean_bot}?start=buy_{product_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

