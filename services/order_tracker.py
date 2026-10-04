"""
services/order_tracker.py
Buyurtmalarni real-vaqtda kuzatish va Mijozga status o'zgarishi haqida xabarnoma (Push Notification) yuborish.
"""

from typing import List, Dict, Any, Optional
from database.db_manager import get_connection

STATUS_MAP = {
    "yangi": {
        "label": "🟡 Qabul qilindi",
        "desc": "Buyurtmangiz muvaffaqiyatli qabul qilindi va tizimda tasdiqlandi.",
        "progress": "🟡⚪⚪⚪"
    },
    "tayyorlanmoqda": {
        "label": "🟠 Qadoqlanmoqda",
        "desc": "Tovarlaringiz ombordan olinib, ehtiyotkorlik bilan qadoqlanmoqda.",
        "progress": "🟢🟠⚪⚪"
    },
    "yetkazilmoqda": {
        "label": "🚚 Yo'lda (Kuryerga berildi)",
        "desc": "Kuryer buyurtmangizni olib, manzilingiz tomon yo'lga chiqdi!",
        "progress": "🟢🟢🚚⚪"
    },
    "yakunlandi": {
        "label": "🟢 Yetkazildi (Yakunlandi)",
        "desc": "Buyurtma topshirildi va to'lov muvaffaqiyatli amalga oshirildi. Rahmat!",
        "progress": "🟢🟢🟢✅"
    },
    "bekor": {
        "label": "❌ Bekor qilingan",
        "desc": "Ushbu buyurtma bekor qilingan.",
        "progress": "❌❌❌❌"
    }
}

class OrderTracker:
    """Mijoz buyurtmalarini kuzatish tizimi"""

    @staticmethod
    def get_customer_orders(customer_telegram_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Mijozning oxirgi buyurtmalarini olish"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, total_amount, payment_method, status, payment_status, created_at, delivery_address, notes
                FROM orders
                WHERE customer_telegram_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (customer_telegram_id, limit))
            orders_rows = cursor.fetchall()

            orders = []
            for row in orders_rows:
                ord_dict = dict(row)
                # Order items
                cursor.execute("""
                    SELECT product_name, size, color, quantity, unit_price, subtotal
                    FROM order_items
                    WHERE order_id = ?
                """, (ord_dict["id"],))
                ord_dict["items"] = [dict(r) for r in cursor.fetchall()]
                orders.append(ord_dict)
            return orders
        finally:
            conn.close()

    @staticmethod
    def format_orders_view(customer_name: str, orders: List[Dict[str, Any]]) -> str:
        """Mijoz uchun chiroyli buyurtmalar paneli"""
        if not orders:
            return (
                f"👤 Hurmatli **{customer_name}**, sizda hozircha rasmiylashtirilgan buyurtmalar yo'q.\n\n"
                "Katalogimizdan kiyim tanlab, birinchi buyurtmangizni berishingiz mumkin! 🛍"
            )

        lines = [f"📦 **SIZNING BUYURTMALARINGIZ ({len(orders)} ta):**\n"]
        for o in orders:
            st_info = STATUS_MAP.get(o["status"], STATUS_MAP["yangi"])
            lines.append(f"🔖 **Buyurtma #{o['id']}** ({o['created_at'][:16]})")
            lines.append(f"Holati: **{st_info['label']}**")
            lines.append(f"Bosqich: `{st_info['progress']}`")
            lines.append(f"Summa: **{o['total_amount']:,.0f} so'm**")

            if o.get("items"):
                items_str = ", ".join([f"{i['product_name']} ({i['quantity']}x)" for i in o["items"][:3]])
                lines.append(f"Tovarlar: {items_str}")

            lines.append("─────────────────────────")

        lines.append("💡 *Agar buyurtmangiz bo'yicha savol tug'ilsa, istalgan vaqtda yozishingiz mumkin!*")
        return "\n".join(lines)

    @staticmethod
    def format_status_notification(order_id: int, new_status: str, customer_name: str) -> str:
        """Status o'zgarganda mijozga yuboriladigan avtomatik xabar"""
        st_info = STATUS_MAP.get(new_status, STATUS_MAP["yangi"])
        return (
            f"🔔 **BUYURTMA HOLATI YANGILANDI!**\n\n"
            f"Hurmatli **{customer_name}**!\n"
            f"Sizning **#{order_id}-sonli** buyurtmangiz holati o'zgardi:\n\n"
            f"📌 **{st_info['label']}**\n"
            f"⚡️ `{st_info['progress']}`\n\n"
            f"ℹ️ {st_info['desc']}\n\n"
            f"Xaridingiz uchun tashakkur! Savollaringiz bo'lsa, xizmatdamiz."
        )
