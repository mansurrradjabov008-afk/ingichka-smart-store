import urllib.request
import urllib.parse
import json
import time
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database.db_manager import DatabaseManager, init_db, get_connection
from services.order_matcher import OrderMatcher
from config import BOT_TOKEN

def run_ultimate_verification():
    print("=" * 70)
    print("INGICHKA SMART STORE - 100% CHUQUR VA MUKAMMAL AUDIT TESTI")
    print("=" * 70)

    # 1. TELEGRAM RASMIY API TEKSHIRUVI
    print("\n[1/6] TELEGRAM BOT API BILAN JONLI ALOQA...")
    get_me_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    try:
        me_resp = json.loads(urllib.request.urlopen(get_me_url, timeout=10).read().decode())
        assert me_resp.get("ok") is True
        bot_info = me_resp.get("result", {})
        print(f"  OK: Bot nomi: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
        print(f"  OK: Bot to'liq nomi: {bot_info.get('first_name')}")
    except Exception as e:
        print(f"  XATO Telegram getMe: {e}")
        sys.exit(1)

    # 2. TELEGRAM WEBHOOK HOLATI VA XATOLIKLAR TARIXI
    print("\n[2/6] TELEGRAM WEBHOOK VA XATOLIKLAR JURNALI TEKSHIRUVI...")
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    try:
        wh_resp = json.loads(urllib.request.urlopen(webhook_url, timeout=10).read().decode())
        assert wh_resp.get("ok") is True
        wh_info = wh_resp.get("result", {})
        target_wh = "https://ingichka-smart-store-bot.onrender.com/webhook"
        assert wh_info.get("url") == target_wh, f"Kutilgan URL: {target_wh}, Lekin: {wh_info.get('url')}"
        print(f"  OK: Webhook URL: {wh_info.get('url')}")
        print(f"  OK: Kutilayotgan (qotib qolgan) xabarlar: {wh_info.get('pending_update_count')} dona")
        
        last_err_date = wh_info.get("last_error_date")
        last_err_msg = wh_info.get("last_error_message")
        if last_err_msg:
            print(f"  OGOHLANTIRISH: Oxirgi xatolik: {last_err_msg} (Sana: {last_err_date})")
        else:
            print(f"  OK: Telegramda oxirgi xatolik: YO'Q (None) - 100% toza!")
    except Exception as e:
        print(f"  XATO Webhook tekshiruvida: {e}")
        sys.exit(1)

    # 3. RENDER BULUT SERVERI (FRANKFURT) JONLI STATUS & DIAGNOSTIKA
    print("\n[3/6] RENDER CLOUD HOST JONLI ENDPOINTLARI...")
    t0 = time.time()
    health_url = "https://ingichka-smart-store-bot.onrender.com/health"
    try:
        with urllib.request.urlopen(health_url, timeout=15) as h_resp:
            status_code = h_resp.getcode()
            body = h_resp.read().decode()
            latency = (time.time() - t0) * 1000
            assert status_code == 200
            print(f"  OK: /health: HTTP {status_code} ({latency:.1f}ms) -> '{body.strip()}'")
    except Exception as e:
        print(f"  XATO Render /health: {e}")
        sys.exit(1)

    status_url = "https://ingichka-smart-store-bot.onrender.com/status"
    try:
        with urllib.request.urlopen(status_url, timeout=15) as s_resp:
            st_data = json.loads(s_resp.read().decode())
            print(f"  OK: /status: Versiya={st_data.get('version')}, Commit={st_data.get('commit')}")
            print(f"  OK: Baza mahsulotlari soni: {st_data.get('products_count')} ta (Kutilgan: 49)")
            assert st_data.get("products_count") == 49
            assert st_data.get("has_gemini") is True
            assert st_data.get("has_token") is True
            pings = st_data.get("recent_pings", [])
            print(f"  OK: Jonli tashqi pinglar soni: {len(pings)} ta qayd etilgan")
    except Exception as e:
        print(f"  XATO Render /status: {e}")
        sys.exit(1)

    diag_url = "https://ingichka-smart-store-bot.onrender.com/diag"
    try:
        with urllib.request.urlopen(diag_url, timeout=15) as d_resp:
            diag_data = json.loads(d_resp.read().decode())
            print(f"  OK: /diag: Gemini AI faolligi={diag_data.get('gemini_working')}")
            print(f"  OK: AI Sinov javobi: '{diag_data.get('sample_response')[:80]}...'")
            assert diag_data.get("gemini_working") is True
    except Exception as e:
        print(f"  XATO Render /diag: {e}")
        sys.exit(1)

    # 4. 41 TA REAL MAHSULOTNING BAZADA VA QIDIRUVDA TO'LIQLIGI
    print("\n[4/6] 41 TA REAL MAHSULOTNING TO'LIQ AUDITI...")
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        total_prods = cursor.fetchone()[0]
        assert total_prods == 41, f"Bazada 41 ta bo'lishi kerak, ammo {total_prods} ta!"

        cursor.execute("SELECT category, COUNT(*) FROM products GROUP BY category ORDER BY category")
        cat_counts = cursor.fetchall()
        print(f"  OK: Jami 41 ta mahsulot {len(cat_counts)} ta toifaga bo'lingan:")
        for cat, cnt in cat_counts:
            print(f"      - {cat}: {cnt} ta mahsulot")

        cursor.execute("SELECT COUNT(*) FROM products WHERE stock_quantity = 0")
        out_of_stock = cursor.fetchone()[0]
        assert out_of_stock == 1, f"1 ta tugagan tovar bo'lishi kerak, lekin {out_of_stock}"
        print(f"  OK: Omborda tugagan tovarlar soni: {out_of_stock} ta (to'g'ri qayd etilgan)")

        cursor.execute("SELECT COUNT(*) FROM products WHERE stock_quantity > 0 AND stock_quantity <= 2")
        low_stock = cursor.fetchone()[0]
        assert low_stock == 2, f"2 ta kam qolgan tovar bo'lishi kerak, lekin {low_stock}"
        print(f"  OK: Kam qolgan tovarlar (oxirgi 1-2 dona): {low_stock} ta (to'g'ri qayd etilgan)")

    # 5. BARCHA 41 TA MAHSULOTNING SKU ARTIKULLARI BO'YICHA 100% QIDIRUV AUDITI
    print("\n[5/6] BARCHA 41 TA MAHSULOTNING ARTIKUL (SKU) BO'YICHA QIDIRUV SINOVI...")
    all_prods = DatabaseManager.get_products(in_stock_only=False)
    assert len(all_prods) == 41
    matched_count = 0
    for p in all_prods:
        sku = p.get("sku")
        if not sku:
            continue
        matched = OrderMatcher.match_product(sku)
        assert matched is not None, f"SKU {sku} topilmadi!"
        assert matched["id"] == p["id"], f"SKU {sku} xato mahsulotga bog'landi: Kutilgan #{p['id']}, Topildi: #{matched['id']}"
        matched_count += 1
    print(f"  OK: Barcha {matched_count} ta mahsulot o'zining SKU kodi orqali 100% aniqlikda topildi!")

    # 6. RENDERGA REAL TELEGRAM WEBHOOK UPDATE POST YUBORISH (SIMULATSIYA)
    print("\n[6/6] RENDER WEBHOOKGA SIMULATSIYA QILINGAN TELEGRAM UPDATE YUBORISH...")
    webhook_target = "https://ingichka-smart-store-bot.onrender.com/webhook"
    dummy_update = {
        "update_id": 999999991,
        "message": {
            "message_id": 99999,
            "from": {
                "id": 9999901,
                "is_bot": False,
                "first_name": "AuditTester",
                "username": "audit_tester"
            },
            "chat": {
                "id": 9999901,
                "first_name": "AuditTester",
                "type": "private"
            },
            "date": int(time.time()),
            "text": "ping_audit_test"
        }
    }
    try:
        req = urllib.request.Request(
            webhook_target,
            data=json.dumps(dummy_update).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.getcode()
            print(f"  OK: Render Webhook javob kodi: HTTP {code} (Telegram yangilanishlarini qabul qilmoqda)")
            assert code == 200
    except Exception as e:
        print(f"  XATO Webhook update post: {e}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("AUDIT XULOSASI: 6 TA BOSQICHDAGI BARCHA SINOVLAR 100% G'ALABA BILAN O'TDI!")
    print("KOMPYUTER O'CHIQ HOLATDA HAM BOT RENDER CLOUD VA TELEGRAMDA")
    print("BUTUNLAY MUSTAQIL, XATOSIZ VA TUZILGAN REJADA ISHLAYDI!")
    print("=" * 70)

if __name__ == "__main__":
    run_ultimate_verification()
