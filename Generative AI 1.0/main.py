import os
import json
import requests
from typing import Dict, Any, List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai
from openai import OpenAI

# --- Setup ---
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI()

# Keys
O_KEY = os.getenv("OPENAI_API_KEY")
G_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

# Modelle
openrouter_model = "arcee-ai/trinity-large-preview:free"
# openrouter_model = "stepfun/step-3.5-flash:free"
# openrouter_model = "z-ai/glm-4.5-air:free"
# openrouter_model = "deepseek/deepseek-r1-0528:free"

# Clients
client_openai = OpenAI(api_key=O_KEY) if O_KEY else None
client_gemini = genai.Client(api_key=G_KEY) if G_KEY else None

# WICHTIG: Statische Dateien (CSS/JS) verfügbar machen
if os.path.exists(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


# --- Datenmodell ---
class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []


# --- Hilfsfunktionen ---
def call_openrouter_with_reasoning(
    message: str, history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json",
    }

    # Historie für Trinity aufbereiten
    messages = history + [{"role": "user", "content": message}]

    payload = {
        "model": openrouter_model,
        "messages": messages,
        "reasoning": {"enabled": True},
    }

    response = requests.post(url, headers=headers, json=payload, timeout=45)
    response.raise_for_status()
    data = response.json()

    choice = data["choices"][0]["message"]
    return {
        "content": choice.get("content"),
        "reasoning": choice.get("reasoning_details"),  # Einheitlicher Name
        "source": "OpenRouter (Trinity)",
    }


# --- Routes ---
@app.get("/")
async def index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "index.html nicht im frontend-Ordner gefunden."}


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.message:
        raise HTTPException(status_code=400, detail="Keine Nachricht empfangen.")

    # 1. OpenRouter (Trinity)
    if OR_KEY:
        try:
            return call_openrouter_with_reasoning(request.message, request.history)
        except Exception as e:
            print(f"Trinity Fehler: {e}")

    # 2. Fallback OpenAI
    if client_openai:
        try:
            resp = client_openai.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": request.message}]
            )
            return {
                "content": resp.choices[0].message.content,
                "source": "OpenAI",
                "reasoning": None,
            }
        except Exception as e:
            print(f"OpenAI Fehler: {e}")

    # 3. Fallback Gemini
    if client_gemini:
        try:
            resp = client_gemini.models.generate_content(
                model="gemini-2.0-flash", contents=request.message
            )
            return {"content": resp.text, "source": "Gemini", "reasoning": None}
        except Exception as e:
            print(f"Gemini Fehler: {e}")

    raise HTTPException(status_code=503, detail="Alle Provider fehlgeschlagen.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
