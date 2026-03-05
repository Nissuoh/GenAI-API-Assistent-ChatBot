import os
import asyncio
import uuid
import time
import fitz  # PyMuPDF
import re
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from database import init_db, save_message, get_chat_history
from telegram_bot import setup_telegram
from ai_logic import fetch_llm_response, fetch_gemini_vision
from calendar_utils import process_calendar_event

load_dotenv()
init_db()

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

T_KEY = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")
tg_app = setup_telegram(T_KEY) if T_KEY else None


async def cleanup_uploads():
    while True:
        try:
            now = time.time()
            for filename in os.listdir(UPLOAD_DIR):
                filepath = os.path.join(UPLOAD_DIR, filename)
                if (
                    os.path.isfile(filepath)
                    and now - os.path.getctime(filepath) > 86400
                ):
                    os.remove(filepath)
        except Exception as e:
            print(f"⚠️ Cleanup-Fehler: {e}")
        await asyncio.sleep(3600)


def extract_pdf_text(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(cleanup_uploads())
    if tg_app:
        try:
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling(drop_pending_updates=True)
            print("🚀 System gestartet: Web & Telegram synchron.")
        except Exception as e:
            print(f"⚠️ Fehler beim Starten des Telegram Bots: {e}")
    yield
    cleanup_task.cancel()
    if tg_app:
        await tg_app.updater.stop()
        await tg_app.stop()
        print("🛑 System heruntergefahren.")


app = FastAPI(lifespan=lifespan)
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str


@app.get("/history")
async def history() -> List[Dict[str, Any]]:
    return get_chat_history(limit=50)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), message: str = Form("")) -> dict:
    try:
        file_bytes = await file.read()
        ext = file.filename.split(".")[-1].lower()
        file_name = f"{uuid.uuid4()}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        file_url = f"/static/uploads/{file_name}"
        save_message("user", f"FILE_CONFIRM:{file_url}|{message}")

        if file.content_type.startswith("image/"):
            response = await asyncio.to_thread(fetch_gemini_vision, message, file_bytes)
        elif file.content_type == "application/pdf":
            extracted_text = await asyncio.to_thread(extract_pdf_text, file_bytes)
            full_prompt = f"{message}\n\nDokumentinhalt:\n{extracted_text}"
            response = await asyncio.to_thread(fetch_llm_response, full_prompt)
        else:
            raise HTTPException(status_code=400, detail="Nicht unterstütztes Format.")

        ai_msg = response.get("content", "Keine Antwort erhalten.")
        cal_status = process_calendar_event(ai_msg)

        display_msg = re.sub(
            r"\[CALENDAR_EVENT\].*?\[/CALENDAR_EVENT\]", "", ai_msg, flags=re.DOTALL
        ).strip()

        if cal_status:
            display_msg += f"\n\n{cal_status}"

        save_message("assistant", display_msg)

        if tg_app and ALLOWED_ID:
            try:
                if file.content_type.startswith("image/"):
                    with open(file_path, "rb") as photo:
                        await tg_app.bot.send_photo(
                            chat_id=ALLOWED_ID,
                            photo=photo,
                            caption=f"👤 Du (Web):\n{message}",
                        )
                else:
                    with open(file_path, "rb") as doc:
                        await tg_app.bot.send_document(
                            chat_id=ALLOWED_ID,
                            document=doc,
                            caption=f"👤 Du (Web):\n{message}",
                        )
                await tg_app.bot.send_message(
                    chat_id=ALLOWED_ID, text=f"🤖 KI:\n{display_msg}"
                )
            except Exception as tg_err:
                print(f"⚠️ Telegram Sync Fehler: {tg_err}")

        response["content"] = display_msg
        return response

    except Exception as e:
        print(f"❌ Fehler im /upload Endpunkt: {e}")
        raise HTTPException(status_code=500, detail=f"Upload-Fehler: {str(e)}")


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    try:
        save_message("user", request.message)
        response = await asyncio.to_thread(fetch_llm_response, request.message)
        ai_msg = response.get("content", "Fehler bei der Antwortgenerierung.")

        cal_status = process_calendar_event(ai_msg)

        display_msg = re.sub(
            r"\[CALENDAR_EVENT\].*?\[/CALENDAR_EVENT\]", "", ai_msg, flags=re.DOTALL
        ).strip()

        if cal_status:
            display_msg += f"\n\n{cal_status}"

        save_message("assistant", display_msg)

        if tg_app and ALLOWED_ID:
            try:
                await tg_app.bot.send_message(
                    chat_id=ALLOWED_ID, text=f"👤 Du (Web):\n{request.message}"
                )
                await tg_app.bot.send_message(
                    chat_id=ALLOWED_ID, text=f"🤖 KI:\n{display_msg}"
                )
            except Exception as tg_err:
                print(f"⚠️ Telegram Sync Fehler: {tg_err}")

        response["content"] = display_msg
        return response

    except Exception as e:
        print(f"❌ Fehler im /chat Endpunkt: {e}")
        raise HTTPException(status_code=500, detail=f"Chat-Fehler: {str(e)}")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("frontend/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
