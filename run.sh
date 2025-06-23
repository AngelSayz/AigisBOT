#!/bin/bash

echo "🎵 Iniciando Bot de Música para Discord..."
echo

# Activar el entorno virtual
source bin/activate

# Verificar si las dependencias están instaladas
python -c "import discord, yt_dlp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Instalando dependencias..."
    pip install -r requirements.txt
    echo
fi

# Ejecutar el bot
echo "🚀 Ejecutando el bot..."
python bot.py

echo
echo "🛑 Bot detenido." 