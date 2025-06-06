from typing import Any, Optional

from pipecat.frames.frames import LLMMessagesFrame, TTSSpeakFrame
from pipecat.processors.user_idle_processor import UserIdleProcessor


class IdleProcessor():
    def __init__(
        self, 
        context_aggregator: Any,
        tries: Optional[int] = 1,
        timeout: Optional[int] = 10
    ):
        self.tries = tries
        self.context_aggregator = context_aggregator
        self.user_idle = UserIdleProcessor(callback=self.handle_user_idle, timeout=timeout)

    def set_task(self, task):
        self.task = task

    async def handle_user_idle(self, user_idle: UserIdleProcessor, retry_count: int):
        if retry_count < self.tries:
            self.context_aggregator.user().add_messages([
                {
                    "role": "system",
                    "content": "The user has been quiet. Politely and briefly ask if they're still there."
                }
            ])
            await user_idle.push_frame(LLMMessagesFrame(self.context_aggregator.user().get_messages()))
            return True
        elif retry_count == self.tries:
            self.context_aggregator.user().add_messages([
                {
                    "role": "system",
                    "content": "The user has been quiet for too long. Politely and briefly inform them that you'll end the call and they can connect back whenever they're free."
                }
            ])
            await user_idle.push_frame(LLMMessagesFrame(self.context_aggregator.user().get_messages()))
            return True
        else:
            await self.task.stop_when_done() 
            return False

    def __call__(self):
        return self.user_idle