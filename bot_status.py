import sys
import socket
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent

# Check socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(('127.0.0.1', 49281))
    s.close()
    print("❌ BOT HOZIR ISHLAMAYAPTI (To'xtagan)!")
    print("Uni ishga tushirish uchun start_silent.vbs yoki start_bot.bat ni ishga tushiring.")
except socket.error:
    print("✅ BOT HOZIR FONDA (24/7) AKTIV ISHLAYAPTI!")

log_file = BASE_DIR / "logs" / "bot_live.log"
if log_file.exists():
    print("\n📋 SO'NGGI LOGLAR (Oxirgi 15 qator):")
    print("---------------------------------------------------")
    try:
        lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines[-15:]:
            print(line)
    except Exception as e:
        print(f"Log o'qishda xatolik: {e}")
    print("---------------------------------------------------")
else:
    print("\nLog fayli hali yaratilmagan.")
