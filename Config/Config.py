# config_cog.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import pytz
from Database.DatabaseHelper.Helper import get_guild_setting, set_guild_setting
from ConsoleHelper.ConsoleMessage import ConsoleMessage

logger = ConsoleMessage()

# -------------------------
# Default Security Config
# -------------------------
DEFAULT_CONFIG = {
    "raid_threshold": "5",
    "spam_threshold": "3",
    "mention_limit": "5",
    "raidmode": "off",
    "antispam": "on",
    "security_roles": "[]",
    "timezone": "Asia/Kolkata",
    "raid_action": "timeout",  # default action
    "raid_log_channel": None,
    # Anti-spam settings
    "spam_cooldown": "10",       # seconds
    "timeout_duration": "300",   # seconds
    "max_warnings": "2",
    "warning_expiry": "300",     # seconds
    "spam_log_channel": None
}

CONFIG_CHOICES = [
    app_commands.Choice(name="Raid Threshold (joins/minute)", value="raid_threshold"),
    app_commands.Choice(name="Spam Threshold (msgs/5s)", value="spam_threshold"),
    app_commands.Choice(name="Mention Limit (mentions/msg)", value="mention_limit"),
    app_commands.Choice(name="Raidmode (on/off)", value="raidmode"),
    app_commands.Choice(name="Antispam (on/off)", value="antispam"),
    app_commands.Choice(name="Security Roles (IDs)", value="security_roles"),
    app_commands.Choice(name="Timezone", value="timezone"),
    app_commands.Choice(name="Raid Action (timeout/mute/kick/ban)", value="raid_action"),
    # Anti-spam choices
    app_commands.Choice(name="Spam Cooldown (seconds)", value="spam_cooldown"),
    app_commands.Choice(name="Timeout Duration (seconds)", value="timeout_duration"),
    app_commands.Choice(name="Max Warnings", value="max_warnings"),
    app_commands.Choice(name="Warning Expiry (seconds)", value="warning_expiry"),
]

# -------------------------
# Config Helpers
# -------------------------
def ensure_default_config(guild_id: int):
    for key, default_value in DEFAULT_CONFIG.items():
        if get_guild_setting(guild_id, key) is None:
            set_guild_setting(guild_id, key, default_value)

def get_config(guild_id: int, key: str):
    value = get_guild_setting(guild_id, key)
    if value is None:
        default = DEFAULT_CONFIG.get(key)
        set_guild_setting(guild_id, key, default)
        return default
    return value

def set_config(guild_id: int, key: str, value: str):
    set_guild_setting(guild_id, key, value)

def get_security_roles(guild_id: int):
    try:
        return json.loads(get_config(guild_id, "security_roles"))
    except Exception:
        return []

def is_guild_owner(user: discord.Member) -> bool:
    return user.id == user.guild.owner_id

def has_security_role(user: discord.Member, guild_id: int) -> bool:
    allowed_roles = get_security_roles(guild_id)
    return any(role.id in allowed_roles for role in user.roles) or is_guild_owner(user)

# -------------------------
# Config Cog
# -------------------------
class ConfigCog(commands.Cog):
    """Manage and view security configuration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="config_get", description="Get a security config value")
    @app_commands.describe(key="Select the config key")
    @app_commands.choices(key=CONFIG_CHOICES)
    async def config_get(self, interaction: discord.Interaction, key: app_commands.Choice[str]):
        ensure_default_config(interaction.guild.id)
        if not has_security_role(interaction.user, interaction.guild.id):
            await interaction.response.send_message(
                "❌ You do not have permission to view security configs.", ephemeral=True
            )
            logger.warning(f"Unauthorized config_get by {interaction.user} in guild {interaction.guild.id}")
            return

        value = get_config(interaction.guild.id, key.value)
        if key.value == "security_roles":
            try:
                roles = json.loads(value)
                value = ", ".join([f"<@&{rid}>" for rid in roles]) if roles else "No security roles configured"
            except Exception:
                value = "Invalid data"

        await interaction.response.send_message(f"🔐 **Config**: `{key.name}` = `{value}`", ephemeral=True)
        logger.info(f"Config fetched: {key.value}={value} by {interaction.user} in guild {interaction.guild.id}")

    @app_commands.command(name="config_set", description="Set a security config value")
    @app_commands.describe(key="Select the config key", value="Enter the new value")
    @app_commands.choices(key=CONFIG_CHOICES)
    async def config_set(self, interaction: discord.Interaction, key: app_commands.Choice[str], value: str):
        ensure_default_config(interaction.guild.id)
        if not is_guild_owner(interaction.user):
            await interaction.response.send_message(
                "❌ Only the server owner can modify security configs.", ephemeral=True
            )
            logger.warning(f"Unauthorized config_set by {interaction.user} in guild {interaction.guild.id}")
            return

        # Numeric validation
        if key.value in [
            "raid_threshold", "spam_threshold", "mention_limit",
            "spam_cooldown", "timeout_duration", "max_warnings", "warning_expiry"
        ]:
            if not value.isdigit() or int(value) < 1:
                await interaction.response.send_message(
                    "❌ Value must be a positive integer.", ephemeral=True
                )
                return

        # Security roles validation
        if key.value == "security_roles":
            try:
                role_ids = [int(rid.strip()) for rid in value.split(",") if rid.strip().isdigit()]
                guild = interaction.guild
                role_ids = [rid for rid in role_ids if any(r.id == rid for r in guild.roles)]
                value = json.dumps(role_ids)
            except Exception:
                await interaction.response.send_message("❌ Invalid role IDs.", ephemeral=True)
                return

        # Timezone validation
        if key.value == "timezone":
            try:
                pytz.timezone(value.strip())
            except Exception:
                await interaction.response.send_message("❌ Invalid timezone.", ephemeral=True)
                return

        # Raid action validation
        if key.value == "raid_action":
            if value.lower() not in ["timeout", "mute", "kick", "ban"]:
                await interaction.response.send_message(
                    "❌ Raid action must be one of: timeout, mute, kick, ban.", ephemeral=True
                )
                return
            value = value.lower()

        set_config(interaction.guild.id, key.value, value)
        await interaction.response.send_message(f"✅ `{key.name}` updated to `{value}`", ephemeral=True)
        logger.info(f"Config updated: {key.value}={value} by {interaction.user} in guild {interaction.guild.id}")
