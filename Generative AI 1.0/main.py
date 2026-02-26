import os
import asyncio
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Eigene Module
from database import init_db, save_message, get_chat_history
from telegram_bot import setup_telegram
from ai_logic import fetch_llm_response, fetch_gemini_vision

# Laden der Umgebungsvariablen und Initialisierung der DB
load_dotenv()
init_db()

# Ordner für Bild-Uploads erstellen
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

T_KEY = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID")
tg_app = setup_telegram(T_KEY) if T_KEY else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if tg_app:
        try:
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling(drop_pending_updates=True)
            print("🚀 System gestartet: Web & Telegram synchron.")
        except Exception as e:
            print(f"⚠️ Fehler beim Starten des Telegram Bots: {e}")
    yield
    if tg_app:
        await tg_app.updater.stop()
        await tg_app.stop()
        print("🛑 System heruntergefahren.")


app = FastAPI(lifespan=lifespan)

# Statische Verzeichnisse mounten
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str


@app.get("/history")
async def history():
    return get_chat_history(limit=50)


@app.post("/upload")
async def upload_image(file: UploadFile = File(...), message: str = Form("")):
    """Verarbeitet Bilder, speichert sie lokal, analysiert sie und synct zu Telegram."""
    try:
        image_bytes = await file.read()

        # 1. Bild lokal speichern für das Web-Interface
        ext = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        # 2. URL für Frontend und DB-Eintrag
        image_url = f"/static/uploads/{file_name}"
        db_entry = f"IMG_CONFIRM:{image_url}|{message}"
        save_message("user", db_entry)

        # 3. KI-Analyse
        response = await asyncio.to_thread(fetch_gemini_vision, message, image_bytes)
        ai_msg = response.get("content", "Keine Antwort erhalten.")
        source = response.get("source", "Unbekannt")

        # 4. KI-Antwort speichern
        save_message("assistant", ai_msg)

        # 5. SYNC ZU TELEGRAM (Jetzt mit echtem Bild!)
        if tg_app and ALLOWED_ID:
            try:
                # Wir öffnen die eben gespeicherte Datei und senden sie als Foto
                with open(file_path, "rb") as photo:
                    await tg_app.bot.send_photo(
                        chat_id=ALLOWED_ID,
                        photo=photo,
                        caption=f"👤 Du (Web):\n{message}",
                    )
                # Dann die KI-Antwort als Text
                await tg_app.bot.send_message(
                    chat_id=ALLOWED_ID, text=f"🤖 KI ({source}):\n{ai_msg}"
                )
            except Exception as tg_err:
                print(f"⚠️ Telegram Sync Fehler: {tg_err}")

        return response
    except Exception as e:
        print(f"❌ Fehler im /upload Endpunkt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        save_message("user", request.message)
        if tg_app and ALLOWED_ID:
            await tg_app.bot.send_message(
                chat_id=ALLOWED_ID, text=f"👤 Du (Web): {request.message}"
            )

        response = await asyncio.to_thread(fetch_llm_response, request.message)
        ai_msg = response.get("content", "Fehler.")

        save_message("assistant", ai_msg)
        if tg_app and ALLOWED_ID:
            await tg_app.bot.send_message(
                chat_id=ALLOWED_ID, text=f"🤖 KI ({response.get('source')}): {ai_msg}"
            )

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail="Chat-Fehler.")


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
