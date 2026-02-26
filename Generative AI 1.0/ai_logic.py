import os
import requests
import base64
import datetime
from openai import OpenAI
from google import genai
from google.genai import types
from database import get_all_info, get_chat_history

# Keys laden
O_KEY = os.getenv("OPENAI_API_KEY")
G_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

# Modelle festlegen
MODEL_OPENAI = "gpt-5-mini"  # Aktuelles OpenAI-Modell
MODEL_GEMINI = "gemini-3.0-flash"  # Aktuelles Gemini-Modell
MODEL_OPENROUTER = "arcee-ai/trinity-large-preview:free"

# Clients initialisieren
client_openai = OpenAI(api_key=O_KEY) if O_KEY else None
client_gemini = genai.Client(api_key=G_KEY) if G_KEY else None


def build_system_instruction() -> str:
    """Generiert die System-Anweisung dynamisch, damit die Zeit immer aktuell ist."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    memories = get_all_info()
    memory_context = (
        "Fakten über den Nutzer:\n" + "\n".join([f"- {k}: {v}" for k, v in memories])
        if memories
        else "Keine spezifischen Nutzerfakten vorhanden."
    )

    return (
        f"Du bist Lumina. Aktuelle Zeit in Frankfurt am Main: {now}. {memory_context} "
        "DEINE HAUPTAUFGABE: Termine im Google Kalender autonom verwalten. "
        "REGELN FÜR TERMINE:\n"
        "1. Frag NIEMALS nach Dauer, Erinnerung oder Format.\n"
        "2. Du kannst Termine hinzufügen (add), löschen (delete) oder bearbeiten (edit).\n"
        "3. Entscheide selbst: Wenn keine Dauer im Text steht, nimm 30 oder 60 Minuten.\n"
        "4. Erstelle IMMER am Ende deiner Antwort den [CALENDAR_EVENT] Block.\n"
        "5. Bei 'edit' nutze New_Title und New_Start, falls sich diese ändern.\n\n"
        "FORMAT:\n"
        "[CALENDAR_EVENT]\n"
        "Action: <add | delete | edit>\n"
        "Title: <Bisheriger Titel des Termins>\n"
        "Start: <YYYY-MM-DDTHH:MM:SSZ>\n"
        "Description: <Zusatzinfo (nur bei add/edit)>\n"
        "New_Title: <Neuer Titel (nur bei edit)>\n"
        "New_Start: <Neue Zeit YYYY-MM-DDTHH:MM:SSZ (nur bei edit)>\n"
        "[/CALENDAR_EVENT]"
    )


def fetch_llm_response(message: str, image_bytes: bytes = None) -> dict:
    """
    KI-Logik mit Fallback-Kaskade: OpenAI -> Gemini -> OpenRouter.
    Verarbeitet Text und Bild (Multimodal).
    """
    system_instruction = build_system_instruction()
    history = get_chat_history(limit=10)

    # --- SCHRITT 1: OpenAI (GPT-5 Mini) ---
    if client_openai:
        try:
            if image_bytes:
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                messages = [
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": message
                                or "Was siehst du auf diesem Bild? Extrahiere Termine, falls vorhanden.",
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

            resp = client_openai.chat.completions.create(
                model=MODEL_OPENAI, messages=messages, timeout=25
            )
            return {
                "content": resp.choices[0].message.content,
                "source": "OpenAI (GPT-5 Mini)",
            }

        except Exception as e:
            print(f"⚠️ OpenAI Fehler, wechsle zu Gemini: {e}")

    # --- SCHRITT 2: Gemini (3.0 Flash) Fallback ---
    if client_gemini:
        try:
            prompt = f"{system_instruction}\n\nNutzer: {message or 'Bildanalyse auf Termine'}"

            if image_bytes:
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
                model=MODEL_GEMINI, contents=contents
            )
            return {"content": resp.text, "source": "Gemini (3.0 Flash)"}

        except Exception as e:
            print(f"⚠️ Gemini Fehler, wechsle zu OpenRouter: {e}")

    # --- SCHRITT 3: OpenRouter (Trinity) - Text-Only Fallback ---
    if OR_KEY and not image_bytes:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OR_KEY}",
                "Content-Type": "application/json",
            }

            payload_messages = (
                [{"role": "system", "content": system_instruction}]
                + history
                + [{"role": "user", "content": message}]
            )

            payload = {
                "model": MODEL_OPENROUTER,
                "messages": payload_messages,
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

    # --- NOTFALL ---
    return {
        "content": "Entschuldigung, derzeit sind alle KI-Server überlastet oder nicht erreichbar.",
        "source": "System Error",
    }


def fetch_gemini_vision(message: str, image_bytes: bytes) -> dict:
    """Alias für Abwärtskompatibilität mit main.py und telegram_bot.py."""
    return fetch_llm_response(message, image_bytes)
