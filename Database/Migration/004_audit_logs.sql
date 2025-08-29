CREATE TABLE IF NOT EXISTS audit_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   TEXT NOT NULL,
    event_type TEXT NOT NULL,    -- e.g. "role_update", "kick", "raid_detected"
    actor_id   TEXT NOT NULL,    -- who performed the action
    target_id  TEXT,             -- who/what was targeted
    details    TEXT,
    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
