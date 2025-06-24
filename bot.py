import discord
from discord.ext import commands
import yt_dlp
import asyncio
from collections import deque
import os
import logging
import shutil
import random
import time

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Lista de User Agents para rotar
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_ytdl_options():
    """Genera opciones dinámicas para yt-dlp"""
    user_agent = random.choice(USER_AGENTS)
    
    return {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        # Configuraciones anti-detección más agresivas
        'user_agent': user_agent,
        'referer': 'https://www.google.com/',
        'http_headers': {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        },
        # Configuraciones para estabilidad y evasión
        'extractor_retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
        'socket_timeout': 30,
        'retries': 5,
        # Configuraciones específicas para YouTube
        'youtube_include_dash_manifest': False,
        'extract_flat': False,
        # Nuevas opciones anti-detección
        'age_limit': None,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
    }

# Variables globales para control de rate limiting
last_request_time = 0
request_count = 0
COOLDOWN_SECONDS = 2
MAX_REQUESTS_PER_MINUTE = 10

# Configuración para yt-dlp
ytdl_format_options = get_ytdl_options()

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Buscar FFmpeg en ubicaciones comunes
ffmpeg_path = '/usr/bin/ffmpeg'
if not ffmpeg_path:
    # Intentar ubicaciones comunes de FFmpeg en Windows
    possible_paths = [
        'C:\\ffmpeg\\bin\\ffmpeg.exe',
        'C:\\ffmpeg\\ffmpeg.exe',
        'ffmpeg.exe'
    ]
    for path in possible_paths:
        if os.path.exists(path):
            ffmpeg_path = path
            break

if ffmpeg_path:
    print(f"✅ FFmpeg encontrado en: {ffmpeg_path}")
else:
    print("⚠️  FFmpeg no encontrado. Descárgalo desde https://ffmpeg.org/")

async def apply_rate_limit():
    """Aplica rate limiting para evitar spam a YouTube"""
    global last_request_time, request_count
    
    current_time = time.time()
    
    # Reset counter cada minuto
    if current_time - last_request_time > 60:
        request_count = 0
    
    # Si hemos hecho muchas requests, esperar
    if request_count >= MAX_REQUESTS_PER_MINUTE:
        wait_time = 60 - (current_time - last_request_time)
        if wait_time > 0:
            print(f"Rate limit alcanzado. Esperando {wait_time:.1f} segundos...")
            await asyncio.sleep(wait_time)
            request_count = 0
    
    # Esperar cooldown mínimo entre requests
    if current_time - last_request_time < COOLDOWN_SECONDS:
        sleep_time = COOLDOWN_SECONDS - (current_time - last_request_time)
        await asyncio.sleep(sleep_time)
    
    last_request_time = time.time()
    request_count += 1

