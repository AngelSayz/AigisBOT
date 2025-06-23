@echo off
echo 🎵 Iniciando Bot de Musica para Discord...
echo.

REM Activar el entorno virtual
call Scripts\activate.bat

REM Verificar si las dependencias están instaladas
python -c "import discord, yt_dlp" 2>nul
if errorlevel 1 (
    echo ⚠️  Instalando dependencias...
    pip install -r requirements.txt
    echo.
)

REM Ejecutar el bot
echo 🚀 Ejecutando el bot...
python bot.py

echo.
echo 🛑 Bot detenido. Presiona cualquier tecla para salir...
pause >nul 