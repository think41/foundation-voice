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
    raise Exception(f"Missing module: {e}")


SARVAM_STT_WS_URL = "wss://api.sarvam.ai/speech-to-text/ws"


class SarvamSTTService(WebsocketSTTService):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "saarika:v2.5",
        language: str = "unknown",
        sample_rate: int = 16000,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)

        self._api_key = api_key
        self._model = model
        self._language = language

        self._audio_buffer = bytearray()

        # Reduced from 50ms → 20ms for lower latency
        self._chunk_size_ms = 20
        self._chunk_size_bytes = 0

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
                self._audio_buffer = self._audio_buffer[self._chunk_size_bytes :]
                await self._websocket.send(chunk)

        yield None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, UserStartedSpeakingFrame):
            await self.start_ttfb_metrics()

        elif isinstance(frame, UserStoppedSpeakingFrame):
            await self._flush_audio_and_finalize()

    async def _flush_audio_and_finalize(self):
        """
        Immediately flush remaining audio before sending finalization signal.
        This removes 100–300ms hidden buffering delay.
        """
        if not self._websocket or self._websocket.state is not State.OPEN:
            return

        try:
            # 🔥 Flush leftover audio first
            if self._audio_buffer:
                await self._websocket.send(bytes(self._audio_buffer))
                self._audio_buffer.clear()

            # Then send flush signal
            await self._websocket.send(json.dumps({"type": "flush"}))

        except Exception as e:
            logger.warning(f"Flush failed: {e}")

    @traced_stt
    async def _trace_transcription(
        self, transcript: str, is_final: bool, language: str
    ):
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
            if self._websocket.state is State.OPEN and self._audio_buffer:
                await self._websocket.send(bytes(self._audio_buffer))
                self._audio_buffer.clear()
        finally:
            await self._disconnect_websocket()

    async def _connect_websocket(self):
        if self._websocket and self._websocket.state is State.OPEN:
            return

        ws_url = self._build_ws_url()
        self._websocket = await websocket_connect(ws_url)
        await self._call_event_handler("on_connected")

    async def _disconnect_websocket(self):
        try:
            if self._websocket:
                await self._websocket.close()
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

                if not transcript:
                    return

                await self.stop_ttfb_metrics()

                if is_final:
                    await self.stop_processing_metrics()
                    await self._trace_transcription(transcript, True, language)
                    await self.push_frame(
                        TranscriptionFrame(
                            transcript,
                            self._user_id,
                            time_now_iso8601(),
                            language,
                        )
                    )
                else:
                    await self._trace_transcription(transcript, False, language)
                    await self.push_frame(
                        InterimTranscriptionFrame(
                            transcript,
                            self._user_id,
                            time_now_iso8601(),
                            language,
                        )
                    )

            elif msg_type == "speech_end":
                # React immediately when Sarvam detects speech end
                await self._flush_audio_and_finalize()

            elif msg_type == "error":
                await self.push_error(
                    error_msg=data.get("message", "Unknown Sarvam STT error")
                )

        except Exception as e:
            logger.exception(f"Sarvam STT error: {e}")
