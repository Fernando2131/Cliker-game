import sqlite3
import time

DB_PATH = "database.db"

def get_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db

def now():
    return time.time()

def init_db():
    db = get_db()
    # tabla users principal (crea si no existe)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            coins REAL DEFAULT 0,
            upgrades TEXT DEFAULT '{}',
            rebirths INTEGER DEFAULT 0
        )
    """)
    db.commit()

    # migraciones seguras: añadir columnas si no existen
    def try_add(col_name, col_type, default=None):
        try:
            db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            if default is not None:
                db.execute(f"UPDATE users SET {col_name} = ?", (default,))
            db.commit()
        except Exception:
            pass

    # columnas para seguridad y leaderboard
    try_add("last_save_ts", "REAL", 0)
    try_add("last_coins", "REAL", 0)
    try_add("save_count_min", "INTEGER", 0)
    try_add("suspicious_count", "INTEGER", 0)
    try_add("banned_until", "REAL", 0)
    try_add("last_ip", "TEXT", "")
    try_add("highscore_coins", "REAL", 0)  # para leaderboard
    try_add("max_cps_record", "REAL", 0)    # mejor CPS registrado
    try_add("best_cps", "REAL", 0)


    # tabla de logs de seguridad
    db.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event TEXT,
            detail TEXT,
            ip TEXT,
            ts REAL
        )
    """)
    db.commit()

    # tabla de eventos de click (registro por click)
    db.execute("""
        CREATE TABLE IF NOT EXISTS click_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ts REAL,
            ip TEXT
        )
    """)
    db.commit()

    # índices para consultas rápidas
    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_click_user_ts ON click_events(user_id, ts)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_security_user ON security_logs(user_id)")
        db.commit()
    except Exception:
        pass
