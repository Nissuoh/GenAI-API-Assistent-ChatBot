import os.path
import datetime
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")


def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                if os.path.exists("token.json"):
                    os.remove("token.json")
                creds = None

        if not creds:
            if not os.path.exists("credentials.json"):
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
        return "Fehler: Kein Kalender-Service."

    start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end_dt = (
        start_dt + datetime.timedelta(hours=1)
        if not end_time
        else datetime.datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    )

    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
    }
    try:
        res = service.events().insert(calendarId="primary", body=event).execute()
        return f"Erfolgreich hinzugefügt (Link: {res.get('htmlLink')})"
    except Exception as e:
        return f"Fehler: {e}"


def get_events(days: int = 7, specific_date: str = None) -> str:
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Service."
    try:
        now = datetime.datetime.utcnow()
        if specific_date:
            target_date = datetime.datetime.strptime(specific_date, "%Y-%m-%d")
            time_min = target_date.isoformat() + "Z"
            time_max = (target_date + datetime.timedelta(days=1)).isoformat() + "Z"
            label = f"am {specific_date}"
        else:
            time_min = (
                now.isoformat() + "Z"
                if days >= 0
                else (now + datetime.timedelta(days=days)).isoformat() + "Z"
            )
            time_max = (
                (now + datetime.timedelta(days=days)).isoformat() + "Z"
                if days >= 0
                else now.isoformat() + "Z"
            )
            label = (
                f"nächsten {days} Tage" if days >= 0 else f"letzten {abs(days)} Tage"
            )

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
            return f"Keine Termine {label} gefunden."

        lines = [f"📅 **Termine {label}:**"]
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            lines.append(
                f"• {start[:10]} {start[11:16] if 'T' in start else ''}: {event.get('summary', 'Ohne Titel')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Fehler: {e}"


def get_events_json(year: int = None, month: int = None) -> list:
    service = get_calendar_service()
    if not service:
        return []
    try:
        now = datetime.datetime.utcnow()
        y = year or now.year
        m = month or now.month

        start_date = datetime.datetime(y, m, 1)
        end_date = (
            datetime.datetime(y + 1, 1, 1)
            if m == 12
            else datetime.datetime(y, m + 1, 1)
        )

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_date.isoformat() + "Z",
                timeMax=end_date.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        result = []
        for event in events_result.get("items", []):
            start = event["start"].get("dateTime", event["start"].get("date"))
            result.append(
                {"summary": event.get("summary", "Ohne Titel"), "start": start}
            )
        return result
    except Exception:
        return []


def find_event_ids(summary: str, date_str: str = "") -> list:
    service = get_calendar_service()
    if not service:
        return []
    try:
        if date_str:
            day_prefix = date_str[:10]
            target_date = datetime.datetime.strptime(day_prefix, "%Y-%m-%d")
            time_min = (target_date - datetime.timedelta(days=1)).isoformat() + "Z"
            time_max = (target_date + datetime.timedelta(days=2)).isoformat() + "Z"
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
        search_term = re.sub(r"[^a-zA-Z0-9]", "", summary.lower())

        return [
            e["id"]
            for e in events_result.get("items", [])
            if search_term in re.sub(r"[^a-zA-Z0-9]", "", e.get("summary", "").lower())
        ]
    except Exception:
        return []


def delete_event(summary: str, date_str: str = "") -> str:
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Service."
    event_ids = find_event_ids(summary, date_str)
    if not event_ids:
        return f"Fehler: Termin '{summary}' nicht gefunden."

    count = 0
    for e_id in event_ids:
        try:
            service.events().delete(calendarId="primary", eventId=e_id).execute()
            count += 1
        except Exception:
            pass
    return f"Erfolgreich gelöscht: {count} Termin(e)."


def edit_event(
    old_summary: str,
    old_date_str: str = "",
    new_summary: str = None,
    new_start_time: str = None,
) -> str:
    service = get_calendar_service()
    if not service:
        return "Fehler: Kein Service."
    event_ids = find_event_ids(old_summary, old_date_str)
    if not event_ids:
        return f"Fehler: Termin '{old_summary}' nicht gefunden."

    try:
        event = (
            service.events().get(calendarId="primary", eventId=event_ids[0]).execute()
        )
        if new_summary:
            event["summary"] = new_summary
        if new_start_time:
            start_dt = datetime.datetime.fromisoformat(
                new_start_time.replace("Z", "+00:00")
            )
            event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE}
            event["end"] = {
                "dateTime": (start_dt + datetime.timedelta(hours=1)).isoformat(),
                "timeZone": TIMEZONE,
            }

        res = (
            service.events()
            .update(calendarId="primary", eventId=event_ids[0], body=event)
            .execute()
        )
        return f"Aktualisiert (Link: {res.get('htmlLink')})"
    except Exception as e:
        return f"Fehler: {e}"
