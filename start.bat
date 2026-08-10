@echo off
echo Activando entorno virtual y ejecutando el servidor...
call .venv\Scripts\activate.bat
python back\app.py
pause
