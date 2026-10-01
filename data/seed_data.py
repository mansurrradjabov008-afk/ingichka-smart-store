import sys
import sqlite3
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database.db_manager import init_db, DatabaseManager, get_connection
from config import DB_PATH

NEW_PRODUCTS = [
    {
        "id": 1,
        "name": "Erkaklar qora kurtkasi",
        "category": "Erkaklar kiyimi",
        "size": "M, L, XL",
        "color": "qora",
        "cost_price": 320000,
        "sale_price": 450000,
        "stock_quantity": 5,
        "description": "Erkaklar uchun qalin va qulay qora kurtka. Shamol va sovuqdan ishonchli himoya qiladi."
    },
    {
        "id": 2,
        "name": "Oversize futbolka",
        "category": "Erkaklar kiyimi",
        "size": "S, M, L",
        "color": "oq, qora",
        "cost_price": 80000,
        "sale_price": 120000,
        "stock_quantity": 12,
        "description": "100% paxtali zamonaviy oversize futbolka. Yozgi va kundalik kiyish uchun qulay."
    },
    {
        "id": 3,
        "name": "Klassik jinsi shim",
        "category": "Erkaklar kiyimi",
        "size": "30, 32, 34",
        "color": "ko'k",
        "cost_price": 190000,
        "sale_price": 280000,
        "stock_quantity": 3,
        "description": "Sifatli matodan tikilgan klassik ko'k jinsi shim. Kundalik va ish uchun mos."
    },
    {
        "id": 4,
        "name": "Ayollar gulli ko'ylagi",
        "category": "Ayollar kiyimi",
        "size": "S, M",
        "color": "qizil, ko'k",
        "cost_price": 240000,
        "sale_price": 350000,
        "stock_quantity": 2,
        "description": "Nafis gulli bezakli ayollar ko'ylagi. Mayin va yoqimli mato."
    },
    {
        "id": 5,
        "name": "Sport kostyum",
        "category": "Erkaklar kiyimi",
        "size": "M, L, XL",
        "color": "kulrang, qora",
        "cost_price": 370000,
        "sale_price": 520000,
        "stock_quantity": 0,
        "description": "Sport va dam olish uchun qulay sport kostyum to'plami. Hozirda omborda vaqtincha tugagan."
    },
    {
        "id": 6,
        "name": "Ayollar qishki paltosi",
        "category": "Ayollar kiyimi",
        "size": "S, M, L",
        "color": "bej",
        "cost_price": 620000,
        "sale_price": 890000,
        "stock_quantity": 1,
        "description": "Issiq va bejirim qishki ayollar paltosi. Elegant ko'rinish va yuqori sifat."
    },
    {
        "id": 7,
        "name": "Kepka",
        "category": "Sumkalar va aksessuarlar",
        "size": "universal",
        "color": "qora, oq",
        "cost_price": 35000,
        "sale_price": 60000,
        "stock_quantity": 20,
        "description": "Zamonaviy universal razmerli kepka. Qora va oq ranglarda mavjud."
    },
    {
        "id": 8,
        "name": "Krossovka",
        "category": "Poyabzallar va Krossovkalar",
        "size": "40, 41, 42, 43",
        "color": "oq",
        "cost_price": 260000,
        "sale_price": 380000,
        "stock_quantity": 7,
        "description": "Oq rangli yengil va qulay sport krossovkasi. Kundalik yurish va yugurish uchun qulay taglik."
    }
]

def seed_database():
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        # Clean existing products table and reset IDs
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='products'")
        
        for p in NEW_PRODUCTS:
            cursor.execute("""
                INSERT INTO products (id, name, category, size, color, cost_price, sale_price, stock_quantity, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["id"], p["name"], p["category"], p["size"], p["color"],
                p["cost_price"], p["sale_price"], p["stock_quantity"], p["description"]
            ))
        conn.commit()
    print(f"✅ Muvaffaqiyatli: {len(NEW_PRODUCTS)} ta rasmiy mahsulot bazaga kiritildi!")

if __name__ == "__main__":
    seed_database()
