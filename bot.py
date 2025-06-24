import discord
from discord.ext import commands
import yt_dlp
import asyncio
from collections import deque
import os
import logging

# Configurar logging básico
logging.basicConfig(level=logging.INFO)

# Variables globales para las colas de música
SONG_QUEUES = {}

# Configuración simplificada para yt-dlp
def get_ytdl_options():
    return {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
        "quiet": True,
        "no_warnings": True,
    }

# Configuración para FFmpeg optimizada para Railway/Discord
ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -c:a libopus -b:a 96k",
}

# Función para buscar canciones de forma asíncrona
async def search_song_async(query):
    loop = asyncio.get_running_loop()
    ydl_options = get_ytdl_options()
    
    def extract_info():
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            return ydl.extract_info(f"ytsearch1:{query}", download=False)
    
    return await loop.run_in_executor(None, extract_info)

# Función para reproducir la siguiente canción
async def play_next_song(voice_client, guild_id, channel):
    guild_id_str = str(guild_id)
    
    if guild_id_str in SONG_QUEUES and SONG_QUEUES[guild_id_str]:
        audio_url, title = SONG_QUEUES[guild_id_str].popleft()
        
        try:
            source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options)
            
            def after_play(error):
                if error:
                    print(f"Error playing {title}: {error}")
                asyncio.run_coroutine_threadsafe(
                    play_next_song(voice_client, guild_id, channel), 
                    voice_client.loop
                )
            
            voice_client.play(source, after=after_play)
            await channel.send(f"🎵 **Reproduciendo:** {title}")
            
        except Exception as e:
            await channel.send(f"❌ **Error al reproducir:** {str(e)[:100]}")
            await play_next_song(voice_client, guild_id, channel)
    else:
        # No hay más canciones, desconectar después de un tiempo
        await asyncio.sleep(300)  # Esperar 5 minutos
        if not voice_client.is_playing():
            await voice_client.disconnect()

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='join', aliases=['connect'])
    async def join(self, ctx, *, channel_name=None):
        """Conecta el bot a un canal de voz"""
        if channel_name:
            voice_channel = discord.utils.get(ctx.guild.voice_channels, name=channel_name)
            if not voice_channel:
                await ctx.send(f"❌ **No se encontró el canal '{channel_name}'**")
                return
        else:
            if not ctx.author.voice:
                await ctx.send("❌ **Debes estar en un canal de voz**")
                return
            voice_channel = ctx.author.voice.channel

        if ctx.voice_client:
            if ctx.voice_client.channel == voice_channel:
                await ctx.send(f"✅ **Ya estoy en {voice_channel.name}**")
                return
            await ctx.voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()
        
        await ctx.send(f"✅ **Conectado a {voice_channel.name}**")

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, search):
        """Reproduce una canción o la añade a la cola"""
        # Verificar conexión de voz
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ **Debes estar en un canal de voz**")
                return

        # Buscar la canción
        try:
            search_msg = await ctx.send("🔍 **Buscando...**")
            data = await search_song_async(search)
            
            tracks = data.get("entries", [])
            if not tracks:
                await search_msg.edit(content="❌ **No se encontraron resultados**")
                return
            
            first_track = tracks[0]
            audio_url = first_track["url"]
            title = first_track.get("title", "Sin título")
            
            # Añadir a la cola
            guild_id_str = str(ctx.guild.id)
            if guild_id_str not in SONG_QUEUES:
                SONG_QUEUES[guild_id_str] = deque()
            
            SONG_QUEUES[guild_id_str].append((audio_url, title))
            
            # Si no está reproduciendo, empezar
            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await search_msg.delete()
                await play_next_song(ctx.voice_client, ctx.guild.id, ctx.channel)
            else:
                position = len(SONG_QUEUES[guild_id_str])
                await search_msg.edit(content=f"📋 **Añadida a la cola:** {title}\n📍 **Posición:** {position}")
                
        except Exception as e:
            await ctx.send(f"❌ **Error:** {str(e)[:200]}")

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        """Salta a la siguiente canción"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ **Canción saltada**")
        else:
            await ctx.send("❌ **No hay música reproduciéndose**")

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Pausa la reproducción"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ **Música pausada**")
        else:
            await ctx.send("❌ **No hay música reproduciéndose**")

    @commands.command(name='resume')
    async def resume(self, ctx):
        """Reanuda la reproducción"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ **Música reanudada**")
        else:
            await ctx.send("❌ **La música no está pausada**")

    @commands.command(name='stop')
    async def stop(self, ctx):
        """Detiene la música y limpia la cola"""
        guild_id_str = str(ctx.guild.id)
        if guild_id_str in SONG_QUEUES:
            SONG_QUEUES[guild_id_str].clear()
        
        if ctx.voice_client:
            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                ctx.voice_client.stop()
            await ctx.send("⏹️ **Música detenida y cola limpiada**")
        else:
            await ctx.send("❌ **No hay música reproduciéndose**")

    @commands.command(name='queue', aliases=['q'])
    async def show_queue(self, ctx):
        """Muestra la cola de reproducción"""
        guild_id_str = str(ctx.guild.id)
        
        if guild_id_str not in SONG_QUEUES or not SONG_QUEUES[guild_id_str]:
            await ctx.send("📋 **La cola está vacía**")
            return
        
        queue_list = list(SONG_QUEUES[guild_id_str])
        queue_text = ""
        
        for i, (_, title) in enumerate(queue_list[:10], 1):
            queue_text += f"`{i}.` {title}\n"
        
        if len(queue_list) > 10:
            queue_text += f"... y {len(queue_list) - 10} más"
        
        embed = discord.Embed(
            title="📋 Cola de Reproducción",
            description=queue_text,
            color=0x00ff00
        )
        embed.set_footer(text=f"Total: {len(queue_list)} canciones")
        await ctx.send(embed=embed)

    @commands.command(name='disconnect', aliases=['leave', 'dc'])
    async def disconnect(self, ctx):
        """Desconecta el bot del canal de voz"""
        guild_id_str = str(ctx.guild.id)
        if guild_id_str in SONG_QUEUES:
            SONG_QUEUES[guild_id_str].clear()
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 **Desconectado**")
        else:
            await ctx.send("❌ **No estoy conectado a ningún canal**")

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} está listo!')

@bot.command(name='help')
async def help_command(ctx):
    """Muestra los comandos disponibles"""
    embed = discord.Embed(
        title="🎵 Comandos de Música",
        color=0x00ff00
    )
    
    commands_list = [
        ("!join [canal]", "Conecta el bot al canal de voz"),
        ("!play [búsqueda]", "Reproduce una canción"),
        ("!pause", "Pausa la música"),
        ("!resume", "Reanuda la música"),
        ("!skip", "Salta a la siguiente canción"),
        ("!stop", "Detiene la música y limpia la cola"),
        ("!queue", "Muestra la cola de reproducción"),
        ("!disconnect", "Desconecta el bot"),
    ]
    
    for command, description in commands_list:
        embed.add_field(name=command, value=description, inline=False)
    
    await ctx.send(embed=embed)

async def main():
    async with bot:
        await bot.add_cog(MusicBot(bot))
        
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            print("❌ Error: Configura la variable DISCORD_TOKEN")
            return
        
        await bot.start(token)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot detenido")
    except Exception as e:
        print(f"❌ Error: {e}")