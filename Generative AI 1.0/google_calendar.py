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

    # Robuste Zeitberechnung (Standard: 60 Minuten, wenn kein end_time gegeben)
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


def find_event_id(summary: str, date_str: str) -> str:
    """Sucht einen Termin am angegebenen Tag basierend auf dem Titel."""
    service = get_calendar_service()
    if not service:
        return None

    try:
        # Suchzeitraum: Gesamter Tag des angegebenen Datums
        day_prefix = date_str[:10]
        start_of_day = day_prefix + "T00:00:00Z"
        end_of_day = day_prefix + "T23:59:59Z"

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        for event in events:
            # Fallback auf leeren String, falls Termin keinen Titel hat
            event_summary = event.get("summary", "").lower()
            if summary.lower() in event_summary:
                return event["id"]
        return None
    except Exception as e:
        print(f"⚠️ Fehler bei der Terminsuche: {e}")
        return None


def delete_event(summary: str, date_str: str) -> str:
    """Löscht einen Termin basierend auf Titel und Startzeit."""
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Kalender-Service verfügbar."

    event_id = find_event_id(summary, date_str)

    if event_id:
        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            return f"Termin '{summary}' erfolgreich gelöscht."
        except Exception as e:
            return f"Fehler beim Löschen: {e}"
    return "Fehler: Termin zum Löschen nicht gefunden."


def edit_event(
    old_summary: str,
    old_date_str: str,
    new_summary: str = None,
    new_start_time: str = None,
) -> str:
    """Bearbeitet einen bestehenden Termin (Titel und/oder Zeit)."""
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Kalender-Service verfügbar."

    event_id = find_event_id(old_summary, old_date_str)

    if not event_id:
        return "Fehler: Termin zum Bearbeiten nicht gefunden."

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
