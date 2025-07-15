import discord
import os
import asyncio
import json
from discord.ext import commands
from dotenv import load_dotenv
from keep_alive import keep_alive

# Load .env variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Channel IDs to exclude (won't be touched)
EXCLUDED_CHANNEL_IDS = {
    1375034161990996019, 1375725136602333246, 1380080047532019723, 1372894052193669200,
    1382391839403016252, 1380946378611490886, 1378775988669779968, 1372950600496709732,
    1380948039606472825, 1372944146494521446, 1380951693772193902, 1380952765173334097,
    1385200112539668500, 1385200244307923035, 1373010470365167617, 1379194252306808972,
    1371145766755631326, 1333507868321779763, 1350036497687904256, 1333360669956771870,
    1372878262899965962
}

# Progress files
PROGRESS_FILE = "history_progress.json"
PAUSE_FILE = "pause_flag.json"

# Intents setup
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True  # ✅ Add this line

bot = commands.Bot(command_prefix='!', intents=intents)

# Load progress
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, 'r') as f:
        progress_data = json.load(f)
else:
    progress_data = {}

if os.path.exists(PAUSE_FILE):
    with open(PAUSE_FILE, 'r') as f:
        pause_flag = json.load(f)
else:
    pause_flag = {"paused": False}

def save_progress():
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress_data, f, indent=4)

def save_pause():
    with open(PAUSE_FILE, 'w') as f:
        json.dump(pause_flag, f, indent=4)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command(name='lockhistory')
@commands.cooldown(1, 10, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def lock_read_history(ctx):
    await ctx.send("🔐 Starting history permission lock...")

    pause_flag["paused"] = False
    save_pause()

    for guild in bot.guilds:
        guild_id = str(guild.id)
        if guild_id not in progress_data:
            progress_data[guild_id] = {}

        for channel in guild.channels:
            if channel.id in EXCLUDED_CHANNEL_IDS:
                continue

            if pause_flag["paused"]:
                await ctx.send("⏸ Process paused. Use !resume to continue.")
                return

            if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                continue

            channel_id = str(channel.id)
            if channel_id not in progress_data[guild_id]:
                progress_data[guild_id][channel_id] = {
                    "channel_name": channel.name,
                    "done_roles": [],
                    "total_roles_updated": 0
                }

            try:
                for role in guild.roles:
                    if role.is_default():
                        continue
                    if str(role.id) in progress_data[guild_id][channel_id]["done_roles"]:
                        continue

                    overwrite = channel.overwrites_for(role)
                    if overwrite.read_message_history is not False:
                        overwrite.read_message_history = False
                        await channel.set_permissions(role, overwrite=overwrite)
                        await asyncio.sleep(1.5)

                    progress_data[guild_id][channel_id]["done_roles"].append(str(role.id))
                    progress_data[guild_id][channel_id]["total_roles_updated"] += 1
                    save_progress()

            except Exception as e:
                print(f"❌ Error on channel {channel.name}: {e}")
                await asyncio.sleep(2)

    await ctx.send("✅ Permissions locked across all applicable channels!")

@bot.command(name='pause')
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def pause(ctx):
    pause_flag["paused"] = True
    save_pause()
    await ctx.send("⏸ Bot has been paused.")

@bot.command(name='resume')
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def resume(ctx):
    pause_flag["paused"] = False
    save_pause()
    await ctx.invoke(bot.get_command("lockhistory"))

@bot.command(name='status')
@commands.cooldown(1, 10, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def status(ctx):
    total_channels = 0
    total_roles = 0
    lines = []

    for guild_id, channels in progress_data.items():
        for ch_id, ch_data in channels.items():
            total_channels += 1
            roles = ch_data.get("total_roles_updated", 0)
            total_roles += roles
            lines.append(f"🔹 {ch_data['channel_name']} → {roles} roles")

    await ctx.send(f"📊 Progress:\n*Total Channels:* {total_channels}\n*Total Roles Updated:* {total_roles}")

    for i in range(0, len(lines), 10):
        await ctx.send("\n".join(lines[i:i+10]))

@bot.command(name='resetprogress')
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def reset(ctx):
    global progress_data
    progress_data = {}
    save_progress()
    await ctx.send("♻ Progress reset.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Please wait {error.retry_after:.1f}s before using this command again.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need administrator permissions for this command.")
    else:
        raise error

# Start Flask keep_alive server and run bot
keep_alive()
bot.run(DISCORD_TOKEN)