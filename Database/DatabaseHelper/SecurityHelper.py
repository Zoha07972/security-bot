import json
from Database.DatabaseHelper.Helper import get_guild_setting
import discord

def get_security_roles(guild_id: int):
    """Return list of role IDs configured as security roles for the guild."""
    roles_json = get_guild_setting(guild_id, "security_roles", "[]")
    try:
        return json.loads(roles_json)
    except Exception:
        return []

def has_security_role(user: discord.Member, guild_id: int) -> bool:
    """Check if the user has at least one security role."""
    allowed_roles = get_security_roles(guild_id)
    user_roles = [role.id for role in user.roles]
    return any(rid in user_roles for rid in allowed_roles)
