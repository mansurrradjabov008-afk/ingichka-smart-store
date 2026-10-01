"""
B2B SaaS Multi-Store Menejeri.
Yangi do'konlarni (mijozlarni) 1 daqiqada platformaga ulash,
ular uchun alohida katalog va sozlamalarni yaratish moduli.
"""

import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path
from config import DB_PATH

class TenantManager:
    @staticmethod
    def init_stores_table():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                owner_phone TEXT,
                location TEXT NOT NULL,
                delivery_zone TEXT NOT NULL,
                bot_token TEXT UNIQUE,
                is_active INTEGER DEFAULT 1,
                subscription_plan TEXT DEFAULT 'standart', -- 'standart', 'premium'
                monthly_fee REAL DEFAULT 500000,           -- Oylik to'lov (so'mda)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def register_new_store(store_name: str, owner_name: str, location: str, delivery_zone: str, bot_token: str, owner_phone: str = "", monthly_fee: float = 500000) -> Dict[str, Any]:
        """Yangi do'konni SaaS platformasiga ulash"""
        TenantManager.init_stores_table()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO stores (store_name, owner_name, owner_phone, location, delivery_zone, bot_token, monthly_fee)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (store_name, owner_name, owner_phone, location, delivery_zone, bot_token, monthly_fee))
            store_id = cursor.lastrowid
            conn.commit()
            return {"success": True, "store_id": store_id, "message": f"'{store_name}' muvaffaqiyatli ro'yxatdan o'tdi!"}
        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_all_stores() -> List[Dict[str, Any]]:
        TenantManager.init_stores_table()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stores ORDER BY id DESC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def calculate_saas_mrr() -> Dict[str, Any]:
        """SaaS biznesingizning oylik daromadi (MRR - Monthly Recurring Revenue)"""
        stores = TenantManager.get_all_stores()
        active_stores = [s for s in stores if s["is_active"] == 1]
        mrr = sum(s["monthly_fee"] for s in active_stores)
        return {
            "total_clients": len(stores),
            "active_clients": len(active_stores),
            "monthly_recurring_revenue": mrr,
            "annual_run_rate": mrr * 12
        }
