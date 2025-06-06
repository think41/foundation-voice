from loguru import logger
from typing import AsyncGenerator, Optional

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame
) 
from pipecat.services.tts_service import TTSService

try:
    from smallestai.waves import AsyncWavesClient
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error("In order to use SmallestAI TTS, please install the smallestai package. pip install smallestai")
    raise Exception(f"Missing module: {e}")


class SmallestTTSService(TTSService):
    def __init__(
        self,
        *,
        api_key: str,
        sample_rate: Optional[int] = 24000,
        **kwargs
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._sample_rate = sample_rate
        self._api_key = api_key

    def can_generate_metrics(self) -> bool:
        return True

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        logger.debug(f"{self}: Generating TTS for text: {text}")
        try:
            await self.start_ttfb_metrics()
            yield TTSStartedFrame()

            async with AsyncWavesClient(api_key=self._api_key) as tts_client:
                audio_stream = await tts_client.synthesize(text=text, stream=True)
                async for audio_chunk in audio_stream:
                    await self.stop_ttfb_metrics()
                    if audio_chunk:
                        yield TTSAudioRawFrame(
                            audio=audio_chunk,
                            sample_rate=self._sample_rate,
                            num_channels=1
                        )

            yield TTSStoppedFrame()
        except Exception as e:
            logger.exception(f"Error during TTS processing: {e}")
            yield ErrorFrame(f"Error generating audio: {str(e)}")
