CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id     TEXT NOT NULL,
    setting_key  TEXT NOT NULL,
    setting_value TEXT,
    PRIMARY KEY (guild_id, setting_key)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_guild_settings
    ON guild_settings (guild_id, setting_key);
