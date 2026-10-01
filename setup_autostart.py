"""
Windows Auto-Start Sozlagich (Avtomatik ishga tushirish)
Ushbu skript kompyuter yoqilganda (Windows ochilganda)
botni avtomatik ravishda orqa fonda (yashirin) ishga tushiradigan qilib sozlaydi.
"""

import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

def setup_startup():
    startup_dir = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
    if not startup_dir.exists():
        print(f"Startup papkasi topilmadi: {startup_dir}")
        return False

    current_dir = Path(__file__).resolve().parent
    vbs_launcher = current_dir / "start_silent.vbs"
    
    target_vbs = startup_dir / "StartIngichkaBot.vbs"
    
    content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{str(current_dir)}"
WshShell.Run """{str(vbs_launcher)}""", 0, False
'''
    target_vbs.write_text(content, encoding="utf-8")
    print(f"✅ Windows Startup avto-ishga tushirish muvaffaqiyatli o'rnatildi!")
    print(f"Fayl: {target_vbs}")
    print(f"Endi kompyuteringiz yoqilishi bilan bot avtomatik orqa fonda ishga tushadi.")
    return True

if __name__ == "__main__":
    setup_startup()
