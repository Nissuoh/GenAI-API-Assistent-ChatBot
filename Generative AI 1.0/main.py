import os
import asyncio
import uuid
import time
import fitz
import re
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from database import init_db, save_message, get_chat_history
from telegram_bot import setup_telegram
from ai_logic import fetch_llm_response, fetch_gemini_vision, update_long_term_memory
from calendar_utils import process_calendar_event
import google_calendar

load_dotenv()
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

T_KEY = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")
tg_app = setup_telegram(T_KEY) if T_KEY else None

ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "application/pdf": "pdf",
}


async def cleanup_uploads():
    while True:
        try:
            now = time.time()
            for f in os.listdir(UPLOAD_DIR):
                path = os.path.join(UPLOAD_DIR, f)
                if os.path.isfile(path) and now - os.path.getmtime(path) > 86400:
                    os.remove(path)
        except:
            pass
        await asyncio.sleep(3600)


async def memory_loop():
    while True:
        await asyncio.sleep(3600)
        try:
            await update_long_term_memory()
        except:
            pass


def extract_pdf_text(b: bytes) -> str:
    return "\n".join(p.get_text() for p in fitz.open(stream=b, filetype="pdf"))


async def background_calendar_task(ai_msg: str, msg_save: str, bot_app=None):
    cal_status = await asyncio.to_thread(process_calendar_event, ai_msg)
    if cal_status:
        msg_save += f"\n\n{cal_status}"
        if bot_app and ALLOWED_ID:
            try:
                await bot_app.bot.send_message(
                    chat_id=ALLOWED_ID, text=f"🗓️ **Update:**\n{cal_status}"
                )
            except:
                pass
    await save_message("assistant", msg_save)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    c_task = asyncio.create_task(cleanup_uploads())
    m_task = asyncio.create_task(memory_loop())
    if tg_app:
        try:
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling(drop_pending_updates=True)
        except:
            pass
    yield
    c_task.cancel()
    m_task.cancel()
    if tg_app:
        await tg_app.updater.stop()
        await tg_app.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str


@app.get("/history")
async def history():
    return await get_chat_history(limit=50)


@app.get("/calendar")
async def calendar_data(year: Optional[int] = None, month: Optional[int] = None):
    events = await asyncio.to_thread(google_calendar.get_events_json, year, month)
    return {"events": events}


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    message: str = Form(""),
    bg_tasks: BackgroundTasks = BackgroundTasks(),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "Format nicht unterstützt.")
    ext = ALLOWED_MIME_TYPES[file.content_type]
    b = await file.read()
    name = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(b)

    url = f"/static/uploads/{name}"
    await save_message("user", f"FILE_CONFIRM:{url}|{message}")

    if file.content_type.startswith("image/"):
        res = await fetch_gemini_vision(message, b)
    else:
        res = await fetch_llm_response(
            f"{message}\n\nDokumentinhalt:\n{await asyncio.to_thread(extract_pdf_text, b)}"
        )

    ai_msg = res.get("content", "")
    disp = re.sub(
        r"\[CALENDAR_EVENT\].*?\[/CALENDAR_EVENT\]", "", ai_msg, flags=re.DOTALL
    ).strip()

    if tg_app and ALLOWED_ID:
        try:
            with open(path, "rb") as f:
                if file.content_type.startswith("image/"):
                    await tg_app.bot.send_photo(
                        chat_id=ALLOWED_ID, photo=f, caption=f"Du:\n{message}"
                    )
                else:
                    await tg_app.bot.send_document(
                        chat_id=ALLOWED_ID, document=f, caption=f"Du:\n{message}"
                    )
            await tg_app.bot.send_message(chat_id=ALLOWED_ID, text=f"KI:\n{disp}")
        except:
            pass

    bg_tasks.add_task(background_calendar_task, ai_msg, disp, tg_app)
    return {"content": disp}


@app.post("/chat")
async def chat(req: ChatRequest, bg_tasks: BackgroundTasks):
    await save_message("user", req.message)
    res = await fetch_llm_response(req.message)
    ai_msg = res.get("content", "")
    disp = re.sub(
        r"\[CALENDAR_EVENT\].*?\[/CALENDAR_EVENT\]", "", ai_msg, flags=re.DOTALL
    ).strip()

    if tg_app and ALLOWED_ID:
        try:
            await tg_app.bot.send_message(
                chat_id=ALLOWED_ID, text=f"Du:\n{req.message}"
            )
            await tg_app.bot.send_message(chat_id=ALLOWED_ID, text=f"KI:\n{disp}")
        except:
            pass

    bg_tasks.add_task(background_calendar_task, ai_msg, disp, tg_app)
    return {"content": disp}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
