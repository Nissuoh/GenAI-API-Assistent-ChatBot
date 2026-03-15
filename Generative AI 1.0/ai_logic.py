import os
import httpx
import base64
import datetime
import asyncio
import re
from openai import AsyncOpenAI
from google import genai
from google.genai import types
from database import (
    get_all_info,
    get_chat_history,
    get_latest_calendar_context,
    save_calendar_context,
    save_info,
)

O_KEY = os.getenv("OPENAI_API_KEY")
G_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL_OPENAI = "gpt-5-mini"
MODEL_GEMINI = "gemini-3.1-flash-lite"
MODEL_OPENROUTER = "openrouter/free"

client_openai = AsyncOpenAI(api_key=O_KEY) if O_KEY else None
client_gemini = genai.Client(api_key=G_KEY) if G_KEY else None


async def build_system_instruction() -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memories = await get_all_info()
    cal_context = await get_latest_calendar_context()

    memory_context = (
        "Fakten über den Nutzer:\n" + "\n".join([f"- {k}: {v}" for k, v in memories])
        if memories
        else "Keine spezifischen Nutzerfakten vorhanden."
    )

    return (
        f"Du bist Lumina, ein privater KI-Assistent. Aktuelle Zeit in Frankfurt am Main: {now}.\n\n"
        f"{memory_context}\n"
        f"KALENDER-GEDÄCHTNIS:\n{cal_context}\n\n"
        "VERHALTENSREGELN:\n"
        "1. Führe natürliche Unterhaltungen ohne ständige Erwähnung deiner Fähigkeiten.\n"
        "2. FRAGE NIEMALS NACH BESTÄTIGUNG für Kalenderaktionen. Handle SOFORT.\n"
        "3. KONTEXT-VERSTÄNDNIS: Analysiere immer den bisherigen Chatverlauf und das KALENDER-GEDÄCHTNIS! Wenn der Nutzer sagt 'Lösche das' oder 'Verschiebe den Termin', suche den exakten Termin-Namen aus dem Kontext. Nutze NIEMALS nur ein Datum als 'Title'.\n\n"
        "KALENDER-FUNKTIONEN:\n"
        "Du kannst Termine hinzufügen (add), löschen (delete), bearbeiten (edit) oder abrufen (list).\n"
        "1. Bei 'list': Verwende bei 'Title' die Anzahl der Tage (z.B. '7' oder '-7') ODER ein exaktes Datum im Format 'YYYY-MM-DD' (z.B. '2025-03-07'), wenn der Nutzer nach einem ganz bestimmten Tag in der Vergangenheit/Zukunft fragt. Nenne bei 'list' NIEMALS selbst Termine im Text!\n"
        "2. Bei 'delete' / 'edit': Verwende bei 'Title' ZWINGEND den echten Namen des Termins.\n"
        "3. WICHTIG: Erstelle den [CALENDAR_EVENT] Block nur bei echten Aktionen. Lass ungenutzte Felder KOMPLETT weg!\n\n"
        "BEISPIEL FÜR 'DELETE' MIT KONTEXT:\n"
        "[CALENDAR_EVENT]\n"
        "Action: delete\n"
        "Title: Zahnarzt\n"
        "Start: 2026-03-21T00:00:00Z\n"
        "[/CALENDAR_EVENT]"
    )


