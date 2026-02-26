import os
import requests
import base64
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


def fetch_llm_response(message: str, image_bytes: bytes = None):
    """
    KI-Logik mit Fallback: OpenAI -> Gemini -> OpenRouter.
    Verarbeitet Text und Bild (Multimodal).
    """
    # 1. Kontext vorbereiten
    memories = get_all_info()
    history = get_chat_history(limit=10)

    memory_context = "Fakten über den Nutzer:\n" + "\n".join(
        [f"- {k}: {v}" for k, v in memories]
    )
    system_instruction = f"Du bist ein hilfreicher Assistent. {memory_context}"

    # --- SCHRITT 1: OpenAI (GPT-5 Mini / GPT-4o Vision) ---
    if client_openai:
        try:
            if image_bytes:
                # Bild für OpenAI vorbereiten
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                messages = [
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": message or "Was siehst du auf diesem Bild?",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ]
            else:
                messages = (
                    [{"role": "system", "content": system_instruction}]
                    + history
                    + [{"role": "user", "content": message}]
                )

            # Hinweis: Falls gpt-5-mini Vision noch nicht unterstützt, hier gpt-4o nutzen
            resp = client_openai.chat.completions.create(
                model="gpt-5-mini", messages=messages, timeout=25
            )
            return {"content": resp.choices[0].message.content, "source": "OpenAI"}
        except Exception as e:
            print(f"⚠️ OpenAI Fehler: {e}")

    # --- SCHRITT 2: Gemini (3.0 Flash) ---
    if client_gemini:
        try:
            prompt = f"{system_instruction}\n\nNutzer: {message or 'Bildanalyse'}"
            if image_bytes:
                # Korrektes Format für das neue Google GenAI SDK
                from google.genai import types

                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(
                                data=image_bytes, mime_type="image/jpeg"
                            ),
                        ],
                    )
                ]
            else:
                contents = prompt

            resp = client_gemini.models.generate_content(
                model="gemini-3.0-flash", contents=contents
            )
            return {"content": resp.text, "source": "Gemini"}
        except Exception as e:
            print(f"⚠️ Gemini Fehler: {e}")

    # --- SCHRITT 3: OpenRouter (Trinity) - Nur Text Fallback ---
    if OR_KEY and not image_bytes:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OR_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_or,
                "messages": [{"role": "system", "content": system_instruction}]
                + history
                + [{"role": "user", "content": message}],
                "reasoning": {"enabled": True},
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "source": "OpenRouter (Trinity)",
                "reasoning": data["choices"][0]["message"].get("reasoning"),
            }
        except Exception as e:
            print(f"❌ OpenRouter Fehler: {e}")

    return {"content": "Fehler: Alle KI-Provider fehlgeschlagen.", "source": "Error"}


def fetch_gemini_vision(message: str, image_bytes: bytes):
    """Alias für Abwärtskompatibilität mit main.py und telegram_bot.py"""
    return fetch_llm_response(message, image_bytes)
