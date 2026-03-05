# 🤖 Lumina – Personal GenAI Assistant

Ein privater, multimodaler KI-Assistent, der über **Telegram** und ein lokales **Webinterface** erreichbar ist. Lumina organisiert den Alltag, verwaltet den Google Kalender autonom, extrahiert Termine aus Bildern sowie PDFs und besitzt ein Langzeitgedächtnis.

---

## 🌟 Kern-Features

* 📱 **Dual-Interface**: Synchronisierte Nutzung über einen privaten Telegram-Bot und ein lokales Web-Frontend (FastAPI).
* 📅 **Google Calendar Integration**: Termine per natürlicher Sprache abfragen (List), erstellen (Add), verschieben (Edit) oder löschen (Delete).
* 📄 **Multimodale Extraktion**: Bilder (Vision) oder PDFs (PyMuPDF) hochladen – die KI erkennt automatisch Daten, Uhrzeiten und Details und steuert den Kalender.
* 🧠 **Langzeitgedächtnis**: Eine lokale SQLite-Datenbank merkt sich persönliche Vorlieben, Fakten und den Chatverlauf.
* 🔄 **KI-Fallback-Kaskade**: Höchste Ausfallsicherheit durch automatisches Routing (OpenAI ➔ Google Gemini ➔ OpenRouter).
* 🔒 **Security First**: Strenges User-Whitelisting (reagiert ausschließlich auf die eigene Telegram-ID).

---

## 🛠 Technologie-Stack

| Komponente | Technologie |
| :--- | :--- |
| **Backend / Web** | Python 3.10+, FastAPI, Uvicorn |
| **Messenger** | `python-telegram-bot` |
| **KI-Modelle** | OpenAI, Google Gemini, OpenRouter |
| **Kalender** | Google Calendar API |
| **Dokumenten-Analyse**| PyMuPDF (`fitz`) |
| **Datenbank** | SQLite |
| **Frontend** | HTML, CSS, Vanilla JS |

---

## ⚙️ Installation & Setup

**1. Repository klonen & Abhängigkeiten installieren**
```bash
git clone [https://github.com/Nissuoh/GenAI-API-Assistent-ChatBot.git](https://github.com/Nissuoh/GenAI-API-Assistent-ChatBot.git)
cd GenAI-API-Assistent-ChatBot
pip install -r requirements.txt
pip install PyMuPDF