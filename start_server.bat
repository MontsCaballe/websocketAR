@echo off
echo Activando entorno virtual...
call venv\Scripts\activate.bat

echo Iniciando servidor WebSocket...
python app.py

pause