import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Eigene Module (Globale Imports sind jetzt sicher)
from database import save_message
from calendar_utils import process_calendar_event
from ai_logic import fetch_llm_response, fetch_gemini_vision

ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")


async def is_allowed(update: Update) -> bool:
    """Prüft, ob der Nutzer autorisiert ist."""
    user_id = str(update.effective_user.id) if update.effective_user else ""
    return user_id == ALLOWED_ID


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Verarbeitet eingehende Textnachrichten."""
    if not await is_allowed(update):
        await update.message.reply_text("⛔ Zugriff verweigert.")
        return

    user_msg = update.message.text
    if not user_msg:
        return

    save_message("user", user_msg)

    try:
        # Ladeindikator "Schreibt..." aktivieren
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )

        # KI-Antwort asynchron abrufen
        response = await asyncio.to_thread(fetch_llm_response, user_msg)
        ai_msg = response.get("content", "Fehler bei der KI-Generierung.")

        # Kalenderaktionen ausführen
        process_calendar_event(ai_msg)

        # In Datenbank speichern & an Telegram senden
        save_message("assistant", ai_msg)
        await update.message.reply_text(ai_msg)

    except Exception as e:
        print(f"❌ Fehler in handle_message: {e}")
        await update.message.reply_text(
            "⚠️ Entschuldigung, es gab einen internen Fehler bei der Verarbeitung."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Verarbeitet eingehende Fotos (Multimodal)."""
    if not await is_allowed(update):
        return

    try:
        # Ladeindikator "Ladet Foto hoch..." aktivieren
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="upload_photo"
        )

        # Bild herunterladen
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        caption = update.message.caption or ""

        # KI-Antwort asynchron abrufen
        response = await asyncio.to_thread(
            fetch_gemini_vision, caption, bytes(image_bytes)
        )
        ai_msg = response.get("content", "Fehler bei der Bildanalyse.")

        # Kalenderaktionen ausführen
        process_calendar_event(ai_msg)

        # In Datenbank speichern & an Telegram senden
        save_message("user", f"[Bild gesendet] {caption}")
        save_message("assistant", ai_msg)
        await update.message.reply_text(ai_msg)

    except Exception as e:
        print(f"❌ Fehler in handle_photo: {e}")
        await update.message.reply_text(
            "⚠️ Entschuldigung, das Bild konnte nicht verarbeitet werden."
        )


def setup_telegram(token: str):
    """Initialisiert den Telegram-Bot."""
    if not token:
        print("⚠️ Kein Telegram Token gefunden! Bot wird nicht gestartet.")
        return None

    app = ApplicationBuilder().token(token).build()

    # Handler registrieren
    app.add_handler(CommandHandler("start", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    return app
