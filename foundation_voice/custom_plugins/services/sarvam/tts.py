import base64
from typing import AsyncGenerator, Optional

import aiohttp
from loguru import logger

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    StartFrame,
    EndFrame,
    CancelFrame,
)
from pipecat.services.tts_service import TTSService
from pipecat.utils.tracing.service_decorators import traced_tts


SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


class SarvamTTSService(TTSService):
    """
    Optimized Sarvam AI TTS service with persistent HTTP session
    and reduced per-turn latency.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "bulbul:v3",
        target_language_code: str = "hi-IN",
        speaker: str = "meera",
        pace: float = 1.0,
        sample_rate: int = 16000,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)

        self._api_key = api_key
        self._model = model
        self._target_language_code = target_language_code
        self._speaker = speaker
        self._pace = pace
        self._sample_rate = sample_rate

        self._session: Optional[aiohttp.ClientSession] = None

    # -----------------------------
    # Lifecycle
    # -----------------------------

    async def start(self, frame: StartFrame):
        await super().start(frame)

        if not self._session:
            timeout = aiohttp.ClientTimeout(total=60)

            # Keep connections alive and reusable
            connector = aiohttp.TCPConnector(
                limit=20,
                ttl_dns_cache=300,
                keepalive_timeout=30,
            )

            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )

            logger.debug("Sarvam TTS: HTTP session initialized")

    async def stop(self, frame: EndFrame):
        await super().stop(frame)
        await self._close_session()

    async def cancel(self, frame: CancelFrame):
        await super().cancel(frame)
        await self._close_session()

    async def _close_session(self):
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("Sarvam TTS: HTTP session closed")

    def can_generate_metrics(self) -> bool:
        return True

    # -----------------------------
    # TTS Execution
    # -----------------------------

    @traced_tts
    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:

        if not self._session:
            yield ErrorFrame("Sarvam TTS session not initialized")
            return

        try:
            await self.start_ttfb_metrics()
            yield TTSStartedFrame()

            payload = {
                "text": text,
                "target_language_code": self._target_language_code,
                "model": self._model,
                "speaker": self._speaker,
                "pace": self._pace,
                "speech_sample_rate": self._sample_rate,
                "output_audio_codec": "linear16",  # raw PCM
            }

            headers = {
                "api-subscription-key": self._api_key,
                "Content-Type": "application/json",
            }

            async with self._session.post(
                SARVAM_TTS_URL,
                json=payload,
                headers=headers,
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f"Sarvam TTS error {response.status}: {error_text}"
                    )
                    yield ErrorFrame(
                        f"Sarvam TTS error {response.status}: {error_text}"
                    )
                    return

                # Stop TTFB as soon as headers arrive
                await self.stop_ttfb_metrics()

                result = await response.json()
                audios = result.get("audios", [])

                if not audios:
                    yield ErrorFrame("Sarvam TTS returned no audio")
                    return

                # Emit audio immediately
                for audio_b64 in audios:
                    try:
                        audio_bytes = base64.b64decode(audio_b64)

                        yield TTSAudioRawFrame(
                            audio=audio_bytes,
                            sample_rate=self._sample_rate,
                            num_channels=1,
                        )
                    except Exception as decode_error:
                        logger.error(f"Audio decode error: {decode_error}")
                        yield ErrorFrame("Audio decode failed")

            yield TTSStoppedFrame()

        except Exception as e:
            logger.exception(f"Sarvam TTS error: {e}")
            yield ErrorFrame(f"Sarvam TTS error: {str(e)}")