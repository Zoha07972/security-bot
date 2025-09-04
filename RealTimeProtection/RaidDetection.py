# raid_detection_cog.py
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from collections import defaultdict, deque
from Database.MySqlConnect import SQLiteConnectionPool
from ConsoleHelper.ConsoleMessage import ConsoleMessage
from Database.DatabaseHelper.AuditLogger import log_security_event
from Config.Config import get_config

logger = ConsoleMessage()
pool = SQLiteConnectionPool()

class RaidDetectionCog(commands.Cog):
    """Detect and handle raids with auto-mute/kick/ban/timeout, auto-unmute, and embed logs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.join_times = defaultdict(lambda: deque(maxlen=1000))
        self.last_raid_alert = defaultdict(lambda: datetime.min)
        self.muted_members = defaultdict(set)
        self.timeout_members = defaultdict(dict)  # member_id -> timeout end
        self.clean_old_joins.start()
        self.default_mute_role_name = "Muted"
        self.raid_cooldown = 2
        self.raid_end_timeout = 5

    async def get_or_create_mute_role(self, guild: discord.Guild) -> discord.Role | None:
        mute_role = discord.utils.get(guild.roles, name=self.default_mute_role_name)
        if not mute_role:
            try:
                mute_role = await guild.create_role(
                    name=self.default_mute_role_name,
                    permissions=discord.Permissions(send_messages=False, add_reactions=False),
                    reason="Created for raid protection"
                )
                for channel in guild.text_channels:
                    overwrite = channel.overwrites_for(mute_role)
                    overwrite.send_messages = False
                    overwrite.add_reactions = False
                    await channel.set_permissions(mute_role, overwrite=overwrite)
            except Exception as e:
                logger.error(f"Failed to create 'Muted' role: {e}")
                return None
        return mute_role

    async def log_embed(self, guild: discord.Guild, title: str, description: str, color=0xFF0000):
        channel_id = get_config(guild.id, "raid_log_channel")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
                embed.set_footer(text=f"Guild ID: {guild.id}")
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = member.guild.id
        raid_threshold = int(get_config(guild_id, "raid_threshold") or 5)
        action = get_config(guild_id, "raid_action") or "timeout"
        if member.bot:
            return

        now = datetime.utcnow()
        self.join_times[guild_id].append(now)
        cutoff = now - timedelta(seconds=60)
        recent_joins = [t for t in self.join_times[guild_id] if t > cutoff]
        raid_detected = len(recent_joins) > raid_threshold

        if raid_detected and now - self.last_raid_alert[guild_id] > timedelta(minutes=self.raid_cooldown):
            self.last_raid_alert[guild_id] = now
            logger.warning(f"Raid detected in guild {guild_id}")
            await self.log_embed(member.guild, "🚨 Raid Detected!", f"{len(recent_joins)} joins in last 1 min.\nAction: {action.upper()}")
            log_security_event(guild_id, "raid_detected", member.id, f"{len(recent_joins)} joins")

            # Lock channels
            for channel in member.guild.text_channels:
                overwrite = channel.overwrites_for(member.guild.default_role)
                overwrite.send_messages = False
                overwrite.add_reactions = False
                await channel.set_permissions(member.guild.default_role, overwrite=overwrite)

            # Apply action dynamically
            try:
                if action == "mute":
                    mute_role = await self.get_or_create_mute_role(member.guild)
                    if mute_role:
                        await member.add_roles(mute_role, reason="Raid protection")
                        self.muted_members[guild_id].add(member.id)
                        await self.log_embed(member.guild, "Member Muted", f"{member.mention} muted during raid.")
                elif action == "timeout":
                    # Timeout member for 10 minutes (adjustable)
                    try:
                        await member.edit(timeout=datetime.utcnow() + timedelta(minutes=10), reason="Raid protection")
                        self.timeout_members[guild_id][member.id] = datetime.utcnow() + timedelta(minutes=10)
                        await self.log_embed(member.guild, "Member Timed Out", f"{member.mention} timed out for 10 minutes.")
                    except Exception as e:
                        logger.error(f"Failed to timeout member {member.id}: {e}")
                elif action == "kick":
                    await member.kick(reason="Raid protection")
                    await self.log_embed(member.guild, "Member Kicked", f"{member.mention} kicked during raid.")
                elif action == "ban":
                    await member.ban(reason="Raid protection")
                    await self.log_embed(member.guild, "Member Banned", f"{member.mention} banned during raid.")
            except Exception as e:
                logger.error(f"Failed to apply raid action: {e}")

        self.join_times[guild_id] = deque([t for t in recent_joins], maxlen=1000)

    @tasks.loop(minutes=1)
    async def clean_old_joins(self):
        now = datetime.utcnow()
        for guild_id in list(self.join_times.keys()):
            self.join_times[guild_id] = deque(
                [t for t in self.join_times[guild_id] if t > now - timedelta(seconds=60)], maxlen=1000
            )

            # Restore guild if raid ended
            if self.join_times[guild_id] and now - max(self.join_times[guild_id]) > timedelta(minutes=self.raid_end_timeout):
                await self.restore_guild_after_raid(guild_id)

        # Check for timeout expiration
        for guild_id, members in self.timeout_members.items():
            expired = [mid for mid, end in members.items() if end <= now]
            guild = self.bot.get_guild(guild_id)
            for member_id in expired:
                if guild:
                    member = guild.get_member(member_id)
                    if member:
                        try:
                            await member.edit(timeout=None, reason="Raid timeout ended")
                        except:
                            pass
                members.pop(member_id, None)

    async def restore_guild_after_raid(self, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        # Restore default role permissions
        for channel in guild.text_channels:
            await channel.set_permissions(guild.default_role, overwrite=None)

        # Unmute members
        mute_role = discord.utils.get(guild.roles, name=self.default_mute_role_name)
        if mute_role:
            for member_id in list(self.muted_members[guild_id]):
                member = guild.get_member(member_id)
                if member and mute_role in member.roles:
                    await member.remove_roles(mute_role, reason="Raid ended")
            self.muted_members[guild_id].clear()

        self.join_times[guild_id].clear()
        await self.log_embed(guild, "Raid Ended", "Guild restored after raid.", color=0x00FF00)
        logger.info(f"Guild {guild_id} restored after raid.")

