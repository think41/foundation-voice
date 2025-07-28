import asyncio
from loguru import logger
from pipecat.frames.frames import LLMMessagesFrame, EndFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

class LLMIidleProcessor(FrameProcessor):
    def __init__(self, *, tries: int = 2, timeout: float = 0.2, **kwargs):
        """
        Watches for no LLM activity (no LLMMessagesFrame) for `timeout` seconds
        and invokes `_on_llm_idle(retry_count)`. Retries up to `tries` times,
        then emits EndFrame.
        """
        super().__init__(**kwargs)
        self.tries = tries
        self.timeout = timeout
        self._retry_count = 0
        self._idle_task = None
        self._last_llm_time = asyncio.get_event_loop().time()

        logger.debug(f"🔧 LLMIidleProcessor initialized (tries={tries}, timeout={timeout}s)")

    async def process_frame(self, frame, direction):
        # If the LLM is about to stream or has new chunks, reset our idle timer
        if isinstance(frame, LLMMessagesFrame) and direction == FrameDirection.DOWNSTREAM:
            now = asyncio.get_event_loop().time()
            logger.debug(f"⏱️ Received LLMMessagesFrame, resetting idle timer (was {now - self._last_llm_time:.2f}s ago)")
            self._last_llm_time = now

            # Cancel existing watcher if any
            if self._idle_task and not self._idle_task.done():
                logger.debug("❌ Cancelling pending idle-watch task")
                self._idle_task.cancel()

            # Schedule a fresh idle-watch
            logger.debug("🚀 Scheduling new idle-watch task")
            self._idle_task = asyncio.create_task(self._watch_for_idle())

        # Always forward frames
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

    async def _watch_for_idle(self):
        try:
            logger.debug(f"⏲️ Idle-watch sleeping for {self.timeout}s")
            await asyncio.sleep(self.timeout)

            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_llm_time
            logger.debug(f"⏳ Idle-watch woke up; elapsed since last LLM: {elapsed:.2f}s")

            if elapsed >= self.timeout:
                logger.warning(f"⚠️ LLM idle detected ({elapsed:.2f}s > {self.timeout}s)")
                keep_going = await self._on_llm_idle(self._retry_count)
                self._retry_count += 1

                if keep_going and self._retry_count <= self.tries:
                    logger.info(f"🔁 Retry {self._retry_count}/{self.tries}: scheduling next idle-watch")
                    self._idle_task = asyncio.create_task(self._watch_for_idle())
                else:
                    logger.error("✋ Max retries reached or callback declined → ending stream")
                    await self.push_frame(EndFrame(), FrameDirection.DOWNSTREAM)

        except asyncio.CancelledError:
            logger.debug("❌ Idle-watch task was cancelled (new LLM activity)")

    async def _on_llm_idle(self, retry_count: int) -> bool:
        """
        Called when LLM has been idle for `timeout` seconds.
        Return True to poke the LLM again, False to stop.
        """
        if retry_count < self.tries:
            msg = {
                "role": "system",
                "content": "The assistant seems stuck—letting the model know to continue. Meanwhile, let the user know that you're still thinking."
            }
            logger.info(f"📨 Idle poke #{retry_count+1}: {msg['content']}")
        else:
            msg = {
                "role": "system",
                "content": "The assistant still isn't responding. Ending the session now."
            }
            logger.error(f"📨 Final idle poke #{retry_count+1}: {msg['content']}")

        await self.push_frame(LLMMessagesFrame([msg]), FrameDirection.DOWNSTREAM)
        return retry_count < self.tries
