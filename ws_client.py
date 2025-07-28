import asyncio
import websockets
import pyaudio
import json
import uuid
import numpy as np
import soundfile as sf
from io import BytesIO

WS_URL = "ws://localhost:8000/ws" # Your FastAPI WebSocket endpoint

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
SESSION_ID = str(uuid.uuid4())

# Start PyAudio
p = pyaudio.PyAudio()

# Audio stream for microphone
mic_stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

# Audio stream for playback
play_stream = p.open(format=FORMAT,
                     channels=CHANNELS,
                     rate=RATE,
                     output=True)

async def send_audio(ws):
    print("🔴 Sending audio from mic...")
    try:
        while True:
            data = mic_stream.read(CHUNK)
            await ws.send(data)
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket closed while sending.")

async def receive(ws):
    print("🟢 Listening to bot...")
    try:
        while True:
            message = await ws.recv()

            if isinstance(message, bytes):
                # Binary: Bot audio
                print("🔊 Bot is speaking...")
                play_stream.write(message)
            else:
                # Text: JSON transcripts
                msg = json.loads(message)
                if "transcript" in msg:
                    print(f"🧑 You: {msg['transcript']}")
                if "response" in msg:
                    print(f"🤖 Bot: {msg['response']}")

    except websockets.exceptions.ConnectionClosed:
        print("WebSocket closed while receiving.")

async def main():
    async with websockets.connect(f"{WS_URL}?session_id={SESSION_ID}") as ws:
        print(f"Connected to {WS_URL} as session {SESSION_ID}")
        await asyncio.gather(send_audio(ws), receive(ws))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🔴 Session ended by user")
    finally:
        mic_stream.stop_stream()
        mic_stream.close()
        play_stream.stop_stream()
        play_stream.close()
        p.terminate()
