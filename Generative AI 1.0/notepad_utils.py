import re
import database


async def process_notepad_event(text: str) -> str:
    print("🔍 Prüfe KI-Antwort auf Notizblock-Aktionen...")
    pattern = r"\[NOTE_EVENT\](.*?)\[/NOTE_EVENT\]"
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

            action = data.get("action", "add").lower()
            content = data.get("content", "")
            note_id_str = data.get("id", "")

            if action == "add":
                if not content:
                    results.append("⚠️ Fehler: Für 'add' fehlt der Inhalt der Notiz.")
                    continue
                note_id = await database.add_note(content)
                if note_id != -1:
                    results.append(f"📝 Notiz '{content}' erfolgreich hinzugefügt (ID: {note_id}).")
                else:
                    results.append("⚠️ Fehler beim Hinzufügen der Notiz.")

            elif action == "delete":
                if not note_id_str and not content:
                    results.append("⚠️ Fehler: Zum Löschen wird eine ID oder der Inhalt benötigt.")
                    continue

                success = False
                if note_id_str:
                    try:
                        note_id = int(note_id_str)
                        success = await database.delete_note(note_id)
                        if success:
                            results.append(f"🗑️ Notiz mit ID {note_id} gelöscht.")
                    except ValueError:
                        results.append(f"⚠️ Ungültige Notiz-ID: {note_id_str}")
                        continue

                if not success and content:
                    # Alternativ nach Inhalt löschen
                    notes = await database.get_all_notes()
                    for n in notes:
                        if content.lower() in n["content"].lower():
                            success = await database.delete_note(n["id"])
                            if success:
                                results.append(f"🗑️ Notiz '{n['content']}' (ID: {n['id']}) gelöscht.")
                                break
                    if not success:
                        results.append(f"⚠️ Keine passende Notiz mit Inhalt '{content}' gefunden.")
                elif not success:
                    results.append(f"⚠️ Notiz mit ID {note_id_str} nicht gefunden.")

            elif action == "list":
                notes = await database.get_all_notes()
                if not notes:
                    results.append("📋 Der Notizblock ist leer.")
                else:
                    items = [f"- [{n['id']}] {n['content']}" for n in notes]
                    results.append("📋 Aktuelle Notizen:\n" + "\n".join(items))

            else:
                results.append(f"⚠️ Unbekannte Aktion: {action}")

        except Exception as e:
            results.append(f"⚠️ Interner Fehler beim Notizblock: {e}")

    return "\n".join(results)
