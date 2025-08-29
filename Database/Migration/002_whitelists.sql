CREATE TABLE IF NOT EXISTS whitelists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    entity_type TEXT NOT NULL,   -- e.g. "role", "user", "channel"
    entity_id   TEXT,            -- Discord ID if applicable
    value       TEXT             -- optional (could be regex, etc.)
);

-- Index for faster lookup per guild
CREATE INDEX IF NOT EXISTS idx_whitelists
    ON whitelists (guild_id, entity_type, entity_id);
