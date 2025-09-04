CREATE TABLE IF NOT EXISTS security_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   TEXT NOT NULL,
    user_id    TEXT,                 -- Added this column
    event_type TEXT NOT NULL,        -- e.g. "spam_detected", "mass_join"
    details    TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
