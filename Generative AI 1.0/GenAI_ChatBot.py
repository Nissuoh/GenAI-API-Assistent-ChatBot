from fastapi import FastAPI
from openai import OpenAI


app = FastAPI()
client = OpenAI()


@app.post("/chat")
async def chat(message: str):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": message}]
    )
    return {"response": response.choices[0].message.content}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
