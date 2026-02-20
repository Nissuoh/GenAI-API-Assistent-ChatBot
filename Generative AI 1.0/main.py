import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Eigene Module
from database import init_db, save_message, get_chat_history
from telegram_bot import setup_telegram
from ai_logic import fetch_llm_response

load_dotenv()
init_db()

T_KEY = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")
tg_app = setup_telegram(T_KEY) if T_KEY else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if tg_app:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        print("🚀 System gestartet: Web & Telegram synchron.")
    yield
    if tg_app:
        await tg_app.updater.stop()
        await tg_app.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


class ChatRequest(BaseModel):
    message: str


@app.get("/history")
async def history():
    return get_chat_history(limit=50)


@app.post("/chat")
async def chat(request: ChatRequest):
    save_message("user", request.message)

    # Sync zu Telegram (deine Nachricht)
    if tg_app:
        await tg_app.bot.send_message(
            chat_id=ALLOWED_ID, text=f"👤 Du (Web): {request.message}"
        )

    response = fetch_llm_response(request.message)
    save_message("assistant", response["content"])

    # Sync zu Telegram (KI Antwort)
    if tg_app:
        await tg_app.bot.send_message(
            chat_id=ALLOWED_ID, text=f"🤖 KI (Web): {response['content']}"
        )

    return response


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
