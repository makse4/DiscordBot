from collections import deque
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
import asyncio


load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
TOKEN = os.getenv("DISCORD_TOKEN")
FFMPEG_PATH = os.getenv("FFMPEG_PATH")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="?", intents=intents)

SONG_QUEUES = {}

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))


def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            return info
        except yt_dlp.utils.DownloadError as e:
            print(f"Error extracting video info: {e}")
            return None


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()  # Sync to the global command tree
        print(f"Synced {len(synced)} command(s).")
        print(f"Registered commands: {[cmd.name for cmd in bot.tree.get_commands()]}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    print(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.command()
async def sync(ctx):
    """
    Syncs the command tree with the guild. Currently useless.
    """
    try:
        test_guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=test_guild)  # Sync to the specific guild
        await ctx.send(f"Synced {len(synced)} commands with the guild.")
    except Exception as e:
        await ctx.send(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)


@bot.command()
async def delete(ctx, amount: int):
    """
    Deletes a specified number of messages from the channel where the command is invoked.
    """
    if amount < 1:
        return

    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)


@bot.command()
async def ping(ctx):
    """
    Responds with 'Pong!' to check if the bot is responsive.
    """
    await ctx.send("Pong!")


@bot.tree.command(name="play", description="Play a song from YouTube")
@app_commands.describe(song_query="The song to play")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()
    
    voice_channel = interaction.user.voice.channel
    if voice_channel is None:
        await interaction.response.send_message("You need to be in a voice channel to use this command.")
        return
    
    voice_client = interaction.guild.voice_client
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)
    
    ydl_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'youtube_include_dash_manifest': False,
    'youtube_include_hls_manifest': False,
}

    query = 'ytsearch1:' + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get('entries', [])

    if tracks is None:
        await interaction.response.send_message("No results found.")
        return

    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Unknown Title")

    guild_id = str(interaction.guild.id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()
    
    SONG_QUEUES[guild_id].append((audio_url, title))

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}**")
        await play_next_song(voice_client, guild_id, interaction.channel)
    

@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("No audio is currently playing.")


@bot.tree.command(name="pause", description="Pause the current audio")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("Paused the audio.")
    else:
        await interaction.response.send_message("No audio is currently playing.")


@bot.tree.command(name="resume", description="Resume the paused audio")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("Resumed the audio.")
    else:
        await interaction.response.send_message("No audio is currently paused.")


@bot.tree.command(name="stop", description="Stop the audio and disconnect from the voice channel")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        await interaction.followup.send("Not connected to a voice channel.")
        return
    
    guild_id = str(interaction.guild.id)
    if guild_id in SONG_QUEUES:
        SONG_QUEUES[guild_id].clear()
    
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    
    await interaction.followup.send("Stopped the audio and disconnected from the voice channel.")
    await voice_client.disconnect()

    


async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()
    
        ffmpeg_options = {
            'options': '-vn -codec:a libopus -b:a 96k',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }
        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable=FFMPEG_PATH)
        
        def after_playing(error):
            if error:
                print(f"Error playing audio: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_playing)
        asyncio.create_task(channel.send(f"Now playing: **{title}**"))
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()

bot.run(TOKEN)
