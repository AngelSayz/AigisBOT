# 🎵 Bot de Música para Discord

Un bot de música completo para Discord que reproduce audio desde YouTube usando `discord.py`, `yt-dlp` y `FFmpeg`.

## 🚀 Características

- ✅ Reproducción de música desde YouTube (URLs o búsquedas)
- ✅ Cola de reproducción por servidor (FIFO)
- ✅ Comandos básicos: play, pause, resume, skip, stop, queue
- ✅ Interfaz en español con emojis
- ✅ Manejo de errores robusto
- ✅ Uso correcto de `asyncio`
- ✅ Embeds de Discord para mejor presentación

## 📋 Comandos Disponibles

| Comando | Alias | Descripción |
|---------|-------|-------------|
| `!play [búsqueda/URL]` | `!p` | Reproduce una canción desde YouTube |
| `!pause` | - | Pausa la música actual |
| `!resume` | - | Reanuda la música pausada |
| `!skip` | `!s` | Salta a la siguiente canción |
| `!stop` | - | Detiene la música y desconecta el bot |
| `!queue` | `!q` | Muestra la cola de reproducción |
| `!now` | `!np` | Muestra la canción actual |
| `!help` | `!ayuda` | Muestra la lista de comandos |

## 🛠️ Instalación Paso a Paso

### 1. Requisitos Previos

#### Instalar Python 3.8+
- Descarga desde [python.org](https://www.python.org/downloads/)
- Durante la instalación, marca "Add Python to PATH"

#### Instalar FFmpeg
**Windows:**
1. Descarga FFmpeg desde [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extrae el archivo zip
3. Copia la carpeta a `C:\ffmpeg`
4. Añade `C:\ffmpeg\bin` a las variables de entorno PATH

**macOS (con Homebrew):**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

### 2. Crear el Bot en Discord

1. Ve a [Discord Developer Portal](https://discord.com/developers/applications)
2. Haz clic en "New Application"
3. Dale un nombre a tu aplicación
4. Ve a la sección "Bot" en el menú izquierdo
5. Haz clic en "Add Bot"
6. Copia el **Token** (lo necesitarás más tarde)
7. En "Privileged Gateway Intents", activa:
   - ✅ **Message Content Intent**
   - ✅ **Server Members Intent** (opcional)

### 3. Invitar el Bot a tu Servidor

1. En el Developer Portal, ve a "OAuth2" > "URL Generator"
2. Selecciona los scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Selecciona los permisos del bot:
   - ✅ `Send Messages`
   - ✅ `Use Slash Commands`
   - ✅ `Connect`
   - ✅ `Speak`
   - ✅ `Use Voice Activity`
4. Copia la URL generada y ábrela en tu navegador
5. Selecciona tu servidor y autoriza el bot

### 4. Configurar el Proyecto

#### Activar el entorno virtual (ya está creado):
```cmd
# Windows
botenv\Scripts\activate

# macOS/Linux
source botenv/bin/activate
```

#### Instalar dependencias:
```cmd
pip install -r requirements.txt
```

#### Configurar el token:
1. Abre `config.py`
2. Reemplaza `'TU_TOKEN_AQUI'` con el token de tu bot

```python
DISCORD_TOKEN = 'tu_token_real_aqui'
```

### 5. Ejecutar el Bot

```cmd
python bot.py
```

Si todo está configurado correctamente, verás:
```
🤖 [Nombre del Bot] está conectado y listo!
ID: [ID del bot]
------------------
```

## 🎮 Cómo Usar el Bot

### Ejemplos de Uso

1. **Reproducir una canción:**
   ```
   !play Never Gonna Give You Up
   !play https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

2. **Controlar la reproducción:**
   ```
   !pause          # Pausa la música
   !resume         # Reanuda la música
   !skip           # Salta a la siguiente canción
   !stop           # Detiene todo y desconecta
   ```

3. **Ver la cola:**
   ```
   !queue          # Muestra la cola de reproducción
   !now            # Muestra la canción actual
   ```

### Flujo Típico de Uso

1. Únete a un canal de voz
2. Usa `!play [canción]` para que el bot se una y reproduzca
3. Agrega más canciones con `!play` (se añaden a la cola)
4. Usa `!skip` para cambiar de canción
5. Usa `!stop` cuando termines

## 🔧 Solución de Problemas

### Errores Comunes

**"No se encontró FFmpeg"**
- Asegúrate de que FFmpeg esté instalado y en el PATH
- Reinicia el terminal después de instalar FFmpeg

**"Invalid token"**
- Verifica que el token en `config.py` sea correcto
- Asegúrate de no haber incluido espacios extra

**"Cannot connect to voice channel"**
- El bot necesita permisos para conectarse al canal de voz
- Verifica que el bot tenga los permisos necesarios

**"No module named 'discord'"**
- Asegúrate de haber activado el entorno virtual
- Ejecuta `pip install -r requirements.txt`

### Permisos Necesarios

El bot necesita estos permisos en Discord:
- 📩 Enviar mensajes
- 🔗 Conectar (a canales de voz)
- 🎤 Hablar (en canales de voz)
- 📖 Leer historial de mensajes
- 🎵 Usar actividad de voz

## 📝 Notas Adicionales

- El bot mantiene colas separadas para cada servidor
- Las canciones se reproducen en orden FIFO (primero en entrar, primero en salir)
- El bot usa streaming para evitar descargar archivos grandes
- Los embeds incluyen información detallada de las canciones

## 🆘 Soporte

Si tienes problemas:
1. Verifica que todos los requisitos estén instalados
2. Revisa los logs en la consola para errores específicos
3. Asegúrate de que el bot tenga los permisos necesarios
4. Verifica que estés en un canal de voz al usar comandos de música

¡Disfruta de tu bot de música! 🎵 