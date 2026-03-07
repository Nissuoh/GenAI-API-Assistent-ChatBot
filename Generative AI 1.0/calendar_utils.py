import re
import google_calendar


def process_calendar_event(text: str) -> str:
    print("🔍 Prüfe KI-Antwort auf Kalender-Aktionen...")
    pattern = r"\[CALENDAR_EVENT\](.*?)\[/CALENDAR_EVENT\]"
    matches = re.findall(pattern, text, re.DOTALL)

    if not matches:
        return ""

    results = []
    for match in matches:
        try:
            data = {}
            for line in match.strip().split("\n"):
                line = line.strip()
                if not line or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                data[k.strip().lower()] = v.strip()

            title = data.get("title", "")
            start = data.get("start", "")
            action = data.get("action", "").lower()

            if not action and not title and not start:
                continue

            if not action:
                action = "add"

            if action == "list":
                title_clean = title.strip()
                # Prüfen, ob ein exaktes Datum im Format YYYY-MM-DD übergeben wurde
                if re.match(r"^\d{4}-\d{2}-\d{2}$", title_clean):
                    res = google_calendar.get_events(specific_date=title_clean)
                else:
                    days = 7
                    try:
                        days = int(title_clean)
                    except ValueError:
                        pass
                    res = google_calendar.get_events(days=days)

                results.append(f"🔎 {res}")
                continue

            if action == "add" and (not title or not start):
                results.append("⚠️ Fehler: Für 'add' fehlen Titel oder Startzeit.")
                continue

            if action in ["delete", "edit"] and not title:
                results.append(
                    "⚠️ Fehler: Für 'delete/edit' fehlt das Suchwort im Titel."
                )
                continue

            if action == "delete":
                res = google_calendar.delete_event(summary=title, date_str=start)
                results.append(f"🗑️ {res}")
            elif action == "edit":
                new_title = data.get("new_title", title)
                new_start = data.get("new_start", start)
                res = google_calendar.edit_event(
                    old_summary=title,
                    old_date_str=start,
                    new_summary=new_title,
                    new_start_time=new_start,
                )
                results.append(f"✏️ {res}")
            else:
                desc = data.get("description", "Von Lumina automatisch erstellt.")
                res = google_calendar.add_event(
                    summary=title, start_time=start, description=desc
                )
                results.append(f"✅ {res}")

        except Exception as e:
            results.append(f"⚠️ Interner Fehler: {e}")

    return "\n".join(results)
