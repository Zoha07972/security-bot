import discord
from discord.ext import commands
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from Config.Config import get_config
from Database.DatabaseHelper.AuditLogger import log_security_event
from Database.MySqlConnect import SQLiteConnectionPool
from ConsoleHelper.ConsoleMessage import ConsoleMessage
from discord.utils import utcnow  # for aware datetime

logger = ConsoleMessage()
pool = SQLiteConnectionPool()  # Your DB connection pool (synchronous SQLite)

class AntiSpamCog(commands.Cog):
    """Detect spam, warn users, and timeout offenders with persistent database storage."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_messages = defaultdict(lambda: deque(maxlen=100))

    async def log_embed(self, guild: discord.Guild, title: str, description: str, color=0xFF0000):
        channel_id = get_config(guild.id, "spam_log_channel")
        if channel_id:
            try:
                channel = guild.get_channel(int(channel_id))
                if channel:
                    embed = discord.Embed(
                        title=title,
                        description=description,
                        color=color,
                        timestamp=utcnow()  # make aware datetime
                    )
                    embed.set_footer(text=f"Guild ID: {guild.id}")
                    await channel.send(embed=embed)
                else:
                    logger.warn(f"Spam log channel {channel_id} not found in guild {guild.id}")
            except Exception as e:
                logger.error(f"Failed to send anti-spam embed in guild {guild.id}: {e}")

    # --- Database Helpers ---
    def get_user_data(self, guild_id: int, user_id: int):
        """Synchronous SQLite fetch"""
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT warnings, last_warning, timeout_until FROM anti_spam WHERE guild_id=? AND user_id=?",
                (guild_id, user_id)
            )
            row = cur.fetchone()
            if row:
                warnings, last_warning, timeout_until = row
                if last_warning:
                    last_warning = datetime.fromisoformat(last_warning).replace(tzinfo=timezone.utc)
                if timeout_until:
                    timeout_until = datetime.fromisoformat(timeout_until).replace(tzinfo=timezone.utc)
                return warnings, last_warning, timeout_until
            return 0, None, None

    def set_user_data(self, guild_id: int, user_id: int, warnings: int, last_warning: datetime, timeout_until: datetime):
        """Synchronous SQLite insert/update"""
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO anti_spam (guild_id, user_id, warnings, last_warning, timeout_until)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    warnings=excluded.warnings,
                    last_warning=excluded.last_warning,
                    timeout_until=excluded.timeout_until
            """, (
                guild_id,
                user_id,
                warnings,
                last_warning.isoformat() if last_warning else None,
                timeout_until.isoformat() if timeout_until else None
            ))
            conn.commit()

    # --- Message Listener ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        now = utcnow()  # aware datetime

        # Load configs
        spam_threshold = int(get_config(guild.id, "spam_threshold") or 3)
        spam_cooldown = int(get_config(guild.id, "spam_cooldown") or 10)
        timeout_duration = int(get_config(guild.id, "timeout_duration") or 300)
        max_warnings = int(get_config(guild.id, "max_warnings") or 2)
        warning_expiry = int(get_config(guild.id, "warning_expiry") or 300)

        # Track messages
        self.user_messages[message.author.id].append(now)
        while self.user_messages[message.author.id] and self.user_messages[message.author.id][0] < now - timedelta(seconds=spam_cooldown):
            self.user_messages[message.author.id].popleft()

        if len(self.user_messages[message.author.id]) > spam_threshold:
            msg_count = len(self.user_messages[message.author.id])
            self.user_messages[message.author.id].clear()

            try:
                await message.delete()
            except Exception:
                pass

            # Log to security_events
            log_security_event(guild.id, "spam_detected", str(message.author.id), f"{msg_count} messages in {spam_cooldown}s")

            warnings, last_warning, timeout_until = self.get_user_data(guild.id, message.author.id)

            # Check timeout
            if timeout_until and timeout_until > now:
                return

            # Reset warnings if expired
            if last_warning and now - last_warning > timedelta(seconds=warning_expiry):
                warnings = 0

            warnings += 1
            last_warning = now

            if warnings < max_warnings:
                self.set_user_data(guild.id, message.author.id, warnings, last_warning, None)
                await self.log_embed(
                    guild,
                    title="Spam Warning",
                    description=f"{message.author.mention} has been warned for spam ({warnings}/{max_warnings}).",
                    color=0xFFFF00
                )
            else:
                warnings = 0
                last_warning = None
                until = now + timedelta(seconds=timeout_duration)
                try:
                    if guild.me.guild_permissions.moderate_members:
                        await message.author.edit(timed_out_until=until, reason="Exceeded spam limit")
                        self.set_user_data(guild.id, message.author.id, warnings, last_warning, until)
                        await self.log_embed(
                            guild,
                            title="User Timed Out for Spam",
                            description=f"{message.author.mention} has been timed out for {timeout_duration // 60} minutes due to repeated spam.",
                            color=0xFF0000
                        )
                    else:
                        await self.log_embed(
                            guild,
                            title="Spam Detected",
                            description=f"{message.author.mention} exceeded spam limit, but bot lacks permission to timeout.",
                            color=0xFF0000
                        )
                        self.set_user_data(guild.id, message.author.id, warnings, last_warning, None)
                except Exception as e:
                    logger.error(f"Failed to timeout {message.author.id} in guild {guild.id}: {e}")
