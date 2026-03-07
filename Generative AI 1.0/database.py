import aiosqlite
import os
from typing import List, Dict, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "assistant_memory.db")


async def init_db() -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id TEXT PRIMARY KEY,
                    name TEXT,
                    role TEXT DEFAULT 'user'
                )
            """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendar_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT,
                    action TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            await conn.commit()
        print("✅ Datenbank erfolgreich initialisiert (async).")
    except Exception as e:
        print(f"❌ Datenbank-Fehler bei Initialisierung: {e}")


async def save_info(key: str, value: str) -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO user_info (key, value) VALUES (?, ?)",
                (key, value),
            )
            await conn.commit()
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern der Info ({key}): {e}")


async def get_all_info() -> List[Tuple[str, str]]:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute("SELECT key, value FROM user_info") as cursor:
                return await cursor.fetchall()
    except Exception as e:
        print(f"⚠️ Fehler beim Laden der Infos: {e}")
        return []


async def save_message(role: str, content: str) -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO chat_history (role, content) VALUES (?, ?)",
                (role, content),
            )
            await conn.commit()
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern der Nachricht: {e}")


async def get_chat_history(limit: int = 100) -> List[Dict[str, str]]:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]
    except Exception as e:
        print(f"⚠️ Fehler beim Laden des Chat-Verlaufs: {e}")
        return []


async def save_calendar_context(event_name: str, action: str) -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO calendar_cache (event_name, action) VALUES (?, ?)",
                (event_name, action),
            )
            await conn.commit()
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern des Kalender-Kontexts: {e}")


async def get_latest_calendar_context() -> str:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                "SELECT event_name, action FROM calendar_cache ORDER BY id DESC LIMIT 5"
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            return "Kein letzter Kalender-Kontext."
        context_str = ", ".join([f"'{r[0]}' ({r[1]})" for r in rows])
        return f"Zuletzt bearbeitete Termine im Kalender: {context_str}"
    except Exception as e:
        return ""


if __name__ == "__main__":
    import asyncio

    asyncio.run(init_db())
    print("Datenbank-Setup abgeschlossen.")
