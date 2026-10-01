import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List
from config import DB_PATH, CRISIS_THRESHOLD_DROP_PCT

class AnalyticsAdvisor:
    @staticmethod
    def get_sales_report(period: str = "day") -> Dict[str, Any]:
        """
        period: 'day' (1 kun), 'week' (1 hafta), 'month' (1 oy), 'year' (1 yil)
        Hisobot: Tushum, Xarajat, Sof Foyda, Buyurtmalar soni, Eng ko'p sotilgan tovarlar.
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        now = datetime.now()
        if period == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = "Bugungi kunlik hisobot"
            prev_start = start_date - timedelta(days=1)
            prev_end = start_date
        elif period == "week":
            start_date = now - timedelta(days=7)
            period_label = "Oxirgi 7 kunlik (Haftalik) hisobot"
            prev_start = start_date - timedelta(days=7)
            prev_end = start_date
        elif period == "month":
            start_date = now - timedelta(days=30)
            period_label = "Oxirgi 30 kunlik (Oylik) hisobot"
            prev_start = start_date - timedelta(days=30)
            prev_end = start_date
        elif period == "year":
            start_date = now - timedelta(days=365)
            period_label = "Oxirgi 1 yillik hisobot"
            prev_start = start_date - timedelta(days=365)
            prev_end = start_date
        else:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = "Bugungi hisobot"
            prev_start = start_date - timedelta(days=1)
            prev_end = start_date

        start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
        prev_start_str = prev_start.strftime("%Y-%m-%d %H:%M:%S")
        prev_end_str = prev_end.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Hozirgi davr moliyasi
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT o.id) as orders_count,
                COALESCE(SUM(oi.subtotal), 0) as total_revenue,
                COALESCE(SUM(oi.cost_price * oi.quantity), 0) as total_cost,
                COALESCE(SUM(oi.quantity), 0) as total_items_sold
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status != 'bekor' AND o.created_at >= ?
        """, (start_str,))
        current_stats = dict(cursor.fetchone())

        revenue = current_stats["total_revenue"]
        cost = current_stats["total_cost"]
        net_profit = revenue - cost
        margin_pct = (net_profit / revenue * 100) if revenue > 0 else 0.0

        # 2. O'tgan ekvivalent davr moliyasi (Taqqoslash va O'sish/Inqiroz tahlili)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(oi.subtotal), 0) as prev_revenue
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status != 'bekor' AND o.created_at >= ? AND o.created_at < ?
        """, (prev_start_str, prev_end_str))
        prev_stats = dict(cursor.fetchone())
        prev_rev = prev_stats["prev_revenue"]

        # O'sish yoki Pasayish foizi
        if prev_rev > 0:
            growth_pct = ((revenue - prev_rev) / prev_rev) * 100
        else:
            growth_pct = 100.0 if revenue > 0 else 0.0

        # Inqiroz signali
        is_crisis = False
        crisis_warning = ""
        if prev_rev > 0 and growth_pct < -CRISIS_THRESHOLD_DROP_PCT:
            is_crisis = True
            crisis_warning = f"⚠️ DIQQAT XAVF: Savdo o'tgan davrga nisbatan {abs(growth_pct):.1f}% ga tushib ketdi! Zudlik bilan faollashtiruvchi aksiyalar kerak."

        # 3. Eng ko'p sotilgan top 5 tovar
        cursor.execute("""
            SELECT 
                oi.product_name,
                oi.size,
                oi.color,
                SUM(oi.quantity) as total_sold,
                SUM(oi.subtotal) as total_revenue
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.status != 'bekor' AND o.created_at >= ?
            GROUP BY oi.product_id, oi.size, oi.color
            ORDER BY total_sold DESC
            LIMIT 5
        """, (start_str,))
        top_products = [dict(r) for r in cursor.fetchall()]

        # 4. Kategoriya bo'yicha tushum
        cursor.execute("""
            SELECT 
                p.category,
                SUM(oi.quantity) as qty_sold,
                SUM(oi.subtotal) as category_revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN orders o ON o.id = oi.order_id
            WHERE o.status != 'bekor' AND o.created_at >= ?
            GROUP BY p.category
            ORDER BY category_revenue DESC
        """, (start_str,))
        category_breakdown = [dict(r) for r in cursor.fetchall()]

        conn.close()

        # Maslahat shakllantirish
        advice = AnalyticsAdvisor._generate_expert_advice(period, revenue, net_profit, growth_pct, is_crisis, top_products)

        return {
            "period": period,
            "period_label": period_label,
            "orders_count": current_stats["orders_count"],
            "total_revenue": revenue,
            "total_cost": cost,
            "net_profit": net_profit,
            "margin_pct": round(margin_pct, 1),
            "growth_pct": round(growth_pct, 1),
            "is_crisis": is_crisis,
            "crisis_warning": crisis_warning,
            "items_sold": current_stats["total_items_sold"],
            "top_products": top_products,
            "category_breakdown": category_breakdown,
            "expert_advice": advice
        }

    @staticmethod
    def _generate_expert_advice(period: str, revenue: float, profit: float, growth: float, is_crisis: bool, top_prods: List[Dict]) -> str:
        """15 yillik biznes maslahatchi tahlili va tavsiyalari"""
        advices = []
        
        if is_crisis:
            advices.append("1. **Tezkor Savdo Taktikasi:** Guruhda faoliyat susaygan. Ingichka aholisi uchun 'Faqat bugun buyurtma berganga sochiq yoki sumka sovg'a' aksiyasini e'lon qiling.")
            advices.append("2. **To'g'ridan-to'g'ri aloqa:** O'tgan oy xarid qilgan mijozlarga lichkada yangi tovarlar haqida samimiy eslatma yuboring.")
        elif growth > 15:
            advices.append("1. **Trenddan maksimal foydalanish:** Savdo yuqori o'smoqda (+{:.1f}%). Eng ommabop modellarning qoldig'ini zudlik bilan to'ldiring, tovar uzilib qolmasin.".format(growth))
            advices.append("2. **O'rtacha chekni oshirish (Cross-sell):** Kiyim xarid qilganlarga mos aksessuarlar yoki sochiqlarni chegirma bilan taklif qiling.")
        else:
            advices.append("1. **Stabil holat:** Savdo maromi yaxshi. Savdoni 20% ga oshirish uchun mavsumiy tovarlar (kuzgi/qishki issiq kiyimlar) assortimentini kengaytirish ayni muddao.")

        if top_prods:
            best_seller = top_prods[0]["product_name"]
            advices.append(f"2. **Lokomotiv Tovar:** '{best_seller}' eng ko'p talab qilinmoqda. Uning yoniga mos qo'shimcha tovarlarni guruhga video obzor qilib chiqaring.")
        else:
            advices.append("2. **Assortiment faolligi:** Yangi kelgan tovarlarni yaxshi sifatli rasm va o'lchamlari bilan guruhga ko'proq joylashtiring.")

        advices.append("3. **Ingichka bo'ylab tezkor yetkazish:** 30 daqiqada eshigingizgacha bepul yetkazib berish xizmatini har bir postda ta'kidlang — bu sizning eng katta mahalliy ustunligingiz!")

        return "\n".join(advices)

    @staticmethod
    def format_report_message(report: Dict[str, Any]) -> str:
        """Do'kon egasiga Telegram orqali chiroyli formatda yetkazish"""
        lines = []
        lines.append(f"📊 **{report['period_label']}**")
        lines.append("───────────────────────")
        lines.append(f"💰 **Jami tushum:** {report['total_revenue']:,.0f} so'm")
        lines.append(f"💵 **Sof foyda:** {report['net_profit']:,.0f} so'm ({report['margin_pct']}%)")
        lines.append(f"📦 **Buyurtmalar soni:** {report['orders_count']} ta ({report['items_sold']} dona tovar)")

        growth_icon = "📈" if report["growth_pct"] >= 0 else "📉"
        lines.append(f"{growth_icon} **Dinamika:** {report['growth_pct']:+.1f}% (o'tgan davrga nisbatan)")

        if report["is_crisis"]:
            lines.append(f"\n{report['crisis_warning']}")

        if report["top_products"]:
            lines.append("\n🔥 **Eng ko'p sotilgan tovarlar:**")
            for i, p in enumerate(report["top_products"], 1):
                lines.append(f"  {i}. {p['product_name']} ({p['size']}/{p['color']}) — {p['total_sold']} dona ({p['total_revenue']:,.0f} so'm)")

        lines.append("\n💡 **25 Yillik Ekspert Maslahati (Siz uchun):**")
        lines.append(report["expert_advice"])
        lines.append("───────────────────────")
        lines.append("📍 *Ingichka Baraka Savdo Markazi*")

        return "\n".join(lines)
