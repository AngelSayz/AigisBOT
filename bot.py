import discord
from discord.ext import commands
import yt_dlp
import asyncio
from collections import deque
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Configuración para yt-dlp
ytdl_format_options = {
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
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Buscar FFmpeg en ubicaciones comunes
import shutil
ffmpeg_path = shutil.which('ffmpeg')
if not ffmpeg_path:
    # Intentar ubicaciones comunes de FFmpeg
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

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

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
        if not ctx.voice_client:
            queue.is_playing = False
            queue.current = None
            await ctx.send("❌ **El bot no está conectado a un canal de voz.**")
            return

        next_song = queue.next()
        if next_song:
            queue.current = next_song
            queue.is_playing = True
            
            try:
                # Verificar conexión antes de procesar audio
                if not ctx.voice_client or not ctx.voice_client.is_connected():
                    queue.is_playing = False
                    queue.current = None
                    await ctx.send("❌ **Bot desconectado del canal de voz.**")
                    return
                
                # Crear el reproductor de audio con timeout
                player = await asyncio.wait_for(
                    YTDLSource.from_url(next_song['url'], loop=self.bot.loop, stream=True),
                    timeout=10.0
                )
                
                # Verificar nuevamente antes de reproducir
                if ctx.voice_client and ctx.voice_client.is_connected():
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
                else:
                    queue.is_playing = False
                    queue.current = None
                    await ctx.send("❌ **Conexión de voz perdida durante la preparación.**")
                
            except asyncio.TimeoutError:
                await ctx.send("❌ **Timeout al cargar el audio. Saltando a la siguiente canción...**")
                queue.is_playing = False
                await self.play_next(ctx)
            except Exception as e:
                await ctx.send(f"❌ **Error al reproducir la canción:** {str(e)}")
                queue.is_playing = False
                await self.play_next(ctx)

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, search):
        """Reproduce una canción desde YouTube"""
        
        # Verificar que el usuario esté en un canal de voz
        if not ctx.author.voice:
            await ctx.send("❌ **Debes estar en un canal de voz para usar este comando.**")
            return

        channel = ctx.author.voice.channel

        # Conectar al canal de voz si no está conectado
        if not ctx.voice_client:
            try:
                await ctx.send("🔗 **Conectando al canal de voz...**")
                voice_client = await channel.connect(timeout=10.0, reconnect=True)
                await ctx.send(f"✅ **Conectado a {channel.name}**")
                # Pausa más larga para estabilizar la conexión
                await asyncio.sleep(2)
            except asyncio.TimeoutError:
                await ctx.send("❌ **Timeout al conectar. Intenta de nuevo en unos segundos.**")
                return
            except Exception as e:
                await ctx.send(f"❌ **Error al conectar al canal de voz:** {str(e)}")
                return
        elif ctx.voice_client.channel != channel:
            try:
                await ctx.voice_client.move_to(channel)
                await asyncio.sleep(2)
            except Exception as e:
                await ctx.send(f"❌ **Error al mover al canal de voz:** {str(e)}")
                return

        # Verificar que la conexión esté estable antes de continuar
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.send("❌ **Conexión de voz inestable. Intenta de nuevo.**")
            return

        try:
            # Buscar la canción (más rápido, sin typing)
            search_msg = await ctx.send("🔍 **Buscando canción...**")
            
            loop = asyncio.get_event_loop()
            # Buscar con timeout para evitar esperas muy largas
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False)),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                await search_msg.edit(content="❌ **Búsqueda demoró demasiado. Intenta con otra canción.**")
                return

            if 'entries' in data:
                if len(data['entries']) == 0:
                    await ctx.send("❌ **No se encontraron resultados.**")
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

            # Verificar que la conexión de voz esté activa antes de reproducir
            if ctx.voice_client and not queue.is_playing and not ctx.voice_client.is_playing():
                await self.play_next(ctx)
            elif not ctx.voice_client:
                await ctx.send("❌ **Error: Conexión de voz perdida. Intenta de nuevo.**")
            else:
                position = len(queue.queue)
                duration_str = f"{song_info['duration'] // 60}:{song_info['duration'] % 60:02d}" if song_info['duration'] else "Desconocida"
                
                embed = discord.Embed(
                    title="📋 Añadida a la cola",
                    description=f"**{song_info['title']}**\n⏱️ Duración: {duration_str}\n📍 Posición en cola: {position}",
                    color=0x0099ff
                )
                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ **Error al buscar la canción:** {str(e)}")

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
        """Detiene la música y desconecta el bot"""
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        queue.is_playing = False
        queue.current = None
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ **Música detenida y desconectado del canal de voz.**")
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
        ("`!play [búsqueda/URL]`", "Reproduce una canción desde YouTube"),
        ("`!pause`", "Pausa la música actual"),
        ("`!resume`", "Reanuda la música pausada"),
        ("`!skip`", "Salta a la siguiente canción"),
        ("`!stop`", "Detiene la música y desconecta el bot"),
        ("`!queue`", "Muestra la cola de reproducción"),
        ("`!now`", "Muestra la canción actual"),
        ("`!reconnect`", "Reconecta el bot si hay problemas"),
        ("`!help`", "Muestra este mensaje de ayuda")
    ]
    
    for command, description in commands_list:
        embed.add_field(name=command, value=description, inline=False)
    
    embed.set_footer(text="¡Disfruta de la música! 🎵")
    await ctx.send(embed=embed)

# Añadir el cog al bot
async def main():
    async with bot:
        await bot.add_cog(MusicBot(bot))
        
        # Importar el token desde config.py
        try:
            token = os.getenv("DISCORD_TOKEN")
            if token == 'TU_TOKEN_AQUI':
                print("❌ Error: Debes configurar tu token en config.py")
                print("Abre config.py y reemplaza 'TU_TOKEN_AQUI' con tu token real.")
                return
        except ImportError:
            print("❌ Error: No se encontró el archivo config.py")
            return
        
        await bot.start(token)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario.")
    except Exception as e:
        print(f"❌ Error al ejecutar el bot: {e}") 