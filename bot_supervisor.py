"""
Ingichka Smart Store - 24/7 Bot Supervisor & Watchdog
Ushbu skript botni uzluksiz 24/7 rejimida ushlab turadi.
Agar bot xatolik tufayli to'xtasa yoki internet uzilsa,
uni darhol avtomatik tarzda qayta ishga tushiradi (Self-Healing).
"""

import sys
import os
import time
import subprocess
import signal
import socket
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "bot_live.log"
PID_FILE = BASE_DIR / ".bot_supervisor.pid"

LOCK_PORT = 49281

if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w")
    except Exception:
        pass

def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    import traceback
    err = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_event(f"CRITICAL UNCAUGHT EXCEPTION: {err}")

sys.excepthook = handle_uncaught_exception

_LOCK_SOCKET = None

def acquire_lock():
    """Yagona nusxa (single instance) kafolati"""
    global _LOCK_SOCKET
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        _LOCK_SOCKET = s
        return s
    except socket.error as e:
        log_event(f"[OGOHLANTIRISH] Port {LOCK_PORT} band ({e}). Bot supervisori allaqachon fonda ishlamoqda!")
        sys.exit(0)

def log_event(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [SUPERVISOR] {message}\n"
    try:
        if sys.stdout and not sys.stdout.closed:
            sys.stdout.write(entry)
            sys.stdout.flush()
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
            f.flush()
    except Exception:
        pass

def main():
    lock_sock = acquire_lock()
    supervisor_pid = os.getpid()
    PID_FILE.write_text(str(supervisor_pid), encoding="utf-8")
    
    log_event(f"24/7 Bot Supervisori ishga tushdi (PID: {supervisor_pid})")
    
    pythonw_path = Path(r"C:\Users\BRand\AppData\Local\Programs\Python\Python311\pythonw.exe")
    python_exe = str(pythonw_path) if pythonw_path.exists() else sys.executable
    bot_script = BASE_DIR / "bot" / "bot_app.py"
    
    # Graceful shutdown handler
    child_process = None
    
    def handle_exit(signum, frame):
        log_event("To'xtatish signali qabul qilindi. Bot yopilmoqda...")
        if child_process and child_process.poll() is None:
            child_process.terminate()
            try:
                child_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child_process.kill()
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    restart_count = 0
    while True:
        try:
            log_event(f"Bot ilovasi ishga tushirilmoqda ({bot_script})...")
            
            child_process = subprocess.Popen(
                [python_exe, "-u", str(bot_script)],
                cwd=str(BASE_DIR),
                env=os.environ.copy()
            )
            log_event(f"Bot jarayoni yaratildi (Child PID: {child_process.pid})")
            
            # Botning chiqishini kutish
            exit_code = child_process.wait()
            
            restart_count += 1
            log_event(f"Bot kodi chiqib ketdi (Kod: {exit_code}). 3 soniyadan so'ng qayta tiriltiriladi (Qayta yuklash #{restart_count})...")
            time.sleep(3)
            
        except Exception as e:
            log_event(f"Supervisorda xatolik: {e}. 5 soniyadan keyin qayta uriniladi...")
            time.sleep(5)

if __name__ == "__main__":
    main()
