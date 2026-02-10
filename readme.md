# 🤖 Personal GPT Telegram Assistant

Ein intelligenter, privater Assistent für **Telegram**, der mithilfe von **OpenAI (GPT-4o)** den Alltag organisiert, Termine aus Bildern extrahiert und ein Langzeitgedächtnis besitzt.

---

## 🌟 Kern-Features

* **📅 Google Calendar Integration**: Termine per natürlicher Sprache erstellen, verschieben oder abfragen.
* **📸 Vision-Extraktion**: Fotos von Briefen oder Einladungen senden – die KI erkennt automatisch Datum, Uhrzeit sowie Details und schlägt Kalendereinträge vor.
* **🧠 Langzeitgedächtnis**: Dank einer **SQLite-Datenbank** vergisst der Bot keine persönlichen Vorlieben oder Aufgaben.
* **🔒 Security First**: Strenges User-Whitelisting (reagiert nur auf die eigene Telegram-ID).
* **✅ Robuste Validierung**: Prüfung aller KI-Daten vor der Verarbeitung, um Logikfehler im Kalender zu vermeiden.

---

## 🛠 Technologie-Stack

| Komponente | Technologie |
| :--- | :--- |
| **Sprache** | Python 3.10+ |
| **KI-Modell** | OpenAI (Vision & Chat) |
| **Messenger** | `python-telegram-bot` |
| **Kalender** | Google Calendar API |
| **Datenbank** | SQLite |