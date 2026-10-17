import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "kino_bot.db")


def _connect():
    path = Path(DB_PATH)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


async def init_db():
    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                banned INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                year TEXT NOT NULL,
                genre TEXT NOT NULL,
                description TEXT DEFAULT '',
                file_id TEXT NOT NULL,
                added_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        """)
        con.commit()


async def add_user(user_id, username, full_name):
    with _connect() as con:
        con.execute(
            """INSERT INTO users(user_id, username, full_name) VALUES(?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name""",
            (user_id, username, full_name)
        )
        con.commit()


async def is_banned(user_id):
    with _connect() as con:
        row = con.execute("SELECT banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row["banned"]) if row else False


async def set_banned(user_id, banned):
    with _connect() as con:
        con.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if banned else 0, user_id))
        con.commit()


async def add_movie(title, year, genre, description, file_id, added_by):
    with _connect() as con:
        cur = con.execute(
            "INSERT INTO movies(title,year,genre,description,file_id,added_by) VALUES(?,?,?,?,?,?)",
            (title, year, genre, description, file_id, added_by)
        )
        con.commit()
        return cur.lastrowid


async def get_movie(movie_id):
    with _connect() as con:
        row = con.execute(
            "SELECT id,title,year,genre,description,file_id,added_by FROM movies WHERE id=?",
            (movie_id,)
        ).fetchone()
        return tuple(row) if row else None


async def search_movies(query):
    with _connect() as con:
        rows = con.execute(
            """SELECT id,title,year,genre,description,file_id,added_by FROM movies
               WHERE title LIKE ? OR description LIKE ? ORDER BY title LIMIT 30""",
            (f"%{query}%", f"%{query}%")
        ).fetchall()
        return [tuple(row) for row in rows]


async def movies_by_year(year):
    with _connect() as con:
        rows = con.execute(
            "SELECT id,title,year,genre,description,file_id,added_by FROM movies WHERE year=? ORDER BY title LIMIT 30",
            (year,)
        ).fetchall()
        return [tuple(row) for row in rows]


async def movies_by_genre(genre):
    with _connect() as con:
        rows = con.execute(
            """SELECT id,title,year,genre,description,file_id,added_by FROM movies
               WHERE genre LIKE ? ORDER BY title LIMIT 30""",
            (f"%{genre}%",)
        ).fetchall()
        return [tuple(row) for row in rows]


async def all_movies():
    with _connect() as con:
        rows = con.execute(
            "SELECT id,title,year,genre,description,file_id,added_by FROM movies ORDER BY id DESC LIMIT 100"
        ).fetchall()
        return [tuple(row) for row in rows]


async def delete_movie(movie_id):
    with _connect() as con:
        cur = con.execute("DELETE FROM movies WHERE id=?", (movie_id,))
        con.commit()
        return cur.rowcount > 0


async def get_setting(key):
    with _connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""


async def set_setting(key, value):
    with _connect() as con:
        con.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        con.commit()


async def user_count():
    with _connect() as con:
        return con.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


async def movie_count():
    with _connect() as con:
        return con.execute("SELECT COUNT(*) AS n FROM movies").fetchone()["n"]


async def latest_users(limit=30):
    with _connect() as con:
        rows = con.execute(
            "SELECT user_id,username,full_name,banned FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [tuple(row) for row in rows]


async def all_user_ids():
    with _connect() as con:
        rows = con.execute("SELECT user_id FROM users WHERE banned=0").fetchall()
        return [row["user_id"] for row in rows]
