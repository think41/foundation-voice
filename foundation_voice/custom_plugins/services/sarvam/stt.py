"""
Sarvam AI Speech-to-Text (Saarika) service.

Real-time transcription via Sarvam AI's WebSocket streaming API.
Supports 12 Indian languages including Hindi, Tamil, Bengali, Telugu, and more.

WebSocket endpoint: wss://api.sarvam.ai/speech-to-text/ws
Authentication: api-subscription-key header
"""

import json
from typing import AsyncGenerator
from urllib.parse import urlencode

from loguru import logger

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InterimTranscriptionFrame,
    StartFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.stt_service import WebsocketSTTService
from pipecat.utils.time import time_now_iso8601
from pipecat.utils.tracing.service_decorators import traced_stt

try:
    from websockets.asyncio.client import connect as websocket_connect
    from websockets.protocol import State
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error("In order to use Sarvam STT, please install websockets: pip install websockets")
    raise Exception(f"Missing module: {e}")

SARVAM_STT_WS_URL = "wss://api.sarvam.ai/speech-to-text/ws"


class SarvamSTTService(WebsocketSTTService):
    """Sarvam AI real-time speech-to-text service (Saarika).

    Streams audio to Sarvam AI's WebSocket API and returns transcriptions
    for 12 Indian languages plus English (India variant).

    Supported models:
        - saarika:v2      - Standard STT
        - saarika:v2.5    - Enhanced STT (recommended)
        - saaras:v2.5     - STT with translation
        - saaras:v3       - Advanced with multiple modes
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "saarika:v2.5",
        language: str = "unknown",
        sample_rate: int = 16000,
        **kwargs,
    ):
        """Initialize the Sarvam STT service.

        Args:
            api_key: Sarvam AI API subscription key.
            model: Saarika model to use (default: saarika:v2.5).
            language: BCP-47 language code. Use 'unknown' for auto-detection
                      (saarika:v2+). Examples: hi-IN, ta-IN, en-IN, bn-IN.
            sample_rate: Audio sample rate in Hz (default: 16000).
        """
        super().__init__(sample_rate=sample_rate, **kwargs)

        self._api_key = api_key
        self._model = model
        self._language = language

        self._audio_buffer = bytearray()
        self._chunk_size_ms = 50
        self._chunk_size_bytes = 0

    def can_generate_metrics(self) -> bool:
        return True

    def _build_ws_url(self) -> str:
        params = {
            "api-subscription-key": self._api_key,
            "model": self._model,
            "sample_rate": self._sample_rate,
            "input_audio_codec": "pcm_s16le",
        }
        if self._language and self._language != "unknown":
            params["language_code"] = self._language
        return f"{SARVAM_STT_WS_URL}?{urlencode(params)}"

    async def start(self, frame: StartFrame):
        await super().start(frame)
        self._chunk_size_bytes = int(self._chunk_size_ms * self._sample_rate * 2 / 1000)
        await self._connect()

    async def stop(self, frame: EndFrame):
        await super().stop(frame)
        await self._disconnect()

    async def cancel(self, frame: CancelFrame):
        await super().cancel(frame)
        await self._disconnect()

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self._audio_buffer.extend(audio)

        if self._websocket and self._websocket.state is State.OPEN:
            while len(self._audio_buffer) >= self._chunk_size_bytes:
                chunk = bytes(self._audio_buffer[: self._chunk_size_bytes])
                self._audio_buffer = self._audio_buffer[self._chunk_size_bytes:]
                await self._websocket.send(chunk)

        yield None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, UserStartedSpeakingFrame):
            await self.start_ttfb_metrics()
        elif isinstance(frame, UserStoppedSpeakingFrame):
            if self._websocket and self._websocket.state is State.OPEN:
                # Send flush signal to finalize in-progress transcription
                try:
                    await self._websocket.send(json.dumps({"type": "flush"}))
                except Exception as e:
                    logger.warning(f"Failed to send flush signal: {e}")
            await self.start_processing_metrics()

    @traced_stt
    async def _trace_transcription(self, transcript: str, is_final: bool, language: str):
        pass

    async def _connect(self):
        await self._connect_websocket()
        self._receive_task = self.create_task(
            self._receive_task_handler(self._report_error)
        )

    async def _disconnect(self):
        if not self._websocket:
            return
        try:
            if self._websocket.state is State.OPEN:
                if self._audio_buffer:
                    await self._websocket.send(bytes(self._audio_buffer))
                    self._audio_buffer.clear()
        except Exception as e:
            logger.warning(f"Error flushing audio on disconnect: {e}")
        finally:
            await self._disconnect_websocket()

    async def _connect_websocket(self):
        try:
            if self._websocket and self._websocket.state is State.OPEN:
                return

            ws_url = self._build_ws_url()

            logger.debug(f"Connecting to Sarvam STT WebSocket")
            self._websocket = await websocket_connect(ws_url)
            await self._call_event_handler("on_connected")
            logger.debug("Connected to Sarvam STT WebSocket")
        except Exception as e:
            await self.push_error(
                error_msg=f"Unable to connect to Sarvam STT: {e}", exception=e
            )
            raise

    async def _disconnect_websocket(self):
        try:
            if self._websocket:
                logger.debug("Disconnecting from Sarvam STT WebSocket")
                await self._websocket.close()
        except Exception as e:
            logger.warning(f"Error closing Sarvam STT websocket: {e}")
        finally:
            self._websocket = None
            await self._call_event_handler("on_disconnected")

    async def _receive_messages(self):
        async for message in self._websocket:
            await self._handle_message(message)

    async def _handle_message(self, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "transcript":
                transcript = data.get("transcript", "")
                is_final = data.get("is_final", False)
                language = data.get("language_code", self._language)

                if transcript:
                    await self.stop_ttfb_metrics()
                    if is_final:
                        await self.stop_processing_metrics()
                        await self._trace_transcription(transcript, True, language)
                        await self.push_frame(
                            TranscriptionFrame(transcript, self._user_id, time_now_iso8601(), language)
                        )
                        logger.debug(f"Sarvam STT final: [{transcript}]")
                    else:
                        await self._trace_transcription(transcript, False, language)
                        await self.push_frame(
                            InterimTranscriptionFrame(transcript, self._user_id, time_now_iso8601(), language)
                        )
            elif msg_type == "speech_start":
                logger.debug("Sarvam STT: speech started")
            elif msg_type == "speech_end":
                logger.debug("Sarvam STT: speech ended")
            elif msg_type == "error":
                error_msg = data.get("message", "Unknown Sarvam STT error")
                logger.error(f"Sarvam STT error: {error_msg}")
                await self.push_error(error_msg=error_msg)

        except json.JSONDecodeError:
            logger.warning(f"Sarvam STT: received non-JSON message: {message}")
        except Exception as e:
            logger.exception(f"Sarvam STT: error handling message: {e}")
