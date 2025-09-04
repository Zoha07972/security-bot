from Database.MySqlConnect import SQLiteConnectionPool
from ConsoleHelper.ConsoleMessage import ConsoleMessage
import datetime

pool = SQLiteConnectionPool()
logger = ConsoleMessage()

def log_audit(guild_id: int, action: str, actor_id: int, target_id: int = None, details: str = None) -> bool:
    """Write an admin action into audit_logs (append-only)."""
    try:
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (guild_id, event_type, actor_id, target_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                guild_id,
                action,  # stored in event_type column
                actor_id,
                target_id,
                details,
                datetime.datetime.utcnow().isoformat()
            ))
            conn.commit()
            cursor.close()
        logger.info(f" Audit log recorded: {action} by {actor_id} (guild={guild_id})")
        return True
    except Exception as e:
        logger.error(f" Failed to log audit action: {e}")
        return False


def log_security_event(guild_id: int, event_type: str, user_id: int, details: str = None) -> bool:
    """Write a detected security event (append-only)."""
    try:
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO security_events (guild_id, event_type, user_id, details, detected_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                guild_id,
                event_type,
                user_id,
                details,
                datetime.datetime.utcnow().isoformat()
            ))
            conn.commit()
            cursor.close()
        logger.info(f" Security event: {event_type} detected for user {user_id} (guild={guild_id})")
        return True
    except Exception as e:
        logger.error(f" Failed to log security event: {e}")
        return False
