import os
import asyncio
import fitz  # PyMuPDF
import re
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
from ai_logic import fetch_llm_response, fetch_gemini_vision

ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")


async def is_allowed(update: Update) -> bool:
    user_id = str(update.effective_user.id) if update.effective_user else ""
    return user_id == ALLOWED_ID


def extract_pdf_text(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


async def background_calendar_task_tg(ai_msg: str, display_msg: str, bot, chat_id):
    """Hintergrund-Task für Telegram, der nachträglich das Kalenderergebnis liefert"""
    cal_status = await asyncio.to_thread(process_calendar_event, ai_msg)

    if cal_status:
        display_msg += f"\n\n{cal_status}"
        try:
            await bot.send_message(chat_id=chat_id, text=f"🗓️ **Update:**\n{cal_status}")
        except Exception as e:
            print(f"⚠️ Background Telegram Error: {e}")

    await save_message("assistant", display_msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_allowed(update):
        await update.message.reply_text("⛔ Zugriff verweigert.")
        return

    user_msg = update.message.text
    if not user_msg:
        return

    await save_message("user", user_msg)

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )

        # Nativer Async-Aufruf
        response = await fetch_llm_response(user_msg)
        ai_msg = response.get("content", "Fehler bei der KI-Generierung.")

        display_msg = re.sub(
            r"\[CALENDAR_EVENT\].*?\[/CALENDAR_EVENT\]", "", ai_msg, flags=re.DOTALL
        ).strip()

        # Nutzer bekommt SOFORT die Antwort
        await update.message.reply_text(display_msg)

        # Kalender & Speichern wird unsichtbar in den Hintergrund ausgelagert
        asyncio.create_task(
            background_calendar_task_tg(
                ai_msg, display_msg, context.bot, update.effective_chat.id
            )
        )

    except Exception as e:
        print(f"❌ Fehler in handle_message: {e}")
        await update.message.reply_text(
            "⚠️ Entschuldigung, es gab einen internen Fehler bei der Verarbeitung."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_allowed(update):
        return

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="upload_photo"
        )
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        caption = update.message.caption or ""

        response = await fetch_gemini_vision(caption, bytes(image_bytes))
        ai_msg = response.get("content", "Fehler bei der Bildanalyse.")

        display_msg = re.sub(
            r"\[CALENDAR_EVENT\].*?\[/CALENDAR_EVENT\]", "", ai_msg, flags=re.DOTALL
        ).strip()

        await update.message.reply_text(display_msg)

        await save_message("user", f"[Bild gesendet] {caption}")
        asyncio.create_task(
            background_calendar_task_tg(
                ai_msg, display_msg, context.bot, update.effective_chat.id
            )
        )

    except Exception as e:
        print(f"❌ Fehler in handle_photo: {e}")
        await update.message.reply_text(
            "⚠️ Entschuldigung, das Bild konnte nicht verarbeitet werden."
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_allowed(update):
        return

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
        doc_file = await update.message.document.get_file()
        doc_bytes = await doc_file.download_as_bytearray()
        caption = update.message.caption or "Extrahiere Termine aus diesem Dokument."
        mime_type = update.message.document.mime_type

        if mime_type == "application/pdf":
            extracted_text = await asyncio.to_thread(extract_pdf_text, doc_bytes)
            full_prompt = f"{caption}\n\nDokumentinhalt:\n{extracted_text}"
            response = await fetch_llm_response(full_prompt)
        else:
            await update.message.reply_text(
                "⚠️ Nur PDF-Dokumente werden aktuell unterstützt."
            )
            return

        ai_msg = response.get("content", "Fehler bei der Dokumentenanalyse.")

        display_msg = re.sub(
            r"\[CALENDAR_EVENT\].*?\[/CALENDAR_EVENT\]", "", ai_msg, flags=re.DOTALL
        ).strip()

        await update.message.reply_text(display_msg)

        await save_message("user", f"[Dokument gesendet] {caption}")
        asyncio.create_task(
            background_calendar_task_tg(
                ai_msg, display_msg, context.bot, update.effective_chat.id
            )
        )

    except Exception as e:
        print(f"❌ Fehler in handle_document: {e}")
        await update.message.reply_text(
            "⚠️ Entschuldigung, das Dokument konnte nicht verarbeitet werden."
        )


def setup_telegram(token: str):
    if not token:
        print("⚠️ Kein Telegram Token gefunden! Bot wird nicht gestartet.")
        return None

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    return app
