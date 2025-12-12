import sqlite3

def get_db():
    db = sqlite3.connect("database.db")
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
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
