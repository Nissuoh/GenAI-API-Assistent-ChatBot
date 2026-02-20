import os
import requests
from openai import OpenAI
from google import genai
from database import get_all_info, get_chat_history

# Keys laden
O_KEY = os.getenv("OPENAI_API_KEY")
G_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

# Modelle
model_or = "arcee-ai/trinity-large-preview:free"

# Clients initialisieren
client_openai = OpenAI(api_key=O_KEY) if O_KEY else None
client_gemini = genai.Client(api_key=G_KEY) if G_KEY else None


def fetch_llm_response(message: str):
    """KI-Logik mit neuer Fallback-Reihenfolge: OpenAI -> Gemini -> OpenRouter"""

    # 1. Kontext vorbereiten
    memories = get_all_info()
    history = get_chat_history(limit=10)

    memory_context = "Fakten über den Nutzer:\n" + "\n".join(
        [f"- {k}: {v}" for k, v in memories]
    )
    system_instruction = {
        "role": "system",
        "content": f"Du bist ein hilfreicher Assistent. {memory_context}",
    }
    full_messages = (
        [system_instruction] + history + [{"role": "user", "content": message}]
    )

    # --- SCHRITT 1: OpenAI (GPT-4o) ---
    if client_openai:
        try:
            resp = client_openai.chat.completions.create(
                model="gpt-5-mini", messages=full_messages, timeout=20
            )
            return {"content": resp.choices[0].message.content, "source": "OpenAI"}
        except Exception as e:
            print(f"⚠️ OpenAI Fehler: {e}")

    # --- SCHRITT 2: Gemini (2.0 Flash) ---
    if client_gemini:
        try:
            # Einfacher Prompt für Gemini (kombiniert System-Anweisung und Nachricht)
            prompt = f"{system_instruction['content']}\n\nNutzer: {message}"
            resp = client_gemini.models.generate_content(
                model="gemini-3.0-flash", contents=prompt
            )
            return {"content": resp.text, "source": "Gemini"}
        except Exception as e:
            print(f"⚠️ Gemini Fehler: {e}")

    # --- SCHRITT 3: OpenRouter (Trinity) ---
    if OR_KEY:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OR_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_or,
                "messages": full_messages,
                "reasoning": {"enabled": True},
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "source": "OpenRouter (Trinity)",
                "reasoning": data["choices"][0]["message"].get(
                    "reasoning"
                ),  # Falls vorhanden
            }
        except Exception as e:
            print(f"❌ OpenRouter Fehler: {e}")

    return {
        "content": "Fehler: Alle KI-Provider (OpenAI, Gemini, OpenRouter) sind fehlgeschlagen.",
        "source": "Error",
    }
