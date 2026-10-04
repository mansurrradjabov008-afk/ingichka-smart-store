import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

PRODUCTS_FILE = Path(__file__).resolve().parent.parent / "products.json"
STORE_INFO_FILE = Path(__file__).resolve().parent.parent / "store_info.json"

def load_products() -> List[Dict[str, Any]]:
    """products.json faylidan barcha tovarlarni o'qish"""
    try:
        if PRODUCTS_FILE.exists():
            with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        pass
    return []

def load_store_info() -> Dict[str, Any]:
    """store_info.json faylidan do'kon ma'lumotlarini o'qish"""
    try:
        if STORE_INFO_FILE.exists():
            with open(STORE_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        pass
    return {}

def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    size: Optional[str] = None,
    color: Optional[str] = None,
    max_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    products.json bo'yicha tovarlarni qidirish vositasi (Tool).
    Case-insensitive, aliaslar va imlo variantlarini qidiradi.
    Natija: topilgan tovarlar va topilmagan holatda eng yaqin alternativlar.
    """
    all_products = load_products()
    matched: List[Dict[str, Any]] = []

    q_clean = query.lower().strip() if query else ""
    # Belgilarni tozalash
    q_words = re.findall(r"[\w']+", q_clean)

    for p in all_products:
        p_name = p.get("name", "").lower()
        p_cat = p.get("category", "").lower()
        p_sku = p.get("sku", "").lower()
        p_brand = p.get("brand", "").lower()
        p_aliases = [a.lower() for a in p.get("aliases", [])]
        p_sizes = [s.upper() for s in p.get("sizes", [])]
        p_colors = [c.lower() for c in p.get("colors", [])]
        p_price = float(p.get("price", 0))

        # 1. Query bo'yicha tekshiruv (nomi, SKU, brend, kategoriya yoki aliaslar)
        if q_clean:
            match_query = False
            # To'liq moslik yoki qism moslik
            if q_clean in p_name or q_clean in p_sku or q_clean in p_brand or any(q_clean in a or a in q_clean for a in p_aliases):
                match_query = True
            elif any(w in p_name or w in p_sku or w in p_brand or any(w in a for a in p_aliases) for w in q_words if len(w) >= 3):
                match_query = True
            
            if not match_query:
                continue

        # 2. Kategoriya filtri
        if category:
            cat_clean = category.lower().strip()
            if cat_clean not in p_cat:
                continue

        # 3. O'lcham (Size) filtri
        if size:
            size_clean = size.upper().strip()
            # Masalan: "42" yoki "L"
            if size_clean not in p_sizes and not any(size_clean in s for s in p_sizes):
                continue

        # 4. Rang (Color) filtri
        if color:
            color_clean = color.lower().strip()
            if not any(color_clean in c for c in p_colors):
                continue

        # 5. Narx (Max Price) filtri
        if max_price is not None:
            if p_price > float(max_price):
                continue

        # Tovarni qo'shish
        prod_copy = dict(p)
        stock = prod_copy.get("stock", 0)
        if stock <= 0:
            prod_copy["stock_status"] = "omborda yo'q"
        elif stock <= 2:
            prod_copy["stock_status"] = f"oxirgi {stock} ta qoldi"
        else:
            prod_copy["stock_status"] = f"{stock} dona bor"
        
        matched.append(prod_copy)

    # Agar so'ralgan tovar topilmagan bo'lsa, katalogdan eng yaqin alternativlarni topish
    closest_alternatives: List[Dict[str, Any]] = []
    if not matched:
        # Omborda bor tovarlarni alternativ sifatida berish
        in_stock_all = [p for p in all_products if p.get("stock", 0) > 0]
        if category:
            closest_alternatives = [p for p in in_stock_all if category.lower() in p.get("category", "").lower()]
        if not closest_alternatives:
            closest_alternatives = in_stock_all[:3]

    return {
        "found": len(matched) > 0,
        "count": len(matched),
        "products": matched,
        "closest_alternatives": closest_alternatives
    }

# LLM Tool Schema (OpenAI/Groq compatible)
SEARCH_PRODUCTS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_products",
        "description": "Search products catalog by query, category, size, color, or max_price in products.json. Returns product details, prices, sizes, and stock.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product name or alias, e.g. 'krasovka', 'krossovka', 'куртка', 'palto', 'futbolka'"
                },
                "category": {
                    "type": "string",
                    "description": "Category name, e.g. 'Erkaklar kiyimi', 'Ayollar kiyimi', 'Poyabzallar'"
                },
                "size": {
                    "type": "string",
                    "description": "Product size, e.g. 'S', 'M', 'L', 'XL', '40', '41', '42'"
                },
                "color": {
                    "type": "string",
                    "description": "Product color, e.g. 'qora', 'oq', 'qizil', 'bej', 'ko\\'k'"
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum price in UZS, e.g. 300000"
                }
            },
            "required": []
        }
    }
}