async def process_and_cache_calendar_actions(ai_msg: str):
    matches = re.findall(
        r"\[CALENDAR_EVENT\](.*?)\[/CALENDAR_EVENT\]", ai_msg, re.DOTALL
    )
    for match in matches:
        title_match = re.search(r"Title:\s*(.+)", match, re.IGNORECASE)
        action_match = re.search(r"Action:\s*(.+)", match, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            action = action_match.group(1).strip() if action_match else "add"
            # Ignoriere reine Zahlen und Datumsformate für 'list', speichere nur echte Terminnamen
            if not title.lstrip("-").isdigit() and not re.match(
                r"^\d{4}-\d{2}-\d{2}$", title
            ):
                await save_calendar_context(title, action)


async def update_long_term_memory():
    """Analysiert den Chatverlauf im Hintergrund und fasst neue Fakten zusammen."""
    history = await get_chat_history(limit=40)
    if len(history) < 5:
        return

    current_memories = await get_all_info()
    memory_text = "\n".join(
        [f"- {k}: {v}" for k, v in current_memories if k == "Zusammenfassung"]
    )
    history_text = "\n".join(
        [f"{msg['role'].upper()}: {msg['content']}" for msg in history]
    )

    prompt = (
        "Du bist der Hintergrund-Analyst für ein KI-System. Deine Aufgabe ist es, das Langzeitgedächtnis zu aktualisieren.\n"
        f"Bisherige Zusammenfassung des Nutzers:\n{memory_text}\n\n"
        f"Hier sind die neuesten Chat-Nachrichten:\n{history_text}\n\n"
        "Aufgabe: Analysiere die Nachrichten auf dauerhaft relevante Fakten (Projekte, Vorlieben, wichtige Personen, wiederkehrende Themen). "
        "Erstelle eine einzige, kompakte Stichpunktliste, die das alte Wissen mit neuen Erkenntnissen kombiniert. "
        "Antworte AUSSCHLIESSLICH mit der neuen Stichpunktliste. Keine Einleitung."
    )

    try:
        if client_openai:
            resp = await client_openai.chat.completions.create(
                model=MODEL_OPENAI,
                messages=[{"role": "user", "content": prompt}],
                timeout=30,
            )
            new_summary = resp.choices[0].message.content.strip()
            if new_summary:
                await save_info("Zusammenfassung", new_summary)
                print("🧠 Langzeitgedächtnis (OpenAI) erfolgreich aktualisiert.")
        elif client_gemini:
            resp = await asyncio.to_thread(
                client_gemini.models.generate_content,
                model=MODEL_GEMINI,
                contents=prompt,
            )
            new_summary = resp.text.strip()
            if new_summary:
                await save_info("Zusammenfassung", new_summary)
                print("🧠 Langzeitgedächtnis (Gemini) erfolgreich aktualisiert.")
    except Exception as e:
        print(f"⚠️ Fehler bei der Memory Summarization: {e}")


async def fetch_llm_response(message: str, image_bytes: bytes = None) -> dict:
    system_instruction = await build_system_instruction()
    history = await get_chat_history(limit=30)
    ai_response_text = "Entschuldigung, derzeit sind alle KI-Server überlastet."
    source = "System Error"
    reasoning = None

    if client_openai:
        try:
            if image_bytes:
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                messages = [
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": message or "Bildanalyse."},
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
            ai_response_text = resp.choices[0].message.content
            source = "OpenAI"
        except Exception as e:
            print(f"⚠️ OpenAI Fehler, wechsle zu Gemini: {e}")

    if source == "System Error" and client_gemini:
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
            resp = await asyncio.to_thread(
                client_gemini.models.generate_content,
                model=MODEL_GEMINI,
                contents=contents,
            )
            ai_response_text = resp.text
            source = "Gemini"
        except Exception as e:
            print(f"⚠️ Gemini Fehler, wechsle zu OpenRouter: {e}")

    if source == "System Error" and OR_KEY and not image_bytes:
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
            ai_response_text = data["choices"][0]["message"]["content"]
            source = "OpenRouter"
            reasoning = data["choices"][0]["message"].get("reasoning")
        except Exception as e:
            print(f"❌ OpenRouter Fehler: {e}")

    await process_and_cache_calendar_actions(ai_response_text)

    return {"content": ai_response_text, "source": source, "reasoning": reasoning}


async def fetch_gemini_vision(message: str, image_bytes: bytes) -> dict:
    return await fetch_llm_response(message, image_bytes)
