import discord
from discord.ext import commands
from discord import app_commands
from Database.MySqlConnect import SQLiteConnectionPool
from Database.DatabaseHelper.SecurityHelper import has_security_role
from Database.DatabaseHelper.Helper import get_guild_setting
from ConsoleHelper.ConsoleMessage import ConsoleMessage
import pytz
from datetime import datetime

pool = SQLiteConnectionPool()
logger = ConsoleMessage()  # Singleton logger

def get_guild_timezone(guild_id: int) -> str:
    tz = get_guild_setting(guild_id, "timezone")
    return tz if tz else "Asia/Kolkata"

def format_timestamp(ts_str: str, tz_name: str) -> str:
    try:
        utc_dt = datetime.fromisoformat(ts_str)
        tz = pytz.timezone(tz_name)
        local_dt = utc_dt.astimezone(tz)
        now = datetime.now(tz)
        diff = now - local_dt

        minutes = int(diff.total_seconds() // 60)
        if minutes < 1:
            relative = "just now"
        elif minutes < 60:
            relative = f"{minutes} minutes ago"
        elif minutes < 1440:
            hours = minutes // 60
            relative = f"{hours} hours ago"
        else:
            days = minutes // 1440
            relative = f"{days} days ago"

        return f"{local_dt.strftime('%Y-%m-%d %H:%M')} ({relative})"
    except Exception:
        return ts_str

class LogsCog(commands.Cog):
    """View recent audit and security logs with pagination."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def paginate_embed(self, interaction, logs, title, color, log_type):
        tz_name = get_guild_timezone(interaction.guild.id)
        per_page = 5
        pages = []
        for i in range(0, len(logs), per_page):
            embed = discord.Embed(title=title, color=color)
            for log in logs[i:i+per_page]:
                if log_type == "audit":
                    event_type, actor, target, details, ts = log
                    ts_formatted = format_timestamp(ts, tz_name)
                    value = f"👮 Actor: <@{actor}>\n🎯 Target: {target if target else 'N/A'}\n📋 {details or 'No details'}\n🕒 {ts_formatted}"
                    embed.add_field(name=f"Action: {event_type}", value=value, inline=False)
                else:
                    event_type, details, ts = log
                    ts_formatted = format_timestamp(ts, tz_name)
                    value = f"📋 {details or 'No details'}\n🕒 {ts_formatted}"
                    embed.add_field(name=f"Event: {event_type}", value=value, inline=False)
            pages.append(embed)

        current = 0
        message = await interaction.response.send_message(embed=pages[current], ephemeral=False)
        message = await interaction.original_response()

        if len(pages) == 1:
            return  # No pagination needed

        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")

        def check(reaction, user):
            return user == interaction.user and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == message.id

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=120.0, check=check)
            except:
                try:
                    await message.clear_reactions()
                except:
                    pass
                break

            if str(reaction.emoji) == "➡️":
                current = (current + 1) % len(pages)
            elif str(reaction.emoji) == "⬅️":
                current = (current - 1) % len(pages)

            await message.edit(embed=pages[current])
            try:
                await message.remove_reaction(reaction, user)
            except:
                pass

    @app_commands.command(name="logs_audit", description="View recent audit logs")
    @app_commands.describe(limit="Number of logs to fetch (default 20)")
    async def logs_audit(self, interaction: discord.Interaction, limit: int = 20):
        if not has_security_role(interaction.user, interaction.guild.id):
            await interaction.response.send_message("❌ You do not have permission to view audit logs.", ephemeral=False)
            return

        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT event_type, actor_id, target_id, details, timestamp 
                FROM audit_logs 
                WHERE guild_id=? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (interaction.guild.id, limit))
            logs = cursor.fetchall()
            cursor.close()

        if not logs:
            await interaction.response.send_message("📭 No audit logs found.", ephemeral=False)
            return

        logger.info(f"User {interaction.user} fetched {len(logs)} audit logs from guild {interaction.guild.id}")
        await self.paginate_embed(interaction, logs, f"📝 Recent Audit Logs (Last {len(logs)})", discord.Color.blue(), "audit")

    @app_commands.command(name="logs_security", description="View recent security events")
    @app_commands.describe(limit="Number of logs to fetch (default 20)")
    async def logs_security(self, interaction: discord.Interaction, limit: int = 20):
        if not has_security_role(interaction.user, interaction.guild.id):
            await interaction.response.send_message("❌ You do not have permission to view security events.", ephemeral=False)
            return

        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT event_type, details, detected_at 
                FROM security_events 
                WHERE guild_id=? 
                ORDER BY detected_at DESC 
                LIMIT ?
            """, (interaction.guild.id, limit))
            logs = cursor.fetchall()
            cursor.close()

        if not logs:
            await interaction.response.send_message("📭 No security events found.", ephemeral=False)
            return

        logger.info(f"User {interaction.user} fetched {len(logs)} security events from guild {interaction.guild.id}")
        await self.paginate_embed(interaction, logs, f"⚠️ Recent Security Events (Last {len(logs)})", discord.Color.red(), "security")
