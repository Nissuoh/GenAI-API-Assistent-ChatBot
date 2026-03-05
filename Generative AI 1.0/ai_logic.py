import os
import httpx
import base64
import datetime
import asyncio
from openai import AsyncOpenAI
from google import genai
from google.genai import types
from database import get_all_info, get_chat_history

# Keys laden
O_KEY = os.getenv("OPENAI_API_KEY")
G_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

# Modelle festlegen
MODEL_OPENAI = "gpt-5-mini"
MODEL_GEMINI = "gemini-3.1-flash-lite"
MODEL_OPENROUTER = "arcee-ai/trinity-large-preview:free"

# Asynchrone Clients initialisieren
client_openai = AsyncOpenAI(api_key=O_KEY) if O_KEY else None
client_gemini = genai.Client(api_key=G_KEY) if G_KEY else None


async def build_system_instruction() -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memories = await get_all_info()
    memory_context = (
        "Fakten über den Nutzer:\n" + "\n".join([f"- {k}: {v}" for k, v in memories])
        if memories
        else "Keine spezifischen Nutzerfakten vorhanden."
    )

    return (
        f"Du bist Lumina, ein privater KI-Assistent. Aktuelle Zeit in Frankfurt am Main: {now}. {memory_context}\n\n"
        "VERHALTENSREGELN:\n"
        "1. Führe natürliche Unterhaltungen ohne ständige Erwähnung deiner Fähigkeiten.\n"
        "2. FRAGE NIEMALS NACH BESTÄTIGUNG für Kalenderaktionen. Wenn der Nutzer nach Terminen fragt oder einen Termin eintragen will, handle SOFORT.\n\n"
        "KALENDER-FUNKTIONEN:\n"
        "Du kannst Termine hinzufügen (add), löschen (delete), bearbeiten (edit) oder abrufen (list).\n"
        "1. Bei 'list': Verwende bei 'Title' die Anzahl der Tage (z.B. '1' für heute, '7' für diese Woche).\n"
        "   WICHTIG: Nenne bei 'list' NIEMALS selbst Termine im Text! Schreibe nur einen kurzen Einleitungssatz wie 'Hier sind deine Termine:' – das System hängt die echten Daten automatisch an.\n"
        "2. Bei 'delete' oder 'edit': Verwende bei 'Title' das Suchwort.\n"
        "3. Bei 'add': Nimm 30-60 Minuten an, wenn nichts genannt ist.\n"
        "4. WICHTIG: Erstelle den [CALENDAR_EVENT] Block nur bei echten Aktionen. Lass ungenutzte/leere Felder KOMPLETT weg! Erstelle KEINE Zeilen ohne Wert.\n\n"
        "BEISPIEL FÜR 'LIST':\n"
        "[CALENDAR_EVENT]\n"
        "Action: list\n"
        "Title: 7\n"
        "[/CALENDAR_EVENT]"
    )


async def fetch_llm_response(message: str, image_bytes: bytes = None) -> dict:
    system_instruction = await build_system_instruction()
    history = await get_chat_history(limit=30)

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
                                "text": message or "Bildanalyse auf Termine.",
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

            resp = await client_openai.chat.completions.create(
                model=MODEL_OPENAI, messages=messages, timeout=25
            )
            return {
                "content": resp.choices[0].message.content,
                "source": "OpenAI (GPT-4o Mini)",
            }
        except Exception as e:
            print(f"⚠️ OpenAI Fehler, wechsle zu Gemini: {e}")

    if client_gemini:
        try:
            prompt = f"{system_instruction}\n\nNutzer: {message or 'Bildanalyse'}"
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

            # Da Google GenAI SDK noch nicht komplett nativ Async ist, wrappen wir den Call sicherheitshalber
            resp = await asyncio.to_thread(
                client_gemini.models.generate_content,
                model=MODEL_GEMINI,
                contents=contents,
            )
            return {"content": resp.text, "source": "Gemini (3.0 Flash)"}
        except Exception as e:
            print(f"⚠️ Gemini Fehler, wechsle zu OpenRouter: {e}")

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

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=45)
                resp.raise_for_status()
                data = resp.json()

            return {
                "content": data["choices"][0]["message"]["content"],
                "source": "OpenRouter (Trinity)",
                "reasoning": data["choices"][0]["message"].get("reasoning"),
            }
        except Exception as e:
            print(f"❌ OpenRouter Fehler: {e}")

    return {
        "content": "Entschuldigung, derzeit sind alle KI-Server überlastet oder nicht erreichbar.",
        "source": "System Error",
    }


async def fetch_gemini_vision(message: str, image_bytes: bytes) -> dict:
    return await fetch_llm_response(message, image_bytes)