async def search_song(search_query, loop=None):
    """Función mejorada para buscar canciones con manejo de errores y rate limiting"""
    loop = loop or asyncio.get_event_loop()
    
    # Aplicar rate limiting
    await apply_rate_limit()
    
    # Lista de prefijos para intentar diferentes tipos de búsqueda y servicios
    search_attempts = [
        f"ytsearch1:{search_query}",     # YouTube búsqueda específica
        f"scsearch1:{search_query}",     # SoundCloud como alternativa
        search_query,                    # Búsqueda automática
        f"ytsearch:{search_query}",      # YouTube búsqueda general
        f"scsearch:{search_query}",      # SoundCloud búsqueda general
    ]
    
    for attempt, search_term in enumerate(search_attempts, 1):
        try:
            print(f"Intento {attempt}: Buscando con '{search_term[:50]}...'")
            
            # Crear nueva instancia de ytdl con opciones frescas para cada intento
            ytdl_options = get_ytdl_options()
            ytdl = yt_dlp.YoutubeDL(ytdl_options)
            
            # Pequeña pausa adicional entre intentos
            if attempt > 1:
                await asyncio.sleep(random.uniform(1, 3))
            
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ytdl.extract_info(search_term, download=False)),
                timeout=30.0
            )
            
            if 'entries' in data and len(data['entries']) > 0:
                # Tomar la primera entrada válida
                for entry in data['entries']:
                    if entry and entry.get('url'):
                        print(f"✅ Encontrado en intento {attempt}: {entry.get('title', 'Sin título')}")
                        return entry
                continue
            elif data and data.get('url'):
                print(f"✅ Encontrado en intento {attempt}: {data.get('title', 'Sin título')}")
                return data
                
        except asyncio.TimeoutError:
            print(f"⏱️ Timeout en intento {attempt}")
            continue
        except Exception as e:
            error_msg = str(e).lower()
            print(f"❌ Error en intento {attempt}: {e}")
            
            # Si es el error específico de bot de YouTube, intentar con otros servicios
            if "sign in to confirm" in error_msg or "bot" in error_msg:
                print("🤖 Detección de bot - probando siguiente método...")
                continue
            elif "video unavailable" in error_msg or "private video" in error_msg:
                print("📹 Video no disponible - probando siguiente método...")
                continue
            elif attempt == len(search_attempts):  # Último intento
                raise e
            else:
                continue
    
    raise Exception("No se pudieron encontrar resultados después de múltiples intentos con diferentes servicios")

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        
        # Aplicar rate limiting
        await apply_rate_limit()
        
        # Crear instancia fresca de ytdl para cada request
        ytdl_options = get_ytdl_options()
        ytdl = yt_dlp.YoutubeDL(ytdl_options)
        
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Toma la primera entrada si es una playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        
        # Usar la ruta de FFmpeg encontrada si está disponible
        if ffmpeg_path and ffmpeg_path != 'ffmpeg':
            return cls(discord.FFmpegPCMAudio(filename, executable=ffmpeg_path, **ffmpeg_options), data=data)
        else:
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current = None
        self.is_playing = False

    def add(self, song):
        self.queue.append(song)

    def next(self):
        if self.queue:
            return self.queue.popleft()
        return None

    def clear(self):
        self.queue.clear()

    def is_empty(self):
        return len(self.queue) == 0

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_queues = {}  # Diccionario para almacenar colas por servidor

    def get_queue(self, guild_id):
        if guild_id not in self.music_queues:
            self.music_queues[guild_id] = MusicQueue()
        return self.music_queues[guild_id]

    async def play_next(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        
        if queue.is_empty():
            queue.is_playing = False
            queue.current = None
            await ctx.send("✅ **Cola de reproducción terminada.**")
            return

        # Verificar que el bot esté conectado al canal de voz
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            queue.is_playing = False
            queue.current = None
            await ctx.send("❌ **El bot no está conectado a un canal de voz. Usa `!join` primero.**")
            return

        next_song = queue.next()
        if next_song:
            queue.current = next_song
            queue.is_playing = True
            
            try:
                # Crear el reproductor de audio con timeout
                player = await asyncio.wait_for(
                    YTDLSource.from_url(next_song['url'], loop=self.bot.loop, stream=True),
                    timeout=15.0
                )
                
                def after_playing(error):
                    if error:
                        print(f"Error en reproducción: {error}")
                    asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
                
                ctx.voice_client.play(player, after=after_playing)
                
                duration_str = f"{next_song['duration'] // 60}:{next_song['duration'] % 60:02d}" if next_song['duration'] else "Desconocida"
                embed = discord.Embed(
                    title="🎵 Reproduciendo ahora",
                    description=f"**{next_song['title']}**\n⏱️ Duración: {duration_str}",
                    color=0x00ff00
                )
                await ctx.send(embed=embed)
                
            except asyncio.TimeoutError:
                await ctx.send("❌ **Timeout al cargar el audio. Saltando a la siguiente canción...**")
                queue.is_playing = False
                await self.play_next(ctx)
            except Exception as e:
                await ctx.send(f"❌ **Error al reproducir la canción:** {str(e)}")
                queue.is_playing = False
                await self.play_next(ctx)

    @commands.command(name='join', aliases=['connect', 'conectar'])
    async def join(self, ctx, *, channel_name=None):
        """Conecta el bot a un canal de voz"""
        
        # Si se especifica un nombre de canal, buscar ese canal
        if channel_name:
            voice_channel = None
            for channel in ctx.guild.voice_channels:
                if channel_name.lower() in channel.name.lower():
                    voice_channel = channel
                    break
            
            if not voice_channel:
                await ctx.send(f"❌ **No se encontró el canal de voz '{channel_name}'.**")
                return
        else:
            # Si no se especifica canal, usar el del usuario
            if not ctx.author.voice:
                await ctx.send("❌ **Debes estar en un canal de voz o especificar el nombre del canal.**")
                return
            voice_channel = ctx.author.voice.channel

        # Desconectar si ya está conectado a otro canal
        if ctx.voice_client:
            if ctx.voice_client.channel == voice_channel:
                await ctx.send(f"✅ **Ya estoy conectado a {voice_channel.name}.**")
                return
            else:
                await ctx.voice_client.disconnect()
                await asyncio.sleep(1)

        try:
            await ctx.send(f"🔗 **Conectando a {voice_channel.name}...**")
            voice_client = await voice_channel.connect(timeout=10.0, reconnect=True)
            await ctx.send(f"✅ **Conectado exitosamente a {voice_channel.name}!**")
            
            # Pequeña pausa para estabilizar la conexión
            await asyncio.sleep(1)
            
        except asyncio.TimeoutError:
            await ctx.send("❌ **Timeout al conectar. Intenta de nuevo.**")
        except Exception as e:
            await ctx.send(f"❌ **Error al conectar al canal de voz:** {str(e)}")

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, search):
        """Añade una canción a la cola de reproducción"""
        
        # Verificar que el bot esté conectado a un canal de voz
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.send("❌ **El bot no está conectado a un canal de voz. Usa `!join` primero.**")
            return

        try:
            # Buscar la canción con la función mejorada
            search_msg = await ctx.send("🔍 **Buscando canción...**")
            
            try:
                data = await search_song(search, loop=self.bot.loop)
            except asyncio.TimeoutError:
                await search_msg.edit(content="❌ **Búsqueda demoró demasiado. Intenta con otra canción.**")
                return
            except Exception as e:
                error_msg = str(e).lower()
                if "sign in to confirm" in error_msg or "bot" in error_msg:
                    await search_msg.edit(content="❌ **YouTube está bloqueando las búsquedas. Intenta con una URL directa o espera unos minutos.**")
                else:
                    await search_msg.edit(content=f"❌ **Error al buscar:** {str(e)}")
                return

            if not data:
                await search_msg.edit(content="❌ **No se encontraron resultados.**")
                return

            song_info = {
                'title': data.get('title', 'Título desconocido'),
                'url': data.get('webpage_url', data.get('url')),
                'duration': data.get('duration'),
                'uploader': data.get('uploader', 'Desconocido')
            }

            queue = self.get_queue(ctx.guild.id)
            queue.add(song_info)

            # Si no hay música reproduciéndose, empezar a reproducir
            if not queue.is_playing and not ctx.voice_client.is_playing():
                await search_msg.delete()
                await self.play_next(ctx)
            else:
                # Mostrar que se añadió a la cola
                position = len(queue.queue)
                duration_str = f"{song_info['duration'] // 60}:{song_info['duration'] % 60:02d}" if song_info['duration'] else "Desconocida"
                
                embed = discord.Embed(
                    title="📋 Añadida a la cola",
                    description=f"**{song_info['title']}**\n⏱️ Duración: {duration_str}\n📍 Posición en cola: {position}",
                    color=0x0099ff
                )
                await search_msg.edit(content="", embed=embed)

        except Exception as e:
            await ctx.send(f"❌ **Error inesperado:** {str(e)}")

    @commands.command(name='url')
    async def play_url(self, ctx, *, url):
        """Añade una canción usando URL directa (para evitar problemas de búsqueda)"""
        
        # Verificar que el bot esté conectado a un canal de voz
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.send("❌ **El bot no está conectado a un canal de voz. Usa `!join` primero.**")
            return

        try:
            # Procesar URL directamente
            search_msg = await ctx.send("🔗 **Procesando URL...**")
            
            # Aplicar rate limiting
            await apply_rate_limit()
            
            # Crear instancia fresca de ytdl
            ytdl_options = get_ytdl_options()
            ytdl = yt_dlp.YoutubeDL(ytdl_options)
            
            loop = asyncio.get_event_loop()
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False)),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                await search_msg.edit(content="❌ **Procesamiento demoró demasiado.**")
                return
            except Exception as e:
                error_msg = str(e).lower()
                if "sign in to confirm" in error_msg or "bot" in error_msg:
                    await search_msg.edit(content="❌ **YouTube está bloqueando las requests. Intenta con otro servicio o espera unos minutos.**")
                else:
                    await search_msg.edit(content=f"❌ **Error al procesar URL:** {str(e)}")
                return

            if 'entries' in data:
                if len(data['entries']) == 0:
                    await search_msg.edit(content="❌ **URL no válida o sin contenido.**")
                    return
                data = data['entries'][0]

            song_info = {
                'title': data.get('title', 'Título desconocido'),
                'url': data.get('webpage_url', data.get('url')),
                'duration': data.get('duration'),
                'uploader': data.get('uploader', 'Desconocido')
            }

            queue = self.get_queue(ctx.guild.id)
            queue.add(song_info)

            # Si no hay música reproduciéndose, empezar a reproducir
            if not queue.is_playing and not ctx.voice_client.is_playing():
                await search_msg.delete()
                await self.play_next(ctx)
            else:
                # Mostrar que se añadió a la cola
                position = len(queue.queue)
                duration_str = f"{song_info['duration'] // 60}:{song_info['duration'] % 60:02d}" if song_info['duration'] else "Desconocida"
                
                embed = discord.Embed(
                    title="📋 Añadida a la cola (URL)",
                    description=f"**{song_info['title']}**\n⏱️ Duración: {duration_str}\n📍 Posición en cola: {position}",
                    color=0x0099ff
                )
                await search_msg.edit(content="", embed=embed)

        except Exception as e:
            await ctx.send(f"❌ **Error al procesar URL:** {str(e)}")

    @commands.command(name='soundcloud', aliases=['sc'])
    async def play_soundcloud(self, ctx, *, search):
        """Busca y reproduce música específicamente desde SoundCloud"""
        
        # Verificar que el bot esté conectado a un canal de voz
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.send("❌ **El bot no está conectado a un canal de voz. Usa `!join` primero.**")
            return

        try:
            # Buscar en SoundCloud específicamente
            search_msg = await ctx.send("🎵 **Buscando en SoundCloud...**")
            
            # Aplicar rate limiting
            await apply_rate_limit()
            
            # Crear instancia fresca de ytdl
            ytdl_options = get_ytdl_options()
            ytdl = yt_dlp.YoutubeDL(ytdl_options)
            
            search_term = f"scsearch1:{search}"
            
            loop = asyncio.get_event_loop()
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: ytdl.extract_info(search_term, download=False)),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                await search_msg.edit(content="❌ **Búsqueda en SoundCloud demoró demasiado.**")
                return
            except Exception as e:
                await search_msg.edit(content=f"❌ **Error al buscar en SoundCloud:** {str(e)}")
                return

            if 'entries' in data and len(data['entries']) > 0:
                data = data['entries'][0]
            elif not data or not data.get('url'):
                await search_msg.edit(content="❌ **No se encontraron resultados en SoundCloud.**")
                return

            song_info = {
                'title': data.get('title', 'Título desconocido'),
                'url': data.get('webpage_url', data.get('url')),
                'duration': data.get('duration'),
                'uploader': data.get('uploader', 'SoundCloud')
            }

            queue = self.get_queue(ctx.guild.id)
            queue.add(song_info)

            # Si no hay música reproduciéndose, empezar a reproducir
            if not queue.is_playing and not ctx.voice_client.is_playing():
                await search_msg.delete()
                await self.play_next(ctx)
            else:
                # Mostrar que se añadió a la cola
                position = len(queue.queue)
                duration_str = f"{song_info['duration'] // 60}:{song_info['duration'] % 60:02d}" if song_info['duration'] else "Desconocida"
                
                embed = discord.Embed(
                    title="📋 Añadida a la cola (SoundCloud)",
                    description=f"**{song_info['title']}**\n⏱️ Duración: {duration_str}\n📍 Posición en cola: {position}\n🎵 Fuente: SoundCloud",
                    color=0xff5500
                )
                await search_msg.edit(content="", embed=embed)

        except Exception as e:
            await ctx.send(f"❌ **Error con SoundCloud:** {str(e)}")

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Pausa la reproducción actual"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ **Música pausada.**")
        else:
            await ctx.send("❌ **No hay música reproduciéndose actualmente.**")

    @commands.command(name='resume')
    async def resume(self, ctx):
        """Reanuda la reproducción pausada"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ **Música reanudada.**")
        else:
            await ctx.send("❌ **La música no está pausada.**")

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        """Salta a la siguiente canción"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ **Canción saltada.**")
        else:
            await ctx.send("❌ **No hay música reproduciéndose actualmente.**")

    @commands.command(name='stop')
    async def stop(self, ctx):
        """Detiene la música y limpia la cola"""
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        queue.is_playing = False
        queue.current = None
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏹️ **Música detenida y cola limpiada.**")
        else:
            await ctx.send("❌ **No hay música reproduciéndose actualmente.**")

    @commands.command(name='disconnect', aliases=['leave', 'dc'])
    async def disconnect(self, ctx):
        """Desconecta el bot del canal de voz"""
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        queue.is_playing = False
        queue.current = None
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 **Desconectado del canal de voz.**")
        else:
            await ctx.send("❌ **No estoy conectado a ningún canal de voz.**")

    @commands.command(name='queue', aliases=['q'])
    async def show_queue(self, ctx):
        """Muestra la cola de reproducción"""
        queue = self.get_queue(ctx.guild.id)
        
        if queue.current is None and queue.is_empty():
            await ctx.send("📋 **La cola está vacía.**")
            return

        embed = discord.Embed(title="📋 Cola de Reproducción", color=0xff9900)
        
        if queue.current:
            duration_str = f"{queue.current['duration'] // 60}:{queue.current['duration'] % 60:02d}" if queue.current['duration'] else "Desconocida"
            embed.add_field(
                name="🎵 Reproduciendo ahora:",
                value=f"**{queue.current['title']}** ({duration_str})",
                inline=False
            )

        if not queue.is_empty():
            queue_text = ""
            for i, song in enumerate(list(queue.queue)[:10], 1):  # Mostrar máximo 10 canciones
                duration_str = f"{song['duration'] // 60}:{song['duration'] % 60:02d}" if song['duration'] else "Desconocida"
                queue_text += f"`{i}.` **{song['title']}** ({duration_str})\n"
            
            if len(queue.queue) > 10:
                queue_text += f"... y {len(queue.queue) - 10} canciones más."
            
            embed.add_field(name="⏭️ Próximas canciones:", value=queue_text, inline=False)
        
        embed.set_footer(text=f"Total de canciones en cola: {len(queue.queue)}")
        await ctx.send(embed=embed)

    @commands.command(name='now', aliases=['np'])
    async def now_playing(self, ctx):
        """Muestra la canción que se está reproduciendo actualmente"""
        queue = self.get_queue(ctx.guild.id)
        
        if queue.current and queue.is_playing:
            duration_str = f"{queue.current['duration'] // 60}:{queue.current['duration'] % 60:02d}" if queue.current['duration'] else "Desconocida"
            
            embed = discord.Embed(
                title="🎵 Reproduciendo ahora",
                description=f"**{queue.current['title']}**\n⏱️ Duración: {duration_str}\n👤 Canal: {queue.current['uploader']}",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ **No hay música reproduciéndose actualmente.**")

    @commands.command(name='reconnect', aliases=['reconectar'])
    async def reconnect(self, ctx):
        """Reconecta el bot al canal de voz"""
        if not ctx.author.voice:
            await ctx.send("❌ **Debes estar en un canal de voz para usar este comando.**")
            return

        channel = ctx.author.voice.channel

        # Desconectar si ya está conectado
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await asyncio.sleep(1)

        try:
            await ctx.send("🔄 **Reconectando...**")
            await channel.connect(timeout=10.0, reconnect=True)
            await ctx.send(f"✅ **Reconectado a {channel.name}**")
            
            # Si había una cola, intentar reanudar
            queue = self.get_queue(ctx.guild.id)
            if queue.current and not queue.is_playing:
                queue.is_playing = True
                await self.play_next(ctx)
                
        except Exception as e:
            await ctx.send(f"❌ **Error al reconectar:** {str(e)}")

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} está conectado y listo!')
    print(f'ID: {bot.user.id}')
    print('------------------')

