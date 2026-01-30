from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()

app = FastAPI()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "PSk5GhCjavRcRMo6NtjK"

AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

class AudioRequest(BaseModel):
    sentence: str


@app.get("/")
def root():
    return {"status": "ok", "message": "TTS API running"}


@app.post("/cementary")
def generate_audio(payload: AudioRequest):
    if not payload.sentence:
        raise HTTPException(status_code=400, detail="sentence is required")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }

    data = {
        "text": payload.sentence,
        "model_id": "eleven_multilingual_v2"
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="ElevenLabs failed")

    # 🔹 Save file
    filename = f"{uuid4()}.mp3"
    file_path = os.path.join(AUDIO_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(response.content)

    return {
        "message": "Audio generated successfully",
        "file": filename,
        "download_url": f"/audio/{filename}"
    }
@app.get("/audio/{filename}")
def get_audio(filename: str):
    file_path = os.path.join(AUDIO_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename
    )
