"""
Sarvam AI Text-to-Speech (Bulbul) service.

Converts text to speech using Sarvam AI's REST API with support for
11 Indian languages and 30+ voices.

REST endpoint: POST https://api.sarvam.ai/text-to-speech
Authentication: api-subscription-key header
Response: base64-encoded PCM audio
"""

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
)
from pipecat.services.tts_service import TTSService
from pipecat.utils.tracing.service_decorators import traced_tts

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

# Supported language codes for Bulbul
SUPPORTED_LANGUAGES = {
    "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN",
    "kn-IN", "ml-IN", "mr-IN", "pa-IN", "od-IN", "en-IN",
}


class SarvamTTSService(TTSService):
    """Sarvam AI text-to-speech service (Bulbul).

    Generates speech from text using Sarvam AI's Bulbul model, optimised
    for Indian languages including code-mixed text (e.g. Hinglish).

    Supported models:
        - bulbul:v3  - Latest, 11 languages, 30+ voices (recommended)
        - bulbul:v2  - Legacy, pitch/loudness control

    Supported languages (bulbul:v3):
        hi-IN, bn-IN, ta-IN, te-IN, gu-IN, kn-IN,
        ml-IN, mr-IN, pa-IN, od-IN, en-IN
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
        """Initialize the Sarvam TTS service.

        Args:
            api_key: Sarvam AI API subscription key.
            model: Bulbul model version (default: bulbul:v3).
            target_language_code: BCP-47 code for output language (default: hi-IN).
            speaker: Voice name (e.g. meera, arvind, amol). Default: meera.
            pace: Speech speed multiplier 0.5–2.0 (default: 1.0).
            sample_rate: Output audio sample rate in Hz (default: 16000).
        """
        super().__init__(sample_rate=sample_rate, **kwargs)

        self._api_key = api_key
        self._model = model
        self._target_language_code = target_language_code
        self._speaker = speaker
        self._pace = pace
        self._sample_rate = sample_rate

        if target_language_code not in SUPPORTED_LANGUAGES:
            logger.warning(
                f"Language '{target_language_code}' may not be supported by Bulbul. "
                f"Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
            )

    def can_generate_metrics(self) -> bool:
        return True

    @traced_tts
    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        logger.debug(f"Sarvam TTS: generating speech for: {text[:60]}...")

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
                "output_audio_codec": "linear16",  # raw PCM, no decoding overhead
            }

            headers = {
                "api-subscription-key": self._api_key,
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    SARVAM_TTS_URL, json=payload, headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Sarvam TTS error {response.status}: {error_text}")
                        yield ErrorFrame(f"Sarvam TTS error {response.status}: {error_text}")
                        return

                    result = await response.json()
                    audios = result.get("audios", [])

                    if not audios:
                        logger.error("Sarvam TTS: empty audio response")
                        yield ErrorFrame("Sarvam TTS returned no audio")
                        return

                    await self.stop_ttfb_metrics()

                    for audio_b64 in audios:
                        audio_bytes = base64.b64decode(audio_b64)
                        yield TTSAudioRawFrame(
                            audio=audio_bytes,
                            sample_rate=self._sample_rate,
                            num_channels=1,
                        )

            yield TTSStoppedFrame()

        except Exception as e:
            logger.exception(f"Sarvam TTS: error generating speech: {e}")
            yield ErrorFrame(f"Sarvam TTS error: {str(e)}")
