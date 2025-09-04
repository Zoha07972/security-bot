CREATE TABLE IF NOT EXISTS anti_spam (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    warnings INT DEFAULT 0,
    last_warning TIMESTAMP NULL,
    timeout_until TIMESTAMP NULL,
    PRIMARY KEY (guild_id, user_id)
);