@bot.command(name='help', aliases=['ayuda'])
async def help_command(ctx):
    """Muestra los comandos disponibles"""
    embed = discord.Embed(
        title="🤖 Comandos del Bot de Música",
        description="Lista de comandos disponibles:",
        color=0x00ff00
    )
    
    commands_list = [
        ("`!join [canal]`", "Conecta el bot a un canal de voz (usa tu canal actual si no especificas)"),
        ("`!play [búsqueda]`", "Busca y añade una canción a la cola"),
        ("`!url [URL_directa]`", "Añade una canción usando URL directa (recomendado si falla !play)"),
        ("`!soundcloud [búsqueda]`", "Busca y reproduce música específicamente desde SoundCloud"),
        ("`!pause`", "Pausa la música actual"),
        ("`!resume`", "Reanuda la música pausada"),
        ("`!skip`", "Salta a la siguiente canción"),
        ("`!stop`", "Detiene la música y limpia la cola"),
        ("`!disconnect`", "Desconecta el bot del canal de voz"),
        ("`!queue`", "Muestra la cola de reproducción"),
        ("`!now`", "Muestra la canción actual"),
        ("`!reconnect`", "Reconecta el bot si hay problemas"),
        ("`!help`", "Muestra este mensaje de ayuda")
    ]
    
    for command, description in commands_list:
        embed.add_field(name=command, value=description, inline=False)
    
    embed.set_footer(text="¡Primero usa !join para conectar el bot, luego !play para añadir música! 🎵")
    await ctx.send(embed=embed)

# Añadir el cog al bot
async def main():
    async with bot:
        await bot.add_cog(MusicBot(bot))
        
        # Obtener el token de la variable de entorno
        try:
            token = os.getenv("DISCORD_TOKEN")
            if not token or token == 'TU_TOKEN_AQUI':
                print("❌ Error: Debes configurar tu token como variable de entorno DISCORD_TOKEN")
                print("En Windows PowerShell: $env:DISCORD_TOKEN='tu_token_aqui'")
                print("En Windows CMD: set DISCORD_TOKEN=tu_token_aqui")
                print("En Linux/Mac: export DISCORD_TOKEN='tu_token_aqui'")
                return
        except Exception as e:
            print(f"❌ Error al obtener el token: {e}")
            return
        
        await bot.start(token)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario.")
    except Exception as e:
        print(f"❌ Error al ejecutar el bot: {e}") 