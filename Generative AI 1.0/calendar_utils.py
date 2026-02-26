import re
import google_calendar


def process_calendar_event(text: str) -> None:
    """
    Sucht nach [CALENDAR_EVENT], extrahiert Daten und führt Add/Delete/Edit aus.
    Ignoriert leere Zeilen und formatiert die Schlüssel-Wert-Paare sicher.
    """
    print("🔍 Prüfe KI-Antwort auf Kalender-Aktionen...")
    pattern = r"\[CALENDAR_EVENT\](.*?)\[/CALENDAR_EVENT\]"
    matches = re.findall(pattern, text, re.DOTALL)

    if not matches:
        print("ℹ️ Kein [CALENDAR_EVENT] Tag in der Nachricht gefunden.")
        return

    for match in matches:
        try:
            data = {}
            # Robustes Parsing: Ignoriert leere Zeilen und filtert saubere Key-Value-Paare
            for line in match.strip().split("\n"):
                line = line.strip()
                if not line or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                data[k.strip().lower()] = v.strip()

            title = data.get("title")
            start = data.get("start")
            action = data.get("action", "add").lower()

            if not title or not start:
                print("⚠️ Fehler: 'Title' oder 'Start' fehlt im Block.")
                continue

            print(f"📅 Aktion: {action.upper()} | Termin: {title} | Zeit: {start}")

            # Aktions-Routing
            if action == "delete":
                result = google_calendar.delete_event(summary=title, date_str=start)
                print(f"✅ Google API (Delete): {result}")

            elif action == "edit":
                new_title = data.get("new_title", title)
                new_start = data.get("new_start", start)
                result = google_calendar.edit_event(
                    old_summary=title,
                    old_date_str=start,
                    new_summary=new_title,
                    new_start_time=new_start,
                )
                print(f"✅ Google API (Edit): {result}")

            else:  # Standard ist 'add'
                desc = data.get("description", "Von Lumina automatisch erstellt.")
                result = google_calendar.add_event(
                    summary=title, start_time=start, description=desc
                )
                print(f"✅ Google API (Add): {result}")

        except Exception as e:
            print(f"⚠️ Kalender-Fehler in process_calendar_event: {e}")
