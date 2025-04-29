@echo off
echo Activando entorno virtual...
call venv\Scripts\activate.bat
pip install -r requirements.txt


echo Iniciando servidor WebSocket...
python app.py

pause