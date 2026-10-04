from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(is_admin: bool = False, cart_count: int = 0) -> ReplyKeyboardMarkup:
    """Asosiy menyu tugmalari (Jahon standarti: Katalog, Savatcha, Buyurtmalar, Promokodlar)"""
    cart_text = f"🛒 Savatcham ({cart_count})" if cart_count > 0 else "🛒 Savatcham"
    buttons = [
        [KeyboardButton(text="🛍️ Katalog va Mahsulotlar"), KeyboardButton(text=cart_text)],
        [KeyboardButton(text="📦 Mening buyurtmalarim"), KeyboardButton(text="🏷️ Aksiya va Promokodlar")],
        [KeyboardButton(text="🚚 Yetkazib berish"), KeyboardButton(text="📞 Sotuvchi bilan bog'lanish")]
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

def get_category_keyboard() -> InlineKeyboardMarkup:
    """Do'kondagi real tovar kategoriyalari inline tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="👕 Futbolkalar", callback_data="cat_Futbolka"),
            InlineKeyboardButton(text="👖 Jinsilar", callback_data="cat_Jinsi")
        ],
        [
            InlineKeyboardButton(text="👔 Ko'ylaklar", callback_data="cat_Ko'ylak"),
            InlineKeyboardButton(text="🧥 Kurtkalar", callback_data="cat_Kurtka")
        ],
        [
            InlineKeyboardButton(text="🧣 Paltolar", callback_data="cat_Palto"),
            InlineKeyboardButton(text="👖 Shimlar", callback_data="cat_Shim")
        ],
        [
            InlineKeyboardButton(text="🧢 Kepkalar", callback_data="cat_Kepka"),
            InlineKeyboardButton(text="🧦 Paypoqlar", callback_data="cat_Paypoq")
        ],
        [
            InlineKeyboardButton(text="🩲 Ichki kiyimlar", callback_data="cat_Ichki kiyim")
        ],
        [
            InlineKeyboardButton(text="🛒 Savatchaga o'tish", callback_data="open_cart")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_product_card_keyboard(product_id: int, category: str, current_idx: int, total_count: int) -> InlineKeyboardMarkup:
    """Interaktiv tovar kartochkasi: Savatga qo'shish, Tezkor xarid va Karusel sahifalash"""
    buttons = [
        [
            InlineKeyboardButton(text="🛒 Savatga qo'shish (+1)", callback_data=f"cart_add_{product_id}"),
            InlineKeyboardButton(text="⚡️ Hoziroq sotib olish", callback_data=f"fast_buy_{product_id}")
        ]
    ]

    # Sahifalash tugmalari
    nav_row = []
    if current_idx > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"p_nav_{category}_{current_idx - 1}"))
    else:
        nav_row.append(InlineKeyboardButton(text="⏹", callback_data="ignore"))

    nav_row.append(InlineKeyboardButton(text=f"{current_idx + 1} / {total_count}", callback_data="ignore"))

    if current_idx < total_count - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"p_nav_{category}_{current_idx + 1}"))
    else:
        nav_row.append(InlineKeyboardButton(text="⏹", callback_data="ignore"))

    buttons.append(nav_row)
    buttons.append([
        InlineKeyboardButton(text="🔙 Bo'limlar", callback_data="p_cats"),
        InlineKeyboardButton(text="🛒 Savatcham", callback_data="open_cart")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cart_keyboard(cart_items: list, has_promo: bool = False) -> InlineKeyboardMarkup:
    """Interaktiv Savat boshqaruvi (+, -, o'chirish, promokod va buyurtma)"""
    buttons = []

    for item in cart_items:
        p_id = item["product_id"]
        qty = item["quantity"]
        p_name = item["name"][:14]
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"cart_dec_{p_id}"),
            InlineKeyboardButton(text=f"{p_name} ({qty})", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_inc_{p_id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"cart_del_{p_id}")
        ])

    if has_promo:
        buttons.append([
            InlineKeyboardButton(text="❌ Promokodni bekor qilish", callback_data="cart_promo_del")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🏷 Promokod kiritish", callback_data="cart_promo_add")
        ])

    buttons.append([
        InlineKeyboardButton(text="🛍 Buyurtma berish (Checkout)", callback_data="cart_checkout")
    ])

    buttons.append([
        InlineKeyboardButton(text="🧹 Savatni tozalash", callback_data="cart_clear"),
        InlineKeyboardButton(text="🛍 Xaridni davom ettirish", callback_data="p_cats")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_order_action_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Buyurtma holatini bosqichma-bosqich boshqarish (Admin uchun)"""
    buttons = [
        [
            InlineKeyboardButton(text="🟠 Qadoqlash", callback_data=f"ord_prep_{order_id}"),
            InlineKeyboardButton(text="🚚 Kuryerga berish", callback_data=f"ord_ship_{order_id}")
        ],
        [
            InlineKeyboardButton(text="✅ Yetkazildi (Yakunlash)", callback_data=f"ord_done_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ord_cancel_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_order_approval_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Yangi buyurtma uchun admin tasdiqlash tugmalari (Task 3: Qabul qilindi / Bekor qilish)"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Qabul qilindi", callback_data=f"ord_done_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ord_cancel_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_review_stars_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """5 yulduzli baholash tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="⭐️ 1", callback_data=f"rev_{order_id}_1"),
            InlineKeyboardButton(text="⭐️ 2", callback_data=f"rev_{order_id}_2"),
            InlineKeyboardButton(text="⭐️ 3", callback_data=f"rev_{order_id}_3"),
            InlineKeyboardButton(text="⭐️ 4", callback_data=f"rev_{order_id}_4"),
            InlineKeyboardButton(text="⭐️ 5", callback_data=f"rev_{order_id}_5")
        ]
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

def get_location_request_keyboard() -> ReplyKeyboardMarkup:
    """Geolokatsiyani 1-bosishda yuborish klaviaturasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Geolokatsiyamni yuborish", request_location=True)],
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
