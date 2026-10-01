import sqlite3
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        size TEXT NOT NULL,
        color TEXT NOT NULL,
        cost_price REAL NOT NULL,      -- Tan narxi (foydani hisoblash uchun)
        sale_price REAL NOT NULL,      -- Sotuv narxi
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        description TEXT,
        photo_id TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Customers Table (AI CRM xotirasi)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        telegram_id INTEGER PRIMARY KEY,
        full_name TEXT NOT NULL,
        username TEXT,
        phone TEXT,
        address TEXT,
        preferences TEXT,             -- AI eslab qoladigan xotira (o'lchami, yoqtirgan rangi)
        total_orders INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0.0,
        last_contact TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_telegram_id INTEGER,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        delivery_address TEXT NOT NULL,
        total_amount REAL NOT NULL,
        payment_method TEXT NOT NULL,  -- 'cash_on_delivery' yoki 'card_transfer'
        status TEXT NOT NULL DEFAULT 'yangi', -- 'yangi', 'yetkazilmoqda', 'yakunlandi', 'bekor'
        payment_status TEXT NOT NULL DEFAULT 'kutilmoqda', -- 'kutilmoqda', 'tolandi'
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_telegram_id) REFERENCES customers (telegram_id)
    );
    """)

    # 4. Order Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        size TEXT,
        color TEXT,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        cost_price REAL NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    );
    """)

    conn.commit()
    conn.close()

