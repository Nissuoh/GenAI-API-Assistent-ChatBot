import aiosqlite
import os
from typing import List, Dict, Tuple

# Pfad zur Datenbank im selben Ordner wie das Skript
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "assistant_memory.db")


async def init_db() -> None:
    """Initialisiert die asynchrone Datenbank und erstellt alle notwendigen Tabellen."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
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
            await conn.commit()
        print("✅ Datenbank erfolgreich initialisiert (async).")
    except Exception as e:
        print(f"❌ Datenbank-Fehler bei Initialisierung: {e}")


async def save_info(key: str, value: str) -> None:
    """Speichert einen Fakt über den Nutzer."""
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
    """Lädt alle gespeicherten Fakten für den System-Prompt."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute("SELECT key, value FROM user_info") as cursor:
                return await cursor.fetchall()
    except Exception as e:
        print(f"⚠️ Fehler beim Laden der Infos: {e}")
        return []


async def save_message(role: str, content: str) -> None:
    """Speichert eine Chat-Nachricht (egal ob von Web oder Telegram)."""
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
    """Holt die letzten Nachrichten für die KI-Historie."""
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


if __name__ == "__main__":
    import asyncio

    asyncio.run(init_db())
