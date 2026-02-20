import sqlite3
import os

# Pfad zur Datenbank im selben Ordner wie das Skript
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "assistant_memory.db")


def init_db():
    """Initialisiert die Datenbank und erstellt alle notwendigen Tabellen."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Tabelle für persönliche Fakten (Gedächtnis)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_info (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """
    )

    # 2. Tabelle für den synchronisierten Chat-Verlauf
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,           -- 'user' oder 'assistant'
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    conn.commit()
    conn.close()
    print("✅ Datenbank erfolgreich initialisiert.")


def save_info(key, value):
    """Speichert einen Fakt über den Nutzer."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_info (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()
    conn.close()


def get_all_info():
    """Läd alle gespeicherten Fakten für den System-Prompt."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_info")
    data = cursor.fetchall()
    conn.close()
    return data


def save_message(role: str, content: str):
    """Speichert eine Chat-Nachricht (egal ob von Web oder Telegram)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content)
    )
    conn.commit()
    conn.close()


def get_chat_history(limit=100):
    """Holt die letzten Nachrichten für die KI-Historie."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Wir holen die letzten Nachrichten, sortiert nach Zeit
    cursor.execute(
        """
        SELECT role, content FROM chat_history 
        ORDER BY id DESC LIMIT ?
    """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    # Wir müssen die Liste umdrehen, damit die älteste Nachricht oben steht (für die KI)
    return [{"role": r, "content": c} for r, c in reversed(rows)]


# Beim Starten der Datei wird die DB sofort vorbereitet
if __name__ == "__main__":
    init_db()
else:
    # Wird ausgeführt, wenn main.py die Datei importiert
    init_db()
