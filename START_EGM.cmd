@echo off
chcp 65001 >nul
title EGM - рабочая система
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Первый запуск: ставлю компоненты, 1-3 минуты...
  where uv >nul 2>nul && (uv venv .venv && uv pip install --python .venv\Scripts\python.exe -r requirements.txt) || (python -m venv .venv && .venv\Scripts\python.exe -m pip install -r requirements.txt)
)
if not exist ".venv\Scripts\python.exe" (
  echo Не найден Python. Установите Python 3.11+ с python.org и запустите снова.
  pause & exit /b 1
)
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"
echo Система работает: http://localhost:8000
echo Для сотрудников в той же сети: http://ИМЯ-ИЛИ-IP-ЭТОГО-ПК:8000
echo Не закрывайте это окно - закрытие останавливает систему.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
