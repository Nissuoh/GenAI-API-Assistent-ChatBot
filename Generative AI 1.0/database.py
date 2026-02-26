import sqlite3
import os
from typing import List, Dict, Tuple

# Pfad zur Datenbank im selben Ordner wie das Skript
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "assistant_memory.db")


def init_db() -> None:
    """Initialisiert die Datenbank und erstellt alle notwendigen Tabellen."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 1. Tabelle für persönliche Fakten (Gedächtnis)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )

            # 2. Tabelle für den synchronisierten Chat-Verlauf
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        print("✅ Datenbank erfolgreich initialisiert.")
    except sqlite3.Error as e:
        print(f"❌ Datenbank-Fehler bei Initialisierung: {e}")


def save_info(key: str, value: str) -> None:
    """Speichert einen Fakt über den Nutzer."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_info (key, value) VALUES (?, ?)",
                (key, value),
            )
    except sqlite3.Error as e:
        print(f"⚠️ Fehler beim Speichern der Info ({key}): {e}")


def get_all_info() -> List[Tuple[str, str]]:
    """Lädt alle gespeicherten Fakten für den System-Prompt."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_info")
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"⚠️ Fehler beim Laden der Infos: {e}")
        return []


def save_message(role: str, content: str) -> None:
    """Speichert eine Chat-Nachricht (egal ob von Web oder Telegram)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO chat_history (role, content) VALUES (?, ?)",
                (role, content),
            )
    except sqlite3.Error as e:
        print(f"⚠️ Fehler beim Speichern der Nachricht: {e}")


def get_chat_history(limit: int = 100) -> List[Dict[str, str]]:
    """Holt die letzten Nachrichten für die KI-Historie."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()

        # Wir müssen die Liste umdrehen, damit die älteste Nachricht oben steht (für die KI)
        return [{"role": r, "content": c} for r, c in reversed(rows)]
    except sqlite3.Error as e:
        print(f"⚠️ Fehler beim Laden des Chat-Verlaufs: {e}")
        return []


# Beim direkten Ausführen wird die DB sofort vorbereitet
if __name__ == "__main__":
    init_db()
