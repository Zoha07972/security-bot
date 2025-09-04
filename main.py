import os
import discord
from discord.ext import commands
import asyncio
from ConsoleHelper.ConsoleMessage import ConsoleMessage
from Database.MySqlConnect import SQLiteConnectionPool ,run_migrations
from Database.DatabaseHelper.Helper import load_mirrors
import Config.Load
import RealTimeProtection.Load
# ---------------------------------------- Variables ----------------------------------------
logger =ConsoleMessage()
pool = SQLiteConnectionPool()
TOKEN = "MTQxMDk5NjI1NDIyNTQ2NTM3NQ.GON-jp.5jvSXBI6S3L0ZRO3zcrV9ya2TedU282Z-TyxBg"
if not TOKEN:
    asyncio.run(logger.error("Bot token not found! Shutting down..."))
    raise ValueError("Bot token not found!")
# -------------------------------------------------------------------------------------------

# ---------------------------------- Bot Setup --------------------------------------
intents = discord.Intents.all()
#intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------------------------------- Event Handlers ---------------------------------
@bot.event
async def on_ready():
    logger.debug(f"Bot `{bot.user.name}` has connected to Discord!")
    await bot.change_presence(activity=discord.CustomActivity(name="Working On Security bot"))
    logger.debug("Bot presence Started`")
    try:
        with pool.get_connection() as conn:
            run_migrations(pool)
            load_mirrors()
            logger.debug(" Database connection established and mirrors loaded.")
    except Exception as e:
        logger.error(f" Failed to connect to the database. Bot features may not work properly:{e}.")
        return

    try:
        # Load commands
        await setup_cogs()
        logger.debug(" Cogs loaded successfully.")
        synced = await bot.tree.sync()
        logger.debug(f" Synced {len(synced)} slash command(s).")
    except Exception as e:
        logger.error(f" Error syncing commands: `{e}`")

@bot.event
async def on_message(message):
    """Event handler for incoming messages."""
    if message.author == bot.user:
        return
    await bot.process_commands(message)
# ---------------------------------- Command and Cog Setup --------------------------
async def setup_cogs():
    """Load all necessary cogs and commands."""
    try:
        await Config.Load.setup(bot)
        await RealTimeProtection.Load.setup(bot)
    except Exception as e:
        logger.error(f" Error loading cogs: `{e}`")
# -----------------------------------------------------------------------------------


# ---------------------------------- Run the Bot ------------------------------------
try:
    bot.run(TOKEN)
except Exception as e:
    asyncio.run(logger.error(f" Bot failed to start: `{e}`"))
# -----------------------------------------------------------------------------------