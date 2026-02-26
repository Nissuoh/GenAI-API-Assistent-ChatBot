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
from database import save_message
from calendar_utils import process_calendar_event

ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")


async def is_allowed(update: Update) -> bool:
    user_id = str(update.effective_user.id) if update.effective_user else ""
    return user_id == ALLOWED_ID


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        await update.message.reply_text("⛔ Zugriff verweigert.")
        return

    from ai_logic import fetch_llm_response

    user_msg = update.message.text
    save_message("user", user_msg)
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    response = await asyncio.to_thread(fetch_llm_response, user_msg)
    ai_msg = response.get("content", "")

    process_calendar_event(ai_msg)
    save_message("assistant", ai_msg)
    await update.message.reply_text(ai_msg)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return

    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    caption = update.message.caption or ""

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="upload_photo"
    )

    from ai_logic import fetch_gemini_vision

    response = await asyncio.to_thread(fetch_gemini_vision, caption, bytes(image_bytes))
    ai_msg = response.get("content", "")

    process_calendar_event(ai_msg)
    save_message("user", f"[Bild gesendet] {caption}")
    save_message("assistant", ai_msg)
    await update.message.reply_text(ai_msg)


def setup_telegram(token: str):
    if not token:
        print("⚠️ Kein Telegram Token gefunden!")
        return None
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return app
