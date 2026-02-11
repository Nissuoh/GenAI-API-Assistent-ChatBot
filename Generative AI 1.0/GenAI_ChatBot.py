from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import uvicorn

app = FastAPI()

# CORS-Konfiguration: Erlaubt dem Browser den Zugriff auf die API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI()


@app.post("/chat")
async def chat(message: str):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": message}]
    )
    return {"response": response.choices[0].message.content}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
