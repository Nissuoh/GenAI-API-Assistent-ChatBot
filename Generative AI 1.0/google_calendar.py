import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Schreibzugriff auf den Kalender
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_calendar_service():
    """Initialisiert und autorisiert die Google Calendar API."""
    creds = None
    print("🔍 Suche nach token.json...")

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        print("✅ Vorhandener Token gefunden.")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Token abgelaufen, erneuere...")
            creds.refresh(Request())
        else:
            print("🔑 Starte neuen Login-Vorgang...")
            if not os.path.exists("credentials.json"):
                print(
                    "❌ FEHLER: Die Datei 'credentials.json' wurde nicht im Ordner gefunden!"
                )
                return None

            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("💾 Neuer Zugriffstoken wurde als 'token.json' gespeichert.")

    return build("calendar", "v3", credentials=creds)


def add_event(
    summary: str,
    start_time: str,
    end_time: str = None,
    description: str = "",
    location: str = "",
) -> str:
    """Fügt einen neuen Termin zum Kalender hinzu."""
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
        print(f"✅ Termin erstellt: {event_result.get('htmlLink')}")
        return f"Erfolgreich hinzugefügt (Link: {event_result.get('htmlLink')})"
    except Exception as e:
        return f"Fehler beim Erstellen des Termins: {e}"


def find_event_ids(summary: str, date_str: str = "") -> list:
    """
    Sucht Termine basierend auf dem Titel.
    Wenn date_str leer ist, werden die nächsten 30 Tage durchsucht.
    Gibt eine Liste aller passenden Event-IDs zurück.
    """
    service = get_calendar_service()
    if not service:
        return []

    try:
        if date_str:
            # Suchen an einem spezifischen Tag
            day_prefix = date_str[:10]
            time_min = day_prefix + "T00:00:00Z"
            time_max = day_prefix + "T23:59:59Z"
        else:
            # Suchen in den nächsten 30 Tagen (ab jetzt)
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
        found_ids = []

        for event in events:
            event_summary = event.get("summary", "").lower()
            if summary.lower() in event_summary:
                found_ids.append(event["id"])

        return found_ids
    except Exception as e:
        print(f"⚠️ Fehler bei der Terminsuche: {e}")
        return []


def delete_event(summary: str, date_str: str = "") -> str:
    """Löscht ALLE gefundenen Termine, die das Suchwort enthalten."""
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
        except Exception as e:
            print(f"⚠️ Fehler beim Löschen der ID {event_id}: {e}")

    return f"Erfolgreich gelöscht: {deleted_count} Termin(e) mit '{summary}' entfernt."


def edit_event(
    old_summary: str,
    old_date_str: str = "",
    new_summary: str = None,
    new_start_time: str = None,
) -> str:
    """Bearbeitet den ERSTEN gefundenen Termin (Titel und/oder Zeit)."""
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Kalender-Service verfügbar."

    event_ids = find_event_ids(old_summary, old_date_str)

    if not event_ids:
        return f"Fehler: Kein Termin mit dem Stichwort '{old_summary}' zum Bearbeiten gefunden."

    # Wir bearbeiten nur den ersten Treffer, um Chaos zu vermeiden
    event_id = event_ids[0]

    try:
        # Aktuellen Termin abrufen
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        # Titel aktualisieren
        if new_summary and new_summary.strip() and new_summary != old_summary:
            event["summary"] = new_summary

        # Zeit aktualisieren
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
        return f"Termin erfolgreich aktualisiert (Neuer Link: {updated_event.get('htmlLink')})"
    except Exception as e:
        return f"Fehler bei der Aktualisierung: {e}"


# --- INITIALISIERUNG / TEST ---
if __name__ == "__main__":
    print("🚀 Initialisiere Google Calendar Verbindung...")
    try:
        svc = get_calendar_service()
        if svc:
            print("🌟 ERFOLG: Du bist erfolgreich mit Google Kalender verbunden!")
            print(
                "Du kannst dieses Fenster nun schließen und mit der main.py weitermachen."
            )
    except Exception as err:
        print(f"💥 Fehler beim Starten: {err}")
