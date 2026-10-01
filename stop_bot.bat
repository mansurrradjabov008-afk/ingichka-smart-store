@echo off
title Ingichka Botini To'xtatish
echo ===================================================
echo   Ingichka Baraka Savdo AI Boti To'xtatilmoqda...
echo ===================================================

cd /d "%~dp0"
python -c "
import os, signal, sys
from pathlib import Path

pid_file = Path('.bot_supervisor.pid')
if pid_file.exists():
    try:
        pid = int(pid_file.read_text().strip())
        print(f'Supervisor (PID {pid}) to\'xtatilmoqda...')
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
    except Exception as e:
        print(f'Xato: {e}')
else:
    print('Supervisor PID fayli topilmadi.')
"

taskkill /F /IM pythonw.exe /T 2>nul
taskkill /F /FI "WINDOWTITLE eq *Ingichka*" 2>nul

echo ===================================================
echo   Bot to'liq to'xtatildi!
echo ===================================================
timeout /t 3
