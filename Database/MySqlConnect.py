# -----------------------------------------------------------------------------
# File Name   : db/connection.py
# Description : SQLite connection pool with migration runner. Ensures that all
#               .sql migration files in the migrations directory are applied
#               automatically on startup. Tracks applied migrations in a
#               schema_migrations table so each migration is executed only once.
#
# Author      : X
# Created On  : 17/08/2025
# Last Updated: 29/08/2025
# -----------------------------------------------------------------------------
import sqlite3
import threading
from pathlib import Path
from datetime import datetime

from ConsoleHelper.ConsoleMessage import ConsoleMessage

# Initialize logger
logger = ConsoleMessage()

DB_FILE = "database.db"
MIGRATIONS_DIR = Path(__file__).parent / "Migration"   # ✅ lowercase recommended


# -----------------------------------------------------------------------------
# Connection Pool with Context Manager Support
# -----------------------------------------------------------------------------
class SQLiteConnectionPool:
    def __init__(self, max_connections=5):
        self._lock = threading.Lock()
        self._connections = []
        self._max_connections = max_connections

    def get_connection(self):
        """Return a context-managed connection from pool"""
        with self._lock:
            if self._connections:
                conn = self._connections.pop()
            else:
                conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL;")  # ✅ better concurrency
        return SQLiteConnectionContext(self, conn)

    def release_connection(self, conn):
        """Return connection back to pool or close it if pool is full"""
        with self._lock:
            if len(self._connections) < self._max_connections:
                self._connections.append(conn)
            else:
                conn.close()


class SQLiteConnectionContext:
    """Context manager wrapper for pooled connections"""
    def __init__(self, pool, conn):
        self.pool = pool
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_value, traceback):
        self.pool.release_connection(self.conn)


# -----------------------------------------------------------------------------
# Migration Runner
# -----------------------------------------------------------------------------
def run_migrations(pool):
    """Run all .sql files in migrations folder (only once each)"""
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # Ensure schema_migrations table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL
            )
        """)
        conn.commit()

        # Get already applied migrations
        cursor.execute("SELECT filename FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}

        # Apply new migrations
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in applied:
                logger.debug(f"Skipping already applied migration: {sql_file.name}")
                continue

            with open(sql_file, "r", encoding="utf-8") as f:
                query = f.read().strip()
                if query:
                    try:
                        cursor.executescript(query)
                        cursor.execute(
                            "INSERT INTO schema_migrations (filename, applied_at) VALUES (?, ?)",
                            (sql_file.name, datetime.now().isoformat())
                        )
                        conn.commit()
                        logger.info(f" Migrated: {sql_file.name}")
                    except Exception as e:
                        logger.error(f" Migration failed ({sql_file.name}): {e}")
                        conn.rollback()
                        break   # ✅ stop if a migration fails


# -----------------------------------------------------------------------------
# End of File: connection.py
# -----------------------------------------------------------------------------
