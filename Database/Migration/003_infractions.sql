CREATE TABLE IF NOT EXISTS infractions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id  TEXT NOT NULL,
    user_id   TEXT NOT NULL,
    action    TEXT NOT NULL,        -- e.g. "warn", "ban", "kick"
    reason    TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_infractions
    ON infractions (guild_id, user_id);
