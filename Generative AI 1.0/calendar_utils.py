import re
import google_calendar


def process_calendar_event(text):
    """Sucht nach [CALENDAR_EVENT], extrahiert Daten und trägt sie autonom ein."""
    print("🔍 Prüfe KI-Antwort auf Termine...")
    # Wir suchen nach dem Muster [CALENDAR_EVENT] ... [/CALENDAR_EVENT]
    pattern = r"\[CALENDAR_EVENT\](.*?)\[/CALENDAR_EVENT\]"
    matches = re.findall(pattern, text, re.DOTALL)

    if not matches:
        print("ℹ️ Kein [CALENDAR_EVENT] Tag in der Nachricht gefunden.")
        return

    for match in matches:
        try:
            data = {}
            # Zeilenweise zerlegen und Schlüssel-Wert-Paare extrahieren
            for line in match.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip().lower()] = v.strip()

            if "title" in data and "start" in data:
                print(f"📅 Extrahiere Termin: {data['title']} für {data['start']}")

                # Aufruf deines Google-Moduls
                result = google_calendar.add_event(
                    summary=data["title"],
                    start_time=data["start"],
                    description=data.get(
                        "description", "Von Lumina automatisch erstellt."
                    ),
                )
                print(f"✅ Google API Erfolg: {result}")
        except Exception as e:
            print(f"⚠️ Kalender-Fehler in process_calendar_event: {e}")
