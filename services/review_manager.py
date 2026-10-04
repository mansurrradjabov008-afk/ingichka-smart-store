"""
services/review_manager.py
Mijozlar fikri va 5-Yulduzli Baholash Tizimi (Customer Rating & Review Module).
Har bir muvaffaqiyatli buyurtmadan so'ng xaridordan sifat bo'yicha fikr olish.
"""

from typing import Dict, Any, List, Optional
from database.db_manager import get_connection

class ReviewManager:
    """Mijozlar baholashi va sharhlari menejeri"""

    @staticmethod
    def init_reviews_table():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_name TEXT,
                    order_id INTEGER,
                    rating INTEGER NOT NULL,  -- 1 dan 5 gacha
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating);")
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def add_review(cls, user_id: int, user_name: str, rating: int, order_id: Optional[int] = None, comment: str = "") -> bool:
        cls.init_reviews_table()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reviews (user_id, user_name, order_id, rating, comment)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, user_name, order_id, rating, comment))
            conn.commit()
            return True
        finally:
            conn.close()

    @classmethod
    def get_store_rating(cls) -> Dict[str, Any]:
        """Do'konning umumiy reytingi va baholar soni"""
        cls.init_reviews_table()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), AVG(rating) FROM reviews")
            count, avg = cursor.fetchone()
            count = count or 0
            avg = round(float(avg), 1) if avg else 5.0
            return {
                "total_reviews": count,
                "average_rating": avg,
                "stars_display": "⭐️" * int(round(avg))
            }
        finally:
            conn.close()

    @classmethod
    def get_recent_reviews(cls, limit: int = 5) -> List[Dict[str, Any]]:
        cls.init_reviews_table()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_name, rating, comment, created_at
                FROM reviews
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
