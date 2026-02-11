import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from openai import OpenAI
from google import genai
import uvicorn

# Pfade absolut setzen
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

load_dotenv()

# Keys abrufen
o_key = os.getenv("OPENAI_API_KEY")
g_key = os.getenv("GEMINI_API_KEY")

# Validierung der Keys (Verhindert deinen aktuellen Fehler)
if not o_key or not g_key:
    raise ValueError(
        f"API-Keys fehlen! OpenAI: {'OK' if o_key else 'FEHLT'}, Gemini: {'OK' if g_key else 'FEHLT'}"
    )

app = FastAPI()

# Clients initialisieren
client_openai = OpenAI(api_key=o_key)
client_gemini = genai.Client(api_key=g_key)

# Statische Dateien
if not os.path.exists(FRONTEND_DIR):
    raise RuntimeError(f"Ordner nicht gefunden: {FRONTEND_DIR}")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
async def main():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.post("/chat")
async def chat(message: str):  # 'None' erlaubt flexiblere Abfragen
    """
    Verarbeitet Chat-Anfragen. Erwartet 'message' als Query-Parameter.
    Beispiel: /chat?message=Hallo
    """
    if not message:
        # Shovals Kritik: Validierung hinzufügen
        raise HTTPException(status_code=400, detail="Parameter 'message' fehlt.")

    try:
        # OpenAI Primärversuch
        response = client_openai.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": message}]
        )
        return {"response": response.choices[0].message.content, "source": "OpenAI"}

    except Exception as e:
        print(f"OpenAI Fehler: {e}")
        try:
            # Fallback zu Gemini
            response = client_gemini.models.generate_content(
                model="gemini-2.0-flash", contents=message
            )
            return {"response": response.text, "source": "Gemini"}
        except Exception as ge:
            return {"response": "Fehler: Beide APIs sind offline.", "details": str(ge)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