class DatabaseManager:
    @staticmethod
    def add_product(name: str, category: str, size: str, color: str, cost_price: float, sale_price: float, stock_quantity: int, description: str = "", photo_id: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (name, category, size, color, cost_price, sale_price, stock_quantity, description, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, category, size, color, cost_price, sale_price, stock_quantity, description, photo_id))
        product_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return product_id

    @staticmethod
    def get_products(category: Optional[str] = None, search_query: Optional[str] = None, in_stock_only: bool = True) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM products WHERE is_active = 1"
        params = []

        if in_stock_only:
            query += " AND stock_quantity > 0"
        if category:
            query += " AND category = ?"
            params.append(category)
        if search_query:
            query += " AND (name LIKE ? OR description LIKE ? OR color LIKE ?)"
            term = f"%{search_query}%"
            params.extend([term, term, term])

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def check_stock_strict(product_id: int, requested_qty: int = 1) -> Dict[str, Any]:
        """Nol gallutsinatsiya kafolati: Ombor qoldig'ini qat'iy tekshirish"""
        product = DatabaseManager.get_product_by_id(product_id)
        if not product:
            return {"available": False, "reason": "Mahsulot topilmadi"}
        if product["stock_quantity"] < requested_qty:
            return {
                "available": False,
                "current_stock": product["stock_quantity"],
                "reason": f"Omborda atigi {product['stock_quantity']} ta qolgan"
            }
        return {"available": True, "current_stock": product["stock_quantity"], "product": product}

    @staticmethod
    def upsert_customer(telegram_id: int, full_name: str, username: Optional[str] = None, phone: Optional[str] = None, address: Optional[str] = None, preferences: Optional[str] = None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        now = datetime.now()

        if row:
            cursor.execute("""
                UPDATE customers 
                SET full_name = COALESCE(?, full_name),
                    username = COALESCE(?, username),
                    phone = COALESCE(?, phone),
                    address = COALESCE(?, address),
                    preferences = CASE 
                        WHEN ? IS NOT NULL THEN (COALESCE(preferences, '') || ' | ' || ?)
                        ELSE preferences 
                    END,
                    last_contact = ?
                WHERE telegram_id = ?
            """, (full_name, username, phone, address, preferences, preferences, now, telegram_id))
        else:
            cursor.execute("""
                INSERT INTO customers (telegram_id, full_name, username, phone, address, preferences, last_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (telegram_id, full_name, username, phone, address, preferences, now))

        conn.commit()
        conn.close()

    @staticmethod
    def get_customer(telegram_id: int) -> Optional[Dict[str, Any]]:
        """Mijoz profilini CRM xotirasidan olish"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_customer_preferred_name(telegram_id: int, preferred_name: str):
        """Mijozning o'zi aytgan ismini (preferred_name) CRM-ga saqlash"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE customers SET preferred_name = ? WHERE telegram_id = ?", (preferred_name, telegram_id))
        conn.commit()
        conn.close()

    @staticmethod
    def create_order(customer_telegram_id: int, customer_name: str, customer_phone: str, delivery_address: str, items: List[Dict[str, Any]], payment_method: str, notes: str = "") -> Dict[str, Any]:
        """Buyurtmani to'liq xatosiz rasmiylashtirish va ombordan qoldiqni kamaytirish (Atomic transaction)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            total_amount = 0.0
            order_items_prepared = []

            # 1. Barcha tovarlar omborda bormi tekshiramiz
            for item in items:
                cursor.execute("SELECT * FROM products WHERE id = ?", (item["product_id"],))
                prod = cursor.fetchone()
                if not prod or prod["stock_quantity"] < item["quantity"]:
                    p_name = prod["name"] if prod else "Noma'lum"
                    avail = prod["stock_quantity"] if prod else 0
                    raise ValueError(f"Xatolik: '{p_name}' mahsulotidan omborda yetarli emas (Bor: {avail} ta, So'ralgan: {item['quantity']} ta)")

                subtotal = prod["sale_price"] * item["quantity"]
                total_amount += subtotal
                order_items_prepared.append({
                    "product_id": prod["id"],
                    "product_name": prod["name"],
                    "size": prod["size"],
                    "color": prod["color"],
                    "quantity": item["quantity"],
                    "unit_price": prod["sale_price"],
                    "cost_price": prod["cost_price"],
                    "subtotal": subtotal
                })

            # 2. Orders jadvaliga yozamiz
            cursor.execute("""
                INSERT INTO orders (customer_telegram_id, customer_name, customer_phone, delivery_address, total_amount, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (customer_telegram_id, customer_name, customer_phone, delivery_address, total_amount, payment_method, notes))
            order_id = cursor.lastrowid

            # 3. Order items yozish va Ombordan ayirish
            for it in order_items_prepared:
                cursor.execute("""
                    INSERT INTO order_items (order_id, product_id, product_name, size, color, quantity, unit_price, cost_price, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_id, it["product_id"], it["product_name"], it["size"], it["color"], it["quantity"], it["unit_price"], it["cost_price"], it["subtotal"]))

                cursor.execute("""
                    UPDATE products 
                    SET stock_quantity = stock_quantity - ? 
                    WHERE id = ? AND stock_quantity >= ?
                """, (it["quantity"], it["product_id"], it["quantity"]))
                if cursor.rowcount == 0:
                    raise ValueError(f"Xatolik: '{it['product_name']}' mahsulotidan omborda yetarli emas yoki ayni daqiqada boshqa xaridor tomonidan sotib olindi!")


            # 4. Mijoz statistikasini yangilash
            cursor.execute("""
                UPDATE customers 
                SET total_orders = total_orders + 1,
                    total_spent = total_spent + ?
                WHERE telegram_id = ?
            """, (total_amount, customer_telegram_id))

            conn.commit()
            return {"success": True, "order_id": order_id, "total_amount": total_amount, "items": order_items_prepared}

        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return None

        order_dict = dict(order)
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        order_dict["items"] = [dict(i) for i in cursor.fetchall()]
        conn.close()
        return order_dict

    @staticmethod
    def update_order_status(order_id: int, new_status: str) -> bool:
        """Buyurtma holatini yangilash (Yetkazildi yoki Bekor qilindi). Agar bekor qilinsa, omborga qaytariladi."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
            current_order = cursor.fetchone()
            if not current_order:
                conn.close()
                return False

            old_status = current_order["status"]
            if old_status == new_status:
                conn.close()
                return True

            # Agar buyurtma bekor qilinsa va oldin bekor bo'lmagan bo'lsa, omborga tovarlarni qaytarish
            if new_status == "bekor" and old_status != "bekor":
                cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
                items = cursor.fetchall()
                for it in items:
                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (it["quantity"], it["product_id"]))

            # Agar buyurtma yetkazib berilsa
            payment_status = "tolandi" if new_status == "yakunlandi" else "kutilmoqda"
            cursor.execute("UPDATE orders SET status = ?, payment_status = ? WHERE id = ?", (new_status, payment_status, order_id))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def get_recent_orders(limit: int = 10) -> List[Dict[str, Any]]:
        """Oxirgi buyurtmalarni olish"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
        orders = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return orders

    @staticmethod
    def get_customer_orders(customer_telegram_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Aynan bitta mijozning buyurtmalar tarixini olish"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM orders 
            WHERE customer_telegram_id = ? 
            ORDER BY id DESC LIMIT ?
        """, (customer_telegram_id, limit))
        orders = [dict(r) for r in cursor.fetchall()]
        for o in orders:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
            o["items"] = [dict(i) for i in cursor.fetchall()]
        conn.close()
        return orders

    @staticmethod
    def get_all_customers_ids() -> List[int]:
        """Reklama xabarlari yuborish uchun barcha mijozlarning Telegram ID larini olish"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id FROM customers")
        ids = [r["telegram_id"] for r in cursor.fetchall()]
        conn.close()
        return ids

