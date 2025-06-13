from pipecat.frames.frames import LLMMessagesFrame, EndFrame
from pipecat.processors.user_idle_processor import (
    UserIdleProcessor as _OriginalUserIdleProcessor,
    UserIdleProcessor,
)


class UserIdleProcessor(_OriginalUserIdleProcessor):
    def __init__(self, *, tries: int = 3, timeout: float = 10, **kwargs):
        super().__init__(callback=self._handle_user_idle, timeout=timeout, **kwargs)
        self.tries = tries

    async def _handle_user_idle(self, processor: UserIdleProcessor, retry_count: int):
        if retry_count < self.tries:
            message = [
                {
                    "role": "system",
                    "content": "The user has been quiet. Politely and briefly ask if they're still there.",
                }
            ]
            await self.push_frame(LLMMessagesFrame(message))
            return True

        elif retry_count == self.tries:
            message = [
                {
                    "role": "system",
                    "content": "The user has been quiet for too long. Inform them you'll end the call and they can reconnect later.",
                }
            ]
            await self.push_frame(LLMMessagesFrame(message))
            return True

        else:
            await self.push_frame(EndFrame())
            return False
