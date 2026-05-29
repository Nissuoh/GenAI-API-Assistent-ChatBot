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
    get_all_notes,
)

O_KEY = os.getenv("OPENAI_API_KEY")
G_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL_OPENAI = "gpt-5-mini"
MODEL_GEMINI = "gemini-3.1-flash-lite"
MODEL_OPENROUTER = "openrouter/free"

client_openai = AsyncOpenAI(api_key=O_KEY) if O_KEY else None
client_gemini = genai.Client(api_key=G_KEY) if G_KEY else None

# Globaler wiederverwendbarer HTTP-Client für schnellere API-Aufrufe (Keep-Alive)
http_client = httpx.AsyncClient()


async def close_http_client():
    await http_client.aclose()


async def build_system_instruction() -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memories = await get_all_info()
    cal_context = await get_latest_calendar_context()
    notes = await get_all_notes()

    memory_context = (
        "Fakten über den Nutzer:\n" + "\n".join([f"- {k}: {v}" for k, v in memories])
        if memories
        else "Keine spezifischen Nutzerfakten vorhanden."
    )

    notes_context = (
        "NOTIZBLOCK-INHALT:\n" + "\n".join([f"- ID: {n['id']} | Inhalt: {n['content']}" for n in notes])
        if notes
        else "Der Notizblock ist leer."
    )

    return (
        f"Du bist Lumina, ein privater KI-Assistent. Aktuelle Zeit in Frankfurt am Main: {now}.\n\n"
        f"{memory_context}\n\n"
        f"KALENDER-GEDÄCHTNIS:\n{cal_context}\n\n"
        f"NOTIZBLOCK-GEDÄCHTNIS:\n{notes_context}\n\n"
        "VERHALTENSREGELN:\n"
        "1. Führe natürliche Unterhaltungen ohne ständige Erwähnung deiner Fähigkeiten.\n"
        "2. FRAGE NIEMALS NACH BESTÄTIGUNG für Kalender- oder Notizblock-Aktionen. Handle SOFORT.\n"
        "3. KONTEXT-VERSTÄNDNIS: Analysiere immer den bisherigen Chatverlauf und das KALENDER-GEDÄCHTNIS / NOTIZBLOCK-GEDÄCHTNIS!\n"
        "4. INTELLIGENTE KLASSIFIZIERUNG (Entscheidung zwischen Kalender und Notizblock):\n"
        "   - KALENDER: Feste Termine, Verabredungen oder Fristen mit einem konkreten Datum und/oder einer Uhrzeit (z. B. 'Meeting morgen um 14 Uhr', 'Zahnarzt am Freitag', 'Konzert am 15. Juni'). Erstelle hierfür einen [CALENDAR_EVENT] Block.\n"
        "   - NOTIZBLOCK: Allgemeine Gedanken, Einkaufslisten, unstrukturierte Erinnerungen, Ideen oder To-Dos ohne festen Kalenderslot (z. B. 'Erinnere mich an Milch kaufen', 'Ich muss das Buch lesen', 'Klopapier holen', 'Coole Geschäftsidee aufschreiben'). Erstelle hierfür einen [NOTE_EVENT] Block.\n\n"
        "KALENDER-FUNKTIONEN:\n"
        "Du kannst Termine hinzufügen (add), löschen (delete), bearbeiten (edit) oder abrufen (list).\n"
        "1. Bei 'list': Verwende bei 'Title' die Anzahl der Tage (z.B. '7' oder '-7') ODER ein exaktes Datum im Format 'YYYY-MM-DD', wenn nach einem ganz bestimmten Tag gefragt wird.\n"
        "2. Bei 'delete' / 'edit': Verwende bei 'Title' ZWINGEND den echten Namen des Termins.\n"
        "3. Block-Format:\n"
        "[CALENDAR_EVENT]\n"
        "Action: add\n"
        "Title: Zahnarzt\n"
        "Start: 2026-03-21T14:30:00Z\n"
        "[/CALENDAR_EVENT]\n\n"
        "NOTIZBLOCK-FUNKTIONEN:\n"
        "Du kannst Notizen hinzufügen (add), löschen (delete) oder auflisten (list).\n"
        "1. Bei 'add': Gib den gewünschten Text im Feld 'Content' an.\n"
        "2. Bei 'delete': Gib die ID der zu löschenden Notiz im Feld 'Id' an (siehe NOTIZBLOCK-GEDÄCHTNIS oben), ODER den ungefähren Text im Feld 'Content'.\n"
        "3. Bei 'list': Zeigt alle Notizen an.\n"
        "4. Block-Format:\n"
        "[NOTE_EVENT]\n"
        "Action: add\n"
        "Content: Milch und Äpfel kaufen\n"
        "[/NOTE_EVENT]\n\n"
        "Beispiel für 'delete' einer Notiz:\n"
        "[NOTE_EVENT]\n"
        "Action: delete\n"
        "Id: 5\n"
        "[/NOTE_EVENT]"
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
            resp = await http_client.post(url, headers=headers, json=payload, timeout=45)
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


async def transcribe_audio(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """
    Transkribiert ogg/opus oder webm Audiodaten in Text.
    Primär: Lokale Offline-Transkription mit faster-whisper (kein API-Key nötig).
    Fallback: OpenAI Whisper API, dann Google Gemini.
    """
    import io
    import tempfile

    # ──────────────────────────────────────────────────────────
    # 1. PRIMÄR: Lokale Offline-Transkription mit faster-whisper
    # ──────────────────────────────────────────────────────────
    try:
        # Stelle sicher, dass ffmpeg im PATH ist (via imageio-ffmpeg Bundle)
        import imageio_ffmpeg
        ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        from faster_whisper import WhisperModel

        print(f"🎙️ Lokale Transkription mit faster-whisper ({filename})...")

        # Audio-Bytes in eine temporäre Datei schreiben
        ext = os.path.splitext(filename)[1] or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # Modell laden (beim ersten Aufruf wird es heruntergeladen, ~75MB für "base")
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, info = model.transcribe(tmp_path, language="de")
            transcript = " ".join(seg.text.strip() for seg in segments).strip()

            if transcript:
                print(f"✅ Lokale Transkription erfolgreich: {transcript}")
                return transcript
            else:
                print("⚠️ Lokale Transkription lieferte leeres Ergebnis.")
        finally:
            # Temporäre Datei aufräumen
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except ImportError as e:
        print(f"⚠️ faster-whisper nicht installiert, überspringe lokale Transkription: {e}")
    except Exception as e:
        print(f"⚠️ Lokale Transkription fehlgeschlagen: {e}")

    # ──────────────────────────────────────────────────────────
    # 2. FALLBACK: OpenAI Whisper API (falls konfiguriert)
    # ──────────────────────────────────────────────────────────
    if client_openai:
        try:
            print(f"🎙️ Transkribiere mit OpenAI Whisper ({filename})...")
            buffer = io.BytesIO(audio_bytes)
            buffer.name = filename
            resp = await client_openai.audio.transcriptions.create(
                model="whisper-1",
                file=buffer,
            )
            transcript = resp.text.strip()
            if transcript:
                print(f"✅ Whisper Transkription erfolgreich: {transcript}")
                return transcript
        except Exception as e:
            print(f"⚠️ OpenAI Whisper Fehler: {e}")

    # ──────────────────────────────────────────────────────────
    # 3. FALLBACK: Google Gemini (falls konfiguriert)
    # ──────────────────────────────────────────────────────────
    if client_gemini:
        try:
            print("🎙️ Transkribiere mit Google Gemini...")
            prompt = "Transkribiere das Audio. Gib AUSSCHLIESSLICH das Transkript zurück, ohne Kommentare oder Zusätze."

            mime_type = "audio/webm" if filename.endswith(".webm") else "audio/ogg"
            resp = await asyncio.to_thread(
                client_gemini.models.generate_content,
                model=MODEL_GEMINI,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    prompt
                ]
            )
            transcript = resp.text.strip()
            if transcript:
                print(f"✅ Gemini Transkription erfolgreich: {transcript}")
                return transcript
        except Exception as e:
            print(f"⚠️ Gemini Transkription Fehler: {e}")

    print("❌ Keine Transkriptions-Engine konnte das Audio verarbeiten.")
    return ""


