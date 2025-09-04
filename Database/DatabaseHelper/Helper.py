import threading
from Database.MySqlConnect import SQLiteConnectionPool
from ConsoleHelper.ConsoleMessage import ConsoleMessage  # For logging

pool = SQLiteConnectionPool()
logger = ConsoleMessage()

# -------------------------
# In-Memory Mirrors
# -------------------------
_guild_settings = {}  # {guild_id: {setting_key: setting_value}}
_whitelists = {}      # {guild_id: [{entity_type, entity_id, value}]}
_lock = threading.Lock()


# -------------------------
# Mirror Loaders
# -------------------------
def load_mirrors():
    """Load guild_settings and whitelists into memory at startup."""
    global _guild_settings, _whitelists
    with _lock:
        _guild_settings.clear()
        _whitelists.clear()

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Load guild_settings
            cursor.execute("SELECT guild_id, setting_key, setting_value FROM guild_settings")
            rows = cursor.fetchall()
            for guild_id, key, value in rows:
                guild_id = int(guild_id)  # Ensure int keys
                if guild_id not in _guild_settings:
                    _guild_settings[guild_id] = {}
                _guild_settings[guild_id][key] = value
            logger.debug(f"Loaded {len(rows)} guild settings into memory.")

            # Load whitelists
            cursor.execute("SELECT guild_id, entity_type, entity_id, value FROM whitelists")
            rows = cursor.fetchall()
            for guild_id, etype, eid, val in rows:
                guild_id = int(guild_id)
                if guild_id not in _whitelists:
                    _whitelists[guild_id] = []
                _whitelists[guild_id].append({
                    "entity_type": etype,
                    "entity_id": eid,
                    "value": val
                })
            logger.debug(f"Loaded {len(rows)} whitelist entries into memory.")

            cursor.close()


# -------------------------
# Guild Settings Accessors
# -------------------------
def get_guild_setting(guild_id, key, default=None):
    """Get a setting quickly from memory."""
    guild_id = int(guild_id)
    return _guild_settings.get(guild_id, {}).get(key, default)


def set_guild_setting(guild_id, key, value):
    """Update DB and in-memory mirror for guild_settings."""
    guild_id = int(guild_id)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO guild_settings (guild_id, setting_key, setting_value)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, setting_key)
            DO UPDATE SET setting_value=excluded.setting_value
        """, (guild_id, key, value))
        conn.commit()
        cursor.close()

    # Update mirror
    with _lock:
        if guild_id not in _guild_settings:
            _guild_settings[guild_id] = {}
        _guild_settings[guild_id][key] = value


# -------------------------
# Whitelist Accessors
# -------------------------
def get_whitelist(guild_id):
    """Get whitelist entries for a guild."""
    guild_id = int(guild_id)
    return _whitelists.get(guild_id, [])


def add_whitelist(guild_id, etype, eid=None, val=None):
    """Add whitelist entry in DB and mirror."""
    guild_id = int(guild_id)
    inserted = False
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO whitelists (guild_id, entity_type, entity_id, value)
            VALUES (?, ?, ?, ?)
        """, (guild_id, etype, eid, val))
        if cursor.rowcount > 0:
            inserted = True
        conn.commit()
        cursor.close()

    if inserted:
        with _lock:
            if guild_id not in _whitelists:
                _whitelists[guild_id] = []
            _whitelists[guild_id].append({
                "entity_type": etype,
                "entity_id": eid,
                "value": val
            })


def remove_whitelist(guild_id, etype, eid=None, val=None):
    """Remove whitelist entry in DB and mirror."""
    guild_id = int(guild_id)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM whitelists
            WHERE guild_id=? AND entity_type=? 
              AND (entity_id=? OR (entity_id IS NULL AND ? IS NULL))
              AND (value=? OR (value IS NULL AND ? IS NULL))
        """, (guild_id, etype, eid, eid, val, val))
        conn.commit()
        cursor.close()

    # Update mirror
    with _lock:
        if guild_id in _whitelists:
            _whitelists[guild_id] = [
                x for x in _whitelists[guild_id]
                if not (x["entity_type"] == etype and x["entity_id"] == eid and x["value"] == val)
            ]


# -------------------------
# Raw DB Helpers
# -------------------------
def execute(query, params=()):
    """Execute a write query (for logs/infractions/etc)."""
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
        finally:
            cursor.close()


def fetch_one(query, params=()):
    """Fetch one row directly from DB (no mirror)."""
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            cursor.close()


def fetch_all(query, params=()):
    """Fetch multiple rows directly from DB (no mirror)."""
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            cursor.close()
