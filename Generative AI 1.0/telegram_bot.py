import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from database import save_message

ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")


# --- Hilfsfunktion: Sicherheit ---
async def is_allowed(update: Update) -> bool:
    user_id = str(update.effective_user.id) if update.effective_user else ""
    return user_id == ALLOWED_ID


# --- Handler für Textnachrichten ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        await update.message.reply_text("⛔ Zugriff verweigert.")
        return

    from ai_logic import fetch_llm_response  # Lazy Import

    user_msg = update.message.text
    save_message("user", user_msg)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    response = fetch_llm_response(user_msg)

    save_message("assistant", response["content"])
    await update.message.reply_text(response["content"])


# --- NEU: Handler für Fotos ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return

    # 1. Das Foto in der höchsten Auflösung holen
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()

    # 2. Begleittext (Caption) extrahieren
    caption = update.message.caption or ""

    # 3. "KI schreibt"-Status anzeigen
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="upload_photo"
    )

    from ai_logic import fetch_gemini_vision  # Lazy Import

    # 4. Bildanalyse via Gemini 3 Flash
    response = fetch_gemini_vision(caption, bytes(image_bytes))

    # 5. Speichern in der DB für Web-Synchronisation
    # Wir markieren es in der DB als Bildnachricht
    save_message("user", f"[Bild gesendet] {caption}")
    save_message("assistant", response["content"])

    # 6. Antwort an Telegram senden
    await update.message.reply_text(response["content"])


# --- Setup der App ---
def setup_telegram(token: str):
    if not token:
        print("⚠️ Kein Telegram Token gefunden!")
        return None

    app = ApplicationBuilder().token(token).build()

    # Start-Befehl und Text-Nachrichten
    app.add_handler(CommandHandler("start", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # NEU: Registrierung des Foto-Handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    return app
