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


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="?", intents=intents)


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
    await bot.tree.sync()
    print(f"{bot.user} is online!")


@bot.command()
async def sync(ctx):
    """
    Syncs the command tree with the guild.
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


@bot.tree.command(name="play", description="Play a song from YouTube", guild=discord.Object(id=GUILD_ID))
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

    ffmpeg_options = {
        'options': '-vn -c:a libopus -b:a 96k',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    }

    source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="bin\\ffmpeg\\ffmpeg.exe")
    voice_client.play(source)

print(f"Registered commands: {[cmd.name for cmd in bot.tree.get_commands()]}")

bot.run(TOKEN)