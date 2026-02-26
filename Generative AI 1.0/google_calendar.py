import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Schreibzugriff auf den Kalender
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_calendar_service():
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
            # Port 8080 oder 0 probieren. open_browser=True sollte auf dem NUC klappen.
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("💾 Neuer Zugriffstoken wurde als 'token.json' gespeichert.")

    return build("calendar", "v3", credentials=creds)


def add_event(summary, start_time, end_time=None, description="", location=""):
    service = get_calendar_service()
    if not service:
        return

    if not end_time:
        start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", ""))
        end_dt = start_dt + datetime.timedelta(hours=1)
        end_time = end_dt.isoformat() + "Z"

    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start_time, "timeZone": "Europe/Berlin"},
        "end": {"dateTime": end_time, "timeZone": "Europe/Berlin"},
    }

    event = service.events().insert(calendarId="primary", body=event).execute()
    print(f"✅ Termin erstellt: {event.get('htmlLink')}")
    return event.get("htmlLink")


# --- DIESER TEIL FEHLTE: DER AUTOMATISCHE START ---
if __name__ == "__main__":
    print("🚀 Initialisiere Google Calendar Verbindung...")
    try:
        service = get_calendar_service()
        if service:
            print("🌟 ERFOLG: Du bist erfolgreich mit Google Kalender verbunden!")
            print(
                "Du kannst dieses Fenster nun schließen und mit der main.py weitermachen."
            )
    except Exception as e:
        print(f"💥 Fehler beim Starten: {e}")
