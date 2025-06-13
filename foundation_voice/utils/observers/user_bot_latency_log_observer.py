import time
from typing import Optional

from loguru import logger

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    Frame,
)
from pipecat.observers.base_observer import BaseObserver
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class UserBotLatencyLogObserver(BaseObserver):
    """Observer that logs the time between when the user stops speaking
    and when the bot starts speaking.
    This measures the total response time from the user's perspective.
    """

    def __init__(self):
        super().__init__()
        self._processed_frames = set()
        self._user_stopped_time: Optional[float] = None

    async def on_push_frame(
        self,
        src: FrameProcessor,
        dst: FrameProcessor,
        frame: Frame,
        direction: FrameDirection,
        timestamp: int,
    ):
        if direction != FrameDirection.DOWNSTREAM:
            return

        if frame.id in self._processed_frames:
            return

        self._processed_frames.add(frame.id)

        # Reset state when user starts speaking
        if isinstance(frame, UserStartedSpeakingFrame):
            self._user_stopped_time = None

        # When user stops speaking, note the time
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._user_stopped_time = time.time()

        # When bot starts speaking, log the time since user stopped speaking
        elif (
            isinstance(frame, BotStartedSpeakingFrame)
            and self._user_stopped_time is not None
        ):
            response_time = time.time() - self._user_stopped_time
            logger.debug(
                f"⏱️ BOT RESPONSE TIME (user stopped to bot speaking): {response_time:.3f}s"
            )
            self._user_stopped_time = None
