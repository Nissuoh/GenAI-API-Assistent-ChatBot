import os
import requests
from openai import OpenAI
from google import genai
from database import get_all_info, get_chat_history

# Keys laden
O_KEY = os.getenv("OPENAI_API_KEY")
G_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")
model_or = "arcee-ai/trinity-large-preview:free"

client_openai = OpenAI(api_key=O_KEY) if O_KEY else None
client_gemini = genai.Client(api_key=G_KEY) if G_KEY else None


def fetch_llm_response(message: str):
    memories = get_all_info()
    history = get_chat_history(limit=10)

    memory_context = "Fakten über den Nutzer:\n" + "\n".join(
        [f"- {k}: {v}" for k, v in memories]
    )
    system_instruction = {
        "role": "system",
        "content": f"Du bist ein hilfreicher Assistent. {memory_context}",
    }
    full_messages = (
        [system_instruction] + history + [{"role": "user", "content": message}]
    )

    # 1. Trinity (OpenRouter)
    if OR_KEY:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OR_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_or,
                "messages": full_messages,
                "reasoning": {"enabled": True},
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "source": "Trinity",
            }
        except Exception as e:
            print(f"❌ Trinity Fehler: {e}")

    # 2. OpenAI Fallback
    if client_openai:
        try:
            resp = client_openai.chat.completions.create(
                model="gpt-4o", messages=full_messages
            )
            return {"content": resp.choices[0].message.content, "source": "OpenAI"}
        except Exception as e:
            print(f"❌ OpenAI Fehler: {e}")

    return {"content": "Fehler: Kein Provider erreichbar.", "source": "Error"}
