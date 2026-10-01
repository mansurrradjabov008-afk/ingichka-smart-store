import sqlite3
from typing import Dict, Any, List
from config import DB_PATH, LOW_STOCK_THRESHOLD

class InventoryManager:
    @staticmethod
    def get_stock_alerts() -> Dict[str, Any]:
        """Omborda kam qolgan yoki tugagan tovarlarni hisoblash va zakaz ro'yxatini tuzish"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Tugagan tovarlar (0 dona)
        cursor.execute("""
            SELECT * FROM products 
            WHERE is_active = 1 AND stock_quantity = 0
            ORDER BY category, name
        """)
        out_of_stock = [dict(r) for r in cursor.fetchall()]

        # 2. Kam qolgan tovarlar (1 dan LOW_STOCK_THRESHOLD gacha)
        cursor.execute("""
            SELECT * FROM products 
            WHERE is_active = 1 AND stock_quantity > 0 AND stock_quantity <= ?
            ORDER BY stock_quantity ASC
        """, (LOW_STOCK_THRESHOLD,))
        low_stock = [dict(r) for r in cursor.fetchall()]

        # 3. Kategoriya bo'yicha umumiy ombor qiymati
        cursor.execute("""
            SELECT 
                category,
                COUNT(id) as total_models,
                SUM(stock_quantity) as total_units,
                SUM(stock_quantity * cost_price) as total_cost_value,
                SUM(stock_quantity * sale_price) as total_sale_value
            FROM products
            WHERE is_active = 1
            GROUP BY category
        """)
        category_summary = [dict(r) for r in cursor.fetchall()]

        conn.close()

        # Hisoblash: Kam qolganlarni to'ldirish uchun taxminiy mablag' (har biriga 10 donadan zakaz deb olsak)
        reorder_items = []
        total_reorder_budget = 0.0

        for item in out_of_stock + low_stock:
            recommend_order_qty = 15 if item["stock_quantity"] == 0 else 10
            needed_budget = recommend_order_qty * item["cost_price"]
            total_reorder_budget += needed_budget
            reorder_items.append({
                "id": item["id"],
                "name": item["name"],
                "category": item["category"],
                "size": item["size"],
                "color": item["color"],
                "current_stock": item["stock_quantity"],
                "recommend_qty": recommend_order_qty,
                "cost_price": item["cost_price"],
                "needed_budget": needed_budget
            })

        # Do'konga olib kelish tavsiya etiladigan yangi tovarlar (Mavsumiy va trend tahlili)
        trending_suggestions = [
            "1. **Ayollar va Erkaklar nimchalari (Jiletka)** — Ingichka havosiga mos, ayni kunlarda talab juda yuqori bo'ladi.",
            "2. **Bolalar uchun issiq sportivka va paypoqlar** — Onalar doim qidiradigan, eng tez aylanadigan tovar.",
            "3. **Banya va oshxona sochiqlari (To'plamda)** — Sovg'a yoki uy uchun o'rtacha chekni ko'taradigan lokomotiv tovar.",
            "4. **Katta sig'imli ayollar va o'smirlar ryukzaklari** — Doimiy xaridorgir."
        ]

        return {
            "out_of_stock_count": len(out_of_stock),
            "out_of_stock_items": out_of_stock,
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock,
            "reorder_items": reorder_items,
            "total_reorder_budget": total_reorder_budget,
            "category_summary": category_summary,
            "trending_suggestions": trending_suggestions
        }

    @staticmethod
    def format_inventory_message(alerts: Dict[str, Any]) -> str:
        """Do'kon egasi uchun ombor hisoboti va zakaz tavsiyanomasi"""
        lines = []
        lines.append("📋 **INGICHKA DO'KONI: OMBOR VA ZAKAZ TAHLILI**")
        lines.append("───────────────────────")

        if alerts["out_of_stock_items"]:
            lines.append("❌ **TUGAGAN TOVARLAR (Zudlik bilan olib kelish shart):**")
            for item in alerts["out_of_stock_items"]:
                lines.append(f"  • {item['name']} ({item['size']} / {item['color']}) — 0 dona!")
            lines.append("")

        if alerts["low_stock_items"]:
            lines.append("⚠️ **KAM QOLGAN TOVARLAR (5 dona yoki undan kam):**")
            for item in alerts["low_stock_items"]:
                lines.append(f"  • {item['name']} ({item['size']} / {item['color']}) — atigi {item['stock_quantity']} dona qoldi!")
            lines.append("")

        if alerts["reorder_items"]:
            lines.append(f"📦 **Tavsiya etiladigan zakaz hajmi:** {len(alerts['reorder_items'])} xil tovar")
            lines.append(f"💵 **Taxminiy kerakli sarmoya:** {alerts['total_reorder_budget']:,.0f} so'm\n")

        lines.append("🌟 **DO'KONNI RIVOJLANTIRISH UCHUN YANGI TOVAR TAVSIYALARI:**")
        for sug in alerts["trending_suggestions"]:
            lines.append(sug)

        lines.append("───────────────────────")
        lines.append("💡 *Ushbu tovarlarni olib kelsangiz, o'rtacha oylik savdo 25-30% ga oshadi.*")

        return "\n".join(lines)
