import json

from loguru import logger
from typing import AsyncGenerator, Optional

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService
from pipecat.utils.tracing.service_decorators import traced_tts

try:
    from smallestai.waves import AsyncWavesClient
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error(
        "In order to use SmallestAI TTS, please install the smallestai package. pip install smallestai"
    )
    raise Exception(f"Missing module: {e}")


class SmallestTTSService(TTSService):
    def __init__(
        self,
        *,
        api_key: str,
        sample_rate: Optional[int] = 24000,
        voice_id: Optional[str] = None,
        model: Optional[str] = "lightning-v2",
        speed: Optional[float] = 1.0,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._sample_rate = sample_rate
        self._speed = speed
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model
        self._create_client()

    def _create_client(self):
        self._client = AsyncWavesClient(api_key=self._api_key, model=self._model)

        if self._voice_id:
            voices = json.loads(self._client.get_voices())
            voice_ids = [voice["voiceId"] for voice in voices["voices"]]
            # logger.info(f"Available voices: {voice_ids}")
            if self._voice_id not in voice_ids:
                logger.warning(
                    f"Voice ID '{self._voice_id}' not found among available voices. Defaulting to 'emily'"
                )
                self._voice_id = "emily"
            self._client.opts.voice_id = self._voice_id

        else:
            self._voice_id = "emily"
            self._client.opts.voice_id = self._voice_id

    def can_generate_metrics(self) -> bool:
        return True

    @traced_tts
    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        logger.debug(f"{self}: Generating TTS for text: {text}")
        try:
            await self.start_ttfb_metrics()
            yield TTSStartedFrame()

            async with AsyncWavesClient(
                api_key=self._api_key, voice_id=self._voice_id, speed=self._speed
            ) as tts_client:
                audio_stream = await tts_client.synthesize(text=text, stream=True)
                async for audio_chunk in audio_stream:
                    await self.stop_ttfb_metrics()
                    if audio_chunk:
                        yield TTSAudioRawFrame(
                            audio=audio_chunk,
                            sample_rate=self._sample_rate,
                            num_channels=1,
                        )

            yield TTSStoppedFrame()
        except Exception as e:
            logger.exception(f"Error during TTS processing: {e}")
            yield ErrorFrame(f"Error generating audio: {str(e)}")
