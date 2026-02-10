🤖 Personal GPT Telegram Assistant
Ein intelligenter, privater Assistent für Telegram, der mithilfe von OpenAI (GPT-4o) den Alltag organisiert, Termine aus Bildern extrahiert und ein Langzeitgedächtnis besitzt.

🌟 Features
📅 Google Calendar Integration: Termine per natürlicher Sprache erstellen, verschieben oder abfragen.

📸 Vision-Extraktion: Fotos von Briefen, Einladungen oder E-Mails senden – die KI erkennt automatisch Datum, Uhrzeit sowie Details und schlägt Kalendereinträge vor.

🧠 Langzeitgedächtnis: Dank einer SQLite-Datenbank vergisst der Bot keine persönlichen Vorlieben oder Aufgaben.

🔒 Security First: Strenges User-Whitelisting (reagiert nur auf die eigene Telegram-ID) und sichere API-Key-Verwaltung.

✅ Robuste Validierung: Prüfung aller KI-generierten Daten vor der Verarbeitung, um Logikfehler im Kalender zu vermeiden.

🛠 Technologie-Stack
Sprache: Python 3.10+

KI-Modelle: OpenAI GPT-4o (Vision & Chat)

Frameworks: python-telegram-bot, google-api-python-client

Datenbank: SQLite

Infrastruktur: Umgebungsvariablen (.env) für maximale Sicherheit