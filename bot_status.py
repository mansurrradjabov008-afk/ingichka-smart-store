import sys
import socket
import json
import requests
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent

print("===================================================")
print("   INGICHKA SMART STORE - 24/7 TIZIM HOLATI")
print("===================================================")

# 1. Check Render Cloud Status
render_url = "https://ingichka-smart-store-bot.onrender.com"
try:
    r = requests.get(f"{render_url}/health", timeout=8)
    if r.status_code == 200:
        print(f"✅ RENDER CLOUD HOST: 100% UYG'OQ VA LIVE (24/7)")
    else:
        print(f"⚠️ RENDER CLOUD HOST: Qaytgan status kodi {r.status_code}")
except Exception as e:
    print(f"❌ RENDER CLOUD HOST: Ulanib bo'lmadi ({e})")

# 2. Check Telegram Webhook Status
try:
    from config import BOT_TOKEN
    r_tg = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=8)
    wh_data = r_tg.json().get("result", {})
    wh_url = wh_data.get("url", "")
    pending = wh_data.get("pending_update_count", 0)
    
    if wh_url == f"{render_url}/webhook":
        print(f"✅ TELEGRAM WEBHOOK: To'g'ri ulangan ({wh_url})")
        print(f"   Kutilayotgan xabarlar (Pending): {pending}")
    elif wh_url:
        print(f"⚠️ TELEGRAM WEBHOOK: Boshqa URL ga ulangan ({wh_url})")
    else:
        print(f"❌ TELEGRAM WEBHOOK: Bo'sh! Telegram Renderga ulanmagan.")
except Exception as e:
    print(f"❌ TELEGRAM API TEKSHIRUVI: {e}")

# 3. Check Local Sentinel
pid_files = [BASE_DIR / ".bot_sentinel.pid", BASE_DIR / ".bot_supervisor.pid"]
sentinel_active = False
sentinel_pid = None
for pf in pid_files:
    if pf.exists():
        try:
            p_val = int(pf.read_text(encoding="utf-8").strip())
            import subprocess
            res = subprocess.run(["tasklist", "/fi", f"PID eq {p_val}"], capture_output=True, text=True)
            if str(p_val) in res.stdout:
                sentinel_active = True
                sentinel_pid = p_val
                break
        except Exception:
            pass

if sentinel_active:
    print(f"✅ LOKAL SENTINEL (KOMPYUTERDA): Aktiv ishlab turibdi (PID: {sentinel_pid})")
    print("   (Renderni doimiy uyg'oq tutmoqda va Webhookni nazorat qilmoqda)")
else:
    print("ℹ️ LOKAL SENTINEL (KOMPYUTERDA): Kutish rejimida (yoki kompyuter o'chirilgan)")
    print("   (Eslatma: Bot Render Cloud serverida 24/7 ishlamoqda, kompyuter o'chiq bo'lsa ham bot to'xtamaydi!)")

# 4. Recent logs
log_file = BASE_DIR / "logs" / "bot_live.log"
if log_file.exists():
    print("\n📋 SO'NGGI LOGLAR (Oxirgi 10 qator):")
    print("---------------------------------------------------")
    try:
        lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines[-10:]:
            print(line)
    except Exception as e:
        print(f"Log o'qishda xatolik: {e}")
    print("---------------------------------------------------")
else:
    print("\nLog fayli hali mavjud emas.")
