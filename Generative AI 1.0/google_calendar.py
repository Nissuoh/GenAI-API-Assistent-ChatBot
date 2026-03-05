import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                print("❌ FEHLER: 'credentials.json' nicht gefunden!")
                return None
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def add_event(
    summary: str,
    start_time: str,
    end_time: str = None,
    description: str = "",
    location: str = "",
) -> str:
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Kalender-Service verfügbar."

    start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    if not end_time:
        end_dt = start_dt + datetime.timedelta(hours=1)
    else:
        end_dt = datetime.datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Berlin"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Berlin"},
    }

    try:
        event_result = (
            service.events().insert(calendarId="primary", body=event).execute()
        )
        return f"Erfolgreich hinzugefügt (Link: {event_result.get('htmlLink')})"
    except Exception as e:
        return f"Fehler beim Erstellen: {e}"


def get_upcoming_events(days: int = 7) -> str:
    """Ruft die Termine der nächsten X Tage ab."""
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Kalender-Service verfügbar."

    try:
        now = datetime.datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + datetime.timedelta(days=days)).isoformat() + "Z"

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        if not events:
            return f"Keine Termine in den nächsten {days} Tag(en) gefunden."

        lines = [f"📅 **Termine der nächsten {days} Tag(e):**"]
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            date_part = start[:10]
            time_part = start[11:16] if "T" in start else "(Ganzjährig)"
            lines.append(
                f"• {date_part} {time_part}: {event.get('summary', 'Ohne Titel')}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Fehler beim Abrufen der Termine: {e}"


def find_event_ids(summary: str, date_str: str = "") -> list:
    service = get_calendar_service()
    if not service:
        return []

    try:
        if date_str:
            day_prefix = date_str[:10]
            time_min = day_prefix + "T00:00:00Z"
            time_max = day_prefix + "T23:59:59Z"
        else:
            now = datetime.datetime.utcnow()
            time_min = now.isoformat() + "Z"
            time_max = (now + datetime.timedelta(days=30)).isoformat() + "Z"

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        found_ids = [
            event["id"]
            for event in events
            if summary.lower() in event.get("summary", "").lower()
        ]
        return found_ids
    except Exception as e:
        return []


def delete_event(summary: str, date_str: str = "") -> str:
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Kalender-Service verfügbar."

    event_ids = find_event_ids(summary, date_str)
    if not event_ids:
        return f"Fehler: Kein Termin mit dem Stichwort '{summary}' gefunden."

    deleted_count = 0
    for event_id in event_ids:
        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            deleted_count += 1
        except Exception:
            pass

    return f"Erfolgreich gelöscht: {deleted_count} Termin(e) entfernt."


def edit_event(
    old_summary: str,
    old_date_str: str = "",
    new_summary: str = None,
    new_start_time: str = None,
) -> str:
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Kalender-Service verfügbar."

    event_ids = find_event_ids(old_summary, old_date_str)
    if not event_ids:
        return f"Fehler: Kein Termin mit dem Stichwort '{old_summary}' gefunden."

    event_id = event_ids[0]
    try:
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        if new_summary and new_summary.strip() and new_summary != old_summary:
            event["summary"] = new_summary

        if new_start_time and new_start_time.strip() and new_start_time != old_date_str:
            start_dt = datetime.datetime.fromisoformat(
                new_start_time.replace("Z", "+00:00")
            )
            end_dt = start_dt + datetime.timedelta(hours=1)
            event["start"] = {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Europe/Berlin",
            }
            event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Berlin"}

        updated_event = (
            service.events()
            .update(calendarId="primary", eventId=event_id, body=event)
            .execute()
        )
        return f"Termin aktualisiert (Neuer Link: {updated_event.get('htmlLink')})"
    except Exception as e:
        return f"Fehler bei der Aktualisierung: {e}"


if __name__ == "__main__":
    svc = get_calendar_service()
    if svc:
        print("🌟 ERFOLG: Google Kalender verbunden!")
