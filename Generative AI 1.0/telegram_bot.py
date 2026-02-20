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


async def is_allowed(update: Update) -> bool:
    user_id = str(update.effective_user.id) if update.effective_user else ""
    return user_id == ALLOWED_ID


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        await update.message.reply_text("⛔ Zugriff verweigert.")
        return

    from ai_logic import (
        fetch_llm_response,
    )  # Lazy Import um Circular Imports zu vermeiden

    user_msg = update.message.text
    save_message("user", user_msg)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )
    response = fetch_llm_response(user_msg)

    save_message("assistant", response["content"])
    await update.message.reply_text(response["content"])


def setup_telegram(token: str):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
